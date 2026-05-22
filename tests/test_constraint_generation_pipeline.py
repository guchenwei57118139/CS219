from __future__ import annotations

from pathlib import Path

from extremal_testing.agents.constraint_generation.models import (
    ConstraintItem,
    DependentOperation,
    OperationConstraintBundle,
)
from extremal_testing.agents.constraint_generation.workflow import ConstraintWorkflow
from extremal_testing.text_parsers.spec_indexer import (
    DEFAULT_SPEC_PATH,
    build_type_registry,
    load_operation_schemas,
    load_type_card,
)


def test_operation_schema_parser_finds_expected_operations() -> None:
    text = DEFAULT_SPEC_PATH.read_text(encoding="utf-8")
    operations = load_operation_schemas(text)

    assert len(operations) == 10
    assert [operation.section_id for operation in operations] == [
        "6.1.3.2.3.1",
        "6.1.3.3.3.1",
        "6.1.3.3.3.2",
        "6.1.3.3.3.3",
        "6.1.3.3.3.4",
        "6.1.3.4.3.1",
        "6.1.3.5.3.1",
        "6.1.3.5.3.2",
        "6.1.5.2.2",
        "6.2.3.2.3.1",
    ]

    discovery = next(operation for operation in operations if operation.section_id == "6.2.3.2.3.1")
    assert discovery.resource_name == "nf-instances"
    assert discovery.method == "GET"
    assert discovery.notes
    assert all(isinstance(note, str) for note in discovery.notes)


def test_type_registry_and_cards_are_minimal_and_sectioned() -> None:
    text = DEFAULT_SPEC_PATH.read_text(encoding="utf-8")
    registry = build_type_registry(text)

    assert "NFProfile" in registry
    assert "NFType" in registry
    assert "SubscriptionData" in registry

    nf_type_entry = registry["NFType"][0]
    nf_type_card = load_type_card(text, nf_type_entry)

    assert nf_type_card is not None
    assert nf_type_card.type_name == "NFType"
    assert nf_type_card.section_id == nf_type_entry.section_id
    assert nf_type_card.section_title.startswith("Enumeration")
    assert nf_type_card.attributes
    assert nf_type_card.attributes[0].attribute_name == "NRF"
    assert nf_type_card.attributes[0].data_type == "enum"


def test_constraint_workflow_emits_expected_bundle_shape(tmp_path: Path) -> None:
    workflow = ConstraintWorkflow(spec_path=DEFAULT_SPEC_PATH, output_dir=tmp_path)
    operation = next(
        item for item in workflow.spec_index.operation_schemas if item.section_id == "6.2.3.2.3.1"
    )
    bundle = workflow._build_heuristic_bundle(workflow.build_scope_packet(operation))

    assert isinstance(bundle, OperationConstraintBundle)
    assert bundle.service == operation.service
    assert bundle.section_id == operation.section_id
    assert bundle.notes == operation.notes
    assert bundle.constraints
    assert all(isinstance(item, ConstraintItem) for item in bundle.constraints)
    assert all(set(item.model_dump(exclude_none=True)) == {"id", "section_id", "statement", "category"} for item in bundle.constraints)
    assert all(isinstance(item, DependentOperation) for item in bundle.dependent_operations)
    assert all(
        set(item.model_dump(exclude_none=True)) == {"section_id", "resource_name", "method"}
        for item in bundle.dependent_operations
    )
    assert "referenced_types" not in bundle.model_dump(exclude_none=True)
    assert "operation_description" not in bundle.model_dump(exclude_none=True)
    assert all("evidence" not in item.model_dump(exclude_none=True) for item in bundle.constraints)
    assert all("why_interesting" not in item.model_dump(exclude_none=True) for item in bundle.constraints)
    assert all("applies_to" not in item.model_dump(exclude_none=True) for item in bundle.constraints)

    workflow.save_results([bundle])
    written_files = list(tmp_path.glob("*.json"))
    assert len(written_files) == 1
    assert written_files[0].read_text(encoding="utf-8")
