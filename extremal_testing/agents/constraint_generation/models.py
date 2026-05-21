"""Pydantic models for constraint-generation inputs and outputs."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ConstraintItem(BaseModel):
    """A single atomic, testable constraint."""

    statement: str
    evidence: List[str] = Field(default_factory=list)
    why_interesting: str
    category: str


class OperationConstraintBundle(BaseModel):
    """Constraints for a single operation."""

    service: str
    section_id: str
    operation: str
    source_file: str
    description: str
    constraints: List[ConstraintItem] = Field(default_factory=list)
