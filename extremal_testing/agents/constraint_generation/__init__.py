"""Constraint generation workflows for the markdown-based NRF spec."""

from __future__ import annotations

from .models import (
    ConstraintItem,
    DependentOperation,
    OperationConstraintBundle,
    OperationField,
    OperationSchema,
    ScopedOperationPacket,
    TypeAttribute,
    TypeCard,
)

__all__ = [
    "ConstraintItem",
    "DependentOperation",
    "OperationConstraintBundle",
    "OperationField",
    "OperationSchema",
    "ScopedOperationPacket",
    "TypeAttribute",
    "TypeCard",
]


def __getattr__(name: str):
    if name in {"ConstraintWorkflow", "generate_constraints"}:
        from .workflow import ConstraintWorkflow, generate_constraints

        globals()["ConstraintWorkflow"] = ConstraintWorkflow
        globals()["generate_constraints"] = generate_constraints
        return globals()[name]
    raise AttributeError(name)
