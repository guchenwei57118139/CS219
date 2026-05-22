"""Shared data models for the NRF agents workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OperationMetadata:
    """Metadata for a single operation from AllOpsMetaData.json."""

    operation: str
    path: str
    method: str
    description: Optional[str] = None
    depends_on: Optional[List[str]] = field(default_factory=list)


@dataclass
class OperationSchema:
    """Extracted schema and constraints for an operation."""

    operation: str
    path: str
    method: str
    input_schema: Dict[str, Any]
    constraints: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)


@dataclass
class OperationInfo:
    """Operation metadata plus extracted schema and constraints."""

    operation: str
    path: str
    method: str
    input_schema: Dict[str, Any]
    constraints: List[str]
    depends_on: List[str]


@dataclass
class TestFormat:
    """Container for the suite/test shape used in prompts."""

    suite_structure: Dict[str, Any]
    step_structure: Dict[str, Any]
    test_case_structure: Dict[str, Any]

