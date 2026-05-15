# Overview

This repository contains an extremal-testing workflow for 5G NRF implementations. The main pipeline is:

`spec source -> parsed sections -> operation metadata -> operation schemas -> generated tests -> implementation test_results -> confidence_scores`

Agents should optimize for small, reversible changes, prefer reading code before editing, and treat generated artifacts and result outputs as derived data unless the task is explicitly about those files.

# Repository Layout

- `README.md`: minimal top-level project description if present.
- `extremal_testing/readme.md`: human-oriented workflow summary.
- `extremal_testing/utils`: spec parsing and result analysis utilities.
- `extremal_testing/llm_prompts`: LLM wrapper plus scripts that generate metadata, schemas, test cases, and confidence scores.
- `extremal_testing/implementation_testers`: implementation-specific NRF test runners for `free5gc`, `oai`, and `open5gs`.
- `extremal_testing/data/specs/original`: original spec inputs, including `1.docx` and `nrf_management_api.txt`.
- `extremal_testing/data/specs/segments`: parsed `section_*.txt` files produced by spec parsing.
- `extremal_testing/data/generated`: generated operation metadata, schemas, and `*_tests.json` files.
- `extremal_testing/data/test_results`: per-operation implementation comparison outputs.
- `extremal_testing/data/confidence_scores`: per-operation LLM confidence judgments.

# Pipeline And Entry Points

Use the existing scripts as the primary interfaces instead of hand-editing derived JSON.

- Parse the spec:
  `python extremal_testing/utils/parse_spec.py`
- Generate operation metadata:
  `python extremal_testing/llm_prompts/generate_operations_metadata.py`
- Generate operation schemas:
  `python extremal_testing/llm_prompts/generate_operation_schemas.py`
- Generate test cases:
  `python extremal_testing/llm_prompts/generate_test_cases.py`
- Generate confidence scores:
  `python extremal_testing/llm_prompts/generate_confidence_scores.py`
- Run Free5GC tests:
  `python extremal_testing/implementation_testers/test_free5gc.py extremal_testing/data/generated/<Operation>_tests.json [base_url]`
- Run OAI tests:
  `python extremal_testing/implementation_testers/test_oai.py extremal_testing/data/generated/<Operation>_tests.json [base_url]`
- Run Open5GS tests:
  `python extremal_testing/implementation_testers/test_open5gs.py extremal_testing/data/generated/<Operation>_tests.json [--resume <results.json>] [--no-auto-restart]`
- Summarize result status codes:
  `python extremal_testing/utils/summarize_results.py [results_dir] --impl {oai,free5gc} [--latest-only] [--json]`
- Compare implementations:
  `python extremal_testing/implementation_testers/test_implementations.py [data/generated/<Operation>_tests.json | data/generated/]`
- Score anomalies by confidence:
  `python extremal_testing/llm_prompts/generate_confidence_scores.py [--test-results-dir <dir>] [--generated-dir <dir>] [--output-dir <dir>] [--batch-size 5]`

There is no `pyproject.toml`, `requirements.txt`, or other dependency manifest in the repo. Infer runtime dependencies from imports before adding setup instructions or changing package usage.

# Environment And Secrets

LLM-driven scripts load configuration from environment variables and may also read a project-root `.env` file via `python-dotenv`.

- `LLM_PROVIDER=google|openai`
- `GOOGLE_API_KEY` or `GEMINI_API_KEY` for Google GenAI
- `OPENAI_API_KEY` for OpenAI
- `LLM_MODEL` to override the provider default

Do not print, copy, or commit secret values from `.env` or the shell environment. If a task needs LLM execution, verify the required provider variables exist without exposing their contents.

# Working Rules For Agents

- Inspect first. Read the relevant script before changing generated JSON or test outputs.
- Prefer editing source code under `extremal_testing/utils`, `extremal_testing/llm_prompts`, and `extremal_testing/implementation_testers`.
- Treat `extremal_testing/data/generated/*` as regenerated artifacts, not authoritative hand-maintained source.
- Treat `extremal_testing/data/test_results/*` and `extremal_testing/data/confidence_scores/*` as execution output and analysis artifacts.
- Assume the worktree may already contain unrelated generated/result changes. Do not revert them unless the user explicitly asks.
- Mention before rerunning generator scripts when the run will overwrite existing generated files.
- Prefer targeted commands over broad churn. Avoid reprocessing the whole pipeline unless the task requires it.
- Any new LLM-assisted stage or CLI entrypoint must print progress updates to standard output so tool execution is easy to track.

# Implementation Notes And Gotchas

- `generate_operations_metadata.py` intentionally scans only `section_5_2*.txt`. Do not widen the scope casually.
- LLM generation scripts are designed to overwrite files in `extremal_testing/data/generated`.
- The test runners target live local NRF services. Failures may be environment-related rather than code-related.
- `test_open5gs.py` can restart a Docker container named `nrf`. Do not trigger that path casually.
- HTTP client behavior differs by implementation:
  `test_free5gc.py` uses `requests`
  `test_oai.py` uses `httpx`
  `test_open5gs.py` uses `httpx`
- Comparison outputs now live under `extremal_testing/data/test_results/`.
- Confidence scoring outputs now live under `extremal_testing/data/confidence_scores/`.
- The confidence scorer only considers tests whose returned status codes differ across implementations.
- Batch anomalies in groups of 5 per LLM call and keep the output one JSON file per operation.

# Validation And Safe Checks

Use lightweight checks before and after changes.

- Inventory files:
  `rg --files extremal_testing`
- Find relevant entrypoints:
  `rg -n "def main|argparse|OpenAI|httpx|requests" extremal_testing -g '*.py'`
- Inspect current worktree state:
  `git status --short`
- Confirm documented directories exist:
  `find extremal_testing -maxdepth 2 -type d | sort`

If a task requires execution against live NRF implementations or LLM providers, state the dependency clearly and avoid assuming the local services or API keys are available.
