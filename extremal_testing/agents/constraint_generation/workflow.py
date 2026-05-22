"""Constraint generation workflow for NRF operations."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:  # pragma: no cover - optional dependency
    from agents import Agent, ModelSettings, Runner
except Exception:  # pragma: no cover - fallback when SDK is unavailable
    Agent = None
    ModelSettings = None
    Runner = None

from ...text_parsers.spec_indexer import DEFAULT_SPEC_PATH, RegistryEntry, build_spec_index, load_type_card
from .models import (
    ConstraintItem,
    DependentOperation,
    OperationConstraintBundle,
    OperationSchema,
    ScopedOperationPacket,
    TypeCard,
)
from .prompts import CONSTRAINT_EXTRACTOR_INSTRUCTIONS, SCOPE_AGENT_INSTRUCTIONS

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "generated" / "operation_constraints"
DEFAULT_EXTRACT_MODEL = "gpt-5.4-mini"

TYPE_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
PRIMITIVE_TYPES = {
    "array",
    "boolean",
    "integer",
    "number",
    "object",
    "string",
}


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _dedupe_constraints(constraints: Sequence[ConstraintItem]) -> List[ConstraintItem]:
    unique: List[ConstraintItem] = []
    seen = set()
    for constraint in constraints:
        key = _normalize_text(constraint.statement).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(constraint)
    return unique


def _dedupe_dependencies(dependencies: Sequence[DependentOperation]) -> List[DependentOperation]:
    unique: List[DependentOperation] = []
    seen = set()
    for dependency in dependencies:
        key = (dependency.section_id, dependency.resource_name.lower(), dependency.method.upper())
        if key in seen:
            continue
        seen.add(key)
        unique.append(dependency)
    return unique


def _dedupe_type_cards(type_cards: Sequence[TypeCard]) -> List[TypeCard]:
    unique: List[TypeCard] = []
    seen = set()
    for card in type_cards:
        if card.type_name in seen:
            continue
        seen.add(card.type_name)
        unique.append(card)
    return unique


def _operation_payload(operation: OperationSchema) -> dict:
    return operation.model_dump(exclude_none=True)


def _extract_type_names(text: str) -> List[str]:
    names: List[str] = []
    for token in TYPE_TOKEN_RE.findall(text or ""):
        if token.lower() in PRIMITIVE_TYPES:
            continue
        names.append(token)
    return names


def _collect_referenced_type_names(operation: OperationSchema) -> List[str]:
    names: List[str] = []
    for field in (
        list(operation.uri_variables)
        + list(operation.query_parameters)
        + list(operation.request_body)
        + list(operation.response_body)
    ):
        if field.data_type:
            names.extend(_extract_type_names(field.data_type))

    deduped: List[str] = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return deduped


def _collect_nested_type_names(type_cards: Sequence[TypeCard]) -> List[str]:
    names: List[str] = []
    for card in type_cards:
        for attribute in card.attributes:
            names.extend(_extract_type_names(attribute.data_type))
    deduped: List[str] = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return deduped


class ConstraintWorkflow:
    """Reusable orchestration for constraint generation."""

    def __init__(
        self,
        *,
        spec_path: Path = DEFAULT_SPEC_PATH,
        extract_model: str = DEFAULT_EXTRACT_MODEL,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self.spec_path = spec_path
        self.extract_model = extract_model
        self.output_dir = output_dir
        self.spec_index = build_spec_index(spec_path)

    def build_scope_packet(self, operation: OperationSchema) -> ScopedOperationPacket:
        type_cards = self._resolve_type_cards(operation)
        return ScopedOperationPacket(
            operation=operation,
            type_cards=type_cards,
            context_notes=list(operation.notes),
        )

    def _select_registry_entry(self, type_name: str, service: str) -> Optional[RegistryEntry]:
        entries = self.spec_index.registry.get(type_name, [])
        if not entries:
            return None
        for entry in entries:
            if entry.service == service:
                return entry
        return entries[0]

    async def _load_type_card_async(self, entry: RegistryEntry) -> Optional[TypeCard]:
        return load_type_card(self.spec_path.read_text(encoding="utf-8"), entry)

    def _resolve_type_cards(self, operation: OperationSchema) -> List[TypeCard]:
        markdown = self.spec_path.read_text(encoding="utf-8")
        direct_names = _collect_referenced_type_names(operation)
        cards: List[TypeCard] = []
        seen = set()

        def add_card(card: Optional[TypeCard]) -> None:
            if card is None or card.type_name in seen:
                return
            seen.add(card.type_name)
            cards.append(card)

        for type_name in direct_names:
            entry = self._select_registry_entry(type_name, operation.service)
            if not entry:
                continue
            add_card(load_type_card(markdown, entry))

        nested_names = _collect_nested_type_names(cards)
        for type_name in nested_names:
            if type_name in seen:
                continue
            entry = self._select_registry_entry(type_name, operation.service)
            if not entry:
                continue
            add_card(load_type_card(markdown, entry))

        return _dedupe_type_cards(cards)

    def build_extractor_agent(self):  # pragma: no cover - thin runtime wrapper
        if Agent is None:
            return None
        return Agent(
            name="Constraint Extractor",
            instructions=CONSTRAINT_EXTRACTOR_INSTRUCTIONS,
            model=self.extract_model,
            model_settings=ModelSettings(temperature=0.0, parallel_tool_calls=False),
            output_type=OperationConstraintBundle,
        )

    def build_scope_agent(self):  # pragma: no cover - thin runtime wrapper
        if Agent is None:
            return None
        return Agent(
            name="Scope Agent",
            instructions=SCOPE_AGENT_INSTRUCTIONS,
            model=self.extract_model,
            model_settings=ModelSettings(temperature=0.0, parallel_tool_calls=False),
            output_type=ScopedOperationPacket,
        )

    async def _run_agent(self, agent, payload: dict):  # pragma: no cover - thin runtime wrapper
        if Runner is None or agent is None:
            raise RuntimeError("OpenAI Agents SDK is not available in this environment.")
        return await Runner.run(agent, json.dumps(payload, indent=2, ensure_ascii=False))

    def _infer_dependencies(self, operation: OperationSchema) -> List[DependentOperation]:
        dependencies: List[DependentOperation] = []
        resource = operation.resource_name.lower()
        method = operation.method.upper()

        if resource == "nf-instances" and method in {"GET", "DELETE", "PATCH"} and operation.service == "Nnrf_NFDiscovery":
            dependencies.append(
                DependentOperation(section_id="6.1.3.3.3.2", resource_name="nf-instance", method="PUT")
            )
        if resource == "subscription" and method in {"PATCH", "DELETE"}:
            dependencies.append(
                DependentOperation(section_id="6.1.3.4.3.1", resource_name="subscriptions", method="POST")
            )
        if operation.section_id.startswith("6.1.5.2"):
            dependencies.append(
                DependentOperation(section_id="6.1.3.4.3.1", resource_name="subscriptions", method="POST")
            )
        return _dedupe_dependencies(dependencies)

    def _type_kind_map(self, type_cards: Sequence[TypeCard]) -> Dict[str, str]:
        kind_map: Dict[str, str] = {}
        for card in type_cards:
            if card.attributes and all(attribute.data_type == "enum" for attribute in card.attributes):
                kind_map[card.type_name] = "enum"
            else:
                kind_map[card.type_name] = "structure"
        return kind_map

    def _build_heuristic_bundle(self, packet: ScopedOperationPacket) -> OperationConstraintBundle:
        operation = packet.operation
        constraints: List[ConstraintItem] = []
        type_kind_map = self._type_kind_map(packet.type_cards)

        def add_constraint(statement: str, category: str, section_id: Optional[str] = None) -> None:
            statement = _normalize_text(statement)
            if not statement:
                return
            constraints.append(
                ConstraintItem(
                    id=f"c{len(constraints) + 1}",
                    section_id=section_id or operation.section_id,
                    statement=statement,
                    category=category,
                )
            )

        for field in operation.uri_variables + operation.query_parameters + operation.request_body:
            if field.name and field.cardinality and "0" not in field.cardinality:
                add_constraint(
                    f"The `{field.name}` field is required.",
                    "required_presence",
                )
            if field.data_type and field.data_type in type_kind_map and type_kind_map[field.data_type] == "enum":
                label = field.name or field.data_type
                add_constraint(
                    f"The `{label}` value must conform to the `{field.data_type}` enumeration.",
                    "enum_domain",
                )

        for field in operation.response_body:
            if field.response_code and _normalize_text(field.response_code):
                add_constraint(
                    f"The operation may return `{field.response_code}` with the described `{field.data_type or 'response body'}` payload.",
                    "response_code",
                    section_id=operation.section_id,
                )
            if field.data_type and field.data_type in type_kind_map and type_kind_map[field.data_type] == "enum":
                label = field.data_type
                add_constraint(
                    f"The response data type `{label}` must conform to its enumeration definition.",
                    "enum_domain",
                )

        for note in operation.notes:
            if "shall" in note.lower() or "must" in note.lower():
                add_constraint(note, "normative_requirement")

        bundle = OperationConstraintBundle(**operation.model_dump())
        bundle.constraints = _dedupe_constraints(constraints)
        bundle.dependent_operations = self._infer_dependencies(operation)
        return bundle

    async def _extract_single(self, operation: OperationSchema) -> OperationConstraintBundle:
        packet = self.build_scope_packet(operation)
        if Runner is None or Agent is None or not os.getenv("OPENAI_API_KEY"):
            return self._build_heuristic_bundle(packet)

        extractor = self.build_extractor_agent()
        scope_agent = self.build_scope_agent()
        scoped_payload = packet.model_dump(exclude_none=True)
        if scope_agent is not None:
            scope_result = await self._run_agent(scope_agent, scoped_payload)
            scoped_payload = scope_result.final_output.model_dump(exclude_none=True)
        result = await self._run_agent(extractor, scoped_payload)
        bundle = result.final_output
        bundle.constraints = _dedupe_constraints(bundle.constraints)
        bundle.dependent_operations = _dedupe_dependencies(bundle.dependent_operations)
        return bundle

    async def run_async(
        self,
        operations: Optional[Sequence[OperationSchema]] = None,
    ) -> List[OperationConstraintBundle]:
        operation_list = list(operations) if operations is not None else list(self.spec_index.operation_schemas)
        bundles: List[OperationConstraintBundle] = []
        for operation in operation_list:
            print(f"[*] {operation.section_id} {operation.resource_name} {operation.method}", flush=True)
            bundles.append(await self._extract_single(operation))
        return bundles

    def run(self, operations: Optional[Sequence[OperationSchema]] = None) -> List[OperationConstraintBundle]:
        return asyncio.run(self.run_async(operations))

    def save_results(self, bundles: Sequence[OperationConstraintBundle]) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for old_file in self.output_dir.glob("*.json"):
            old_file.unlink()
        for bundle in bundles:
            safe_resource = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in bundle.resource_name.lower())
            filename = f"{bundle.section_id.replace('.', '_')}_{safe_resource}_{bundle.method.lower()}.json"
            output_file = self.output_dir / filename
            output_file.write_text(bundle.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")


def generate_constraints(
    *,
    spec_path: Path = DEFAULT_SPEC_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    extract_model: str = DEFAULT_EXTRACT_MODEL,
    operations: Optional[Sequence[OperationSchema]] = None,
) -> List[OperationConstraintBundle]:
    workflow = ConstraintWorkflow(
        spec_path=spec_path,
        extract_model=extract_model,
        output_dir=output_dir,
    )
    bundles = workflow.run(operations)
    workflow.save_results(bundles)
    return bundles
