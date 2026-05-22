"""CLI for generating per-operation constraint bundles from the markdown spec."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from ...text_parsers.spec_indexer import DEFAULT_SPEC_PATH
from .workflow import DEFAULT_OUTPUT_DIR, generate_constraints

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parents[3]


def load_environment() -> None:
    """Load repo-local environment variables before contacting the LLM."""
    load_dotenv(ROOT_DIR / ".env", override=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate constraints from the normalized NRF markdown spec.")
    parser.add_argument("--spec-path", type=Path, default=DEFAULT_SPEC_PATH, help="Path to the normalized markdown spec.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write per-operation constraint JSON files.",
    )
    parser.add_argument("--extract-model", default=None, help="Override the extractor model.")
    return parser.parse_args()


def main() -> None:
    load_environment()
    args = parse_args()
    generate_constraints(
        spec_path=args.spec_path,
        output_dir=args.output_dir,
        extract_model=args.extract_model or "gpt-5.4-mini",
    )


if __name__ == "__main__":
    main()
