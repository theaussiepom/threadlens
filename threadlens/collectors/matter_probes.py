"""Internal Matter read reachability probe runner (read-only).

Uses only allowlisted read-only Matter Server commands:
``read_attribute`` and ``ping_node``. No mutation or control commands.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol

from threadlens.collectors.matter_ws import MatterCommandResult
from threadlens.config import MatterProbeConfig
from threadlens.models.events import EventSeverity
from threadlens.models.state import MatterNodeState
from threadlens.utils.time import utc_now

READ_PROBE_SUCCEEDED = "matter_node.read_probe.succeeded"
READ_PROBE_FAILED = "matter_node.read_probe.failed"
READ_PROBE_TIMED_OUT = "matter_node.read_probe.timed_out"
READ_PROBE_UNSUPPORTED = "matter_node.read_probe.unsupported"
READ_PROBE_SKIPPED = "matter_node.read_probe.skipped"

PING_SUCCEEDED = "matter_node.ping.succeeded"
PING_FAILED = "matter_node.ping.failed"
PING_TIMED_OUT = "matter_node.ping.timed_out"

READ_PROBE_FAILURE_EVENT_TYPES = frozenset(
    {
        READ_PROBE_FAILED,
        READ_PROBE_TIMED_OUT,
    }
)
READ_PROBE_SUCCESS_EVENT_TYPES = frozenset({READ_PROBE_SUCCEEDED})
PING_FAILURE_EVENT_TYPES = frozenset({PING_FAILED, PING_TIMED_OUT})
PING_SUCCESS_EVENT_TYPES = frozenset({PING_SUCCEEDED})

_UNSUPPORTED_DETAILS_RE = re.compile(
    r"unsupported|not\s+support|unknown\s+attribute|invalid\s+attribute|attribute.+(?:missing|not\s+found)",
    re.IGNORECASE,
)


class MatterProbeRequester(Protocol):
    async def __call__(
        self,
        command: str,
        args: dict[str, Any],
        *,
        timeout: float,
    ) -> MatterCommandResult: ...


class MatterProbeEventEmitter(Protocol):
    async def __call__(
        self,
        *,
        node_id: int,
        event_type: str,
        message: str,
        severity: EventSeverity = EventSeverity.INFO,
        data: dict[str, Any] | None = None,
    ) -> None: ...


class MatterProbeEventCounter(Protocol):
    async def __call__(
        self,
        *,
        node_id: int,
        event_types: frozenset[str],
        since: Any,
    ) -> int: ...


@dataclass(frozen=True)
class MatterProbeRunResult:
    """Outcome of a manual/internal probe invocation."""

    node_id: int
    skipped: bool = False
    skip_reason: str | None = None
    read_probe_attempted: bool = False
    read_probe_ok: bool | None = None
    ping_attempted: bool = False
    ping_ok: bool | None = None


def is_unsupported_attribute_error(result: MatterCommandResult) -> bool:
    """Best-effort classification for unsupported attribute read failures."""
    if result.ok or result.timed_out:
        return False
    details = result.details or ""
    if _UNSUPPORTED_DETAILS_RE.search(details):
        return True
    if isinstance(result.error_code, str) and _UNSUPPORTED_DETAILS_RE.search(result.error_code):
        return True
    return False


def resolve_read_probe_attribute_path(
    *,
    attribute_keys: frozenset[str] | set[str] | None,
    device_types: list[str] | None,
    config: MatterProbeConfig,
) -> str:
    """Choose a node-type-specific attribute path when known, else fallback."""
    window_paths = config.attributes.window_covering
    fallback_paths = config.attributes.fallback

    is_window_covering = False
    if device_types:
        lowered = {item.strip().lower() for item in device_types if item}
        is_window_covering = any("window covering" in item for item in lowered)
    if not is_window_covering and attribute_keys:
        is_window_covering = any(key.startswith("1/258/") for key in attribute_keys)

    if is_window_covering and window_paths:
        return window_paths[0]
    if fallback_paths:
        return fallback_paths[0]
    return "0/40/5"


def _error_summary(result: MatterCommandResult) -> str | None:
    if result.ok:
        return None
    if result.timed_out:
        return "TimedOut"
    if result.details:
        return result.details
    if result.error_code is not None:
        return str(result.error_code)
    return None


class MatterProbeRunner:
    """Perform a single read reachability probe for one Matter node."""

    def __init__(
        self,
        *,
        server_id: str,
        config: MatterProbeConfig,
        request_command: MatterProbeRequester,
        emit_event: MatterProbeEventEmitter,
        count_events: MatterProbeEventCounter,
        get_node: Callable[[int], MatterNodeState | None],
        get_attribute_keys: Callable[[int], frozenset[str] | None],
        is_connected: Callable[[], bool],
        persist_node: Callable[[MatterNodeState], Awaitable[None]],
    ) -> None:
        self._server_id = server_id
        self._config = config
        self._request_command = request_command
        self._emit_event = emit_event
        self._count_events = count_events
        self._get_node = get_node
        self._get_attribute_keys = get_attribute_keys
        self._is_connected = is_connected
        self._persist_node = persist_node

    async def run_manual_probe(
        self,
        node_id: int,
        *,
        device_types: list[str] | None = None,
        include_ping: bool | None = None,
    ) -> MatterProbeRunResult:
        """Run one read probe (and optional ping) for a single node."""
        if not self._config.manual_enabled:
            return await self._skip(node_id, "manual probes disabled")
        return await self._run_probe_for_node(
            node_id,
            device_types=device_types,
            include_ping=include_ping,
        )

    async def run_scheduled_probe(
        self,
        node_id: int,
        *,
        include_ping: bool | None = None,
    ) -> MatterProbeRunResult:
        """Run a scheduled read probe when probes are explicitly enabled."""
        if not self._config.enabled:
            return await self._skip(node_id, "probes disabled")
        if not self._config.schedule_enabled:
            return await self._skip(node_id, "scheduled probes disabled")
        return await self._run_probe_for_node(node_id, include_ping=include_ping)

    async def _run_probe_for_node(
        self,
        node_id: int,
        *,
        device_types: list[str] | None = None,
        include_ping: bool | None = None,
    ) -> MatterProbeRunResult:
        node = self._get_node(node_id)
        if node is None:
            return await self._skip(node_id, "node not known")

        if not self._is_connected():
            return await self._skip(node_id, "matter server not connected")

        if not node.available:
            return await self._skip(node_id, "node unavailable")

        timeout = self._config.timeout_seconds
        attribute_path = resolve_read_probe_attribute_path(
            attribute_keys=self._get_attribute_keys(node_id),
            device_types=device_types,
            config=self._config,
        )

        read_result = await self._run_read_probe(
            node=node,
            attribute_path=attribute_path,
            timeout=timeout,
        )

        ping_attempted = False
        ping_ok: bool | None = None
        should_ping = include_ping if include_ping is not None else self._config.ping_enabled
        if should_ping:
            ping_attempted = True
            ping_ok = await self._run_ping(node=node, timeout=timeout)

        return MatterProbeRunResult(
            node_id=node_id,
            read_probe_attempted=True,
            read_probe_ok=read_result,
            ping_attempted=ping_attempted,
            ping_ok=ping_ok,
        )

    async def _skip(self, node_id: int, reason: str) -> MatterProbeRunResult:
        await self._emit_event(
            node_id=node_id,
            event_type=READ_PROBE_SKIPPED,
            message=f"Read probe skipped for Matter node {node_id} on {self._server_id}",
            severity=EventSeverity.INFO,
            data={
                "node_id": node_id,
                "probe_type": "read_attribute",
                "skip_reason": reason,
            },
        )
        return MatterProbeRunResult(node_id=node_id, skipped=True, skip_reason=reason)

    async def _run_read_probe(
        self,
        *,
        node: MatterNodeState,
        attribute_path: str,
        timeout: float,
    ) -> bool:
        now = utc_now()
        command_result = await self._request_command(
            "read_attribute",
            {"node_id": node.node_id, "attribute_path": attribute_path},
            timeout=timeout,
        )

        limited = False
        if command_result.timed_out:
            event_type = READ_PROBE_TIMED_OUT
            message = f"Read probe timed out for Matter node {node.node_id} on {self._server_id}"
            severity = EventSeverity.WARNING
            ok = False
        elif command_result.ok:
            event_type = READ_PROBE_SUCCEEDED
            message = f"Read probe succeeded for Matter node {node.node_id} on {self._server_id}"
            severity = EventSeverity.INFO
            ok = True
        elif is_unsupported_attribute_error(command_result):
            event_type = READ_PROBE_UNSUPPORTED
            message = f"Read probe unsupported for Matter node {node.node_id} on {self._server_id}"
            severity = EventSeverity.WARNING
            ok = False
            limited = True
        else:
            event_type = READ_PROBE_FAILED
            message = f"Read probe failed for Matter node {node.node_id} on {self._server_id}"
            severity = EventSeverity.WARNING
            ok = False

        since = now - timedelta(hours=24)
        failures_24h = await self._count_events(
            node_id=node.node_id,
            event_types=READ_PROBE_FAILURE_EVENT_TYPES,
            since=since,
        )
        successes_24h = await self._count_events(
            node_id=node.node_id,
            event_types=READ_PROBE_SUCCESS_EVENT_TYPES,
            since=since,
        )
        if ok:
            successes_24h += 1
        elif not limited:
            failures_24h += 1

        updated = node.model_copy(
            update={
                "read_probe_diagnostics_available": True,
                "last_read_probe_at": now,
                "last_read_probe_ok": None if limited else ok,
                "last_read_probe_limited": limited,
                "last_read_probe_attribute_path": attribute_path,
                "last_read_probe_duration_ms": command_result.duration_ms,
                "last_read_probe_error_code": None if ok or limited else command_result.error_code,
                "read_probe_failures_24h": failures_24h,
                "read_probe_successes_24h": successes_24h,
            }
        )
        await self._persist_node(updated)

        await self._emit_event(
            node_id=node.node_id,
            event_type=event_type,
            message=message,
            severity=severity,
            data={
                "node_id": node.node_id,
                "probe_type": "read_attribute",
                "attribute_path": attribute_path,
                "duration_ms": command_result.duration_ms,
                "error_code": command_result.error_code,
                "error_summary": _error_summary(command_result),
            },
        )
        return ok

    async def _run_ping(self, *, node: MatterNodeState, timeout: float) -> bool:
        now = utc_now()
        command_result = await self._request_command(
            "ping_node",
            {"node_id": node.node_id},
            timeout=timeout,
        )

        if command_result.timed_out:
            event_type = PING_TIMED_OUT
            message = f"Ping timed out for Matter node {node.node_id} on {self._server_id}"
            severity = EventSeverity.WARNING
            ok = False
        elif command_result.ok:
            event_type = PING_SUCCEEDED
            message = f"Ping succeeded for Matter node {node.node_id} on {self._server_id}"
            severity = EventSeverity.INFO
            ok = True
        else:
            event_type = PING_FAILED
            message = f"Ping failed for Matter node {node.node_id} on {self._server_id}"
            severity = EventSeverity.WARNING
            ok = False

        since = now - timedelta(hours=24)
        failures_24h = await self._count_events(
            node_id=node.node_id,
            event_types=PING_FAILURE_EVENT_TYPES,
            since=since,
        )
        successes_24h = await self._count_events(
            node_id=node.node_id,
            event_types=PING_SUCCESS_EVENT_TYPES,
            since=since,
        )
        if not ok:
            failures_24h += 1
        else:
            successes_24h += 1

        updated = node.model_copy(
            update={
                "ping_diagnostics_available": True,
                "last_ping_at": now,
                "last_ping_ok": ok,
                "ping_failures_24h": failures_24h,
                "ping_successes_24h": successes_24h,
            }
        )
        await self._persist_node(updated)

        await self._emit_event(
            node_id=node.node_id,
            event_type=event_type,
            message=message,
            severity=severity,
            data={
                "node_id": node.node_id,
                "probe_type": "ping_node",
                "duration_ms": command_result.duration_ms,
                "error_code": command_result.error_code,
                "error_summary": _error_summary(command_result),
            },
        )
        return ok
