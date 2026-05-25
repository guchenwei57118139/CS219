# Progress Printing

Workflow entrypoints and long-running scripts should print progress to standard output as they work.

## Rules

- Print when a workflow stage starts and when it writes its main output.
- For loops over operations, suites, batches, implementations, or test cases, print the current item and count when practical.
- Use `flush=True` for progress messages so output appears during long runs.
- Keep messages short, factual, and stable enough to diagnose where a run stopped.
- Do not print secrets, request credentials, or full sensitive payloads.
