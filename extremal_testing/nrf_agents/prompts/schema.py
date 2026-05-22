"""Prompt helpers for schema and constraint extraction."""

from __future__ import annotations

from typing import Any, Dict

from nrf_agents.models.common import OperationMetadata


SYSTEM_PROMPT_SCHEMA_EXTRACTION = """
You are an expert in OpenAPI specifications and API schema extraction. Your task is to analyze the provided OpenAPI specification and extract the input schema and constraints for a specific operation.

Given an operation (identified by its path and HTTP method), you must:
1. Locate the operation in the OpenAPI specification
2. Extract the request body schema (if present) - this includes the structure, types, and references
3. Extract all validity constraints from the specification text related to this operation

Constraints should be written as natural-language sentences that describe validation rules, requirements, or limitations found in the specification text. Do not invent constraints that are not explicitly stated or implied in the specification.

Return your response as a valid JSON object with the following structure:
{
  "input_schema": {
    // JSON schema structure representing the request body
    // Include properties, types, required fields, references, etc.
    // If there is no request body, this should be an empty object {}
  },
  "constraints": [
    // Array of natural-language sentences describing validity constraints
    // Each constraint should be a complete sentence
    // Only include constraints that are explicitly stated in the specification
  ]
}

Important:
- The input_schema should represent the complete request body structure
- Include schema references ($ref) as they appear in the specification
- Include parameter information (query, path, header parameters) if relevant
- Constraints must be derived directly from the specification text
- Do not include constraints that are not supported by the specification
- Return only valid JSON, no markdown code blocks or additional text
""".strip()


def build_operation_schema_prompt(operation: OperationMetadata, spec_content: str) -> str:
    return f"""Analyze the following OpenAPI specification and extract the input schema and constraints for this operation:

Operation Name: {operation.operation}
Path: {operation.path}
HTTP Method: {operation.method}
Description: {operation.description or 'N/A'}

OpenAPI Specification:
{spec_content}

Please extract:
1. The input_schema (request body structure, parameters, etc.) for the operation at path "{operation.path}" with method "{operation.method}"
2. All validity constraints from the specification text related to this operation

Return your response as a valid JSON object with "input_schema" and "constraints" keys."""

