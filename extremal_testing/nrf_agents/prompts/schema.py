"""Prompt helpers for schema and constraint extraction."""

from __future__ import annotations

import json
from typing import Any, Dict

from extremal_testing.nrf_agents.models.common import OperationMetadata


_SCHEMA_VALUE_KEYS = {
    "$ref",
    "schema_id",
    "location",
    "source",
    "type",
    "format",
    "nullable",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
    "enum",
    "const",
    "default",
    "required",
    "readOnly",
    "writeOnly",
    "minItems",
    "maxItems",
    "minProperties",
    "maxProperties",
    "description",
}

_SCHEMA_WRAPPER_KEYS = {
    "definitions",
    "constraint_index",
    "parameters",
    "request_body",
    "requestBody",
    "content",
    "schema",
    "properties",
    "patternProperties",
    "dependentSchemas",
    "items",
    "additionalProperties",
    "not",
    "contains",
    "allOf",
    "anyOf",
    "oneOf",
}

_PARAMETER_KEYS = {
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


def _trim_text(text: Any, limit: int = 280) -> Any:
    if not isinstance(text, str):
        return text
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _compact_schema_for_prompt(node: Any) -> Any:
    if isinstance(node, list):
        return [_compact_schema_for_prompt(item) for item in node]
    if not isinstance(node, dict):
        return node

    compacted: Dict[str, Any] = {}
    for key, value in node.items():
        if key in {"properties", "patternProperties", "dependentSchemas", "definitions"} and isinstance(value, dict):
            compacted[key] = {prop_key: _compact_schema_for_prompt(prop_value) for prop_key, prop_value in value.items()}
        elif key in {"items", "additionalProperties", "not", "contains", "schema", "content", "request_body", "requestBody", "parameters", "input_schema", "definitions", "constraint_index", "rules"}:
            compacted[key] = _compact_schema_for_prompt(value)
        elif key in {"allOf", "anyOf", "oneOf"} and isinstance(value, list):
            compacted[key] = [_compact_schema_for_prompt(item) for item in value]
        elif key in _SCHEMA_VALUE_KEYS or key in _PARAMETER_KEYS:
            compacted[key] = _trim_text(value) if key == "description" else value
    return compacted


SYSTEM_PROMPT_CONSTRAINT_EXTRACTION = """
You are an expert in OpenAPI specifications and API constraint extraction.

You will receive:
- one OpenAPI operation definition
- one compact operation input schema graph
- one deterministic constraint_index listing constraint-bearing schema paths

Task:
Extract all validity constraints that apply to the operation inputs using constraint_index as the primary source.

Constraints must be:
- short
- atomic
- written as clear MUST statements
- specific to the input schema fields provided
- derived only from the operation definition and compact schema graph

Return your response as a valid JSON object with the following structure:
{
  "constraints": [
    {
      "schema_id": "request_body.fieldName",
      "constraint": "request_body.fieldName MUST satisfy the indexed rule."
    }
  ]
}

Important:
- Every constraint MUST contain an explicit MUST statement
- Every returned constraint object MUST contain exactly two keys: schema_id and constraint
- Use schema_id values from constraint_index
- Use constraint_index as the primary source of truth
- Use the exact field names and request locations from the schema graph when possible
- Do not include response-only behavior or unrelated operation details
- Split combined rules into separate sentences when possible
- Return only valid JSON, no markdown code blocks or additional text
""".strip()


def build_operation_schema_prompt(
    operation: OperationMetadata,
    operation_spec: Dict[str, Any],
    schema_graph: Dict[str, Any],
) -> str:
    operation_spec_json = json.dumps(operation_spec, indent=2, ensure_ascii=False)
    compact_schema_graph = _compact_schema_for_prompt(schema_graph)
    schema_graph_json = json.dumps(compact_schema_graph, indent=2, ensure_ascii=False)

    return f"""Analyze the following OpenAPI operation definition and extract all input constraints from the compact schema graph below.

Operation Name: {operation.operation}
Path: {operation.path}
HTTP Method: {operation.method}
Description: {operation.description or 'N/A'}

Operation Definition:
{operation_spec_json}

Compact Schema Graph:
{schema_graph_json}

Rules:
1. Return only constraints that apply to operation inputs.
2. Every constraint MUST be a standalone MUST statement.
3. Use constraint_index as the primary source; do not stop at top-level parameters.
4. Write one atomic constraint per meaningful indexed rule.
5. Each constraint object MUST contain exactly schema_id and constraint.
6. Return a valid JSON object with a single "constraints" key.
"""


SYSTEM_PROMPT_SCHEMA_EXTRACTION = SYSTEM_PROMPT_CONSTRAINT_EXTRACTION
