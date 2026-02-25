"""
Extract high-level API operation information from specification sections using LLM.
Generates AllOpsMetaData.json with deduplicated operations.
"""
from pathlib import Path
import sys
import json
import re
from typing import List, Dict, Set, Tuple, Optional

# Force unbuffered output for immediate printing
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# Add parent directory to path for imports
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from llm_prompts.llm import GPT
from utils.postprocess_dependencies import DependencyProcessor

# =========== Constants ===========

OUTPUT_FORMAT_PATH = Path(__file__).resolve().parent.parent / "data" / "generated" / "AllOpsMetaData.json"
SPEC_SEGMENT_DIR = Path(__file__).resolve().parent.parent / "data" / "specs" / "segments"

SYSTEM_PROMPT_OPERATION_EXTRACTION = """
You are a document analysis expert proficient in 3GPP protocol specifications. Your task is to extract high-level API operation information from the provided specification text (specifically the Resources sections) and organize it into a standard JSON format.

### Inputs:
- A chunk of spec text.

### Task:
Please read the provided text, identify every API operation defined within (Resource + HTTP Method), and extract the following fields:

***Operation***: The operation name of operations in Nnrf_NFManagement Service.
***Description***: A brief description of the operation (extracted from the document text).
***DependsOn***: The list of operation names that must be executed before testing this operation.
***Paths***: The URI path of the resource (e.g., /nf-instances/{nfInstanceId}).
***Method***: The HTTP method (GET, PUT, PATCH, POST, DELETE, etc.).

### Important:
- Method Differentiation: You must accurately distinguish between different operations using different HTTP methods under the same URI (e.g., PUT for registration, PATCH for update, DELETE for deregistration).
- Variable Preservation: Keep URI variables exactly as they appear (e.g., {nfInstanceId})..
- Assume that shared-data is not supported.
- JSON Integrity: The output must be valid JSON and should not contain any text outside of the Markdown code block.

### Output format (for each chunk):
Return ONLY a JSON array like:
[
  {
    "Operation": "NFRegister",
    "Description": "Registers a new NF Instance in the NRF.",
    "DependsOn": ["NFInstanceRetrieve"],
    "Paths": "/nf-instances/{nfInstanceId}",
    "Method": "PUT"
  },
  ...
]
No markdown, no explanation.
"""

# =========== Type Definitions ===========

OperationMetadata = Dict[str, str]  # {"Operation": str, "Description": str, "DependsOn": str (optional), "Paths": str, "Method": str}

# =========== JSON Parsing Utilities ===========

def parse_json_from_llm_response(llm_response_text: str) -> Optional[List]:
    """Parse JSON array from LLM response, attempting to extract JSON even if wrapped in text."""
    try:
        return json.loads(llm_response_text)
    except json.JSONDecodeError:
        json_start_index = llm_response_text.find("[")
        json_end_index = llm_response_text.rfind("]")
        
        if json_start_index != -1 and json_end_index != -1 and json_end_index > json_start_index:
            try:
                return json.loads(llm_response_text[json_start_index:json_end_index + 1])
            except json.JSONDecodeError:
                print("Could not parse JSON from section. Skipping this section.", flush=True)
                return None
        
        print("No JSON array found in model output for this section. Skipping.", flush=True)
        return None


def validate_operation_metadata(operation_dict: Dict) -> bool:
    """Validate that a dictionary contains all required operation metadata fields."""
    return (
        isinstance(operation_dict, dict)
        and "Operation" in operation_dict and isinstance(operation_dict["Operation"], str)
        and "Description" in operation_dict and isinstance(operation_dict["Description"], str)
        and "Paths" in operation_dict and isinstance(operation_dict["Paths"], str)
        and "Method" in operation_dict and isinstance(operation_dict["Method"], str)
        # DependsOn is optional
    )


def normalize_operation_metadata(operation_dict: Dict[str, str]) -> OperationMetadata:
    """Normalize operation metadata by stripping whitespace from all string fields."""
    normalized = {
        "Operation": operation_dict["Operation"].strip(),
        "Description": operation_dict["Description"].strip(),
        "Paths": operation_dict["Paths"].strip(),
        "Method": operation_dict["Method"].strip()
    }
    # Add DependsOn if present (handle both string and list types)
    if "DependsOn" in operation_dict and operation_dict["DependsOn"]:
        depends_on_value = operation_dict["DependsOn"]
        if isinstance(depends_on_value, list):
            # If it's a list, join with comma or take first element
            normalized["DependsOn"] = ", ".join(str(item).strip() for item in depends_on_value if item)
        elif isinstance(depends_on_value, str):
            normalized["DependsOn"] = depends_on_value.strip()
        else:
            normalized["DependsOn"] = str(depends_on_value).strip()
    return normalized

# =========== Deduplication Functions ===========

def filter_nf_operations(operations: List[OperationMetadata]) -> List[OperationMetadata]:
    """Filter operations to only keep those where Operation starts with 'NF' and Method is not 'PATCH'."""
    return [
        op for op in operations 
        if op.get("Operation", "").startswith("NF") 
        and op.get("Method", "").upper() != "PATCH"
    ]


def deduplicate_operations(operations: List[OperationMetadata]) -> List[OperationMetadata]:
    """Remove duplicate operations based on operation name, keeping the most recent occurrence."""
    operation_name_to_operation: Dict[str, OperationMetadata] = {}
    
    for operation in operations:
        operation_name = operation["Operation"].strip().lower()
        # Keep the most recent one (overwrite previous occurrences)
        operation_name_to_operation[operation_name] = operation
    
    return list(operation_name_to_operation.values())

# =========== LLM Extraction Functions ===========

def extract_operations_from_section(llm_client: GPT, section_text: str) -> List[OperationMetadata]:
    """Extract high-level API operation information from a specification section using LLM."""
    prompt = (
        "Here is a section of the spec to extract high-level API operation information.\n\n"
        "\n\n=== Spec SECTION START ===\n"
        f"{section_text}\n"
        "=== Spec SECTION END ===\n"
    )
    
    llm_response = llm_client.ask_llm(prompt)
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

# =========== File Processing Functions ===========

def find_spec_segment_files(spec_segment_directory: Path) -> List[Path]:
    """Find all section files matching section 5.2 pattern (section_5_2*.txt) in the spec segment directory."""
    section_file_pattern = re.compile(r"^section_5_2.*\.txt$")
    matching_files: List[Path] = []
    
    for file_path in spec_segment_directory.iterdir():
        if file_path.is_file() and section_file_pattern.match(file_path.name):
            matching_files.append(file_path)
    
    matching_files.sort(key=lambda path: path.name)
    return matching_files


def process_spec_segment_files(
    llm_client: GPT,
    spec_segment_directory: Path
) -> List[OperationMetadata]:
    """Process all spec segment files and extract operations from each."""
    all_extracted_operations: List[OperationMetadata] = []
    spec_segment_files = find_spec_segment_files(spec_segment_directory)
    
    print(f"Found {len(spec_segment_files)} section file(s) to process", flush=True)
    
    for section_file_path in spec_segment_files:
        print(f"[*] Processing section file: {section_file_path.name}...", flush=True)
        
        with section_file_path.open("r", encoding="utf-8") as file:
            section_text = file.read()
        
        print(f"  → Sending to LLM...", flush=True)
        extracted_operations = extract_operations_from_section(llm_client, section_text)
        print(f"  → Extracted {len(extracted_operations)} operation(s) from this section", flush=True)
        
        if extracted_operations:
            all_extracted_operations.extend(extracted_operations)
    
    return all_extracted_operations


def save_operations_metadata(
    operations: List[OperationMetadata],
    output_file_path: Path
) -> None:
    """Save extracted operations metadata to a JSON file."""
    output_file_path.write_text(
        json.dumps(operations, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

# =========== Main Function ===========

def main() -> None:
    """Generate input format JSON by extracting high-level API operation info from spec sections using LLM."""
    print("Starting operations metadata extraction...", flush=True)
    print(f"Looking for section files in: {SPEC_SEGMENT_DIR}", flush=True)
    
    llm_client = GPT(
        system_prompt=SYSTEM_PROMPT_OPERATION_EXTRACTION,
        max_retries=3,
        retry_delay_seconds=2.0,
    )
    
    print("LLM client initialized. Processing section files...", flush=True)
    extracted_operations = process_spec_segment_files(llm_client, SPEC_SEGMENT_DIR)
    
    print(f"Processing complete. Filtering NF operations...", flush=True)
    nf_operations = filter_nf_operations(extracted_operations)
    print(f"  → Found {len(nf_operations)} NF operation(s) out of {len(extracted_operations)} total", flush=True)
    
    # Skip deduplication - use filtered operations directly
    print(f"Expanding dependencies (computing transitive closure)...", flush=True)
    dependency_processor = DependencyProcessor(nf_operations)
    expanded_operations = dependency_processor.expand_dependencies()
    ops_with_deps = sum(1 for op in expanded_operations if "DependsOn" in op and op["DependsOn"])
    print(f"  → {ops_with_deps} operation(s) have dependencies", flush=True)
    
    print(f"Saving to {OUTPUT_FORMAT_PATH}...", flush=True)
    save_operations_metadata(expanded_operations, OUTPUT_FORMAT_PATH)
    
    print(f"\n[✓] Extracted {len(extracted_operations)} operation(s) total")
    print(f"[✓] Filtered to {len(nf_operations)} NF operation(s)")
    print(f"[✓] Expanded dependencies for {ops_with_deps} operation(s)", flush=True)
    print(f"[✓] Saved to {OUTPUT_FORMAT_PATH.name}", flush=True)


if __name__ == "__main__":
    main()

