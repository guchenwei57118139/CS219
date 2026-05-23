"""Top-level orchestration for the NRF extremal testing workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Optional

PROJECT_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extremal_testing.implementation_testers.implementation_tester import ImplementationTester
from extremal_testing.nrf_agents.workflow.bug_report_agent import BugReportAgent
from extremal_testing.nrf_agents.workflow.constraint_agent import ConstraintAgent
from extremal_testing.nrf_agents.workflow.test_agent import TestAgent


@dataclass
class NRFWorkflowPaths:
    """Canonical repo paths used by the workflow."""

    root_dir: Path

    @property
    def testcases_dir(self) -> Path:
        return self.root_dir / "json" / "testcases"

    @property
    def test_results_dir(self) -> Path:
        return self.root_dir / "json" / "test_results"

    @property
    def reports_dir(self) -> Path:
        return self.root_dir / "reports"


class NRFExtremalTestingAgent:
    """Coordinate the full NRF extremal testing pipeline."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = root_dir or PROJECT_DIR
        self.paths = NRFWorkflowPaths(self.root_dir)

    def run_constraint_generation(self) -> None:
        ConstraintAgent(
            metadata_file=self.root_dir / "json" / "AllOpsMetaData.json",
            spec_file=self.root_dir / "specs" / "original" / "TS29510_Nnrf_NFManagement.yaml",
            output_dir=self.root_dir / "json" / "constraints",
        ).run()

    def run_test_generation(self) -> None:
        TestAgent(
            constraints_dir=self.root_dir / "json" / "constraints",
            metadata_file=self.root_dir / "json" / "AllOpsMetaData.json",
            test_format_file=self.root_dir / "json" / "config" / "test_format.json",
            output_dir=self.root_dir / "json" / "testcases",
        ).run()

    def run_implementation_testing(self) -> list[Path]:
        tester = ImplementationTester()
        suite_files = tester.discover_suite_files()
        if not suite_files:
            print("No generated suites found for implementation testing.", flush=True)
            return []

        written_files = tester.run(suite_files)
        for path in written_files:
            print(f"Implementation comparison saved to {path}", flush=True)
        return written_files

    def run_bug_report_generation(self, result_files: list[Path]) -> None:
        BugReportAgent(
            test_results_dir=self.paths.test_results_dir,
            testcases_dir=self.paths.testcases_dir,
            reports_dir=self.paths.reports_dir,
        ).run(result_files=result_files)

    def run(self) -> None:
        """Run the complete workflow end to end."""
        print("[1/4] Constraint Generation...", flush=True)
        self.run_constraint_generation()

        print("[2/4] Test Generation...", flush=True)
        self.run_test_generation()

        print("[3/4] Implementation Testing...", flush=True)
        result_files = self.run_implementation_testing()

        print("[4/4] Bug Report Generation...", flush=True)
        self.run_bug_report_generation(result_files)


def main() -> None:
    NRFExtremalTestingAgent().run()


if __name__ == "__main__":
    main()
