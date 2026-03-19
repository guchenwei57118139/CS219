import json
import sys
import httpx
import os
import subprocess
import time
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path


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
            check=True
        )
        if result.returncode == 0:
            print("NRF container restart successful")
            print("Waiting 5 seconds for NRF to initialize...")
            time.sleep(5)  # Give more time for NRF to fully initialize
            return True
        else:
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


def build_full_url(resource_url, base_url):
    """
    Build a full URL from a resource path and a base URL.

    Supported patterns:
    - '/nnrf-nfm/v1/...' absolute API path (use base_url scheme+host)
    - Other paths starting with '/' (append to base_url)
    - Relative paths without a leading '/' (treat as a sub-path)
    """
    if resource_url.startswith("/nnrf-nfm/v1"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{resource_url}"
    elif resource_url.startswith("/"):
        return base_url.rstrip("/") + resource_url
    else:
        return base_url.rstrip("/") + "/" + resource_url


def execute_driving_state(client, driving_state, base_url, base_headers):
    """
    Execute the driving_state request (if present) and return a subscriptionId if it can be parsed.

    This function does not perform token-based auth; it only sends the request and tries to extract the
    subscription identifier from the response.
    """
    if not driving_state:
        return None

    resource_url = driving_state.get("resource_url", "")
    method = driving_state.get("method", "GET").upper()
    body = driving_state.get("request_body", {})
    headers = dict(base_headers)
    headers.update(driving_state.get("headers", {}))

    full_url = build_full_url(resource_url, base_url)

    if method == "PUT":
        resp = client.put(full_url, headers=headers, json=body or None, timeout=10.0)
    elif method == "POST":
        resp = client.post(full_url, headers=headers, json=body or None, timeout=10.0)
    elif method == "GET":
        resp = client.get(full_url, headers=headers, timeout=10.0)
    elif method == "DELETE":
        resp = client.delete(full_url, headers=headers, timeout=10.0)
    else:
        print(f"  [driving_state] Unsupported method: {method}")
        return None

    print(f"  [driving_state] {method} {full_url} -> {resp.status_code}")

    sub_id = None
    if resp.status_code in (200, 201, 204):
        # 1) Extract .../subscriptions/{id} from the Location header.
        loc = resp.headers.get("Location", "")
        if loc and "subscriptions" in loc:
            sub_id = loc.split("subscriptions/")[-1].split("/")[0]

        # 2) Fall back to searching for 'subscriptionId' in JSON response body.
        if not sub_id:
            try:
                body_json = resp.json()
                if isinstance(body_json, dict) and "subscriptionId" in body_json:
                    sub_id = body_json["subscriptionId"]
            except ValueError:
                pass

    return sub_id


def execute_test_request(client, request_def, base_url, base_headers, driving_state_data=None):
    """
    Execute the actual test request (the 'request' field).

    Supports injecting a subscriptionId obtained from driving_state into the request URL.
    Returns a dict with status_code / reason_phrase / response_time / headers / body / error.
    """
    resource_url = request_def.get("resource_url", "")
    method = request_def.get("method", "GET").upper()
    body = request_def.get("request_body", {})
    headers = dict(base_headers)
    headers.update(request_def.get("headers", {}))

    # Inject subscriptionId into URL if needed.
    if driving_state_data and "{subscriptionId}" in resource_url:
        resource_url = resource_url.replace("{subscriptionId}", driving_state_data)
    elif driving_state_data and "subscriptions" in resource_url and "{subscriptionId}" not in resource_url:
        if resource_url.rstrip("/").endswith("/subscriptions"):
            resource_url = resource_url.rstrip("/") + f"/{driving_state_data}"

    full_url = build_full_url(resource_url, base_url)

    if method == "PUT":
        resp = client.put(full_url, headers=headers, json=body or None, timeout=10.0)
    elif method == "POST":
        resp = client.post(full_url, headers=headers, json=body or None, timeout=10.0)
    elif method == "GET":
        resp = client.get(full_url, headers=headers, timeout=10.0)
    elif method == "DELETE":
        #resp = client.delete(full_url, headers=headers, json=body or None, timeout=10.0)
        resp = client.request("DELETE", full_url, headers=headers, json=body or None, timeout=10.0)
    else:
        return {
            "status_code": None,
            "reason_phrase": f"Unsupported method: {method}",
            "response_time": None,
            "response_headers": None,
            "response_body": None,
            "error": f"Unsupported HTTP method: {method}",
        }

    return {
        "status_code": resp.status_code,
        "reason_phrase": resp.reason_phrase,
        "response_time": resp.elapsed.total_seconds(),
        "response_headers": dict(resp.headers),
        "response_body": resp.text if resp.text else None,
        "error": None,
    }


def run_nrf_tests(test_cases_file, resume_file=None, auto_restart=True, max_restarts=10):
    """
    Run NRF tests using HTTPX with HTTP/2 prior knowledge.
    Supports JSON test cases that include driving_state + request, such as:
    - testing_cases/NFStatusSubscibe_tests.json
    - testing_cases/NFDeregister_tests.json
    - testing_cases/NFRegister_tests.json
    - testing_cases/NFStatusNotify_tests.json
    """
    # Load test cases from the JSON file
    try:
        with open(test_cases_file, 'r') as f:
            content = f.read()
            test_cases = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"File not found: {test_cases_file}")
        sys.exit(1)

    if not isinstance(test_cases, list):
        print("Error: Test cases file must contain a JSON array")
        sys.exit(1)

    # Base URL and default headers.
    base_url = "http://localhost:7777/nnrf-nfm/v1"
    base_headers = {"Content-Type": "application/json"}

    # Determine results file name based on input file name.
    test_path = Path(test_cases_file)
    stem = test_path.stem  # e.g. 'NFStatusSubscibe_tests'
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

    # Results container and starting index
    results = []
    start_index = 0
    restart_count = 0

    # If resume file is provided, load previous results and determine starting index
    if resume_file and os.path.exists(resume_file):
        try:
            with open(resume_file, 'r') as f:
                resume_data = json.loads(f.read())
                if isinstance(resume_data, dict) and "results" in resume_data:
                    # New format with metadata
                    results = resume_data["results"]
                    if "crash_info" in resume_data:
                        print(f"\nPrevious crash detected at test case index: {resume_data['crash_info']['crash_index']}")
                        print("Crashed payload:")
                        print(json.dumps(resume_data["crash_info"]["crashed_payload"], indent=2))
                else:
                    # Old format (just an array of results)
                    results = resume_data

                if results:
                    # Find the highest test case index that was completed
                    start_index = max(r.get("test_case_index", -1) for r in results) + 1
                    print(f"Resuming from test case {start_index+1}")
        except Exception as e:
            print(f"Error loading resume file: {e}")
            print("Starting from the beginning")

    # Save progress function
    def save_progress(crashed_payload=None):
        # Add crash information if available
        progress_data = {
            "results": results,
            "last_completed_index": results[-1]["test_case_index"] if results else -1,
            "timestamp": datetime.now().isoformat(),
            "total_test_cases": len(test_cases),
            "completed_test_cases": len(results)
        }

        if crashed_payload is not None:
            progress_data["crash_info"] = {
                "crashed_payload": crashed_payload,
                "crash_index": results[-1]["test_case_index"] if results else -1
            }

        with open(results_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
        print(f"\nProgress saved to {results_file}")

    # Process test cases
    try:
        i = start_index
        while i < len(test_cases):
            # Create new client for each test case to handle potential crashes
            with httpx.Client(http1=False, http2=True) as client:
                test_case = test_cases[i]
                print(f"\nProcessing test case {i+1}/{len(test_cases)}")

                name = test_case.get("name", f"Test case {i+1}")
                violated_constraints = test_case.get("violated_constraints", [])
                constraint_text = violated_constraints[0] if violated_constraints else ""

                driving_state = test_case.get("driving_state")
                request_def = test_case.get("request", {})

                try:
                    # 1) Execute driving_state (if any) to obtain subscriptionId, etc.
                    driving_state_data = None
                    if driving_state:
                        driving_state_data = execute_driving_state(
                            client, driving_state, base_url, base_headers
                        )

                    # 2) Execute the actual request.
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
                        resp_info = execute_test_request(
                            client,
                            request_def,
                            base_url,
                            base_headers,
                            driving_state_data=driving_state_data,
                        )

                    # 3) Record results.
                    result = {
                        "test_case_index": i,
                        "name": name,
                        "constraint": constraint_text,
                        "status_code": resp_info.get("status_code"),
                        "reason_phrase": resp_info.get("reason_phrase"),
                        "response_time": resp_info.get("response_time"),
                        "response_headers": resp_info.get("response_headers"),
                        "response_body": resp_info.get("response_body"),
                        "error": resp_info.get("error"),
                    }
                    results.append(result)

                    if result["status_code"] is not None:
                        print(f"  Status: {result['status_code']} {result['reason_phrase']}")
                    else:
                        print(f"  Error: {result['error']}")

                except httpx.RequestError as e:
                    # Handle request exceptions
                    result = {
                        "test_case_index": i,
                        "status_code": None,
                        "reason_phrase": str(e),
                        "response_time": None,
                        "response_headers": None,
                        "response_body": None,
                        "error": str(e),
                        "error_type": e.__class__.__name__,
                    }
                    results.append(result)
                    print(f"  HTTPX Error: {e}")

                    # Detect crash when "Server disconnected" appears
                    if "Server disconnected" in str(e) and auto_restart:
                        print("\n*** NRF SERVICE CRASH DETECTED ***")
                        print("Crashed test case payload:")
                        print(json.dumps(test_case, indent=2))
                        save_progress(test_case)

                        # Automatically restart NRF
                        restart_count += 1
                        if restart_count <= max_restarts:
                            print(f"\nAutomatically restarting NRF (restart #{restart_count})...")
                            restart_nrf_container()
                        else:
                            print("Maximum restart attempts reached, stopping further restarts.")

                # Save progress periodically (every 20 test cases)
                if (i + 1) % 20 == 0:
                    save_progress()

                # Small delay between requests to avoid overwhelming the server
                time.sleep(0.1)

                # Always move to the next test case, even after a crash
                i += 1

    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    finally:
        # Always save results before exiting
        save_progress()

    # Print summary
    success_count = sum(1 for r in results if r.get("status_code") in [200, 201, 204])
    print(f"\nTest complete. Results saved to {results_file}")
    print(f"Summary: {success_count}/{len(results)} tests successful")
    print(f"NRF container was automatically restarted {restart_count} times")

    return results_file


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="NRF Testing Tool with automatic recovery (Open5GS, driving_state-aware)"
    )
    parser.add_argument(
        "test_cases_file",
        help=(
            "JSON file containing test cases "
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
