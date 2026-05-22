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
├── nrf_agents/                    # OpenAI Agents SDK-based workflow implementation
│   ├── prompts/                   # Prompt builders and system prompts
│   ├── models/                    # Shared dataclasses and workflow models
│   └── workflow/                  # Metadata/schema/test/confidence agents and orchestrator
├── utils/                         # Utility scripts
│   └── parse_spec.py              # Parse spec documents into segments
└── implementation_testers/        # Test execution scripts
    ├── test_implementations.py    # Cross-implementation comparison runner
    └── test_free5gc.py            # Free5GC NRF tester
```

## Workflow

The main end-to-end entrypoint is `nrf_agents/workflow/orchestrator.py`. It runs the full pipeline in order and handles all stages below.

- End-to-end run: `python3 extremal_testing/nrf_agents/workflow/orchestrator.py`

### 1. Generate Operations Metadata
- Run `nrf_agents/workflow/metadata_agent.py`
- Input: `data/specs/segments/section_*.txt`
- Output: `data/generated/AllOpsMetaData.json`
- Dependency expansion happens inside the metadata agent before saving

### 2. Generate Operation Schemas
- Run `nrf_agents/workflow/schema_agent.py`
- Input: `data/generated/AllOpsMetaData.json`, `data/specs/original/nrf_management_api.txt`
- Output: `data/generated/operation_schemas.json`

### 3. Generate Test Cases
- Run `nrf_agents/workflow/testcase_agent.py`
- Input: `data/generated/operation_schemas.json`, `data/config/test_format.json`
- Output: `data/generated/{Operation}_tests.json`
- Each suite uses `setup`, `tests`, and `cleanup` arrays
- Each step uses `method`, `path`, `headers`, and optional `body`
- Each test case adds `name` and `constraint`

### 4. Run Tests
- The orchestrator runs `implementation_testers/test_implementations.py` logic directly over all generated suites
- The comparison runner executes each test case against `free5gc`, `oai`, and `open5gs`
- Output: `data/test_results/{Operation}.json`

### 5. Generate Confidence Scores
- Run `nrf_agents/workflow/confidence_agent.py`
- Input: `data/test_results/{Operation}.json` and `data/generated/{Operation}_tests.json`
- Only test cases with differing returned status codes are sent to the LLM
- Anomalies are batched in groups of 5 per LLM call
- Files are written one per operation
- Output: `data/confidence_scores/{Operation}.json`

## Configuration

- `data/config/test_format.json`: Defines the structure for generated test cases
- OpenAI API key: Configure `OPENAI_API_KEY` in the environment or `.env`

## TODO
- Generate test cases for each operation
- Generate more cases for Register, then extract nfInstanceId from successful cases
- Regenerate more cases for Deregister/Update/Subscribe operations
