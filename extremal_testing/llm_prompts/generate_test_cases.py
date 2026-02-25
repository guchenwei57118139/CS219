"""
Generate test cases for operations using LLM to create invalid test cases that violate constraints.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import sys
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from llm_prompts.llm import GPT


@dataclass
class OperationConstraint:
    """Represents a single constraint for an operation."""
    constraint_text: str


@dataclass
class OperationInfo:
    """Represents an operation with its schema and constraints."""
    operation: str
    path: str
    method: str
    input_schema: Dict[str, Any]
    constraints: List[str]
    depends_on: List[str]


@dataclass
class TestCase:
    """Represents a single test case."""
    name: str
    description: str
    driving_state: Optional[Dict[str, Any]] = None
    request: Dict[str, Any] = field(default_factory=dict)
    violated_constraints: List[str] = field(default_factory=list)


@dataclass
class TestFormat:
    """Represents the structure that test cases must follow."""
    test_case_structure: Dict[str, Any]


SYSTEM_PROMPT_TEST_GENERATION = """
You are an expert in API testing and constraint validation. Your task is to generate a single invalid test case that violates a specific constraint for an API operation.

CRITICAL REQUIREMENTS:
1. Generate exactly one test case that violates the provided constraint
2. Include ONLY the fields specified in test_format.json: name, driving_state (if needed), request, violated_constraints
3. Do NOT include: description, notes, operation field in driving_state, unnecessary headers, query_parameters (unless required for GET)
4. For driving_state: include ONLY resource_url, method, headers.Content-Type, and request_body (if needed)
5. For request: include ONLY resource_url, method, headers.Content-Type, and request_body (if needed)
6. If an operation has dependencies (depends_on), include a valid "driving_state" request that sets up the required state
7. The driving_state request should be a valid request that would succeed
8. The main request in the test case should be invalid and violate the specified constraint
9. The target NRF type should always be "NRF"

Return your response as a valid JSON object (not an array) representing a single test case. Do not include markdown code blocks or additional text - return only valid JSON.
"""


class TestCaseGenerator:
    """Main class for generating test cases using LLM."""
    
    def __init__(self, operation_schemas_file: Path, test_format_file: Path, output_dir: Path):
        """Initialize with paths to input files and output directory."""
        self.operation_schemas_file = operation_schemas_file
        self.test_format_file = test_format_file
        self.output_dir = output_dir
        self.llm_client: Optional[GPT] = None
        self.test_format: Optional[TestFormat] = None
        self.operations: List[OperationInfo] = []
    
    def load_test_format(self) -> TestFormat:
        """Load the test format structure from JSON file."""
        with open(self.test_format_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return TestFormat(test_case_structure=data)
    
    def load_operations(self) -> List[OperationInfo]:
        """Load operations with their schemas and constraints from JSON file."""
        with open(self.operation_schemas_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        operations = []
        for op_data in data:
            operation = OperationInfo(
                operation=op_data.get('operation', ''),
                path=op_data.get('path', ''),
                method=op_data.get('method', ''),
                input_schema=op_data.get('input_schema', {}),
                constraints=op_data.get('constraints', []),
                depends_on=op_data.get('depends_on', [])
            )
            operations.append(operation)
        
        return operations
    
    def initialize_llm(self) -> None:
        """Initialize the LLM client."""
        self.llm_client = GPT(
            system_prompt=SYSTEM_PROMPT_TEST_GENERATION,
            max_retries=3,
            retry_delay_seconds=2.0,
        )
    
    def create_test_generation_prompt(self, operation: OperationInfo, constraint: str) -> str:
        """Create a prompt for the LLM to generate a test case for an operation that violates a specific constraint."""
        test_format_json = json.dumps(self.test_format.test_case_structure, indent=2)
        depends_on_text = ", ".join(operation.depends_on) if operation.depends_on else "None"
        
        prompt = f"""Generate a single invalid test case for the following operation that violates the specified constraint.

Operation: {operation.operation}
Path: {operation.path}
Method: {operation.method}
Dependencies (operations that must be executed first): {depends_on_text}

Input Schema:
{json.dumps(operation.input_schema, indent=2)}

Constraint to violate:
{constraint}

Test Case Format Structure:
{test_format_json}

CRITICAL INSTRUCTIONS:
1. Include ONLY these fields: name, driving_state (if dependencies exist), request, violated_constraints
2. Do NOT include: description, notes, operation field, unnecessary headers, query_parameters
3. For driving_state: ONLY resource_url, method, headers with Content-Type, request_body (if needed)
4. For request: ONLY resource_url, method, headers with Content-Type, request_body (if needed)
5. The test case must clearly and specifically violate the constraint
6. If dependencies exist ({depends_on_text}), include a valid "driving_state" request that sets up the required state
7. The driving_state request should be a valid request that would succeed
8. The main request in the test case should be invalid and violate the constraint
9. The target NRF type should always be "NRF"

Return your response as a valid JSON object (not an array) representing a single test case. Do not include markdown code blocks or additional text - return only valid JSON."""
        
        return prompt
    
    def parse_llm_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse the LLM response to extract a single test case as JSON."""
        cleaned_response = response_text.strip()
        
        # Remove markdown code blocks if present
        if cleaned_response.startswith('```'):
            first_newline = cleaned_response.find('\n')
            if first_newline != -1:
                cleaned_response = cleaned_response[first_newline + 1:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
        
        # Try to find JSON object in the response
        json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
        if json_match:
            cleaned_response = json_match.group(0)
        
        try:
            parsed = json.loads(cleaned_response)
            if isinstance(parsed, dict):
                return parsed
            elif isinstance(parsed, list) and len(parsed) > 0:
                # If it's an array, take the first element
                return parsed[0] if isinstance(parsed[0], dict) else None
            else:
                return None
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse LLM response as JSON: {e}", flush=True)
            print(f"Response text: {cleaned_response[:500]}...", flush=True)
            return None
    
    def generate_test_cases_for_operation(self, operation: OperationInfo) -> List[Dict[str, Any]]:
        """Generate test cases for a single operation using LLM, one call per constraint."""
        if not self.llm_client:
            raise RuntimeError("LLM client not initialized. Call initialize_llm() first.")
        
        if not operation.constraints:
            print(f"  → No constraints found for {operation.operation}, skipping", flush=True)
            return []
        
        total_constraints = len(operation.constraints)
        print(f"  → Generating test cases for {total_constraints} constraint(s) (one call per constraint)...", flush=True)
        
        all_test_cases = []
        
        # Process each constraint individually
        for constraint_idx, constraint in enumerate(operation.constraints, 1):
            print(f"  → Processing constraint {constraint_idx}/{total_constraints}...", flush=True)
            
            # Create prompt for this single constraint
            prompt = self.create_test_generation_prompt(operation, constraint)
            
            # Call LLM
            try:
                response_text = self.llm_client.ask_llm(prompt, use_history=False)
            except Exception as e:
                print(f"  → Error calling LLM for constraint {constraint_idx}: {e}", flush=True)
                continue
            
            # Parse response
            test_case = self.parse_llm_response(response_text)
            if not test_case:
                print(f"  → Failed to parse test case from LLM response for constraint {constraint_idx}", flush=True)
                continue
            
            all_test_cases.append(test_case)
            print(f"  → Generated test case for constraint {constraint_idx}", flush=True)
        
        print(f"  → Total: Generated {len(all_test_cases)} test case(s) from {total_constraints} constraint(s)", flush=True)
        return all_test_cases
    
    def save_test_cases(self, operation_name: str, test_cases: List[Dict[str, Any]]) -> None:
        """Save test cases to a JSON file."""
        output_file = self.output_dir / f"{operation_name}_tests.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(test_cases, f, indent=2, ensure_ascii=False)
        
        print(f"  → Saved {len(test_cases)} test case(s) to {output_file.name}", flush=True)
    
    def generate_all_test_cases(self) -> None:
        """Generate test cases for all operations."""
        # Load test format
        print(f"[*] Loading test format from {self.test_format_file.name}...", flush=True)
        self.test_format = self.load_test_format()
        print(f"[*] Test format loaded", flush=True)
        
        # Load operations
        print(f"[*] Loading operations from {self.operation_schemas_file.name}...", flush=True)
        self.operations = self.load_operations()
        print(f"[*] Loaded {len(self.operations)} operation(s)", flush=True)
        
        # Initialize LLM
        print(f"[*] Initializing LLM client...", flush=True)
        self.initialize_llm()
        print(f"[*] LLM client initialized", flush=True)
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Filter to only NFStatusSubscribe
        filtered_operations = [op for op in self.operations if op.operation == "NFStatusSubscribe"]
        if not filtered_operations:
            print(f"[!] Error: NFStatusSubscribe operation not found", flush=True)
            return
        
        print(f"[*] Filtered to {len(filtered_operations)} operation(s) (NFStatusSubscribe only)", flush=True)
        
        # Generate test cases for each operation
        for i, operation in enumerate(filtered_operations, 1):
            print(f"\n[{i}/{len(filtered_operations)}] Processing {operation.operation}...", flush=True)
            print(f"  → Path: {operation.method} {operation.path}", flush=True)
            print(f"  → Dependencies: {', '.join(operation.depends_on) if operation.depends_on else 'None'}", flush=True)
            
            test_cases = self.generate_test_cases_for_operation(operation)
            
            if test_cases:
                self.save_test_cases(operation.operation, test_cases)
            else:
                print(f"  → No test cases generated for {operation.operation}", flush=True)
        
        print(f"\n[✓] Test case generation complete")


def main() -> None:
    """Main entry point for the script."""
    script_dir = Path(__file__).resolve().parent.parent
    operation_schemas_file = script_dir / "data" / "generated" / "operation_schemas.json"
    test_format_file = script_dir / "data" / "config" / "test_format.json"
    output_dir = script_dir / "data" / "generated"
    
    # Check if test_format.json exists, if not create a default structure
    if not test_format_file.exists():
        print(f"[*] test_format.json not found, creating default structure...", flush=True)
        default_format = {
            "name": "string - Name of the test case",
            "description": "string - Description of what constraint is being violated",
            "driving_state": {
                "operation": "string - Operation name for setup (if needed)",
                "path": "string - Path with variables",
                "method": "string - HTTP method",
                "request_body": "object - Valid request body for setup"
            },
            "request": {
                "path": "string - Path with variables filled in",
                "method": "string - HTTP method",
                "headers": "object - HTTP headers",
                "request_body": "object - Invalid request body that violates constraints"
            },
            "violated_constraints": ["array of strings - List of constraint descriptions that are violated"]
        }
        with open(test_format_file, 'w', encoding='utf-8') as f:
            json.dump(default_format, f, indent=2)
        print(f"[*] Created default test_format.json", flush=True)
    
    generator = TestCaseGenerator(operation_schemas_file, test_format_file, output_dir)
    generator.generate_all_test_cases()


if __name__ == "__main__":
    main()

