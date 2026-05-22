"""Generate suite-level positive and negative test cases for NRF operations."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from llm_prompts.llm import GPT


CANONICAL_NF_INSTANCE_ID = "550e8400-e29b-41d4-a716-446655440000"
CANONICAL_SUBSCRIPTION_ID = "{subscriptionId}"

CANONICAL_REGISTER_STEP: Dict[str, Any] = {
    "path": "/nnrf-nfm/v1/nf-instances/{nfInstanceId}",
    "method": "PUT",
    "headers": {
        "Content-Type": "application/json",
    },
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
    "headers": {
        "Content-Type": "application/json",
    },
    "body": {
        "callbackReference": {
            "notifyUri": "https://example.client/callback",
        },
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


@dataclass
class OperationInfo:
    """Metadata for a single operation."""

    operation: str
    path: str
    method: str
    input_schema: Dict[str, Any]
    constraints: List[str]
    depends_on: List[str]


@dataclass
class TestFormat:
    """Container for the suite/test shape used in prompts."""

    suite_structure: Dict[str, Any]
    step_structure: Dict[str, Any]
    test_case_structure: Dict[str, Any]


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


class TestCaseGenerator:
    """Generate operation suites with one shared setup and cleanup."""

    def __init__(self, operation_schemas_file: Path, test_format_file: Path, output_dir: Path):
        self.operation_schemas_file = operation_schemas_file
        self.test_format_file = test_format_file
        self.output_dir = output_dir
        self.llm_client: Optional[GPT] = None
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

    def initialize_llm(self) -> None:
        self.llm_client = GPT(
            system_prompt=(
                "You are an expert in API testing. Generate only the requested JSON object "
                "and do not include markdown or commentary."
            ),
            max_retries=3,
            retry_delay_seconds=2.0,
        )

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
                    "headers": {
                        "Content-Type": "application/json",
                    },
                }
            )

        cleanup.append(
            {
                "path": "/nnrf-nfm/v1/nf-instances/{nfInstanceId}",
                "method": "DELETE",
                "headers": {
                    "Content-Type": "application/json",
                },
            }
        )
        return cleanup

    def create_test_generation_prompt(
        self,
        operation: OperationInfo,
        constraint: str,
        shared_setup: List[Dict[str, Any]],
        shared_cleanup: List[Dict[str, Any]],
        constraint_index: int,
    ) -> str:
        if not self.test_format:
            raise RuntimeError("Test format not loaded")

        suite_format_json = json.dumps(self.test_format.suite_structure, indent=2)
        step_format_json = json.dumps(self.test_format.step_structure, indent=2)
        test_format_json = json.dumps(self.test_format.test_case_structure, indent=2)
        setup_json = json.dumps(shared_setup, indent=2)
        cleanup_json = json.dumps(shared_cleanup, indent=2)

        return f"""Generate exactly two test cases for the operation below: one positive and one negative.

Operation: {operation.operation}
Path: {operation.path}
Method: {operation.method}
Constraint index: {constraint_index}

Shared setup executed before every test in this suite:
{setup_json}

Shared cleanup executed after every test in this suite:
{cleanup_json}

Input Schema:
{json.dumps(operation.input_schema, indent=2)}

Constraint to violate:
{constraint}

Suite format:
{suite_format_json}

Step format:
{step_format_json}

Target suite/test format:
{test_format_json}

Rules:
1. Return only a single JSON object with exactly these keys: positive_test_case, negative_test_case.
2. Each test case object may include only: name, constraint, method, path, headers, body.
3. Do not include request, violated_constraints, driving_state, setup, cleanup, description, notes, or id.
4. The positive test case must satisfy the supplied constraint.
5. The negative test case must violate the supplied constraint.
6. Use the shared setup context instead of inventing test-specific prerequisite state.
7. Keep Content-Type as application/json unless the constraint requires otherwise.
8. The target NRF type should always be NRF.
9. Return valid JSON only, with no markdown or explanation.
"""

    def _standardize_generated_test_case(
        self,
        test_case: Dict[str, Any],
        test_id: str,
        constraint: str,
    ) -> Dict[str, Any]:
        standardized = {
            "id": test_id,
            "name": test_id,
            "constraint": constraint,
            "method": test_case.get("method", ""),
            "path": test_case.get("path", ""),
            "headers": test_case.get("headers", {}),
            "body": test_case.get("body"),
        }
        return standardized

    def generate_suite_test_pair(
        self,
        operation: OperationInfo,
        constraint: str,
        shared_setup: List[Dict[str, Any]],
        shared_cleanup: List[Dict[str, Any]],
        constraint_index: int,
    ) -> Optional[List[Dict[str, Any]]]:
        if not self.llm_client:
            raise RuntimeError("LLM client not initialized. Call initialize_llm() first.")

        prompt = self.create_test_generation_prompt(
            operation,
            constraint,
            shared_setup,
            shared_cleanup,
            constraint_index,
        )
        try:
            response_text = self.llm_client.ask_llm(prompt, use_history=False)
        except Exception as exc:
            print(f"  → Error calling LLM: {exc}", flush=True)
            return None

        parsed = _parse_json_object(response_text)
        if not parsed:
            return None

        positive = parsed.get("positive_test_case")
        negative = parsed.get("negative_test_case")
        if not isinstance(positive, dict) or not isinstance(negative, dict):
            print("  → LLM response did not include both positive_test_case and negative_test_case", flush=True)
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
                print(f"  → Failed to parse test pair from LLM response for constraint {idx}", flush=True)
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

        print("[*] Initializing LLM client...", flush=True)
        self.initialize_llm()
        print("[*] LLM client initialized", flush=True)

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


def main() -> None:
    script_dir = Path(__file__).resolve().parent.parent
    operation_schemas_file = script_dir / "data" / "generated" / "operation_schemas.json"
    test_format_file = script_dir / "data" / "config" / "test_format.json"
    output_dir = script_dir / "data" / "generated"

    if not test_format_file.exists():
        raise FileNotFoundError(f"test_format.json not found at {test_format_file}")

    generator = TestCaseGenerator(operation_schemas_file, test_format_file, output_dir)
    generator.generate_all_test_cases()


if __name__ == "__main__":
    main()
