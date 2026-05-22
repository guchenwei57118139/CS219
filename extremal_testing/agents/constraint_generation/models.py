"""Pydantic models for the constraint-generation pipeline."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class OperationField(BaseModel):
    """A row from a URI, query, request, or response table."""

    name: Optional[str] = None
    data_type: Optional[str] = None
    cardinality: Optional[str] = None
    description: str = ""
    response_code: Optional[str] = None
    applicability: Optional[str] = None


class TypeAttribute(BaseModel):
    """A compact attribute row in a data model card."""

    attribute_name: str
    data_type: str
    cardinality: Optional[str] = None
    description: str = ""


class TypeCard(BaseModel):
    """A compact, token-efficient type summary."""

    type_name: str
    section_id: str
    section_title: str
    attributes: List[TypeAttribute] = Field(default_factory=list)


class DependentOperation(BaseModel):
    """An operation that should happen before the current one."""

    section_id: str
    resource_name: str
    method: str


class ConstraintItem(BaseModel):
    """A single atomic, testable constraint."""

    id: str
    section_id: str
    statement: str
    category: str


class OperationSchema(BaseModel):
    """Canonical operation input used by the generation pipeline."""

    service: str
    section_id: str
    resource_name: str
    resource_kind: str
    method: str
    operation_title: str
    resource_uri: str
    uri_variables: List[OperationField] = Field(default_factory=list)
    query_parameters: List[OperationField] = Field(default_factory=list)
    request_body: List[OperationField] = Field(default_factory=list)
    response_body: List[OperationField] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class OperationConstraintBundle(OperationSchema):
    """Final per-operation output."""

    constraints: List[ConstraintItem] = Field(default_factory=list)
    dependent_operations: List[DependentOperation] = Field(default_factory=list)


class ScopedOperationPacket(BaseModel):
    """Internal packet used to keep prompts compact."""

    operation: OperationSchema
    type_cards: List[TypeCard] = Field(default_factory=list)
    context_notes: List[str] = Field(default_factory=list)
