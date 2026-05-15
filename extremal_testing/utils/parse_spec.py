"""
Parse specification documents and extract sections into individual text files.
"""
from pathlib import Path
import re
from typing import List, Tuple, Optional

try:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# =========== Constants ===========

SPEC_DIR = Path(__file__).resolve().parent.parent / "data" / "specs" / "original"
SPEC_SEGMENT_DIR = Path(__file__).resolve().parent.parent / "data" / "specs" / "segments"

# =========== Type Definitions ===========

SectionTuple = Tuple[str, str, List[str]]  # (section_number, section_title, section_lines)

# =========== Document Parsing Functions ===========

def parse_rfc_sections(document_lines: List[str], use_spec_format: bool = False) -> List[SectionTuple]:
    """Parse document text into sections at Level 1 (X), Level 2 (X.Y), and Level 3 (X.Y.Z)."""
    sections: List[SectionTuple] = []
    
    if use_spec_format:
        section_pattern = re.compile(r"^(\s*)(\d+(?:\.\d+)*)[\t ]+(.+?)(?:[\t ]+(\d+))?\s*$")
        table_of_contents_pattern = None
    else:
        section_pattern = re.compile(r"^(\s*)(\d+(?:\.\d+)*)\.\s+(.+)$")
        table_of_contents_pattern = re.compile(r"\.\s*\.\s*\.|\.\s+\d+\s*$")
    
    current_section_number: Optional[str] = None
    current_section_title: Optional[str] = None
    current_section_lines: List[str] = []
    
    for line in document_lines:
        match = section_pattern.match(line)
        if match:
            section_number = match.group(2)
            section_title = match.group(3).strip()
            
            if not use_spec_format and table_of_contents_pattern is not None:
                if table_of_contents_pattern.search(section_title):
                    continue
            
            section_number_parts = section_number.split(".")
            if len(section_number_parts) <= 3:
                if current_section_number is not None:
                    sections.append((current_section_number, current_section_title, current_section_lines))
                current_section_number = section_number
                current_section_title = section_title
                current_section_lines = [line]
            else:
                if current_section_number is not None:
                    current_section_lines.append(line)
                else:
                    current_section_number = section_number
                    current_section_title = section_title
                    current_section_lines = [line]
        else:
            if current_section_number is not None:
                current_section_lines.append(line)
    
    if current_section_number is not None:
        sections.append((current_section_number, current_section_title, current_section_lines))
    
    return sections


def is_docx_section_header(paragraph: Paragraph) -> bool:
    """Check if a paragraph is a section header based on heading style or bold formatting."""
    if getattr(paragraph, "style", None) and getattr(paragraph.style, "name", None):
        if str(paragraph.style.name).startswith("Heading"):
            return True
    
    if getattr(paragraph, "runs", None) and paragraph.runs:
        bold_character_count = 0
        total_character_count = 0
        for run in paragraph.runs:
            text = (run.text or "").strip()
            if text:
                total_character_count += len(text)
                if getattr(run, "bold", False):
                    bold_character_count += len(text)
        
        if total_character_count > 0 and bold_character_count / total_character_count > 0.5:
            return True
    
    return False


def convert_table_to_lines(table: Table) -> List[str]:
    """Convert a DOCX table to a list of text lines with tab-separated cells."""
    lines: List[str] = []
    for row in table.rows:
        cell_texts = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        lines.append("\t".join(cell_texts))
    return lines


def parse_docx_sections(docx_file_path: Path) -> List[SectionTuple]:
    """Parse a Word (DOCX) specification into sections at Level 1, 2, and 3."""
    if not DOCX_AVAILABLE:
        raise RuntimeError("python-docx is required for Word support. Install with: pip install python-docx")
    
    document = Document(str(docx_file_path))
    section_header_pattern = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
    sections: List[SectionTuple] = []
    
    current_section_number: Optional[str] = None
    current_section_title: Optional[str] = None
    current_section_lines: List[str] = []
    
    for element in document.element.body:
        element_tag = getattr(element, "tag", "") or ""
        
        if element_tag.endswith("p"):
            paragraph = Paragraph(element, document)
            paragraph_text = (paragraph.text or "").strip()
            
            if not paragraph_text:
                if current_section_number is not None:
                    current_section_lines.append("")
                continue
            
            match = section_header_pattern.match(paragraph_text)
            if match and is_docx_section_header(paragraph):
                section_number = match.group(1)
                section_title = match.group(2).strip()
                section_number_parts = section_number.split(".")
                
                if len(section_number_parts) <= 3:
                    if current_section_number is not None:
                        sections.append((current_section_number, current_section_title, current_section_lines))
                    current_section_number = section_number
                    current_section_title = section_title
                    current_section_lines = [paragraph_text]
                else:
                    if current_section_number is not None:
                        current_section_lines.append(paragraph_text)
                    else:
                        current_section_number = section_number
                        current_section_title = section_title
                        current_section_lines = [paragraph_text]
            else:
                if current_section_number is not None:
                    current_section_lines.append(paragraph_text)
        
        elif element_tag.endswith("tbl"):
            table = Table(element, document)
            table_lines = convert_table_to_lines(table)
            if current_section_number is not None and table_lines:
                current_section_lines.append("")
                current_section_lines.extend(table_lines)
                current_section_lines.append("")
    
    if current_section_number is not None:
        sections.append((current_section_number, current_section_title, current_section_lines))
    
    return sections


def load_spec_sections(spec_file_path: Path, use_spec_format: bool = False) -> List[SectionTuple]:
    """Load specification from file and return parsed sections, dispatching based on file type."""
    spec_file_path = Path(spec_file_path)
    file_suffix = spec_file_path.suffix.lower()
    
    if file_suffix == ".docx":
        return parse_docx_sections(spec_file_path)
    
    document_lines = spec_file_path.read_text(encoding="utf-8").splitlines()
    return parse_rfc_sections(document_lines, use_spec_format=use_spec_format)

# =========== Section File Saving Functions ===========

def save_section_to_file(
    section_number: str,
    section_title: str,
    section_lines: List[str],
    output_directory: Path
) -> Path:
    """Save a single section to a text file in the output directory."""
    safe_section_filename = section_number.replace(".", "_")
    section_file_path = output_directory / f"section_{safe_section_filename}.txt"
    
    section_content = "\n".join(section_lines)
    section_file_path.write_text(section_content, encoding="utf-8")
    
    return section_file_path


def save_all_sections(
    parsed_sections: List[SectionTuple],
    output_directory: Path
) -> int:
    """Save all parsed sections to individual text files in the output directory."""
    saved_file_count = 0
    
    for section_number, section_title, section_lines in parsed_sections:
        section_file_path = save_section_to_file(
            section_number,
            section_title,
            section_lines,
            output_directory
        )
        print(f"    → Saved section {section_number} ({section_title}) to {section_file_path.name}")
        saved_file_count += 1
    
    return saved_file_count

# =========== Main Function ===========

def main() -> None:
    """Parse specification document and save all sections to data/specs/segments directory."""
    spec_file_path = SPEC_DIR / "1.docx"
    
    if not spec_file_path.exists():
        print(f"Error: Spec file not found at {spec_file_path}")
        return
    
    print(f"[*] Loading specification from {spec_file_path.name}...")
    parsed_sections = load_spec_sections(spec_file_path, use_spec_format=True)
    print(f"[*] Parsed {len(parsed_sections)} sections")
    
    print(f"[*] Saving sections to {SPEC_SEGMENT_DIR}...")
    saved_count = save_all_sections(parsed_sections, SPEC_SEGMENT_DIR)
    
    print(f"\n[✓] Successfully saved {saved_count} section(s) to {SPEC_SEGMENT_DIR}")


if __name__ == "__main__":
    main()

