"""mDNS/DNS-SD observer tests."""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from zeroconf import ServiceInfo

from threadlens.collectors.mdns import (
    MdnsObserver,
    NormalizedMdnsRecord,
    _AsyncMdnsListener,
    normalize_service_info,
)
from threadlens.collectors.mdns_txt import decode_txt_properties, ext_pan_id_from_txt
from threadlens.config import FlappingConfig, MdnsConfig, RuntimeMode, ThreadLensConfig
from threadlens.models.state import MdnsServiceState
from threadlens.server.app import create_server_app
from threadlens.storage.db import Database
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.ids import normalize_mdns_service_id


@pytest.fixture
async def observer(tmp_path: Path) -> MdnsObserver:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        flapping=FlappingConfig(debounce_seconds=30),
        mdns=MdnsConfig(enabled=True),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    obs = MdnsObserver(config, repository)
    yield obs
    await database.close()


def _trel_record(
    *,
    instance_name: str = "example-host._trel._udp.local.",
    hostname: str = "example-host.local.",
    addresses: list[str] | None = None,
    port: int = 49191,
    txt_records: dict[str, str] | None = None,
    raw_properties: dict[bytes, bytes] | None = None,
) -> NormalizedMdnsRecord:
    service_type = "_trel._udp.local."
    return NormalizedMdnsRecord(
        service_id=normalize_mdns_service_id(instance_name, service_type),
        service_type=service_type,
        instance_name=instance_name,
        hostname=hostname,
        addresses=addresses or ["192.168.1.10"],
        port=port,
        txt_records=txt_records or {},
        raw_properties=raw_properties,
    )


def _matter_record() -> NormalizedMdnsRecord:
    instance_name = "matter-device._matter._tcp.local."
    service_type = "_matter._tcp.local."
    return NormalizedMdnsRecord(
        service_id=normalize_mdns_service_id(instance_name, service_type),
        service_type=service_type,
        instance_name=instance_name,
        hostname="matter-device.local.",
        addresses=["192.168.1.20"],
        port=5540,
        txt_records={"VP": "1234+5678"},
    )


def test_txt_record_decoding() -> None:
    decoded = decode_txt_properties(
        {
            b"xp": bytes.fromhex("d6f401f0227e1ec0"),
            b"xa": b"\xaa\xbb\xcc\xdd\xee\xff\x00\x11",
            b"broken": b"\xff\xfe",
            123: None,
        }
    )
    assert "xp" in decoded
    assert ext_pan_id_from_txt(
        decoded, raw_properties={b"xp": bytes.fromhex("d6f401f0227e1ec0")}
    ) == ("d6f401f0227e1ec0")


def test_mdns_service_id_stability() -> None:
    first = normalize_mdns_service_id("host._trel._udp.local.", "_trel._udp.local.")
    second = normalize_mdns_service_id("host._trel._udp.local.", "_trel._udp.local.")
    assert first == second


async def test_add_service_creates_current_state(observer: MdnsObserver) -> None:
    record = _matter_record()
    await observer.process_service_added(record)

    stored = await observer._repository.get_model_state(
        CurrentStateType.MDNS_SERVICE,
        record.service_id,
        MdnsServiceState,
    )
    assert stored is not None
    assert stored.currently_visible is True
    assert stored.instance_name == record.instance_name


async def test_add_service_emits_mdns_service_added(observer: MdnsObserver) -> None:
    record = _matter_record()
    await observer.process_service_added(record)
    events = await observer._repository.get_events(event_type="mdns.service_added")
    assert len(events) == 1
    assert events[0].subject_id == f"mdns_service:{record.service_id}"
    assert events[0].data.get("initial_observation") is True


async def test_initial_trel_service_added_marks_initial_observation_true(
    observer: MdnsObserver,
) -> None:
    record = _trel_record()
    await observer.process_service_added(record)
    events = await observer._repository.get_events(event_type="trel.service_added")
    assert len(events) == 1
    assert events[0].data.get("initial_observation") is True


async def test_readded_mdns_service_marks_initial_observation_false(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens-readd.db")},
        flapping=FlappingConfig(debounce_seconds=0),
        mdns=MdnsConfig(enabled=True),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    observer = MdnsObserver(config, repository)
    record = _matter_record()
    await observer.process_service_added(record)
    await observer.process_service_removed(record)
    await observer.process_service_added(record)
    events = await observer._repository.get_events(event_type="mdns.service_added")
    assert len(events) == 2
    assert events[0].data.get("initial_observation") is True
    assert events[1].data.get("initial_observation") is False
    await database.close()


async def test_remove_service_marks_not_visible(observer: MdnsObserver) -> None:
    record = _matter_record()
    await observer.process_service_added(record)
    await observer.process_service_removed(record)

    stored = await observer._repository.get_model_state(
        CurrentStateType.MDNS_SERVICE,
        record.service_id,
        MdnsServiceState,
    )
    assert stored is not None
    assert stored.currently_visible is False


async def test_remove_service_emits_mdns_service_removed(observer: MdnsObserver) -> None:
    record = _matter_record()
    await observer.process_service_added(record)
    await observer.process_service_removed(record)
    events = await observer._repository.get_events(event_type="mdns.service_removed")
    assert len(events) == 1


async def test_changed_txt_emits_mdns_service_changed(observer: MdnsObserver) -> None:
    record = _matter_record()
    await observer.process_service_added(record)
    changed = NormalizedMdnsRecord(
        service_id=record.service_id,
        service_type=record.service_type,
        instance_name=record.instance_name,
        hostname=record.hostname,
        addresses=record.addresses,
        port=record.port,
        txt_records={"VP": "9999+0000"},
    )
    await observer.process_service_updated(changed)
    events = await observer._repository.get_events(event_type="mdns.service_changed")
    assert len(events) == 1


async def test_duplicate_identical_update_does_not_emit_second_change_event(
    observer: MdnsObserver,
) -> None:
    record = _matter_record()
    await observer.process_service_added(record)
    await observer.process_service_updated(record)
    added = len(await observer._repository.get_events(event_type="mdns.service_added"))
    changed = len(await observer._repository.get_events(event_type="mdns.service_changed"))
    assert added == 1
    assert changed == 0


async def test_trel_service_creates_mdns_and_trel_state(observer: MdnsObserver) -> None:
    record = _trel_record()
    await observer.process_service_added(record)

    mdns = await observer._repository.get_current_state(
        CurrentStateType.MDNS_SERVICE,
        record.service_id,
    )
    trel = await observer._repository.get_current_state(
        CurrentStateType.TREL_SERVICE,
        record.service_id,
    )
    assert mdns is not None
    assert trel is not None


async def test_trel_txt_xp_normalises_ext_pan_id(observer: MdnsObserver) -> None:
    raw = {b"xp": bytes.fromhex("d6f401f0227e1ec0")}
    record = _trel_record(txt_records=decode_txt_properties(raw), raw_properties=raw)
    await observer.process_service_added(record)
    trel = await observer._repository.get_current_state(
        CurrentStateType.TREL_SERVICE,
        record.service_id,
    )
    assert trel is not None
    assert trel["ext_pan_id"] == "d6f401f0227e1ec0"


async def test_missing_malformed_txt_does_not_crash(observer: MdnsObserver) -> None:
    record = _trel_record(
        txt_records=decode_txt_properties({b"": b"", b"bad": b"\xff"}),
        raw_properties={b"": b"", b"bad": b"\xff"},
    )
    await observer.process_service_added(record)
    stored = await observer._repository.get_current_state(
        CurrentStateType.TREL_SERVICE,
        record.service_id,
    )
    assert stored is not None


async def test_api_endpoints_return_stored_state(observer: MdnsObserver, tmp_path: Path) -> None:
    await observer.process_service_added(_matter_record())
    await observer.process_service_added(_trel_record())

    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )
    app = create_server_app(config, active_mode=RuntimeMode.SERVER)
    app.state.storage = observer._repository
    app.state.storage_ready = True
    app.state.mdns_observer = None

    client = TestClient(app)
    mdns_response = client.get("/api/v1/mdns/services")
    trel_response = client.get("/api/v1/trel/services")
    assert mdns_response.status_code == 200
    assert trel_response.status_code == 200
    assert mdns_response.json()["count"] == 2
    assert trel_response.json()["count"] == 1


def test_normalize_service_info_from_zeroconf() -> None:
    info = ServiceInfo(
        "_trel._udp.local.",
        "example-host._trel._udp.local.",
        addresses=[socket.inet_aton("192.168.1.5")],
        port=49191,
        properties={b"xp": bytes.fromhex("d6f401f0227e1ec0")},
        server="example-host.local.",
    )
    record = normalize_service_info(info)
    assert record.service_type == "_trel._udp.local."
    assert record.port == 49191
    assert "192.168.1.5" in record.addresses


def test_status_includes_mdns_observer_fields(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        mdns = response.json()["collectors"]["mdns"]
        assert mdns["enabled"] is False
        assert mdns["services_configured"] == 4
        assert mdns["observer_running"] is False
        assert mdns["observation_degraded"] is None


def _fake_service_info() -> ServiceInfo:
    return ServiceInfo(
        "_matter._tcp.local.",
        "matter-device._matter._tcp.local.",
        addresses=[socket.inet_aton("192.168.1.20")],
        port=5540,
        properties={b"VP": "1234+5678"},
        server="matter-device.local.",
    )


def test_async_mdns_listener_exposes_zeroconf_sync_callbacks() -> None:
    observer = MagicMock()
    loop = asyncio.new_event_loop()
    listener = _AsyncMdnsListener(observer, loop)
    try:
        for method_name in ("add_service", "update_service", "remove_service"):
            method = getattr(listener, method_name)
            assert callable(method)
    finally:
        loop.close()


@pytest.mark.asyncio
async def test_listener_add_service_reaches_observer(observer: MdnsObserver) -> None:
    loop = asyncio.get_running_loop()
    listener = _AsyncMdnsListener(observer, loop)
    mock_zc = MagicMock()
    mock_zc.async_get_service_info = AsyncMock(return_value=_fake_service_info())

    dispatch = getattr(listener, "add_service")
    dispatch(mock_zc, "_matter._tcp.local.", "matter-device._matter._tcp.local.")
    await asyncio.sleep(0.05)

    services = await observer.list_mdns_services()
    assert len(services) == 1
    assert observer.observation_degraded is False


@pytest.mark.asyncio
async def test_listener_update_service_reaches_observer(observer: MdnsObserver) -> None:
    loop = asyncio.get_running_loop()
    listener = _AsyncMdnsListener(observer, loop)
    mock_zc = MagicMock()
    info = _fake_service_info()
    mock_zc.async_get_service_info = AsyncMock(return_value=info)

    getattr(listener, "add_service")(mock_zc, info.type, info.name)
    await asyncio.sleep(0.05)

    updated = ServiceInfo(
        info.type,
        info.name,
        addresses=[socket.inet_aton("192.168.1.21")],
        port=5540,
        properties={b"VP": "9999+0000"},
        server="matter-device.local.",
    )
    mock_zc.async_get_service_info = AsyncMock(return_value=updated)
    getattr(listener, "update_service")(mock_zc, info.type, info.name)
    await asyncio.sleep(0.05)

    stored = await observer._repository.get_model_state(
        CurrentStateType.MDNS_SERVICE,
        normalize_service_info(info).service_id,
        MdnsServiceState,
    )
    assert stored is not None
    assert "192.168.1.21" in stored.addresses


@pytest.mark.asyncio
async def test_listener_remove_service_reaches_observer(observer: MdnsObserver) -> None:
    loop = asyncio.get_running_loop()
    listener = _AsyncMdnsListener(observer, loop)
    record = _matter_record()
    await observer.process_service_added(record)
    observer.observation_degraded = None

    mock_zc = MagicMock()
    getattr(listener, "remove_service")(mock_zc, record.service_type, record.instance_name)
    await asyncio.sleep(0.05)

    stored = await observer._repository.get_model_state(
        CurrentStateType.MDNS_SERVICE,
        record.service_id,
        MdnsServiceState,
    )
    assert stored is not None
    assert stored.currently_visible is False
    assert observer.observation_degraded is False


@pytest.mark.asyncio
async def test_zeroconf_dispatch_method_names_do_not_raise_attribute_error(
    observer: MdnsObserver,
) -> None:
    loop = asyncio.get_running_loop()
    listener = _AsyncMdnsListener(observer, loop)
    mock_zc = MagicMock()
    mock_zc.async_get_service_info = AsyncMock(return_value=None)

    for change_name in ("add_service", "update_service", "remove_service"):
        method = getattr(listener, change_name)
        method(mock_zc, "_matter._tcp.local.", "matter-device._matter._tcp.local.")

    await asyncio.sleep(0.05)
