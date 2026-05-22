"""Render ``api_spec.pdf`` to a deterministic Markdown inspection file."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from extremal_testing.text_parsers.parse_api_resources import (
    SECTION_HEADING_RE,
    TABLE_TITLE_RE,
    collect_headings,
    load_pdf_text,
    normalize_whitespace,
    sanitize_lines,
)

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PDF_PATH = ROOT_DIR / "data" / "specs" / "api_spec.pdf"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "data" / "generated" / "api_spec_markdown.md"


def _heading_level(section_id: str) -> int:
    return max(1, min(len(section_id.split(".")), 6))


def _looks_table_like(block: Sequence[str]) -> bool:
    if len(block) < 2:
        return False

    aligned_lines = 0
    for line in block:
        if len(re.findall(r"\S\s{2,}\S", line)) >= 2:
            aligned_lines += 1
    return aligned_lines >= 2


def _render_block(block: Sequence[str]) -> List[str]:
    if not block:
        return []

    first = block[0].strip()
    if not first:
        return []

    if first.startswith("Table "):
        rendered = [f"### {first}"]
        body = [line.rstrip() for line in block[1:] if line.strip()]
        if body:
            rendered.append("```text")
            rendered.extend(body)
            rendered.append("```")
        return rendered

    if _looks_table_like(block):
        return ["```text", *[line.rstrip() for line in block], "```"]

    return [normalize_whitespace(" ".join(block))]


def convert_pdf_to_markdown(pdf_path: Path = DEFAULT_PDF_PATH) -> str:
    pdf_text = load_pdf_text(pdf_path)
    lines = sanitize_lines(pdf_text.splitlines())
    headings = {heading.line_index: heading for heading in collect_headings(lines)}

    output: List[str] = ["# API Spec"]
    index = 0
    while index < len(lines):
        heading = headings.get(index)
        if heading is not None:
            output.append("")
            output.append(f"{'#' * _heading_level(heading.section_id)} {heading.section_id} {heading.title}")
            index = heading.title_index + 1
            continue

        line = lines[index].rstrip()
        if not line.strip():
            index += 1
            continue

        block: List[str] = []
        while index < len(lines):
            if index in headings:
                break
            current = lines[index].rstrip()
            if not current.strip():
                break
            block.append(current)
            index += 1

        output.append("")
        output.extend(_render_block(block))

        while index < len(lines) and not lines[index].strip():
            index += 1

    output.append("")
    return "\n".join(output)


def write_api_spec_markdown(
    pdf_path: Path = DEFAULT_PDF_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    markdown = convert_pdf_to_markdown(pdf_path=pdf_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render api_spec.pdf to Markdown for inspection.")
    parser.add_argument("--pdf-path", type=Path, default=DEFAULT_PDF_PATH, help="Path to api_spec.pdf.")
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Markdown file to write.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    print("Starting Markdown rendering from PDF...", flush=True)
    print(f"[*] Input PDF: {args.pdf_path}", flush=True)
    print(f"[*] Output file: {args.output_path}", flush=True)
    output_path = write_api_spec_markdown(pdf_path=args.pdf_path, output_path=args.output_path)
    print(f"[*] Wrote {output_path}", flush=True)


if __name__ == "__main__":
    main()
