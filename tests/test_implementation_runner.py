import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

from extremal_testing.implementation_testers.base import BaseNRFTester
from extremal_testing.implementation_testers.implementation_tester import (
    IMPLEMENTATION_ORDER,
    ImplementationTester,
)


class FakeElapsed:
    def total_seconds(self) -> float:
        return 0.01


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "", headers: Optional[Dict[str, str]] = None, reason: str = "OK"):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.reason = reason
        self.elapsed = FakeElapsed()


class FakeClient:
    def __init__(self, responses: Optional[List[Any]] = None):
        self.responses = list(responses or [])
        self.calls: List[Dict[str, Any]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            return FakeResponse()
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeTester(BaseNRFTester):
    implementation_name = "fake"
    default_base_url = "http://example.test/nnrf-nfm/v1"

    def __init__(self, client: Optional[FakeClient] = None, readiness_error: Optional[str] = None):
        super().__init__()
        self.client = client or FakeClient()
        self.readiness_error = readiness_error
        self.create_client_count = 0
        self.probe_count = 0

    def create_client(self):
        self.create_client_count += 1
        return self.client

    def probe_service(self, client: Any) -> Optional[str]:
        self.probe_count += 1
        return self.readiness_error


class ImplementationRunnerTests(unittest.TestCase):
    def test_setup_failure_skips_test_and_still_runs_cleanup(self) -> None:
        client = FakeClient(
            [
                FakeResponse(500, "setup failed", reason="Internal Server Error"),
                FakeResponse(204, "", reason="No Content"),
            ]
        )
        tester = FakeTester(client)

        result = tester.execute_test_case(
            client,
            [{"method": "PUT", "path": "/nf-instances/setup", "headers": {}}],
            [{"method": "DELETE", "path": "/nf-instances/setup", "headers": {}}],
            {"name": "main", "constraint": "c", "method": "POST", "path": "/subscriptions", "headers": {}},
        )

        self.assertEqual([call["method"] for call in client.calls], ["PUT", "DELETE"])
        self.assertIsNone(result["response"]["status_code"])
        self.assertIn("Setup failed; test request skipped", result["response"]["error"])
        self.assertEqual(result["cleanup"]["status_code"], 204)

    def test_aggregate_runner_reuses_client_but_resets_context_per_test(self) -> None:
        runner = ImplementationTester.__new__(ImplementationTester)
        clients = {
            name: FakeClient([FakeResponse(), FakeResponse(), FakeResponse()])
            for name in IMPLEMENTATION_ORDER
        }
        runner.testers = {name: FakeTester(client) for name, client in clients.items()}

        with tempfile.TemporaryDirectory() as temp_dir:
            suite_file = Path(temp_dir) / "NFExample_tests.json"
            suite_file.write_text(
                json.dumps(
                    {
                        "operation": "NFExample",
                        "setup": [],
                        "cleanup": [],
                        "tests": [
                            {
                                "name": "seeds context",
                                "constraint": "c1",
                                "method": "GET",
                                "path": "/nf-instances/first",
                                "headers": {},
                            },
                            {
                                "name": "fresh context",
                                "constraint": "c2",
                                "method": "GET",
                                "path": "/nf-instances/{nfInstanceId}",
                                "headers": {},
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = runner.run_suite(suite_file)

        self.assertEqual(len(result["tests"]), 2)
        for implementation_name in IMPLEMENTATION_ORDER:
            self.assertEqual(runner.testers[implementation_name].create_client_count, 1)
            urls = [call["url"] for call in clients[implementation_name].calls]
            self.assertTrue(urls[0].endswith("/nf-instances/first"))
            self.assertTrue(urls[1].endswith("/nf-instances/{nfInstanceId}"))

    def test_unavailable_implementation_uses_existing_result_keys(self) -> None:
        runner = ImplementationTester.__new__(ImplementationTester)
        runner.testers = {
            name: FakeTester(readiness_error=f"{name} unavailable")
            for name in IMPLEMENTATION_ORDER
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            suite_file = Path(temp_dir) / "NFExample_tests.json"
            suite_file.write_text(
                json.dumps(
                    {
                        "operation": "NFExample",
                        "setup": [],
                        "cleanup": [],
                        "tests": [
                            {
                                "name": "test",
                                "constraint": "c",
                                "method": "GET",
                                "path": "/nf-instances/example",
                                "headers": {},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = runner.run_suite(suite_file)

        implementations = result["tests"][0]["implementations"]
        for implementation_name, implementation_result in implementations.items():
            self.assertEqual(set(implementation_result.keys()), {"status_code", "response_body", "error"})
            self.assertIsNone(implementation_result["status_code"])
            self.assertIsNone(implementation_result["response_body"])
            self.assertEqual(implementation_result["error"], f"{implementation_name} unavailable")


if __name__ == "__main__":
    unittest.main()
