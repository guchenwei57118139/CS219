from __future__ import annotations

import json
from pathlib import Path

import pytest

from extremal_testing.text_parsers.parse_api_resources import generate_api_resources, parse_api_resources


ROOT_DIR = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT_DIR / "extremal_testing" / "data" / "specs" / "api_spec.pdf"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _walk_values(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_values(item)
    else:
        yield value


@pytest.fixture()
def generated_dir(tmp_path: Path) -> Path:
    out_dir = tmp_path / "api_resources"
    generate_api_resources(pdf_path=PDF_PATH, output_dir=out_dir)
    return out_dir


def test_parser_writes_expected_resources(generated_dir: Path) -> None:
    files = sorted(generated_dir.glob("*.json"))
    assert len(files) == 6

    resources = {item["section_id"]: item for item in map(_load_json, files)}

    nf_instance = resources["6.1.3.3"]
    assert nf_instance["resource_uri"] == "{apiRoot}/nnrf-nfm/v1/nf-instances/{nfInstanceID}"
    assert [var["name"] for var in nf_instance["uri_variables"]] == ["apiRoot", "nfInstanceID"]
    assert nf_instance["methods"][0]["method"] == "GET"
    assert nf_instance["methods"][0]["response_body"][0]["data_type"] == "NFProfile"
    assert nf_instance["methods"][0]["response_body"][0]["response_code"] == "200 OK"

    subscriptions = resources["6.1.3.4"]
    assert subscriptions["methods"][0]["method"] == "POST"
    assert subscriptions["methods"][0]["response_body"][0]["response_code"] == "201 Created"

    subscription = resources["6.1.3.5"]
    patch_method = next(method for method in subscription["methods"] if method["method"] == "PATCH")
    assert patch_method["request_body"][0]["data_type"] == "array(PatchItem)"
    assert patch_method["response_body"][-1]["response_code"] == "204 No Content"

    notification = resources["6.1.5.2"]
    post_method = notification["methods"][0]
    assert notification["resource_uri"] == "{nfStatusNotificationUri}"
    assert post_method["request_body"][0]["data_type"] == "NotificationData"
    assert post_method["response_body"][0]["data_type"] == "n/a"
    assert post_method["response_body"][0]["response_code"] == "204 No Content"

    discovery = resources["6.2.3.2"]
    query_names = {item["name"] for item in discovery["methods"][0]["query_parameters"]}
    assert {"target-nf-type", "requester-nf-type", "service-names", "complex-query", "limit"}.issubset(query_names)
    complex_query = next(item for item in discovery["methods"][0]["query_parameters"] if item["name"] == "complex-query")
    assert complex_query["applicability"] == "Complex-Query"


def test_parser_is_deterministic_and_cleans_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "api_resources"
    generate_api_resources(pdf_path=PDF_PATH, output_dir=output_dir)
    output_dir.joinpath("stale.json").write_text("stale", encoding="utf-8")

    first_pass = {
        path.name: _load_json(path)
        for path in sorted(output_dir.glob("*.json"))
        if path.name != "stale.json"
    }

    generate_api_resources(pdf_path=PDF_PATH, output_dir=output_dir)
    second_pass = {path.name: _load_json(path) for path in sorted(output_dir.glob("*.json"))}

    assert "stale.json" not in second_pass
    assert first_pass == second_pass
    assert all("P" not in key for item in second_pass.values() for key in item.keys())
