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
- Do not claim a spec violation unless the evidence is unusually clear.
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
    "investigation_value": "why this is worth investigating",
    "strength": 1
  }}
]

Field rules:
- evidence_test_ids must contain only test_id values from the input.
- evidence_schema_ids must contain only keys from schema_context.schema_definitions.
- strength is an integer from 1 to 10 where 10 means strongest evidence.
- possibly_affected_implementations may be empty when the evidence does not support naming an implementation.
- Keep prose compact and suitable for a Markdown bug report.
""".strip()


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
        "schema_context": schema_context,
        "anomaly_tests": anomalies,
    }
    return (
        f"Operation: {operation}\n"
        f"Protocol: {protocol}\n\n"
        "Review the following anomaly set and return only the JSON array requested by the system prompt.\n\n"
        f"{json.dumps(input_payload, indent=2, ensure_ascii=False)}"
    )
