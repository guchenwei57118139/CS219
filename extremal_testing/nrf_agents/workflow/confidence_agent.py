"""Confidence scoring agent for NRF implementation anomalies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from nrf_agents.prompts.confidence import (
    DEFAULT_PROTOCOL,
    SYSTEM_PROMPT_CONFIDENCE_TRIAGE,
    build_confidence_prompt,
)
from nrf_agents.workflow.sdk import run_text_agent

DEFAULT_BATCH_SIZE = 5

TEST_RESULTS_DIR = ROOT_DIR / "json" / "test_results"
TESTCASES_DIR = ROOT_DIR / "json" / "testcases"
CONFIDENCE_SCORES_DIR = ROOT_DIR / "json" / "confidence_scores"


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _parse_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
    cleaned = _strip_code_fences(text)
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        print(f"Warning: Failed to parse agent response as JSON: {exc}", flush=True)
        print(f"Response text: {cleaned[:500]}...", flush=True)
        return None
    return parsed if isinstance(parsed, list) else None


def _chunked(items: Sequence[Dict[str, Any]], chunk_size: int) -> List[List[Dict[str, Any]]]:
    return [list(items[idx : idx + chunk_size]) for idx in range(0, len(items), chunk_size)]


def _load_json_file(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _status_code_values(implementations: Dict[str, Any], implementation_order: Sequence[str]) -> List[int]:
    status_codes: List[int] = []
    for implementation_name in implementation_order:
        implementation_result = implementations.get(implementation_name, {})
        status_code = implementation_result.get("status_code")
        if isinstance(status_code, int):
            status_codes.append(status_code)
    return status_codes


def _has_status_code_difference(test_result: Dict[str, Any], implementation_order: Sequence[str]) -> bool:
    implementations = test_result.get("implementations", {})
    status_codes = _status_code_values(implementations, implementation_order)
    return len(status_codes) >= 2 and len(set(status_codes)) > 1


def _normalize_score_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    test_id = item.get("test_id")
    comment = item.get("comment")
    confidence = item.get("confidence")
    if not isinstance(test_id, int):
        return None
    if not isinstance(comment, str):
        comment = str(comment) if comment is not None else ""
    if isinstance(confidence, bool):
        confidence = int(confidence)
    elif not isinstance(confidence, int):
        try:
            confidence = int(confidence)
        except (TypeError, ValueError):
            return None
    confidence = max(0, min(10, confidence))
    return {"test_id": test_id, "comment": comment.strip(), "confidence": confidence}


class ConfidenceScoreAgent:
    """Generate confidence scores for status-code anomalies, grouped by operation."""

    def __init__(
        self,
        test_results_dir: Path = TEST_RESULTS_DIR,
        testcases_dir: Path = TESTCASES_DIR,
        output_dir: Path = CONFIDENCE_SCORES_DIR,
        batch_size: int = DEFAULT_BATCH_SIZE,
        protocol: str = DEFAULT_PROTOCOL,
    ) -> None:
        self.test_results_dir = test_results_dir
        self.testcases_dir = testcases_dir
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.protocol = protocol

    def discover_result_files(self) -> List[Path]:
        if not self.test_results_dir.exists():
            return []
        result_files: List[Path] = []
        for path in sorted(self.test_results_dir.glob("*.json")):
            if not path.is_file():
                continue
            try:
                payload = _load_json_file(path)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            if not isinstance(payload.get("tests"), list):
                continue
            if not isinstance(payload.get("implementation_order"), list):
                continue
            result_files.append(path)
        return result_files

    def load_test_suite(self, operation: str) -> Dict[str, Any]:
        suite_file = self.testcases_dir / f"{operation}_tests.json"
        if not suite_file.exists():
            raise FileNotFoundError(f"Matching test suite not found for {operation}: {suite_file}")
        suite = _load_json_file(suite_file)
        if not isinstance(suite, dict) or not isinstance(suite.get("tests"), list):
            raise ValueError(f"Suite file is not a suite object with a tests array: {suite_file}")
        return suite

    def load_test_results(self, result_file: Path) -> Dict[str, Any]:
        payload = _load_json_file(result_file)
        if not isinstance(payload, dict) or not isinstance(payload.get("tests"), list):
            raise ValueError(f"Result file is not a comparison result object: {result_file}")
        return payload

    def build_anomalies(self, operation: str, result_file: Path) -> List[Dict[str, Any]]:
        suite = self.load_test_suite(operation)
        result_payload = self.load_test_results(result_file)
        implementation_order = result_payload.get("implementation_order", [])
        if not isinstance(implementation_order, list) or not implementation_order:
            implementation_order = ["free5gc", "oai", "open5gs"]

        source_tests = suite.get("tests", [])
        anomalies: List[Dict[str, Any]] = []
        for test_result in result_payload.get("tests", []):
            if not isinstance(test_result, dict):
                continue
            if not _has_status_code_difference(test_result, implementation_order):
                continue

            test_id = test_result.get("test_case_index")
            if not isinstance(test_id, int) or test_id < 0 or test_id >= len(source_tests):
                continue

            original_test_case = source_tests[test_id]
            if not isinstance(original_test_case, dict):
                continue

            implementations = test_result.get("implementations", {})
            normalized_implementations: Dict[str, Dict[str, Any]] = {}
            for implementation_name in implementation_order:
                implementation_result = implementations.get(implementation_name, {})
                if not isinstance(implementation_result, dict):
                    implementation_result = {}
                normalized_implementations[implementation_name] = {
                    "status_code": implementation_result.get("status_code"),
                    "response_body": implementation_result.get("response_body"),
                    "error": implementation_result.get("error"),
                }

            anomalies.append(
                {
                    "test_id": test_id,
                    "test_name": test_result.get("test_name", f"Test case {test_id + 1}"),
                    "original_test_case": original_test_case,
                    "implementations": normalized_implementations,
                }
            )

        return anomalies

    def score_batch(
        self,
        operation: str,
        batch: List[Dict[str, Any]],
        result_file: Path,
        suite_file: Path,
    ) -> List[Dict[str, Any]]:
        prompt = build_confidence_prompt(
            operation=operation,
            batch=batch,
            result_file=str(result_file),
            suite_file=str(suite_file),
            protocol=self.protocol,
        )
        try:
            response_text = run_text_agent(
                agent_name="NRF Confidence Agent",
                instructions=SYSTEM_PROMPT_CONFIDENCE_TRIAGE.format(protocol=self.protocol),
                prompt=prompt,
                workflow_name="NRF Confidence Scoring",
            )
        except Exception as exc:
            print(f"  → Error calling agent for {operation}: {exc}", flush=True)
            return []

        parsed = _parse_json_array(response_text)
        if parsed is None:
            return []

        normalized_scores: List[Dict[str, Any]] = []
        for item in parsed:
            normalized = _normalize_score_item(item)
            if normalized is not None:
                normalized_scores.append(normalized)
        return normalized_scores

    def write_operation_scores(
        self,
        operation: str,
        source_result_file: Path,
        source_suite_file: Path,
        scores: List[Dict[str, Any]],
    ) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_file = self.output_dir / f"{operation}.json"
        payload = {
            "operation": operation,
            "source_test_results_file": str(source_result_file),
            "source_tests_file": str(source_suite_file),
            "scores": sorted(scores, key=lambda item: item["test_id"]),
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return output_file

    def process_result_file(self, result_file: Path) -> Optional[Path]:
        result_payload = self.load_test_results(result_file)
        operation = str(result_payload.get("operation") or result_file.stem)
        suite_file = self.testcases_dir / f"{operation}_tests.json"
        anomalies = self.build_anomalies(operation, result_file)
        if not anomalies:
            return self.write_operation_scores(operation, result_file, suite_file, [])

        all_scores: List[Dict[str, Any]] = []
        batches = _chunked(anomalies, self.batch_size)
        for batch_index, batch in enumerate(batches, 1):
            print(
                f"  → Scoring {operation} anomaly batch {batch_index}/{len(batches)} ({len(batch)} test(s))",
                flush=True,
            )
            batch_scores = self.score_batch(operation, batch, result_file, suite_file)
            all_scores.extend(batch_scores)

        return self.write_operation_scores(operation, result_file, suite_file, all_scores)

    def run(self, result_files: Optional[Sequence[Path]] = None) -> List[Path]:
        if result_files is None:
            result_files = self.discover_result_files()

        written_files: List[Path] = []
        for result_file in result_files:
            if result_file.name.startswith("."):
                continue
            try:
                written_file = self.process_result_file(result_file)
            except FileNotFoundError as exc:
                print(f"Skipping {result_file.name}: {exc}", flush=True)
                continue
            written_files.append(written_file)
            print(f"Confidence scores saved to {written_file}", flush=True)
        return written_files


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate confidence scores for NRF implementation anomalies.")
    parser.add_argument(
        "--test-results-dir",
        type=Path,
        default=TEST_RESULTS_DIR,
        help="Directory containing per-operation comparison result JSON files.",
    )
    parser.add_argument(
        "--testcases-dir",
        type=Path,
        default=TESTCASES_DIR,
        help="Directory containing the original *_tests.json suites.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=CONFIDENCE_SCORES_DIR,
        help="Directory where confidence score JSON files should be written.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Maximum number of anomaly tests to send to the agent per call.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    generator = ConfidenceScoreAgent(
        test_results_dir=args.test_results_dir,
        testcases_dir=args.testcases_dir,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
    )
    generator.run()


if __name__ == "__main__":
    main()
