"""Metadata extraction agent for NRF operations."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from nrf_agents.models.common import OperationMetadata
from nrf_agents.prompts.metadata import (
    SYSTEM_PROMPT_OPERATION_EXTRACTION,
    build_operation_metadata_prompt,
)
from nrf_agents.workflow.sdk import run_text_agent
from utils.postprocess_dependencies import DependencyProcessor

OUTPUT_FORMAT_PATH = ROOT_DIR / "data" / "generated" / "AllOpsMetaData.json"
SPEC_SEGMENT_DIR = ROOT_DIR / "data" / "specs" / "segments"


def parse_json_from_llm_response(llm_response_text: str) -> Optional[List]:
    """Parse a JSON array from LLM output."""
    try:
        return json.loads(llm_response_text)
    except json.JSONDecodeError:
        json_start_index = llm_response_text.find("[")
        json_end_index = llm_response_text.rfind("]")

        if json_start_index != -1 and json_end_index != -1 and json_end_index > json_start_index:
            try:
                return json.loads(llm_response_text[json_start_index : json_end_index + 1])
            except json.JSONDecodeError:
                print("Could not parse JSON from section. Skipping this section.", flush=True)
                return None

        print("No JSON array found in model output for this section. Skipping.", flush=True)
        return None


def validate_operation_metadata(operation_dict: Dict) -> bool:
    return (
        isinstance(operation_dict, dict)
        and "Operation" in operation_dict
        and isinstance(operation_dict["Operation"], str)
        and "Description" in operation_dict
        and isinstance(operation_dict["Description"], str)
        and "Paths" in operation_dict
        and isinstance(operation_dict["Paths"], str)
        and "Method" in operation_dict
        and isinstance(operation_dict["Method"], str)
    )


def normalize_operation_metadata(operation_dict: Dict[str, str]) -> OperationMetadata:
    normalized = {
        "Operation": operation_dict["Operation"].strip(),
        "Description": operation_dict["Description"].strip(),
        "Paths": operation_dict["Paths"].strip(),
        "Method": operation_dict["Method"].strip(),
    }
    if "DependsOn" in operation_dict and operation_dict["DependsOn"]:
        depends_on_value = operation_dict["DependsOn"]
        if isinstance(depends_on_value, list):
            normalized["DependsOn"] = ", ".join(str(item).strip() for item in depends_on_value if item)
        elif isinstance(depends_on_value, str):
            normalized["DependsOn"] = depends_on_value.strip()
        else:
            normalized["DependsOn"] = str(depends_on_value).strip()
    return normalized


def filter_nf_operations(operations: List[OperationMetadata]) -> List[OperationMetadata]:
    return [
        op
        for op in operations
        if op.get("Operation", "").startswith("NF")
        and op.get("Method", "").upper() != "PATCH"
    ]


class OperationMetadataAgent:
    """Extract high-level API operation information from specification sections."""

    def __init__(self, spec_segment_directory: Path = SPEC_SEGMENT_DIR, output_file: Path = OUTPUT_FORMAT_PATH):
        self.spec_segment_directory = spec_segment_directory
        self.output_file = output_file

    def extract_operations_from_section(self, section_text: str) -> List[OperationMetadata]:
        prompt = build_operation_metadata_prompt(section_text)
        llm_response = run_text_agent(
            agent_name="NRF Metadata Agent",
            instructions=SYSTEM_PROMPT_OPERATION_EXTRACTION,
            prompt=prompt,
            workflow_name="NRF Metadata Extraction",
        )
        parsed_data = parse_json_from_llm_response(llm_response)
        if parsed_data is None or not isinstance(parsed_data, list):
            if parsed_data is not None:
                print("Model output is not a list. Skipping this section.", flush=True)
            return []

        extracted_operations: List[OperationMetadata] = []
        for operation_item in parsed_data:
            if validate_operation_metadata(operation_item):
                extracted_operations.append(normalize_operation_metadata(operation_item))
        return extracted_operations

    def find_spec_segment_files(self) -> List[Path]:
        section_file_pattern = re.compile(r"^section_5_2.*\.txt$")
        matching_files: List[Path] = []
        for file_path in self.spec_segment_directory.iterdir():
            if file_path.is_file() and section_file_pattern.match(file_path.name):
                matching_files.append(file_path)
        matching_files.sort(key=lambda path: path.name)
        return matching_files

    def process_spec_segment_files(self) -> List[OperationMetadata]:
        all_extracted_operations: List[OperationMetadata] = []
        spec_segment_files = self.find_spec_segment_files()

        print(f"Found {len(spec_segment_files)} section file(s) to process", flush=True)

        for section_file_path in spec_segment_files:
            print(f"[*] Processing section file: {section_file_path.name}...", flush=True)
            with section_file_path.open("r", encoding="utf-8") as file:
                section_text = file.read()

            print("  → Sending to agent...", flush=True)
            extracted_operations = self.extract_operations_from_section(section_text)
            print(f"  → Extracted {len(extracted_operations)} operation(s) from this section", flush=True)

            if extracted_operations:
                all_extracted_operations.extend(extracted_operations)

        return all_extracted_operations

    def save_operations_metadata(self, operations: List[OperationMetadata]) -> None:
        self.output_file.write_text(json.dumps(operations, indent=2, ensure_ascii=False), encoding="utf-8")

    def run(self) -> None:
        print("Starting operations metadata extraction...", flush=True)
        print(f"Looking for section files in: {self.spec_segment_directory}", flush=True)

        extracted_operations = self.process_spec_segment_files()

        print("Processing complete. Filtering NF operations...", flush=True)
        nf_operations = filter_nf_operations(extracted_operations)
        print(f"  → Found {len(nf_operations)} NF operation(s) out of {len(extracted_operations)} total", flush=True)

        print("Expanding dependencies (computing transitive closure)...", flush=True)
        dependency_processor = DependencyProcessor(nf_operations)
        expanded_operations = dependency_processor.expand_dependencies()
        ops_with_deps = sum(1 for op in expanded_operations if "DependsOn" in op and op["DependsOn"])
        print(f"  → {ops_with_deps} operation(s) have dependencies", flush=True)

        print(f"Saving to {self.output_file}...", flush=True)
        self.save_operations_metadata(expanded_operations)

        print(f"\n[✓] Extracted {len(extracted_operations)} operation(s) total")
        print(f"[✓] Filtered to {len(nf_operations)} NF operation(s)")
        print(f"[✓] Expanded dependencies for {ops_with_deps} operation(s)", flush=True)
        print(f"[✓] Saved to {self.output_file.name}", flush=True)


def main() -> None:
    OperationMetadataAgent().run()


if __name__ == "__main__":
    main()
