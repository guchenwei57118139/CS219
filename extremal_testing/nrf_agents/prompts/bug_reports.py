"""Prompt helpers for bug report generation."""

from __future__ import annotations

import json
from typing import Any, Dict, List

DEFAULT_PROTOCOL = "NRF"

SYSTEM_PROMPT_BUG_REPORT_TRIAGE = """
Role:
You are helping turn cross-implementation {protocol} test differences into concise bug reports.

Inputs:
You will receive anomaly tests where multiple implementations produced different observable behavior, plus compact schema context for the operation inputs those tests exercise.

Task:
Group related anomalies into a small number of strong bug report candidates.

Selection rules:
- Be picky. Return only high-signal reports worth investigating.
- Prefer grouped behavior patterns over one report per test.
- Use schema_context to identify broader schema-level patterns, especially required vs optional inputs.
- Heavily prioritize repeated identical implementation error messages, especially errors that name a missing field or missing condition.
- If one implementation repeatedly rejects otherwise varied tests with the same field-specific error, focus the report on that implementation, field, and exact error instead of using a generic "inconsistent handling" summary.
- If an error says a field is missing or not found and schema_context shows that field is present but not required, treat this as a likely implementation bug or likely requiredness mismatch.
- Prefer concrete titles that name the implementation and field, such as "Open5GS likely requires optional subscrCond", over broad titles like "Inconsistent request body handling".
- Do not claim a spec violation unless the evidence is unusually clear, but do call out likely bugs when repeated errors conflict with required vs optional schema evidence.
- Use cautious wording such as "possibly affected implementations" and "observed incompatibility".
- Omit weak, isolated, ambiguous, or duplicate anomalies.
- A normal operation should return around 0 to 3 reports. Return more only for exceptional, clearly distinct patterns.

Output:
Return only a JSON array. Each item must use this exact shape:
[
  {{
    "title": "short report title",
    "description": "ticket-ready description of the observed incompatibility",
    "possibly_affected_implementations": ["implementation name"],
    "affected_rationale": "short cautious rationale, or empty string",
    "evidence_test_ids": [0, 3],
    "evidence_schema_ids": ["query.nf-type"],
    "implementation_differences": "compact status/error/body differences that support the report",
    "investigation_value": "why this is worth investigating",
    "strength": 1
  }}
]

Field rules:
- evidence_test_ids must contain only test_id values from the input.
- evidence_schema_ids must contain only keys from schema_context.schema_definitions.
- implementation_differences must preserve important status differences, error messages, and response snippets because a later coalescing step will receive only these reports.
- implementation_differences must quote exact repeated error text when present, including field names such as "No SubscrCond found in NF Subscription message".
- Repeated or generic implementation errors may become important across schema batches; include exact wording, affected implementation, status code, and why the error appears field-specific.
- When schema_context shows only certain root fields are required, mention if the repeated error appears to require some other optional field.
- strength is an integer from 1 to 10 where 10 means strongest evidence.
- possibly_affected_implementations may be empty when the evidence does not support naming an implementation.
- Keep prose compact and suitable for a Markdown bug report.
""".strip()


SYSTEM_PROMPT_BUG_REPORT_COALESCE = """
Role:
You are coalescing schema-batched {protocol} bug report candidates into final operation-level bug reports.

Inputs:
You will receive only slice-level report JSON produced from schema batches. You will not receive raw tests, raw schemas, or full implementation results.

Task:
Merge duplicate or overlapping slice reports into a small final set of strong bug report candidates.

Selection rules:
- Be picky. Prefer a few high-signal operation-level reports over many narrow reports.
- Preserve distinct behavior patterns even when they mention overlapping tests or schemas.
- Treat repeated identical error messages across multiple slice reports as top-priority evidence, not as noise to blindly deduplicate.
- If the same implementation shows the same status/error/body pattern across unrelated schema IDs, usually promote that repeated message into a focused operation-level report.
- If the repeated message names a missing field or condition, infer the likely field-level mismatch and name the implementation plus field in the title.
- If slice reports indicate the named field is optional or not root-required, phrase the result as a likely implementation bug or likely requiredness mismatch.
- Avoid broad reports like "Inconsistent Handling of Various Request Body Fields" when a repeated concrete error explains the behavior.
- Do not claim a spec violation unless the report evidence is unusually clear, but do not hide strong repeated field-specific errors behind vague compatibility language.
- Use cautious wording such as "possibly affected implementations" and "observed incompatibility".

Output:
Return only a JSON array. Each item must use this exact shape:
[
  {{
    "title": "short report title",
    "description": "ticket-ready description of the observed incompatibility",
    "possibly_affected_implementations": ["implementation name"],
    "affected_rationale": "short cautious rationale, or empty string",
    "evidence_test_ids": [0, 3],
    "evidence_schema_ids": ["query.nf-type"],
    "implementation_differences": "compact status/error/body differences, including repeated cross-slice errors when relevant",
    "investigation_value": "why this is worth investigating",
    "strength": 1
  }}
]

Field rules:
- evidence_test_ids must contain only test IDs cited by the slice reports.
- evidence_schema_ids must contain only schema IDs cited by the slice reports.
- implementation_differences must be self-contained because final Markdown rendering uses it directly.
- implementation_differences must quote exact repeated error text when it drives the final report, and include the affected implementation, status code, field name, and repeated cross-slice nature.
- Prefer final reports whose title, description, affected_rationale, implementation_differences, and investigation_value explain the specific repeated error and likely requiredness mismatch.
- strength is an integer from 1 to 10 where 10 means strongest evidence.
- Keep prose compact and suitable for a Markdown bug report.
""".strip()


def _compact_schema_node(node: Any, depth: int = 0, max_depth: int = 3) -> Any:
    if depth > max_depth:
        if isinstance(node, dict):
            return {"keys": sorted(str(key) for key in node.keys())[:40]}
        if isinstance(node, list):
            return f"<list length={len(node)}>"
        return node

    if isinstance(node, list):
        return [_compact_schema_node(item, depth + 1, max_depth) for item in node[:20]]

    if not isinstance(node, dict):
        return node

    keep_keys = {
        "$ref",
        "anyOf",
        "description",
        "enum",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "items",
        "maxItems",
        "maxLength",
        "maximum",
        "minItems",
        "minLength",
        "minimum",
        "nullable",
        "oneOf",
        "pattern",
        "properties",
        "required",
        "type",
        "uniqueItems",
    }
    compacted: Dict[str, Any] = {}
    for key, value in node.items():
        if key == "definitions":
            continue
        if key not in keep_keys:
            continue
        if key == "description":
            compacted[key] = value[:240] + "..." if isinstance(value, str) and len(value) > 240 else value
        elif key == "properties" and isinstance(value, dict):
            compacted[key] = {
                str(prop_key): _compact_schema_node(prop_value, depth + 1, max_depth)
                for prop_key, prop_value in list(value.items())[:60]
            }
        else:
            compacted[key] = _compact_schema_node(value, depth + 1, max_depth)
    if not compacted:
        compacted["keys"] = sorted(str(key) for key in node.keys())[:40]
    return compacted


def _compact_schema_context_for_prompt(schema_context: Dict[str, Any]) -> Dict[str, Any]:
    schema_definitions = schema_context.get("schema_definitions", {})
    compact_definitions: Dict[str, Any] = {}
    if isinstance(schema_definitions, dict):
        for schema_id, schema_definition in schema_definitions.items():
            if not isinstance(schema_definition, dict):
                continue
            compact_definition = {
                key: value
                for key, value in schema_definition.items()
                if key not in {"definitions"}
            }
            if isinstance(compact_definition.get("schema"), dict):
                compact_definition["schema"] = _compact_schema_node(compact_definition["schema"])
            content = compact_definition.get("content")
            if isinstance(content, dict):
                compact_content: Dict[str, Any] = {}
                for content_type, content_slice in content.items():
                    if not isinstance(content_slice, dict):
                        continue
                    compact_content[str(content_type)] = {
                        "root_required": content_slice.get("root_required", []),
                        "root_anyOf": _compact_schema_node(content_slice.get("root_anyOf")),
                        "target_schema": _compact_schema_node(content_slice.get("target_schema")),
                    }
                compact_definition["content"] = compact_content
            compact_definitions[str(schema_id)] = compact_definition

    return {
        "operation_input_summary": schema_context.get("operation_input_summary", {}),
        "schema_definitions": compact_definitions,
    }


def build_bug_report_prompt(
    operation: str,
    anomalies: List[Dict[str, Any]],
    schema_context: Dict[str, Any],
    result_file: str,
    suite_file: str,
    protocol: str = DEFAULT_PROTOCOL,
) -> str:
    input_payload = {
        "operation": operation,
        "source_test_results_file": result_file,
        "source_tests_file": suite_file,
        "schema_context": _compact_schema_context_for_prompt(schema_context),
        "anomaly_tests": anomalies,
    }
    return (
        f"Operation: {operation}\n"
        f"Protocol: {protocol}\n\n"
        "Review the following schema-batched anomaly set and return only the JSON array requested by the system prompt.\n\n"
        "Each returned report must be self-contained because the final coalescing step receives only slice reports.\n\n"
        f"{json.dumps(input_payload, indent=2, ensure_ascii=False)}"
    )


def build_bug_report_coalesce_prompt(
    operation: str,
    slice_report_batches: List[Dict[str, Any]],
    result_file: str,
    suite_file: str,
    protocol: str = DEFAULT_PROTOCOL,
) -> str:
    input_payload = {
        "operation": operation,
        "source_test_results_file": result_file,
        "source_tests_file": suite_file,
        "slice_report_batches": slice_report_batches,
    }
    return (
        f"Operation: {operation}\n"
        f"Protocol: {protocol}\n\n"
        "Coalesce the following schema-batched slice reports into final operation-level reports.\n"
        "Use only these slice reports; raw anomalies and full schema context are intentionally omitted.\n\n"
        f"{json.dumps(input_payload, indent=2, ensure_ascii=False)}"
    )
