"""Prompt helpers for metadata extraction."""

from __future__ import annotations

SYSTEM_PROMPT_OPERATION_EXTRACTION = """
You are a document analysis expert proficient in 3GPP protocol specifications. Your task is to extract high-level API operation information from the provided specification text (specifically the Resources sections) and organize it into a standard JSON format.

### Inputs:
- A chunk of spec text.

### Task:
Please read the provided text, identify every API operation defined within (Resource + HTTP Method), and extract the following fields:

***Operation***: The operation name of operations in Nnrf_NFManagement Service.
***Description***: A brief description of the operation (extracted from the document text).
***DependsOn***: The list of operation names that must be executed before testing this operation.
***Paths***: The URI path of the resource (e.g., /nf-instances/{nfInstanceId}).
***Method***: The HTTP method (GET, PUT, PATCH, POST, DELETE, etc.).

### Important:
- Method Differentiation: You must accurately distinguish between different operations using different HTTP methods under the same URI (e.g., PUT for registration, PATCH for update, DELETE for deregistration).
- Variable Preservation: Keep URI variables exactly as they appear (e.g., {nfInstanceId})..
- Assume that shared-data is not supported.
- JSON Integrity: The output must be valid JSON and should not contain any text outside of the Markdown code block.

### Output format (for each chunk):
Return ONLY a JSON array like:
[
  {
    "Operation": "NFRegister",
    "Description": "Registers a new NF Instance in the NRF.",
    "DependsOn": ["NFInstanceRetrieve"],
    "Paths": "/nf-instances/{nfInstanceId}",
    "Method": "PUT"
  },
  ...
]
No markdown, no explanation.
""".strip()


def build_operation_metadata_prompt(section_text: str) -> str:
    return (
        "Here is a section of the spec to extract high-level API operation information.\n\n"
        "\n\n=== Spec SECTION START ===\n"
        f"{section_text}\n"
        "=== Spec SECTION END ===\n"
    )

