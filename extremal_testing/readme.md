# Extremal Testing Repository

## Directory Structure

```
extremal_testing/
├── data/                          # All data files organized by lifecycle
│   ├── specs/                     # Source specification documents
│   │   ├── original/              # Original spec documents (1.docx, nrf_management_api.txt)
│   │   └── segments/              # Parsed spec segments (section_*.txt)
│   ├── config/                    # Configuration files
│   │   └── test_format.json       # Test case format template
│   ├── generated/                 # Generated data files
│   │   ├── AllOpsMetaData.json    # Operations metadata
│   │   ├── operation_schemas.json # Operation schemas and constraints
│   │   └── *_tests.json           # Generated test cases
│   └── results/                   # Test execution results
│       └── nrf_test_results_*.json
├── llm_prompts/                   # LLM-based generation scripts
│   ├── generate_operations_metadata.py  # Extract operations from spec segments
│   ├── generate_operation_schemas.py    # Generate schemas and constraints
│   └── generate_test_cases.py          # Generate test cases
├── utils/                         # Utility scripts
│   ├── parse_spec.py              # Parse spec documents into segments
│   └── postprocess_dependencies.py # Post-process dependencies
└── implementation_testers/        # Test execution scripts
    └── test_free5gc.py            # Free5GC NRF tester
```

## Workflow

### 1. Parse Specification
- Use `utils/parse_spec.py` to parse spec documents
- Input: `data/specs/original/1.docx` or `data/specs/original/nrf_management_api.txt`
- Output: `data/specs/segments/section_*.txt`

### 2. Generate Operations Metadata
- Run `llm_prompts/generate_operations_metadata.py`
- Input: `data/specs/segments/section_*.txt`
- Output: `data/generated/AllOpsMetaData.json`

### 3. Generate Operation Schemas
- Run `llm_prompts/generate_operation_schemas.py`
- Input: `data/generated/AllOpsMetaData.json`, `data/specs/original/nrf_management_api.txt`
- Output: `data/generated/operation_schemas.json`

### 4. Generate Test Cases
- Run `llm_prompts/generate_test_cases.py`
- Input: `data/generated/operation_schemas.json`, `data/config/test_format.json`
- Output: `data/generated/{Operation}_tests.json`

### 5. Run Tests
- Run `implementation_testers/test_free5gc.py data/generated/{Operation}_tests.json`
- Output: `data/results/nrf_test_results_*.json`

## Configuration

- `data/config/test_format.json`: Defines the structure for generated test cases
- LLM API keys: Configure in environment variables or `.env` file (see `llm_prompts/llm.py`)

## TODO
- Generate test cases for each operation
- Generate more cases for Register, then extract nfInstanceId from successful cases
- Regenerate more cases for Deregister/Update/Subscribe operations
