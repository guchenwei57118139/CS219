"""Deterministic markdown spec indexing for NRF operation generation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..agents.constraint_generation.models import (
    OperationField,
    OperationSchema,
    TypeAttribute,
    TypeCard,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SPEC_PATH = ROOT_DIR / "data" / "specs" / "nrf_specification.md"

PRIMITIVE_TYPES = {
    "array",
    "boolean",
    "integer",
    "number",
    "object",
    "string",
}


@dataclass(frozen=True)
class RegistryEntry:
    """A lookup record for a type name."""

    service: str
    type_name: str
    section_id: str
    section_title: str


@dataclass
class SpecIndex:
    """Parsed operation schemas and type registry."""

    operation_schemas: List[OperationSchema]
    registry: Dict[str, List[RegistryEntry]]
    source_path: Path


RESOURCE_SECTION_SPECS: Sequence[Tuple[str, str, str, str]] = (
    (
        "6.1.3.2",
        "#### 6.1.3.2 Resource: nf-instances (Store)",
        r"^####\s+6\.1\.3\.3\s+Resource:\s+nf-instance\s+\(Document\)",
        "Nnrf_NFManagement",
    ),
    (
        "6.1.3.3",
        "#### 6.1.3.3 Resource: nf-instance (Document)",
        r"^####\s+6\.1\.3\.4\s+Resource:\s+subscriptions\s+\(Collection\)",
        "Nnrf_NFManagement",
    ),
    (
        "6.1.3.4",
        "#### 6.1.3.4 Resource: subscriptions (Collection)",
        r"^####\s+6\.1\.3\.5\s+Resource:\s+subscription\s+\(Document\)",
        "Nnrf_NFManagement",
    ),
    (
        "6.1.3.5",
        "#### 6.1.3.5 Resource: subscription (Document)",
        r"^###\s+6\.1\.4\s+Custom Operations without associated resources",
        "Nnrf_NFManagement",
    ),
    (
        "6.1.5.2",
        "#### 6.1.5.2 NF Instance Status Notification",
        r"^###\s+6\.1\.6\s+Data Model",
        "Nnrf_NFManagement",
    ),
    (
        "6.2.3.2",
        "#### 6.2.3.2 Resource: nf-instances (Store)",
        r"^###\s+6\.2\.4\s+Custom Operations without associated resources",
        "Nnrf_NFDiscovery",
    ),
)

TYPE_INVENTORY_TABLES: Sequence[Tuple[str, str, str]] = (
    ("Nnrf_NFManagement", "6.1.6.1-1", r"^###\s+Table\s+6\.1\.6\.1-1:"),
    ("Nnrf_NFDiscovery", "6.2.6.1-1", r"^###\s+Table\s+6\.2\.6\.1-1:"),
)


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _split_table_row(line: str) -> List[str]:
    body = line.strip().strip("|")
    return [cell.strip() for cell in body.split("|")]


def _is_separator_row(line: str) -> bool:
    stripped = line.strip()
    return bool(re.fullmatch(r"\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", stripped))


def _parse_table_block(lines: Sequence[str], start_index: int) -> Tuple[List[str], List[List[str]], int]:
    if start_index >= len(lines) or not lines[start_index].strip().startswith("|"):
        return [], [], start_index

    headers = _split_table_row(lines[start_index])
    index = start_index + 1
    while index < len(lines) and _is_separator_row(lines[index]):
        index += 1

    rows: List[List[str]] = []
    while index < len(lines):
        line = lines[index]
        if not line.strip().startswith("|"):
            break
        rows.append(_split_table_row(line))
        index += 1

    return headers, rows, index


def _find_first_line(lines: Sequence[str], pattern: str, start: int = 0) -> int:
    compiled = re.compile(pattern)
    for index in range(start, len(lines)):
        if compiled.search(lines[index]):
            return index
    return -1


def _collect_block(lines: Sequence[str], start_pattern: str, end_pattern: str) -> List[str]:
    start_index = _find_first_line(lines, start_pattern)
    if start_index < 0:
        return []
    end_index = _find_first_line(lines, end_pattern, start_index + 1)
    if end_index < 0:
        end_index = len(lines)
    return list(lines[start_index:end_index])


def _collect_paragraphs(block_lines: Sequence[str]) -> List[str]:
    paragraphs: List[str] = []
    current: List[str] = []

    def flush() -> None:
        if not current:
            return
        paragraph = _normalize_text(" ".join(current))
        if paragraph:
            paragraphs.append(paragraph)
        current.clear()

    for line in block_lines:
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("Resource URI:"):
            flush()
            continue
        if stripped.startswith("EXAMPLE"):
            flush()
            continue
        current.append(stripped)

    flush()
    return paragraphs


def _collect_notes(block_lines: Sequence[str]) -> List[str]:
    notes: List[str] = []
    current: List[str] = []
    in_note = False

    def flush() -> None:
        nonlocal current, in_note
        if current:
            note = _normalize_text(" ".join(current))
            if note:
                notes.append(note)
        current = []
        in_note = False

    for line in block_lines:
        stripped = line.strip()
        if not stripped:
            if in_note:
                flush()
            continue
        if stripped.startswith("NOTE"):
            if in_note:
                flush()
            current = [stripped]
            in_note = True
            continue
        if in_note:
            if stripped.startswith("#") or stripped.startswith("EXAMPLE"):
                flush()
                continue
            current.append(stripped)

    if in_note:
        flush()
    return notes


def _find_block_table(block_lines: Sequence[str], title_substring: str) -> Tuple[List[str], List[List[str]]]:
    for index, line in enumerate(block_lines):
        if line.strip().startswith("### Table") and title_substring in line:
            table_start = index + 1
            while table_start < len(block_lines) and not block_lines[table_start].strip():
                table_start += 1
            if table_start < len(block_lines) and block_lines[table_start].strip().startswith("|"):
                headers, rows, _ = _parse_table_block(block_lines, table_start)
                return headers, rows
            return [], []
    return [], []


def _select_section_entry(registry: Dict[str, List[RegistryEntry]], type_name: str, service: str) -> Optional[RegistryEntry]:
    entries = registry.get(type_name, [])
    if not entries:
        return None
    for entry in entries:
        if entry.service == service:
            return entry
    return entries[0]


def _extract_type_tokens(text: str) -> List[str]:
    tokens: List[str] = []
    for match in re.findall(r"[A-Za-z][A-Za-z0-9_]*", text or ""):
        if match.lower() in PRIMITIVE_TYPES:
            continue
        tokens.append(match)
    return tokens


def _collect_referenced_type_names(operation: OperationSchema) -> List[str]:
    candidates: List[str] = []
    fields = (
        list(operation.uri_variables)
        + list(operation.query_parameters)
        + list(operation.request_body)
        + list(operation.response_body)
    )
    for field in fields:
        if field.data_type:
            candidates.extend(_extract_type_tokens(field.data_type))
    deduped: List[str] = []
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _parse_row_to_operation_field(headers: Sequence[str], row: Sequence[str]) -> OperationField:
    mapping = {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
    if "Name" in mapping and "Data type" in mapping:
        return OperationField(
            name=mapping.get("Name") or None,
            data_type=mapping.get("Data type") or None,
            cardinality=mapping.get("Cardinality") or None,
            description=_normalize_text(mapping.get("Description") or ""),
            response_code=(mapping.get("Response code") or None),
            applicability=(mapping.get("Applicability") or None),
        )
    if "Data type" in mapping:
        return OperationField(
            name=(mapping.get("Name") or None),
            data_type=mapping.get("Data type") or None,
            cardinality=mapping.get("Cardinality") or None,
            description=_normalize_text(mapping.get("Description") or ""),
            response_code=(mapping.get("Response code") or None),
            applicability=(mapping.get("Applicability") or None),
        )
    return OperationField(
        name=(row[0] if row else None),
        data_type=(row[0] if row else None),
        cardinality=None,
        description=_normalize_text(row[1]) if len(row) > 1 else "",
    )


def _parse_operation_table(block_lines: Sequence[str], title_substring: str) -> List[OperationField]:
    headers, rows = _find_block_table(block_lines, title_substring)
    if not headers and not rows:
        return []
    if rows and len(rows) == 1 and rows[0] and _normalize_text(rows[0][0]).lower().startswith("no "):
        return []
    return [_parse_row_to_operation_field(headers, row) for row in rows]


def _parse_resource_uri(block_lines: Sequence[str]) -> str:
    for line in block_lines:
        stripped = line.strip()
        if stripped.startswith("Resource URI:"):
            return _normalize_text(stripped.split("Resource URI:", 1)[1])
    return ""


def _parse_operation_title(block_lines: Sequence[str], fallback: str) -> Tuple[str, List[str]]:
    paragraphs = _collect_paragraphs(block_lines)
    if not paragraphs:
        return fallback, []
    title = paragraphs[0]
    return title, paragraphs[1:]


def _parse_resource_operation(
    lines: Sequence[str],
    *,
    service: str,
    resource_name: str,
    resource_kind: str,
    resource_section_id: str,
    resource_start_pattern: str,
    resource_end_pattern: str,
) -> List[OperationSchema]:
    block_lines = _collect_block(lines, resource_start_pattern, resource_end_pattern)
    if not block_lines:
        return []

    resource_uri = _parse_resource_uri(block_lines)
    uri_variables = _parse_operation_table(block_lines, "Resource URI variables")

    op_schemas: List[OperationSchema] = []
    method_heading_re = re.compile(r"^######\s+([0-9.]+)\s+([A-Z]+)\s*$")
    method_indices: List[Tuple[int, str, str]] = []
    for index, line in enumerate(block_lines):
        match = method_heading_re.match(line.strip())
        if match:
            method_indices.append((index, match.group(1), match.group(2)))

    for index, method_section_id, method in method_indices:
        next_index = len(block_lines)
        for later_index, _, _ in method_indices:
            if later_index > index:
                next_index = later_index
                break
        method_block = block_lines[index:next_index]
        operation_title, notes = _parse_operation_title(method_block[1:], fallback=method)
        query_parameters = _parse_operation_table(method_block, "URI query parameters")
        request_body = _parse_operation_table(method_block, "Request Body")
        response_body = _parse_operation_table(method_block, "Response Body")
        notes.extend(_collect_notes(method_block))
        deduped_notes: List[str] = []
        seen_notes = set()
        for note in notes:
            normalized = _normalize_text(note)
            if not normalized or normalized in seen_notes:
                continue
            seen_notes.add(normalized)
            deduped_notes.append(normalized)
        op_schemas.append(
            OperationSchema(
                service=service,
                section_id=method_section_id,
                resource_name=resource_name,
                resource_kind=resource_kind,
                method=method,
                operation_title=operation_title,
                resource_uri=resource_uri,
                uri_variables=uri_variables,
                query_parameters=query_parameters,
                request_body=request_body,
                response_body=response_body,
                notes=deduped_notes,
            )
        )

    return op_schemas


def _parse_notification_operation(lines: Sequence[str]) -> List[OperationSchema]:
    block_lines = _collect_block(lines, r"^####\s+6\.1\.5\.2\s+NF Instance Status Notification", r"^###\s+6\.1\.6\s+Data Model")
    if not block_lines:
        return []
    resource_uri = _parse_resource_uri(block_lines)
    operation_title, notes = _parse_operation_title(block_lines[1:], fallback="POST")
    query_parameters = _parse_operation_table(block_lines, "URI query parameters")
    request_body = _parse_operation_table(block_lines, "Request Body")
    response_body = _parse_operation_table(block_lines, "Response Body")
    notes.extend(_collect_notes(block_lines))
    deduped_notes: List[str] = []
    seen_notes = set()
    for note in notes:
        normalized = _normalize_text(note)
        if not normalized or normalized in seen_notes:
            continue
        seen_notes.add(normalized)
        deduped_notes.append(normalized)
    return [
        OperationSchema(
            service="Nnrf_NFManagement",
            section_id="6.1.5.2.2",
            resource_name="NF Instance Status Notification",
            resource_kind="Notification",
            method="POST",
            operation_title=operation_title,
            resource_uri=resource_uri,
            uri_variables=[],
            query_parameters=query_parameters,
            request_body=request_body,
            response_body=response_body,
            notes=deduped_notes,
        )
    ]


def build_type_registry(text: str) -> Dict[str, List[RegistryEntry]]:
    lines = text.splitlines()
    registry: Dict[str, List[RegistryEntry]] = {}
    for service, section_suffix, title_pattern in TYPE_INVENTORY_TABLES:
        title_index = _find_first_line(lines, title_pattern)
        if title_index < 0:
            continue
        table_start = title_index + 1
        while table_start < len(lines) and not lines[table_start].strip():
            table_start += 1
        headers, rows, _ = _parse_table_block(lines, table_start)
        if not headers:
            continue
        for row in rows:
            if len(row) < 2:
                continue
            type_name = _normalize_text(row[0])
            section_id = _normalize_text(row[1])
            description = _normalize_text(row[2]) if len(row) > 2 else ""
            section_title = f"{service} {section_suffix}"
            registry.setdefault(type_name, []).append(
                RegistryEntry(
                    service=service,
                    type_name=type_name,
                    section_id=section_id,
                    section_title=section_title if not description else f"{section_title}: {description}",
                )
            )
    return registry


def _parse_type_card(text: str, entry: RegistryEntry) -> Optional[TypeCard]:
    lines = text.splitlines()
    heading_pattern = rf"^#####\s+{re.escape(entry.section_id)}\s+(Type|Enumeration):\s+{re.escape(entry.type_name)}\s*$"
    heading_index = _find_first_line(lines, heading_pattern)
    if heading_index < 0:
        return None
    next_heading_index = _find_first_line(lines, r"^#####\s+6\.\d+\.\d+\.\d+\.\d+\s+", heading_index + 1)
    if next_heading_index < 0:
        next_heading_index = len(lines)
    block_lines = list(lines[heading_index:next_heading_index])

    section_title = _normalize_text(block_lines[0].split(entry.section_id, 1)[1])
    table_start = -1
    for index, line in enumerate(block_lines):
        if line.strip().startswith("### Table"):
            table_start = index + 1
            while table_start < len(block_lines) and not block_lines[table_start].strip():
                table_start += 1
            break
    if table_start < 0 or table_start >= len(block_lines):
        return None

    if not block_lines[table_start].strip().startswith("|"):
        return None

    headers, rows, _ = _parse_table_block(block_lines, table_start)
    attributes: List[TypeAttribute] = []

    if headers and "Enumeration value" in headers and "Description" in headers:
        for row in rows:
            if not row:
                continue
            attributes.append(
                TypeAttribute(
                    attribute_name=_normalize_text(row[0]),
                    data_type="enum",
                    cardinality="1",
                    description=_normalize_text(row[1]) if len(row) > 1 else "",
                )
            )
    else:
        for row in rows:
            if not row:
                continue
            if headers and "Attribute name" in headers:
                mapping = {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
                attributes.append(
                    TypeAttribute(
                        attribute_name=_normalize_text(mapping.get("Attribute name") or mapping.get("Type Name") or mapping.get("Data type") or ""),
                        data_type=_normalize_text(mapping.get("Data type") or mapping.get("Type Definition") or mapping.get("Description") or ""),
                        cardinality=_normalize_text(mapping.get("Cardinality") or "") or None,
                        description=_normalize_text(mapping.get("Description") or ""),
                    )
                )
            elif headers and "Type Name" in headers:
                mapping = {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
                attributes.append(
                    TypeAttribute(
                        attribute_name=_normalize_text(mapping.get("Type Name") or ""),
                        data_type=_normalize_text(mapping.get("Type Definition") or ""),
                        cardinality=None,
                        description=_normalize_text(mapping.get("Description") or ""),
                    )
                )

    return TypeCard(
        type_name=entry.type_name,
        section_id=entry.section_id,
        section_title=section_title,
        attributes=attributes,
    )


def load_type_card(text: str, entry: RegistryEntry) -> Optional[TypeCard]:
    return _parse_type_card(text, entry)


def load_operation_schemas(text: str) -> List[OperationSchema]:
    lines = text.splitlines()
    operation_schemas: List[OperationSchema] = []
    for section_id, start_marker, end_marker, service in RESOURCE_SECTION_SPECS:
        if section_id == "6.1.5.2":
            operation_schemas.extend(_parse_notification_operation(lines))
            continue

        resource_name, resource_kind = (
            ("nf-instances", "Store")
            if section_id == "6.1.3.2"
            else ("nf-instance", "Document")
            if section_id == "6.1.3.3"
            else ("subscriptions", "Collection")
            if section_id == "6.1.3.4"
            else ("subscription", "Document")
            if section_id == "6.1.3.5"
            else ("nf-instances", "Store")
        )
        operation_schemas.extend(
            _parse_resource_operation(
                lines,
                service=service,
                resource_name=resource_name,
                resource_kind=resource_kind,
                resource_section_id=section_id,
                resource_start_pattern=re.escape(start_marker),
                resource_end_pattern=end_marker,
            )
        )

    return operation_schemas


def build_spec_index(spec_path: Path = DEFAULT_SPEC_PATH) -> SpecIndex:
    text = spec_path.read_text(encoding="utf-8")
    return SpecIndex(
        operation_schemas=load_operation_schemas(text),
        registry=build_type_registry(text),
        source_path=spec_path,
    )


def referenced_types_for_operation(operation: OperationSchema) -> List[str]:
    return _collect_referenced_type_names(operation)
