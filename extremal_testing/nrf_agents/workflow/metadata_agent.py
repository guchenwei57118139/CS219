"""Metadata extraction agent for NRF operations."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extremal_testing.nrf_agents.models.common import OperationMetadata
from extremal_testing.nrf_agents.prompts.metadata import (
    SYSTEM_PROMPT_OPERATION_DEDUPLICATION,
    SYSTEM_PROMPT_OPERATION_EXTRACTION,
    build_operation_metadata_deduplication_prompt,
    build_operation_metadata_prompt,
)
from extremal_testing.nrf_agents.workflow.sdk import run_text_agent

OUTPUT_FORMAT_PATH = ROOT_DIR / "json" / "AllOpsMetaData.json"
SPEC_SEGMENT_DIR = ROOT_DIR / "specs" / "segments"


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


def operation_group_key(operation: Dict[str, Any]) -> str:
    operation_name = str(operation.get("Operation", "")).strip().lower()
    if operation_name:
        return operation_name

    path = str(operation.get("Paths", "")).strip().lower()
    method = str(operation.get("Method", "")).strip().upper()
    return f"{path}|{method}"


def serialize_operation(operation: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "Operation": operation.get("Operation", ""),
        "Description": operation.get("Description", ""),
        "Paths": operation.get("Paths", ""),
        "Method": operation.get("Method", ""),
    }
    if "DependsOn" in operation and operation["DependsOn"]:
        payload["DependsOn"] = operation["DependsOn"]
    return payload


def unique_operations(operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for operation in operations:
        signature = json.dumps(operation, sort_keys=True, ensure_ascii=False)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(operation)
    return deduped


def filter_nf_operations(operations: List[OperationMetadata]) -> List[OperationMetadata]:
    return [
        op
        for op in operations
        if op.get("Operation", "").startswith("NF")
        and op.get("Method", "").upper() != "PATCH"
    ]


class DependencyProcessor:
    """Process and expand operation dependencies to include all direct and indirect parents."""

    def __init__(self, operations: List[Dict]):
        """Initialize with a list of operations."""
        self.operations = operations
        self.operation_names = {op["Operation"] for op in operations}
        self.dependency_graph: Dict[str, Set[str]] = {}
        self._build_graph()

    def _build_graph(self) -> None:
        """Build a dependency graph mapping operation names to their direct dependencies."""
        graph: Dict[str, Set[str]] = defaultdict(set)

        for operation in self.operations:
            operation_name = operation["Operation"]
            if "DependsOn" in operation and operation["DependsOn"]:
                depends_on_value = operation["DependsOn"]

                # Handle both string (comma-separated) and list formats
                if isinstance(depends_on_value, str):
                    dependencies = [dep.strip() for dep in depends_on_value.split(",") if dep.strip()]
                elif isinstance(depends_on_value, list):
                    dependencies = [str(dep).strip() for dep in depends_on_value if dep]
                else:
                    dependencies = [str(depends_on_value).strip()]

                # Only add dependencies that exist in the operations list
                for dep in dependencies:
                    if dep in self.operation_names:
                        graph[operation_name].add(dep)

        self.dependency_graph = dict(graph)

    def _compute_transitive_dependencies_with_depth(
        self,
        operation_name: str,
        visited: Set[str] = None,
        current_depth: int = 0,
    ) -> Dict[str, int]:
        """Compute all direct and indirect dependencies with their depth in the dependency tree."""
        if visited is None:
            visited = set()

        if operation_name in visited:
            return {}  # Cycle detected, return empty to avoid infinite recursion

        visited.add(operation_name)
        dependency_depths: Dict[str, int] = {}

        if operation_name in self.dependency_graph:
            direct_deps = self.dependency_graph[operation_name]

            # Direct dependencies are at current_depth (youngest from this node's perspective)
            for dep in direct_deps:
                if dep not in dependency_depths:
                    dependency_depths[dep] = current_depth

            # Recursively get indirect dependencies (deeper = older ancestors)
            for dep in direct_deps:
                # Recursive call starts at depth 0 for the child node
                indirect_deps = self._compute_transitive_dependencies_with_depth(
                    dep, visited.copy(), 0
                )
                for indirect_dep, indirect_depth in indirect_deps.items():
                    # Add 1 to convert depth relative to 'dep' to depth relative to 'operation_name'
                    # Keep the maximum depth (deepest = eldest ancestor)
                    adjusted_depth = indirect_depth + 1
                    if indirect_dep not in dependency_depths or dependency_depths[indirect_dep] < adjusted_depth:
                        dependency_depths[indirect_dep] = adjusted_depth

        return dependency_depths

    def expand_dependencies(self) -> List[Dict]:
        """Expand DependsOn to include all direct and indirect parent operations, ordered from eldest to youngest ancestor."""
        expanded_operations = []

        for operation in self.operations:
            operation_name = operation["Operation"]
            expanded_operation = operation.copy()

            # Get all transitive dependencies with their depths
            dependency_depths = self._compute_transitive_dependencies_with_depth(operation_name)

            if dependency_depths:
                # Sort by depth descending (eldest first), then by name for consistency
                sorted_deps = sorted(
                    dependency_depths.keys(),
                    key=lambda dep: (-dependency_depths[dep], dep)
                )
                expanded_operation["DependsOn"] = sorted_deps
            else:
                # Remove DependsOn if empty or not present
                expanded_operation.pop("DependsOn", None)

            expanded_operations.append(expanded_operation)

        return expanded_operations


def expand_dependencies(operations: List[Dict]) -> List[Dict]:
    """Convenience function to expand dependencies for a list of operations."""
    processor = DependencyProcessor(operations)
    return processor.expand_dependencies()


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

    def deduplicate_operations(self, operations: List[OperationMetadata]) -> List[OperationMetadata]:
        if not operations:
            return []

        grouped_operations: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        group_order: List[str] = []
        for operation in operations:
            serialized_operation = serialize_operation(operation)
            key = operation_group_key(serialized_operation)
            if key not in grouped_operations:
                group_order.append(key)
            grouped_operations[key].append(serialized_operation)

        deduplicated_operations: List[OperationMetadata] = []
        duplicate_groups = sum(1 for key in group_order if len(grouped_operations[key]) > 1)
        if duplicate_groups == 0:
            print("  → No duplicate candidate groups found; skipping LLM deduplication", flush=True)
            return list(operations)

        print(f"  → Running LLM deduplication across {duplicate_groups} duplicate candidate group(s)", flush=True)
        for index, key in enumerate(group_order, 1):
            group = grouped_operations[key]
            if len(group) == 1:
                deduplicated_operations.append(normalize_operation_metadata(group[0]))
                continue

            group_label = str(group[0].get("Operation", "")).strip() or key
            print(f"    [dedupe {index}/{len(group_order)}] Reviewing {group_label} ({len(group)} candidate record(s))...", flush=True)

            prompt = build_operation_metadata_deduplication_prompt(group_label, group)
            try:
                response_text = run_text_agent(
                    agent_name="NRF Metadata Deduplication Agent",
                    instructions=SYSTEM_PROMPT_OPERATION_DEDUPLICATION,
                    prompt=prompt,
                    workflow_name="NRF Metadata Deduplication",
                )
            except Exception as exc:
                print(f"      → Error calling deduplication agent: {exc}", flush=True)
                deduplicated_operations.extend(normalize_operation_metadata(item) for item in unique_operations(group))
                continue

            parsed_data = parse_json_from_llm_response(response_text)
            if parsed_data is None or not isinstance(parsed_data, list):
                print("      → Deduplication agent returned an invalid payload; keeping the original group", flush=True)
                deduplicated_operations.extend(normalize_operation_metadata(item) for item in unique_operations(group))
                continue

            canonical_records: List[Dict[str, Any]] = []
            for record in parsed_data:
                if validate_operation_metadata(record):
                    canonical_records.append(serialize_operation(normalize_operation_metadata(record)))

            if not canonical_records:
                print("      → No valid deduplicated records returned; keeping the original group", flush=True)
                deduplicated_operations.extend(normalize_operation_metadata(item) for item in unique_operations(group))
                continue

            deduplicated_operations.extend(normalize_operation_metadata(item) for item in unique_operations(canonical_records))

        return deduplicated_operations

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

        print("Processing complete. Deduplicating extracted operations...", flush=True)
        deduplicated_operations = self.deduplicate_operations(extracted_operations)
        print(f"  → Reduced to {len(deduplicated_operations)} operation(s) after deduplication", flush=True)

        print("Filtering NF operations...", flush=True)
        nf_operations = filter_nf_operations(deduplicated_operations)
        print(f"  → Found {len(nf_operations)} NF operation(s) out of {len(deduplicated_operations)} deduplicated operation(s)", flush=True)

        print("Expanding dependencies (computing transitive closure)...", flush=True)
        dependency_processor = DependencyProcessor(nf_operations)
        expanded_operations = dependency_processor.expand_dependencies()
        ops_with_deps = sum(1 for op in expanded_operations if "DependsOn" in op and op["DependsOn"])
        print(f"  → {ops_with_deps} operation(s) have dependencies", flush=True)

        print(f"Saving to {self.output_file}...", flush=True)
        self.save_operations_metadata(expanded_operations)

        print(f"\n[✓] Extracted {len(extracted_operations)} operation(s) total")
        print(f"[✓] Deduplicated to {len(deduplicated_operations)} operation(s)")
        print(f"[✓] Filtered to {len(nf_operations)} NF operation(s)")
        print(f"[✓] Expanded dependencies for {ops_with_deps} operation(s)", flush=True)
        print(f"[✓] Saved to {self.output_file.name}", flush=True)


def main() -> None:
    OperationMetadataAgent().run()


if __name__ == "__main__":
    main()
