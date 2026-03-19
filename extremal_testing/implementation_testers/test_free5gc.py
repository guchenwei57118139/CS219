#!/usr/bin/env python3
import json
import sys
import time
import uuid
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

def build_full_url(resource_url: str, base_url: str) -> str:
    """Build a full URL from a resource URL and base URL."""
    if resource_url.startswith('/nnrf-nfm/v1'):
        parsed_base = urlparse(base_url)
        return f"{parsed_base.scheme}://{parsed_base.netloc}{resource_url}"
    elif resource_url.startswith('/'):
        return base_url.rstrip('/') + resource_url
    else:
        return base_url.rstrip('/') + '/' + resource_url


def replace_nf_instance_id_in_url(resource_url: str, new_instance_id: str) -> str:
    """Replace the NF instance ID in a resource URL with a new one."""
    if '/nf-instances/' not in resource_url:
        return resource_url
    
    parts = resource_url.split('/nf-instances/')
    if len(parts) == 2:
        suffix = parts[1].split('/', 1)[1] if '/' in parts[1] else ''
        if suffix:
            return f"{parts[0]}/nf-instances/{new_instance_id}/{suffix}"
        else:
            return f"{parts[0]}/nf-instances/{new_instance_id}"
    return resource_url


def check_nrf_health(base_url: str) -> bool:
    """Check if the NRF container is responding."""
    try:
        health_url = base_url.rstrip('/') + '/nf-instances'
        response = requests.get(health_url, timeout=10)
        return response.status_code is not None
    except requests.RequestException:
        try:
            root_url = base_url.rstrip('/')
            response = requests.get(root_url, timeout=5)
            return True
        except requests.RequestException:
            return False


def execute_driving_state(driving_state: Optional[Dict[str, Any]], base_url: str, headers: Dict[str, str]) -> Optional[str]:
    """Execute the driving state request and return subscription_data (if any)."""
    if not driving_state:
        return None
    
    resource_url = driving_state.get('resource_url', '')
    method = driving_state.get('method', 'GET').upper()
    request_body = driving_state.get('request_body', {})
    driving_headers = {**headers, **driving_state.get('headers', {})}
    
    is_nf_registration = method == 'PUT' and '/nf-instances/' in resource_url and request_body
    
    # Approach #1: keep the nfInstanceId from the test case (do not generate a fresh one)
    
    full_url = build_full_url(resource_url, base_url)
    subscription_data = None
    
    try:
        if method == 'PUT':
            response = requests.put(full_url, headers=driving_headers, json=request_body if request_body else None, timeout=10)
        elif method == 'POST':
            response = requests.post(full_url, headers=driving_headers, json=request_body if request_body else None, timeout=10)
        elif method == 'GET':
            response = requests.get(full_url, headers=driving_headers, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(full_url, headers=driving_headers, json=request_body if request_body else None, timeout=10)
        else:
            return None
        
        if response.status_code in [200, 201, 204]:
            location = response.headers.get('Location', '')
            if location and 'subscriptions' in location:
                subscription_id = location.split('subscriptions/')[-1].split('/')[0]
                subscription_data = subscription_id
            
            if not subscription_data:
                try:
                    body = response.json()
                    if 'subscriptionId' in body:
                        subscription_data = body['subscriptionId']
                except (json.JSONDecodeError, KeyError):
                    pass
        
        return subscription_data
    except requests.RequestException:
        return None


def execute_test_request(request: Dict[str, Any], base_url: str, headers: Dict[str, str], driving_state_data: Optional[str] = None) -> Dict[str, Any]:
    """Execute the actual test request and return the response details."""
    resource_url = request.get('resource_url', '')
    method = request.get('method', 'GET').upper()
    request_body = request.get('request_body', {})
    test_headers = {**headers, **request.get('headers', {})}
    
    if driving_state_data and '{subscriptionId}' in resource_url:
        resource_url = resource_url.replace('{subscriptionId}', driving_state_data)
    elif driving_state_data and 'subscriptions' in resource_url and '{subscriptionId}' not in resource_url:
        if resource_url.endswith('/subscriptions'):
            resource_url = f"{resource_url}/{driving_state_data}"
    
    full_url = build_full_url(resource_url, base_url)
    
    try:
        if method == 'PUT':
            response = requests.put(full_url, headers=test_headers, json=request_body if request_body else None, timeout=10)
        elif method == 'POST':
            response = requests.post(full_url, headers=test_headers, json=request_body if request_body else None, timeout=10)
        elif method == 'GET':
            response = requests.get(full_url, headers=test_headers, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(full_url, headers=test_headers, json=request_body if request_body else None, timeout=10)
        else:
            return {
                "status_code": None,
                "status_message": f"Unsupported method: {method}",
                "response_body": None,
                "error": f"Unsupported HTTP method: {method}"
            }
        
        return {
            "status_code": response.status_code,
            "status_message": response.reason,
            "response_body": response.text if response.text else None,
            "response_headers": dict(response.headers)
        }
    except requests.RequestException as e:
        return {
            "status_code": None,
            "status_message": str(e),
            "response_body": None,
            "error": str(e)
        }


def run_nrf_tests(test_cases_file: str, base_url: str = "http://localhost:7778/nnrf-nfm/v1") -> str:
    """Run test cases against the Free5GC NRF and return the results file path."""
    try:
        with open(test_cases_file, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"File not found: {test_cases_file}")
        sys.exit(1)
    
    if not isinstance(test_cases, list):
        print(f"Error: Test cases file must contain a JSON array")
        sys.exit(1)
    
    print(f"[*] Checking NRF health at {base_url}...")
    if not check_nrf_health(base_url):
        print(f"[!] Error: NRF container is not responding at {base_url}")
        print(f"[!] Please ensure Free5GC NRF is running and accessible")
        sys.exit(1)
    print(f"[✓] NRF is responding")
    
    headers = {"Content-Type": "application/json"}
    
    test_file_path = Path(test_cases_file)
    operation_name = test_file_path.stem.replace('_tests', '')
    
    results = []
    
    total_cases = len(test_cases)
    for i, test_case in enumerate(test_cases, 1):
        test_name = test_case.get('name', f'Test case {i}')
        violated_constraints = test_case.get('violated_constraints', [])
        constraint_text = violated_constraints[0] if violated_constraints else "Unknown constraint"
        
        print(f"\n[{i}/{total_cases}] {test_name}")
        print(f"  Constraint: {constraint_text[:80]}...")
        
        test_headers = {"Content-Type": "application/json"}
        
        driving_state = test_case.get('driving_state')
        driving_state_data = None
        
        if driving_state:
            driving_state_data = execute_driving_state(driving_state, base_url, test_headers)
        
        request = test_case.get('request', {})
        if not request:
            result = {
                "test_case_index": i - 1,
                "test_name": test_name,
                "operation": operation_name,
                "constraint": constraint_text,
                "status_code": None,
                "status_message": "No request found in test case",
                "response_body": None,
                "error": "Test case missing request field"
            }
            results.append(result)
            continue
        
        response = execute_test_request(request, base_url, test_headers, driving_state_data)
        
        status_code = response.get("status_code")
        status_message = response.get("status_message", "")
        if status_code:
            print(f"  Status: {status_code} {status_message}")
        else:
            error = response.get("error", "Unknown error")
            print(f"  Error: {error}")
        
        result = {
            "test_case_index": i - 1,
            "test_name": test_name,
            "operation": operation_name,
            "constraint": constraint_text,
            "status_code": status_code,
            "status_message": status_message,
            "response_body": response.get("response_body"),
            "error": response.get("error")
        }
        results.append(result)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_dir = Path(__file__).resolve().parent.parent
    results_dir = script_dir / "data" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_file = str(results_dir / f"nrf_test_results_free5gc_{operation_name}_{timestamp}.json")
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n[✓] Test complete. Results saved to {results_file}")
    
    return results_file


def main() -> None:
    """Main entry point for the test driver."""
    if len(sys.argv) < 2:
        print("Usage: python test_free5gc.py <test_cases_file> [base_url]")
        print("  test_cases_file: Path to JSON file containing test cases (e.g., data/generated/NFStatusSubscribe_tests.json)")
        print("  base_url: Optional base URL for NRF (default: http://localhost:7778/nnrf-nfm/v1)")
        sys.exit(1)
    
    test_cases_file = sys.argv[1]
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:7778/nnrf-nfm/v1"
    
    run_nrf_tests(test_cases_file, base_url)


if __name__ == "__main__":
    main()

