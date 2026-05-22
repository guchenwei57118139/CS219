from __future__ import annotations

from pathlib import Path

from extremal_testing.text_parsers.render_api_spec_markdown import (
    convert_pdf_to_markdown,
    write_api_spec_markdown,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT_DIR / "extremal_testing" / "data" / "specs" / "api_spec.pdf"


def test_markdown_renderer_writes_stable_file(tmp_path: Path) -> None:
    output_path = tmp_path / "api_spec_markdown.md"

    first = write_api_spec_markdown(pdf_path=PDF_PATH, output_path=output_path)
    first_text = first.read_text(encoding="utf-8")

    second = write_api_spec_markdown(pdf_path=PDF_PATH, output_path=output_path)
    second_text = second.read_text(encoding="utf-8")

    assert first == output_path
    assert first_text == second_text
    assert "# API Spec" in first_text
    assert "6.1.6.2.12 Type: SmfInfo" in first_text
    assert "Table 6.1.6.2.12-1: Definition of type SmfInfo" in first_text
    assert "```text" in first_text


def test_markdown_renderer_returns_markdown_text() -> None:
    markdown = convert_pdf_to_markdown(pdf_path=PDF_PATH)
    assert markdown.startswith("# API Spec")
    assert "6.2.3.2" in markdown
