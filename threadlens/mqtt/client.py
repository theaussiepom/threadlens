"""MQTT transport abstraction."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from threadlens.config import MqttConfig


class MqttTransport(Protocol):
    async def publish(
        self,
        topic: str,
        payload: str = "",
        *,
        retain: bool = False,
    ) -> None: ...


@dataclass
class FakeMqttTransport:
    """In-memory MQTT transport for tests."""

    published: list[tuple[str, str, bool]] = field(default_factory=list)
    connected: bool = True
    should_fail_connect: bool = False

    async def publish(
        self,
        topic: str,
        payload: str = "",
        *,
        retain: bool = False,
    ) -> None:
        self.published.append((topic, payload, retain))

    async def __aenter__(self) -> FakeMqttTransport:
        if self.should_fail_connect:
            raise ConnectionError("broker unavailable")
        self.connected = True
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        self.connected = False
        return False


class AiomqttTransport:
    """Thin aiomqtt wrapper implementing MqttTransport."""

    def __init__(self, config: MqttConfig) -> None:
        self._config = config
        self._client: Any = None

    async def __aenter__(self) -> AiomqttTransport:
        from aiomqtt import Client

        kwargs: dict[str, Any] = {
            "hostname": self._config.host,
            "port": self._config.port,
        }
        if self._config.username:
            kwargs["username"] = self._config.username
        if self._config.password:
            kwargs["password"] = self._config.password
        self._client = Client(**kwargs)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        if self._client is not None:
            await self._client.__aexit__(*exc)
            self._client = None
        return False

    async def publish(
        self,
        topic: str,
        payload: str = "",
        *,
        retain: bool = False,
    ) -> None:
        if self._client is None:
            raise RuntimeError("MQTT client is not connected")
        await self._client.publish(topic, payload=payload, retain=retain)


def dumps_json(payload: Any) -> str:
    return json.dumps(payload, default=str)
