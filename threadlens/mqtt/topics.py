"""MQTT topic helpers."""

from __future__ import annotations

from threadlens.config import MqttConfig
from threadlens.utils.ids import slugify_id

PRODUCT = "threadlens"


class TopicBuilder:
    """Build stable ThreadLens MQTT topics."""

    def __init__(self, config: MqttConfig) -> None:
        self._prefix = config.topic_prefix.rstrip("/")
        self._discovery_prefix = config.discovery_prefix.rstrip("/")

    @property
    def availability(self) -> str:
        return f"{self._prefix}/status"

    @property
    def status(self) -> str:
        return f"{self._prefix}/status"

    def summary(self, entity_key: str, *, part: str = "state") -> str:
        return f"{self._prefix}/summary/{entity_key}/{part}"

    def matter_node(
        self,
        server_id: str,
        node_id: int,
        entity: str,
        *,
        part: str = "state",
    ) -> str:
        sid = slugify_id(server_id, max_length=32)
        slug = slugify_id(entity, max_length=48)
        return f"{self._prefix}/matter_node/{sid}/{node_id}/{slug}/{part}"

    def discovery_topic(self, component: str, entity_key: str, *, product: str = PRODUCT) -> str:
        return f"{self._discovery_prefix}/{component}/{product}/{entity_key}/config"

    def legacy_discovery_topic(self, component: str, object_id: str) -> str:
        return f"{self._discovery_prefix}/{component}/{object_id}/config"


# Legacy discovery topics from the pre-clean Lens MQTT model (for manual cleanup).
LEGACY_DISCOVERY_TOPICS: tuple[str, ...] = (
    "homeassistant/sensor/threadlens_health/config",
    "homeassistant/sensor/threadlens_event_count_24h/config",
    "homeassistant/sensor/threadlens_warning_count_24h/config",
    "homeassistant/binary_sensor/threadlens_running/config",
    "homeassistant/sensor/threadlens_report_url/config",
    "homeassistant/sensor/threadlens_last_report_generated_at/config",
    "homeassistant/sensor/threadlens_environment_health/config",
    "homeassistant/sensor/threadlens_thread_network_count/config",
    "homeassistant/sensor/threadlens_foreign_trel_service_count/config",
    "homeassistant/sensor/threadlens_matter_node_count/config",
    "homeassistant/sensor/threadlens_unavailable_matter_node_count/config",
    "homeassistant/sensor/threadlens_matter_read_probe_issues/config",
)
