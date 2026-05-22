# Extremal Testing Repository

## Directory Structure

```
extremal_testing/
├── agents/                        # OpenAI Agents SDK workflows
│   └── constraint_generation/     # Constraint extraction agents and CLI
├── data/                          # All data files organized by lifecycle
│   ├── specs/                     # Source specification documents
│   │   ├── nrf_management_api.txt # Original OpenAPI source
│   │   ├── section_5_2.txt        # Full Nnrf_NFManagement section text
│   │   ├── section_5_3.txt        # Full Nnrf_NFDiscovery section text
│   │   ├── section_6_1.txt        # Full section 6.1 text
│   │   └── section_6_2.txt        # Full section 6.2 text
│   └── generated/                 # Derived outputs
│       └── operation_constraints/  # One JSON file per operation after agent generation
├── text_parsers/                  # Deterministic text parsers
│   ├── parse_operations_descriptions.py # Split section 5 into per-operation descriptions
│   ├── parse_api_resources.py     # Parse resource-backed API sections from api_spec.pdf
│   └── render_api_spec_markdown.py # Render api_spec.pdf to a Markdown inspection file
└── implementation_testers/        # Test execution scripts
    ├── test_implementations.py    # Cross-implementation comparison runner
    └── test_free5gc.py            # Free5GC NRF tester
```

## Workflow

### 1. Parse Section Text Into Operation Descriptions
- Run `text_parsers/parse_operations_descriptions.py`
- Input: `data/specs/section_5_2.txt` and `data/specs/section_5_3.txt`
- Output: in-memory operation description records
- The parser is deterministic and does not write to `data/operation_descriptions/`

### 2. Parse PDF Resource Tables Into JSON
- Run `text_parsers/parse_api_resources.py`
- Input: `data/specs/api_spec.pdf`
- Output: `data/generated/api_resources/{Section}_{Resource}.json`
- The parser uses layout-preserving PDF extraction and writes one JSON file per resource

### 3. Render the PDF to Markdown for inspection
- Run `text_parsers/render_api_spec_markdown.py`
- Input: `data/specs/api_spec.pdf`
- Output: `data/generated/api_spec_markdown.md`
- The renderer is deterministic and preserves section structure plus readable table blocks

### 4. Generate Constraints With Agents
- Run `agents/constraint_generation/cli.py`
- Input: parsed operation descriptions from the parser module
- Output: `data/generated/operation_constraints/{Operation}.json`
- The workflow uses the OpenAI Agents SDK with one fixed per-operation extraction flow
- Each output file stores atomic testable constraints derived from `shall` and `must` statements

## Configuration

- Install `openai-agents` and `eval_type_backport` when running on Python 3.9
- Set `OPENAI_API_KEY` before running the agent workflow
- The parser itself does not require any external services

## TODO
- Add a test-generation stage that consumes `operation_constraints`
- Add a coordinator pass that merges cross-operation duplicate constraints
