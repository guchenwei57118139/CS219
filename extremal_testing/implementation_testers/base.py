"""Shared base tester for NRF implementation runners."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from extremal_testing.implementation_testers.common import (
    build_request_details,
    load_suite_or_legacy_tests,
    response_headers_dict,
    response_reason,
    response_text,
    seed_context_from_step,
    update_context_from_response,
)


class BaseNRFTester(ABC):
    """Template-method base class for all NRF implementation testers."""

    implementation_name: str = "base"
    default_base_url: str = ""
    results_prefix: str = "nrf_test_results_"
    request_timeout: Any = 10

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or self.default_base_url

    @abstractmethod
    def create_client(self):
        """Return a context manager yielding an HTTP client."""

    def build_default_headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}

    def build_auth_headers(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Hook for optional auth header injection. Default is no auth."""
        return {}

    def build_results_file(self, operation_name: str) -> Path:
        results_dir = Path(__file__).resolve().parent.parent / "data" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return results_dir / f"{self.results_prefix}{operation_name}_{timestamp}.json"

    def load_suite(self, test_cases_file: str) -> Dict[str, Any]:
        operation_name = Path(test_cases_file).stem.replace("_tests", "")
        return load_suite_or_legacy_tests(test_cases_file, operation_name)

    def execute_step(
        self,
        client: Any,
        step: Dict[str, Any],
        headers: Dict[str, str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        seed_context_from_step(step, context)
        request_details = build_request_details(step, self.base_url, headers, context)
        method = request_details["method"]
        full_url = request_details["full_url"]
        request_body = request_details["request_body"]
        request_headers = request_details["headers"]

        try:
            response = client.request(
                method,
                full_url,
                headers=request_headers,
                json=request_body if request_body is not None else None,
                timeout=self.request_timeout,
            )
            payload = {
                "status_code": response.status_code,
                "status_message": response_reason(response),
                "response_body": response_text(response),
                "response_headers": response_headers_dict(response),
                "response_time": response.elapsed.total_seconds() if hasattr(response, "elapsed") else None,
            }
            update_context_from_response(context, payload["response_headers"], payload["response_body"])
            return payload
        except Exception as exc:
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
        self,
        client: Any,
        steps: List[Dict[str, Any]],
        headers: Dict[str, str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        step_results: List[Dict[str, Any]] = []
        for step in steps:
            result = self.execute_step(client, step, headers, context)
            step_results.append(result)
            if result.get("status_code") is None:
                break
        return self.summarize_step_results(step_results)

    def summarize_step_results(self, step_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "step_results": step_results,
            "status_code": step_results[-1].get("status_code") if step_results else None,
            "status_message": step_results[-1].get("status_message") if step_results else None,
            "error": next((item.get("error") for item in step_results if item.get("error")), None),
        }

    def build_result(
        self,
        index: int,
        test_case: Dict[str, Any],
        setup_summary: Dict[str, Any],
        response: Dict[str, Any],
        cleanup_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        violated_constraints = test_case.get("violated_constraints", [])
        constraint_text = violated_constraints[0] if violated_constraints else "Unknown constraint"
        return {
            "test_case_index": index,
            "test_name": test_case.get("name", f"Test case {index + 1}"),
            "operation": test_case.get("operation", ""),
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
            "error": response.get("error") or setup_summary.get("error"),
        }

    def run_nrf_tests(self, test_cases_file: str) -> str:
        suite = self.load_suite(test_cases_file)
        tests = suite.get("tests", [])
        if not isinstance(tests, list):
            raise ValueError("Test suite must contain a tests array")

        shared_setup = suite.get("setup", [])
        shared_cleanup = suite.get("cleanup", [])
        operation_name = str(suite.get("operation") or Path(test_cases_file).stem.replace("_tests", ""))
        results_file = self.build_results_file(operation_name)
        results: List[Dict[str, Any]] = []

        for index, test_case in enumerate(tests):
            with self.create_client() as client:
                context: Dict[str, Any] = {}
                headers = self.build_default_headers()
                headers.update(self.build_auth_headers(context))

                setup_steps = list(shared_setup)
                legacy_setup = test_case.get("driving_state")
                if legacy_setup:
                    setup_steps.append(legacy_setup)
                setup_summary = self.execute_steps(client, setup_steps, headers, context)

                request_def = test_case.get("request", {})
                if request_def:
                    response = self.execute_step(client, request_def, headers, context)
                else:
                    response = {
                        "status_code": None,
                        "status_message": "No request found in test case",
                        "response_body": None,
                        "response_headers": {},
                        "response_time": None,
                        "error": "Test case missing request field",
                    }

                cleanup_context = dict(context)
                cleanup_summary = self.execute_steps(client, shared_cleanup, headers, cleanup_context)

            result = self.build_result(index, test_case, setup_summary, response, cleanup_summary)
            result["operation"] = operation_name
            results.append(result)

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        return str(results_file)

