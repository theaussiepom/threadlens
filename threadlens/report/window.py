"""Report window parsing."""

from __future__ import annotations

from datetime import timedelta

SUPPORTED_WINDOWS = frozenset({"24h", "7d"})


def parse_window(window: str) -> timedelta:
    if window not in SUPPORTED_WINDOWS:
        raise ValueError(f"Unsupported window: {window}")
    if window == "24h":
        return timedelta(hours=24)
    return timedelta(days=7)
