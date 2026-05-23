# Extremal Testing Repository

## Directory Structure

```
extremal_testing/
├── specs/                         # Source specification documents
│   ├── original/                  # Original spec documents (1.docx, nrf_management_api.txt)
│   └── segments/                  # Parsed spec segments (section_*.txt)
├── json/                          # Generated JSON artifacts and configuration
│   ├── config/                    # Configuration files
│   │   └── test_format.json       # Test case format template
│   ├── AllOpsMetaData.json        # Static operation metadata input
│   ├── constraints/               # Per-operation resolved input schemas and constraints
│   │   └── <Operation>.json       # One file per operation
│   ├── testcases/                 # Generated test cases
│   │   └── *_tests.json           # One suite file per operation
│   ├── test_results/              # Per-operation implementation comparison results
│   │   └── *.json                 # One comparison file per operation
├── reports/                       # Markdown bug reports
│   └── *.md                       # One bug report per operation
├── nrf_agents/                    # OpenAI Agents SDK-based workflow implementation
│   ├── prompts/                   # Prompt builders and system prompts
│   ├── models/                    # Shared dataclasses and workflow models
│   └── workflow/                  # Constraint/test/bug-report agents and orchestrator
└── implementation_testers/        # Test execution scripts
    ├── implementation_tester.py   # Cross-implementation tester
    └── test_free5gc.py            # Free5GC NRF tester
    
```

## Workflow

The main end-to-end entrypoint is `nrf_agents/workflow/orchestrator.py`. It runs the full pipeline in order and handles all stages below.

- End-to-end run: `python3 extremal_testing/nrf_agents/workflow/orchestrator.py`

### 1. Constraint Generation
- Run `nrf_agents/workflow/constraint_agent.py`
- Input: `json/AllOpsMetaData.json`, `specs/original/TS29510_Nnrf_NFManagement.yaml`, `specs/original/TS29571_CommonData.yaml`
- Output: `json/constraints/{Operation}.json`

### 2. Test Generation
- Run `nrf_agents/workflow/test_agent.py`
- Input: `json/constraints/`, `json/AllOpsMetaData.json`, `json/config/test_format.json`
- Output: `json/testcases/{Operation}_tests.json`
- Each suite uses `setup`, `tests`, and `cleanup` arrays
- Each step uses `method`, `path`, `headers`, and optional `body`
- Each test case adds `name` and `constraint`

### 3. Implementation Testing
- The orchestrator runs `implementation_testers/implementation_tester.py` logic directly over all generated suites
- The implementation tester executes each test case against `free5gc`, `oai`, and `open5gs`
- Output: `json/test_results/{Operation}.json`

### 4. Bug Report Generation
- Run `nrf_agents/workflow/bug_report_agent.py`
- Input: `json/test_results/{Operation}.json` and `json/testcases/{Operation}_tests.json`
- Test cases with differing implementation behavior are sent to the LLM
- Anomalies are batched in groups of 5 per LLM call
- The bug report agent groups related anomalies and keeps only high-signal candidates
- Files are written one per operation
- Output: `reports/{Operation}.md`

## Configuration

- `json/config/test_format.json`: Defines the structure for generated test cases
- OpenAI API key: Configure `OPENAI_API_KEY` in the environment or `.env`

## TODO
- Generate test cases for each operation
- Generate more cases for Register, then extract nfInstanceId from successful cases
- Regenerate more cases for Deregister/Update/Subscribe operations
