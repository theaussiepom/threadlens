"""MQTT topic helpers."""

from __future__ import annotations

from threadlens.config import MqttConfig
from threadlens.utils.ids import slugify_id


class TopicBuilder:
    """Build stable ThreadLens MQTT topics."""

    def __init__(self, config: MqttConfig) -> None:
        self._prefix = config.topic_prefix.rstrip("/")
        self._discovery_prefix = config.discovery_prefix.rstrip("/")

    @property
    def availability(self) -> str:
        return f"{self._prefix}/availability"

    @property
    def status(self) -> str:
        return f"{self._prefix}/status"

    def diagnostics(self, entity: str, *, part: str = "state") -> str:
        slug = slugify_id(entity, max_length=48)
        return f"{self._prefix}/diagnostics/{slug}/{part}"

    def environment(self, entity: str, *, part: str = "state") -> str:
        slug = slugify_id(entity, max_length=48)
        return f"{self._prefix}/environment/{slug}/{part}"

    def otbr(self, otbr_id: str, entity: str, *, part: str = "state") -> str:
        oid = slugify_id(otbr_id, max_length=32)
        slug = slugify_id(entity, max_length=48)
        return f"{self._prefix}/otbr/{oid}/{slug}/{part}"

    def matter_server(self, server_id: str, entity: str, *, part: str = "state") -> str:
        sid = slugify_id(server_id, max_length=32)
        slug = slugify_id(entity, max_length=48)
        return f"{self._prefix}/matter_server/{sid}/{slug}/{part}"

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

    def thread_network(self, ext_pan_id: str, entity: str, *, part: str = "state") -> str:
        network_id = slugify_id(ext_pan_id, max_length=32)
        slug = slugify_id(entity, max_length=48)
        return f"{self._prefix}/thread_network/{network_id}/{slug}/{part}"

    def discovery_topic(self, component: str, object_id: str) -> str:
        return f"{self._discovery_prefix}/{component}/{object_id}/config"
