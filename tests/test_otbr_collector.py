"""OTBR REST collector tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from threadlens.collectors.otbr_rest import OtbrCollector, classify_trel_service
from threadlens.config import (
    FlappingConfig,
    MdnsConfig,
    OtbrConfig,
    OtbrPollingConfig,
    RuntimeMode,
    ThreadLensConfig,
)
from threadlens.models.state import OtbrState, ThreadNetworkClassification, TrelServiceState
from threadlens.server.app import create_server_app
from threadlens.storage.db import Database
from threadlens.storage.repositories import CurrentStateType, StorageRepository


def _node_payload(
    *,
    role: str = "router",
    network_name: str = "ha-thread-7fba",
    ext_pan_id: str = "d6f401f0227e1ec0",
    channel: int = 15,
) -> dict[str, Any]:
    return {
        "data": {
            "type": "threadBorderRouter",
            "id": "br0",
            "attributes": {
                "role": role,
                "state": role,
                "networkName": network_name,
                "extPanId": ext_pan_id,
                "channel": channel,
                "panId": "0x1234",
                "rloc16": "0x0001",
            },
        }
    }


def _devices_payload() -> dict[str, Any]:
    return {
        "data": [
            {
                "type": "threadBorderRouter",
                "id": "br0",
                "attributes": {
                    "role": "router",
                    "networkName": "ha-thread-7fba",
                    "extPanId": "d6f401f0227e1ec0",
                    "channel": 15,
                },
            }
        ]
    }


def _mock_transport(
    *,
    node: dict[str, Any] | None = None,
    devices: dict[str, Any] | None = None,
    fail: bool = False,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("connection failed", request=request)
        if request.url.path == "/api/node":
            if node is None:
                return httpx.Response(404)
            return httpx.Response(200, json=node)
        if request.url.path == "/api/devices":
            if devices is None:
                return httpx.Response(404)
            return httpx.Response(200, json=devices)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
async def collector_factory(tmp_path: Path):
    async def _make(
        otbrs: list[OtbrConfig],
        *,
        transport: httpx.MockTransport,
    ) -> OtbrCollector:
        config = ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "threadlens.db")},
            flapping=FlappingConfig(debounce_seconds=0),
            mdns=MdnsConfig(enabled=False),
            otbr=OtbrPollingConfig(poll_interval_seconds=3600),
            otbrs=otbrs,
        )
        database = Database(config.storage.sqlite_path)
        repository = StorageRepository(database)
        await repository.initialize()
        client = httpx.AsyncClient(transport=transport)
        collector = OtbrCollector(config, repository, client=client)
        return collector

    yield _make


@pytest.mark.asyncio
async def test_otbr_reachable_creates_state(collector_factory) -> None:
    collector = await collector_factory(
        [OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.1.4:8081")],
        transport=_mock_transport(node=_node_payload(), devices=_devices_payload()),
    )
    await collector.poll_all()
    state = await collector._repository.get_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState,
    )
    assert state is not None
    assert state.reachable is True
    assert state.ext_pan_id == "d6f401f0227e1ec0"
    assert state.role == "router"
    assert state.thread_state == "router"


@pytest.mark.asyncio
async def test_otbr_unreachable_emits_event(collector_factory) -> None:
    collector = await collector_factory(
        [OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.1.4:8081")],
        transport=_mock_transport(fail=True),
    )
    await collector.poll_all()
    state = await collector._repository.get_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState,
    )
    assert state is not None
    assert state.reachable is False
    events = await collector._repository.get_events(event_type="otbr.unreachable")
    assert len(events) == 1


@pytest.mark.asyncio
async def test_reachable_after_unreachable_emits_reachable(collector_factory) -> None:
    collector = await collector_factory(
        [OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.1.4:8081")],
        transport=_mock_transport(fail=True),
    )
    await collector.poll_all()
    collector._client = httpx.AsyncClient(
        transport=_mock_transport(node=_node_payload(), devices=_devices_payload())
    )
    await collector.poll_all()
    events = await collector._repository.get_events(event_type="otbr.reachable")
    assert len(events) == 1


@pytest.mark.asyncio
async def test_role_change_emits_event(collector_factory) -> None:
    collector = await collector_factory(
        [OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.1.4:8081")],
        transport=_mock_transport(node=_node_payload(role="router"), devices=_devices_payload()),
    )
    await collector.poll_all()
    collector._client = httpx.AsyncClient(
        transport=_mock_transport(node=_node_payload(role="leader"), devices=_devices_payload())
    )
    await collector.poll_all()
    events = await collector._repository.get_events(event_type="otbr.role_changed")
    assert len(events) == 1


@pytest.mark.asyncio
async def test_thread_network_created_from_otbr(collector_factory) -> None:
    collector = await collector_factory(
        [OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.1.4:8081")],
        transport=_mock_transport(node=_node_payload(), devices=_devices_payload()),
    )
    await collector.poll_all()
    networks = await collector._repository.list_current_state(CurrentStateType.THREAD_NETWORK)
    assert len(networks) == 1
    assert networks[0]["ext_pan_id"] == "d6f401f0227e1ec0"
    assert networks[0]["classification"] == "primary"


@pytest.mark.asyncio
async def test_two_otbrs_same_ext_pan_id_primary(collector_factory) -> None:
    collector = await collector_factory(
        [
            OtbrConfig(id="study", name="Study", rest_url="http://192.168.1.4:8081"),
            OtbrConfig(id="lounge", name="Lounge", rest_url="http://192.168.1.7:8081"),
        ],
        transport=_mock_transport(node=_node_payload(), devices=_devices_payload()),
    )
    await collector.poll_all()
    networks = await collector._repository.list_current_state(CurrentStateType.THREAD_NETWORK)
    assert len(networks) == 1
    assert networks[0]["classification"] == "primary"
    assert networks[0]["border_router_count"] == 2


@pytest.mark.asyncio
async def test_two_otbrs_different_ext_pan_id_unknown_primary(collector_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "192.168.1.4":
            return httpx.Response(200, json=_node_payload(ext_pan_id="aaaaaaaaaaaaaaaa"))
        return httpx.Response(200, json=_node_payload(ext_pan_id="bbbbbbbbbbbbbbbb"))

    collector = await collector_factory(
        [
            OtbrConfig(id="study", name="Study", rest_url="http://192.168.1.4:8081"),
            OtbrConfig(id="lounge", name="Lounge", rest_url="http://192.168.1.7:8081"),
        ],
        transport=httpx.MockTransport(handler),
    )
    await collector.poll_all()
    networks = await collector._repository.list_current_state(CurrentStateType.THREAD_NETWORK)
    assert len(networks) == 2
    assert all(network["classification"] == "unknown" for network in networks)


@pytest.mark.asyncio
async def test_missing_devices_marks_topology_unavailable(collector_factory) -> None:
    collector = await collector_factory(
        [OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.1.4:8081")],
        transport=_mock_transport(node=_node_payload(), devices=None),
    )
    await collector.poll_all()
    state = await collector._repository.get_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState,
    )
    assert state is not None
    assert state.capabilities.topology_available is False
    assert state.reachable is True


@pytest.mark.asyncio
async def test_malformed_response_does_not_crash(collector_factory) -> None:
    collector = await collector_factory(
        [OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.1.4:8081")],
        transport=_mock_transport(node={"unexpected": True}, devices={"also": "bad"}),
    )
    await collector.poll_all()
    state = await collector._repository.get_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState,
    )
    assert state is not None
    assert state.reachable is True
    assert state.ext_pan_id is None


@pytest.mark.asyncio
async def test_trel_correlation_matching_ext_pan_id(collector_factory) -> None:
    collector = await collector_factory(
        [OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.1.4:8081")],
        transport=_mock_transport(node=_node_payload(), devices=_devices_payload()),
    )
    trel = TrelServiceState(
        service_id="trel_udp__host",
        instance_name="host._trel._udp.local.",
        ext_pan_id="d6f401f0227e1ec0",
        currently_visible=True,
    )
    await collector._repository.upsert_model_state(
        CurrentStateType.TREL_SERVICE,
        trel.service_id,
        trel,
    )
    await collector.poll_all()
    updated = await collector._repository.get_model_state(
        CurrentStateType.TREL_SERVICE,
        trel.service_id,
        TrelServiceState,
    )
    assert updated is not None
    assert updated.is_foreign is False
    assert updated.network_classification == ThreadNetworkClassification.PRIMARY


@pytest.mark.asyncio
async def test_trel_correlation_foreign_ext_pan_id(collector_factory) -> None:
    collector = await collector_factory(
        [OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.1.4:8081")],
        transport=_mock_transport(node=_node_payload(), devices=_devices_payload()),
    )
    trel = TrelServiceState(
        service_id="trel_udp__foreign",
        instance_name="foreign._trel._udp.local.",
        ext_pan_id="bbbbbbbbbbbbbbbb",
        currently_visible=True,
    )
    await collector._repository.upsert_model_state(
        CurrentStateType.TREL_SERVICE,
        trel.service_id,
        trel,
    )
    await collector.poll_all()
    updated = await collector._repository.get_model_state(
        CurrentStateType.TREL_SERVICE,
        trel.service_id,
        TrelServiceState,
    )
    assert updated is not None
    assert updated.is_foreign is True
    assert updated.network_classification == ThreadNetworkClassification.OBSERVED_OTHER


@pytest.mark.asyncio
async def test_trel_correlation_missing_ext_pan_id_null(collector_factory) -> None:
    is_foreign, classification = classify_trel_service(
        None,
        configured_ext_pan_ids={"d6f401f0227e1ec0"},
        primary_ext_pan_id="d6f401f0227e1ec0",
        primary_class=ThreadNetworkClassification.PRIMARY,
    )
    assert is_foreign is None
    assert classification == ThreadNetworkClassification.UNKNOWN


@pytest.mark.asyncio
async def test_api_endpoints_return_stored_state(collector_factory, tmp_path: Path) -> None:
    collector = await collector_factory(
        [OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.1.4:8081")],
        transport=_mock_transport(node=_node_payload(), devices=_devices_payload()),
    )
    await collector.poll_all()

    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )
    app = create_server_app(config, active_mode=RuntimeMode.SERVER)
    app.state.storage = collector._repository
    app.state.storage_ready = True

    client = TestClient(app)
    otbrs = client.get("/api/v1/otbrs")
    networks = client.get("/api/v1/networks")
    assert otbrs.status_code == 200
    assert networks.status_code == 200
    assert otbrs.json()["count"] == 1
    assert otbrs.json()["otbrs"][0]["thread_state"] == "router"
    assert networks.json()["count"] == 1


def test_status_includes_otbr_collector_fields(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
        otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        response = client.get("/api/v1/status")
        otbr = response.json()["collectors"]["otbr"]
        assert otbr["configured"] == 1
        assert otbr["collector_running"] is True
        assert "last_poll_at" in otbr
