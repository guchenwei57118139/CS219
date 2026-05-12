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


def build_full_url(resource_url: str, base_url: str) -> str:
    """Build a fully qualified URL from a resource URL and base URL."""
    if resource_url.startswith("/nnrf-nfm/v1"):
        parsed_base = urlparse(base_url)
        return f"{parsed_base.scheme}://{parsed_base.netloc}{resource_url}"
    if resource_url.startswith("/"):
        return base_url.rstrip("/") + resource_url
    return base_url.rstrip("/") + "/" + resource_url


def load_suite_or_legacy_tests(test_cases_file: str, operation_name: str) -> Dict[str, Any]:
    """Load a suite object or a legacy flat test array."""
    with open(test_cases_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict) and isinstance(payload.get("tests"), list):
        suite = dict(payload)
        suite.setdefault("operation", operation_name)
        suite.setdefault("setup", [])
        suite.setdefault("cleanup", [])
        return suite

    if isinstance(payload, list):
        return {
            "operation": operation_name,
            "path": "",
            "method": "",
            "setup": [],
            "cleanup": [],
            "tests": payload,
        }

    raise ValueError("Test cases file must contain either a suite object or a JSON array")


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
    request_body = step.get("request_body")
    if isinstance(request_body, dict):
        for key in ("nfInstanceId", "subscriptionId"):
            if key in request_body and request_body[key] is not None:
                context.setdefault(key, request_body[key])

    resource_url = str(step.get("resource_url", ""))
    nf_match = re.search(r"/nf-instances/([^/?]+)", resource_url)
    if nf_match:
        context.setdefault("nfInstanceId", nf_match.group(1))

    sub_match = re.search(r"/subscriptions/([^/?]+)", resource_url)
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
    resource_url = str(resolved_step.get("resource_url", ""))
    headers = normalize_http_headers({**default_headers, **resolved_step.get("headers", {})})
    request_body = resolved_step.get("request_body")
    return {
        "resource_url": resource_url,
        "full_url": build_full_url(resource_url, base_url),
        "method": str(resolved_step.get("method", "GET")).upper(),
        "headers": headers,
        "request_body": request_body,
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

