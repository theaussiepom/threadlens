"""Tests for Matter read reachability probe foundation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from tests.test_matter_collector import (
    SERVER,
    FakeWebsocket,
    _make_repo,
    _node_events,
    _node_payload,
)
from threadlens.collectors.matter_probes import (
    PING_FAILED,
    PING_SUCCEEDED,
    READ_PROBE_FAILED,
    READ_PROBE_SKIPPED,
    READ_PROBE_SUCCEEDED,
    READ_PROBE_TIMED_OUT,
    READ_PROBE_UNSUPPORTED,
    is_unsupported_attribute_error,
    resolve_read_probe_attribute_path,
)
from threadlens.collectors.matter_server import MatterServerObserver
from threadlens.collectors.matter_ws import MatterCommandResult
from threadlens.config import (
    MatterPollingConfig,
    MatterProbeAdvancedConfig,
    MatterProbeAttributesConfig,
    MatterProbeConfig,
    ProbeMode,
    ThreadLensConfig,
)
from threadlens.models.state import MatterNodeState


def _probe_config(**overrides: Any) -> MatterPollingConfig:
    probe_overrides = {
        key: value for key, value in overrides.items() if key in MatterProbeConfig.model_fields
    }
    if "mode" not in probe_overrides:
        probe_overrides["mode"] = ProbeMode.CONSERVATIVE
    if "advanced" not in probe_overrides:
        probe_overrides["advanced"] = MatterProbeAdvancedConfig(
            attributes=MatterProbeAttributesConfig(fallback=["0/40/5"])
        )
    probes = MatterProbeConfig(**probe_overrides)
    base = {"probes": probes, **{k: v for k, v in overrides.items() if k == "matter"}}
    return MatterPollingConfig(**base)


async def _observer_with_node(
    tmp_path: Path,
    *,
    node_id: int = 24,
    available: bool = True,
    attribute_keys: list[str] | None = None,
    probes: MatterProbeConfig | None = None,
) -> MatterServerObserver:
    repository = await _make_repo(tmp_path)
    matter = _probe_config() if probes is None else MatterPollingConfig(probes=probes)
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        flapping={"debounce_seconds": 0},
        mdns={"enabled": False},
        matter=matter,
        matter_servers=[SERVER],
    )
    observer = MatterServerObserver(config, SERVER, repository)
    payload = _node_payload(node_id, available=available, label="Living Blind 3")
    if attribute_keys is not None:
        payload["attributes"] = {key: "cached" for key in attribute_keys}
    await observer._process_node(payload)
    observer._websocket = FakeWebsocket([])
    observer.connected = True
    return observer


async def _wait_for_command(observer: MatterServerObserver, command: str) -> dict[str, Any]:
    for _ in range(200):
        await asyncio.sleep(0.01)
        websocket = observer._websocket
        if websocket is not None:
            matching = [message for message in websocket.sent if message.get("command") == command]
            if matching:
                return matching[-1]
    raise AssertionError(f"Expected command {command!r} to be sent")


async def _dispatch_command(
    observer: MatterServerObserver,
    command: str,
    *,
    result: Any | None = None,
    error_code: int | str | None = None,
    details: str | None = None,
) -> dict[str, Any]:
    sent = await _wait_for_command(observer, command)
    payload: dict[str, Any] = {"message_id": sent["message_id"]}
    if result is not None:
        payload["result"] = result
    if error_code is not None:
        payload["error_code"] = error_code
    if details is not None:
        payload["details"] = details
    observer._requests.dispatch_incoming(payload)
    return sent


async def _dispatch_last_command(
    observer: MatterServerObserver,
    *,
    result: Any | None = None,
    error_code: int | str | None = None,
    details: str | None = None,
) -> dict[str, Any]:
    websocket = observer._websocket
    assert websocket is not None
    assert websocket.sent
    sent = websocket.sent[-1]
    payload: dict[str, Any] = {"message_id": sent["message_id"]}
    if result is not None:
        payload["result"] = result
    if error_code is not None:
        payload["error_code"] = error_code
    if details is not None:
        payload["details"] = details
    observer._requests.dispatch_incoming(payload)
    return sent


@pytest.mark.asyncio
async def test_read_probe_success_updates_node_state(tmp_path: Path) -> None:
    observer = await _observer_with_node(tmp_path)

    probe_task = asyncio.create_task(observer.run_manual_read_probe(24))
    await asyncio.sleep(0)
    sent = await _dispatch_last_command(observer, result={"0/40/5": "Living Blind 3"})
    result = await probe_task

    assert result.read_probe_attempted is True
    assert result.read_probe_ok is True
    assert sent["command"] == "read_attribute"
    assert sent["args"]["attribute_path"] == "0/40/5"

    state = observer._nodes[24]
    assert state.last_read_probe_ok is True
    assert state.read_probe_diagnostics_available is True
    assert state.last_read_probe_attribute_path == "0/40/5"
    assert state.read_probe_successes_24h == 1
    assert state.read_probe_failures_24h == 0

    events = await _node_events(observer, 24)
    succeeded = [event for event in events if event.event_type == READ_PROBE_SUCCEEDED]
    assert len(succeeded) == 1
    assert "Read probe succeeded" in succeeded[0].message
    assert "command failed" not in succeeded[0].message.lower()
    assert succeeded[0].data["probe_type"] == "read_attribute"


@pytest.mark.asyncio
async def test_read_probe_failure_updates_node_state(tmp_path: Path) -> None:
    observer = await _observer_with_node(tmp_path)

    probe_task = asyncio.create_task(observer.run_manual_read_probe(24))
    await asyncio.sleep(0)
    await _dispatch_last_command(observer, error_code=3, details="NodeNotReady")
    result = await probe_task

    assert result.read_probe_ok is False
    state = observer._nodes[24]
    assert state.last_read_probe_ok is False
    assert state.read_probe_failures_24h == 1
    assert state.read_probe_successes_24h == 0
    assert state.last_read_probe_error_code == 3

    events = await _node_events(observer, 24)
    failed = [event for event in events if event.event_type == READ_PROBE_FAILED]
    assert len(failed) == 1
    assert "Read probe failed" in failed[0].message


@pytest.mark.asyncio
async def test_read_probe_timeout_records_timed_out_event(tmp_path: Path) -> None:
    probes = MatterProbeConfig(
        mode=ProbeMode.CONSERVATIVE,
        advanced=MatterProbeAdvancedConfig(
            timeout_seconds=0.05,
            attributes=MatterProbeAttributesConfig(fallback=["0/40/5"]),
        ),
    )
    observer = await _observer_with_node(tmp_path, probes=probes)

    result = await observer.run_manual_read_probe(24)

    assert result.read_probe_ok is False
    state = observer._nodes[24]
    assert state.last_read_probe_ok is False
    assert state.read_probe_failures_24h == 1

    events = await _node_events(observer, 24)
    timed_out = [event for event in events if event.event_type == READ_PROBE_TIMED_OUT]
    assert len(timed_out) == 1
    assert "timed out" in timed_out[0].message.lower()


@pytest.mark.asyncio
async def test_read_probe_unsupported_attribute_event(tmp_path: Path) -> None:
    observer = await _observer_with_node(tmp_path)

    probe_task = asyncio.create_task(observer.run_manual_read_probe(24))
    await asyncio.sleep(0)
    await _dispatch_last_command(
        observer,
        error_code=7,
        details="Unsupported attribute path 0/40/5",
    )
    result = await probe_task

    assert result.read_probe_ok is None
    state = observer._nodes[24]
    assert state.last_read_probe_ok is None
    assert state.last_read_probe_limited is True
    assert state.read_probe_failures_24h == 0
    events = await _node_events(observer, 24)
    unsupported = [event for event in events if event.event_type == READ_PROBE_UNSUPPORTED]
    assert len(unsupported) == 1
    assert "unsupported" in unsupported[0].message.lower()


@pytest.mark.asyncio
async def test_unavailable_node_records_skipped(tmp_path: Path) -> None:
    observer = await _observer_with_node(tmp_path, available=False)

    result = await observer.run_manual_read_probe(24)

    assert result.skipped is True
    assert result.skip_reason == "node unavailable"
    events = await _node_events(observer, 24)
    skipped = [event for event in events if event.event_type == READ_PROBE_SKIPPED]
    assert len(skipped) == 1


@pytest.mark.asyncio
async def test_ping_success_and_failure_update_ping_fields(tmp_path: Path) -> None:
    probes = MatterProbeConfig(
        mode=ProbeMode.CONSERVATIVE,
        advanced=MatterProbeAdvancedConfig(
            ping_enabled=True,
            attributes=MatterProbeAttributesConfig(fallback=["0/40/5"]),
        ),
    )
    observer = await _observer_with_node(tmp_path, probes=probes)

    probe_task = asyncio.create_task(observer.run_manual_read_probe(24))
    await _dispatch_command(observer, "read_attribute", result={"0/40/5": "Living Blind 3"})
    await _dispatch_command(observer, "ping_node", result=True)
    result = await probe_task

    assert result.ping_attempted is True
    assert result.ping_ok is True
    state = observer._nodes[24]
    assert state.ping_diagnostics_available is True
    assert state.last_ping_ok is True
    assert state.ping_successes_24h == 1
    assert state.ping_failures_24h == 0

    observer._websocket = FakeWebsocket([])
    probe_task = asyncio.create_task(observer.run_manual_read_probe(24, include_ping=True))
    await _dispatch_command(observer, "read_attribute", result={"0/40/5": "Living Blind 3"})
    await _dispatch_command(observer, "ping_node", error_code=4, details="NodeNotResolving")
    await probe_task

    state = observer._nodes[24]
    assert state.last_ping_ok is False
    assert state.ping_failures_24h == 1
    events = await _node_events(observer, 24)
    assert any(event.event_type == PING_SUCCEEDED for event in events)
    assert any(event.event_type == PING_FAILED for event in events)


@pytest.mark.asyncio
async def test_24h_counters_distinguish_none_vs_zero(tmp_path: Path) -> None:
    observer = await _observer_with_node(tmp_path)
    initial = observer._nodes[24]
    assert initial.read_probe_failures_24h is None
    assert initial.read_probe_successes_24h is None

    probe_task = asyncio.create_task(observer.run_manual_read_probe(24))
    await asyncio.sleep(0)
    await _dispatch_last_command(observer, result={"0/40/5": "Living Blind 3"})
    await probe_task

    updated = observer._nodes[24]
    assert updated.read_probe_successes_24h == 1
    assert updated.read_probe_failures_24h == 0


@pytest.mark.asyncio
async def test_window_covering_attribute_path_selection(tmp_path: Path) -> None:
    probes = MatterProbeConfig(
        mode=ProbeMode.STANDARD,
        advanced=MatterProbeAdvancedConfig(
            attributes=MatterProbeAttributesConfig(fallback=["0/40/5"])
        ),
    )
    observer = await _observer_with_node(
        tmp_path,
        attribute_keys=["2/258/10", "0/40/5"],
        probes=probes,
    )

    probe_task = asyncio.create_task(observer.run_manual_read_probe(24))
    await _dispatch_command(observer, "read_attribute", result={"0/40/5": "ok"})
    sent = await _dispatch_command(observer, "read_attribute", result={"2/258/10": 50})
    await probe_task

    assert sent["args"]["attribute_path"] == "2/258/10"


def test_resolve_read_probe_attribute_path_uses_planner_fallback() -> None:
    config = MatterProbeConfig(
        mode=ProbeMode.CONSERVATIVE,
        advanced=MatterProbeAdvancedConfig(
            attributes=MatterProbeAttributesConfig(fallback=["0/40/5"])
        ),
    )
    path = resolve_read_probe_attribute_path(
        attribute_keys=None,
        device_types=None,
        config=config,
    )
    assert path == "0/40/5"


def test_is_unsupported_attribute_error_detects_details() -> None:
    assert is_unsupported_attribute_error(
        MatterCommandResult(ok=False, details="Unsupported attribute path")
    )
    assert not is_unsupported_attribute_error(
        MatterCommandResult(ok=False, error_code=3, details="NodeNotReady")
    )


@pytest.mark.asyncio
async def test_correlated_ping_node_request(tmp_path: Path) -> None:
    observer = await _observer_with_node(tmp_path)
    observer._websocket = FakeWebsocket([])

    request_task = asyncio.create_task(observer._request_command("ping_node", {"node_id": 24}))
    await asyncio.sleep(0)
    sent = observer._websocket.sent[-1]
    observer._requests.dispatch_incoming({"message_id": sent["message_id"], "result": True})
    result = await request_task
    assert result.ok is True
    assert sent["command"] == "ping_node"


@pytest.mark.asyncio
async def test_request_command_uses_request_manager(tmp_path: Path) -> None:
    observer = await _observer_with_node(tmp_path)
    observer._websocket = FakeWebsocket([])

    request_task = asyncio.create_task(
        observer._request_command("read_attribute", {"node_id": 24, "attribute_path": "0/40/5"})
    )
    await asyncio.sleep(0)
    sent = observer._websocket.sent[-1]
    observer._requests.dispatch_incoming(
        {"message_id": sent["message_id"], "result": {"0/40/5": "Label"}}
    )
    result = await request_task
    assert result.ok is True
    assert sent["command"] == "read_attribute"


@pytest.mark.asyncio
async def test_probe_fields_preserved_on_passive_node_update(tmp_path: Path) -> None:
    observer = await _observer_with_node(tmp_path)
    probe_task = asyncio.create_task(observer.run_manual_read_probe(24))
    await asyncio.sleep(0)
    await _dispatch_last_command(observer, result={"0/40/5": "Living Blind 3"})
    await probe_task

    await observer._process_node(_node_payload(24, label="Living Blind 3 Updated"))
    state = observer._nodes[24]
    assert state.last_read_probe_ok is True
    assert state.read_probe_successes_24h == 1


def test_matter_probe_config_defaults() -> None:
    config = MatterProbeConfig()
    assert config.mode == ProbeMode.OFF
    assert config.schedule_enabled is False
    assert config.manual_enabled is True
    assert config.timeout_seconds == 10.0
    assert config.max_concurrent == 1
    assert config.interval_seconds == 3600
    assert config.jitter_seconds == 300
    assert config.attributes.fallback == ["0/40/2", "0/40/4", "0/40/5"]
    assert config.attributes.window_covering == ["1/258/10"]
    assert config.effective_mode == ProbeMode.OFF


def test_matter_node_probe_field_defaults() -> None:
    node = MatterNodeState(node_id=1, server_id="study")
    assert node.read_probe_diagnostics_available is False
    assert node.last_read_probe_at is None
    assert node.last_read_probe_ok is None
    assert node.read_probe_failures_24h is None
    assert node.read_probe_successes_24h is None
    assert node.ping_diagnostics_available is False
    assert node.last_ping_at is None
    assert node.command_diagnostics_available is False
    assert node.command_failures_24h is None


def test_matter_node_probe_fields_serialize_missing_old_data() -> None:
    legacy = MatterNodeState.model_validate(
        {
            "node_id": 24,
            "server_id": "study",
            "available": True,
            "command_diagnostics_available": False,
        }
    )
    assert legacy.read_probe_diagnostics_available is False
    assert legacy.last_read_probe_ok is None
    assert legacy.ping_failures_24h is None
