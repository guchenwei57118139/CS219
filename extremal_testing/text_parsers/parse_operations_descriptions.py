"""Parse section 5 service-operation text into per-operation description records.

This is the first step of the new section-5-only pipeline. It reads the
root-level `section_5_2.txt` and `section_5_3.txt` files in `data/specs/`
and returns one record per operation containing the raw text for that
operation.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT_DIR / "data" / "specs"

SECTION_SOURCES = [
    {
        "service": "Nnrf_NFManagement",
        "section_prefix": "5.2.2",
        "section_file": SPEC_DIR / "section_5_2.txt",
    },
    {
        "service": "Nnrf_NFDiscovery",
        "section_prefix": "5.3.2",
        "section_file": SPEC_DIR / "section_5_3.txt",
    },
]

OPERATION_NAME_NORMALIZATION = {
    "NFStatusUnSubscribe": "NFStatusUnsubscribe",
    "SCPDomainRoutingInfoUnSubscribe": "SCPDomainRoutingInfoUnsubscribe",
}

@dataclass
class OperationDescription:
    service: str
    section_id: str
    operation: str
    description: str
    source_file: str

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "section_id": self.section_id,
            "operation": self.operation,
            "description": self.description,
            "source_file": self.source_file,
        }


def load_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing section file: {path}")
    return path.read_text(encoding="utf-8")


def normalize_operation_name(name: str) -> str:
    return OPERATION_NAME_NORMALIZATION.get(name.strip(), name.strip())


def iter_operation_blocks(section_text: str, section_prefix: str) -> Iterable[tuple[str, str, List[str]]]:
    """Yield (section_id, operation_name, lines) for each top-level operation block."""
    heading_pattern = re.compile(rf"^({re.escape(section_prefix)}\.[A-Za-z0-9]+)\s+(.+?)\s*$")
    lines = section_text.splitlines()
    current_section_id = None
    current_operation = None
    current_lines: List[str] = []

    for line in lines:
        match = heading_pattern.match(line)
        if match:
            section_id = match.group(1)
            operation_name = normalize_operation_name(match.group(2))

            # Skip the introduction block; only the actual operation clauses matter.
            if operation_name.lower() == "introduction":
                if current_section_id is not None:
                    current_lines.append(line)
                continue

            if current_section_id is not None:
                yield current_section_id, current_operation, current_lines

            current_section_id = section_id
            current_operation = operation_name
            current_lines = [line]
            continue

        if current_section_id is not None:
            current_lines.append(line)

    if current_section_id is not None:
        yield current_section_id, current_operation, current_lines


def parse_section_file(service: str, section_prefix: str, section_file: Path) -> List[OperationDescription]:
    section_text = load_text(section_file)
    operations: List[OperationDescription] = []

    for section_id, operation_name, lines in iter_operation_blocks(section_text, section_prefix):
        description = "\n".join(lines).strip()
        if not description:
            continue
        operations.append(
            OperationDescription(
                service=service,
                section_id=section_id,
                operation=operation_name,
                description=description,
                source_file=section_file.name,
            )
        )

    return operations


def parse_all_operation_descriptions() -> List[OperationDescription]:
    operations: List[OperationDescription] = []
    for source in SECTION_SOURCES:
        print(f"[*] Parsing {source['section_file'].name} for {source['service']}...", flush=True)
        operations.extend(
            parse_section_file(
                service=source["service"],
                section_prefix=source["section_prefix"],
                section_file=source["section_file"],
            )
        )
    return operations


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse section-5 operation descriptions.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the parsed operation descriptions as JSON to stdout.",
    )
    args = parser.parse_args()

    print("Starting section-5 operation description parsing...", flush=True)
    print(f"Input directory: {SPEC_DIR}", flush=True)

    operations = parse_all_operation_descriptions()
    print(f"[*] Parsed {len(operations)} operation description block(s)", flush=True)

    if args.json:
        print(json.dumps([operation.to_dict() for operation in operations], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
