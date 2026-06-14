"""Matter Server websocket observer (read-only).

ThreadLens connects to a python-matter-server websocket as a passive
observer. It only ever sends read-only commands (``start_listening`` /
``get_nodes``) and never mutating/commissioning commands.

Subscription, CASE and command diagnostics are intentionally marked
*unavailable*: the current public python-matter-server event stream does not
expose true subscription lifecycle diagnostics, so we must not infer them
(and must never derive subscription flaps from availability flaps).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any, Protocol

from threadlens.collectors.matter_parse import parse_matter_node
from threadlens.config import MatterServerConfig, ThreadLensConfig
from threadlens.models.capabilities import MatterServerCapabilities
from threadlens.models.events import Event, EventSeverity, EventSourceType, EventSubjectType
from threadlens.models.health import HealthState, HealthStatus
from threadlens.models.state import MatterNodeState, MatterServerState
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.debounce import EventDebouncer
from threadlens.utils.time import utc_now

# Explicit read-only allowlist. Any command not in this set must never be sent.
ALLOWED_COMMANDS = frozenset({"start_listening", "get_nodes", "server_info"})

# python-matter-server event names we act on.
EVENT_NODE_ADDED = "node_added"
EVENT_NODE_UPDATED = "node_updated"
EVENT_NODE_REMOVED = "node_removed"
EVENT_SERVER_SHUTDOWN = "server_shutdown"


class WebsocketLike(Protocol):
    async def send(self, message: str) -> None: ...

    def __aiter__(self) -> AsyncIterator[str | bytes]: ...


def _node_subject_id(server_id: str, node_id: int) -> str:
    return f"matter_node:{server_id}:{node_id}"


def _server_subject_id(server_id: str) -> str:
    return f"matter_server:{server_id}"


class MatterServerObserver:
    """Observe a single configured Matter Server websocket."""

    def __init__(
        self,
        config: ThreadLensConfig,
        server_config: MatterServerConfig,
        repository: StorageRepository,
        *,
        debouncer: EventDebouncer | None = None,
        connect: Any | None = None,
    ) -> None:
        self._config = config
        self._server_config = server_config
        self._repository = repository
        self._debouncer = debouncer or EventDebouncer(config.flapping.debounce_seconds)
        self._connect = connect
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._nodes: dict[int, MatterNodeState] = {}
        self.connected = False
        self.last_error: str | None = None
        self.last_event_at: datetime | None = None
        self.last_seen: datetime | None = None
        self.last_connected: datetime | None = None
        self.last_disconnected: datetime | None = None
        self._capabilities = MatterServerCapabilities(variant=str(server_config.variant))
        self.sent_commands: list[str] = []

    @property
    def server_id(self) -> str:
        return self._server_config.id

    @property
    def running(self) -> bool:
        return self._running

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def unavailable_node_count(self) -> int:
        return sum(1 for node in self._nodes.values() if not node.available)

    async def start(self) -> None:
        if self._running:
            return
        await self._load_cache()
        self._running = True
        await self._persist_server_state()
        self._task = asyncio.create_task(self._run(), name=f"matter-observer:{self.server_id}")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    # -- connection lifecycle -------------------------------------------------

    async def _run(self) -> None:
        backoff = self._config.matter.reconnect_initial_seconds
        max_backoff = self._config.matter.reconnect_max_seconds
        while self._running:
            try:
                await self._session()
                backoff = self._config.matter.reconnect_initial_seconds
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - resilience by design
                await self._on_disconnected(str(exc))
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
                continue
            # Clean socket close; reconnect after the initial backoff.
            if self._running:
                await asyncio.sleep(backoff)

    async def _session(self) -> None:
        connect = self._connect or _default_connect
        async with connect(self._server_config.websocket_url) as websocket:
            await self._on_connected()
            await self._send_command(websocket, "start_listening")
            async for raw in websocket:
                payload = _decode_message(raw)
                if payload is None:
                    continue
                await self._handle_message(payload)
        await self._on_disconnected("connection closed")

    async def _send_command(
        self,
        websocket: WebsocketLike,
        command: str,
        args: dict[str, Any] | None = None,
    ) -> str:
        if command not in ALLOWED_COMMANDS:
            raise ValueError(f"Refusing to send non-allowlisted command: {command!r}")
        message_id = uuid.uuid4().hex
        self.sent_commands.append(command)
        await websocket.send(
            json.dumps(
                {
                    "message_id": message_id,
                    "command": command,
                    "args": args or {},
                }
            )
        )
        return message_id

    async def _on_connected(self) -> None:
        now = utc_now()
        self._capabilities.websocket_available = True
        self.last_seen = now
        self.last_connected = now
        self.last_error = None
        if not self.connected:
            self.connected = True
            await self._persist_server_state()
            await self._emit_server_event(
                event_type="matter_server.connected",
                message=f"Matter Server {self.server_id} connected",
            )
        else:
            await self._persist_server_state()

    async def _on_disconnected(self, reason: str | None) -> None:
        now = utc_now()
        self.last_error = reason
        self.last_disconnected = now
        self._capabilities.websocket_available = False
        if self.connected:
            self.connected = False
            await self._persist_server_state()
            await self._emit_server_event(
                event_type="matter_server.disconnected",
                message=f"Matter Server {self.server_id} disconnected",
                severity=EventSeverity.WARNING,
                data={"reason": reason} if reason else None,
            )
        else:
            await self._persist_server_state()

    # -- message handling -----------------------------------------------------

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        self.last_event_at = utc_now()

        # Command responses (result of start_listening / get_nodes).
        if "result" in payload and "message_id" in payload:
            await self._handle_result(payload["result"])
            return

        # Event stream messages.
        if "event" in payload:
            await self._handle_event(payload.get("event"), payload.get("data"))
            return

        # Initial ServerInfoMessage (carries no message_id / event).
        if _looks_like_server_info(payload):
            await self._persist_server_state()

    async def _handle_result(self, result: Any) -> None:
        nodes = _extract_nodes(result)
        if nodes is None:
            return
        self._capabilities.node_inventory_available = True
        for node_payload in nodes:
            await self._process_node(node_payload, is_initial=True)
        await self._persist_server_state()

    async def _handle_event(self, event_type: Any, data: Any) -> None:
        if event_type in (EVENT_NODE_ADDED, EVENT_NODE_UPDATED):
            if isinstance(data, dict):
                await self._process_node(data)
                await self._persist_server_state()
        elif event_type == EVENT_NODE_REMOVED:
            await self._process_node_removed(data)
            await self._persist_server_state()
        elif event_type == EVENT_SERVER_SHUTDOWN:
            await self._on_disconnected("server_shutdown")
        # Other events (attribute_updated, node_event, ...) are intentionally
        # ignored for Pass 6: we do not emit an event for every attribute update.

    async def _process_node(self, payload: dict[str, Any], *, is_initial: bool = False) -> None:
        parsed = parse_matter_node(payload)
        if parsed is None:
            return
        now = utc_now()
        node_id = parsed.node_id
        existing = self._nodes.get(node_id)

        if parsed.available is not None:
            self._capabilities.node_availability_available = True
            available = parsed.available
        else:
            # Missing availability means unchanged/unknown — never unavailable.
            available = existing.available if existing is not None else False

        last_unavailable = existing.last_unavailable if existing else None
        if parsed.available is False:
            last_unavailable = now

        transition_event: tuple[str, EventSeverity, str] | None = None
        if existing is None:
            transition_event = (
                "matter_node.seen",
                EventSeverity.INFO,
                f"Matter node {node_id} seen on {self.server_id}",
            )
        elif parsed.available is not None and existing.available != available:
            if available:
                transition_event = (
                    "matter_node.recovered",
                    EventSeverity.INFO,
                    f"Matter node {node_id} recovered on {self.server_id}",
                )
            else:
                transition_event = (
                    "matter_node.unavailable",
                    EventSeverity.WARNING,
                    f"Matter node {node_id} unavailable on {self.server_id}",
                )

        if transition_event is not None:
            event_type, severity, message = transition_event
            await self._emit_node_event(
                node_id=node_id,
                event_type=event_type,
                message=message,
                severity=severity,
            )

        availability_flaps_24h = await self._count_availability_flaps(node_id)

        state = MatterNodeState(
            node_id=node_id,
            server_id=self.server_id,
            friendly_name=_pick(parsed.friendly_name, existing.friendly_name if existing else None),
            vendor=_pick(parsed.vendor, existing.vendor if existing else None),
            vendor_id=_pick(parsed.vendor_id, existing.vendor_id if existing else None),
            product=_pick(parsed.product, existing.product if existing else None),
            product_id=_pick(parsed.product_id, existing.product_id if existing else None),
            serial=_pick(parsed.serial, existing.serial if existing else None),
            firmware=_pick(parsed.firmware, existing.firmware if existing else None),
            available=available,
            health=HealthStatus(state=HealthState.UNKNOWN),
            last_seen=now,
            last_unavailable=last_unavailable,
            availability_flaps_24h=availability_flaps_24h,
            subscription_flaps_24h=None,
            subscription_diagnostics_available=False,
            case_diagnostics_available=False,
            command_diagnostics_available=False,
        )
        self._nodes[node_id] = state
        await self._repository.upsert_model_state(
            CurrentStateType.MATTER_NODE,
            _node_subject_id(self.server_id, node_id),
            state,
        )

    async def _process_node_removed(self, data: Any) -> None:
        node_id: int | None = None
        if isinstance(data, dict):
            raw = data.get("node_id")
            node_id = raw if isinstance(raw, int) and not isinstance(raw, bool) else None
        elif isinstance(data, int) and not isinstance(data, bool):
            node_id = data
        if node_id is None or node_id not in self._nodes:
            return
        del self._nodes[node_id]
        await self._repository.delete_current_state(
            CurrentStateType.MATTER_NODE,
            _node_subject_id(self.server_id, node_id),
        )
        await self._emit_node_event(
            node_id=node_id,
            event_type="matter_node.removed",
            message=f"Matter node {node_id} removed from {self.server_id}",
            severity=EventSeverity.INFO,
        )

    # -- persistence helpers --------------------------------------------------

    def server_state(self) -> MatterServerState:
        return MatterServerState(
            id=self._server_config.id,
            name=self._server_config.name,
            websocket_url=self._server_config.websocket_url,
            variant=str(self._server_config.variant),
            connected=self.connected,
            health=HealthStatus(
                state=HealthState.HEALTHY if self.connected else HealthState.UNKNOWN
            ),
            node_count=self.node_count,
            unavailable_node_count=self.unavailable_node_count,
            capabilities=self._capabilities.model_copy(),
            last_seen=self.last_seen,
            last_connected=self.last_connected,
            last_disconnected=self.last_disconnected,
            last_error=self.last_error,
        )

    async def _persist_server_state(self) -> None:
        await self._repository.upsert_model_state(
            CurrentStateType.MATTER_SERVER,
            self._server_config.id,
            self.server_state(),
        )

    async def _load_cache(self) -> None:
        for payload in await self._repository.list_current_state(CurrentStateType.MATTER_NODE):
            clean = {key: value for key, value in payload.items() if not key.startswith("_")}
            node = MatterNodeState.model_validate(clean)
            if node.server_id == self.server_id:
                self._nodes[node.node_id] = node

    async def _count_availability_flaps(self, node_id: int) -> int:
        since = utc_now() - timedelta(hours=24)
        events = await self._repository.get_events(
            subject_type=EventSubjectType.MATTER_NODE.value,
            subject_id=_node_subject_id(self.server_id, node_id),
            event_type="matter_node.unavailable",
            since=since,
        )
        return len(events)

    async def _emit_server_event(
        self,
        *,
        event_type: str,
        message: str,
        severity: EventSeverity = EventSeverity.INFO,
        data: dict[str, Any] | None = None,
    ) -> None:
        if not self._debouncer.should_emit(f"{self.server_id}:{event_type}"):
            return
        await self._repository.insert_event(
            Event(
                id=str(uuid.uuid4()),
                timestamp=utc_now(),
                source_type=EventSourceType.MATTER_SERVER,
                source_id=self.server_id,
                event_type=event_type,
                severity=severity,
                subject_type=EventSubjectType.MATTER_SERVER,
                subject_id=_server_subject_id(self.server_id),
                message=message,
                data=data or {},
            )
        )

    async def _emit_node_event(
        self,
        *,
        node_id: int,
        event_type: str,
        message: str,
        severity: EventSeverity = EventSeverity.INFO,
        data: dict[str, Any] | None = None,
    ) -> None:
        if not self._debouncer.should_emit(f"{self.server_id}:{node_id}:{event_type}"):
            return
        await self._repository.insert_event(
            Event(
                id=str(uuid.uuid4()),
                timestamp=utc_now(),
                source_type=EventSourceType.MATTER_SERVER,
                source_id=self.server_id,
                event_type=event_type,
                severity=severity,
                subject_type=EventSubjectType.MATTER_NODE,
                subject_id=_node_subject_id(self.server_id, node_id),
                message=message,
                data={"node_id": node_id, **(data or {})},
            )
        )


class MatterCollector:
    """Own and aggregate one observer per configured Matter Server."""

    def __init__(
        self,
        config: ThreadLensConfig,
        repository: StorageRepository,
        *,
        connect: Any | None = None,
    ) -> None:
        self._config = config
        self._repository = repository
        self._observers: list[MatterServerObserver] = [
            MatterServerObserver(config, server_config, repository, connect=connect)
            for server_config in config.matter_servers
        ]
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    @property
    def configured_count(self) -> int:
        return len(self._config.matter_servers)

    @property
    def observers(self) -> list[MatterServerObserver]:
        return self._observers

    async def start(self) -> None:
        if self._running or not self._observers:
            return
        self._running = True
        for observer in self._observers:
            await observer.start()

    async def stop(self) -> None:
        self._running = False
        for observer in self._observers:
            await observer.stop()

    def status(self) -> dict[str, Any]:
        connected = sum(1 for obs in self._observers if obs.connected)
        nodes_seen = sum(obs.node_count for obs in self._observers)
        unavailable = sum(obs.unavailable_node_count for obs in self._observers)
        last_events = [obs.last_event_at for obs in self._observers if obs.last_event_at]
        last_event_at = max(last_events) if last_events else None
        return {
            "configured": self.configured_count,
            "collector_running": self._running,
            "connected": connected,
            "disconnected": self.configured_count - connected,
            "nodes_seen": nodes_seen,
            "unavailable_nodes": unavailable,
            "last_event_at": last_event_at.isoformat() if last_event_at else None,
        }


def _pick(new_value: Any, old_value: Any) -> Any:
    return new_value if new_value is not None else old_value


def _decode_message(raw: str | bytes) -> dict[str, Any] | None:
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _extract_nodes(result: Any) -> list[dict[str, Any]] | None:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        if "nodes" in result and isinstance(result["nodes"], list):
            return [item for item in result["nodes"] if isinstance(item, dict)]
        if "node_id" in result:
            return [result]
    return None


def _looks_like_server_info(payload: dict[str, Any]) -> bool:
    return "schema_version" in payload or "fabric_id" in payload or "sdk_version" in payload


def _default_connect(url: str):  # pragma: no cover - thin websockets wrapper
    import websockets

    return websockets.connect(url, open_timeout=10, close_timeout=5)
