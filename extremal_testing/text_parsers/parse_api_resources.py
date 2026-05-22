"""Deterministically parse resource-backed sections from ``api_spec.pdf``.

The parser is intentionally standalone and produces one JSON file per resource
for the resource-backed sections of the NRF management and discovery APIs.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PDF_PATH = ROOT_DIR / "data" / "specs" / "api_spec.pdf"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "generated" / "api_resources"

SECTION_SPECS = (
    {
        "service": "Nnrf_NFManagement",
        "section_id": "6.1.3.2",
        "end_section_id": "6.1.3.3",
        "resource_name": "nf-instances",
        "resource_kind": "Store",
    },
    {
        "service": "Nnrf_NFManagement",
        "section_id": "6.1.3.3",
        "end_section_id": "6.1.3.4",
        "resource_name": "nf-instance",
        "resource_kind": "Document",
    },
    {
        "service": "Nnrf_NFManagement",
        "section_id": "6.1.3.4",
        "end_section_id": "6.1.3.5",
        "resource_name": "subscriptions",
        "resource_kind": "Collection",
    },
    {
        "service": "Nnrf_NFManagement",
        "section_id": "6.1.3.5",
        "end_section_id": "6.1.5.2",
        "resource_name": "subscription",
        "resource_kind": "Document",
    },
    {
        "service": "Nnrf_NFManagement",
        "section_id": "6.1.5.2",
        "end_section_id": "6.1.6",
        "resource_name": "notification callback",
        "resource_kind": "Notification",
    },
    {
        "service": "Nnrf_NFDiscovery",
        "section_id": "6.2.3.2",
        "end_section_id": "6.2.4",
        "resource_name": "nf-instances",
        "resource_kind": "Store",
    },
)

SECTION_HEADING_RE = re.compile(
    r"^(?P<section_id>\d+(?:\.\d+)+)(?:\s+(?P<title>.*\S))?\s*$"
)
RESOURCE_TITLE_RE = re.compile(r"^Resource:\s*(?P<resource_name>.+?)\s*\((?P<resource_kind>[^)]+)\)\s*$")
RESOURCE_URI_RE = re.compile(r"^Resource URI:\s*(?P<resource_uri>.+?)\s*$")
TABLE_TITLE_RE = re.compile(r"^Table\s+(?P<table_id>\S+):\s*(?P<title>.+?)\s*$")
METHOD_HEADING_RE = re.compile(r"^(?P<section_id>\d+(?:\.\d+){5,})\s*$")
CARDINALITY_RE = re.compile(r"^(?:(?P<p>[MOC])\s+)?(?P<card>\d+(?:\.\.\d+|\.\.N)?)\s*$")
P_ONLY_RE = re.compile(r"^[MOC]\s*$")
P_CARD_RE = re.compile(r"^(?:(?P<p>[MOC])\s+)?(?P<card>\d+(?:\.\.\d+|\.\.N)?)\s*$")
RESPONSE_CODE_RE = re.compile(r"^\d{3}\s+.+$")

APPLICABILITY_MARKERS = {
    "query-paramsext1": "Query-Params-Ext1",
    "complexquery": "Complex-Query",
}

TABLE_HEADER_MARKERS = {
    "name",
    "definition",
    "data type",
    "p",
    "cardinality",
    "description",
    "response",
    "codes",
    "response codes",
    "applicability",
}

DESCRIPTION_STARTERS = (
    "the ",
    "this ",
    "if ",
    "when ",
    "upon ",
    "a ",
    "an ",
    "in ",
    "it ",
    "list ",
    "representation ",
    "successful ",
    "note:",
)

QUERY_TABLE_END_MARKERS = (
    "This method shall support the request data structures",
    "The default logical relationship among the query parameters",
    "The NRF may support the Complex query expression",
    "A NRF not supporting Complex query expression",
)


@dataclass(frozen=True)
class ResourceSectionSpec:
    service: str
    section_id: str
    end_section_id: str
    resource_name: str
    resource_kind: str


@dataclass
class MethodSpec:
    method: str
    section_id: str
    description: str
    query_parameters: List[dict] = field(default_factory=list)
    request_body: List[dict] = field(default_factory=list)
    response_body: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "section_id": self.section_id,
            "description": self.description,
            "query_parameters": self.query_parameters,
            "request_body": self.request_body,
            "response_body": self.response_body,
        }


@dataclass
class ResourceSpec:
    service: str
    section_id: str
    resource_name: str
    resource_kind: str
    description: str
    resource_uri: str
    uri_variables: List[dict]
    methods: List[MethodSpec]

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "section_id": self.section_id,
            "resource_name": self.resource_name,
            "resource_kind": self.resource_kind,
            "description": self.description,
            "resource_uri": self.resource_uri,
            "uri_variables": self.uri_variables,
            "methods": [method.to_dict() for method in self.methods],
        }


@dataclass(frozen=True)
class Heading:
    section_id: str
    title: str
    line_index: int
    title_index: int

    @property
    def depth(self) -> int:
        return len(self.section_id.split("."))


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split()).strip()


def compact_text(lines: Sequence[str]) -> str:
    return "".join(line.strip() for line in lines if line.strip())


def join_paragraphs(lines: Sequence[str]) -> str:
    paragraphs: List[str] = []
    current: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(normalize_whitespace(" ".join(current)))
                current = []
            continue
        current.append(stripped)
    if current:
        paragraphs.append(normalize_whitespace(" ".join(current)))
    return "\n\n".join(paragraphs).strip()


def is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped == "ETSI":
        return True
    if stripped.startswith("ETSI TS 129 510"):
        return True
    if stripped.startswith("3GPP TS 29.510 version"):
        return True
    if stripped.isdigit():
        return True
    return False


def sanitize_lines(lines: Sequence[str]) -> List[str]:
    sanitized: List[str] = []
    for line in lines:
        stripped = line.rstrip()
        if is_noise_line(stripped):
            sanitized.append("")
        else:
            sanitized.append(stripped)
    return sanitized


def load_pdf_text(pdf_path: Path) -> str:
    if not pdf_path.exists():
        raise FileNotFoundError(f"Missing PDF file: {pdf_path}")

    if shutil.which("pdftotext"):
        try:
            completed = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                check=True,
                capture_output=True,
                text=True,
            )
            if completed.stdout.strip():
                return completed.stdout
        except (OSError, subprocess.CalledProcessError):
            pass

    import fitz  # type: ignore

    document = fitz.open(str(pdf_path))
    pages: List[str] = []
    for page in document:
        pages.append(page.get_text("text"))
    return "\n".join(pages)


def is_section_heading(line: str) -> bool:
    return bool(SECTION_HEADING_RE.match(line.strip()))


def collect_headings(lines: Sequence[str]) -> List[Heading]:
    headings: List[Heading] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        match = SECTION_HEADING_RE.match(line)
        if not match:
            index += 1
            continue
        section_id = match.group("section_id")
        title_text = match.group("title")
        if title_text:
            title_index = index
            title = normalize_whitespace(title_text)
        else:
            title_index = index + 1
            while title_index < len(lines) and not lines[title_index].strip():
                title_index += 1
            if title_index >= len(lines):
                break
            title = normalize_whitespace(lines[title_index])
        headings.append(
            Heading(
                section_id=section_id,
                title=title,
                line_index=index,
                title_index=title_index,
            )
        )
        index = title_index + 1
    return headings


def section_depth(section_id: str) -> int:
    return len(section_id.split("."))


def slice_lines(lines: Sequence[str], start_index: int, end_index: int) -> List[str]:
    return list(lines[start_index:end_index])


def find_heading(headings: Sequence[Heading], section_id: str) -> Heading:
    for heading in headings:
        if heading.section_id == section_id:
            return heading
    raise ValueError(f"Unable to locate section heading {section_id}")


def compact_marker(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def is_name_fragment(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.lower() == "n/a":
        return True
    return bool(re.fullmatch(r"[a-z][a-z0-9-]*", stripped))


def is_data_type_fragment(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.lower() == "n/a":
        return True
    if stripped.startswith("array("):
        return True
    if stripped in {"string", "integer", "boolean", "Uri", "Fqdn", "Dnn", "Tai"}:
        return True
    if stripped[0].isupper():
        return True
    return False


def is_cardinality_fragment(line: str) -> bool:
    return bool(P_CARD_RE.match(line.strip()))


def is_p_only_fragment(line: str) -> bool:
    return bool(P_ONLY_RE.match(line.strip()))


def is_response_code_fragment(line: str) -> bool:
    return bool(RESPONSE_CODE_RE.match(normalize_whitespace(line)))


def is_applicability_fragment(text: str) -> Optional[str]:
    compact = compact_marker(text)
    return APPLICABILITY_MARKERS.get(compact)


def split_blocks(lines: Sequence[str]) -> List[List[str]]:
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def drop_until_row_start(lines: Sequence[str], row_start_predicate) -> List[str]:
    index = 0
    while index < len(lines):
        stripped = normalize_whitespace(lines[index])
        if not stripped:
            index += 1
            continue
        if row_start_predicate(lines[index]):
            return list(lines[index:])
        index += 1
    return []


def is_table_header_text(text: str) -> bool:
    normalized = normalize_whitespace(text).lower()
    return any(
        normalized == marker or normalized.startswith(marker + " ")
        for marker in TABLE_HEADER_MARKERS
    )


def split_query_rows(lines: Sequence[str]) -> List[List[str]]:
    rows: List[List[str]] = []
    current: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("NOTE:"):
            if current:
                rows.append(current)
            break
        if not current:
            if not is_name_fragment(line):
                continue
            current = [line]
            continue
        if any(line_contains_cardinality(item) for item in current) and any(
            stripped.startswith(marker) for marker in QUERY_TABLE_END_MARKERS
        ):
            rows.append(current)
            break
        if is_name_fragment(line) and any(line_contains_cardinality(item) for item in current):
            rows.append(current)
            current = [line]
            continue
        current.append(line)

    if current:
        rows.append(current)
    return rows


def split_query_row(block: Sequence[str]) -> Tuple[List[str], List[str], str, List[str]]:
    card_index = None
    for index, line in enumerate(block):
        if line_contains_cardinality(line):
            card_index = index
            break
    if card_index is None:
        raise ValueError(f"Missing cardinality line in query row: {block}")

    pre = list(block[:card_index])
    cardinality_line = block[card_index]
    remainder = list(block[card_index + 1 :])

    if not pre:
        parts = [part for part in re.split(r"\s{2,}", cardinality_line.strip()) if part]
        if len(parts) < 3:
            raise ValueError(f"Unable to split compact query row: {block}")
        name_lines = [parts[0]]
        data_type_lines = [parts[1]]
        cardinality_line = parts[2]
        if len(parts) > 3:
            remainder = [parts[3]] + remainder
    else:
        index = 0
        name_lines = []
        while index < len(pre) and is_name_fragment(pre[index]):
            name_lines.append(pre[index])
            index += 1

        data_type_lines = list(pre[index:])

    return name_lines, data_type_lines, cardinality_line, remainder


def line_contains_cardinality(line: str) -> bool:
    normalized = normalize_whitespace(line)
    return bool(
        re.search(r"(?:^|\s)(?:[MOC]\s+)?(?:\d+\.\.\d+|\d+\.\.N|\d+)(?:\s|$)", normalized)
    )


def split_body_row(block: Sequence[str]) -> Tuple[List[str], List[str], Optional[str], List[str]]:
    card_index = None
    for index, line in enumerate(block):
        if line_contains_cardinality(line):
            card_index = index
            break
    if card_index is None:
        raise ValueError(f"Missing cardinality line in body row: {block}")

    pre = list(block[:card_index])
    cardinality_line = block[card_index]
    remainder = list(block[card_index + 1 :])

    if not pre:
        parts = [part for part in re.split(r"\s{2,}", cardinality_line.strip()) if part]
        if len(parts) < 3:
            raise ValueError(f"Unable to split compact body row: {block}")
        data_type_lines = [parts[0]]
        p_value = parts[1] if parts[1] in {"M", "O", "C"} else None
        cardinality_line = parts[2] if p_value else parts[1]
        if len(parts) > 3:
            remainder = parts[3:]
    else:
        index = 0
        data_type_lines = []
        while index < len(pre) and not is_p_only_fragment(pre[index]) and not is_cardinality_fragment(pre[index]):
            data_type_lines.append(pre[index])
            index += 1

        p_value = None
        if index < len(pre) and is_p_only_fragment(pre[index]):
            p_value = pre[index].strip()
            index += 1

        if index < len(pre) and is_cardinality_fragment(pre[index]):
            cardinality_line = pre[index]
        elif data_type_lines and is_cardinality_fragment(data_type_lines[-1]):
            cardinality_line = data_type_lines.pop()

    return data_type_lines, [cardinality_line], p_value, remainder


def parse_cardinality(cardinality_line: str) -> str:
    match = P_CARD_RE.match(cardinality_line.strip())
    if not match:
        raise ValueError(f"Invalid cardinality line: {cardinality_line!r}")
    return match.group("card")


def parse_response_code(lines: Sequence[str]) -> Tuple[Optional[str], List[str]]:
    if not lines:
        return None, []

    max_prefix = min(3, len(lines))
    for prefix_len in range(1, max_prefix + 1):
        candidate = normalize_whitespace(" ".join(lines[:prefix_len]))
        if not is_response_code_fragment(candidate):
            continue
        if prefix_len == len(lines):
            return candidate, []
        next_line = lines[prefix_len].strip().lower()
        if any(next_line.startswith(starter) for starter in DESCRIPTION_STARTERS):
            return candidate, list(lines[prefix_len:])
    return None, list(lines)


def parse_query_parameters_table(lines: Sequence[str]) -> List[dict]:
    table_lines = drop_until_row_start(lines, lambda line: is_name_fragment(line))
    first_content = next((line for line in table_lines if line.strip()), None)
    if first_content and compact_marker(first_content) == "n/a":
        return []

    rows: List[dict] = []
    for block in split_query_rows(table_lines):
        normalized = compact_marker("".join(block))
        if normalized == "n/a":
            continue

        name_lines, data_type_lines, cardinality_line, remainder = split_query_row(block)
        applicability: Optional[str] = None
        if remainder:
            for tail_len in range(min(3, len(remainder)), 0, -1):
                candidate = is_applicability_fragment("".join(remainder[-tail_len:]))
                if candidate:
                    applicability = candidate
                    remainder = remainder[:-tail_len]
                    break

        rows.append(
            {
                "name": compact_text(name_lines),
                "data_type": compact_text(data_type_lines),
                "cardinality": parse_cardinality(cardinality_line),
                "description": join_paragraphs(remainder),
                **({"applicability": applicability} if applicability else {}),
            }
        )
    return rows


def parse_uri_variables_table(lines: Sequence[str]) -> List[dict]:
    blocks = split_blocks(drop_until_row_start(lines, lambda line: is_name_fragment(line)))
    rows: List[dict] = []
    for block in blocks:
        if not block:
            continue
        if block[0].strip().startswith("NOTE:"):
            continue
        normalized = compact_marker("".join(block))
        if normalized in {"name", "definition"}:
            continue
        rows.append(
            {
                "name": compact_text(block[:1]),
                "description": join_paragraphs(block[1:]),
            }
        )
    return rows


def parse_request_body_table(lines: Sequence[str]) -> List[dict]:
    table_lines = drop_until_row_start(
        lines,
        lambda line: is_data_type_fragment(line)
        and not is_table_header_text(line)
        and not line.strip().startswith("Table "),
    )
    first_content = next((line for line in table_lines if line.strip()), None)
    if first_content and compact_marker(first_content) == "n/a":
        return []

    blocks = split_blocks(table_lines)
    rows: List[dict] = []
    for block in blocks:
        if not block or block[0].strip().startswith("NOTE:"):
            continue
        normalized = compact_marker("".join(block))
        if normalized == "n/a":
            continue

        data_type_lines, cardinality_lines, _p_value, remainder = split_body_row(block)
        rows.append(
            {
                "data_type": compact_text(data_type_lines),
                "cardinality": parse_cardinality(cardinality_lines[0]),
                "description": join_paragraphs(remainder),
            }
        )
    return rows


def parse_response_body_table(lines: Sequence[str]) -> List[dict]:
    table_lines = drop_until_row_start(
        lines,
        lambda line: is_data_type_fragment(line)
        and not is_table_header_text(line)
        and not line.strip().startswith("Table "),
    )

    rows: List[List[str]] = []
    current: List[str] = []
    for line in table_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("NOTE:"):
            if current:
                rows.append(current)
            break
        if current and line_contains_cardinality(line):
            rows.append(current)
            current = [line]
            continue
        if not current:
            if stripped.lower() == "n/a" or line_contains_cardinality(line):
                current = [line]
            continue
        current.append(line)

    if current:
        rows.append(current)

    parsed_rows: List[dict] = []
    for block in rows:
        if not block:
            continue
        first_line = block[0].strip()
        if not (
            first_line.lower().startswith("n/a")
            or line_contains_cardinality(first_line)
            or is_response_code_fragment(first_line)
        ):
            continue
        if first_line.lower().startswith("n/a"):
            tail = block[:]
            tail[0] = re.sub(r"^\s*n/?a\s*", "", tail[0], flags=re.IGNORECASE)
            tail = [line for line in tail if line.strip()]
            response_code, remainder = parse_response_code(tail)
            row = {
                "data_type": "n/a",
                "description": join_paragraphs(remainder),
            }
            if response_code:
                row["response_code"] = response_code
            parsed_rows.append(row)
            continue

        data_type_lines, cardinality_lines, _p_value, remainder = split_body_row(block)
        response_code, remainder = parse_response_code(remainder)
        row = {
            "data_type": compact_text(data_type_lines),
            "cardinality": parse_cardinality(cardinality_lines[0]),
            "description": join_paragraphs(remainder),
        }
        if response_code:
            row["response_code"] = response_code
        parsed_rows.append(row)
    return parsed_rows


def extract_table_block(lines: Sequence[str], start_index: int) -> Tuple[str, List[str], int]:
    title = normalize_whitespace(lines[start_index])
    end_index = start_index + 1
    while end_index < len(lines):
        stripped = lines[end_index].strip()
        if not stripped:
            end_index += 1
            continue
        if stripped.startswith("Table ") or stripped.startswith("NOTE:") or is_section_heading(stripped):
            break
        end_index += 1
    return title, list(lines[start_index + 1 : end_index]), end_index


def extract_top_subsection_blocks(
    lines: Sequence[str],
    section_id: str,
    headings: Sequence[Heading],
) -> List[Tuple[str, List[str]]]:
    depth = section_depth(section_id)
    relevant = [
        heading
        for heading in headings
        if heading.section_id.startswith(section_id + ".") and heading.depth == depth + 1
    ]
    blocks: List[Tuple[str, List[str]]] = []
    for index, heading in enumerate(relevant):
        next_line_index = relevant[index + 1].line_index if index + 1 < len(relevant) else len(lines)
        content = slice_lines(lines, heading.title_index + 1, next_line_index)
        blocks.append((heading.title, content))
    return blocks


def extract_method_blocks(
    lines: Sequence[str],
    section_id: str,
    headings: Sequence[Heading],
) -> List[Heading]:
    depth = section_depth(section_id)
    return [
        heading
        for heading in headings
        if heading.section_id.startswith(section_id + ".") and heading.depth == depth + 2
    ]


def parse_method_tables(method_lines: Sequence[str], method_name: str) -> Tuple[List[dict], List[dict], List[dict]]:
    query_parameters: List[dict] = []
    request_body: List[dict] = []
    response_body: List[dict] = []

    table_starts = [index for index, line in enumerate(method_lines) if line.strip().startswith("Table ")]
    for table_index, start in enumerate(table_starts):
        title, body_lines, _end_index = extract_table_block(method_lines, start)
        normalized_title = normalize_whitespace(title)
        if "URI query parameters supported by the" in normalized_title:
            query_parameters = parse_query_parameters_table(body_lines)
        elif f"Request Body" in normalized_title and method_name in normalized_title:
            request_body = parse_request_body_table(body_lines)
        elif f"Response Body" in normalized_title and method_name in normalized_title:
            response_body = parse_response_body_table(body_lines)
        elif "Response Body" in normalized_title and method_name not in normalized_title and not response_body:
            response_body = parse_response_body_table(body_lines)

    return query_parameters, request_body, response_body


def parse_method_block(
    method_heading: Heading,
    lines: Sequence[str],
    headings: Sequence[Heading],
    resource_section_id: str,
) -> MethodSpec:
    relevant_following = [
        heading
        for heading in headings
        if heading.section_id.startswith(resource_section_id + ".")
        and heading.line_index > method_heading.line_index
        and (
            heading.depth == method_heading.depth
            or heading.depth == section_depth(resource_section_id) + 1
        )
    ]
    end_line = relevant_following[0].line_index if relevant_following else len(lines)
    method_lines = slice_lines(lines, method_heading.title_index + 1, end_line)

    description_lines: List[str] = []
    first_table_index = None
    for index, line in enumerate(method_lines):
        if line.strip().startswith("Table "):
            first_table_index = index
            break
        description_lines.append(line)
    description = join_paragraphs(description_lines)
    table_lines = method_lines[first_table_index:] if first_table_index is not None else []
    query_parameters, request_body, response_body = parse_method_tables(table_lines, method_heading.title)

    return MethodSpec(
        method=method_heading.title,
        section_id=method_heading.section_id,
        description=description,
        query_parameters=query_parameters,
        request_body=request_body,
        response_body=response_body,
    )


def parse_resource_section(section_spec: ResourceSectionSpec, lines: Sequence[str]) -> ResourceSpec:
    sanitized = sanitize_lines(lines)
    headings = collect_headings(sanitized)
    resource_heading = find_heading(headings, section_spec.section_id)
    end_heading = find_heading(headings, section_spec.end_section_id)

    resource_block = slice_lines(sanitized, resource_heading.line_index, end_heading.line_index)
    block_headings = collect_headings(resource_block)

    resource_title_line = normalize_whitespace(resource_heading.title)
    if RESOURCE_TITLE_RE.match(resource_title_line):
        title_match = RESOURCE_TITLE_RE.match(resource_title_line)
        assert title_match is not None
        resource_name = normalize_whitespace(title_match.group("resource_name"))
        resource_kind = normalize_whitespace(title_match.group("resource_kind"))
    else:
        resource_name = section_spec.resource_name
        resource_kind = section_spec.resource_kind

    description = ""
    resource_uri = ""
    uri_variables: List[dict] = []

    top_level_blocks = extract_top_subsection_blocks(resource_block, section_spec.section_id, block_headings)
    for title, content in top_level_blocks:
        normalized_title = normalize_whitespace(title)
        if normalized_title == "Description":
            description = join_paragraphs(content)
        elif normalized_title in {"Resource Definition", "Notification Definition"}:
            for index, line in enumerate(content):
                stripped = normalize_whitespace(line)
                uri_match = RESOURCE_URI_RE.match(stripped)
                if uri_match:
                    resource_uri = normalize_whitespace(uri_match.group("resource_uri"))
                if stripped.startswith("Table ") and "Resource URI variables" in stripped:
                    table_title, table_body, _end_index = extract_table_block(content, index)
                    uri_variables = parse_uri_variables_table(table_body)
                    break

    method_headings = extract_method_blocks(resource_block, section_spec.section_id, block_headings)
    methods = [
        parse_method_block(method_heading, resource_block, block_headings, section_spec.section_id)
        for method_heading in method_headings
    ]

    return ResourceSpec(
        service=section_spec.service,
        section_id=section_spec.section_id,
        resource_name=resource_name,
        resource_kind=resource_kind,
        description=description,
        resource_uri=resource_uri,
        uri_variables=uri_variables,
        methods=methods,
    )


def parse_api_resources(pdf_path: Path = DEFAULT_PDF_PATH) -> List[ResourceSpec]:
    pdf_text = load_pdf_text(pdf_path)
    lines = sanitize_lines(pdf_text.splitlines())
    resources = [
        parse_resource_section(ResourceSectionSpec(**spec), lines)
        for spec in SECTION_SPECS
    ]
    return resources


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "resource"


def output_filename(resource: ResourceSpec) -> str:
    section = resource.section_id.replace(".", "_")
    return f"{section}__{slugify(resource.resource_name)}__{slugify(resource.resource_kind)}.json"


def write_api_resources(resources: Sequence[ResourceSpec], output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.glob("*.json"):
        path.unlink()
    for resource in resources:
        output_path = output_dir / output_filename(resource)
        output_path.write_text(
            json.dumps(resource.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def generate_api_resources(
    pdf_path: Path = DEFAULT_PDF_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> List[ResourceSpec]:
    resources = parse_api_resources(pdf_path=pdf_path)
    write_api_resources(resources, output_dir=output_dir)
    return resources


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse resource-backed sections from api_spec.pdf.")
    parser.add_argument(
        "--pdf-path",
        type=Path,
        default=DEFAULT_PDF_PATH,
        help="Path to api_spec.pdf.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for per-resource JSON output.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    print("Starting resource parsing from PDF...", flush=True)
    print(f"[*] Input PDF: {args.pdf_path}", flush=True)
    print(f"[*] Output directory: {args.output_dir}", flush=True)
    resources = parse_api_resources(args.pdf_path)
    print(f"[*] Parsed {len(resources)} resource(s)", flush=True)
    write_api_resources(resources, args.output_dir)
    for resource in resources:
        print(f"[*] Wrote {output_filename(resource)}", flush=True)


if __name__ == "__main__":
    main()
