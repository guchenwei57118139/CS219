"""Prompt helpers for schema and constraint extraction."""

from __future__ import annotations

import json
from typing import Any, Dict

from extremal_testing.nrf_agents.models.common import OperationMetadata


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
    input_schema_json = json.dumps(resolved_input_schema, indent=2, ensure_ascii=False)

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
