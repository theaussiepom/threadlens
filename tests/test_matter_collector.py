"""Matter Server websocket observer tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from threadlens.collectors.matter_server import (
    ALLOWED_COMMANDS,
    FORBIDDEN_COMMANDS,
    MatterServerObserver,
)
from threadlens.config import (
    FlappingConfig,
    MatterPollingConfig,
    MatterServerConfig,
    MdnsConfig,
    RuntimeMode,
    ThreadLensConfig,
)
from threadlens.models.state import MatterNodeState, MatterServerState
from threadlens.server.app import create_server_app
from threadlens.storage.db import Database
from threadlens.storage.repositories import CurrentStateType, StorageRepository

SERVER = MatterServerConfig(
    id="study",
    name="Study Matter Server",
    websocket_url="ws://192.168.100.4:5580/ws",
    variant="python",
)


def _node_payload(
    node_id: int,
    *,
    available: bool | None = None,
    label: str | None = None,
    vendor: str | None = None,
    vendor_id: int | None = None,
    product: str | None = None,
    product_id: int | None = None,
    serial: str | None = None,
    firmware: str | None = None,
    include_attributes: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"node_id": node_id}
    if available is not None:
        payload["available"] = available
    if include_attributes:
        attrs: dict[str, Any] = {}
        if label is not None:
            attrs["0/40/5"] = label
        if vendor is not None:
            attrs["0/40/1"] = vendor
        if vendor_id is not None:
            attrs["0/40/2"] = vendor_id
        if product is not None:
            attrs["0/40/3"] = product
        if product_id is not None:
            attrs["0/40/4"] = product_id
        if serial is not None:
            attrs["0/40/15"] = serial
        if firmware is not None:
            attrs["0/40/10"] = firmware
        payload["attributes"] = attrs
    return payload


class FakeWebsocket:
    """Async-iterable fake websocket yielding pre-baked JSON messages."""

    def __init__(self, messages: list[dict[str, Any]], *, raise_on_enter: Exception | None = None):
        self._messages = [json.dumps(m) for m in messages]
        self.sent: list[dict[str, Any]] = []
        self._raise_on_enter = raise_on_enter

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    def __aiter__(self) -> FakeWebsocket:
        return self

    async def __anext__(self) -> str:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def __aenter__(self) -> FakeWebsocket:
        if self._raise_on_enter is not None:
            raise self._raise_on_enter
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False


def _connect_with(websocket: FakeWebsocket):
    def _connect(url: str) -> FakeWebsocket:
        return websocket

    return _connect


async def _make_repo(tmp_path: Path) -> StorageRepository:
    database = Database(str(tmp_path / "threadlens.db"))
    repository = StorageRepository(database)
    await repository.initialize()
    return repository


def _config(tmp_path: Path) -> ThreadLensConfig:
    return ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        flapping=FlappingConfig(debounce_seconds=0),
        mdns=MdnsConfig(enabled=False),
        matter=MatterPollingConfig(reconnect_initial_seconds=0.01, reconnect_max_seconds=0.05),
        matter_servers=[SERVER],
    )


@pytest.fixture
async def observer_factory(tmp_path: Path):
    async def _make(*, connect: Any | None = None) -> MatterServerObserver:
        repository = await _make_repo(tmp_path)
        config = _config(tmp_path)
        return MatterServerObserver(config, SERVER, repository, connect=connect)

    yield _make


async def _node_events(observer: MatterServerObserver, node_id: int) -> list[Any]:
    return await observer._repository.get_events(
        subject_id=f"matter_node:{observer.server_id}:{node_id}",
    )


@pytest.mark.asyncio
async def test_connect_marks_server_connected(observer_factory) -> None:
    observer = await observer_factory()
    await observer._on_connected()
    assert observer.connected is True
    state = await observer._repository.get_model_state(
        CurrentStateType.MATTER_SERVER, observer.server_id, MatterServerState
    )
    assert state is not None
    assert state.connected is True
    assert state.capabilities.websocket_available is True
    events = await observer._repository.get_events(event_type="matter_server.connected")
    assert len(events) == 1


@pytest.mark.asyncio
async def test_connection_failure_marks_disconnected_without_crashing(observer_factory) -> None:
    ws = FakeWebsocket([], raise_on_enter=ConnectionError("refused"))
    observer = await observer_factory(connect=_connect_with(ws))
    await observer._on_connected()
    assert observer.connected is True
    # A failing session should surface the error to the reconnect loop.
    with pytest.raises(ConnectionError):
        await observer._session()
    await observer._on_disconnected("refused")
    assert observer.connected is False
    state = await observer._repository.get_model_state(
        CurrentStateType.MATTER_SERVER, observer.server_id, MatterServerState
    )
    assert state is not None
    assert state.connected is False
    assert state.last_error == "refused"


@pytest.mark.asyncio
async def test_get_nodes_result_creates_node_records(observer_factory) -> None:
    observer = await observer_factory()
    await observer._handle_result(
        [_node_payload(1, available=True), _node_payload(2, available=True)]
    )
    nodes = await observer._repository.list_current_state(CurrentStateType.MATTER_NODE)
    assert len(nodes) == 2
    assert observer.node_count == 2


@pytest.mark.asyncio
async def test_node_available_true_persists_available(observer_factory) -> None:
    observer = await observer_factory()
    await observer._process_node(_node_payload(1, available=True))
    state = await observer._repository.get_model_state(
        CurrentStateType.MATTER_NODE, "matter_node:study:1", MatterNodeState
    )
    assert state is not None
    assert state.available is True
    assert state.last_unavailable is None


@pytest.mark.asyncio
async def test_node_available_false_persists_last_unavailable(observer_factory) -> None:
    observer = await observer_factory()
    await observer._process_node(_node_payload(1, available=False))
    state = await observer._repository.get_model_state(
        CurrentStateType.MATTER_NODE, "matter_node:study:1", MatterNodeState
    )
    assert state is not None
    assert state.available is False
    assert state.last_unavailable is not None


@pytest.mark.asyncio
async def test_available_false_after_true_emits_unavailable(observer_factory) -> None:
    observer = await observer_factory()
    await observer._process_node(_node_payload(1, available=True))
    await observer._process_node(_node_payload(1, available=False))
    events = await _node_events(observer, 1)
    types = [event.event_type for event in events]
    assert "matter_node.seen" in types
    assert "matter_node.unavailable" in types


@pytest.mark.asyncio
async def test_available_true_after_false_emits_recovered(observer_factory) -> None:
    observer = await observer_factory()
    await observer._process_node(_node_payload(1, available=False))
    await observer._process_node(_node_payload(1, available=True))
    events = await _node_events(observer, 1)
    types = [event.event_type for event in events]
    assert "matter_node.recovered" in types


@pytest.mark.asyncio
async def test_duplicate_update_does_not_emit_duplicate_events(observer_factory) -> None:
    observer = await observer_factory()
    await observer._process_node(_node_payload(1, available=True))
    await observer._process_node(_node_payload(1, available=True))
    await observer._process_node(_node_payload(1, available=True))
    events = await _node_events(observer, 1)
    types = [event.event_type for event in events]
    assert types.count("matter_node.seen") == 1
    assert "matter_node.unavailable" not in types
    assert "matter_node.recovered" not in types


@pytest.mark.asyncio
async def test_missing_availability_does_not_mark_unavailable(observer_factory) -> None:
    observer = await observer_factory()
    await observer._process_node(_node_payload(1, available=True))
    # Update without an availability field at all.
    await observer._process_node(_node_payload(1, label="Living Blind 3"))
    state = await observer._repository.get_model_state(
        CurrentStateType.MATTER_NODE, "matter_node:study:1", MatterNodeState
    )
    assert state is not None
    assert state.available is True
    events = await _node_events(observer, 1)
    assert "matter_node.unavailable" not in [event.event_type for event in events]


@pytest.mark.asyncio
async def test_node_metadata_normalisation(observer_factory) -> None:
    observer = await observer_factory()
    await observer._process_node(
        _node_payload(
            24,
            available=True,
            label="Living Blind 3",
            vendor="Acme",
            vendor_id=4660,
            product="Smart Blind",
            product_id=22136,
            serial="SN-12345",
            firmware="1.2.3",
        )
    )
    state = await observer._repository.get_model_state(
        CurrentStateType.MATTER_NODE, "matter_node:study:24", MatterNodeState
    )
    assert state is not None
    assert state.friendly_name == "Living Blind 3"
    assert state.vendor == "Acme"
    assert state.vendor_id == 4660
    assert state.product == "Smart Blind"
    assert state.product_id == 22136
    assert state.serial == "SN-12345"
    assert state.firmware == "1.2.3"


@pytest.mark.asyncio
async def test_subscription_diagnostics_unavailable(observer_factory) -> None:
    observer = await observer_factory()
    await observer._process_node(_node_payload(1, available=True))
    state = await observer._repository.get_model_state(
        CurrentStateType.MATTER_NODE, "matter_node:study:1", MatterNodeState
    )
    assert state is not None
    assert state.subscription_flaps_24h is None
    assert state.subscription_diagnostics_available is False
    assert state.case_diagnostics_available is False
    assert state.command_diagnostics_available is False
    assert state.read_probe_diagnostics_available is False
    assert state.last_read_probe_ok is None
    assert state.ping_diagnostics_available is False


@pytest.mark.asyncio
async def test_forbidden_commands_are_not_sent(observer_factory) -> None:
    ws = FakeWebsocket([{"event": "node_added", "data": _node_payload(1, available=True)}])
    observer = await observer_factory(connect=_connect_with(ws))
    await observer._session()
    sent_commands = [message["command"] for message in ws.sent]
    assert sent_commands == ["start_listening"]
    assert all(command in ALLOWED_COMMANDS for command in sent_commands)
    for forbidden in FORBIDDEN_COMMANDS:
        with pytest.raises(ValueError, match="non-allowlisted"):
            await observer._send_command(ws, forbidden)


def test_read_attribute_and_ping_node_are_allowlisted() -> None:
    assert "read_attribute" in ALLOWED_COMMANDS
    assert "ping_node" in ALLOWED_COMMANDS


def test_forbidden_commands_do_not_overlap_allowlist() -> None:
    assert ALLOWED_COMMANDS.isdisjoint(FORBIDDEN_COMMANDS)


@pytest.mark.asyncio
async def test_dispatch_consumes_registered_response_without_breaking_passive_flow(
    observer_factory,
) -> None:
    observer = await observer_factory()
    observer._requests.register("probe-1")

    async def _wait():
        return await observer._requests.wait_for("probe-1", timeout=1.0)

    waiter = asyncio.create_task(_wait())
    await asyncio.sleep(0)

    consumed = observer._requests.dispatch_incoming(
        {"message_id": "probe-1", "result": {"ping": True}}
    )
    assert consumed is True
    result = await waiter
    assert result.ok is True
    assert result.result == {"ping": True}

    # Uncorrelated start_listening-style inventory still reaches passive handler.
    await observer._handle_message(
        {"message_id": "startup", "result": [_node_payload(9, available=True)]}
    )
    assert observer.node_count == 1
    state = await observer._repository.get_model_state(
        CurrentStateType.MATTER_NODE, "matter_node:study:9", MatterNodeState
    )
    assert state is not None
    assert state.available is True


@pytest.mark.asyncio
async def test_node_removed_event_and_cleanup(observer_factory) -> None:
    observer = await observer_factory()
    await observer._process_node(_node_payload(1, available=True))
    await observer._process_node_removed({"node_id": 1})
    assert observer.node_count == 0
    nodes = await observer._repository.list_current_state(CurrentStateType.MATTER_NODE)
    assert nodes == []
    events = await _node_events(observer, 1)
    assert "matter_node.removed" in [event.event_type for event in events]


def test_matter_api_endpoints_and_status(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        servers = client.get("/api/v1/matter-servers")
        assert servers.status_code == 200
        assert servers.json() == {"count": 0, "matter_servers": []}

        nodes = client.get("/api/v1/matter-nodes")
        assert nodes.status_code == 200
        assert nodes.json() == {"count": 0, "matter_nodes": []}

        status = client.get("/api/v1/status")
        matter = status.json()["collectors"]["matter"]
        assert matter["configured"] == 0
        assert matter["collector_running"] is False
        assert matter["connected"] == 0
        assert matter["last_event_at"] is None


def test_matter_server_offline_does_not_block_startup(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
        matter=MatterPollingConfig(reconnect_initial_seconds=0.01, reconnect_max_seconds=0.05),
        matter_servers=[SERVER],
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        status = client.get("/api/v1/status")
        assert status.status_code == 200
        matter = status.json()["collectors"]["matter"]
        assert matter["configured"] == 1
        assert matter["collector_running"] is True
        # Offline server: stored server state exists and reports disconnected.
        servers = client.get("/api/v1/matter-servers").json()
        assert servers["count"] == 1
        assert servers["matter_servers"][0]["connected"] is False
