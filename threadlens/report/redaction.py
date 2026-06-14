"""Recursive report redaction helpers."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "REDACTED"

SECRET_KEY_PATTERNS = (
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"passwd", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"pskc", re.IGNORECASE),
    re.compile(r"network[_-]?key", re.IGNORECASE),
    re.compile(r"networkkey", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
    re.compile(r"bearer", re.IGNORECASE),
    re.compile(r"authorization", re.IGNORECASE),
    re.compile(r"^auth$", re.IGNORECASE),
    re.compile(r"^key$", re.IGNORECASE),
)

SAFE_KEY_NAMES = frozenset(
    {
        "ext_pan_id",
        "extended_pan_id",
        "object_id",
        "unique_id",
        "subject_id",
        "node_id",
        "service_id",
        "product_id",
        "vendor_id",
        "cluster_id",
        "attribute_id",
        "endpoint_id",
        "event_type",
        "message_id",
        "api/node",
    }
)

DEFAULT_SECRETS_REMOVED = [
    "Thread network key",
    "PSKc",
    "Matter fabric secrets",
    "Wi-Fi credentials",
    "Home Assistant tokens",
    "API tokens",
    "MQTT password",
    "Bearer tokens",
]


def _should_redact_key(key: str) -> bool:
    if key in SAFE_KEY_NAMES:
        return False
    return any(pattern.search(key) for pattern in SECRET_KEY_PATTERNS)


def redact_structure(value: Any) -> Any:
    """Recursively redact secret-like keys in dict/list structures."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _should_redact_key(str(key)):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_structure(item)
        return redacted
    if isinstance(value, list):
        return [redact_structure(item) for item in value]
    return value
