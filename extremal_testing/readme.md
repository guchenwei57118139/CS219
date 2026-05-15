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
│   ├── test_results/              # Per-operation implementation comparison results
│   │   └── *.json                 # One comparison file per operation
│   └── confidence_scores/         # LLM confidence judgments
│       └── *.json                 # One confidence file per operation
├── llm_prompts/                   # LLM-based generation scripts
│   ├── generate_operations_metadata.py  # Extract operations from spec segments
│   ├── generate_operation_schemas.py    # Generate schemas and constraints
│   ├── generate_test_cases.py          # Generate test cases
│   └── generate_confidence_scores.py    # Score status-code anomalies with an LLM
├── utils/                         # Utility scripts
│   ├── parse_spec.py              # Parse spec documents into segments
│   └── postprocess_dependencies.py # Post-process dependencies
└── implementation_testers/        # Test execution scripts
    ├── test_implementations.py    # Cross-implementation comparison runner
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
- Each suite uses `setup`, `tests`, and `cleanup` arrays
- Each step uses `method`, `path`, `headers`, and optional `body`
- Each test case adds `name` and `constraint`

### 5. Run Tests
- Run `implementation_testers/test_implementations.py data/generated/{Operation}_tests.json`
- The comparison runner executes each test case against `free5gc`, `oai`, and `open5gs`
- Output: `data/test_results/{Operation}.json`

### 6. Generate Confidence Scores
- Run `llm_prompts/generate_confidence_scores.py`
- Input: `data/test_results/{Operation}.json` and `data/generated/{Operation}_tests.json`
- Only test cases with differing returned status codes are sent to the LLM
- Anomalies are batched in groups of 5 per LLM call
- Files are written one per operation
- Output: `data/confidence_scores/{Operation}.json`

## Configuration

- `data/config/test_format.json`: Defines the structure for generated test cases
- LLM API keys: Configure in environment variables or `.env` file (see `llm_prompts/llm.py`)

## TODO
- Generate test cases for each operation
- Generate more cases for Register, then extract nfInstanceId from successful cases
- Regenerate more cases for Deregister/Update/Subscribe operations
