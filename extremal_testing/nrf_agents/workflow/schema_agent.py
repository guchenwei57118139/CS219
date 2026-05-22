"""Schema and constraint extraction agent for NRF operations."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extremal_testing.nrf_agents.models.common import OperationMetadata, OperationSchema
from extremal_testing.nrf_agents.prompts.schema import SYSTEM_PROMPT_SCHEMA_EXTRACTION, build_operation_schema_prompt
from extremal_testing.nrf_agents.workflow.sdk import run_text_agent


class OperationSchemaAgent:
    """Extract schemas and constraints for operations."""

    def __init__(
        self,
        metadata_file: Path = ROOT_DIR / "json" / "AllOpsMetaData.json",
        spec_file: Path = ROOT_DIR / "specs" / "original" / "TS29510_Nnrf_NFManagement.yaml",
        common_data_file: Path = ROOT_DIR / "specs" / "original" / "TS29571_CommonData.yaml",
        output_file: Path = ROOT_DIR / "json" / "operation_schemas.json",
    ):
        self.metadata_file = metadata_file
        self.spec_file = spec_file
        self.common_data_file = common_data_file
        self.output_file = output_file
        self.spec_doc: Dict[str, Dict] = {}
        self.common_data_doc: Dict[str, Dict] = {}
        self._ref_cache: Dict[str, Dict] = {}
        self._path_index: Dict[str, Dict[str, Dict]] = {}

    @staticmethod
    def _load_yaml_file(file_path: Path) -> Dict:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Expected {file_path} to contain a YAML mapping")
        return data

    def load_specification(self) -> None:
        self.spec_doc = self._load_yaml_file(self.spec_file)
        if self.common_data_file.exists():
            self.common_data_doc = self._load_yaml_file(self.common_data_file)
        else:
            self.common_data_doc = {}
        self._build_path_index()

    def _build_path_index(self) -> None:
        self._path_index = {}
        for path, path_item in self.spec_doc.get("paths", {}).items():
            if isinstance(path_item, dict):
                self._path_index[self._normalize_path_template(path)] = path_item

    @staticmethod
    def _normalize_path_template(path: str) -> str:
        return re.sub(r"\{[^}]+\}", "{}", str(path)).strip().lower()

    @staticmethod
    def _normalize_method(method: str) -> str:
        return str(method).strip().lower()

    @staticmethod
    def _decode_json_pointer_token(token: str) -> str:
        return token.replace("~1", "/").replace("~0", "~")

    def _get_doc_for_ref(self, ref: str) -> Optional[Dict]:
        if ref.startswith("#"):
            return self.spec_doc

        file_part = ref.split("#", 1)[0]
        if not file_part:
            return self.spec_doc

        ref_path = (self.spec_file.parent / file_part).resolve()
        if ref_path == self.common_data_file.resolve():
            if not self.common_data_doc:
                self.common_data_doc = self._load_yaml_file(self.common_data_file)
            return self.common_data_doc

        if not ref_path.exists():
            return None

        return self._load_yaml_file(ref_path)

    def _resolve_pointer(self, doc: Dict, pointer: str) -> Dict:
        target: object = doc
        if not pointer:
            return doc

        if pointer.startswith("/"):
            parts = [self._decode_json_pointer_token(part) for part in pointer.lstrip("/").split("/") if part]
        else:
            parts = [self._decode_json_pointer_token(part) for part in pointer.split("/") if part]

        for part in parts:
            if isinstance(target, dict):
                target = target.get(part)
            elif isinstance(target, list):
                index = int(part)
                target = target[index]
            else:
                raise KeyError(f"Cannot resolve pointer segment {part!r} in {pointer!r}")

        if not isinstance(target, dict):
            return {"value": target}
        return target

    def _resolve_ref(self, ref: str, stack: Optional[List[str]] = None) -> Dict:
        stack = stack or []
        if ref in self._ref_cache:
            return copy.deepcopy(self._ref_cache[ref])
        if ref in stack:
            return {"$ref": ref}

        doc = self._get_doc_for_ref(ref)
        if doc is None:
            return {"$ref": ref}
        _, pointer = ref.split("#", 1) if "#" in ref else (ref, "")
        resolved = copy.deepcopy(self._resolve_pointer(doc, pointer))
        resolved = self._resolve_schema_node(resolved, stack + [ref])
        self._ref_cache[ref] = copy.deepcopy(resolved)
        return resolved

    def _resolve_schema_node(self, node: object, stack: Optional[List[str]] = None) -> object:
        stack = stack or []
        if isinstance(node, list):
            return [self._resolve_schema_node(item, stack) for item in node]
        if not isinstance(node, dict):
            return node

        if "$ref" in node:
            resolved = self._resolve_ref(str(node["$ref"]), stack)
            merged = copy.deepcopy(resolved)
            for key, value in node.items():
                if key == "$ref":
                    continue
                merged[key] = self._resolve_schema_node(value, stack)
            return merged

        resolved_dict: Dict[str, object] = {}
        for key, value in node.items():
            if key in {"properties", "patternProperties", "dependentSchemas"} and isinstance(value, dict):
                resolved_dict[key] = {prop_key: self._resolve_schema_node(prop_value, stack) for prop_key, prop_value in value.items()}
            elif key in {"items", "additionalProperties", "not", "contains"}:
                resolved_dict[key] = self._resolve_schema_node(value, stack)
            elif key in {"allOf", "anyOf", "oneOf"} and isinstance(value, list):
                resolved_dict[key] = [self._resolve_schema_node(item, stack) for item in value]
            else:
                resolved_dict[key] = self._resolve_schema_node(value, stack)
        return resolved_dict

    def _find_operation_spec(self, operation: OperationMetadata) -> Optional[Dict]:
        target_path = self._normalize_path_template(operation.path)
        target_method = self._normalize_method(operation.method)

        path_item = self._path_index.get(target_path)
        if not path_item:
            return None

        operation_spec = path_item.get(target_method)
        if not isinstance(operation_spec, dict):
            return None
        return operation_spec

    def _resolve_parameter(self, parameter: Dict[str, object]) -> Dict[str, object]:
        if "$ref" in parameter:
            parameter = self._resolve_ref(str(parameter["$ref"]))

        resolved: Dict[str, object] = {}
        for key in ("name", "in", "required", "description", "deprecated", "allowEmptyValue", "style", "explode", "allowReserved"):
            if key in parameter:
                resolved[key] = parameter[key]

        if "schema" in parameter:
            resolved["schema"] = self._resolve_schema_node(parameter["schema"])
        if "content" in parameter and isinstance(parameter["content"], dict):
            resolved["content"] = {
                content_type: self._resolve_schema_node(content_obj)
                for content_type, content_obj in parameter["content"].items()
            }
        return resolved

    def _resolve_request_body(self, request_body: Dict[str, object]) -> Dict[str, object]:
        if "$ref" in request_body:
            request_body = self._resolve_ref(str(request_body["$ref"]))

        resolved: Dict[str, object] = {}
        if "required" in request_body:
            resolved["required"] = request_body["required"]
        if "description" in request_body:
            resolved["description"] = request_body["description"]
        if "content" in request_body and isinstance(request_body["content"], dict):
            resolved["content"] = {}
            for content_type, content_obj in request_body["content"].items():
                if isinstance(content_obj, dict):
                    resolved_content: Dict[str, object] = {}
                    if "schema" in content_obj:
                        resolved_content["schema"] = self._resolve_schema_node(content_obj["schema"])
                    for key in ("example", "examples", "encoding"):
                        if key in content_obj:
                            resolved_content[key] = self._resolve_schema_node(content_obj[key])
                    resolved["content"][content_type] = resolved_content
        return resolved

    def build_input_schema(self, operation: OperationMetadata) -> Dict[str, object]:
        operation_spec = self._find_operation_spec(operation)
        if operation_spec is None:
            return {}
        resolved: Dict[str, object] = {}

        parameters = operation_spec.get("parameters", [])
        if isinstance(parameters, list):
            resolved_parameters = [
                self._resolve_parameter(parameter)
                for parameter in parameters
                if isinstance(parameter, dict)
            ]
            resolved["parameters"] = resolved_parameters

        request_body = operation_spec.get("requestBody")
        if isinstance(request_body, dict):
            resolved["request_body"] = self._resolve_request_body(request_body)

        return resolved

    def build_operation_context(self, operation: OperationMetadata) -> Optional[Dict[str, object]]:
        operation_spec = self._find_operation_spec(operation)
        if operation_spec is None:
            return None
        return {
            "path": operation.path,
            "method": operation.method,
            "operationId": operation_spec.get("operationId"),
            "summary": operation_spec.get("summary"),
            "description": operation_spec.get("description"),
            "parameters": operation_spec.get("parameters", []),
            "requestBody": operation_spec.get("requestBody"),
        }

    def load_operations_metadata(self) -> List[OperationMetadata]:
        with open(self.metadata_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        operations: List[OperationMetadata] = []
        for op_data in data:
            operations.append(
                OperationMetadata(
                    operation=op_data.get("Operation", ""),
                    path=op_data.get("Paths", ""),
                    method=op_data.get("Method", ""),
                    description=op_data.get("Description"),
                    depends_on=op_data.get("DependsOn", []),
                )
            )
        return operations

    def parse_llm_response(self, response_text: str) -> Optional[Dict]:
        cleaned_response = response_text.strip()
        if cleaned_response.startswith("```"):
            first_newline = cleaned_response.find("\n")
            if first_newline != -1:
                cleaned_response = cleaned_response[first_newline + 1 :]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

        json_match = re.search(r'\{.*"constraints".*\}', cleaned_response, re.DOTALL)
        if json_match:
            cleaned_response = json_match.group(0)

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError as exc:
            print(f"Warning: Failed to parse LLM response as JSON: {exc}", flush=True)
            print(f"Response text: {cleaned_response[:500]}...", flush=True)
            return None

    def extract_operation_schema(self, operation: OperationMetadata) -> Optional[OperationSchema]:
        print(f"[*] Processing operation: {operation.operation} ({operation.method} {operation.path})...", flush=True)

        try:
            input_schema = self.build_input_schema(operation)
            operation_context = self.build_operation_context(operation)
        except Exception as exc:
            print(f"  → Error resolving YAML schema for {operation.operation}: {exc}", flush=True)
            return None

        if not operation_context:
            print(f"  → No matching YAML operation found for {operation.operation}; skipping", flush=True)
            return None

        prompt = build_operation_schema_prompt(operation, operation_context, input_schema)

        try:
            response_text = run_text_agent(
                agent_name="NRF Schema Agent",
                instructions=SYSTEM_PROMPT_SCHEMA_EXTRACTION,
                prompt=prompt,
                workflow_name="NRF Schema Extraction",
            )
        except Exception as exc:
            print(f"  → Error calling agent: {exc}", flush=True)
            return None

        parsed_response = self.parse_llm_response(response_text)
        if not parsed_response:
            return None

        constraints = parsed_response.get("constraints", [])
        if not isinstance(constraints, list):
            constraints = [str(constraints)] if constraints else []

        print(
            f"  → Extracted {len(input_schema.get('parameters', []))} parameter(s), "
            f"{1 if 'request_body' in input_schema else 0} request body section(s), "
            f"and {len(constraints)} constraint(s)",
            flush=True,
        )

        return OperationSchema(
            operation=operation.operation,
            path=operation.path,
            method=operation.method,
            input_schema=input_schema,
            constraints=constraints,
            depends_on=operation.depends_on or [],
        )

    def extract_all_schemas(self) -> List[OperationSchema]:
        print(f"[*] Loading specification from {self.spec_file.name}...", flush=True)
        self.load_specification()
        print(f"[*] Specification loaded ({len(self.spec_doc.get('paths', {}))} path(s))", flush=True)

        print(f"[*] Loading operations from {self.metadata_file.name}...", flush=True)
        operations = self.load_operations_metadata()
        print(f"[*] Loaded {len(operations)} operation(s)", flush=True)

        results: List[OperationSchema] = []
        total_ops = len(operations)
        for i, op in enumerate(operations, 1):
            print(f"\n[{i}/{total_ops}] Processing {op.operation}...", flush=True)
            schema = self.extract_operation_schema(op)
            if schema:
                results.append(schema)
            else:
                print(f"  → Failed to extract schema for {op.operation}", flush=True)
        return results

    def save_results(self, schemas: List[OperationSchema]) -> None:
        results = []
        for schema in schemas:
            results.append(
                {
                    "operation": schema.operation,
                    "path": schema.path,
                    "method": schema.method,
                    "input_schema": schema.input_schema,
                    "constraints": schema.constraints,
                    "depends_on": schema.depends_on,
                }
            )

        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    def run(self) -> None:
        schemas = self.extract_all_schemas()
        self.save_results(schemas)
        print(f"\n[✓] Extracted schemas for {len(schemas)} operation(s)")
        print(f"[✓] Results saved to {self.output_file}")


def main() -> None:
    OperationSchemaAgent().run()


if __name__ == "__main__":
    main()
