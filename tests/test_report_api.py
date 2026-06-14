"""Report API and generator tests."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from threadlens.config import (
    MatterServerConfig,
    MdnsConfig,
    MqttConfig,
    OtbrConfig,
    RuntimeMode,
    ThreadLensConfig,
)
from threadlens.models.capabilities import MatterServerCapabilities, OtbrRestCapabilities
from threadlens.models.events import Event, EventSeverity, EventSourceType, EventSubjectType
from threadlens.models.state import (
    MatterNodeState,
    MatterServerState,
    MdnsServiceState,
    OtbrState,
    ThreadNetworkClassification,
    ThreadNetworkState,
    TrelServiceState,
)
from threadlens.report.generator import ReportContext, ReportGenerator
from threadlens.report.redaction import REDACTED, redact_structure
from threadlens.report.serialize import report_to_dict, report_to_yaml
from threadlens.server.app import create_server_app
from threadlens.storage.db import Database
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.time import utc_now


async def _seed_report_data(repository: StorageRepository) -> None:
    await repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(
            id="study",
            name="Study OTBR",
            reachable=True,
            thread_state="router",
            role="router",
            ext_pan_id="d6f401f0227e1ec0",
            channel=15,
            capabilities=OtbrRestCapabilities(
                rest_available=True,
                network_dataset_available=True,
            ),
        ),
    )
    await repository.upsert_model_state(
        CurrentStateType.THREAD_NETWORK,
        "d6f401f0227e1ec0",
        ThreadNetworkState(
            ext_pan_id="d6f401f0227e1ec0",
            name="ha-thread",
            channel=15,
            classification=ThreadNetworkClassification.PRIMARY,
            currently_visible=True,
            source_otbr_ids=["study"],
        ),
    )
    await repository.upsert_model_state(
        CurrentStateType.MDNS_SERVICE,
        "trel__instance",
        MdnsServiceState(
            service_id="trel__instance",
            service_type="_trel._udp.local.",
            instance_name="instance",
            currently_visible=True,
        ),
    )
    await repository.upsert_model_state(
        CurrentStateType.TREL_SERVICE,
        "foreign-trel",
        TrelServiceState(
            service_id="foreign-trel",
            instance_name="foreign",
            ext_pan_id="bbbbbbbbbbbbbbbb",
            currently_visible=True,
            is_foreign=True,
            network_classification=ThreadNetworkClassification.OBSERVED_OTHER,
        ),
    )
    await repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study Matter",
            connected=True,
            node_count=1,
            unavailable_node_count=0,
            capabilities=MatterServerCapabilities(
                websocket_available=True,
                node_inventory_available=True,
                node_availability_available=True,
                subscription_diagnostics_available=False,
            ),
        ),
    )
    await repository.upsert_model_state(
        CurrentStateType.MATTER_NODE,
        "matter_node:study_matter:24",
        MatterNodeState(
            node_id=24,
            server_id="study_matter",
            friendly_name="Living Blind 3",
            available=False,
            availability_flaps_24h=4,
            subscription_flaps_24h=None,
            subscription_diagnostics_available=False,
        ),
    )
    await repository.insert_event(
        Event(
            id=str(uuid.uuid4()),
            timestamp=utc_now() - timedelta(hours=1),
            source_type=EventSourceType.MATTER_SERVER,
            source_id="study_matter",
            event_type="matter_node.unavailable",
            severity=EventSeverity.WARNING,
            subject_type=EventSubjectType.MATTER_NODE,
            subject_id="matter_node:study_matter:24",
            message="Matter node 24 unavailable",
            data={"node_id": 24},
        )
    )


@pytest.fixture
async def report_context(tmp_path: Path):
    async def _make(**overrides) -> ReportContext:
        config = ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "report.db")},
            mdns=MdnsConfig(enabled=False),
            mqtt=MqttConfig(enabled=False, password="super-secret"),
            otbrs=[OtbrConfig(id="study", name="Study OTBR", rest_url="http://127.0.0.1:8081")],
            matter_servers=[
                MatterServerConfig(
                    id="study_matter",
                    name="Study Matter",
                    websocket_url="ws://127.0.0.1:5580/ws",
                )
            ],
            **overrides,
        )
        database = Database(config.storage.sqlite_path)
        repository = StorageRepository(database)
        await repository.initialize()
        await _seed_report_data(repository)
        return ReportContext(config=config, repository=repository)

    yield _make


def _app_config(tmp_path: Path) -> ThreadLensConfig:
    return ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "report-api.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=False, password="mqtt-secret"),
        otbrs=[OtbrConfig(id="study", name="Study OTBR", rest_url="http://127.0.0.1:8081")],
        matter_servers=[
            MatterServerConfig(
                id="study_matter",
                name="Study Matter",
                websocket_url="ws://127.0.0.1:5580/ws",
            )
        ],
    )


@pytest.mark.asyncio
async def test_report_includes_read_probe_fields(report_context) -> None:
    ctx = await report_context()
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_NODE,
        "matter_node:study_matter:24",
        MatterNodeState(
            node_id=24,
            server_id="study_matter",
            friendly_name="Living Blind 3",
            available=True,
            read_probe_diagnostics_available=True,
            last_read_probe_ok=False,
            read_probe_failures_24h=2,
            read_probe_successes_24h=5,
        ),
    )
    report = await ReportGenerator(ctx).generate(window="24h")
    node = report.matter_nodes[0]
    assert node.read_probe_diagnostics_available is True
    assert node.last_read_probe_ok is False
    assert node.read_probe_failures_24h == 2
    assert report.capabilities.matter_read_probe_diagnostics is True
    assert "read_probe_note" in report.aggregates.extra
    assert "command failed" not in report.aggregates.extra["read_probe_note"].lower()


@pytest.mark.asyncio
async def test_report_yaml_and_json_serialisation(report_context) -> None:
    ctx = await report_context()
    report = await ReportGenerator(ctx).generate(window="24h")
    yaml_payload = yaml.safe_load(report_to_yaml(report))
    json_payload = json.loads(json.dumps(report_to_dict(report)))
    assert yaml_payload["report"]["tool"] == "ThreadLens"
    assert json_payload["summary"]["health"] is not None
    assert yaml_payload["matter_nodes"][0]["subscription_flaps_24h"] is None


async def _seed_database(sqlite_path: str) -> None:
    database = Database(sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    await _seed_report_data(repository)
    await database.close()


def test_report_yaml_endpoint(tmp_path: Path) -> None:
    config = _app_config(tmp_path)
    import asyncio

    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        asyncio.run(_seed_database(config.storage.sqlite_path))
        response = client.get("/api/v1/report.yaml")
        assert response.status_code == 200
        assert "application/yaml" in response.headers["content-type"]
        payload = yaml.safe_load(response.text)
        assert payload["report"]["window"] == "24h"


def test_report_json_endpoint(tmp_path: Path) -> None:
    config = _app_config(tmp_path)
    import asyncio

    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        asyncio.run(_seed_database(config.storage.sqlite_path))
        response = client.get("/api/v1/report.json")
        assert response.status_code == 200
        payload = response.json()
        assert payload["health"]["overall"]["state"]


def test_report_content_negotiation_yaml(tmp_path: Path) -> None:
    config = _app_config(tmp_path)
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        response = client.get("/api/v1/report", headers={"Accept": "application/yaml"})
        assert response.status_code == 200
        assert "yaml" in response.headers["content-type"]


def test_report_content_negotiation_json(tmp_path: Path) -> None:
    config = _app_config(tmp_path)
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        response = client.get("/api/v1/report", headers={"Accept": "application/json"})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


def test_invalid_window_returns_400(tmp_path: Path) -> None:
    config = _app_config(tmp_path)
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        response = client.get("/api/v1/report.yaml", params={"window": "30d"})
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_report_includes_health_summary_capabilities_and_state(report_context) -> None:
    ctx = await report_context()
    report = await ReportGenerator(ctx).generate(window="24h")
    payload = report_to_dict(report)
    assert payload["summary"]["otbrs_configured"] == 1
    assert "overall" in payload["health"]
    assert payload["capabilities"]["matter_subscription_diagnostics"] is False
    assert payload["otbrs"][0]["id"] == "study"
    assert payload["otbrs"][0]["thread_state"] == "router"
    assert payload["thread_networks"][0]["ext_pan_id"] == "d6f401f0227e1ec0"
    assert payload["mdns_services"]
    assert payload["trel_services"]
    assert payload["matter_servers"][0]["id"] == "study_matter"
    assert payload["matter_nodes"][0]["subscription_flaps_24h"] is None
    assert payload["matter_nodes"][0]["subscription_diagnostics_available"] is False


@pytest.mark.asyncio
async def test_report_includes_recent_events_and_counts(report_context) -> None:
    ctx = await report_context()
    report = await ReportGenerator(ctx).generate(window="24h")
    payload = report_to_dict(report)
    assert payload["events"]["recent"]
    assert payload["aggregates"]["events_by_type"]["matter_node.unavailable"] >= 1


def test_redaction_removes_secret_keys_recursively() -> None:
    payload = {
        "mqtt": {"password": "secret"},
        "nested": [{"api_token": "abc"}, {"ext_pan_id": "d6f401f0227e1ec0"}],
        "network_key": "should-redact",
    }
    redacted = redact_structure(payload)
    assert redacted["mqtt"]["password"] == REDACTED
    assert redacted["nested"][0]["api_token"] == REDACTED
    assert redacted["nested"][1]["ext_pan_id"] == "d6f401f0227e1ec0"
    assert redacted["network_key"] == REDACTED


@pytest.mark.asyncio
async def test_report_redacts_mqtt_password(report_context) -> None:
    ctx = await report_context()
    report = await ReportGenerator(ctx).generate(window="24h")
    text = report_to_yaml(report)
    assert "mqtt-secret" not in text
    assert "super-secret" not in text


@pytest.mark.asyncio
async def test_report_yaml_includes_otbr_reconciliation_fields(report_context) -> None:
    ctx = await report_context()
    await ctx.repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(
            id="study",
            name="Study OTBR",
            reachable=True,
            thread_state="leader",
            thread_state_source="legacy_node",
            json_api_thread_state="disabled",
            legacy_node_thread_state="leader",
            rest_endpoint_mismatch=True,
            role="leader",
            network_name="ha-thread-11",
            ext_pan_id="3ca76a62d0c054c3",
            capabilities=OtbrRestCapabilities(
                network_dataset_available=True,
                thread_stack_active=True,
                legacy_node_available=True,
                json_api_state_stale=True,
            ),
        ),
    )
    report = await ReportGenerator(ctx).generate(window="24h")
    text = report_to_yaml(report)
    parsed = yaml.safe_load(text)
    study = parsed["otbrs"][0]
    assert study["thread_state"] == "leader"
    assert study["rest_endpoint_mismatch"] is True
    assert study["json_api_thread_state"] == "disabled"
    assert study["legacy_node_thread_state"] == "leader"
    assert study["thread_state_source"] == "legacy_node"
    assert "rest_endpoint_mismatch" in text


@pytest.mark.asyncio
async def test_focus_node_prioritises_matching_events(report_context) -> None:
    ctx = await report_context()
    report = await ReportGenerator(ctx).generate(window="24h", focus_node="24")
    assert report.focus is not None
    assert report.focus.matched is True
    assert report.events.recent[0].subject_id == "matter_node:study_matter:24"


@pytest.mark.asyncio
async def test_focus_device_no_match_still_returns_report(report_context) -> None:
    ctx = await report_context()
    report = await ReportGenerator(ctx).generate(window="24h", focus_device="nonexistent-device")
    assert report.focus is not None
    assert report.focus.matched is False
    assert report.summary.otbrs_configured == 1


def test_status_includes_report_metadata(tmp_path: Path) -> None:
    config = _app_config(tmp_path)
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        client.get("/api/v1/report.yaml")
        status = client.get("/api/v1/status").json()
        assert status["reports"]["last_generated_at"] is not None
        assert status["reports"]["last_window"] == "24h"
