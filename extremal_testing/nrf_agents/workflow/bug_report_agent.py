"""Bug report agent for NRF implementation differences."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extremal_testing.nrf_agents.prompts.bug_reports import (
    DEFAULT_PROTOCOL,
    SYSTEM_PROMPT_BUG_REPORT_TRIAGE,
    build_bug_report_prompt,
)
from extremal_testing.nrf_agents.workflow.sdk import run_text_agent

DEFAULT_BATCH_SIZE = 5
DEFAULT_MAX_REPORTS = 3
DEFAULT_MIN_STRENGTH = 7
DEFAULT_EXCEPTIONAL_STRENGTH = 9
BODY_SNIPPET_LIMIT = 240

TEST_RESULTS_DIR = ROOT_DIR / "json" / "test_results"
TESTCASES_DIR = ROOT_DIR / "json" / "testcases"
REPORTS_DIR = ROOT_DIR / "reports"


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
    if chunk_size <= 0:
        chunk_size = DEFAULT_BATCH_SIZE
    return [list(items[idx : idx + chunk_size]) for idx in range(0, len(items), chunk_size)]


def _load_json_file(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _stringify_compact(value: Any, limit: int = BODY_SNIPPET_LIMIT) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, sort_keys=True, ensure_ascii=False)
        except TypeError:
            text = str(value)
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def _status_code_values(implementations: Dict[str, Any], implementation_order: Sequence[str]) -> List[int]:
    status_codes: List[int] = []
    for implementation_name in implementation_order:
        implementation_result = implementations.get(implementation_name, {})
        if not isinstance(implementation_result, dict):
            continue
        status_code = implementation_result.get("status_code")
        if isinstance(status_code, int):
            status_codes.append(status_code)
    return status_codes


def _normalized_values(
    implementations: Dict[str, Any],
    implementation_order: Sequence[str],
    field: str,
) -> List[Optional[str]]:
    values: List[Optional[str]] = []
    for implementation_name in implementation_order:
        implementation_result = implementations.get(implementation_name, {})
        if not isinstance(implementation_result, dict):
            continue
        values.append(_stringify_compact(implementation_result.get(field)))
    return values


def _has_meaningful_difference(test_result: Dict[str, Any], implementation_order: Sequence[str]) -> bool:
    implementations = test_result.get("implementations", {})
    if not isinstance(implementations, dict):
        return False

    status_codes = _status_code_values(implementations, implementation_order)
    if len(status_codes) >= 2 and len(set(status_codes)) > 1:
        return True

    errors = _normalized_values(implementations, implementation_order, "error")
    non_empty_errors = [value for value in errors if value]
    if non_empty_errors and len(set(errors)) > 1:
        return True

    bodies = _normalized_values(implementations, implementation_order, "response_body")
    non_empty_bodies = [value for value in bodies if value]
    if non_empty_bodies and len(set(bodies)) > 1:
        return True

    return False


def _normalize_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _normalize_report_item(
    item: Dict[str, Any],
    valid_test_ids: set[int],
    min_strength: int,
) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None

    title = _normalize_string(item.get("title"))
    description = _normalize_string(item.get("description"))
    investigation_value = _normalize_string(item.get("investigation_value"))
    if not title or not description:
        return None

    evidence_ids_raw = item.get("evidence_test_ids")
    if not isinstance(evidence_ids_raw, list):
        return None
    evidence_test_ids: List[int] = []
    for test_id in evidence_ids_raw:
        if isinstance(test_id, bool):
            continue
        if isinstance(test_id, int) and test_id in valid_test_ids and test_id not in evidence_test_ids:
            evidence_test_ids.append(test_id)
    if not evidence_test_ids:
        return None

    strength = item.get("strength")
    if isinstance(strength, bool):
        strength = int(strength)
    elif not isinstance(strength, int):
        try:
            strength = int(strength)
        except (TypeError, ValueError):
            strength = min_strength
    strength = max(1, min(10, strength))
    if strength < min_strength:
        return None

    affected_raw = item.get("possibly_affected_implementations")
    possibly_affected: List[str] = []
    if isinstance(affected_raw, list):
        for implementation_name in affected_raw:
            normalized = _normalize_string(implementation_name)
            if normalized and normalized not in possibly_affected:
                possibly_affected.append(normalized)

    return {
        "title": title,
        "description": description,
        "possibly_affected_implementations": possibly_affected,
        "affected_rationale": _normalize_string(item.get("affected_rationale")),
        "evidence_test_ids": evidence_test_ids,
        "investigation_value": investigation_value,
        "strength": strength,
    }


def _dedupe_reports(reports: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen: set[tuple[str, tuple[int, ...]]] = set()
    for report in reports:
        key = (
            str(report["title"]).casefold(),
            tuple(sorted(report["evidence_test_ids"])),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(report)
    return deduped


def _select_strong_reports(
    reports: Sequence[Dict[str, Any]],
    max_reports: int,
    exceptional_strength: int,
) -> List[Dict[str, Any]]:
    sorted_reports = sorted(
        _dedupe_reports(reports),
        key=lambda item: (item["strength"], len(item["evidence_test_ids"])),
        reverse=True,
    )
    if max_reports <= 0:
        return sorted_reports

    selected: List[Dict[str, Any]] = []
    for index, report in enumerate(sorted_reports):
        if index < max_reports or report["strength"] >= exceptional_strength:
            selected.append(report)
    return selected


def _markdown_escape_cell(value: Any) -> str:
    text = _normalize_string(value)
    if not text:
        return "-"
    return text.replace("|", "\\|").replace("\n", " ")


class BugReportAgent:
    """Generate Markdown bug reports for implementation differences, grouped by operation."""

    def __init__(
        self,
        test_results_dir: Path = TEST_RESULTS_DIR,
        testcases_dir: Path = TESTCASES_DIR,
        reports_dir: Path = REPORTS_DIR,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_reports: int = DEFAULT_MAX_REPORTS,
        min_strength: int = DEFAULT_MIN_STRENGTH,
        exceptional_strength: int = DEFAULT_EXCEPTIONAL_STRENGTH,
        protocol: str = DEFAULT_PROTOCOL,
    ) -> None:
        self.test_results_dir = test_results_dir
        self.testcases_dir = testcases_dir
        self.reports_dir = reports_dir
        self.batch_size = batch_size
        self.max_reports = max_reports
        self.min_strength = min_strength
        self.exceptional_strength = exceptional_strength
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
            if not _has_meaningful_difference(test_result, implementation_order):
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
                    "response_body": _stringify_compact(implementation_result.get("response_body")),
                    "error": _stringify_compact(implementation_result.get("error")),
                }

            anomalies.append(
                {
                    "test_id": test_id,
                    "test_case_id": original_test_case.get("id"),
                    "test_name": test_result.get("test_name", f"Test case {test_id + 1}"),
                    "constraint": original_test_case.get("constraint"),
                    "constraint_schema_id": original_test_case.get("constraint_schema_id"),
                    "request": {
                        "method": original_test_case.get("method"),
                        "path": original_test_case.get("path"),
                        "body": _stringify_compact(original_test_case.get("body")),
                    },
                    "implementations": normalized_implementations,
                }
            )

        return anomalies

    def generate_bug_report_batch(
        self,
        operation: str,
        batch: List[Dict[str, Any]],
        result_file: Path,
        suite_file: Path,
    ) -> List[Dict[str, Any]]:
        prompt = build_bug_report_prompt(
            operation=operation,
            batch=batch,
            result_file=str(result_file),
            suite_file=str(suite_file),
            protocol=self.protocol,
        )
        try:
            response_text = run_text_agent(
                agent_name="Bug Report Agent",
                instructions=SYSTEM_PROMPT_BUG_REPORT_TRIAGE.format(protocol=self.protocol),
                prompt=prompt,
                workflow_name="Bug Report Generation",
            )
        except Exception as exc:
            print(f"  -> Error calling agent for {operation}: {exc}", flush=True)
            return []

        parsed = _parse_json_array(response_text)
        if parsed is None:
            return []

        valid_test_ids = {item["test_id"] for item in batch if isinstance(item.get("test_id"), int)}
        normalized_reports: List[Dict[str, Any]] = []
        for item in parsed:
            normalized = _normalize_report_item(item, valid_test_ids, self.min_strength)
            if normalized is not None:
                normalized_reports.append(normalized)
        return normalized_reports

    def render_markdown(
        self,
        operation: str,
        source_result_file: Path,
        source_suite_file: Path,
        anomalies: Sequence[Dict[str, Any]],
        reports: Sequence[Dict[str, Any]],
    ) -> str:
        anomaly_by_id = {
            anomaly["test_id"]: anomaly
            for anomaly in anomalies
            if isinstance(anomaly.get("test_id"), int)
        }

        lines: List[str] = [
            f"# {operation} Bug Report",
            "",
            f"- Source results: `{source_result_file}`",
            f"- Source tests: `{source_suite_file}`",
            f"- Anomaly tests reviewed: {len(anomalies)}",
            f"- Reports selected: {len(reports)}",
            "",
        ]

        if not reports:
            lines.extend(
                [
                    "## No High-Signal Reports Selected",
                    "",
                    "No strong reportable bug patterns were selected from the observed implementation differences.",
                    "",
                ]
            )
            return "\n".join(lines).rstrip() + "\n"

        for index, report in enumerate(reports, 1):
            possibly_affected = report.get("possibly_affected_implementations", [])
            affected_text = ", ".join(possibly_affected) if possibly_affected else "Not assigned"
            lines.extend(
                [
                    f"## {index}. {report['title']}",
                    "",
                    report["description"],
                    "",
                    f"- Possibly affected implementations: {affected_text}",
                    f"- Evidence strength: {report['strength']}/10",
                ]
            )
            affected_rationale = report.get("affected_rationale")
            if affected_rationale:
                lines.append(f"- Rationale: {affected_rationale}")
            investigation_value = report.get("investigation_value")
            if investigation_value:
                lines.append(f"- Why investigate: {investigation_value}")
            lines.extend(
                [
                    "",
                    "| Test | Constraint | Request | free5gc | oai | open5gs |",
                    "| --- | --- | --- | --- | --- | --- |",
                ]
            )

            for test_id in report["evidence_test_ids"]:
                anomaly = anomaly_by_id.get(test_id)
                if anomaly is None:
                    continue
                request = anomaly.get("request", {})
                request_text = f"{request.get('method', '-')} {request.get('path', '-')}"
                implementations = anomaly.get("implementations", {})
                row = [
                    f"{anomaly.get('test_case_id') or test_id}: {anomaly.get('test_name', '')}",
                    anomaly.get("constraint"),
                    request_text,
                    self._implementation_summary(implementations.get("free5gc", {})),
                    self._implementation_summary(implementations.get("oai", {})),
                    self._implementation_summary(implementations.get("open5gs", {})),
                ]
                lines.append("| " + " | ".join(_markdown_escape_cell(value) for value in row) + " |")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def _implementation_summary(self, implementation_result: Any) -> str:
        if not isinstance(implementation_result, dict):
            return "-"
        parts = [f"status={implementation_result.get('status_code')}"]
        if implementation_result.get("error"):
            parts.append(f"error={implementation_result['error']}")
        if implementation_result.get("response_body"):
            parts.append(f"body={implementation_result['response_body']}")
        return "; ".join(parts)

    def write_operation_report(
        self,
        operation: str,
        source_result_file: Path,
        source_suite_file: Path,
        anomalies: Sequence[Dict[str, Any]],
        reports: Sequence[Dict[str, Any]],
    ) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        output_file = self.reports_dir / f"{operation}.md"
        markdown = self.render_markdown(operation, source_result_file, source_suite_file, anomalies, reports)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown)
        return output_file

    def process_result_file(self, result_file: Path) -> Optional[Path]:
        result_payload = self.load_test_results(result_file)
        operation = str(result_payload.get("operation") or result_file.stem)
        suite_file = self.testcases_dir / f"{operation}_tests.json"
        anomalies = self.build_anomalies(operation, result_file)
        if not anomalies:
            return self.write_operation_report(operation, result_file, suite_file, [], [])

        all_reports: List[Dict[str, Any]] = []
        batches = _chunked(anomalies, self.batch_size)
        for batch_index, batch in enumerate(batches, 1):
            print(
                f"  -> Reviewing {operation} anomaly batch {batch_index}/{len(batches)} ({len(batch)} test(s))",
                flush=True,
            )
            batch_reports = self.generate_bug_report_batch(operation, batch, result_file, suite_file)
            all_reports.extend(batch_reports)

        selected_reports = _select_strong_reports(all_reports, self.max_reports, self.exceptional_strength)
        return self.write_operation_report(operation, result_file, suite_file, anomalies, selected_reports)

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
            print(f"Bug report saved to {written_file}", flush=True)
        return written_files


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Markdown bug reports for NRF implementation differences.")
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
        "--reports-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Directory where Markdown bug reports should be written.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Maximum number of anomaly tests to send to the agent per call.",
    )
    parser.add_argument(
        "--max-reports",
        type=int,
        default=DEFAULT_MAX_REPORTS,
        help="Soft maximum number of bug reports to keep per operation.",
    )
    parser.add_argument(
        "--min-strength",
        type=int,
        default=DEFAULT_MIN_STRENGTH,
        help="Minimum LLM report strength required to include a bug report.",
    )
    parser.add_argument(
        "--exceptional-strength",
        type=int,
        default=DEFAULT_EXCEPTIONAL_STRENGTH,
        help="Strength threshold that allows reports beyond --max-reports.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    generator = BugReportAgent(
        test_results_dir=args.test_results_dir,
        testcases_dir=args.testcases_dir,
        reports_dir=args.reports_dir,
        batch_size=args.batch_size,
        max_reports=args.max_reports,
        min_strength=args.min_strength,
        exceptional_strength=args.exceptional_strength,
    )
    generator.run()


if __name__ == "__main__":
    main()
