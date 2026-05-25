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
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extremal_testing.nrf_agents.models.common import OperationInfo, TestFormat
from extremal_testing.nrf_agents.prompts.test_cases import build_test_case_chunk_prompt
from extremal_testing.nrf_agents.workflow.sdk import run_text_agent

CANONICAL_NF_INSTANCE_ID = "550e8400-e29b-41d4-a716-446655440000"
CANONICAL_SUBSCRIPTION_ID = "{subscriptionId}"
CONSTRAINT_CHUNK_SIZE = 10
REQUIRED_TEST_FIELDS = {"name", "constraint", "method", "path", "headers"}

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
        "nfStatusNotificationUri": "https://example.client/callback",
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


class TestAgent:
    """Generate operation suites with one shared setup and cleanup."""

    def __init__(
        self,
        constraints_dir: Path = ROOT_DIR / "json" / "constraints",
        metadata_file: Path = ROOT_DIR / "json" / "AllOpsMetaData.json",
        test_format_file: Path = ROOT_DIR / "json" / "config" / "test_format.json",
        output_dir: Path = ROOT_DIR / "json" / "testcases",
    ):
        self.constraints_dir = constraints_dir
        self.metadata_file = metadata_file
        self.test_format_file = test_format_file
        self.output_dir = output_dir
        self.test_format: Optional[TestFormat] = None
        self.operations: List[OperationInfo] = []
        self.operation_metadata_by_name: Dict[str, Dict[str, Any]] = {}

    def load_test_format(self) -> TestFormat:
        with open(self.test_format_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TestFormat(
            suite_structure=data.get("suite_structure", {}),
            step_structure=data.get("step_structure", {}),
            test_case_structure=data.get("test_case_structure", {}),
        )

    def load_metadata_index(self) -> Dict[str, Dict[str, Any]]:
        with open(self.metadata_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        metadata_by_name: Dict[str, Dict[str, Any]] = {}
        for op_data in data:
            name = str(op_data.get("Operation", "")).strip()
            if name:
                metadata_by_name[name] = op_data
        return metadata_by_name

    def load_operations(self) -> List[OperationInfo]:
        if not self.constraints_dir.exists():
            raise FileNotFoundError(f"Constraints directory does not exist: {self.constraints_dir}")

        self.operation_metadata_by_name = self.load_metadata_index()
        constraint_files = sorted(
            path for path in self.constraints_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json"
        )

        operations: List[OperationInfo] = []
        for file_path in constraint_files:
            operation_name = file_path.stem
            metadata = self.operation_metadata_by_name.get(operation_name)
            if not metadata:
                print(f"  → Skipping constraint file with no matching metadata: {file_path.name}", flush=True)
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                op_data = json.load(f)

            raw_constraints = op_data.get("constraints", [])
            normalized_constraints: List[Dict[str, Any]] = []
            if isinstance(raw_constraints, list):
                for idx, constraint in enumerate(raw_constraints, 1):
                    if isinstance(constraint, dict):
                        constraint_text = constraint.get("constraint") or constraint.get("text") or constraint.get("value")
                        schema_id = str(constraint.get("schema_id", "unknown")).strip() or "unknown"
                    else:
                        constraint_text = str(constraint)
                        schema_id = f"legacy_constraint_{idx}"

                    if not isinstance(constraint_text, str) or not constraint_text.strip():
                        continue

                    normalized_constraints.append(
                        {
                            "schema_id": schema_id,
                            "constraint": constraint_text.strip(),
                        }
                    )

            operations.append(
                OperationInfo(
                    operation=operation_name,
                    path=metadata.get("Paths", ""),
                    method=metadata.get("Method", ""),
                    input_schema=op_data.get("input_schema", {}),
                    constraints=normalized_constraints,
                    depends_on=metadata.get("DependsOn", []),
                    definitions=op_data.get("definitions", {}),
                )
            )
        return operations

    @staticmethod
    def chunk_constraints(constraints: List[Dict[str, Any]], chunk_size: int = CONSTRAINT_CHUNK_SIZE) -> List[List[Dict[str, Any]]]:
        return [constraints[index : index + chunk_size] for index in range(0, len(constraints), chunk_size)]

    @staticmethod
    def _definition_key_from_ref(ref: str) -> Optional[str]:
        prefix = "#/definitions/"
        if not ref.startswith(prefix):
            return None
        return ref[len(prefix):]

    def _resolve_local_ref(self, schema: Dict[str, Any], definitions: Dict[str, Any]) -> Dict[str, Any]:
        ref = schema.get("$ref")
        if not isinstance(ref, str):
            return schema
        definition_key = self._definition_key_from_ref(ref)
        if not definition_key:
            return schema
        definition = definitions.get(definition_key)
        return definition if isinstance(definition, dict) else schema

    def _collect_referenced_definitions(
        self,
        node: Any,
        definitions: Dict[str, Any],
        collected: Dict[str, Any],
        seen: Optional[set[str]] = None,
    ) -> None:
        seen = seen or set()
        if isinstance(node, list):
            for item in node:
                self._collect_referenced_definitions(item, definitions, collected, seen)
            return
        if not isinstance(node, dict):
            return

        ref = node.get("$ref")
        if isinstance(ref, str):
            definition_key = self._definition_key_from_ref(ref)
            if definition_key and definition_key not in seen:
                definition = definitions.get(definition_key)
                if isinstance(definition, dict):
                    seen.add(definition_key)
                    collected[definition_key] = definition
                    self._collect_referenced_definitions(definition, definitions, collected, seen)

        for value in node.values():
            self._collect_referenced_definitions(value, definitions, collected, seen)

    def _find_parameter_schema_slice(self, operation: OperationInfo, schema_id: str) -> Optional[Dict[str, Any]]:
        try:
            location, name = schema_id.split(".", 1)
        except ValueError:
            return None

        parameters = operation.input_schema.get("parameters", [])
        if not isinstance(parameters, list):
            return None

        for parameter in parameters:
            if not isinstance(parameter, dict):
                continue
            if parameter.get("in") == location and parameter.get("name") == name:
                referenced_definitions: Dict[str, Any] = {}
                self._collect_referenced_definitions(parameter, operation.definitions, referenced_definitions)
                return {
                    "schema_id": schema_id,
                    "parameter": parameter,
                    "definitions": referenced_definitions,
                }
        return None

    def _request_body_content_schemas(self, operation: OperationInfo) -> Dict[str, Dict[str, Any]]:
        request_body = operation.input_schema.get("request_body", {})
        if not isinstance(request_body, dict):
            return {}
        content = request_body.get("content", {})
        if not isinstance(content, dict):
            return {}

        schemas: Dict[str, Dict[str, Any]] = {}
        for content_type, content_obj in content.items():
            if not isinstance(content_obj, dict):
                continue
            schema = content_obj.get("schema")
            if isinstance(schema, dict):
                schemas[str(content_type)] = schema
        return schemas

    def _walk_request_schema_path(
        self,
        root_schema: Dict[str, Any],
        path_parts: List[str],
        definitions: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        current = root_schema
        for raw_part in path_parts:
            current = self._resolve_local_ref(current, definitions)
            part = raw_part.removesuffix("[]")

            properties = current.get("properties", {})
            if isinstance(properties, dict) and part in properties and isinstance(properties[part], dict):
                current = properties[part]
            else:
                return None

            if raw_part.endswith("[]"):
                current = self._resolve_local_ref(current, definitions)
                items = current.get("items")
                if not isinstance(items, dict):
                    return None
                current = items
        return current

    def _find_request_schema_slice(self, operation: OperationInfo, schema_id: str) -> Optional[Dict[str, Any]]:
        content_schemas = self._request_body_content_schemas(operation)
        if not content_schemas:
            return None

        path_suffix = schema_id.removeprefix("request_body").lstrip(".")
        path_parts = [part for part in path_suffix.split(".") if part]
        content_slices: Dict[str, Dict[str, Any]] = {}
        referenced_definitions: Dict[str, Any] = {}

        for content_type, root_schema in content_schemas.items():
            target_schema = root_schema if not path_parts else self._walk_request_schema_path(
                root_schema,
                path_parts,
                operation.definitions,
            )
            if not isinstance(target_schema, dict):
                continue

            content_slices[content_type] = {
                "root_required": root_schema.get("required", []),
                "root_anyOf": root_schema.get("anyOf"),
                "target_schema": target_schema,
            }
            self._collect_referenced_definitions(target_schema, operation.definitions, referenced_definitions)

        if not content_slices:
            return None

        return {
            "schema_id": schema_id,
            "request_body": {
                "required": operation.input_schema.get("request_body", {}).get("required"),
                "content": content_slices,
            },
            "definitions": referenced_definitions,
        }

    def build_schema_slice(self, operation: OperationInfo, constraint: Dict[str, Any]) -> Dict[str, Any]:
        schema_id = str(constraint.get("schema_id", "unknown")).strip() or "unknown"
        if schema_id.startswith(("path.", "query.", "header.")):
            parameter_slice = self._find_parameter_schema_slice(operation, schema_id)
            if parameter_slice:
                return parameter_slice

        if schema_id == "request_body" or schema_id.startswith("request_body."):
            request_slice = self._find_request_schema_slice(operation, schema_id)
            if request_slice:
                return request_slice

        return {
            "schema_id": schema_id,
            "input_summary": {
                "parameters": operation.input_schema.get("parameters", []),
                "has_request_body": "request_body" in operation.input_schema,
            },
        }

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

    @staticmethod
    def _has_required_test_fields(test_case: Any) -> bool:
        if not isinstance(test_case, dict):
            return False
        return all(field in test_case for field in REQUIRED_TEST_FIELDS)

    def _standardize_chunk_test_case(
        self,
        test_case: Dict[str, Any],
        test_id: str,
        constraint: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "id": test_id,
            "name": str(test_case.get("name", test_id)),
            "constraint": str(test_case.get("constraint") or constraint.get("constraint", "")),
            "constraint_schema_id": str(constraint.get("schema_id", "unknown")),
            "method": test_case.get("method", ""),
            "path": test_case.get("path", ""),
            "headers": test_case.get("headers", {}),
            "body": test_case.get("body"),
        }

    def generate_suite_test_chunk(
        self,
        operation: OperationInfo,
        constraints: List[Dict[str, Any]],
        shared_setup: List[Dict[str, Any]],
        shared_cleanup: List[Dict[str, Any]],
        start_index: int,
    ) -> Optional[List[Dict[str, Any]]]:
        if not self.test_format:
            raise RuntimeError("Test format not loaded")

        constraint_items: List[Dict[str, Any]] = []
        constraints_by_id: Dict[str, Dict[str, Any]] = {}
        for offset, constraint in enumerate(constraints):
            constraint_number = start_index + offset
            constraint_id = f"constraint_{constraint_number}"
            constraints_by_id[constraint_id] = constraint
            constraint_items.append(
                {
                    "constraint_id": constraint_id,
                    "schema_id": constraint.get("schema_id", "unknown"),
                    "constraint": constraint.get("constraint", ""),
                    "schema_slice": self.build_schema_slice(operation, constraint),
                }
            )

        prompt = build_test_case_chunk_prompt(
            operation,
            constraint_items,
            shared_setup,
            shared_cleanup,
            self.test_format,
        )

        try:
            response_text = run_text_agent(
                agent_name="Test Agent",
                instructions=(
                    "You are an expert in API testing. Generate only the requested JSON object "
                    "and do not include markdown or commentary."
                ),
                prompt=prompt,
                workflow_name="Test Generation",
            )
        except Exception as exc:
            print(f"  → Error calling agent: {exc}", flush=True)
            return None

        parsed = _parse_json_object(response_text)
        if not parsed:
            return None

        test_pairs = parsed.get("test_pairs")
        if not isinstance(test_pairs, list):
            print("  → Agent response did not include a test_pairs array", flush=True)
            return None

        tests: List[Dict[str, Any]] = []
        for pair in test_pairs:
            if not isinstance(pair, dict):
                continue
            constraint_id = str(pair.get("constraint_id", "")).strip()
            constraint = constraints_by_id.get(constraint_id)
            if not constraint:
                continue

            positive = pair.get("positive_test_case")
            negative = pair.get("negative_test_case")
            if not self._has_required_test_fields(positive) or not self._has_required_test_fields(negative):
                continue

            constraint_number = constraint_id.removeprefix("constraint_")
            tests.append(self._standardize_chunk_test_case(positive, f"tc_{constraint_number}_pos", constraint))
            tests.append(self._standardize_chunk_test_case(negative, f"tc_{constraint_number}_neg", constraint))

        return tests

    def generate_operation_suite(self, operation: OperationInfo) -> Optional[Dict[str, Any]]:
        if not operation.constraints:
            print(f"  → No constraints found for {operation.operation}, skipping", flush=True)
            return None

        shared_setup = self.build_shared_setup(operation)
        shared_cleanup = self.build_shared_cleanup(operation)
        print(f"  → Shared setup steps: {len(shared_setup)}", flush=True)
        print(f"  → Shared cleanup steps: {len(shared_cleanup)}", flush=True)
        chunks = self.chunk_constraints(operation.constraints)
        print(
            f"  → Generating up to {len(operation.constraints) * 2} test case(s) "
            f"from {len(chunks)} chunk(s) of {CONSTRAINT_CHUNK_SIZE} constraint(s)...",
            flush=True,
        )

        tests: List[Dict[str, Any]] = []
        start_index = 1
        for chunk_index, constraint_chunk in enumerate(chunks, 1):
            print(
                f"  → Processing chunk {chunk_index}/{len(chunks)} "
                f"({len(constraint_chunk)} constraint(s))...",
                flush=True,
            )
            chunk_tests = self.generate_suite_test_chunk(
                operation,
                constraint_chunk,
                shared_setup,
                shared_cleanup,
                start_index,
            )
            if not chunk_tests:
                print(f"  → No valid tests generated for chunk {chunk_index}; skipping", flush=True)
                start_index += len(constraint_chunk)
                continue
            tests.extend(chunk_tests)
            print(f"  → Generated {len(chunk_tests)} test case(s) from chunk {chunk_index}", flush=True)
            start_index += len(constraint_chunk)

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
        output_file = self.output_dir / f"{operation_name}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(suite, f, indent=2, ensure_ascii=False)
        print(f"  → Saved suite with {len(suite.get('tests', []))} test case(s) to {output_file.name}", flush=True)

    def generate_all_test_cases(self) -> None:
        print(f"[*] Loading test format from {self.test_format_file.name}...", flush=True)
        self.test_format = self.load_test_format()
        print("[*] Test format loaded", flush=True)

        print(f"[*] Loading operations from {self.constraints_dir.name}...", flush=True)
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
    TestAgent().run()


if __name__ == "__main__":
    main()
