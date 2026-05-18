# BUG_REPORT.md Generation Instructions

Use this when regenerating the root-level `BUG_REPORT.md` from the current NRF test artifacts.

## Inputs

- `extremal_testing/data/test_results/*.json`
- `extremal_testing/data/confidence_scores/*.json`
- `extremal_testing/data/generated/*_tests.json`

## What To Produce

Create a concise markdown report grouped by operation. Each bug entry should include:

- A short 2 to 4 word title
- The violated constraint
- Each implementation's returned status code
- The confidence score
- The confidence explanation
- The testcase reference

## Generation Steps

1. Load the confidence-score file for each operation.
2. For each scored anomaly, read the matching test result and generated testcase.
3. Extract:
   - `test_id`
   - `test_name`
   - violated `constraint`
   - implementation returns from `test_results`
   - `confidence`
   - `comment`
4. Group entries by operation.
5. Merge repeated testcase entries only when they reflect the same underlying issue.
6. Write the report in clean markdown with short headings and compact bullets.

## Recommended Layout

```md
# BUG REPORT

## NFRegister

### Missing Addressing Fields
- Testcase: `NFRegister_tests.json#3` (`NFProfile missing addressing fields`)
- Violated constraint: `...`
- Returns: `free5gc: 201; oai: 201; open5gs: 400`
- Confidence: `9/10`
- Why: ...

### Empty plmnList
- Testcase: `NFRegister_tests.json#6` (`Invalid empty plmnList`)
- Violated constraint: `...`
- Returns: `...`
- Confidence: `...`
- Why: ...
```

## Style Rules

- Keep headings short and readable.
- Prefer plain bullets over long prose.
- Preserve testcase IDs so the source evidence is traceable.
- Do not include unrelated pipeline notes or implementation details.
- Keep the report deterministic: the same inputs should produce the same output order.

