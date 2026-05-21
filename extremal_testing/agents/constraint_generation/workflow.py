"""Constraint generation workflow powered by the OpenAI Agents SDK."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import List, Optional, Sequence

from agents import Agent, ModelSettings, Runner

from ...text_parsers.parse_operations_descriptions import (
    OperationDescription,
    parse_all_operation_descriptions,
)
from .models import ConstraintItem, OperationConstraintBundle
from .prompts import EXTRACTOR_INSTRUCTIONS

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "generated" / "operation_constraints"
DEFAULT_EXTRACT_MODEL = "gpt-5.4-mini"


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


def _normalize_bundle(bundle: OperationConstraintBundle) -> OperationConstraintBundle:
    bundle.constraints = _dedupe_constraints(bundle.constraints)
    return bundle


def _description_payload(operation: OperationDescription) -> dict:
    return {
        "service": operation.service,
        "section_id": operation.section_id,
        "operation": operation.operation,
        "source_file": operation.source_file,
        "description": operation.description,
    }


class ConstraintWorkflow:
    """Reusable orchestration for constraint generation.

    This workflow intentionally uses one fixed design:
    - parse all operation descriptions
    - run one extractor agent per operation
    - write one JSON output file per operation
    """

    def __init__(
        self,
        *,
        extract_model: str = DEFAULT_EXTRACT_MODEL,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self.extract_model = extract_model
        self.output_dir = output_dir

    def build_extractor_agent(self) -> Agent[None]:
        return Agent(
            name="Constraint Extractor",
            instructions=EXTRACTOR_INSTRUCTIONS,
            model=self.extract_model,
            model_settings=ModelSettings(temperature=0.0, parallel_tool_calls=False),
            output_type=OperationConstraintBundle,
        )

    def _build_extraction_prompt(self, operation: OperationDescription) -> str:
        return json.dumps(_description_payload(operation), indent=2, ensure_ascii=False)

    async def _run_agent(self, agent: Agent[None], prompt: str):
        return await Runner.run(agent, prompt)

    async def _extract_single(self, operation: OperationDescription) -> OperationConstraintBundle:
        extractor = self.build_extractor_agent()
        result = await self._run_agent(extractor, self._build_extraction_prompt(operation))
        bundle = result.final_output
        return _normalize_bundle(bundle)

    async def run_async(
        self,
        operations: Optional[Sequence[OperationDescription]] = None,
    ) -> List[OperationConstraintBundle]:
        operation_list = list(operations) if operations is not None else parse_all_operation_descriptions()
        bundles: List[OperationConstraintBundle] = []
        for operation in operation_list:
            print(f"[*] {operation.operation}", flush=True)
            bundles.append(await self._extract_single(operation))
        return bundles

    def run(self, operations: Optional[Sequence[OperationDescription]] = None) -> List[OperationConstraintBundle]:
        return asyncio.run(self.run_async(operations))

    def save_results(self, bundles: Sequence[OperationConstraintBundle]) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for old_file in self.output_dir.glob("*.json"):
            old_file.unlink()
        for bundle in bundles:
            output_file = self.output_dir / f"{bundle.operation}.json"
            output_file.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")


def generate_constraints(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    extract_model: str = DEFAULT_EXTRACT_MODEL,
    operations: Optional[Sequence[OperationDescription]] = None,
) -> List[OperationConstraintBundle]:
    workflow = ConstraintWorkflow(
        extract_model=extract_model,
        output_dir=output_dir,
    )
    bundles = workflow.run(operations)
    workflow.save_results(bundles)
    return bundles
