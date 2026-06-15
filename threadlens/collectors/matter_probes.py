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

from threadlens.collectors.matter_probe_planner import (
    MatterProbePlanner,
    ProbeCandidate,
    first_probe_candidate,
)
from threadlens.collectors.matter_ws import MatterCommandResult
from threadlens.config import MatterProbeConfig, ProbeMode
from threadlens.models.events import EventSeverity
from threadlens.models.state import MatterNodeState
from threadlens.utils.network import extract_ping_ipv6
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

_READ_PROBE_LIMITED_NOTE = (
    "ThreadLens tried several read-only Matter attributes but could not find one this device "
    "accepts. Identical devices can use different Matter endpoints; unsupported paths are "
    "remembered and skipped on future probes."
)

_GENERIC_WEIGHTS = frozenset({"generic", "override"})


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


@dataclass(frozen=True)
class _ProbeAttemptOutcome:
    ok: bool | None
    limited: bool
    candidate: ProbeCandidate
    command_result: MatterCommandResult


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
    node: MatterNodeState | None = None,
) -> str:
    """Return the first planned probe path for compatibility helpers."""
    del device_types
    probe_node = node or MatterNodeState(node_id=0, server_id="")
    candidate = first_probe_candidate(
        node=probe_node,
        attribute_keys=frozenset(attribute_keys or []),
        config=config,
    )
    if candidate is not None:
        return candidate.attribute_path
    return config.attributes.fallback[0] if config.attributes.fallback else "0/40/2"


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


def _is_generic_candidate(candidate: ProbeCandidate) -> bool:
    return candidate.health_weight in _GENERIC_WEIGHTS


class MatterProbeRunner:
    """Perform read reachability probes for one Matter node."""

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
        planner: MatterProbePlanner | None = None,
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
        self._planner = planner or MatterProbePlanner()

    async def run_manual_probe(
        self,
        node_id: int,
        *,
        device_types: list[str] | None = None,
        include_ping: bool | None = None,
    ) -> MatterProbeRunResult:
        """Run one read probe (and optional ping) for a single node."""
        del device_types
        if not self._config.manual_enabled:
            return await self._skip(node_id, "manual probes disabled")
        if not self._config.probes_active:
            return await self._skip(node_id, "probes disabled")
        return await self._run_probe_for_node(
            node_id,
            include_ping=include_ping,
        )

    async def run_thread_identity_capture(self, node_id: int) -> MatterNodeState | None:
        """Capture Thread IPv6 for one node via read-only ping_node."""
        if not self._config.probes_active:
            return None
        if not self._is_connected():
            return None
        node = self._get_node(node_id)
        if node is None or not node.available:
            return None
        timeout = self._config.timeout_seconds
        _, updated = await self._run_ping(
            node=node,
            timeout=timeout,
            update_ping_diagnostics=False,
            capture_thread_identity=True,
        )
        await self._persist_node(updated)
        return updated

    async def run_scheduled_probe(
        self,
        node_id: int,
        *,
        include_ping: bool | None = None,
    ) -> MatterProbeRunResult:
        """Run a scheduled read probe when probes are explicitly enabled."""
        if not self._config.probes_active:
            return await self._skip(node_id, "probes disabled")
        if not self._config.schedule_enabled:
            return await self._skip(node_id, "scheduled probes disabled")
        return await self._run_probe_for_node(node_id, include_ping=include_ping)

    async def _run_probe_for_node(
        self,
        node_id: int,
        *,
        include_ping: bool | None = None,
    ) -> MatterProbeRunResult:
        node = self._get_node(node_id)
        if node is None:
            return await self._skip(node_id, "node not known")

        if not self._is_connected():
            return await self._skip(node_id, "matter server not connected")

        if not node.available:
            return await self._skip(node_id, "node unavailable")

        candidates = self._planner.plan(
            node,
            attribute_keys=self._get_attribute_keys(node_id),
            config=self._config,
        )
        if not candidates:
            return await self._skip(node_id, "no probe candidates")

        timeout = self._config.timeout_seconds
        outcomes = []
        for candidate in candidates:
            outcome = await self._attempt_read_probe(
                node=node,
                candidate=candidate,
                timeout=timeout,
            )
            outcomes.append(outcome)
            node = self._get_node(node_id) or node

            if outcome.limited:
                continue
            if outcome.ok and candidate.health_weight == "device_specific":
                break
            if outcome.ok and _is_generic_candidate(candidate):
                if self._config.effective_mode == ProbeMode.CONSERVATIVE:
                    break
                continue
            if outcome.ok is False and candidate.health_weight == "device_specific":
                continue
            if outcome.ok is False and _is_generic_candidate(candidate):
                continue

        node = self._get_node(node_id) or node
        final = self._aggregate_probe_outcomes(node, outcomes)
        await self._persist_node(final)

        ping_attempted = False
        ping_ok: bool | None = None
        should_capture_identity = self._config.probes_active
        should_ping_diagnostics = (
            include_ping if include_ping is not None else self._config.ping_enabled
        )
        if should_capture_identity or should_ping_diagnostics:
            ping_attempted = True
            ping_ok, final = await self._run_ping(
                node=final,
                timeout=timeout,
                update_ping_diagnostics=should_ping_diagnostics,
                capture_thread_identity=should_capture_identity,
            )
            await self._persist_node(final)

        return MatterProbeRunResult(
            node_id=node_id,
            read_probe_attempted=True,
            read_probe_ok=final.last_read_probe_ok,
            ping_attempted=ping_attempted,
            ping_ok=ping_ok,
        )

    def _aggregate_probe_outcomes(
        self,
        node: MatterNodeState,
        outcomes: list[_ProbeAttemptOutcome],
    ) -> MatterNodeState:
        if not outcomes:
            return node

        device_specific_success = next(
            (
                outcome
                for outcome in outcomes
                if outcome.ok is True and outcome.candidate.health_weight == "device_specific"
            ),
            None,
        )
        generic_success = next(
            (
                outcome
                for outcome in outcomes
                if outcome.ok is True and _is_generic_candidate(outcome.candidate)
            ),
            None,
        )
        generic_failure = next(
            (
                outcome
                for outcome in outcomes
                if outcome.ok is False and _is_generic_candidate(outcome.candidate)
            ),
            None,
        )
        device_specific_unsupported = any(
            outcome.limited and outcome.candidate.health_weight == "device_specific"
            for outcome in outcomes
        )
        device_specific_failure = any(
            outcome.ok is False
            and not outcome.limited
            and outcome.candidate.health_weight == "device_specific"
            for outcome in outcomes
        )

        final_outcome = outcomes[-1]
        if device_specific_success is not None:
            final_outcome = device_specific_success
            last_ok: bool | None = True
            limited = False
            note = None
        elif generic_success is not None:
            final_outcome = generic_success
            last_ok = True
            limited = device_specific_unsupported or device_specific_failure
            note = None
            if device_specific_unsupported:
                note = (
                    "A device-specific read check was not supported on this device, but a "
                    "basic read check succeeded."
                )
            elif device_specific_failure:
                note = (
                    "A device-specific read check did not complete, but the device responded "
                    "to a basic read check."
                )
        elif generic_failure is not None:
            final_outcome = generic_failure
            last_ok = False
            limited = False
            note = None
        else:
            last_ok = None if final_outcome.limited else final_outcome.ok
            limited = final_outcome.limited
            note = _READ_PROBE_LIMITED_NOTE if limited else None

        unsupported_paths = list(node.last_unsupported_probe_paths or [])
        for outcome in outcomes:
            if outcome.limited and outcome.candidate.attribute_path not in unsupported_paths:
                unsupported_paths.append(outcome.candidate.attribute_path)

        update: dict[str, Any] = {
            "last_read_probe_ok": last_ok,
            "last_read_probe_limited": limited,
            "last_read_probe_attribute_path": final_outcome.candidate.attribute_path,
            "last_read_probe_duration_ms": final_outcome.command_result.duration_ms,
            "last_read_probe_error_code": (
                None if last_ok is True or limited else final_outcome.command_result.error_code
            ),
            "last_probe_label": final_outcome.candidate.label,
            "last_unsupported_probe_paths": unsupported_paths or None,
            "last_read_probe_note": note,
        }
        if last_ok is True:
            update["last_successful_probe_kind"] = final_outcome.candidate.kind
            update["last_successful_probe_path"] = final_outcome.candidate.attribute_path

        return node.model_copy(update=update)

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

    async def _attempt_read_probe(
        self,
        *,
        node: MatterNodeState,
        candidate: ProbeCandidate,
        timeout: float,
    ) -> _ProbeAttemptOutcome:
        now = utc_now()
        command_result = await self._request_command(
            "read_attribute",
            {"node_id": node.node_id, "attribute_path": candidate.attribute_path},
            timeout=timeout,
        )

        limited = False
        if command_result.timed_out:
            event_type = READ_PROBE_TIMED_OUT
            message = f"Read probe timed out for Matter node {node.node_id} on {self._server_id}"
            severity = EventSeverity.WARNING
            ok: bool | None = False
        elif command_result.ok:
            event_type = READ_PROBE_SUCCEEDED
            message = f"Read probe succeeded for Matter node {node.node_id} on {self._server_id}"
            severity = EventSeverity.INFO
            ok = True
        elif is_unsupported_attribute_error(command_result):
            event_type = READ_PROBE_UNSUPPORTED
            message = f"Read probe unsupported for Matter node {node.node_id} on {self._server_id}"
            severity = EventSeverity.WARNING
            ok = None
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
        counts_generic_failure = ok is False and _is_generic_candidate(candidate)
        if ok is True:
            successes_24h += 1
        elif counts_generic_failure:
            failures_24h += 1

        updated = node.model_copy(
            update={
                "read_probe_diagnostics_available": True,
                "last_read_probe_at": now,
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
                "probe_kind": candidate.kind,
                "probe_label": candidate.label,
                "attribute_path": candidate.attribute_path,
                "duration_ms": command_result.duration_ms,
                "error_code": command_result.error_code,
                "error_summary": _error_summary(command_result),
            },
        )
        return _ProbeAttemptOutcome(
            ok=ok,
            limited=limited,
            candidate=candidate,
            command_result=command_result,
        )

    async def _run_ping(
        self,
        *,
        node: MatterNodeState,
        timeout: float,
        update_ping_diagnostics: bool,
        capture_thread_identity: bool,
    ) -> tuple[bool | None, MatterNodeState]:
        now = utc_now()
        command_result = await self._request_command(
            "ping_node",
            {"node_id": node.node_id},
            timeout=timeout,
        )
        ipv6 = extract_ping_ipv6(command_result.result)

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

        updates: dict[str, Any] = {}
        if capture_thread_identity:
            updates.update(
                {
                    "thread_ipv6_address": ipv6,
                    "thread_identity_last_at": now if ipv6 else node.thread_identity_last_at,
                }
            )

        if update_ping_diagnostics:
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
            updates.update(
                {
                    "ping_diagnostics_available": True,
                    "last_ping_at": now,
                    "last_ping_ok": ok,
                    "ping_failures_24h": failures_24h,
                    "ping_successes_24h": successes_24h,
                }
            )
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
                    "thread_ipv6_address": ipv6,
                },
            )

        updated = node.model_copy(update=updates) if updates else node
        if update_ping_diagnostics:
            await self._persist_node(updated)
        return ok, updated
