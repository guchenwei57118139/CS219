"""Constraint generation agent for NRF operations."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extremal_testing.nrf_agents.models.common import OperationMetadata, OperationSchema
from extremal_testing.nrf_agents.prompts.schema import (
    SYSTEM_PROMPT_CONSTRAINT_EXTRACTION,
    build_operation_schema_prompt,
)
from extremal_testing.nrf_agents.workflow.sdk import run_text_agent

CONSTRAINT_SCHEMA_KEYS = {
    "$ref",
    "type",
    "format",
    "nullable",
    "required",
    "properties",
    "patternProperties",
    "dependentSchemas",
    "items",
    "additionalProperties",
    "enum",
    "const",
    "pattern",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "minProperties",
    "maxProperties",
    "oneOf",
    "anyOf",
    "allOf",
    "not",
    "contains",
    "deprecated",
    "description",
}

PARAMETER_KEYS = {
    "name",
    "in",
    "required",
    "description",
    "deprecated",
    "allowEmptyValue",
    "style",
    "explode",
    "allowReserved",
}

class ConstraintAgent:
    """Extract resolved input schemas and constraints for operations."""

    def __init__(
        self,
        metadata_file: Path = ROOT_DIR / "json" / "AllOpsMetaData.json",
        spec_file: Path = ROOT_DIR / "specs" / "original" / "TS29510_Nnrf_NFManagement.yaml",
        common_data_file: Path = ROOT_DIR / "specs" / "original" / "TS29571_CommonData.yaml",
        output_dir: Path = ROOT_DIR / "json" / "constraints",
    ):
        self.metadata_file = metadata_file
        self.spec_file = spec_file
        self.common_data_file = common_data_file
        self.output_dir = output_dir
        self.spec_doc: Dict[str, Dict] = {}
        self.common_data_doc: Dict[str, Dict] = {}
        self._ref_definition_keys: Dict[str, str] = {}
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

    @staticmethod
    def _trim_description(value: object, limit: int = 220) -> object:
        if not isinstance(value, str):
            return value
        cleaned = " ".join(value.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3].rstrip() + "..."

    def _canonical_ref(self, ref: str) -> str:
        if ref.startswith("#"):
            return f"{self.spec_file.name}{ref}"
        return ref

    def _definition_key_for_ref(self, ref: str) -> str:
        canonical_ref = self._canonical_ref(ref)
        existing_key = self._ref_definition_keys.get(canonical_ref)
        if existing_key:
            return existing_key

        file_part, pointer = canonical_ref.split("#", 1) if "#" in canonical_ref else (canonical_ref, "")
        file_stem = Path(file_part).stem or self.spec_file.stem
        pointer_name = pointer.rstrip("/").split("/")[-1] if pointer else file_stem
        pointer_name = self._decode_json_pointer_token(pointer_name)
        base_key = f"{file_stem}.{pointer_name}"
        key = base_key
        suffix = 2
        used_keys = set(self._ref_definition_keys.values())
        while key in used_keys:
            key = f"{base_key}.{suffix}"
            suffix += 1

        self._ref_definition_keys[canonical_ref] = key
        return key

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
                if part not in target:
                    raise KeyError(f"Cannot resolve pointer segment {part!r} in {pointer!r}")
                target = target[part]
            elif isinstance(target, list):
                index = int(part)
                target = target[index]
            else:
                raise KeyError(f"Cannot resolve pointer segment {part!r} in {pointer!r}")

        if not isinstance(target, dict):
            return {"value": target}
        return target

    def _raw_ref_target(self, ref: str) -> Optional[Dict[str, Any]]:
        doc = self._get_doc_for_ref(ref)
        if doc is None:
            return None
        _, pointer = ref.split("#", 1) if "#" in ref else (ref, "")
        try:
            target = self._resolve_pointer(doc, pointer)
        except (KeyError, IndexError, ValueError):
            return None
        return copy.deepcopy(target)

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

    def _add_definition(
        self,
        ref: str,
        definitions: Dict[str, Any],
        stack: Optional[List[str]] = None,
    ) -> str:
        stack = stack or []
        definition_key = self._definition_key_for_ref(ref)
        if definition_key in definitions:
            return definition_key
        if ref in stack or self._canonical_ref(ref) in stack:
            definitions[definition_key] = {"$ref": f"#/definitions/{definition_key}"}
            return definition_key

        target = self._raw_ref_target(ref)
        if target is None:
            definitions[definition_key] = {"$ref": ref}
            return definition_key

        definitions[definition_key] = {}
        definitions[definition_key] = self._compact_schema_node(
            target,
            definitions,
            stack + [ref, self._canonical_ref(ref)],
            expand_ref=False,
        )
        return definition_key

    def _compact_ref_node(
        self,
        node: Dict[str, Any],
        definitions: Dict[str, Any],
        stack: Optional[List[str]],
        expand_ref: bool,
    ) -> Dict[str, Any]:
        ref = str(node["$ref"])
        sibling_items = {key: value for key, value in node.items() if key != "$ref"}

        if expand_ref:
            target = self._raw_ref_target(ref)
            if target is None:
                compacted: Dict[str, Any] = {"$ref": ref}
            else:
                compacted = self._compact_schema_node(
                    target,
                    definitions,
                    (stack or []) + [ref, self._canonical_ref(ref)],
                    expand_ref=False,
                )
        else:
            definition_key = self._add_definition(ref, definitions, stack)
            compacted = {"$ref": f"#/definitions/{definition_key}"}

        for key, value in sibling_items.items():
            if key not in CONSTRAINT_SCHEMA_KEYS:
                continue
            compacted[key] = self._compact_schema_node(value, definitions, stack, expand_ref=False)
        return compacted

    def _compact_schema_node(
        self,
        node: object,
        definitions: Dict[str, Any],
        stack: Optional[List[str]] = None,
        *,
        expand_ref: bool = False,
    ) -> object:
        if isinstance(node, list):
            return [self._compact_schema_node(item, definitions, stack, expand_ref=False) for item in node]
        if not isinstance(node, dict):
            return node

        if "$ref" in node:
            return self._compact_ref_node(node, definitions, stack, expand_ref)

        compacted: Dict[str, Any] = {}
        for key, value in node.items():
            if key not in CONSTRAINT_SCHEMA_KEYS:
                continue
            if key in {"properties", "patternProperties", "dependentSchemas"} and isinstance(value, dict):
                compacted[key] = {
                    prop_key: self._compact_schema_node(prop_value, definitions, stack, expand_ref=False)
                    for prop_key, prop_value in value.items()
                }
            elif key in {"items", "additionalProperties", "not"}:
                compacted[key] = self._compact_schema_node(value, definitions, stack, expand_ref=False)
            elif key in {"allOf", "anyOf", "oneOf"} and isinstance(value, list):
                compacted[key] = [
                    self._compact_schema_node(item, definitions, stack, expand_ref=False)
                    for item in value
                ]
            elif key == "description":
                compacted[key] = self._trim_description(value)
            else:
                compacted[key] = copy.deepcopy(value)
        return compacted

    def _compact_parameter(self, parameter: Dict[str, object], definitions: Dict[str, Any]) -> Dict[str, object]:
        if "$ref" in parameter:
            target = self._raw_ref_target(str(parameter["$ref"]))
            if target is None:
                return {"$ref": str(parameter["$ref"])}
            parameter = target

        resolved: Dict[str, object] = {}
        for key in PARAMETER_KEYS:
            if key in parameter:
                value = parameter[key]
                resolved[key] = self._trim_description(value) if key == "description" else value

        if "schema" in parameter:
            resolved["schema"] = self._compact_schema_node(parameter["schema"], definitions, expand_ref=True)
        if "content" in parameter and isinstance(parameter["content"], dict):
            resolved["content"] = {
                content_type: self._compact_schema_node(content_obj, definitions, expand_ref=True)
                for content_type, content_obj in parameter["content"].items()
            }
        return resolved

    def _compact_request_body(self, request_body: Dict[str, object], definitions: Dict[str, Any]) -> Dict[str, object]:
        if "$ref" in request_body:
            target = self._raw_ref_target(str(request_body["$ref"]))
            if target is None:
                return {"$ref": str(request_body["$ref"])}
            request_body = target

        resolved: Dict[str, object] = {}
        if "required" in request_body:
            resolved["required"] = request_body["required"]
        if "description" in request_body:
            resolved["description"] = self._trim_description(request_body["description"])
        if "content" in request_body and isinstance(request_body["content"], dict):
            resolved["content"] = {}
            for content_type, content_obj in request_body["content"].items():
                if isinstance(content_obj, dict):
                    resolved_content: Dict[str, object] = {}
                    if "schema" in content_obj:
                        resolved_content["schema"] = self._compact_schema_node(
                            content_obj["schema"],
                            definitions,
                            expand_ref=True,
                        )
                    resolved["content"][content_type] = resolved_content
        return resolved

    def build_input_schema_graph(self, operation: OperationMetadata) -> Dict[str, Dict[str, object]]:
        operation_spec = self._find_operation_spec(operation)
        if operation_spec is None:
            return {"input_schema": {}, "definitions": {}}
        resolved: Dict[str, object] = {}
        definitions: Dict[str, object] = {}

        parameters = operation_spec.get("parameters", [])
        if isinstance(parameters, list):
            resolved_parameters = [
                self._compact_parameter(parameter, definitions)
                for parameter in parameters
                if isinstance(parameter, dict)
            ]
            resolved["parameters"] = resolved_parameters

        request_body = operation_spec.get("requestBody")
        if isinstance(request_body, dict):
            resolved["request_body"] = self._compact_request_body(request_body, definitions)

        return {"input_schema": resolved, "definitions": definitions}

    def build_input_schema(self, operation: OperationMetadata) -> Dict[str, object]:
        return self.build_input_schema_graph(operation)["input_schema"]

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

    @staticmethod
    def _normalize_constraint_text(constraint: Any) -> Optional[str]:
        if not isinstance(constraint, str):
            constraint = str(constraint) if constraint is not None else ""
        cleaned = " ".join(constraint.split()).strip()
        if not cleaned:
            return None

        if "MUST" not in cleaned.upper():
            return None

        cleaned = re.sub(r"\bmust\b", "MUST", cleaned, flags=re.IGNORECASE)
        return cleaned

    def _normalize_constraint_records(self, raw_constraints: Any) -> List[Dict[str, Any]]:
        normalized_records: List[Dict[str, Any]] = []
        if not isinstance(raw_constraints, list):
            return normalized_records

        for constraint in raw_constraints:
            if isinstance(constraint, dict):
                constraint_text = constraint.get("constraint") or constraint.get("text") or constraint.get("value")
                schema_id = str(constraint.get("schema_id", "operation_input")).strip() or "operation_input"
            else:
                constraint_text = constraint
                schema_id = "operation_input"

            normalized_text = self._normalize_constraint_text(constraint_text)
            if not normalized_text:
                continue

            normalized_records.append(
                {
                    "schema_id": schema_id,
                    "constraint": normalized_text,
                }
            )

        return normalized_records

    @staticmethod
    def _dedupe_constraint_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for record in records:
            normalized_constraint = " ".join(str(record.get("constraint", "")).split()).strip().lower()
            if not normalized_constraint:
                continue
            if normalized_constraint in seen:
                continue
            seen.add(normalized_constraint)
            deduped.append(record)
        return deduped

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
            schema_graph = self.build_input_schema_graph(operation)
            input_schema = schema_graph["input_schema"]
            definitions = schema_graph["definitions"]
            operation_context = self.build_operation_context(operation)
        except Exception as exc:
            print(f"  → Error resolving YAML schema for {operation.operation}: {exc}", flush=True)
            return None

        if not operation_context:
            print(f"  → No matching YAML operation found for {operation.operation}; skipping", flush=True)
            return None

        if not input_schema:
            print(f"  → No input schema found for {operation.operation}; skipping", flush=True)
            return None

        print(
            f"  → Extracting constraints from compact schema graph "
            f"({len(definitions)} definition(s))...",
            flush=True,
        )
        prompt = build_operation_schema_prompt(operation, operation_context, schema_graph)

        try:
            response_text = run_text_agent(
                agent_name="Constraint Agent",
                instructions=SYSTEM_PROMPT_CONSTRAINT_EXTRACTION,
                prompt=prompt,
                workflow_name="Constraint Generation",
            )
        except Exception as exc:
            print(f"  → Error calling agent: {exc}", flush=True)
            return None

        parsed_response = self.parse_llm_response(response_text)
        if not parsed_response:
            return None

        constraints = self._dedupe_constraint_records(
            self._normalize_constraint_records(parsed_response.get("constraints", []))
        )

        if not constraints:
            print(f"  → No valid constraints extracted for {operation.operation}", flush=True)
            return None

        print(f"  → Consolidated to {len(constraints)} unique constraint(s)", flush=True)

        return OperationSchema(
            operation=operation.operation,
            path=operation.path,
            method=operation.method,
            input_schema=input_schema,
            definitions=definitions,
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
        if not schemas:
            print("  → No schemas extracted; leaving existing constraint files unchanged", flush=True)
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        for existing_file in self.output_dir.glob("*.json"):
            existing_file.unlink()
        for schema in schemas:
            output_file = self.output_dir / f"{schema.operation}.json"
            payload = {
                "input_schema": schema.input_schema,
                "definitions": schema.definitions,
                "constraints": schema.constraints,
            }
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

    def run(self) -> None:
        schemas = self.extract_all_schemas()
        self.save_results(schemas)
        print(f"\n[✓] Extracted constraints for {len(schemas)} operation(s)")
        print(f"[✓] Results saved to {self.output_dir}")


def main() -> None:
    ConstraintAgent().run()


if __name__ == "__main__":
    main()
