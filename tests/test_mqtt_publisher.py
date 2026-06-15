"""MQTT Discovery publisher tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from threadlens.config import (
    HomeAssistantConfig,
    MdnsConfig,
    MqttConfig,
    RuntimeMode,
    ThreadLensConfig,
)
from threadlens.health.engine import HealthContext, HealthEngine
from threadlens.models.state import MatterNodeState
from threadlens.mqtt.client import FakeMqttTransport
from threadlens.mqtt.discovery import PublishSnapshot, build_publications
from threadlens.mqtt.publisher import MqttPublisher
from threadlens.mqtt.topics import LEGACY_DISCOVERY_TOPICS
from threadlens.server.app import create_server_app
from threadlens.storage.db import Database
from threadlens.storage.repositories import CurrentStateType, StorageRepository


async def _health_report(config: ThreadLensConfig, repository: StorageRepository):
    engine = HealthEngine(HealthContext(config=config, repository=repository))
    return await engine.build_report(version="0.1.0", mode="server")


async def _snapshot(
    tmp_path: Path,
    *,
    config: ThreadLensConfig | None = None,
    matter_nodes: list[MatterNodeState] | None = None,
) -> PublishSnapshot:
    cfg = config or ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "mqtt.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True, per_node_entities=False),
    )
    database = Database(cfg.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    if matter_nodes:
        for node in matter_nodes:
            await repository.upsert_model_state(
                CurrentStateType.MATTER_NODE,
                f"matter_node:{node.server_id}:{node.node_id}",
                node,
            )
    health = await _health_report(cfg, repository)
    return PublishSnapshot(
        config=cfg,
        version="0.1.0",
        mode="server",
        storage_ready=True,
        health=health,
        matter_nodes=matter_nodes or [],
        collector_status={"mdns": {}, "otbr": {"collector_running": False}, "matter": {}},
    )


def _find_publication(publications, object_id: str):
    return next(item for item in publications if item.object_id == object_id)


@pytest.mark.asyncio
async def test_clean_discovery_payload_for_health_sensor(tmp_path: Path) -> None:
    publications = build_publications(await _snapshot(tmp_path))
    health = _find_publication(publications, "threadlens_health")
    assert health.discovery["unique_id"] == "threadlens_health"
    assert health.discovery["state_topic"] == "threadlens/summary/health/state"
    assert health.discovery["json_attributes_topic"] == "threadlens/summary/health/attributes"
    assert health.state in {
        "healthy",
        "recently_unstable",
        "needs_attention",
        "unavailable",
        "diagnostics_limited",
        "unknown",
    }


@pytest.mark.asyncio
async def test_clean_summary_entity_set(tmp_path: Path) -> None:
    publications = build_publications(await _snapshot(tmp_path))
    object_ids = {item.object_id for item in publications}
    assert object_ids == {
        "threadlens_health",
        "threadlens_issues",
        "threadlens_unavailable",
        "threadlens_needs_attention",
        "threadlens_recently_unstable",
        "threadlens_diagnostics_limited",
        "threadlens_matter_read_probe_issues",
    }


@pytest.mark.asyncio
async def test_health_attributes_include_lens_bucket_fields(tmp_path: Path) -> None:
    publications = build_publications(
        await _snapshot(
            tmp_path,
            matter_nodes=[
                MatterNodeState(
                    node_id=1,
                    server_id="home",
                    available=False,
                )
            ],
        )
    )
    health = _find_publication(publications, "threadlens_health")
    assert health.attributes["product"] == "threadlens"
    assert health.attributes["lens_bucket"]
    assert health.attributes["lens_bucket_label"]
    assert "issue_count" in health.attributes
    assert health.attributes["redaction_profile"] == "public_safe"
    assert "password" not in str(health.attributes).lower()


@pytest.mark.asyncio
async def test_read_probe_issues_unknown_without_diagnostics(tmp_path: Path) -> None:
    publications = build_publications(
        await _snapshot(
            tmp_path,
            matter_nodes=[
                MatterNodeState(
                    node_id=1,
                    server_id="home",
                    available=True,
                    read_probe_diagnostics_available=False,
                )
            ],
        )
    )
    read_probe = _find_publication(publications, "threadlens_matter_read_probe_issues")
    assert read_probe.state == "unknown"


@pytest.mark.asyncio
async def test_read_probe_issues_zero_when_no_failures(tmp_path: Path) -> None:
    publications = build_publications(
        await _snapshot(
            tmp_path,
            matter_nodes=[
                MatterNodeState(
                    node_id=1,
                    server_id="home",
                    available=True,
                    read_probe_diagnostics_available=True,
                    last_read_probe_ok=True,
                    read_probe_failures_24h=0,
                )
            ],
        )
    )
    read_probe = _find_publication(publications, "threadlens_matter_read_probe_issues")
    assert read_probe.state == "0"


@pytest.mark.asyncio
async def test_per_node_entities_skipped_by_default(tmp_path: Path) -> None:
    publications = build_publications(
        await _snapshot(
            tmp_path,
            matter_nodes=[MatterNodeState(node_id=24, server_id="study", available=True)],
        )
    )
    assert not any(item.object_id.startswith("threadlens_matter_node_") for item in publications)


@pytest.mark.asyncio
async def test_per_node_entities_when_enabled(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "per-node.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True, per_node_entities=True),
    )
    publications = build_publications(
        await _snapshot(
            tmp_path,
            config=config,
            matter_nodes=[
                MatterNodeState(
                    node_id=24,
                    server_id="study",
                    available=True,
                    read_probe_diagnostics_available=True,
                    last_read_probe_ok=True,
                )
            ],
        )
    )
    assert any(item.object_id.startswith("threadlens_matter_node_") for item in publications)


@pytest.mark.asyncio
async def test_availability_uses_status_topic(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "availability.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True, publish_interval_seconds=3600),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    transport = FakeMqttTransport()
    publisher = MqttPublisher(config, repository, transport_factory=lambda: transport)
    await publisher.publish_once(transport)
    await publisher.start()
    await asyncio.sleep(0.05)
    await publisher.stop()
    availability_messages = [
        (topic, payload)
        for topic, payload, _retain in transport.published
        if topic == "threadlens/status"
    ]
    assert ("threadlens/status", "online") in availability_messages
    assert ("threadlens/status", "offline") in availability_messages


@pytest.mark.asyncio
async def test_publisher_publishes_clean_discovery_topics(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "publish.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    transport = FakeMqttTransport()
    publisher = MqttPublisher(config, repository, transport_factory=lambda: transport)
    await publisher.publish_once(transport)
    discovery_topics = [topic for topic, _, _ in transport.published if topic.endswith("/config")]
    assert "homeassistant/sensor/threadlens/health/config" in discovery_topics
    assert "threadlens/summary/health/state" in [t for t, _, _ in transport.published]


@pytest.mark.asyncio
async def test_discovery_cleanup_helper(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "cleanup.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    transport = FakeMqttTransport()
    publisher = MqttPublisher(config, repository, transport_factory=lambda: transport)
    await publisher.publish_discovery_cleanup("homeassistant/sensor/old_entity/config")
    assert transport.published == [("homeassistant/sensor/old_entity/config", "", True)]


def test_legacy_discovery_topics_documented() -> None:
    assert "homeassistant/sensor/threadlens_health/config" in LEGACY_DISCOVERY_TOPICS


@pytest.mark.asyncio
async def test_publisher_does_not_start_when_mqtt_disabled(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "mqtt-disabled.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=False),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    publisher = MqttPublisher(config, repository, transport_factory=lambda: FakeMqttTransport())
    await publisher.start()
    assert publisher.running is False


def test_broker_failure_does_not_block_app_startup(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "mqtt-fail.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True, publish_interval_seconds=3600),
    )

    def failing_factory() -> FakeMqttTransport:
        return FakeMqttTransport(should_fail_connect=True)

    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        status = client.get("/api/v1/status")
        assert status.status_code == 200
        mqtt = status.json()["collectors"]["mqtt"]
        assert mqtt["enabled"] is True
        assert mqtt["publisher_running"] is True


def test_status_includes_mqtt_publisher_status(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "status-mqtt.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=False),
        homeassistant=HomeAssistantConfig(mqtt_discovery_enabled=True),
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        mqtt = client.get("/api/v1/status").json()["collectors"]["mqtt"]
        assert mqtt["enabled"] is False
        assert mqtt["publisher_running"] is False
        assert mqtt["homeassistant_discovery_enabled"] is True


@pytest.mark.asyncio
async def test_ha_discovery_disabled_skips_discovery_and_entity_topics(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "ha-discovery-off.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True),
        homeassistant=HomeAssistantConfig(mqtt_discovery_enabled=False),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    transport = FakeMqttTransport()
    publisher = MqttPublisher(config, repository, transport_factory=lambda: transport)
    await publisher.publish_once(transport)
    topics = [topic for topic, _, _ in transport.published]
    assert topics == ["threadlens/status"]
    assert not any(topic.startswith("homeassistant/") for topic in topics)
