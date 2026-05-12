#!/usr/bin/env python3
"""Test driver for OAI NRF implementation."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx

from extremal_testing.implementation_testers.common import build_request_details, load_suite_or_legacy_tests, seed_context_from_step, update_context_from_response


DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=30.0, read=30.0, write=30.0, pool=30.0)
def execute_step(
    client: httpx.Client,
    step: Dict[str, Any],
    base_url: str,
    headers: Dict[str, str],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute a single setup, test, or cleanup step."""
    seed_context_from_step(step, context)
    request_details = build_request_details(step, base_url, headers, context)
    method = request_details["method"]
    full_url = request_details["full_url"]
    request_body = request_details["request_body"]
    request_headers = request_details["headers"]

    try:
        if method == "PUT":
            response = client.put(full_url, headers=request_headers, json=request_body if request_body is not None else None, timeout=DEFAULT_TIMEOUT)
        elif method == "POST":
            response = client.post(full_url, headers=request_headers, json=request_body if request_body is not None else None, timeout=DEFAULT_TIMEOUT)
        elif method == "GET":
            response = client.get(full_url, headers=request_headers, timeout=DEFAULT_TIMEOUT)
        elif method == "DELETE":
            response = client.delete(full_url, headers=request_headers, timeout=DEFAULT_TIMEOUT)
        else:
            return {
                "status_code": None,
                "status_message": f"Unsupported method: {method}",
                "response_body": None,
                "response_headers": {},
                "response_time": None,
                "error": f"Unsupported HTTP method: {method}",
            }

        payload = {
            "status_code": response.status_code,
            "status_message": response.reason_phrase,
            "response_body": response.text if response.text else None,
            "response_headers": dict(response.headers),
            "response_time": response.elapsed.total_seconds() if hasattr(response, "elapsed") else None,
        }
        update_context_from_response(context, payload["response_headers"], payload["response_body"])
        return payload
    except httpx.TimeoutException as exc:
        return {
            "status_code": None,
            "status_message": str(exc),
            "response_body": None,
            "response_headers": {},
            "response_time": None,
            "error": f"Timeout: {str(exc)}",
            "error_type": "TimeoutException",
            "error_location": f"{method} {request_details['resource_url']}",
        }
    except httpx.RequestError as exc:
        return {
            "status_code": None,
            "status_message": str(exc),
            "response_body": None,
            "response_headers": {},
            "response_time": None,
            "error": str(exc),
            "error_type": exc.__class__.__name__,
            "error_location": f"{method} {request_details['resource_url']}",
        }


def execute_steps(
    steps: List[Dict[str, Any]],
    base_url: str,
    headers: Dict[str, str],
    client: httpx.Client,
    context: Dict[str, Any],
    stop_on_error: bool,
) -> Dict[str, Any]:
    """Execute a sequence of steps and aggregate the results."""
    step_results: List[Dict[str, Any]] = []
    for step in steps:
        result = execute_step(client, step, base_url, headers, context)
        step_results.append(result)
        if stop_on_error and result.get("status_code") is None:
            break

    return {
        "step_results": step_results,
        "status_code": step_results[-1].get("status_code") if step_results else None,
        "status_message": step_results[-1].get("status_message") if step_results else None,
        "error": next((item.get("error") for item in step_results if item.get("error")), None),
    }


def run_nrf_tests(
    test_cases_file: str,
    base_url: str = "http://localhost:8080/nnrf-nfm/v1",
) -> str:
    """Run test cases against the OAI NRF and return the results file path."""
    try:
        suite = load_suite_or_legacy_tests(test_cases_file, Path(test_cases_file).stem.replace("_tests", ""))
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Error loading test cases file: {exc}")
        sys.exit(1)

    tests = suite.get("tests", [])
    if not isinstance(tests, list):
        print("Error: test suite must contain a tests array")
        sys.exit(1)

    operation_name = str(suite.get("operation") or Path(test_cases_file).stem.replace("_tests", ""))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_dir = Path(__file__).resolve().parent.parent
    results_dir = script_dir / "data" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_file = str(results_dir / f"nrf_test_results_oai_{operation_name}_{timestamp}.json")

    results: List[Dict[str, Any]] = []
    headers = {"Content-Type": "application/json"}
    total_cases = len(tests)
    shared_setup = suite.get("setup", [])
    shared_cleanup = suite.get("cleanup", [])

    for i, test_case in enumerate(tests, 1):
        test_name = test_case.get("name", f"Test case {i}")
        violated_constraints = test_case.get("violated_constraints", [])
        constraint_text = violated_constraints[0] if violated_constraints else "Unknown constraint"

        print(f"\n[{i}/{total_cases}] {test_name}")
        print(f"  Constraint: {constraint_text[:80]}...")

        with httpx.Client(http1=False, http2=True, timeout=DEFAULT_TIMEOUT) as client:
            context: Dict[str, Any] = {}

            setup_steps = list(shared_setup)
            legacy_setup = test_case.get("driving_state")
            if legacy_setup:
                setup_steps.append(legacy_setup)

            setup_summary = execute_steps(setup_steps, base_url, headers, client, context, stop_on_error=True)

            request = test_case.get("request", {})
            if request:
                seed_context_from_step(request, context)
                response = execute_step(client, request, base_url, headers, context)
            else:
                response = {
                    "status_code": None,
                    "status_message": "No request found in test case",
                    "response_body": None,
                    "response_headers": {},
                    "response_time": None,
                    "error": "Test case missing request field",
                }

            update_context_from_response(context, response.get("response_headers"), response.get("response_body"))
            cleanup_context = dict(context)
            cleanup_summary = execute_steps(shared_cleanup, base_url, headers, client, cleanup_context, stop_on_error=False)

        result = {
            "test_case_index": i - 1,
            "test_name": test_name,
            "operation": operation_name,
            "constraint": constraint_text,
            "setup_status_code": setup_summary.get("status_code"),
            "setup_status_message": setup_summary.get("status_message"),
            "setup_error": setup_summary.get("error"),
            "status_code": response.get("status_code"),
            "status_message": response.get("status_message", ""),
            "response_body": response.get("response_body"),
            "response_time": response.get("response_time"),
            "response_headers": response.get("response_headers"),
            "cleanup_status_code": cleanup_summary.get("status_code"),
            "cleanup_status_message": cleanup_summary.get("status_message"),
            "cleanup_error": cleanup_summary.get("error"),
            "error": response.get("error"),
        }
        results.append(result)

        if result["status_code"] is not None:
            print(f"  Status: {result['status_code']} {result['status_message']}")
        else:
            print(f"  Error: {result.get('error') or result.get('setup_error')}")

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n[✓] Test complete. Results saved to {results_file}")
    return results_file


def main() -> None:
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print("Usage: python test_oai.py <test_cases_file> [base_url]")
        print(
            "  test_cases_file: Path to JSON file containing a suite object or legacy JSON array "
            "(e.g., data/generated/NFStatusSubscribe_tests.json)"
        )
        print("  base_url: Optional base URL for NRF (default: http://localhost:8080/nnrf-nfm/v1)")
        sys.exit(1)

    test_cases_file = sys.argv[1]
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8080/nnrf-nfm/v1"
    run_nrf_tests(test_cases_file, base_url)


if __name__ == "__main__":
    main()
