"""Generate per-operation schema JSON files from the NRF markdown spec."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from .spec_indexer import DEFAULT_SPEC_PATH, build_spec_index

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "generated" / "operation_schemas"


def _safe_filename(section_id: str, resource_name: str, method: str) -> str:
    safe_resource = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in resource_name.strip().lower())
    return f"{section_id.replace('.', '_')}_{safe_resource}_{method.lower()}.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate per-operation schema JSON files from the NRF markdown spec.")
    parser.add_argument("--spec-path", type=Path, default=DEFAULT_SPEC_PATH, help="Path to the normalized markdown spec.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory to write operation schemas.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    index = build_spec_index(args.spec_path)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in args.output_dir.glob("*.json"):
        old_file.unlink()

    for operation in index.operation_schemas:
        filename = _safe_filename(operation.section_id, operation.resource_name, operation.method)
        output_file = args.output_dir / filename
        print(f"[*] writing {output_file.name}", flush=True)
        output_file.write_text(operation.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")


if __name__ == "__main__":
    main()
