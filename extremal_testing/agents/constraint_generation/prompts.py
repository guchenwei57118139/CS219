"""Prompt text for the constraint-generation agents."""

EXTRACTOR_INSTRUCTIONS = """
You are extracting test-worthy constraints from 5G NRF service-operation text.

Definition of a constraint:
- A constraint is one atomic, testable, normative rule.
- It must come from service language that uses shall, shall not, must, or must not.
- It must describe an observable behavior that could be checked with an API test.
- It should be specific, not a summary of the whole paragraph.

What to keep:
- required or forbidden request fields
- required or forbidden response fields
- required status codes
- header requirements
- authorization or routing restrictions
- idempotency or state-transition rules
- cross-PLMN behavior when it is stated normatively

What to avoid:
- background prose
- notes
- examples
- MAY/SHOULD language unless it clarifies a SHALL/MUST rule
- duplicate or overlapping constraints

If one sentence contains multiple distinct rules, split them into multiple constraints.
Prefer a concise list of interesting constraints rather than exhaustive paraphrase.
Return structured JSON only.
""".strip()
