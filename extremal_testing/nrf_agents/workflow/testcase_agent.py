"""Test-case generation agent for NRF operations."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from nrf_agents.models.common import OperationInfo, TestFormat
from nrf_agents.prompts.test_cases import build_test_case_prompt
from nrf_agents.workflow.sdk import run_text_agent

CANONICAL_NF_INSTANCE_ID = "550e8400-e29b-41d4-a716-446655440000"
CANONICAL_SUBSCRIPTION_ID = "{subscriptionId}"

CANONICAL_REGISTER_STEP: Dict[str, Any] = {
    "path": "/nnrf-nfm/v1/nf-instances/{nfInstanceId}",
    "method": "PUT",
    "headers": {"Content-Type": "application/json"},
    "body": {
        "nfInstanceId": CANONICAL_NF_INSTANCE_ID,
        "nfType": "NRF",
        "nfStatus": "REGISTERED",
        "fqdn": "nrf.example.3gppnetwork.org",
    },
}

CANONICAL_SUBSCRIBE_STEP: Dict[str, Any] = {
    "path": "/nnrf-nfm/v1/subscriptions",
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "body": {
        "callbackReference": {"notifyUri": "https://example.client/callback"},
        "eventTypes": ["NF_STATUS_CHANGE"],
        "duration": 3600,
        "targetNfType": "NRF",
    },
}

SUBSCRIPTION_OPERATION_NAMES = {
    "NFStatusSubscribe",
    "NFStatusNotify",
    "NFStatusUnsubscribe",
}

REGISTER_DEPENDENT_OPERATION_NAMES = {
    "NFUpdate",
    "NFDeregister",
    "NFListRetrieval",
    "NFProfileRetrieval",
    "NFStatusSubscribe",
    "NFStatusNotify",
    "NFStatusUnsubscribe",
}


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    cleaned = _strip_code_fences(text)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        print(f"Warning: Failed to parse LLM response as JSON: {exc}", flush=True)
        print(f"Response text: {cleaned[:500]}...", flush=True)
        return None
    return parsed if isinstance(parsed, dict) else None


class TestCaseAgent:
    """Generate operation suites with one shared setup and cleanup."""

    def __init__(
        self,
        operation_schemas_file: Path = ROOT_DIR / "json" / "operation_schemas.json",
        test_format_file: Path = ROOT_DIR / "json" / "config" / "test_format.json",
        output_dir: Path = ROOT_DIR / "json" / "testcases",
    ):
        self.operation_schemas_file = operation_schemas_file
        self.test_format_file = test_format_file
        self.output_dir = output_dir
        self.test_format: Optional[TestFormat] = None
        self.operations: List[OperationInfo] = []

    def load_test_format(self) -> TestFormat:
        with open(self.test_format_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TestFormat(
            suite_structure=data.get("suite_structure", {}),
            step_structure=data.get("step_structure", {}),
            test_case_structure=data.get("test_case_structure", {}),
        )

    def load_operations(self) -> List[OperationInfo]:
        with open(self.operation_schemas_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        operations: List[OperationInfo] = []
        for op_data in data:
            operations.append(
                OperationInfo(
                    operation=op_data.get("operation", ""),
                    path=op_data.get("path", ""),
                    method=op_data.get("method", ""),
                    input_schema=op_data.get("input_schema", {}),
                    constraints=op_data.get("constraints", []),
                    depends_on=op_data.get("depends_on", []),
                )
            )
        return operations

    def build_shared_setup(self, operation: OperationInfo) -> List[Dict[str, Any]]:
        if operation.operation == "NFRegister":
            return []

        setup: List[Dict[str, Any]] = []
        if operation.operation in REGISTER_DEPENDENT_OPERATION_NAMES:
            setup.append(dict(CANONICAL_REGISTER_STEP))

        if operation.operation in SUBSCRIPTION_OPERATION_NAMES:
            setup.append(dict(CANONICAL_SUBSCRIBE_STEP))

        return setup

    def build_shared_cleanup(self, operation: OperationInfo) -> List[Dict[str, Any]]:
        cleanup: List[Dict[str, Any]] = []
        if operation.operation in SUBSCRIPTION_OPERATION_NAMES:
            cleanup.append(
                {
                    "path": f"/nnrf-nfm/v1/subscriptions/{CANONICAL_SUBSCRIPTION_ID}",
                    "method": "DELETE",
                    "headers": {"Content-Type": "application/json"},
                }
            )

        cleanup.append(
            {
                "path": "/nnrf-nfm/v1/nf-instances/{nfInstanceId}",
                "method": "DELETE",
                "headers": {"Content-Type": "application/json"},
            }
        )
        return cleanup

    def _standardize_generated_test_case(
        self,
        test_case: Dict[str, Any],
        test_id: str,
        constraint: str,
    ) -> Dict[str, Any]:
        return {
            "id": test_id,
            "name": test_id,
            "constraint": constraint,
            "method": test_case.get("method", ""),
            "path": test_case.get("path", ""),
            "headers": test_case.get("headers", {}),
            "body": test_case.get("body"),
        }

    def generate_suite_test_pair(
        self,
        operation: OperationInfo,
        constraint: str,
        shared_setup: List[Dict[str, Any]],
        shared_cleanup: List[Dict[str, Any]],
        constraint_index: int,
    ) -> Optional[List[Dict[str, Any]]]:
        if not self.test_format:
            raise RuntimeError("Test format not loaded")

        prompt = build_test_case_prompt(
            operation,
            constraint,
            shared_setup,
            shared_cleanup,
            self.test_format,
            constraint_index,
        )

        try:
            response_text = run_text_agent(
                agent_name="NRF Test Case Agent",
                instructions=(
                    "You are an expert in API testing. Generate only the requested JSON object "
                    "and do not include markdown or commentary."
                ),
                prompt=prompt,
                workflow_name="NRF Test Case Generation",
            )
        except Exception as exc:
            print(f"  → Error calling agent: {exc}", flush=True)
            return None

        parsed = _parse_json_object(response_text)
        if not parsed:
            return None

        positive = parsed.get("positive_test_case")
        negative = parsed.get("negative_test_case")
        if not isinstance(positive, dict) or not isinstance(negative, dict):
            print("  → Agent response did not include both positive_test_case and negative_test_case", flush=True)
            return None

        positive_id = f"tc_{constraint_index}_pos"
        negative_id = f"tc_{constraint_index}_neg"
        return [
            self._standardize_generated_test_case(positive, positive_id, constraint),
            self._standardize_generated_test_case(negative, negative_id, constraint),
        ]

    def generate_operation_suite(self, operation: OperationInfo) -> Optional[Dict[str, Any]]:
        if not operation.constraints:
            print(f"  → No constraints found for {operation.operation}, skipping", flush=True)
            return None

        shared_setup = self.build_shared_setup(operation)
        shared_cleanup = self.build_shared_cleanup(operation)
        print(f"  → Shared setup steps: {len(shared_setup)}", flush=True)
        print(f"  → Shared cleanup steps: {len(shared_cleanup)}", flush=True)
        print(f"  → Generating {len(operation.constraints) * 2} test case(s) with one shared setup...", flush=True)

        tests: List[Dict[str, Any]] = []
        for idx, constraint in enumerate(operation.constraints, 1):
            print(f"  → Processing constraint {idx}/{len(operation.constraints)}...", flush=True)
            test_pair = self.generate_suite_test_pair(operation, constraint, shared_setup, shared_cleanup, idx)
            if not test_pair:
                print(f"  → Failed to parse test pair from agent response for constraint {idx}", flush=True)
                continue
            tests.extend(test_pair)
            print(f"  → Generated positive and negative test cases for constraint {idx}", flush=True)

        if not tests:
            return None

        return {
            "operation": operation.operation,
            "path": operation.path,
            "method": operation.method,
            "setup": shared_setup,
            "cleanup": shared_cleanup,
            "tests": tests,
        }

    def save_operation_suite(self, operation_name: str, suite: Dict[str, Any]) -> None:
        output_file = self.output_dir / f"{operation_name}_tests.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(suite, f, indent=2, ensure_ascii=False)
        print(f"  → Saved suite with {len(suite.get('tests', []))} test case(s) to {output_file.name}", flush=True)

    def generate_all_test_cases(self) -> None:
        print(f"[*] Loading test format from {self.test_format_file.name}...", flush=True)
        self.test_format = self.load_test_format()
        print("[*] Test format loaded", flush=True)

        print(f"[*] Loading operations from {self.operation_schemas_file.name}...", flush=True)
        self.operations = self.load_operations()
        print(f"[*] Loaded {len(self.operations)} operation(s)", flush=True)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        for idx, operation in enumerate(self.operations, 1):
            print(f"\n[{idx}/{len(self.operations)}] Processing {operation.operation}...", flush=True)
            print(f"  → Path: {operation.method} {operation.path}", flush=True)

            suite = self.generate_operation_suite(operation)
            if suite:
                self.save_operation_suite(operation.operation, suite)
            else:
                print(f"  → No test suite generated for {operation.operation}", flush=True)

        print("\n[✓] Test case generation complete", flush=True)

    def run(self) -> None:
        self.generate_all_test_cases()


def main() -> None:
    TestCaseAgent().run()


if __name__ == "__main__":
    main()
