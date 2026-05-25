"""Shared base tester for NRF implementation runners."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from extremal_testing.implementation_testers.common import (
    build_prerequisite_steps,
    build_request_details,
    load_clean_suite,
    operation_name_from_suite_path,
    response_headers_dict,
    response_reason,
    response_text,
    seed_context_from_step,
    validate_clean_suite,
    update_context_from_response,
)


class BaseNRFTester(ABC):
    """Template-method base class for all NRF implementation testers."""

    implementation_name: str = "base"
    default_base_url: str = ""
    results_prefix: str = "nrf_test_results_"
    request_timeout: Any = 10
    server_crash_error = "This operation crashed the server."

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

    def probe_service(self, client: Any) -> Optional[str]:
        """Return an error string when the target service is unreachable."""
        try:
            client.request("GET", self.base_url, timeout=self.request_timeout)
        except Exception as exc:
            return f"Readiness probe failed for {self.base_url}: {exc.__class__.__name__}: {exc}"
        return None

    def wait_for_service(
        self,
        max_wait_seconds: float = 60,
        initial_delay_seconds: float = 1,
        max_delay_seconds: float = 8,
    ) -> bool:
        deadline = time.monotonic() + max_wait_seconds
        delay = initial_delay_seconds

        while time.monotonic() <= deadline:
            with self.create_client() as client:
                if self.probe_service(client) is None:
                    return True

            if time.monotonic() + delay > deadline:
                time.sleep(max(0, deadline - time.monotonic()))
            else:
                time.sleep(delay)
            delay = min(delay * 2, max_delay_seconds)

        with self.create_client() as client:
            return self.probe_service(client) is None

    def build_results_file(self, operation_name: str) -> Path:
        results_dir = Path(__file__).resolve().parent.parent / "data" / "test_results"
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return results_dir / f"{self.results_prefix}{operation_name}_{timestamp}.json"

    @staticmethod
    def is_transport_failure(error_type: Optional[str], message: Optional[str]) -> bool:
        normalized_type = error_type or ""
        normalized_message = (message or "").lower()
        transport_error_types = {
            "BrokenPipeError",
            "ConnectionResetError",
            "RemoteProtocolError",
            "TransportError",
            "ReadError",
            "WriteError",
            "ProtocolError",
            "ServerDisconnectedError",
            "RemoteProtocolError",
        }
        transport_message_fragments = (
            "server disconnected",
            "connection reset by peer",
            "broken pipe",
            "connection refused",
            "connection aborted",
            "connection closed",
            "cannot connect",
            "connect error",
            "network is unreachable",
            "peer closed",
            "read of closed file",
            "remote protocol error",
            "cannot parse http message",
        )
        return normalized_type in transport_error_types or any(fragment in normalized_message for fragment in transport_message_fragments)

    def result_has_transport_failure(self, result: Dict[str, Any]) -> bool:
        if self.is_transport_failure(result.get("error_type"), result.get("error") or result.get("status_message")):
            return True
        for step_result in result.get("step_results", []) or []:
            if self.result_has_transport_failure(step_result):
                return True
        return False

    def execution_has_transport_failure(self, execution: Dict[str, Dict[str, Any]]) -> bool:
        return self.result_has_transport_failure(execution["setup"]) or self.result_has_transport_failure(execution["response"])

    def recover_from_transport_failure(self) -> bool:
        return False

    def after_recovery_attempt(
        self,
        original_execution: Dict[str, Dict[str, Any]],
        recovered_execution: Dict[str, Dict[str, Any]],
    ) -> None:
        pass

    def _request_once(
        self,
        client: Any,
        method: str,
        full_url: str,
        request_headers: Dict[str, str],
        request_body: Any,
    ) -> Dict[str, Any]:
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
                "error_location": f"{method} {full_url}",
            }

    def load_suite(self, test_cases_file: str) -> Dict[str, Any]:
        operation_name = operation_name_from_suite_path(Path(test_cases_file))
        suite = load_clean_suite(test_cases_file, operation_name)
        validate_clean_suite(suite)
        return suite

    def execute_step(
        self,
        client: Any,
        step: Dict[str, Any],
        headers: Dict[str, str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        seed_context_from_step(step, context)
        request_details = build_request_details(step, self.base_url, headers, context)
        payload = self._request_once(
            client,
            request_details["method"],
            request_details["full_url"],
            request_details["headers"],
            request_details["body"],
        )
        if payload.get("error"):
            payload["error_location"] = f"{request_details['method']} {request_details['path']}"
        else:
            update_context_from_response(context, payload["response_headers"], payload["response_body"])
        return payload

    def execute_steps(
        self,
        client_factory: Any,
        steps: List[Dict[str, Any]],
        headers: Dict[str, str],
        context: Dict[str, Any],
        stop_on_failure: bool = True,
    ) -> Dict[str, Any]:
        step_results: List[Dict[str, Any]] = []
        for step in steps:
            with client_factory() as client:
                result = self.execute_step(client, step, headers, context)
            step_results.append(result)
            if stop_on_failure and self.step_failed(result):
                break
        return self.summarize_step_results(step_results)

    def step_failed(self, result: Dict[str, Any]) -> bool:
        status_code = result.get("status_code")
        return status_code is None or (isinstance(status_code, int) and status_code >= 400)

    def summarize_step_results(self, step_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        error = next((item.get("error") for item in step_results if item.get("error")), None)
        if error is None:
            failed_result = next((item for item in step_results if self.step_failed(item)), None)
            if failed_result is not None:
                error = f"Step failed with status {failed_result.get('status_code')}: {failed_result.get('status_message') or ''}".rstrip()
        return {
            "step_results": step_results,
            "status_code": step_results[-1].get("status_code") if step_results else None,
            "status_message": step_results[-1].get("status_message") if step_results else None,
            "error": error,
        }

    def skipped_response(self, reason: str) -> Dict[str, Any]:
        return {
            "status_code": None,
            "status_message": reason,
            "response_body": None,
            "response_headers": {},
            "response_time": None,
            "error": reason,
        }

    def unavailable_response(self, error: str) -> Dict[str, Any]:
        return self.skipped_response(error)

    def server_crash_response(self) -> Dict[str, Any]:
        return self.skipped_response(self.server_crash_error)

    def result_error(
        self,
        setup_summary: Dict[str, Any],
        response: Dict[str, Any],
    ) -> Optional[str]:
        return response.get("error") or setup_summary.get("error")

    def execute_test_case(
        self,
        client_factory: Any,
        operation_name: str,
        test_case: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        prerequisites = test_case.get("prerequisites", {})
        setup_steps, setup_context = build_prerequisite_steps(operation_name, test_case, prerequisites)
        context: Dict[str, Any] = dict(setup_context)
        headers = self.build_default_headers()
        headers.update(self.build_auth_headers(context))

        setup_summary = self.execute_steps(client_factory, setup_steps, headers, context)
        if setup_summary.get("error"):
            response = self.skipped_response(f"Setup failed; test request skipped: {setup_summary['error']}")
        else:
            with client_factory() as client:
                response = self.execute_step(client, test_case, headers, context)

        return {
            "setup": setup_summary,
            "response": response,
        }

    def execute_test_case_with_recovery(
        self,
        client_factory: Any,
        operation_name: str,
        test_case: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        execution = self.execute_test_case(client_factory, operation_name, test_case)
        if not self.execution_has_transport_failure(execution):
            return execution
        if not self.recover_from_transport_failure():
            return execution
        recovered_execution = self.execute_test_case(client_factory, operation_name, test_case)
        self.after_recovery_attempt(execution, recovered_execution)
        return {
            "setup": execution["setup"],
            "response": self.server_crash_response(),
        }

    def build_result(
        self,
        index: int,
        test_case: Dict[str, Any],
        setup_summary: Dict[str, Any],
        response: Dict[str, Any],
    ) -> Dict[str, Any]:
        constraint_text = str(test_case.get("constraint") or "Unknown constraint")
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
            "error": self.result_error(setup_summary, response),
        }

    def run_nrf_tests(self, test_cases_file: str) -> str:
        suite = self.load_suite(test_cases_file)
        tests = suite.get("tests", [])
        if not isinstance(tests, list):
            raise ValueError("Test suite must contain a tests array")

        operation_name = str(suite.get("operation") or operation_name_from_suite_path(Path(test_cases_file)))
        results_file = self.build_results_file(operation_name)
        results: List[Dict[str, Any]] = []

        with self.create_client() as client:
            readiness_error = self.probe_service(client)
        if readiness_error and self.is_transport_failure(None, readiness_error) and self.recover_from_transport_failure():
            readiness_error = None

        for index, test_case in enumerate(tests):
            if readiness_error:
                setup_summary = self.summarize_step_results([])
                response = self.unavailable_response(readiness_error)
            else:
                execution = self.execute_test_case_with_recovery(self.create_client, operation_name, test_case)
                setup_summary = execution["setup"]
                response = execution["response"]

            result = self.build_result(index, test_case, setup_summary, response)
            result["operation"] = operation_name
            results.append(result)

        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        return str(results_file)
