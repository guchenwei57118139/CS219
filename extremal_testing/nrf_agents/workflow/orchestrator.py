"""Top-level orchestration for the NRF extremal testing workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from implementation_testers.test_implementations import ImplementationComparisonRunner
from nrf_agents.workflow.confidence_agent import ConfidenceScoreAgent
from nrf_agents.workflow.metadata_agent import OperationMetadataAgent
from nrf_agents.workflow.schema_agent import OperationSchemaAgent
from nrf_agents.workflow.testcase_agent import TestCaseAgent


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
    def confidence_scores_dir(self) -> Path:
        return self.root_dir / "json" / "confidence_scores"


class NRFExtremalTestingAgent:
    """Coordinate the full NRF extremal testing pipeline."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = root_dir or ROOT_DIR
        self.paths = NRFWorkflowPaths(self.root_dir)

    def run_metadata_extraction(self) -> None:
        OperationMetadataAgent(
            spec_segment_directory=self.root_dir / "specs" / "segments",
            output_file=self.root_dir / "json" / "AllOpsMetaData.json",
        ).run()

    def run_schema_extraction(self) -> None:
        OperationSchemaAgent(
            metadata_file=self.root_dir / "json" / "AllOpsMetaData.json",
            spec_file=self.root_dir / "specs" / "original" / "nrf_management_api.txt",
            output_file=self.root_dir / "json" / "operation_schemas.json",
        ).run()

    def run_test_generation(self) -> None:
        TestCaseAgent(
            operation_schemas_file=self.root_dir / "json" / "operation_schemas.json",
            test_format_file=self.root_dir / "json" / "config" / "test_format.json",
            output_dir=self.root_dir / "json" / "testcases",
        ).run()

    def run_implementation_testing(self) -> list[Path]:
        runner = ImplementationComparisonRunner()
        suite_files = runner.discover_suite_files()
        if not suite_files:
            print("No generated suites found for implementation testing.", flush=True)
            return []

        written_files = runner.run(suite_files)
        for path in written_files:
            print(f"Implementation comparison saved to {path}", flush=True)
        return written_files

    def run_confidence_scoring(self, result_files: list[Path]) -> None:
        ConfidenceScoreAgent(
            test_results_dir=self.paths.test_results_dir,
            testcases_dir=self.paths.testcases_dir,
            output_dir=self.paths.confidence_scores_dir,
        ).run(result_files=result_files)

    def run(self) -> None:
        """Run the complete workflow end to end."""
        print("[1/5] Generating operation metadata...", flush=True)
        self.run_metadata_extraction()

        print("[2/5] Generating operation schemas...", flush=True)
        self.run_schema_extraction()

        print("[3/5] Generating test cases...", flush=True)
        self.run_test_generation()

        print("[4/5] Running implementation tests...", flush=True)
        result_files = self.run_implementation_testing()

        print("[5/5] Generating confidence scores...", flush=True)
        self.run_confidence_scoring(result_files)


def main() -> None:
    NRFExtremalTestingAgent().run()


if __name__ == "__main__":
    main()
