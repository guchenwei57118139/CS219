"""Schema and constraint extraction agent for NRF operations."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extremal_testing.nrf_agents.models.common import OperationMetadata, OperationSchema
from extremal_testing.nrf_agents.prompts.schema import SYSTEM_PROMPT_SCHEMA_EXTRACTION, build_operation_schema_prompt
from extremal_testing.nrf_agents.workflow.sdk import run_text_agent


class OperationSchemaAgent:
    """Extract schemas and constraints for operations."""

    def __init__(
        self,
        metadata_file: Path = ROOT_DIR / "json" / "AllOpsMetaData.json",
        spec_file: Path = ROOT_DIR / "specs" / "original" / "nrf_management_api.txt",
        output_file: Path = ROOT_DIR / "json" / "operation_schemas.json",
    ):
        self.metadata_file = metadata_file
        self.spec_file = spec_file
        self.output_file = output_file
        self.spec_content: str = ""

    def load_specification(self) -> None:
        with open(self.spec_file, "r", encoding="utf-8") as f:
            self.spec_content = f.read()

    def load_operations_metadata(self) -> List[OperationMetadata]:
        with open(self.metadata_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        operations: List[OperationMetadata] = []
        for op_data in data:
            operations.append(
                OperationMetadata(
                    operation=op_data.get("Operation", ""),
                    path=op_data.get("Paths", ""),
                    method=op_data.get("Method", ""),
                    description=op_data.get("Description"),
                    depends_on=op_data.get("DependsOn", []),
                )
            )
        return operations

    def parse_llm_response(self, response_text: str) -> Optional[Dict]:
        cleaned_response = response_text.strip()
        if cleaned_response.startswith("```"):
            first_newline = cleaned_response.find("\n")
            if first_newline != -1:
                cleaned_response = cleaned_response[first_newline + 1 :]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

        json_match = re.search(r'\{.*"input_schema".*"constraints".*\}', cleaned_response, re.DOTALL)
        if json_match:
            cleaned_response = json_match.group(0)

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError as exc:
            print(f"Warning: Failed to parse LLM response as JSON: {exc}", flush=True)
            print(f"Response text: {cleaned_response[:500]}...", flush=True)
            return None

    def extract_operation_schema(self, operation: OperationMetadata) -> Optional[OperationSchema]:
        print(f"[*] Processing operation: {operation.operation} ({operation.method} {operation.path})...", flush=True)

        prompt = build_operation_schema_prompt(operation, self.spec_content)

        try:
            response_text = run_text_agent(
                agent_name="NRF Schema Agent",
                instructions=SYSTEM_PROMPT_SCHEMA_EXTRACTION,
                prompt=prompt,
                workflow_name="NRF Schema Extraction",
            )
        except Exception as exc:
            print(f"  → Error calling agent: {exc}", flush=True)
            return None

        parsed_response = self.parse_llm_response(response_text)
        if not parsed_response:
            return None

        input_schema = parsed_response.get("input_schema", {})
        constraints = parsed_response.get("constraints", [])
        if not isinstance(constraints, list):
            constraints = [str(constraints)] if constraints else []

        print(f"  → Extracted schema with {len(input_schema)} field(s) and {len(constraints)} constraint(s)", flush=True)

        return OperationSchema(
            operation=operation.operation,
            path=operation.path,
            method=operation.method,
            input_schema=input_schema,
            constraints=constraints,
            depends_on=operation.depends_on or [],
        )

    def extract_all_schemas(self) -> List[OperationSchema]:
        print(f"[*] Loading specification from {self.spec_file.name}...", flush=True)
        self.load_specification()
        print(f"[*] Specification loaded ({len(self.spec_content)} characters)", flush=True)

        print(f"[*] Loading operations from {self.metadata_file.name}...", flush=True)
        operations = self.load_operations_metadata()
        print(f"[*] Loaded {len(operations)} operation(s)", flush=True)

        results: List[OperationSchema] = []
        total_ops = len(operations)
        for i, op in enumerate(operations, 1):
            print(f"\n[{i}/{total_ops}] Processing {op.operation}...", flush=True)
            schema = self.extract_operation_schema(op)
            if schema:
                results.append(schema)
            else:
                print(f"  → Failed to extract schema for {op.operation}", flush=True)
        return results

    def save_results(self, schemas: List[OperationSchema]) -> None:
        results = []
        for schema in schemas:
            results.append(
                {
                    "operation": schema.operation,
                    "path": schema.path,
                    "method": schema.method,
                    "input_schema": schema.input_schema,
                    "constraints": schema.constraints,
                    "depends_on": schema.depends_on,
                }
            )

        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    def run(self) -> None:
        schemas = self.extract_all_schemas()
        self.save_results(schemas)
        print(f"\n[✓] Extracted schemas for {len(schemas)} operation(s)")
        print(f"[✓] Results saved to {self.output_file}")


def main() -> None:
    OperationSchemaAgent().run()


if __name__ == "__main__":
    main()
