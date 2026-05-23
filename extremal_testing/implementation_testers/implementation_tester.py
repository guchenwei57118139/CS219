#!/usr/bin/env python3
"""Run each generated NRF operation suite across all implementations."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

from extremal_testing.implementation_testers.base import BaseNRFTester
from extremal_testing.implementation_testers.common import load_clean_suite, validate_clean_suite
from extremal_testing.implementation_testers.test_free5gc import Free5GCNRFTester
from extremal_testing.implementation_testers.test_oai import OAINRFTester
from extremal_testing.implementation_testers.test_open5gs import Open5GSNRFTester

ROOT_DIR = Path(__file__).resolve().parent.parent
TESTCASES_DIR = ROOT_DIR / "json" / "testcases"
TEST_RESULTS_DIR = ROOT_DIR / "json" / "test_results"

IMPLEMENTATION_ORDER = ["free5gc", "oai", "open5gs"]
TESTER_CLASSES = {
    "free5gc": Free5GCNRFTester,
    "oai": OAINRFTester,
    "open5gs": Open5GSNRFTester,
}


class ImplementationTester:
    """Execute each test case for each implementation and write one JSON result per operation."""

    def __init__(self) -> None:
        self.testers: Dict[str, BaseNRFTester] = {
            name: tester_class()
            for name, tester_class in TESTER_CLASSES.items()
        }

    def discover_suite_files(self) -> List[Path]:
        suite_files = sorted(TESTCASES_DIR.glob("*_tests.json"))
        return [
            path
            for path in suite_files
            if path.name != "dummy_tests.json" and self._is_clean_suite_file(path)
        ]

    def _is_clean_suite_file(self, suite_file: Path) -> bool:
        try:
            with open(suite_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return False

        if not isinstance(payload, dict):
            return False

        tests = payload.get("tests", [])
        if not isinstance(tests, list) or not tests:
            return False

        required_keys = {"name", "constraint", "method", "path", "headers"}
        for test_case in tests:
            if not isinstance(test_case, dict):
                return False
            if "request" in test_case or "violated_constraints" in test_case:
                return False
            if not required_keys.issubset(test_case.keys()):
                return False
        return True

    def load_suite(self, test_cases_file: Path) -> Dict[str, Any]:
        suite = load_clean_suite(str(test_cases_file), test_cases_file.stem.replace("_tests", ""))
        validate_clean_suite(suite)
        suite.setdefault("setup", [])
        suite.setdefault("cleanup", [])
        suite.setdefault("operation", test_cases_file.stem.replace("_tests", ""))
        return suite

    def run_test_case_for_impl(
        self,
        tester: BaseNRFTester,
        shared_setup: List[Dict[str, Any]],
        shared_cleanup: List[Dict[str, Any]],
        test_case: Dict[str, Any],
    ) -> Dict[str, Any]:
        with tester.create_client() as client:
            context: Dict[str, Any] = {}
            headers = tester.build_default_headers()
            headers.update(tester.build_auth_headers(context))

            setup_summary = tester.execute_steps(client, list(shared_setup), headers, context)

            response = tester.execute_step(client, test_case, headers, context)

            cleanup_context = dict(context)
            tester.execute_steps(client, list(shared_cleanup), headers, cleanup_context)

        return {
            "status_code": response.get("status_code"),
            "response_body": response.get("response_body"),
            "error": response.get("error") or setup_summary.get("error"),
        }

    def run_suite(self, test_cases_file: Path) -> Dict[str, Any]:
        suite = self.load_suite(test_cases_file)
        operation = str(suite.get("operation") or test_cases_file.stem.replace("_tests", ""))
        shared_setup = suite.get("setup", [])
        shared_cleanup = suite.get("cleanup", [])
        tests = suite.get("tests", [])

        result_tests: List[Dict[str, Any]] = []
        for index, test_case in enumerate(tests):
            implementation_results: Dict[str, Any] = {}
            for implementation_name in IMPLEMENTATION_ORDER:
                implementation_results[implementation_name] = self.run_test_case_for_impl(
                    self.testers[implementation_name],
                    shared_setup,
                    shared_cleanup,
                    test_case,
                )

            result_tests.append(
                {
                    "test_case_index": index,
                    "test_name": test_case.get("name", f"Test case {index + 1}"),
                    "implementations": implementation_results,
                }
            )

        return {
            "operation": operation,
            "source_tests_file": str(test_cases_file),
            "implementation_order": IMPLEMENTATION_ORDER,
            "tests": result_tests,
        }

    def build_results_path(self, operation: str) -> Path:
        TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        return TEST_RESULTS_DIR / f"{operation}.json"

    def write_suite_result(self, result: Dict[str, Any]) -> Path:
        operation = str(result["operation"])
        results_path = self.build_results_path(operation)
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return results_path

    def run(self, suite_files: Sequence[Path]) -> List[Path]:
        written_files: List[Path] = []
        for suite_file in suite_files:
            suite_result = self.run_suite(suite_file)
            written_files.append(self.write_suite_result(suite_result))
        return written_files


def _resolve_input_paths(args: Sequence[str]) -> List[Path]:
    if not args:
        return ImplementationTester().discover_suite_files()

    resolved: List[Path] = []
    for raw_arg in args:
        path = Path(raw_arg)
        if path.is_dir():
            resolved.extend(sorted(path.glob("*_tests.json")))
        else:
            resolved.append(path)

    seen: set[Path] = set()
    unique_paths: List[Path] = []
    for path in resolved:
        if path.name == "dummy_tests.json":
            continue
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)
    return unique_paths


def main() -> None:
    suite_files = _resolve_input_paths(sys.argv[1:])
    if not suite_files:
        print("No clean-format test suites found.")
        return
    tester = ImplementationTester()
    written_files = tester.run(suite_files)
    for path in written_files:
        print(f"Comparison result saved to {path}")


if __name__ == "__main__":
    main()
