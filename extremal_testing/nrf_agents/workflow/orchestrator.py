"""Top-level orchestration for the NRF extremal testing workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nrf_agents.workflow.confidence_agent import ConfidenceScoreAgent
from nrf_agents.workflow.metadata_agent import OperationMetadataAgent
from nrf_agents.workflow.schema_agent import OperationSchemaAgent
from nrf_agents.workflow.testcase_agent import TestCaseAgent


@dataclass
class NRFWorkflowPaths:
    """Canonical repo paths used by the workflow."""

    root_dir: Path

    @property
    def generated_dir(self) -> Path:
        return self.root_dir / "data" / "generated"

    @property
    def test_results_dir(self) -> Path:
        return self.root_dir / "data" / "test_results"

    @property
    def confidence_scores_dir(self) -> Path:
        return self.root_dir / "data" / "confidence_scores"


class NRFExtremalTestingAgent:
    """Coordinate the full NRF extremal testing pipeline."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = root_dir or Path(__file__).resolve().parents[2]
        self.paths = NRFWorkflowPaths(self.root_dir)

    def run_metadata_extraction(self) -> None:
        OperationMetadataAgent(
            spec_segment_directory=self.root_dir / "data" / "specs" / "segments",
            output_file=self.root_dir / "data" / "generated" / "AllOpsMetaData.json",
        ).run()

    def run_schema_extraction(self) -> None:
        OperationSchemaAgent(
            metadata_file=self.root_dir / "data" / "generated" / "AllOpsMetaData.json",
            spec_file=self.root_dir / "data" / "specs" / "original" / "nrf_management_api.txt",
            output_file=self.root_dir / "data" / "generated" / "operation_schemas.json",
        ).run()

    def run_test_generation(self) -> None:
        TestCaseAgent(
            operation_schemas_file=self.root_dir / "data" / "generated" / "operation_schemas.json",
            test_format_file=self.root_dir / "data" / "config" / "test_format.json",
            output_dir=self.root_dir / "data" / "generated",
        ).run()

    def run_confidence_scoring(self) -> None:
        ConfidenceScoreAgent(
            test_results_dir=self.paths.test_results_dir,
            generated_dir=self.paths.generated_dir,
            output_dir=self.paths.confidence_scores_dir,
        ).run()

    def run(self) -> None:
        """Run the complete workflow end to end."""
        self.run_metadata_extraction()
        self.run_schema_extraction()
        self.run_test_generation()
        self.run_confidence_scoring()


def main() -> None:
    NRFExtremalTestingAgent().run()


if __name__ == "__main__":
    main()
