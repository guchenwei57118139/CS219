#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from extremal_testing.implementation_testers.common import (
    build_request_details,
    load_suite_or_legacy_tests,
    seed_context_from_step,
    update_context_from_response,
)


DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=30.0, read=30.0, write=30.0, pool=30.0)


def restart_nrf_container():
    """
    Restart the NRF container automatically using docker command.
    Returns True if successful, False otherwise.
    """
    try:
        print("\nAttempting to automatically restart NRF container...")
        result = subprocess.run(
            ["docker", "restart", "nrf"],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.returncode == 0:
            print("NRF container restart successful")
            print("Waiting 5 seconds for NRF to initialize...")
            time.sleep(5)
            return True
        print("Failed to restart NRF container")
        print(f"Error: {result.stderr}")
        return False
    except subprocess.CalledProcessError as e:
        print("Failed to restart NRF container")
        print(f"Error: {e.stderr}")
        return False
    except Exception as e:
        print("Failed to restart NRF container")
        print(f"Unexpected error: {str(e)}")
        return False


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
            response = client.request("DELETE", full_url, headers=request_headers, json=request_body if request_body is not None else None, timeout=DEFAULT_TIMEOUT)
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


def run_nrf_tests(test_cases_file, resume_file=None, auto_restart=True, max_restarts=10):
    """
    Run NRF tests using HTTPX with HTTP/2 prior knowledge.
    Supports both the new suite format and legacy JSON arrays.
    """
    try:
        suite = load_suite_or_legacy_tests(test_cases_file, Path(test_cases_file).stem.replace("_tests", ""))
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Error parsing JSON file: {exc}")
        sys.exit(1)

    tests = suite.get("tests", [])
    if not isinstance(tests, list):
        print("Error: Test cases file must contain a suite tests array")
        sys.exit(1)

    base_url = "http://localhost:7777/nnrf-nfm/v1"
    base_headers = {"Content-Type": "application/json"}

    test_path = Path(test_cases_file)
    stem = test_path.stem
    if "_tests" in stem:
        input_name = stem.split("_tests", 1)[0]
    elif "_test" in stem:
        input_name = stem.split("_test", 1)[0]
    else:
        input_name = stem

    project_root = Path(__file__).resolve().parent  # .../extremal_testing
    results_dir = project_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_file = str(results_dir / f"nrf_test_results_open5gs_{input_name}.json")

    results = []
    start_index = 0
    restart_count = 0
    shared_setup = suite.get("setup", [])
    shared_cleanup = suite.get("cleanup", [])

    if resume_file and os.path.exists(resume_file):
        try:
            with open(resume_file, "r", encoding="utf-8") as f:
                resume_data = json.load(f)
                if isinstance(resume_data, dict) and "results" in resume_data:
                    results = resume_data["results"]
                    if "crash_info" in resume_data:
                        print(f"\nPrevious crash detected at test case index: {resume_data['crash_info']['crash_index']}")
                        print("Crashed payload:")
                        print(json.dumps(resume_data["crash_info"]["crashed_payload"], indent=2))
                else:
                    results = resume_data

                if results:
                    start_index = max(r.get("test_case_index", -1) for r in results) + 1
                    print(f"Resuming from test case {start_index + 1}")
        except Exception as e:
            print(f"Error loading resume file: {e}")
            print("Starting from the beginning")

    def save_progress(crashed_payload=None):
        progress_data = {
            "results": results,
            "last_completed_index": results[-1]["test_case_index"] if results else -1,
            "timestamp": datetime.now().isoformat(),
            "total_test_cases": len(tests),
            "completed_test_cases": len(results),
        }

        if crashed_payload is not None:
            progress_data["crash_info"] = {
                "crashed_payload": crashed_payload,
                "crash_index": results[-1]["test_case_index"] if results else -1,
            }

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(progress_data, f, indent=2)
        print(f"\nProgress saved to {results_file}")

    def should_restart(summary: Dict[str, Any]) -> bool:
        error = summary.get("error")
        return bool(error and "Server disconnected" in str(error))

    try:
        i = start_index
        while i < len(tests):
            with httpx.Client(http1=False, http2=True, timeout=DEFAULT_TIMEOUT) as client:
                test_case = tests[i]
                print(f"\nProcessing test case {i + 1}/{len(tests)}")

                name = test_case.get("name", f"Test case {i + 1}")
                violated_constraints = test_case.get("violated_constraints", [])
                constraint_text = violated_constraints[0] if violated_constraints else ""

                context: Dict[str, Any] = {}
                setup_steps = list(shared_setup)
                legacy_setup = test_case.get("driving_state")
                if legacy_setup:
                    setup_steps.append(legacy_setup)

                setup_summary = execute_steps(setup_steps, base_url, base_headers, client, context, stop_on_error=True)

                request_def = test_case.get("request", {})
                if not request_def:
                    resp_info = {
                        "status_code": None,
                        "reason_phrase": "No request in test case",
                        "response_time": None,
                        "response_headers": None,
                        "response_body": None,
                        "error": "Missing request field",
                    }
                else:
                    seed_context_from_step(request_def, context)
                    resp_info = execute_step(client, request_def, base_url, base_headers, context)

                update_context_from_response(context, resp_info.get("response_headers"), resp_info.get("response_body"))
                cleanup_context = dict(context)
                cleanup_summary = execute_steps(shared_cleanup, base_url, base_headers, client, cleanup_context, stop_on_error=False)

                result = {
                    "test_case_index": i,
                    "name": name,
                    "constraint": constraint_text,
                    "setup_status_code": setup_summary.get("status_code"),
                    "setup_status_message": setup_summary.get("status_message"),
                    "setup_error": setup_summary.get("error"),
                    "status_code": resp_info.get("status_code"),
                    "reason_phrase": resp_info.get("status_message"),
                    "response_time": resp_info.get("response_time"),
                    "response_headers": resp_info.get("response_headers"),
                    "response_body": resp_info.get("response_body"),
                    "cleanup_status_code": cleanup_summary.get("status_code"),
                    "cleanup_status_message": cleanup_summary.get("status_message"),
                    "cleanup_error": cleanup_summary.get("error"),
                    "error": resp_info.get("error"),
                }
                results.append(result)

                if result["status_code"] is not None:
                    print(f"  Status: {result['status_code']} {result['reason_phrase']}")
                else:
                    print(f"  Error: {result['error']}")

                if any(should_restart(summary) for summary in (setup_summary, resp_info, cleanup_summary)) and auto_restart:
                    print("\n*** NRF SERVICE CRASH DETECTED ***")
                    print("Crashed test case payload:")
                    print(json.dumps(test_case, indent=2))
                    save_progress(test_case)
                    restart_count += 1
                    if restart_count <= max_restarts:
                        print(f"\nAutomatically restarting NRF (restart #{restart_count})...")
                        restart_nrf_container()
                    else:
                        print("Maximum restart attempts reached, stopping further restarts.")

                if (i + 1) % 20 == 0:
                    save_progress()

                time.sleep(0.1)
                i += 1
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    finally:
        save_progress()

    success_count = sum(1 for r in results if r.get("status_code") in [200, 201, 204])
    print(f"\nTest complete. Results saved to {results_file}")
    print(f"Summary: {success_count}/{len(results)} tests successful")
    print(f"NRF container was automatically restarted {restart_count} times")

    return results_file


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="NRF Testing Tool with automatic recovery (Open5GS, suite-aware)"
    )
    parser.add_argument(
        "test_cases_file",
        help=(
            "JSON file containing a suite object or legacy array "
            "(e.g., testing_cases/NFStatusSubscibe_tests.json, "
            "testing_cases/NFDeregister_tests.json, "
            "testing_cases/NFRegister_tests.json, or "
            "testing_cases/NFStatusNotify_tests.json)"
        ),
    )
    parser.add_argument("-r", "--resume", help="Resume from a previous test results file")
    parser.add_argument("--no-auto-restart", action="store_true", help="Disable automatic restart of NRF container")
    parser.add_argument("--max-restarts", type=int, default=10, help="Maximum number of automatic restarts")

    args = parser.parse_args()

    results_file = run_nrf_tests(
        args.test_cases_file,
        args.resume,
        auto_restart=not args.no_auto_restart,
        max_restarts=args.max_restarts,
    )

    print(f"To resume testing later, use: python {sys.argv[0]} {args.test_cases_file} -r {results_file}")
