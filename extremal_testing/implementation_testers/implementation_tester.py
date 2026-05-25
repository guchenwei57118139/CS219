#!/usr/bin/env python3
"""Run each generated NRF operation suite across all implementations."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extremal_testing.implementation_testers.base import BaseNRFTester
from extremal_testing.implementation_testers.common import (
    load_clean_suite,
    operation_name_from_suite_path,
    validate_clean_suite,
)
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
        suite_files = [
            path
            for path in sorted(TESTCASES_DIR.glob("*.json"))
            if path.name != "dummy_tests.json" and self._is_clean_suite_file(path)
        ]
        by_operation: Dict[str, Path] = {}
        for path in suite_files:
            operation = operation_name_from_suite_path(path)
            current = by_operation.get(operation)
            if current is None or current.stem.endswith("_tests"):
                by_operation[operation] = path
        return [by_operation[operation] for operation in sorted(by_operation)]

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
        operation_name = operation_name_from_suite_path(test_cases_file)
        suite = load_clean_suite(str(test_cases_file), operation_name)
        validate_clean_suite(suite)
        suite.setdefault("setup", [])
        suite.setdefault("cleanup", [])
        suite.setdefault("operation", operation_name)
        return suite

    def run_test_case_for_impl(
        self,
        tester: BaseNRFTester,
        client_factory: Any,
        operation_name: str,
        test_case: Dict[str, Any],
    ) -> Dict[str, Any]:
        execution = tester.execute_test_case_with_recovery(client_factory, operation_name, test_case)
        response = execution["response"]
        setup_summary = execution["setup"]

        return {
            "status_code": response.get("status_code"),
            "response_body": response.get("response_body"),
            "error": tester.result_error(setup_summary, response),
        }

    def unavailable_result(self, error: str) -> Dict[str, Any]:
        return {
            "status_code": None,
            "response_body": None,
            "error": error,
        }

    def run_suite(self, test_cases_file: Path) -> Dict[str, Any]:
        suite = self.load_suite(test_cases_file)
        operation = str(suite.get("operation") or operation_name_from_suite_path(test_cases_file))
        tests = suite.get("tests", [])
        print(f"[*] Running {operation} from {test_cases_file} ({len(tests)} test case(s))", flush=True)

        result_tests: List[Dict[str, Any]] = [
            {
                "test_case_index": index,
                "test_name": test_case.get("name", f"Test case {index + 1}"),
                "implementations": {},
            }
            for index, test_case in enumerate(tests)
        ]

        for implementation_name in IMPLEMENTATION_ORDER:
            tester = self.testers[implementation_name]
            print(f"  -> {operation}: starting {implementation_name}", flush=True)
            with tester.create_client() as client:
                readiness_error = tester.probe_service(client)
                if (
                    readiness_error
                    and tester.is_transport_failure(None, readiness_error)
                    and tester.recover_from_transport_failure()
                ):
                    readiness_error = None
                if readiness_error:
                    print(f"  -> {operation}: {implementation_name} unavailable; recording errors", flush=True)
                    for index in range(len(tests)):
                        result_tests[index]["implementations"][implementation_name] = self.unavailable_result(readiness_error)
                    continue
                for index, test_case in enumerate(tests):
                    test_name = test_case.get("name", f"Test case {index + 1}")
                    print(
                        f"    [{index + 1}/{len(tests)}] {implementation_name}: {test_name}",
                        flush=True,
                    )
                    implementation_result = self.run_test_case_for_impl(
                        tester,
                        tester.create_client,
                        operation,
                        test_case,
                    )
                    result_tests[index]["implementations"][implementation_name] = implementation_result

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
        print(f"[*] Implementation Testing: {len(suite_files)} suite(s)", flush=True)
        for suite_index, suite_file in enumerate(suite_files, 1):
            print(f"[*] Suite {suite_index}/{len(suite_files)}: {suite_file}", flush=True)
            suite_result = self.run_suite(suite_file)
            result_path = self.write_suite_result(suite_result)
            print(f"[*] Saved comparison result to {result_path}", flush=True)
            written_files.append(result_path)
        return written_files


def _resolve_input_paths(args: Sequence[str]) -> List[Path]:
    if not args:
        return ImplementationTester().discover_suite_files()

    resolved: List[Path] = []
    for raw_arg in args:
        path = Path(raw_arg)
        if path.is_dir():
            resolved.extend(sorted(path.glob("*.json")))
        elif path.exists():
            resolved.append(path)
        elif path.suffix:
            raise SystemExit(f"Test suite not found: {path}")
        else:
            suite_path = TESTCASES_DIR / f"{raw_arg}.json"
            legacy_suite_path = TESTCASES_DIR / f"{raw_arg}_tests.json"
            if suite_path.exists():
                resolved.append(suite_path)
            elif legacy_suite_path.exists():
                resolved.append(legacy_suite_path)
            else:
                raise SystemExit(f"Test suite not found for operation: {raw_arg}")

    seen: set[Path] = set()
    by_operation: Dict[str, Path] = {}
    for path in resolved:
        if path.name == "dummy_tests.json":
            continue
        if path in seen:
            continue
        seen.add(path)
        operation = operation_name_from_suite_path(path)
        current = by_operation.get(operation)
        if current is None or current.stem.endswith("_tests"):
            by_operation[operation] = path
    return [by_operation[operation] for operation in sorted(by_operation)]


def main() -> None:
    suite_files = _resolve_input_paths(sys.argv[1:])
    if not suite_files:
        print("No clean-format test suites found.")
        return
    tester = ImplementationTester()
    tester.run(suite_files)


if __name__ == "__main__":
    main()
