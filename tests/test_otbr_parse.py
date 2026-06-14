"""OTBR live-shape parser tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from threadlens.collectors.otbr_parse import (
    merge_snapshots,
    parse_legacy_node_response,
    parse_otbr_devices_response,
    parse_otbr_node_response,
    reconcile_otbr_snapshots,
)
from threadlens.collectors.otbr_rest import OtbrCollector
from threadlens.config import (
    FlappingConfig,
    MdnsConfig,
    OtbrConfig,
    OtbrPollingConfig,
    ThreadLensConfig,
)
from threadlens.models.state import OtbrState
from threadlens.storage.db import Database
from threadlens.storage.repositories import CurrentStateType, StorageRepository

FIXTURES = Path(__file__).parent / "fixtures" / "otbr"


def _load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def _active_variant(payload: dict[str, Any], *, role: str) -> dict[str, Any]:
    variant = copy.deepcopy(payload)
    attributes = variant["data"]["attributes"]
    attributes["role"] = role
    attributes["state"] = role
    attributes["networkName"] = "ha-thread-7fba"
    attributes["channel"] = 15
    attributes["panId"] = 4660
    attributes["rloc16"] = "0xf000" if role == "leader" else "0x0800"
    attributes["leaderData"] = {
        "partitionId": 61563841,
        "weighting": 64,
        "dataVersion": 211,
        "stableDataVersion": 110,
        "leaderRouterId": 14,
    }
    return variant


@pytest.mark.parametrize(
    ("fixture_name", "role"),
    [
        ("study-api-node.live.json", "leader"),
        ("lounge-api-node.live.json", "router"),
    ],
)
def test_live_node_fixture_parses_role_when_active(fixture_name: str, role: str) -> None:
    payload = _active_variant(_load_fixture(fixture_name), role=role)
    snapshot = parse_otbr_node_response(payload)
    assert snapshot.thread_state == role
    assert snapshot.role == role


def test_live_study_node_fixture_parses_ext_pan_id() -> None:
    snapshot = parse_otbr_node_response(_load_fixture("study-api-node.live.json"))
    assert snapshot.ext_pan_id == "3ca76a62d0c054c3"


def test_live_study_node_disabled_shape_normalises_empty_role_to_none() -> None:
    snapshot = parse_otbr_node_response(_load_fixture("study-api-node.live.json"))
    assert snapshot.thread_state == "disabled"
    assert snapshot.role is None
    assert snapshot.network_name is None


def test_live_lounge_node_disabled_fixture_parses_thread_state_disabled() -> None:
    snapshot = parse_otbr_node_response(_load_fixture("lounge-api-node.live.json"))
    assert snapshot.thread_state == "disabled"
    assert snapshot.role is None
    assert snapshot.network_name is None


def test_live_active_fixture_parses_thread_state_and_role() -> None:
    payload = _active_variant(_load_fixture("study-api-node.live.json"), role="leader")
    snapshot = parse_otbr_node_response(payload)
    assert snapshot.thread_state == "leader"
    assert snapshot.role == "leader"


def test_live_active_fixture_parses_network_name_channel_pan_id_rloc16() -> None:
    payload = _active_variant(_load_fixture("study-api-node.live.json"), role="leader")
    snapshot = parse_otbr_node_response(payload)
    assert snapshot.network_name == "ha-thread-7fba"
    assert snapshot.channel == 15
    assert snapshot.pan_id == "1234"
    assert snapshot.rloc16 == "f000"
    assert snapshot.partition_id == 61563841


def test_live_devices_fixture_parses_device_count_and_fields() -> None:
    payload = copy.deepcopy(_load_fixture("study-api-devices.live.json"))
    for item in payload["data"]:
        item["attributes"]["role"] = "leader"
        item["attributes"]["networkName"] = "ha-thread-7fba"
        item["attributes"]["channel"] = 15
        item["attributes"]["panId"] = 4660
    snapshot = parse_otbr_devices_response(payload)
    assert snapshot.device_count == 1
    assert snapshot.role == "leader"
    assert snapshot.ext_pan_id == "3ca76a62d0c054c3"


def test_json_api_envelope_still_parses() -> None:
    payload = {
        "data": {
            "type": "threadBorderRouter",
            "id": "br0",
            "attributes": {
                "role": "router",
                "networkName": "ha-thread-7fba",
                "extPanId": "d6f401f0227e1ec0",
                "channel": 15,
                "panId": "0x1234",
                "rloc16": "0x0001",
            },
        }
    }
    snapshot = parse_otbr_node_response(payload)
    assert snapshot.role == "router"
    assert snapshot.network_name == "ha-thread-7fba"
    assert snapshot.channel == 15
    assert snapshot.ext_pan_id == "d6f401f0227e1ec0"
    assert snapshot.pan_id == "1234"
    assert snapshot.rloc16 == "0001"


def test_flattened_response_parses() -> None:
    payload = {
        "role": "leader",
        "networkName": "OpenThread-e445",
        "channel": 21,
        "extPanId": "996d3bee320097a3",
        "panId": 58437,
        "rloc16": 14336,
    }
    snapshot = parse_otbr_node_response(payload)
    assert snapshot.role == "leader"
    assert snapshot.network_name == "OpenThread-e445"
    assert snapshot.channel == 21
    assert snapshot.ext_pan_id == "996d3bee320097a3"
    assert snapshot.pan_id == "e445"
    assert snapshot.rloc16 == "3800"


def test_nested_active_dataset_fields_parse() -> None:
    payload = {
        "data": {
            "type": "threadBorderRouter",
            "id": "br0",
            "attributes": {
                "role": "",
                "state": "router",
                "activeDataset": {
                    "networkName": "OpenThread-e445",
                    "channel": 21,
                    "panId": 4660,
                    "extPanId": "996d3bee320097a3",
                },
            },
        }
    }
    snapshot = parse_otbr_node_response(payload)
    assert snapshot.role == "router"
    assert snapshot.network_name == "OpenThread-e445"
    assert snapshot.channel == 21
    assert snapshot.pan_id == "1234"
    assert snapshot.ext_pan_id == "996d3bee320097a3"


def test_merge_snapshots_prefers_first_non_empty_values() -> None:
    node = parse_otbr_node_response(
        {
            "data": {
                "type": "threadBorderRouter",
                "attributes": {"role": "leader", "extPanId": "aaaaaaaaaaaaaaaa"},
            }
        }
    )
    devices = parse_otbr_devices_response(
        {
            "data": [
                {
                    "type": "threadBorderRouter",
                    "attributes": {
                        "networkName": "ha-thread-7fba",
                        "channel": 15,
                    },
                }
            ]
        }
    )
    merged = merge_snapshots(node, devices)
    assert merged.role == "leader"
    assert merged.network_name == "ha-thread-7fba"
    assert merged.channel == 15
    assert merged.ext_pan_id == "aaaaaaaaaaaaaaaa"
    assert merged.device_count == 1


@pytest.mark.asyncio
async def test_collector_populates_role_from_live_active_shape(tmp_path: Path) -> None:
    study_node = _active_variant(_load_fixture("study-api-node.live.json"), role="leader")
    lounge_node = _active_variant(_load_fixture("lounge-api-node.live.json"), role="router")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "192.168.100.4":
            if request.url.path == "/api/node":
                return httpx.Response(200, json=study_node)
            return httpx.Response(200, json=_load_fixture("study-api-devices.live.json"))
        if request.url.path == "/api/node":
            return httpx.Response(200, json=lounge_node)
        return httpx.Response(200, json=_load_fixture("lounge-api-devices.live.json"))

    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "otbr-live.db")},
        flapping=FlappingConfig(debounce_seconds=0),
        mdns=MdnsConfig(enabled=False),
        otbr=OtbrPollingConfig(poll_interval_seconds=3600),
        otbrs=[
            OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.100.4:8081"),
            OtbrConfig(id="lounge", name="Lounge OTBR", rest_url="http://192.168.100.7:8081"),
        ],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    collector = OtbrCollector(config, repository, client=client)
    await collector.poll_all()

    study = await repository.get_model_state(CurrentStateType.OTBR, "study", OtbrState)
    lounge = await repository.get_model_state(CurrentStateType.OTBR, "lounge", OtbrState)
    assert study is not None
    assert lounge is not None
    assert study.role == "leader"
    assert lounge.role == "router"
    assert study.thread_state == "leader"
    assert lounge.thread_state == "router"
    assert study.network_name == "ha-thread-7fba"
    assert study.channel == 15
    assert study.ext_pan_id == "3ca76a62d0c054c3"
    assert study.pan_id == "1234"
    assert study.capabilities.thread_stack_active is True

    networks = await repository.list_current_state(CurrentStateType.THREAD_NETWORK)
    assert len(networks) == 1
    assert networks[0]["border_router_count"] == 2

    await database.close()


def test_legacy_study_fixture_parses_leader_state() -> None:
    snapshot = parse_legacy_node_response(_load_fixture("study-legacy-node.live.json"))
    assert snapshot.thread_state == "leader"
    assert snapshot.network_name == "ha-thread-11"
    assert snapshot.rloc16 == "3c00"
    assert snapshot.ext_pan_id == "3ca76a62d0c054c3"


def test_legacy_lounge_fixture_parses_router_state() -> None:
    snapshot = parse_legacy_node_response(_load_fixture("lounge-legacy-node.live.json"))
    assert snapshot.thread_state == "router"
    assert snapshot.network_name == "ha-thread-11"
    assert snapshot.rloc16 == "7c00"
    assert snapshot.ext_pan_id == "3ca76a62d0c054c3"


def test_reconcile_prefers_legacy_active_when_json_api_disabled() -> None:
    json_api = parse_otbr_node_response(_load_fixture("study-api-node.live.json"))
    legacy = parse_legacy_node_response(_load_fixture("study-legacy-node.live.json"))
    result = reconcile_otbr_snapshots(
        json_api,
        legacy,
        legacy_available=True,
        use_legacy_fallback=True,
    )
    assert result.snapshot.thread_state == "leader"
    assert result.snapshot.network_name == "ha-thread-11"
    assert result.snapshot.rloc16 == "3c00"
    assert result.thread_state_source == "legacy_node"
    assert result.json_api_thread_state == "disabled"
    assert result.legacy_node_thread_state == "leader"
    assert result.rest_endpoint_mismatch is True
    assert result.json_api_state_stale is True


def test_reconcile_both_disabled_stays_disabled() -> None:
    json_api = parse_otbr_node_response(_load_fixture("study-api-node.live.json"))
    legacy = parse_legacy_node_response(_load_fixture("study-legacy-node-disabled.live.json"))
    result = reconcile_otbr_snapshots(
        json_api,
        legacy,
        legacy_available=True,
        use_legacy_fallback=True,
    )
    assert result.snapshot.thread_state == "disabled"
    assert result.rest_endpoint_mismatch is False
    assert result.json_api_state_stale is False


@pytest.mark.asyncio
async def test_collector_populates_disabled_live_shape(tmp_path: Path) -> None:
    study_node = _load_fixture("study-api-node.live.json")
    lounge_node = _load_fixture("lounge-api-node.live.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "192.168.100.4":
            if request.url.path == "/api/node":
                return httpx.Response(200, json=study_node)
            return httpx.Response(200, json=_load_fixture("study-api-devices.live.json"))
        if request.url.path == "/api/node":
            return httpx.Response(200, json=lounge_node)
        return httpx.Response(200, json=_load_fixture("lounge-api-devices.live.json"))

    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "otbr-disabled-live.db")},
        flapping=FlappingConfig(debounce_seconds=0),
        mdns=MdnsConfig(enabled=False),
        otbr=OtbrPollingConfig(poll_interval_seconds=3600, use_legacy_node_fallback=False),
        otbrs=[
            OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.100.4:8081"),
            OtbrConfig(id="lounge", name="Lounge OTBR", rest_url="http://192.168.100.7:8081"),
        ],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    collector = OtbrCollector(
        config,
        repository,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await collector.poll_all()

    study = await repository.get_model_state(CurrentStateType.OTBR, "study", OtbrState)
    assert study is not None
    assert study.reachable is True
    assert study.thread_state == "disabled"
    assert study.role is None
    assert study.network_name is None
    assert study.ext_pan_id == "3ca76a62d0c054c3"
    assert study.capabilities.network_dataset_available is True
    assert study.capabilities.thread_stack_active is False

    await database.close()


@pytest.mark.asyncio
async def test_collector_reconciles_stale_json_api_with_legacy_node(tmp_path: Path) -> None:
    study_node = _load_fixture("study-api-node.live.json")
    lounge_node = _load_fixture("lounge-api-node.live.json")
    study_legacy = _load_fixture("study-legacy-node.live.json")
    lounge_legacy = _load_fixture("lounge-legacy-node.live.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "192.168.100.4":
            if request.url.path == "/api/node":
                return httpx.Response(200, json=study_node)
            if request.url.path == "/node":
                return httpx.Response(200, json=study_legacy)
            return httpx.Response(200, json=_load_fixture("study-api-devices.live.json"))
        if request.url.path == "/api/node":
            return httpx.Response(200, json=lounge_node)
        if request.url.path == "/node":
            return httpx.Response(200, json=lounge_legacy)
        return httpx.Response(200, json=_load_fixture("lounge-api-devices.live.json"))

    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "otbr-reconcile-live.db")},
        flapping=FlappingConfig(debounce_seconds=0),
        mdns=MdnsConfig(enabled=False),
        otbr=OtbrPollingConfig(poll_interval_seconds=3600, use_legacy_node_fallback=True),
        otbrs=[
            OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.100.4:8081"),
            OtbrConfig(id="lounge", name="Lounge OTBR", rest_url="http://192.168.100.7:8081"),
        ],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    collector = OtbrCollector(
        config,
        repository,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await collector.poll_all()

    study = await repository.get_model_state(CurrentStateType.OTBR, "study", OtbrState)
    lounge = await repository.get_model_state(CurrentStateType.OTBR, "lounge", OtbrState)
    assert study is not None
    assert lounge is not None
    assert study.thread_state == "leader"
    assert lounge.thread_state == "router"
    assert study.network_name == "ha-thread-11"
    assert lounge.network_name == "ha-thread-11"
    assert study.rloc16 == "3c00"
    assert lounge.rloc16 == "7c00"
    assert study.rest_endpoint_mismatch is True
    assert lounge.rest_endpoint_mismatch is True
    assert study.thread_state_source == "legacy_node"
    assert study.json_api_thread_state == "disabled"
    assert study.legacy_node_thread_state == "leader"
    assert study.capabilities.json_api_state_stale is True
    assert study.capabilities.legacy_node_available is True
    assert study.capabilities.thread_stack_active is True

    await database.close()
