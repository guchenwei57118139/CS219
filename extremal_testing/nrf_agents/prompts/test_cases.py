"""Prompt helpers for test-case generation."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from extremal_testing.nrf_agents.models.common import OperationInfo, TestFormat


def build_test_case_prompt(
    operation: OperationInfo,
    constraint: Dict[str, Any],
    shared_setup: List[Dict[str, Any]],
    shared_cleanup: List[Dict[str, Any]],
    test_format: TestFormat,
    constraint_index: int,
) -> str:
    suite_format_json = json.dumps(test_format.suite_structure, indent=2)
    step_format_json = json.dumps(test_format.step_structure, indent=2)
    test_format_json = json.dumps(test_format.test_case_structure, indent=2)
    setup_json = json.dumps(shared_setup, indent=2)
    cleanup_json = json.dumps(shared_cleanup, indent=2)
    constraint_schema_id = str(constraint.get("schema_id", "unknown"))
    constraint_text = str(constraint.get("constraint", ""))

    return f"""Generate exactly two test cases for the operation below: one positive and one negative.

Operation: {operation.operation}
Path: {operation.path}
Method: {operation.method}
Constraint index: {constraint_index}
Constraint schema id: {constraint_schema_id}

Shared setup executed before every test in this suite:
{setup_json}

Shared cleanup executed after every test in this suite:
{cleanup_json}

Input Schema:
{json.dumps(operation.input_schema, indent=2)}

Schema Definitions:
{json.dumps(operation.definitions, indent=2)}

Constraint to violate:
{constraint_text}

Suite format:
{suite_format_json}

Step format:
{step_format_json}

Target suite/test format:
{test_format_json}

Rules:
1. Return only a single JSON object with exactly these keys: positive_test_case, negative_test_case.
2. Each test case object may include only: name, constraint, method, path, headers, body.
3. Do not include request, violated_constraints, driving_state, setup, cleanup, description, notes, or id.
4. The positive test case must satisfy the supplied constraint.
5. The negative test case must violate the supplied constraint.
6. Use the shared setup context instead of inventing test-specific prerequisite state.
7. Keep Content-Type as application/json unless the constraint requires otherwise.
8. The target NRF type should always be NRF.
9. Return valid JSON only, with no markdown or explanation.
"""
