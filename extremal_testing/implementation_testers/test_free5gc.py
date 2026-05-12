#!/usr/bin/env python3
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests

from extremal_testing.implementation_testers.common import (
    build_request_details,
    load_suite_or_legacy_tests,
    seed_context_from_step,
    update_context_from_response,
)
def check_nrf_health(base_url: str) -> bool:
    """Check if the NRF container is responding."""
    try:
        health_url = base_url.rstrip("/") + "/nf-instances"
        response = requests.get(health_url, timeout=10)
        return response.status_code is not None
    except requests.RequestException:
        try:
            root_url = base_url.rstrip("/")
            requests.get(root_url, timeout=5)
            return True
        except requests.RequestException:
            return False


def execute_step(
    client: requests.Session,
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
            response = client.put(full_url, headers=request_headers, json=request_body if request_body is not None else None, timeout=10)
        elif method == "POST":
            response = client.post(full_url, headers=request_headers, json=request_body if request_body is not None else None, timeout=10)
        elif method == "GET":
            response = client.get(full_url, headers=request_headers, timeout=10)
        elif method == "DELETE":
            response = client.delete(full_url, headers=request_headers, json=request_body if request_body is not None else None, timeout=10)
        else:
            return {
                "status_code": None,
                "status_message": f"Unsupported method: {method}",
                "response_body": None,
                "response_headers": {},
                "error": f"Unsupported HTTP method: {method}",
            }

        response_payload = {
            "status_code": response.status_code,
            "status_message": response.reason,
            "response_body": response.text if response.text else None,
            "response_headers": dict(response.headers),
        }
        update_context_from_response(context, response_payload["response_headers"], response_payload["response_body"])
        return response_payload
    except requests.RequestException as exc:
        return {
            "status_code": None,
            "status_message": str(exc),
            "response_body": None,
            "response_headers": {},
            "error": str(exc),
        }


def execute_steps(
    steps: List[Dict[str, Any]],
    base_url: str,
    headers: Dict[str, str],
    client: requests.Session,
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


def run_nrf_tests(test_cases_file: str, base_url: str = "http://localhost:7778/nnrf-nfm/v1") -> str:
    """Run test cases against the Free5GC NRF and return the results file path."""
    try:
        suite = load_suite_or_legacy_tests(test_cases_file, Path(test_cases_file).stem.replace("_tests", ""))
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Error loading test cases file: {exc}")
        sys.exit(1)

    tests = suite.get("tests", [])
    if not isinstance(tests, list):
        print("Error: test suite must contain a tests array")
        sys.exit(1)

    print(f"[*] Checking NRF health at {base_url}...")
    if not check_nrf_health(base_url):
        print(f"[!] Error: NRF container is not responding at {base_url}")
        print("[!] Please ensure Free5GC NRF is running and accessible")
        sys.exit(1)
    print("[✓] NRF is responding")

    headers = {"Content-Type": "application/json"}
    operation_name = str(suite.get("operation") or Path(test_cases_file).stem.replace("_tests", ""))

    results: List[Dict[str, Any]] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_dir = Path(__file__).resolve().parent.parent
    results_dir = script_dir / "data" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_file = str(results_dir / f"nrf_test_results_free5gc_{operation_name}_{timestamp}.json")

    total_cases = len(tests)
    shared_setup = suite.get("setup", [])
    shared_cleanup = suite.get("cleanup", [])

    for i, test_case in enumerate(tests, 1):
        test_name = test_case.get("name", f"Test case {i}")
        violated_constraints = test_case.get("violated_constraints", [])
        constraint_text = violated_constraints[0] if violated_constraints else "Unknown constraint"
        print(f"\n[{i}/{total_cases}] {test_name}")
        print(f"  Constraint: {constraint_text[:80]}...")

        with requests.Session() as client:
            context: Dict[str, Any] = {}

            setup_steps = list(shared_setup)
            legacy_setup = test_case.get("driving_state")
            if legacy_setup:
                setup_steps.append(legacy_setup)

            setup_summary = execute_steps(setup_steps, base_url, headers, client, context, stop_on_error=True)

            request_def = test_case.get("request", {})
            if request_def:
                seed_context_from_step(request_def, context)
                response = execute_step(client, request_def, base_url, headers, context)
            else:
                response = {
                    "status_code": None,
                    "status_message": "No request found in test case",
                    "response_body": None,
                    "response_headers": {},
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
            "cleanup_status_code": cleanup_summary.get("status_code"),
            "cleanup_status_message": cleanup_summary.get("status_message"),
            "cleanup_error": cleanup_summary.get("error"),
            "error": response.get("error"),
        }
        results.append(result)

        if result["status_code"]:
            print(f"  Status: {result['status_code']} {result['status_message']}")
        else:
            print(f"  Error: {result.get('error') or result.get('setup_error')}")

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n[✓] Test complete. Results saved to {results_file}")
    return results_file


def main() -> None:
    """Main entry point for the test driver."""
    if len(sys.argv) < 2:
        print("Usage: python test_free5gc.py <test_cases_file> [base_url]")
        print(
            "  test_cases_file: Path to JSON file containing a suite object or legacy JSON array "
            "(e.g., data/generated/NFStatusSubscribe_tests.json)"
        )
        print("  base_url: Optional base URL for NRF (default: http://localhost:7778/nnrf-nfm/v1)")
        sys.exit(1)

    test_cases_file = sys.argv[1]
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:7778/nnrf-nfm/v1"
    run_nrf_tests(test_cases_file, base_url)


if __name__ == "__main__":
    main()
