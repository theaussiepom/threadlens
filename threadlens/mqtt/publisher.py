"""MQTT Discovery publisher."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from datetime import datetime
from typing import Any

from threadlens import __version__
from threadlens.collectors.matter_server import MatterCollector
from threadlens.collectors.mdns import MdnsObserver
from threadlens.collectors.otbr_rest import OtbrCollector
from threadlens.config import ThreadLensConfig
from threadlens.health import HealthEngine
from threadlens.health.engine import HealthContext
from threadlens.models.state import (
    MatterNodeState,
    MatterServerState,
    OtbrState,
    ThreadNetworkState,
)
from threadlens.mqtt.client import AiomqttTransport, MqttTransport, dumps_json
from threadlens.mqtt.discovery import (
    EntityPublication,
    PublishSnapshot,
    build_publications,
    discovery_cleanup_payload,
)
from threadlens.mqtt.topics import TopicBuilder
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.time import utc_now

TransportFactory = Callable[[], Any]


class MqttPublisher:
    """Publish Home Assistant MQTT Discovery config and ThreadLens state."""

    def __init__(
        self,
        config: ThreadLensConfig,
        repository: StorageRepository,
        *,
        version: str = __version__,
        mode: str = "server",
        mdns_observer: MdnsObserver | None = None,
        otbr_collector: OtbrCollector | None = None,
        matter_collector: MatterCollector | None = None,
        storage_ready: bool = True,
        transport_factory: TransportFactory | None = None,
    ) -> None:
        self._config = config
        self._repository = repository
        self._version = version
        self._mode = mode
        self._mdns_observer = mdns_observer
        self._otbr_collector = otbr_collector
        self._matter_collector = matter_collector
        self._storage_ready = storage_ready
        self._transport_factory = transport_factory or self._default_transport_factory
        self._topics = TopicBuilder(config.mqtt)
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._connected = False
        self._last_error: str | None = None
        self._last_publish_at: datetime | None = None
        self._published_discovery: set[str] = set()
        self._active_transport: MqttTransport | None = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_publish_at(self) -> datetime | None:
        return self._last_publish_at

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self._config.mqtt.enabled,
            "connected": self._connected,
            "publisher_running": self._running,
            "homeassistant_discovery_enabled": self._config.homeassistant.mqtt_discovery_enabled,
            "last_publish_at": (
                self._last_publish_at.isoformat() if self._last_publish_at else None
            ),
            "last_error": self._last_error,
        }

    async def start(self) -> None:
        if self._running or not self._config.mqtt.enabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="mqtt-publisher")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._connected = False
        self._active_transport = None

    async def publish_once(self, transport: MqttTransport | None = None) -> None:
        """Publish a single cycle; useful in tests."""
        if transport is None:
            async with self._transport_factory() as client:
                if self._config.homeassistant.mqtt_discovery_enabled:
                    await self._publish_availability(client, online=True)
                await self._publish_cycle(client)
            return
        if self._config.homeassistant.mqtt_discovery_enabled:
            await self._publish_availability(transport, online=True)
        await self._publish_cycle(transport)

    async def publish_discovery_cleanup(self, discovery_topic: str) -> None:
        """Publish an empty retained discovery payload for future entity cleanup."""
        if not self._config.homeassistant.mqtt_discovery_enabled:
            return
        async with self._transport_factory() as transport:
            await transport.publish(
                discovery_topic,
                discovery_cleanup_payload(),
                retain=True,
            )

    async def _run(self) -> None:
        reconnect_delay = 5.0
        while self._running:
            try:
                async with self._transport_factory() as transport:
                    self._active_transport = transport
                    self._connected = True
                    self._last_error = None
                    try:
                        if self._config.homeassistant.mqtt_discovery_enabled:
                            await self._publish_availability(transport, online=True)
                        await self._publish_cycle(transport)
                        while self._running:
                            await asyncio.sleep(self._config.mqtt.publish_interval_seconds)
                            await self._publish_cycle(transport)
                    finally:
                        if self._config.homeassistant.mqtt_discovery_enabled:
                            with contextlib.suppress(Exception):
                                await self._publish_availability(transport, online=False)
                        self._connected = False
                        self._active_transport = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - reconnect resilience
                self._connected = False
                self._active_transport = None
                self._last_error = str(exc)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60.0)

    async def _publish_cycle(self, transport: MqttTransport) -> None:
        if self._config.homeassistant.mqtt_discovery_enabled:
            snapshot = await self._build_snapshot()
            publications = build_publications(snapshot)
            await self._publish_entities(transport, publications)
        await transport.publish(
            self._topics.status, "running", retain=self._config.mqtt.retain_state
        )
        self._last_publish_at = utc_now()

    async def _publish_entities(
        self,
        transport: MqttTransport,
        publications: list[EntityPublication],
    ) -> None:
        for publication in publications:
            discovery_topic = self._topics.discovery_topic(
                publication.component,
                publication.object_id,
            )
            if discovery_topic not in self._published_discovery:
                await transport.publish(
                    discovery_topic,
                    dumps_json(publication.discovery),
                    retain=self._config.mqtt.retain_discovery,
                )
                self._published_discovery.add(discovery_topic)

            state_topic = publication.discovery["state_topic"]
            await transport.publish(
                state_topic,
                publication.state,
                retain=self._config.mqtt.retain_state,
            )
            attributes_topic = publication.discovery.get("json_attributes_topic")
            if attributes_topic:
                await transport.publish(
                    attributes_topic,
                    dumps_json(publication.attributes),
                    retain=self._config.mqtt.retain_state,
                )

    async def _publish_availability(self, transport: MqttTransport, *, online: bool) -> None:
        await transport.publish(
            self._topics.availability,
            "online" if online else "offline",
            retain=self._config.mqtt.retain_state,
        )

    async def _build_snapshot(self) -> PublishSnapshot:
        engine = HealthEngine(
            HealthContext(
                config=self._config,
                repository=self._repository,
                mdns_observer=self._mdns_observer,
                otbr_collector=self._otbr_collector,
                matter_collector=self._matter_collector,
            )
        )
        health = await engine.build_report(version=self._version, mode=self._mode)
        report_last_generated_at = await self._repository.get_metadata("report_last_generated_at")
        host = self._config.server.host
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        report_url = f"http://{host}:{self._config.server.port}/api/v1/report.yaml"
        return PublishSnapshot(
            config=self._config,
            version=self._version,
            mode=self._mode,
            storage_ready=self._storage_ready,
            health=health,
            otbr_states=await self._load_states(CurrentStateType.OTBR, OtbrState),
            matter_servers=await self._load_states(
                CurrentStateType.MATTER_SERVER,
                MatterServerState,
            ),
            matter_nodes=await self._load_states(CurrentStateType.MATTER_NODE, MatterNodeState),
            thread_networks=await self._load_states(
                CurrentStateType.THREAD_NETWORK,
                ThreadNetworkState,
            ),
            collector_status=self._collector_status(),
            report_url=report_url,
            report_last_generated_at=report_last_generated_at,
        )

    async def _load_states(self, object_type: CurrentStateType, model_type: type[Any]) -> list[Any]:
        payloads = await self._repository.list_current_state(object_type)
        results: list[Any] = []
        for payload in payloads:
            clean = {key: value for key, value in payload.items() if not key.startswith("_")}
            results.append(model_type.model_validate(clean))
        return results

    def _collector_status(self) -> dict[str, Any]:
        mdns_status = {
            "enabled": self._config.mdns.enabled,
            "observer_running": bool(self._mdns_observer and self._mdns_observer.running),
            "observation_degraded": (
                self._mdns_observer.observation_degraded if self._mdns_observer else None
            ),
        }
        otbr_status = {
            "configured": len(self._config.otbrs),
            "collector_running": bool(self._otbr_collector and self._otbr_collector.running),
            "reachable": self._otbr_collector.reachable_count if self._otbr_collector else 0,
            "unreachable": self._otbr_collector.unreachable_count if self._otbr_collector else 0,
        }
        if self._matter_collector is not None:
            matter_status = self._matter_collector.status()
        else:
            matter_status = {
                "configured": len(self._config.matter_servers),
                "collector_running": False,
                "connected": 0,
                "disconnected": len(self._config.matter_servers),
            }
        return {"mdns": mdns_status, "otbr": otbr_status, "matter": matter_status}

    def _default_transport_factory(self) -> MqttTransport:
        return AiomqttTransport(self._config.mqtt)
