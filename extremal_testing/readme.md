# Extremal Testing Repository

## Directory Structure

```
extremal_testing/
├── data/                          # All data files organized by lifecycle
│   ├── specs/                     # Source specification documents
│   │   └── segments/              # Parsed section text used as parser input
│   │       ├── section_5_2.txt    # Full Nnrf_NFManagement section text
│   │       └── section_5_3.txt    # Full Nnrf_NFDiscovery section text
│   └── generated/                 # Derived parser output
│       └── operation_descriptions.json
├── text_parsers/                  # Deterministic text parsers
│   └── parse_model_descriptions.py # Split section 5 into per-operation descriptions
└── implementation_testers/        # Test execution scripts
    ├── test_implementations.py    # Cross-implementation comparison runner
    └── test_free5gc.py            # Free5GC NRF tester
```

## Workflow

### 1. Parse Section Text Into Operation Descriptions
- Run `text_parsers/parse_model_descriptions.py`
- Input: `data/specs/segments/section_5_2.txt` and `data/specs/segments/section_5_3.txt`
- Output: `data/generated/operation_descriptions.json`
- Each record stores the full raw description block for one operation
- The parser is deterministic and does not call an LLM

### 2. Downstream Processing
- Later stages can consume `operation_descriptions.json` and deterministically extract `shall` statements, constraints, and tests
- Old LLM-driven metadata and schema generation paths are no longer part of the active workflow

## Configuration

- LLM API keys are only needed for older legacy scripts
- The new section-5 parser does not require any external services

## TODO
- Add deterministic extraction of `shall` statements from each operation description
- Build a new test generation stage from the parsed operation descriptions
