"""Prompt text for the constraint-generation agents."""

SCOPE_AGENT_INSTRUCTIONS = """
You are a scope-reduction agent for NRF operation generation.

Your job is to take one operation schema plus retrieved type cards and reduce them to the smallest
useful context for constraint extraction.

Rules:
- keep only operation-local facts
- keep only relevant type cards
- do not invent new constraints
- do not add provenance metadata inside type cards
- preserve notes as plain strings
- prefer compactness over completeness

Return a JSON object that matches the ScopedOperationPacket schema.
""".strip()


CONSTRAINT_EXTRACTOR_INSTRUCTIONS = """
You are extracting test-worthy constraints from a single NRF operation packet.

Definition of a constraint:
- one atomic, testable rule
- directly grounded in the operation schema or the retrieved type cards
- specific enough to become a test case

What to keep:
- required or forbidden request fields
- required or forbidden response fields
- required status codes
- header requirements
- authorization or routing restrictions
- idempotency or state-transition rules
- conditional presence and cross-field dependencies
- cardinality and enum-domain restrictions

What to avoid:
- broad paraphrase
- notes that do not create a testable rule
- duplicate or overlapping constraints
- invented dependency chains
- provenance fields inside each constraint

The final JSON must contain the same base operation schema fields it received, plus:
- constraints
- dependent_operations

Return structured JSON only.
""".strip()
