"""Bug report agent for NRF implementation differences."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extremal_testing.nrf_agents.prompts.bug_reports import (
    DEFAULT_PROTOCOL,
    SYSTEM_PROMPT_BUG_REPORT_COALESCE,
    SYSTEM_PROMPT_BUG_REPORT_TRIAGE,
    build_bug_report_coalesce_prompt,
    build_bug_report_prompt,
)
from extremal_testing.nrf_agents.workflow.sdk import run_text_agent

DEFAULT_MAX_REPORTS = 3
DEFAULT_MIN_STRENGTH = 7
DEFAULT_EXCEPTIONAL_STRENGTH = 9
DEFAULT_SCHEMA_BATCH_SIZE = 20
BODY_SNIPPET_LIMIT = 240

TEST_RESULTS_DIR = ROOT_DIR / "json" / "test_results"
TESTCASES_DIR = ROOT_DIR / "json" / "testcases"
CONSTRAINTS_DIR = ROOT_DIR / "json" / "constraints"
REPORTS_DIR = ROOT_DIR / "reports"


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _parse_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
    cleaned = _strip_code_fences(text)
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        print(f"Warning: Failed to parse agent response as JSON: {exc}", flush=True)
        print(f"Response text: {cleaned[:500]}...", flush=True)
        return None
    return parsed if isinstance(parsed, list) else None


def _load_json_file(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _suite_file_for_operation(testcases_dir: Path, operation: str) -> Path:
    canonical = testcases_dir / f"{operation}.json"
    if canonical.exists():
        return canonical
    return testcases_dir / f"{operation}_tests.json"


def _stringify_compact(value: Any, limit: int = BODY_SNIPPET_LIMIT) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, sort_keys=True, ensure_ascii=False)
        except TypeError:
            text = str(value)
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def _status_code_values(implementations: Dict[str, Any], implementation_order: Sequence[str]) -> List[int]:
    status_codes: List[int] = []
    for implementation_name in implementation_order:
        implementation_result = implementations.get(implementation_name, {})
        if not isinstance(implementation_result, dict):
            continue
        status_code = implementation_result.get("status_code")
        if isinstance(status_code, int):
            status_codes.append(status_code)
    return status_codes


def _normalized_values(
    implementations: Dict[str, Any],
    implementation_order: Sequence[str],
    field: str,
) -> List[Optional[str]]:
    values: List[Optional[str]] = []
    for implementation_name in implementation_order:
        implementation_result = implementations.get(implementation_name, {})
        if not isinstance(implementation_result, dict):
            continue
        values.append(_stringify_compact(implementation_result.get(field)))
    return values


def _has_meaningful_difference(test_result: Dict[str, Any], implementation_order: Sequence[str]) -> bool:
    implementations = test_result.get("implementations", {})
    if not isinstance(implementations, dict):
        return False

    status_codes = _status_code_values(implementations, implementation_order)
    if len(status_codes) >= 2 and len(set(status_codes)) > 1:
        return True

    return False


def _normalize_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _normalize_report_item(
    item: Dict[str, Any],
    valid_test_ids: set[int],
    valid_schema_ids: set[str],
    min_strength: int,
) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None

    title = _normalize_string(item.get("title"))
    description = _normalize_string(item.get("description"))
    investigation_value = _normalize_string(item.get("investigation_value"))
    implementation_differences = _normalize_string(item.get("implementation_differences"))
    if not title or not description:
        return None

    evidence_ids_raw = item.get("evidence_test_ids")
    if not isinstance(evidence_ids_raw, list):
        return None
    evidence_test_ids: List[int] = []
    for test_id in evidence_ids_raw:
        if isinstance(test_id, bool):
            continue
        if isinstance(test_id, int) and test_id in valid_test_ids and test_id not in evidence_test_ids:
            evidence_test_ids.append(test_id)
    if not evidence_test_ids:
        return None

    evidence_schema_ids_raw = item.get("evidence_schema_ids")
    evidence_schema_ids: List[str] = []
    if isinstance(evidence_schema_ids_raw, list):
        for schema_id in evidence_schema_ids_raw:
            normalized = _normalize_string(schema_id)
            if normalized in valid_schema_ids and normalized not in evidence_schema_ids:
                evidence_schema_ids.append(normalized)
    if valid_schema_ids and not evidence_schema_ids:
        return None

    strength = item.get("strength")
    if isinstance(strength, bool):
        strength = int(strength)
    elif not isinstance(strength, int):
        try:
            strength = int(strength)
        except (TypeError, ValueError):
            strength = min_strength
    strength = max(1, min(10, strength))
    if strength < min_strength:
        return None

    affected_raw = item.get("possibly_affected_implementations")
    possibly_affected: List[str] = []
    if isinstance(affected_raw, list):
        for implementation_name in affected_raw:
            normalized = _normalize_string(implementation_name)
            if normalized and normalized not in possibly_affected:
                possibly_affected.append(normalized)

    return {
        "title": title,
        "description": description,
        "possibly_affected_implementations": possibly_affected,
        "affected_rationale": _normalize_string(item.get("affected_rationale")),
        "evidence_test_ids": evidence_test_ids,
        "evidence_schema_ids": evidence_schema_ids,
        "implementation_differences": implementation_differences,
        "investigation_value": investigation_value,
        "strength": strength,
    }


def _dedupe_reports(reports: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen: set[tuple[str, tuple[int, ...]]] = set()
    for report in reports:
        key = (
            str(report["title"]).casefold(),
            tuple(sorted(report["evidence_test_ids"])),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(report)
    return deduped


def _select_strong_reports(
    reports: Sequence[Dict[str, Any]],
    max_reports: int,
    exceptional_strength: int,
) -> List[Dict[str, Any]]:
    sorted_reports = sorted(
        _dedupe_reports(reports),
        key=lambda item: (item["strength"], len(item["evidence_test_ids"])),
        reverse=True,
    )
    if max_reports <= 0:
        return sorted_reports

    selected: List[Dict[str, Any]] = []
    for index, report in enumerate(sorted_reports):
        if index < max_reports or report["strength"] >= exceptional_strength:
            selected.append(report)
    return selected


def _markdown_escape_cell(value: Any) -> str:
    text = _normalize_string(value)
    if not text:
        return "-"
    return text.replace("|", "\\|").replace("\n", " ")


class BugReportAgent:
    """Generate Markdown bug reports for implementation differences, grouped by operation."""

    def __init__(
        self,
        test_results_dir: Path = TEST_RESULTS_DIR,
        testcases_dir: Path = TESTCASES_DIR,
        constraints_dir: Path = CONSTRAINTS_DIR,
        reports_dir: Path = REPORTS_DIR,
        max_reports: int = DEFAULT_MAX_REPORTS,
        min_strength: int = DEFAULT_MIN_STRENGTH,
        exceptional_strength: int = DEFAULT_EXCEPTIONAL_STRENGTH,
        schema_batch_size: int = DEFAULT_SCHEMA_BATCH_SIZE,
        protocol: str = DEFAULT_PROTOCOL,
    ) -> None:
        self.test_results_dir = test_results_dir
        self.testcases_dir = testcases_dir
        self.constraints_dir = constraints_dir
        self.reports_dir = reports_dir
        self.max_reports = max_reports
        self.min_strength = min_strength
        self.exceptional_strength = exceptional_strength
        self.schema_batch_size = max(1, schema_batch_size)
        self.protocol = protocol

    def discover_result_files(self) -> List[Path]:
        if not self.test_results_dir.exists():
            return []
        result_files: List[Path] = []
        for path in sorted(self.test_results_dir.glob("*.json")):
            if not path.is_file():
                continue
            try:
                payload = _load_json_file(path)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            if not isinstance(payload.get("tests"), list):
                continue
            if not isinstance(payload.get("implementation_order"), list):
                continue
            result_files.append(path)
        return result_files

    def load_test_suite(self, operation: str) -> Dict[str, Any]:
        suite_file = _suite_file_for_operation(self.testcases_dir, operation)
        if not suite_file.exists():
            raise FileNotFoundError(f"Matching test suite not found for {operation}: {suite_file}")
        suite = _load_json_file(suite_file)
        if not isinstance(suite, dict) or not isinstance(suite.get("tests"), list):
            raise ValueError(f"Suite file is not a suite object with a tests array: {suite_file}")
        return suite

    def load_test_results(self, result_file: Path) -> Dict[str, Any]:
        payload = _load_json_file(result_file)
        if not isinstance(payload, dict) or not isinstance(payload.get("tests"), list):
            raise ValueError(f"Result file is not a comparison result object: {result_file}")
        return payload

    def load_constraints(self, operation: str) -> Dict[str, Any]:
        constraints_file = self.constraints_dir / f"{operation}.json"
        if not constraints_file.exists():
            return {}
        payload = _load_json_file(constraints_file)
        return payload if isinstance(payload, dict) else {}

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

    def _build_operation_input_summary(self, operation: str, input_schema: Dict[str, Any]) -> Dict[str, Any]:
        summary: Dict[str, Any] = {"operation": operation}
        parameters = input_schema.get("parameters", [])
        grouped_params: Dict[str, Dict[str, List[str]]] = {}
        if isinstance(parameters, list):
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    continue
                location = str(parameter.get("in") or "unknown")
                name = _normalize_string(parameter.get("name"))
                if not name:
                    continue
                bucket = grouped_params.setdefault(location, {"required": [], "optional": []})
                key = "required" if parameter.get("required") is True else "optional"
                bucket[key].append(name)
        summary["parameters"] = grouped_params

        request_body = input_schema.get("request_body", {})
        if isinstance(request_body, dict):
            summary["request_body"] = {
                "required": request_body.get("required") is True,
                "root_required": self._request_body_root_required(request_body),
            }
        else:
            summary["request_body"] = {"required": False, "root_required": []}
        return summary

    def _request_body_root_required(self, request_body: Dict[str, Any]) -> List[str]:
        content = request_body.get("content", {})
        if not isinstance(content, dict):
            return []
        for content_obj in content.values():
            if not isinstance(content_obj, dict):
                continue
            schema = content_obj.get("schema")
            if isinstance(schema, dict) and isinstance(schema.get("required"), list):
                return [str(item) for item in schema["required"]]
        return []

    def _find_parameter_schema_slice(
        self,
        schema_id: str,
        input_schema: Dict[str, Any],
        definitions: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        try:
            location, name = schema_id.split(".", 1)
        except ValueError:
            return None

        parameters = input_schema.get("parameters", [])
        if not isinstance(parameters, list):
            return None
        for parameter in parameters:
            if not isinstance(parameter, dict):
                continue
            if parameter.get("in") == location and parameter.get("name") == name:
                referenced_definitions: Dict[str, Any] = {}
                self._collect_referenced_definitions(parameter, definitions, referenced_definitions)
                return {
                    "schema_id": schema_id,
                    "kind": "parameter",
                    "location": location,
                    "name": name,
                    "required": parameter.get("required") is True,
                    "description": parameter.get("description"),
                    "schema": parameter.get("schema", {}),
                    "definitions": referenced_definitions,
                }
        return None

    def _request_body_content_schemas(self, input_schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        request_body = input_schema.get("request_body", {})
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
            if isinstance(properties, dict) and isinstance(properties.get(part), dict):
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

    def _find_request_schema_slice(
        self,
        schema_id: str,
        input_schema: Dict[str, Any],
        definitions: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        content_schemas = self._request_body_content_schemas(input_schema)
        if not content_schemas:
            return None

        request_body = input_schema.get("request_body", {})
        path_suffix = schema_id.removeprefix("request_body").lstrip(".")
        path_parts = [part for part in path_suffix.split(".") if part]
        content_slices: Dict[str, Dict[str, Any]] = {}
        referenced_definitions: Dict[str, Any] = {}

        for content_type, root_schema in content_schemas.items():
            target_schema = root_schema if not path_parts else self._walk_request_schema_path(
                root_schema,
                path_parts,
                definitions,
            )
            if not isinstance(target_schema, dict):
                continue
            content_slices[content_type] = {
                "root_required": root_schema.get("required", []),
                "root_anyOf": root_schema.get("anyOf"),
                "target_schema": target_schema,
            }
            self._collect_referenced_definitions(target_schema, definitions, referenced_definitions)

        if not content_slices:
            return None

        return {
            "schema_id": schema_id,
            "kind": "request_body",
            "request_body_required": isinstance(request_body, dict) and request_body.get("required") is True,
            "field_path": path_suffix or "<root>",
            "content": content_slices,
            "definitions": referenced_definitions,
        }

    def build_schema_context(self, operation: str, anomalies: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        constraints = self.load_constraints(operation)
        input_schema = constraints.get("input_schema", {})
        definitions = constraints.get("definitions", {})
        if not isinstance(input_schema, dict):
            input_schema = {}
        if not isinstance(definitions, dict):
            definitions = {}

        schema_ids: List[str] = []
        for anomaly in anomalies:
            schema_id = _normalize_string(anomaly.get("constraint_schema_id"))
            if schema_id and schema_id not in schema_ids:
                schema_ids.append(schema_id)

        schema_definitions: Dict[str, Dict[str, Any]] = {}
        for schema_id in schema_ids:
            schema_slice: Optional[Dict[str, Any]] = None
            if schema_id.startswith(("path.", "query.", "header.")):
                schema_slice = self._find_parameter_schema_slice(schema_id, input_schema, definitions)
            elif schema_id == "request_body" or schema_id.startswith("request_body."):
                schema_slice = self._find_request_schema_slice(schema_id, input_schema, definitions)
            schema_definitions[schema_id] = schema_slice or {
                "schema_id": schema_id,
                "kind": "unresolved",
                "note": "No exact schema slice found for this referenced schema ID.",
            }

        return {
            "operation_input_summary": self._build_operation_input_summary(operation, input_schema),
            "schema_definitions": schema_definitions,
        }

    def build_anomalies(self, operation: str, result_file: Path) -> List[Dict[str, Any]]:
        suite = self.load_test_suite(operation)
        result_payload = self.load_test_results(result_file)
        implementation_order = result_payload.get("implementation_order", [])
        if not isinstance(implementation_order, list) or not implementation_order:
            implementation_order = ["free5gc", "oai", "open5gs"]

        source_tests = suite.get("tests", [])
        anomalies: List[Dict[str, Any]] = []
        for test_result in result_payload.get("tests", []):
            if not isinstance(test_result, dict):
                continue
            if not _has_meaningful_difference(test_result, implementation_order):
                continue

            test_id = test_result.get("test_case_index")
            if not isinstance(test_id, int) or test_id < 0 or test_id >= len(source_tests):
                continue

            original_test_case = source_tests[test_id]
            if not isinstance(original_test_case, dict):
                continue

            implementations = test_result.get("implementations", {})
            normalized_implementations: Dict[str, Dict[str, Any]] = {}
            for implementation_name in implementation_order:
                implementation_result = implementations.get(implementation_name, {})
                if not isinstance(implementation_result, dict):
                    implementation_result = {}
                normalized_implementations[implementation_name] = {
                    "status_code": implementation_result.get("status_code"),
                    "response_body": _stringify_compact(implementation_result.get("response_body")),
                    "error": _stringify_compact(implementation_result.get("error")),
                }

            anomalies.append(
                {
                    "test_id": test_id,
                    "test_case_id": original_test_case.get("id"),
                    "test_name": test_result.get("test_name", f"Test case {test_id + 1}"),
                    "constraint": original_test_case.get("constraint"),
                    "constraint_schema_id": original_test_case.get("constraint_schema_id"),
                    "request": {
                        "method": original_test_case.get("method"),
                        "path": original_test_case.get("path"),
                        "body": _stringify_compact(original_test_case.get("body")),
                    },
                    "implementations": normalized_implementations,
                }
            )

        return anomalies

    def _schema_group_key(self, anomaly: Dict[str, Any]) -> tuple[str, ...]:
        schema_ids_raw = anomaly.get("constraint_schema_ids")
        if isinstance(schema_ids_raw, list):
            schema_ids = sorted(
                {
                    _normalize_string(schema_id)
                    for schema_id in schema_ids_raw
                    if _normalize_string(schema_id)
                }
            )
            if schema_ids:
                return tuple(schema_ids)

        schema_id = _normalize_string(anomaly.get("constraint_schema_id"))
        return (schema_id or "unknown_schema",)

    def group_anomalies_by_schema(self, anomalies: Sequence[Dict[str, Any]]) -> Dict[tuple[str, ...], List[Dict[str, Any]]]:
        grouped: Dict[tuple[str, ...], List[Dict[str, Any]]] = {}
        for anomaly in anomalies:
            grouped.setdefault(self._schema_group_key(anomaly), []).append(anomaly)
        return grouped

    def build_schema_batches(self, anomalies: Sequence[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        grouped = self.group_anomalies_by_schema(anomalies)
        sorted_groups = sorted(grouped.items(), key=lambda item: item[0])
        batches: List[List[Dict[str, Any]]] = []
        current_batch: List[Dict[str, Any]] = []
        current_group_count = 0

        for _schema_key, group_anomalies in sorted_groups:
            if current_group_count >= self.schema_batch_size:
                batches.append(current_batch)
                current_batch = []
                current_group_count = 0
            current_batch.extend(group_anomalies)
            current_group_count += 1

        if current_batch:
            batches.append(current_batch)
        return batches

    def _schema_keys_for_batch(self, anomalies: Sequence[Dict[str, Any]]) -> List[str]:
        keys: List[str] = []
        for anomaly in anomalies:
            key = ",".join(self._schema_group_key(anomaly))
            if key not in keys:
                keys.append(key)
        return keys

    def generate_bug_report(
        self,
        operation: str,
        anomalies: List[Dict[str, Any]],
        schema_context: Dict[str, Any],
        result_file: Path,
        suite_file: Path,
    ) -> List[Dict[str, Any]]:
        prompt = build_bug_report_prompt(
            operation=operation,
            anomalies=anomalies,
            schema_context=schema_context,
            result_file=str(result_file),
            suite_file=str(suite_file),
            protocol=self.protocol,
        )
        try:
            response_text = run_text_agent(
                agent_name="Bug Report Agent",
                instructions=SYSTEM_PROMPT_BUG_REPORT_TRIAGE.format(protocol=self.protocol),
                prompt=prompt,
                workflow_name="Bug Report Generation",
            )
        except Exception as exc:
            print(f"  -> Error calling agent for {operation}: {exc}", flush=True)
            return []

        parsed = _parse_json_array(response_text)
        if parsed is None:
            return []

        valid_test_ids = {item["test_id"] for item in anomalies if isinstance(item.get("test_id"), int)}
        schema_definitions = schema_context.get("schema_definitions", {})
        valid_schema_ids = set(schema_definitions) if isinstance(schema_definitions, dict) else set()
        normalized_reports: List[Dict[str, Any]] = []
        for item in parsed:
            normalized = _normalize_report_item(item, valid_test_ids, valid_schema_ids, self.min_strength)
            if normalized is not None:
                normalized_reports.append(normalized)
        return normalized_reports

    def generate_schema_batched_reports(
        self,
        operation: str,
        anomalies: List[Dict[str, Any]],
        result_file: Path,
        suite_file: Path,
    ) -> List[Dict[str, Any]]:
        schema_batches = self.build_schema_batches(anomalies)
        slice_report_batches: List[Dict[str, Any]] = []

        for batch_index, batch_anomalies in enumerate(schema_batches, 1):
            schema_context = self.build_schema_context(operation, batch_anomalies)
            schema_keys = self._schema_keys_for_batch(batch_anomalies)
            print(
                f"  -> Reviewing {operation} schema batch {batch_index}/{len(schema_batches)} "
                f"({len(schema_keys)} schema group(s), {len(batch_anomalies)} test(s))",
                flush=True,
            )
            reports = self.generate_bug_report(
                operation=operation,
                anomalies=list(batch_anomalies),
                schema_context=schema_context,
                result_file=result_file,
                suite_file=suite_file,
            )
            if not reports:
                continue
            slice_report_batches.append(
                {
                    "schema_batch_index": batch_index,
                    "schema_group_keys": schema_keys,
                    "reports": reports,
                }
            )

        if not slice_report_batches:
            return []
        return self.coalesce_slice_reports(operation, slice_report_batches, anomalies, result_file, suite_file)

    def coalesce_slice_reports(
        self,
        operation: str,
        slice_report_batches: List[Dict[str, Any]],
        anomalies: Sequence[Dict[str, Any]],
        result_file: Path,
        suite_file: Path,
    ) -> List[Dict[str, Any]]:
        prompt = build_bug_report_coalesce_prompt(
            operation=operation,
            slice_report_batches=slice_report_batches,
            result_file=str(result_file),
            suite_file=str(suite_file),
            protocol=self.protocol,
        )
        try:
            response_text = run_text_agent(
                agent_name="Bug Report Coalescing Agent",
                instructions=SYSTEM_PROMPT_BUG_REPORT_COALESCE.format(protocol=self.protocol),
                prompt=prompt,
                workflow_name="Bug Report Generation",
            )
        except Exception as exc:
            print(f"  -> Error coalescing reports for {operation}: {exc}", flush=True)
            return [
                report
                for batch in slice_report_batches
                for report in batch.get("reports", [])
                if isinstance(report, dict)
            ]

        parsed = _parse_json_array(response_text)
        if parsed is None:
            return [
                report
                for batch in slice_report_batches
                for report in batch.get("reports", [])
                if isinstance(report, dict)
            ]

        valid_test_ids = {item["test_id"] for item in anomalies if isinstance(item.get("test_id"), int)}
        valid_schema_ids = {
            schema_id
            for anomaly in anomalies
            for schema_id in self._schema_group_key(anomaly)
            if schema_id != "unknown_schema"
        }
        normalized_reports: List[Dict[str, Any]] = []
        for item in parsed:
            normalized = _normalize_report_item(item, valid_test_ids, valid_schema_ids, self.min_strength)
            if normalized is not None:
                normalized_reports.append(normalized)
        return normalized_reports

    def render_markdown(
        self,
        operation: str,
        source_result_file: Path,
        source_suite_file: Path,
        anomalies: Sequence[Dict[str, Any]],
        schema_context: Dict[str, Any],
        reports: Sequence[Dict[str, Any]],
    ) -> str:
        anomaly_by_id = {
            anomaly["test_id"]: anomaly
            for anomaly in anomalies
            if isinstance(anomaly.get("test_id"), int)
        }

        lines: List[str] = [
            f"# {operation} Bug Report",
            "",
            f"- Source results: `{source_result_file}`",
            f"- Source tests: `{source_suite_file}`",
            f"- Anomaly tests reviewed: {len(anomalies)}",
            f"- Reports selected: {len(reports)}",
            "",
        ]

        if not reports:
            lines.extend(
                [
                    "## No High-Signal Reports Selected",
                    "",
                    "No strong reportable bug patterns were selected from the observed implementation differences.",
                    "",
                ]
            )
            return "\n".join(lines).rstrip() + "\n"

        for index, report in enumerate(reports, 1):
            possibly_affected = report.get("possibly_affected_implementations", [])
            affected_text = ", ".join(possibly_affected) if possibly_affected else "Not assigned"
            lines.extend(
                [
                    f"## {index}. {report['title']}",
                    "",
                    report["description"],
                    "",
                    f"- Possibly affected implementations: {affected_text}",
                    f"- Evidence strength: {report['strength']}/10",
                ]
            )
            affected_rationale = report.get("affected_rationale")
            if affected_rationale:
                lines.append(f"- Rationale: {affected_rationale}")
            implementation_differences = report.get("implementation_differences")
            if implementation_differences:
                lines.append(f"- Implementation differences: {implementation_differences}")
            investigation_value = report.get("investigation_value")
            if investigation_value:
                lines.append(f"- Why investigate: {investigation_value}")
            lines.extend(
                [
                    "",
                    "### Relevant Schema Evidence",
                    "",
                ]
            )
            schema_ids = report.get("evidence_schema_ids", [])
            if isinstance(schema_ids, list) and schema_ids:
                lines.extend(self._render_schema_evidence(schema_context, schema_ids))
            else:
                lines.append("No schema definitions were selected by the report agent.")
            lines.extend(
                [
                    "",
                    "| Test | Constraint | Request | free5gc | oai | open5gs |",
                    "| --- | --- | --- | --- | --- | --- |",
                ]
            )

            for test_id in report["evidence_test_ids"]:
                anomaly = anomaly_by_id.get(test_id)
                if anomaly is None:
                    continue
                request = anomaly.get("request", {})
                request_text = f"{request.get('method', '-')} {request.get('path', '-')}"
                implementations = anomaly.get("implementations", {})
                row = [
                    f"{anomaly.get('test_case_id') or test_id}: {anomaly.get('test_name', '')}",
                    anomaly.get("constraint"),
                    request_text,
                    self._implementation_summary(implementations.get("free5gc", {})),
                    self._implementation_summary(implementations.get("oai", {})),
                    self._implementation_summary(implementations.get("open5gs", {})),
                ]
                lines.append("| " + " | ".join(_markdown_escape_cell(value) for value in row) + " |")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def _render_schema_evidence(self, schema_context: Dict[str, Any], schema_ids: Sequence[Any]) -> List[str]:
        schema_definitions = schema_context.get("schema_definitions", {})
        if not isinstance(schema_definitions, dict):
            return ["No schema context was available."]

        lines = [
            "| Schema ID | Location / Field | Required | Schema Summary |",
            "| --- | --- | --- | --- |",
        ]
        for raw_schema_id in schema_ids:
            schema_id = _normalize_string(raw_schema_id)
            schema_definition = schema_definitions.get(schema_id)
            if not isinstance(schema_definition, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    _markdown_escape_cell(value)
                    for value in [
                        schema_id,
                        self._schema_location_summary(schema_definition),
                        self._schema_required_summary(schema_definition),
                        self._schema_shape_summary(schema_definition),
                    ]
                )
                + " |"
            )
        return lines if len(lines) > 2 else ["No matching schema definitions were found."]

    def _schema_location_summary(self, schema_definition: Dict[str, Any]) -> str:
        kind = schema_definition.get("kind")
        if kind == "parameter":
            return f"{schema_definition.get('location', '-')}.{schema_definition.get('name', '-')}"
        if kind == "request_body":
            return f"request_body.{schema_definition.get('field_path', '<root>')}"
        return _normalize_string(schema_definition.get("note")) or "unresolved"

    def _schema_required_summary(self, schema_definition: Dict[str, Any]) -> str:
        kind = schema_definition.get("kind")
        if kind == "parameter":
            return str(schema_definition.get("required") is True).lower()
        if kind == "request_body":
            parts = [f"request_body={str(schema_definition.get('request_body_required') is True).lower()}"]
            content = schema_definition.get("content", {})
            if isinstance(content, dict):
                root_required_values = []
                for content_slice in content.values():
                    if isinstance(content_slice, dict) and isinstance(content_slice.get("root_required"), list):
                        root_required_values.extend(str(item) for item in content_slice["root_required"])
                if root_required_values:
                    parts.append(f"root_required={sorted(set(root_required_values))}")
            return "; ".join(parts)
        return "-"

    def _schema_shape_summary(self, schema_definition: Dict[str, Any]) -> str:
        kind = schema_definition.get("kind")
        if kind == "parameter":
            return _stringify_compact(schema_definition.get("schema"), limit=360) or "-"
        if kind == "request_body":
            content = schema_definition.get("content", {})
            summaries: List[str] = []
            if isinstance(content, dict):
                for content_type, content_slice in content.items():
                    if not isinstance(content_slice, dict):
                        continue
                    target_schema = content_slice.get("target_schema")
                    root_any_of = content_slice.get("root_anyOf")
                    summary = f"{content_type}: target={_stringify_compact(target_schema, limit=280)}"
                    if root_any_of:
                        summary += f"; root_anyOf={_stringify_compact(root_any_of, limit=160)}"
                    summaries.append(summary)
            return " | ".join(summaries) if summaries else "-"
        return _normalize_string(schema_definition.get("note")) or "-"

    def _implementation_summary(self, implementation_result: Any) -> str:
        if not isinstance(implementation_result, dict):
            return "-"
        parts = [f"status={implementation_result.get('status_code')}"]
        if implementation_result.get("error"):
            parts.append(f"error={implementation_result['error']}")
        if implementation_result.get("response_body"):
            parts.append(f"body={implementation_result['response_body']}")
        return "; ".join(parts)

    def write_operation_report(
        self,
        operation: str,
        source_result_file: Path,
        source_suite_file: Path,
        anomalies: Sequence[Dict[str, Any]],
        reports: Sequence[Dict[str, Any]],
    ) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        output_file = self.reports_dir / f"{operation}.md"
        schema_context = self.build_schema_context(operation, anomalies)
        markdown = self.render_markdown(operation, source_result_file, source_suite_file, anomalies, schema_context, reports)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown)
        return output_file

    def process_result_file(self, result_file: Path) -> Optional[Path]:
        result_payload = self.load_test_results(result_file)
        operation = str(result_payload.get("operation") or result_file.stem)
        suite_file = _suite_file_for_operation(self.testcases_dir, operation)
        anomalies = self.build_anomalies(operation, result_file)
        if not anomalies:
            return self.write_operation_report(operation, result_file, suite_file, [], [])

        print(
            f"  -> Reviewing {operation} anomaly set ({len(anomalies)} test(s)) by schema batch",
            flush=True,
        )
        all_reports = self.generate_schema_batched_reports(operation, anomalies, result_file, suite_file)
        selected_reports = _select_strong_reports(all_reports, self.max_reports, self.exceptional_strength)
        return self.write_operation_report(operation, result_file, suite_file, anomalies, selected_reports)

    def run(self, result_files: Optional[Sequence[Path]] = None) -> List[Path]:
        if result_files is None:
            result_files = self.discover_result_files()

        written_files: List[Path] = []
        for result_file in result_files:
            if result_file.name.startswith("."):
                continue
            try:
                written_file = self.process_result_file(result_file)
            except FileNotFoundError as exc:
                print(f"Skipping {result_file.name}: {exc}", flush=True)
                continue
            written_files.append(written_file)
            print(f"Bug report saved to {written_file}", flush=True)
        return written_files


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Markdown bug reports for NRF implementation differences.")
    parser.add_argument(
        "--test-results-dir",
        type=Path,
        default=TEST_RESULTS_DIR,
        help="Directory containing per-operation comparison result JSON files.",
    )
    parser.add_argument(
        "--testcases-dir",
        type=Path,
        default=TESTCASES_DIR,
        help="Directory containing the original operation JSON suites.",
    )
    parser.add_argument(
        "--constraints-dir",
        type=Path,
        default=CONSTRAINTS_DIR,
        help="Directory containing per-operation constraint/schema JSON files.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Directory where Markdown bug reports should be written.",
    )
    parser.add_argument(
        "--max-reports",
        type=int,
        default=DEFAULT_MAX_REPORTS,
        help="Soft maximum number of bug reports to keep per operation.",
    )
    parser.add_argument(
        "--min-strength",
        type=int,
        default=DEFAULT_MIN_STRENGTH,
        help="Minimum LLM report strength required to include a bug report.",
    )
    parser.add_argument(
        "--exceptional-strength",
        type=int,
        default=DEFAULT_EXCEPTIONAL_STRENGTH,
        help="Strength threshold that allows reports beyond --max-reports.",
    )
    parser.add_argument(
        "--schema-batch-size",
        type=int,
        default=DEFAULT_SCHEMA_BATCH_SIZE,
        help="Maximum number of schema groups to include in one slice-level LLM call.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    generator = BugReportAgent(
        test_results_dir=args.test_results_dir,
        testcases_dir=args.testcases_dir,
        constraints_dir=args.constraints_dir,
        reports_dir=args.reports_dir,
        max_reports=args.max_reports,
        min_strength=args.min_strength,
        exceptional_strength=args.exceptional_strength,
        schema_batch_size=args.schema_batch_size,
    )
    generator.run()


if __name__ == "__main__":
    main()
