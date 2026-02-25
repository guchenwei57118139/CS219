"""
Extract JSON input schemas and constraints for operations from the NRF Management API specification using LLM.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import sys
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from llm_prompts.llm import GPT


@dataclass
class OperationMetadata:
    """Metadata for a single operation from AllOpsMetaData.json."""
    operation: str
    path: str
    method: str
    description: Optional[str] = None
    depends_on: Optional[List[str]] = field(default_factory=list)


@dataclass
class OperationSchema:
    """Extracted schema and constraints for an operation."""
    operation: str
    path: str
    method: str
    input_schema: Dict
    constraints: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)


SYSTEM_PROMPT_SCHEMA_EXTRACTION = """
You are an expert in OpenAPI specifications and API schema extraction. Your task is to analyze the provided OpenAPI specification and extract the input schema and constraints for a specific operation.

Given an operation (identified by its path and HTTP method), you must:
1. Locate the operation in the OpenAPI specification
2. Extract the request body schema (if present) - this includes the structure, types, and references
3. Extract all validity constraints from the specification text related to this operation

Constraints should be written as natural-language sentences that describe validation rules, requirements, or limitations found in the specification text. Do not invent constraints that are not explicitly stated or implied in the specification.

Return your response as a valid JSON object with the following structure:
{
  "input_schema": {
    // JSON schema structure representing the request body
    // Include properties, types, required fields, references, etc.
    // If there is no request body, this should be an empty object {}
  },
  "constraints": [
    // Array of natural-language sentences describing validity constraints
    // Each constraint should be a complete sentence
    // Only include constraints that are explicitly stated in the specification
  ]
}

Important:
- The input_schema should represent the complete request body structure
- Include schema references ($ref) as they appear in the specification
- Include parameter information (query, path, header parameters) if relevant
- Constraints must be derived directly from the specification text
- Do not include constraints that are not supported by the specification
- Return only valid JSON, no markdown code blocks or additional text
"""


class OperationSchemaExtractor:
    """Main class for extracting operation schemas and constraints using LLM."""
    
    def __init__(self, metadata_file: Path, spec_file: Path):
        """Initialize with paths to metadata and specification files."""
        self.metadata_file = metadata_file
        self.spec_file = spec_file
        self.spec_content: str = ""
        self.llm_client: Optional[GPT] = None
    
    def load_specification(self) -> None:
        """Load the specification file content into memory."""
        with open(self.spec_file, 'r', encoding='utf-8') as f:
            self.spec_content = f.read()
    
    def initialize_llm(self) -> None:
        """Initialize the LLM client."""
        self.llm_client = GPT(
            system_prompt=SYSTEM_PROMPT_SCHEMA_EXTRACTION,
            max_retries=3,
            retry_delay_seconds=2.0,
        )
    
    def load_operations_metadata(self) -> List[OperationMetadata]:
        """Load operation metadata from JSON file."""
        with open(self.metadata_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        operations = []
        for op_data in data:
            operation = OperationMetadata(
                operation=op_data.get('Operation', ''),
                path=op_data.get('Paths', ''),
                method=op_data.get('Method', ''),
                description=op_data.get('Description'),
                depends_on=op_data.get('DependsOn', [])
            )
            operations.append(operation)
        
        return operations
    
    def create_operation_prompt(self, operation: OperationMetadata) -> str:
        """Create a prompt for the LLM to extract schema and constraints for an operation."""
        prompt = f"""Analyze the following OpenAPI specification and extract the input schema and constraints for this operation:

Operation Name: {operation.operation}
Path: {operation.path}
HTTP Method: {operation.method}
Description: {operation.description or 'N/A'}

OpenAPI Specification:
{self.spec_content}

Please extract:
1. The input_schema (request body structure, parameters, etc.) for the operation at path "{operation.path}" with method "{operation.method}"
2. All validity constraints from the specification text related to this operation

Return your response as a valid JSON object with "input_schema" and "constraints" keys."""
        
        return prompt
    
    def parse_llm_response(self, response_text: str) -> Optional[Dict]:
        """Parse the LLM response to extract JSON."""
        # Try to extract JSON from the response
        # Remove markdown code blocks if present
        cleaned_response = response_text.strip()
        
        # Remove markdown code blocks
        if cleaned_response.startswith('```'):
            # Find the first newline after ```
            first_newline = cleaned_response.find('\n')
            if first_newline != -1:
                cleaned_response = cleaned_response[first_newline + 1:]
            # Remove trailing ```
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
        
        # Try to find JSON object in the response
        json_match = re.search(r'\{.*"input_schema".*"constraints".*\}', cleaned_response, re.DOTALL)
        if json_match:
            cleaned_response = json_match.group(0)
        
        try:
            parsed = json.loads(cleaned_response)
            return parsed
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse LLM response as JSON: {e}", flush=True)
            print(f"Response text: {cleaned_response[:500]}...", flush=True)
            return None
    
    def extract_operation_schema(self, operation: OperationMetadata) -> Optional[OperationSchema]:
        """Extract schema and constraints for a single operation using LLM."""
        if not self.llm_client:
            raise RuntimeError("LLM client not initialized. Call initialize_llm() first.")
        
        print(f"[*] Processing operation: {operation.operation} ({operation.method} {operation.path})...", flush=True)
        
        # Create prompt
        prompt = self.create_operation_prompt(operation)
        
        # Call LLM
        try:
            response_text = self.llm_client.ask_llm(prompt, use_history=False)
        except Exception as e:
            print(f"  → Error calling LLM: {e}", flush=True)
            return None
        
        # Parse response
        parsed_response = self.parse_llm_response(response_text)
        if not parsed_response:
            return None
        
        # Extract input_schema and constraints
        input_schema = parsed_response.get('input_schema', {})
        constraints = parsed_response.get('constraints', [])
        
        # Ensure constraints is a list
        if not isinstance(constraints, list):
            constraints = [str(constraints)] if constraints else []
        
        print(f"  → Extracted schema with {len(input_schema)} field(s) and {len(constraints)} constraint(s)", flush=True)
        
        return OperationSchema(
            operation=operation.operation,
            path=operation.path,
            method=operation.method,
            input_schema=input_schema,
            constraints=constraints,
            depends_on=operation.depends_on or []
        )
    
    def extract_all_schemas(self) -> List[OperationSchema]:
        """Extract schemas and constraints for all operations."""
        # Load specification
        print(f"[*] Loading specification from {self.spec_file.name}...", flush=True)
        self.load_specification()
        print(f"[*] Specification loaded ({len(self.spec_content)} characters)", flush=True)
        
        # Initialize LLM
        print(f"[*] Initializing LLM client...", flush=True)
        self.initialize_llm()
        print(f"[*] LLM client initialized", flush=True)
        
        # Load operations
        print(f"[*] Loading operations from {self.metadata_file.name}...", flush=True)
        operations = self.load_operations_metadata()
        print(f"[*] Loaded {len(operations)} operation(s)", flush=True)
        
        # Extract schema for each operation
        results = []
        total_ops = len(operations)
        for i, op in enumerate(operations, 1):
            print(f"\n[{i}/{total_ops}] Processing {op.operation}...", flush=True)
            schema = self.extract_operation_schema(op)
            if schema:
                results.append(schema)
            else:
                print(f"  → Failed to extract schema for {op.operation}", flush=True)
        
        return results
    
    def save_results(self, schemas: List[OperationSchema], output_file: Path) -> None:
        """Save extracted schemas to a JSON file."""
        results = []
        for schema in schemas:
            result = {
                'operation': schema.operation,
                'path': schema.path,
                'method': schema.method,
                'input_schema': schema.input_schema,
                'constraints': schema.constraints,
                'depends_on': schema.depends_on
            }
            results.append(result)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)


def main() -> None:
    """Main entry point for the script."""
    script_dir = Path(__file__).resolve().parent.parent
    metadata_file = script_dir / "data" / "generated" / "AllOpsMetaData.json"
    spec_file = script_dir / "data" / "specs" / "original" / "nrf_management_api.txt"
    output_file = script_dir / "data" / "generated" / "operation_schemas.json"
    
    extractor = OperationSchemaExtractor(metadata_file, spec_file)
    schemas = extractor.extract_all_schemas()
    extractor.save_results(schemas, output_file)
    
    print(f"\n[✓] Extracted schemas for {len(schemas)} operation(s)")
    print(f"[✓] Results saved to {output_file}")


if __name__ == "__main__":
    main()
