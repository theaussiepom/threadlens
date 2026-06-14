"""Shared debounce helper for collector events."""

from __future__ import annotations

from datetime import datetime

from threadlens.utils.time import utc_now


class EventDebouncer:
    """Suppress duplicate transition events within a debounce window."""

    def __init__(self, debounce_seconds: int) -> None:
        self._debounce_seconds = debounce_seconds
        self._last_event_at: dict[str, datetime] = {}

    def should_emit(self, key: str, now: datetime | None = None) -> bool:
        current = now or utc_now()
        previous = self._last_event_at.get(key)
        if previous is not None:
            elapsed = (current - previous).total_seconds()
            if elapsed < self._debounce_seconds:
                return False
        self._last_event_at[key] = current
        return True
