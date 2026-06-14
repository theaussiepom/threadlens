"""MQTT Discovery publisher tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from threadlens.config import (
    HomeAssistantConfig,
    MatterServerConfig,
    MdnsConfig,
    MqttConfig,
    OtbrConfig,
    RuntimeMode,
    ThreadLensConfig,
)
from threadlens.health.engine import HealthContext, HealthEngine
from threadlens.models.capabilities import MatterServerCapabilities, OtbrRestCapabilities
from threadlens.models.health import HealthState
from threadlens.models.state import (
    MatterNodeState,
    MatterServerState,
    OtbrState,
)
from threadlens.mqtt.client import FakeMqttTransport
from threadlens.mqtt.discovery import PublishSnapshot, build_publications
from threadlens.mqtt.publisher import MqttPublisher
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
    extra_upserts: list[tuple[CurrentStateType, str, Any]] | None = None,
) -> PublishSnapshot:
    cfg = config or ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "mqtt.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True, per_node_entities=True),
    )
    database = Database(cfg.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    if extra_upserts:
        for object_type, object_id, model in extra_upserts:
            await repository.upsert_model_state(object_type, object_id, model)
    health = await _health_report(cfg, repository)
    return PublishSnapshot(
        config=cfg,
        version="0.1.0",
        mode="server",
        storage_ready=True,
        health=health,
        otbr_states=[],
        matter_servers=[],
        matter_nodes=[],
        thread_networks=[],
        collector_status={"mdns": {}, "otbr": {}, "matter": {}},
    )


def _find_publication(publications, object_id: str):
    return next(item for item in publications if item.object_id == object_id)


@pytest.mark.asyncio
async def test_discovery_payload_for_threadlens_health_sensor(tmp_path: Path) -> None:
    snapshot = await _snapshot(tmp_path)
    publications = build_publications(snapshot)
    health = _find_publication(publications, "threadlens_health")
    assert health.component == "sensor"
    assert health.discovery["unique_id"] == "threadlens_health"
    assert health.discovery["state_topic"].endswith("/diagnostics/health/state")
    assert health.state in {state.value for state in HealthState}


@pytest.mark.asyncio
async def test_discovery_payload_has_stable_unique_id_and_device(tmp_path: Path) -> None:
    snapshot = await _snapshot(tmp_path)
    health = _find_publication(build_publications(snapshot), "threadlens_health")
    device = health.discovery["device"]
    assert device["identifiers"] == ["threadlens_diagnostics"]
    assert device["manufacturer"] == "ThreadLens"
    assert health.discovery["availability_topic"] == "threadlens/availability"


@pytest.mark.asyncio
async def test_environment_payload_includes_health_and_summary_counts(tmp_path: Path) -> None:
    snapshot = await _snapshot(tmp_path)
    env = _find_publication(build_publications(snapshot), "threadlens_environment_health")
    assert "health_reasons" in env.attributes
    assert env.attributes["otbrs_configured"] == 0
    assert env.attributes["matter_servers_configured"] == 0


@pytest.mark.asyncio
async def test_otbr_discovery_and_state_payloads(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "otbr-mqtt.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True),
        otbrs=[OtbrConfig(id="study", name="Study OTBR", rest_url="http://127.0.0.1:8081")],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    snapshot = PublishSnapshot(
        config=config,
        version="0.1.0",
        mode="server",
        storage_ready=True,
        health=await _health_report(config, repository),
        otbr_states=[
            OtbrState(
                id="study",
                name="Study OTBR",
                reachable=True,
                thread_state="router",
                role="router",
                network_name="ha-thread",
                channel=15,
                ext_pan_id="d6f401f0227e1ec0",
                capabilities=OtbrRestCapabilities(network_dataset_available=True),
            )
        ],
        matter_servers=[],
        matter_nodes=[],
        thread_networks=[],
        collector_status={"mdns": {}, "otbr": {}, "matter": {}},
    )
    publications = build_publications(snapshot)
    reachable = _find_publication(publications, "threadlens_otbr_study_reachable")
    assert reachable.state == "ON"
    assert reachable.discovery["payload_on"] == "ON"
    assert "health_reasons" in reachable.attributes
    assert reachable.attributes["thread_state"] == "router"


@pytest.mark.asyncio
async def test_otbr_mqtt_attributes_include_disabled_thread_state(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "otbr-disabled-mqtt.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True),
        otbrs=[OtbrConfig(id="study", name="Study OTBR", rest_url="http://127.0.0.1:8081")],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    disabled_state = OtbrState(
        id="study",
        name="Study OTBR",
        reachable=True,
        thread_state="disabled",
        ext_pan_id="3ca76a62d0c054c3",
        capabilities=OtbrRestCapabilities(
            network_dataset_available=True,
            thread_stack_active=False,
        ),
    )
    await repository.upsert_model_state(CurrentStateType.OTBR, "study", disabled_state)
    snapshot = PublishSnapshot(
        config=config,
        version="0.1.0",
        mode="server",
        storage_ready=True,
        health=await _health_report(config, repository),
        otbr_states=[disabled_state],
        matter_servers=[],
        matter_nodes=[],
        thread_networks=[],
        collector_status={"mdns": {}, "otbr": {}, "matter": {}},
    )
    publications = build_publications(snapshot)
    health_pub = _find_publication(publications, "threadlens_otbr_study_health")
    assert health_pub.attributes["thread_state"] == "disabled"
    assert "otbr_thread_stack_disabled" in health_pub.attributes["health_reasons"]


@pytest.mark.asyncio
async def test_matter_server_discovery_and_state_payloads(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "matter-server-mqtt.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True),
        matter_servers=[
            MatterServerConfig(
                id="study_matter",
                name="Study Matter",
                websocket_url="ws://127.0.0.1:5580/ws",
            )
        ],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    snapshot = PublishSnapshot(
        config=config,
        version="0.1.0",
        mode="server",
        storage_ready=True,
        health=await _health_report(config, repository),
        otbr_states=[],
        matter_servers=[
            MatterServerState(
                id="study_matter",
                name="Study Matter",
                connected=True,
                node_count=3,
                unavailable_node_count=1,
                capabilities=MatterServerCapabilities(
                    node_inventory_available=True,
                    node_availability_available=True,
                ),
            )
        ],
        matter_nodes=[],
        thread_networks=[],
        collector_status={"mdns": {}, "otbr": {}, "matter": {}},
    )
    publications = build_publications(snapshot)
    connected = _find_publication(publications, "threadlens_matter_server_study_matter_connected")
    node_count = _find_publication(publications, "threadlens_matter_server_study_matter_node_count")
    assert connected.state == "ON"
    assert node_count.state == "3"


@pytest.mark.asyncio
async def test_matter_node_entities_when_per_node_entities_true(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "matter-node-mqtt.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True, per_node_entities=True),
        matter_servers=[
            MatterServerConfig(
                id="study_matter",
                name="Study Matter",
                websocket_url="ws://127.0.0.1:5580/ws",
            )
        ],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    await repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study Matter",
            connected=True,
            capabilities=MatterServerCapabilities(node_availability_available=True),
        ),
    )
    snapshot = PublishSnapshot(
        config=config,
        version="0.1.0",
        mode="server",
        storage_ready=True,
        health=await _health_report(config, repository),
        otbr_states=[],
        matter_servers=[],
        matter_nodes=[
            MatterNodeState(
                node_id=24,
                server_id="study_matter",
                friendly_name="Living Blind 3",
                available=True,
                subscription_diagnostics_available=False,
                subscription_flaps_24h=None,
            )
        ],
        thread_networks=[],
        collector_status={"mdns": {}, "otbr": {}, "matter": {}},
    )
    publications = build_publications(snapshot)
    assert any(
        item.object_id.startswith("threadlens_matter_node_study_matter_24") for item in publications
    )


@pytest.mark.asyncio
async def test_matter_node_entities_skipped_when_per_node_entities_false(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "matter-node-skip.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True, per_node_entities=False),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    snapshot = PublishSnapshot(
        config=config,
        version="0.1.0",
        mode="server",
        storage_ready=True,
        health=await _health_report(config, repository),
        otbr_states=[],
        matter_servers=[],
        matter_nodes=[
            MatterNodeState(node_id=24, server_id="study_matter", available=True),
        ],
        thread_networks=[],
        collector_status={"mdns": {}, "otbr": {}, "matter": {}},
    )
    publications = build_publications(snapshot)
    per_node_entities = [
        item.object_id
        for item in publications
        if item.object_id.startswith("threadlens_matter_node_")
        and item.object_id not in {"threadlens_matter_node_count"}
    ]
    assert per_node_entities == []


@pytest.mark.asyncio
async def test_per_trel_service_entities_not_published_by_default(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "trel-skip.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True, per_trel_service_entities=False),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    snapshot = PublishSnapshot(
        config=config,
        version="0.1.0",
        mode="server",
        storage_ready=True,
        health=await _health_report(config, repository),
        otbr_states=[],
        matter_servers=[],
        matter_nodes=[],
        thread_networks=[],
        collector_status={"mdns": {}, "otbr": {}, "matter": {}},
    )
    publications = build_publications(snapshot)
    assert not any(item.object_id.startswith("threadlens_trel_service_") for item in publications)


@pytest.mark.asyncio
async def test_binary_sensor_payloads_use_on_off(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "binary.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True),
        otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    snapshot = PublishSnapshot(
        config=config,
        version="0.1.0",
        mode="server",
        storage_ready=True,
        health=await _health_report(config, repository),
        otbr_states=[OtbrState(id="study", name="Study", reachable=False)],
        matter_servers=[],
        matter_nodes=[],
        thread_networks=[],
        collector_status={"mdns": {}, "otbr": {}, "matter": {}},
    )
    publications = build_publications(snapshot)
    reachable = _find_publication(publications, "threadlens_otbr_study_reachable")
    assert reachable.discovery["payload_on"] == "ON"
    assert reachable.discovery["payload_off"] == "OFF"
    assert reachable.state == "OFF"


@pytest.mark.asyncio
async def test_attributes_include_health_reason_codes(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "reasons.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True),
        otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    await repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(id="study", name="Study", reachable=False),
    )
    snapshot = PublishSnapshot(
        config=config,
        version="0.1.0",
        mode="server",
        storage_ready=True,
        health=await _health_report(config, repository),
        otbr_states=[OtbrState(id="study", name="Study", reachable=False)],
        matter_servers=[],
        matter_nodes=[],
        thread_networks=[],
        collector_status={"mdns": {}, "otbr": {}, "matter": {}},
    )
    publications = build_publications(snapshot)
    health_pub = _find_publication(publications, "threadlens_otbr_study_health")
    assert "otbr_unreachable" in health_pub.attributes["health_reasons"]


@pytest.mark.asyncio
async def test_subscription_diagnostics_unavailable_in_attributes(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "sub-unavail.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True, per_node_entities=True),
        matter_servers=[
            MatterServerConfig(
                id="study_matter",
                name="Study",
                websocket_url="ws://127.0.0.1:5580/ws",
            )
        ],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    await repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study",
            connected=True,
            capabilities=MatterServerCapabilities(node_availability_available=True),
        ),
    )
    snapshot = PublishSnapshot(
        config=config,
        version="0.1.0",
        mode="server",
        storage_ready=True,
        health=await _health_report(config, repository),
        otbr_states=[],
        matter_servers=[],
        matter_nodes=[
            MatterNodeState(
                node_id=24,
                server_id="study_matter",
                available=True,
                subscription_diagnostics_available=False,
                subscription_flaps_24h=None,
            )
        ],
        thread_networks=[],
        collector_status={"mdns": {}, "otbr": {}, "matter": {}},
    )
    node_health = _find_publication(
        build_publications(snapshot),
        "threadlens_matter_node_study_matter_24_health",
    )
    assert node_health.attributes["subscription_diagnostics_available"] is False
    assert node_health.attributes["subscription_flaps_24h"] is None


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
        transport = FakeMqttTransport(should_fail_connect=True)
        return transport

    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        status = client.get("/api/v1/status")
        assert status.status_code == 200
        mqtt = status.json()["collectors"]["mqtt"]
        assert mqtt["enabled"] is True
        assert mqtt["publisher_running"] is True


@pytest.mark.asyncio
async def test_availability_online_and_offline_payloads(tmp_path: Path) -> None:
    import asyncio

    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "availability.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True, publish_interval_seconds=3600),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    transport = FakeMqttTransport()
    publisher = MqttPublisher(
        config,
        repository,
        transport_factory=lambda: transport,
    )
    await publisher.publish_once(transport)
    await publisher.start()
    await asyncio.sleep(0.05)
    await publisher.stop()
    availability_messages = [
        (topic, payload)
        for topic, payload, _retain in transport.published
        if topic == "threadlens/availability"
    ]
    assert ("threadlens/availability", "online") in availability_messages
    assert ("threadlens/availability", "offline") in availability_messages


@pytest.mark.asyncio
async def test_publisher_publishes_discovery_and_state(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "publish.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True),
        otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    transport = FakeMqttTransport()
    publisher = MqttPublisher(
        config,
        repository,
        transport_factory=lambda: transport,
    )
    await publisher.publish_once(transport)
    discovery_topics = [topic for topic, _, _ in transport.published if topic.endswith("/config")]
    assert any(
        "homeassistant/sensor/threadlens_health/config" == topic for topic in discovery_topics
    )
    state_topics = [topic for topic, _, _ in transport.published if topic.endswith("/state")]
    assert state_topics


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
    publisher = MqttPublisher(
        config,
        repository,
        transport_factory=lambda: transport,
    )
    await publisher.publish_discovery_cleanup("homeassistant/sensor/old_entity/config")
    assert transport.published == [("homeassistant/sensor/old_entity/config", "", True)]


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
        assert mqtt["connected"] is False
        assert mqtt["homeassistant_discovery_enabled"] is True
        assert mqtt["last_publish_at"] is None


@pytest.mark.asyncio
async def test_ha_discovery_disabled_skips_discovery_and_entity_topics(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "ha-discovery-off.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True),
        homeassistant=HomeAssistantConfig(mqtt_discovery_enabled=False),
        otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    transport = FakeMqttTransport()
    publisher = MqttPublisher(
        config,
        repository,
        transport_factory=lambda: transport,
    )
    await publisher.publish_once(transport)
    topics = [topic for topic, _, _ in transport.published]
    assert topics == ["threadlens/status"]
    assert not any(topic.startswith("homeassistant/") for topic in topics)
    assert not any(topic.endswith("/state") for topic in topics)


@pytest.mark.asyncio
async def test_ha_discovery_enabled_publishes_discovery_and_state(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "ha-discovery-on.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True),
        homeassistant=HomeAssistantConfig(mqtt_discovery_enabled=True),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    transport = FakeMqttTransport()
    publisher = MqttPublisher(
        config,
        repository,
        transport_factory=lambda: transport,
    )
    await publisher.publish_once(transport)
    discovery_topics = [topic for topic, _, _ in transport.published if topic.endswith("/config")]
    state_topics = [topic for topic, _, _ in transport.published if topic.endswith("/state")]
    assert any(topic.startswith("homeassistant/") for topic in discovery_topics)
    assert state_topics


@pytest.mark.asyncio
async def test_ha_discovery_disabled_skips_availability_topic(tmp_path: Path) -> None:
    import asyncio

    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "ha-availability-off.db")},
        mdns=MdnsConfig(enabled=False),
        mqtt=MqttConfig(enabled=True, publish_interval_seconds=3600),
        homeassistant=HomeAssistantConfig(mqtt_discovery_enabled=False),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    transport = FakeMqttTransport()
    publisher = MqttPublisher(
        config,
        repository,
        transport_factory=lambda: transport,
    )
    await publisher.publish_once(transport)
    await publisher.start()
    await asyncio.sleep(0.05)
    await publisher.stop()
    availability_messages = [
        topic for topic, _, _ in transport.published if topic == "threadlens/availability"
    ]
    assert availability_messages == []
