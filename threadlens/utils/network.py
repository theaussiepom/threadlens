"""Network address helpers."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

_IPV6_LIKE = re.compile(r"(?:[0-9a-f]{0,4}:){2,}[0-9a-f:]+", re.IGNORECASE)


def normalize_ipv6(value: str | None) -> str | None:
    """Normalise an IPv6 address string for stable comparison."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "::":
        return None
    try:
        return ipaddress.IPv6Address(text).compressed.lower()
    except ValueError:
        return None


def extract_ping_ipv6(result: Any) -> str | None:
    """Extract the first successful IPv6 address from a ping_node result."""
    if not isinstance(result, dict):
        return None
    for address, ok in result.items():
        if ok and isinstance(address, str):
            normalized = normalize_ipv6(address)
            if normalized:
                return normalized
    return None


def find_ipv6_addresses(value: Any) -> list[str]:
    """Recursively collect normalised IPv6-like strings from nested data."""
    found: list[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, str):
            for match in _IPV6_LIKE.findall(item):
                normalized = normalize_ipv6(match)
                if normalized:
                    found.append(normalized)
        elif isinstance(item, dict):
            for nested in item.values():
                walk(nested)
        elif isinstance(item, list):
            for nested in item:
                walk(nested)

    walk(value)
    return found
