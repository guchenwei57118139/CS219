"""Prompt helpers for test-case generation."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from extremal_testing.nrf_agents.models.common import OperationInfo, TestFormat


def build_test_case_chunk_prompt(
    operation: OperationInfo,
    constraint_items: List[Dict[str, Any]],
    shared_setup: List[Dict[str, Any]],
    shared_cleanup: List[Dict[str, Any]],
    test_format: TestFormat,
) -> str:
    suite_format_json = json.dumps(test_format.suite_structure, indent=2)
    step_format_json = json.dumps(test_format.step_structure, indent=2)
    test_format_json = json.dumps(test_format.test_case_structure, indent=2)
    setup_json = json.dumps(shared_setup, indent=2)
    cleanup_json = json.dumps(shared_cleanup, indent=2)
    constraint_items_json = json.dumps(constraint_items, indent=2)

    return f"""Generate positive and negative test cases for each constraint below.

Operation: {operation.operation}
Path: {operation.path}
Method: {operation.method}

Shared setup executed before every test in this suite:
{setup_json}

Shared cleanup executed after every test in this suite:
{cleanup_json}

Constraint items:
{constraint_items_json}

Suite format:
{suite_format_json}

Step format:
{step_format_json}

Target suite/test format:
{test_format_json}

Rules:
1. Return only a single JSON object with exactly one top-level key: test_pairs.
2. test_pairs must be an array with one object per constraint item you can handle.
3. Each test_pairs item must include constraint_id, positive_test_case, and negative_test_case.
4. Each positive_test_case and negative_test_case may include only: name, constraint, method, path, headers, body.
5. The positive test case must satisfy that item's constraint.
6. The negative test case must violate only that item's constraint while keeping other inputs valid.
7. Use the provided schema_slice for each item; do not require the full operation schema.
8. Use the shared setup context instead of inventing test-specific prerequisite state.
9. Keep Content-Type as application/json unless the constraint requires otherwise.
10. The target NRF type should always be NRF.
11. Return valid JSON only, with no markdown or explanation.
"""
