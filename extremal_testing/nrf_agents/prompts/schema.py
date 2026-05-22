"""Prompt helpers for schema and constraint extraction."""

from __future__ import annotations

import json
from typing import Any, Dict

from extremal_testing.nrf_agents.models.common import OperationMetadata


_SCHEMA_VALUE_KEYS = {
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
        if key in {"properties", "patternProperties", "dependentSchemas"} and isinstance(value, dict):
            compacted[key] = {prop_key: _compact_schema_for_prompt(prop_value) for prop_key, prop_value in value.items()}
        elif key in {"items", "additionalProperties", "not", "contains", "schema", "content", "request_body", "requestBody", "parameters"}:
            compacted[key] = _compact_schema_for_prompt(value)
        elif key in {"allOf", "anyOf", "oneOf"} and isinstance(value, list):
            compacted[key] = [_compact_schema_for_prompt(item) for item in value]
        elif key in _SCHEMA_VALUE_KEYS or key in _PARAMETER_KEYS:
            compacted[key] = _trim_text(value) if key == "description" else value
    return compacted


SYSTEM_PROMPT_SCHEMA_EXTRACTION = """
You are an expert in OpenAPI specifications and API constraint extraction.

Given an operation definition and its resolved input schema, extract all validity constraints that apply to the operation inputs.

Constraints should be written as short, atomic natural-language sentences that describe validation rules, requirements, limitations, and conditional behavior for:
- path/query/header parameters
- request bodies and content types
- required fields
- schema limits such as enum, pattern, minimum, maximum, minItems, maxItems, and related constraints

Return your response as a valid JSON object with the following structure:
{
  "constraints": [
    // Array of natural-language sentences describing validity constraints
    // Each constraint should be a complete sentence
    // Only include constraints that are supported by the operation definition or resolved input schema
  ]
}

Important:
- Use the provided resolved input schema as the source of truth for input constraints
- Include constraints implied by schema keywords and parameter metadata
- Do not include response-only behavior or unrelated operation details
- Split combined rules into separate constraint sentences when possible
- Return only valid JSON, no markdown code blocks or additional text
""".strip()


def build_operation_schema_prompt(
    operation: OperationMetadata,
    operation_spec: Dict[str, Any],
    resolved_input_schema: Dict[str, Any],
) -> str:
    operation_spec_json = json.dumps(operation_spec, indent=2, ensure_ascii=False)
    compact_input_schema = _compact_schema_for_prompt(resolved_input_schema)
    input_schema_json = json.dumps(compact_input_schema, indent=2, ensure_ascii=False)

    return f"""Analyze the following OpenAPI operation definition and extract all input constraints:

Operation Name: {operation.operation}
Path: {operation.path}
HTTP Method: {operation.method}
Description: {operation.description or 'N/A'}

Operation Definition:
{operation_spec_json}

Resolved Input Schema:
{input_schema_json}

Return your response as a valid JSON object with a single "constraints" key."""
