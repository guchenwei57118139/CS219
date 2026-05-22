"""Prompt helpers for confidence scoring."""

from __future__ import annotations

from typing import Any, Dict, List

DEFAULT_PROTOCOL = "NRF"

SYSTEM_PROMPT_CONFIDENCE_TRIAGE = """
Role:
You are helping triage differences between {protocol} implementations.

Inputs:
You will receive test results where multiple implementations produced
different responses for the same test case.

Field description:
The test results follow this JSON output format:
[
  {{
    "test_id": 0,
    "test_name": "string",
    "original_test_case": {{
      "name": "string",
      "constraint": "string",
      "method": "string",
      "path": "string",
      "headers": {{ }},
      "body": {{ }}
    }},
    "implementations": {{
      "free5gc": {{
        "status_code": 200,
        "response_body": "string or null",
        "error": "string or null"
      }},
      "oai": {{
        "status_code": 201,
        "response_body": "string or null",
        "error": "string or null"
      }},
      "open5gs": {{
        "status_code": 201,
        "response_body": "string or null",
        "error": "string or null"
      }}
    }}
  }}
]

Task:
For each test:
1. Reason about the differences between implementation outputs.
2. Decide whether one implementation likely violates the RFC.
3. Consider whether the difference might be acceptable behavior or configuration.
4. Write a short comment explaining the judgment.
5. Assign confidence from 0 to 10.

Confidence:
0 = probably not a bug.
10 = almost certainly a real RFC violation / implementation bug.

Output:
Return only a JSON array:
[
  {{
    "test_id": <same test_id as input>,
    "comment": "<short explanation>",
    "confidence": <integer 0-10>
  }}
]
""".strip()


def build_confidence_prompt(operation: str, batch: List[Dict[str, Any]], result_file: str, suite_file: str, protocol: str = DEFAULT_PROTOCOL) -> str:
    import json

    input_payload = {
        "operation": operation,
        "source_test_results_file": result_file,
        "source_tests_file": suite_file,
        "tests": batch,
    }
    return (
        f"Operation: {operation}\n"
        f"Protocol: {protocol}\n\n"
        "Review the following anomaly batch and return only the JSON array requested by the system prompt.\n\n"
        f"{json.dumps(input_payload, indent=2, ensure_ascii=False)}"
    )

