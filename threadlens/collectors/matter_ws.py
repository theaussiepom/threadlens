"""Matter Server websocket request/response correlation (read-only plumbing)."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

MAX_ERROR_DETAILS_LEN = 200


@dataclass(frozen=True)
class MatterCommandResult:
    """Result of a correlated Matter Server websocket command."""

    ok: bool
    result: Any | None = None
    error_code: int | str | None = None
    details: str | None = None
    duration_ms: int | None = None
    timed_out: bool = False


def sanitize_error_details(details: Any | None) -> str | None:
    """Truncate error details for safe storage and logs."""
    if details is None:
        return None
    text = str(details).strip()
    if not text:
        return None
    if len(text) <= MAX_ERROR_DETAILS_LEN:
        return text
    return f"{text[:MAX_ERROR_DETAILS_LEN]}..."


class MatterWebsocketRequestManager:
    """Correlate Matter Server websocket responses by ``message_id``.

    Passive observer traffic (for example ``start_listening`` inventory dumps)
    is not registered here and falls through to the existing handler.
    """

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[MatterCommandResult]] = {}
        self._registered_at: dict[str, float] = {}

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def register(self, message_id: str) -> None:
        """Register a pending request before the command is sent."""
        if not message_id:
            raise ValueError("message_id must not be empty")
        if message_id in self._pending:
            raise ValueError(f"Duplicate message_id: {message_id!r}")
        loop = asyncio.get_running_loop()
        self._pending[message_id] = loop.create_future()
        self._registered_at[message_id] = time.monotonic()

    async def wait_for(self, message_id: str, *, timeout: float) -> MatterCommandResult:
        """Wait for a correlated response or timeout."""
        future = self._pending.get(message_id)
        if future is None:
            raise KeyError(message_id)
        started = self._registered_at.get(message_id, time.monotonic())
        try:
            result = await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
            if result.duration_ms is None:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                return MatterCommandResult(
                    ok=result.ok,
                    result=result.result,
                    error_code=result.error_code,
                    details=result.details,
                    duration_ms=elapsed_ms,
                    timed_out=result.timed_out,
                )
            return result
        except TimeoutError:
            self._discard(message_id, cancel_future=True)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return MatterCommandResult(ok=False, timed_out=True, duration_ms=elapsed_ms)
        finally:
            self._discard(message_id, cancel_future=False)

    def dispatch_incoming(self, payload: dict[str, Any]) -> bool:
        """Return True when the payload resolved a registered pending request."""
        message_id = payload.get("message_id")
        if not isinstance(message_id, str):
            return False

        future = self._pending.get(message_id)
        if future is None:
            return False

        started = self._registered_at.get(message_id, time.monotonic())
        elapsed_ms = int((time.monotonic() - started) * 1000)

        if "result" in payload:
            if not future.done():
                future.set_result(
                    MatterCommandResult(
                        ok=True,
                        result=payload.get("result"),
                        duration_ms=elapsed_ms,
                    )
                )
            self._discard(message_id, cancel_future=False)
            return True

        if "error_code" in payload:
            if not future.done():
                future.set_result(
                    MatterCommandResult(
                        ok=False,
                        error_code=payload.get("error_code"),
                        details=sanitize_error_details(payload.get("details")),
                        duration_ms=elapsed_ms,
                    )
                )
            self._discard(message_id, cancel_future=False)
            return True

        return False

    def cancel_all(self, *, reason: str | None = None) -> None:
        """Cancel or fail all pending requests (for example on disconnect)."""
        detail = sanitize_error_details(reason) or "disconnected"
        for message_id in list(self._pending):
            future = self._pending.get(message_id)
            if future is not None and not future.done():
                started = self._registered_at.get(message_id, time.monotonic())
                elapsed_ms = int((time.monotonic() - started) * 1000)
                future.set_result(
                    MatterCommandResult(
                        ok=False,
                        details=detail,
                        duration_ms=elapsed_ms,
                    )
                )
            self._discard(message_id, cancel_future=False)

    def _discard(self, message_id: str, *, cancel_future: bool) -> None:
        future = self._pending.pop(message_id, None)
        self._registered_at.pop(message_id, None)
        if cancel_future and future is not None and not future.done():
            future.cancel()
