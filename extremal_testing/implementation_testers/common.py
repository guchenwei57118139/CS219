"""Shared helpers for NRF implementation test runners."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


def normalize_http_headers(headers: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Return headers in a form both requests and httpx accept."""
    if not headers:
        return {}

    normalized: Dict[str, str] = {}
    for key, value in headers.items():
        if value is None:
            continue
        if isinstance(value, bytes):
            normalized[key] = value.decode("latin-1", errors="replace")
        elif isinstance(value, str):
            normalized[key] = value
        else:
            normalized[key] = str(value)
    return normalized


def build_full_url(path: str, base_url: str) -> str:
    """Build a fully qualified URL from a request path and base URL."""
    if path.startswith("/nnrf-nfm/v1"):
        parsed_base = urlparse(base_url)
        return f"{parsed_base.scheme}://{parsed_base.netloc}{path}"
    if path.startswith("/"):
        return base_url.rstrip("/") + path
    return base_url.rstrip("/") + "/" + path


def load_clean_suite(test_cases_file: str, operation_name: str) -> Dict[str, Any]:
    """Load a suite object."""
    with open(test_cases_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict) and isinstance(payload.get("tests"), list):
        suite = dict(payload)
        suite.setdefault("operation", operation_name)
        suite.setdefault("setup", [])
        suite.setdefault("cleanup", [])
        return suite

    raise ValueError("Test cases file must contain a suite object with a tests array")


def validate_clean_suite(suite: Dict[str, Any]) -> None:
    """Ensure the suite uses the clean step-based schema."""
    if not isinstance(suite.get("setup", []), list):
        raise ValueError("Suite setup must be a list")
    if not isinstance(suite.get("cleanup", []), list):
        raise ValueError("Suite cleanup must be a list")

    tests = suite.get("tests", [])
    if not isinstance(tests, list):
        raise ValueError("Suite tests must be a list")

    step_required_keys = {"method", "path", "headers"}
    test_required_keys = {"name", "constraint", "method", "path", "headers"}
    forbidden_fields = {
        "request",
        "request_body",
        "resource_url",
        "url",
        "violated_constraints",
        "path_params",
        "pathParameters",
        "pathParams",
    }

    for step in suite.get("setup", []) + suite.get("cleanup", []):
        if not isinstance(step, dict):
            raise ValueError("Setup and cleanup items must be objects")
        if not step_required_keys.issubset(step.keys()):
            raise ValueError("Setup and cleanup items must include method, path, and headers")
        if forbidden_fields.intersection(step.keys()):
            raise ValueError("Suite contains unsupported step fields")

    for test_case in tests:
        if not isinstance(test_case, dict):
            raise ValueError("Test cases must be objects")
        if not test_required_keys.issubset(test_case.keys()):
            raise ValueError("Test cases must include name, constraint, method, path, and headers")
        if forbidden_fields.intersection(test_case.keys()):
            raise ValueError("Suite contains unsupported test fields")


def resolve_placeholders(value: Any, context: Dict[str, Any]) -> Any:
    """Recursively replace {placeholder} strings using the provided context."""
    if isinstance(value, str):
        resolved = value
        for key, replacement in context.items():
            if replacement is None:
                continue
            resolved = resolved.replace(f"{{{key}}}", str(replacement))
        return resolved

    if isinstance(value, list):
        return [resolve_placeholders(item, context) for item in value]

    if isinstance(value, dict):
        return {key: resolve_placeholders(item, context) for key, item in value.items()}

    return value


def seed_context_from_step(step: Dict[str, Any], context: Dict[str, Any]) -> None:
    """Seed placeholder values from a request step before execution."""
    body = step.get("body")
    if isinstance(body, dict):
        for key in ("nfInstanceId", "subscriptionId"):
            if key in body and body[key] is not None:
                context.setdefault(key, body[key])

    resource_path = str(step.get("path", ""))
    nf_match = re.search(r"/nf-instances/([^/?{}]+)", resource_path)
    if nf_match:
        context.setdefault("nfInstanceId", nf_match.group(1))

    sub_match = re.search(r"/subscriptions/([^/?{}]+)", resource_path)
    if sub_match:
        context.setdefault("subscriptionId", sub_match.group(1))


def update_context_from_response(
    context: Dict[str, Any],
    response_headers: Optional[Dict[str, Any]] = None,
    response_body_text: Optional[str] = None,
) -> None:
    """Extract identifiers from a response and store them in the execution context."""
    if response_headers:
        location = response_headers.get("Location") or response_headers.get("location") or ""
        if location:
            nf_match = re.search(r"/nf-instances/([^/?]+)", str(location))
            if nf_match:
                context["nfInstanceId"] = nf_match.group(1)

            sub_match = re.search(r"/subscriptions/([^/?]+)", str(location))
            if sub_match:
                context["subscriptionId"] = sub_match.group(1)

    if not response_body_text:
        return

    try:
        body = json.loads(response_body_text)
    except json.JSONDecodeError:
        return

    if isinstance(body, dict):
        for key in ("nfInstanceId", "subscriptionId"):
            if body.get(key):
                context[key] = body[key]


def build_request_details(
    step: Dict[str, Any],
    base_url: str,
    default_headers: Dict[str, str],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Resolve a step into concrete request details."""
    resolved_step = resolve_placeholders(step, context)
    path = str(resolved_step.get("path", ""))
    headers = normalize_http_headers({**default_headers, **resolved_step.get("headers", {})})
    request_body = resolved_step.get("body")
    return {
        "path": path,
        "full_url": build_full_url(path, base_url),
        "method": str(resolved_step.get("method", "GET")).upper(),
        "headers": headers,
        "body": request_body,
    }


def response_reason(response: Any) -> str:
    """Return a human-readable HTTP reason phrase across clients."""
    return (
        getattr(response, "reason_phrase", None)
        or getattr(response, "reason", None)
        or ""
    )


def response_headers_dict(response: Any) -> Dict[str, Any]:
    """Normalize response headers to a plain dictionary."""
    try:
        return dict(response.headers)
    except Exception:
        return {}


def response_text(response: Any) -> Optional[str]:
    """Return response text if present."""
    text = getattr(response, "text", None)
    return text if text else None
