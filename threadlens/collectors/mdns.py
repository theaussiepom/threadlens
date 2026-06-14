"""mDNS/DNS-SD observer for ThreadLens."""

from __future__ import annotations

import asyncio
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from threadlens.collectors.mdns_txt import (
    decode_txt_properties,
    ext_address_from_txt,
    ext_pan_id_from_txt,
    is_trel_service_type,
)
from threadlens.config import ThreadLensConfig
from threadlens.models.events import Event, EventSeverity, EventSourceType, EventSubjectType
from threadlens.models.state import MdnsServiceState, TrelServiceState
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.debounce import EventDebouncer
from threadlens.utils.ids import normalize_mdns_service_id
from threadlens.utils.time import utc_now

try:
    from zeroconf import ServiceInfo
    from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf
except ImportError:  # pragma: no cover - guarded by dependency
    ServiceInfo = Any  # type: ignore[misc, assignment]
    AsyncServiceBrowser = Any  # type: ignore[misc, assignment]
    AsyncZeroconf = Any  # type: ignore[misc, assignment]


@dataclass(frozen=True)
class NormalizedMdnsRecord:
    service_id: str
    service_type: str
    instance_name: str
    hostname: str | None
    addresses: list[str]
    port: int | None
    txt_records: dict[str, str]
    raw_properties: dict[Any, Any] | None = None


def normalize_service_info(info: ServiceInfo) -> NormalizedMdnsRecord:
    """Normalise a zeroconf ServiceInfo into a stable ThreadLens record."""
    service_type = _ensure_trailing_dot(info.type or "")
    instance_name = info.name or ""
    service_id = normalize_mdns_service_id(instance_name, service_type)
    txt_records = decode_txt_properties(info.properties)
    addresses = _extract_addresses(info)
    hostname = (info.server or "").rstrip(".") or None
    port = info.port or None
    return NormalizedMdnsRecord(
        service_id=service_id,
        service_type=service_type,
        instance_name=instance_name,
        hostname=hostname,
        addresses=addresses,
        port=port,
        txt_records=txt_records,
        raw_properties=info.properties,
    )


def build_mdns_state(
    record: NormalizedMdnsRecord,
    *,
    previous: MdnsServiceState | None,
    now: datetime,
    visible: bool,
    changed: bool,
) -> MdnsServiceState:
    first_seen = previous.first_seen if previous and previous.first_seen else now
    change_count = previous.change_count if previous else 0
    last_changed = previous.last_changed if previous else None
    if changed:
        change_count += 1
        last_changed = now
    return MdnsServiceState(
        service_id=record.service_id,
        service_type=record.service_type,
        instance_name=record.instance_name,
        hostname=record.hostname,
        addresses=record.addresses,
        port=record.port,
        txt_records=record.txt_records,
        currently_visible=visible,
        first_seen=first_seen,
        last_seen=now,
        last_changed=last_changed,
        change_count=change_count,
    )


def build_trel_state(
    mdns_state: MdnsServiceState,
    *,
    record: NormalizedMdnsRecord,
    previous: TrelServiceState | None,
    now: datetime,
    visible: bool,
    changed: bool,
) -> TrelServiceState:
    first_seen = previous.first_seen if previous and previous.first_seen else now
    change_count = previous.change_count if previous else 0
    last_changed = previous.last_changed if previous else None
    if changed:
        change_count += 1
        last_changed = now
    return TrelServiceState(
        service_id=mdns_state.service_id,
        instance_name=mdns_state.instance_name,
        hostname=mdns_state.hostname,
        addresses=mdns_state.addresses,
        port=mdns_state.port,
        txt_records=mdns_state.txt_records,
        ext_pan_id=ext_pan_id_from_txt(
            mdns_state.txt_records,
            raw_properties=record.raw_properties,
        ),
        ext_address=ext_address_from_txt(
            mdns_state.txt_records,
            raw_properties=record.raw_properties,
        ),
        currently_visible=visible,
        is_foreign=None,
        first_seen=first_seen,
        last_seen=now,
        last_changed=last_changed,
        change_count=change_count,
    )


def _meaningful_snapshot(state: MdnsServiceState) -> dict[str, Any]:
    return {
        "hostname": state.hostname,
        "addresses": sorted(state.addresses),
        "port": state.port,
        "txt_records": dict(sorted(state.txt_records.items())),
    }


def _ensure_trailing_dot(value: str) -> str:
    return value if value.endswith(".") else f"{value}."


def _extract_addresses(info: ServiceInfo) -> list[str]:
    addresses: list[str] = []
    if hasattr(info, "parsed_addresses"):
        try:
            addresses = [str(address) for address in info.parsed_addresses()]
        except Exception:
            addresses = []
    if not addresses and info.addresses:
        for packed in info.addresses:
            try:
                addresses.append(socket.inet_ntop(socket.AF_INET, packed))
            except OSError:
                try:
                    addresses.append(socket.inet_ntop(socket.AF_INET6, packed))
                except OSError:
                    continue
    return sorted(set(addresses))


class MdnsObserver:
    """Observe configured mDNS service types and persist state/events."""

    def __init__(self, config: ThreadLensConfig, repository: StorageRepository) -> None:
        self._config = config
        self._repository = repository
        self._debouncer = EventDebouncer(config.flapping.debounce_seconds)
        self._known_mdns: dict[str, MdnsServiceState] = {}
        self._known_trel: dict[str, TrelServiceState] = {}
        self._aiozc: AsyncZeroconf | None = None
        self._browser: AsyncServiceBrowser | None = None
        self._running = False
        self.observation_degraded: bool | None = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def services_configured(self) -> int:
        return len(self._config.mdns.services)

    async def start(self) -> None:
        if self._running or not self._config.mdns.enabled:
            return
        await self._load_cache()
        loop = asyncio.get_running_loop()
        self._aiozc = AsyncZeroconf()
        listener = _AsyncMdnsListener(self, loop)
        self._browser = AsyncServiceBrowser(
            self._aiozc.zeroconf,
            self._config.mdns.services,
            listener=listener,
        )
        self._running = True
        self.observation_degraded = None

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.async_cancel()
            self._browser = None
        if self._aiozc is not None:
            await self._aiozc.async_close()
            self._aiozc = None
        self._running = False

    async def on_service_added(self, info: ServiceInfo) -> None:
        record = normalize_service_info(info)
        await self.process_service_added(record)
        self._mark_observation_success()

    async def on_service_updated(self, info: ServiceInfo) -> None:
        record = normalize_service_info(info)
        await self.process_service_updated(record)
        self._mark_observation_success()

    async def on_service_removed(self, service_type: str, instance_name: str) -> None:
        record = NormalizedMdnsRecord(
            service_id=normalize_mdns_service_id(instance_name, _ensure_trailing_dot(service_type)),
            service_type=_ensure_trailing_dot(service_type),
            instance_name=instance_name,
            hostname=None,
            addresses=[],
            port=None,
            txt_records={},
        )
        await self.process_service_removed(record)
        self._mark_observation_success()

    def _mark_observation_success(self) -> None:
        if self.observation_degraded is None:
            self.observation_degraded = False

    async def process_service_added(self, record: NormalizedMdnsRecord) -> None:
        previous = self._known_mdns.get(record.service_id)
        now = utc_now()
        if previous and previous.currently_visible and not _record_changed(previous, record):
            previous.last_seen = now
            self._known_mdns[record.service_id] = previous
            await self._persist_mdns(previous)
            return

        changed = bool(
            previous and previous.currently_visible and _record_changed(previous, record)
        )
        state = build_mdns_state(
            record,
            previous=previous,
            now=now,
            visible=True,
            changed=changed,
        )
        self._known_mdns[record.service_id] = state
        await self._persist_mdns(state)

        event_type = "mdns.service_changed" if changed else "mdns.service_added"
        await self._emit_mdns_event(
            event_type=event_type,
            state=state,
            message=f"mDNS service {state.instance_name} {event_type.split('.')[-1]}",
            debounce_key=f"{state.service_id}:{event_type}",
            initial_observation=event_type == "mdns.service_added" and previous is None,
        )

        if is_trel_service_type(record.service_type):
            await self._upsert_trel(
                record,
                state,
                now=now,
                visible=True,
                changed=changed,
                is_new=previous is None or not previous.currently_visible,
            )

    async def process_service_updated(self, record: NormalizedMdnsRecord) -> None:
        previous = self._known_mdns.get(record.service_id)
        if previous and not _record_changed(previous, record):
            previous.last_seen = utc_now()
            self._known_mdns[record.service_id] = previous
            await self._persist_mdns(previous)
            return
        await self.process_service_added(record)

    async def process_service_removed(self, record: NormalizedMdnsRecord) -> None:
        previous = self._known_mdns.get(record.service_id)
        now = utc_now()
        if previous is None:
            return
        if not previous.currently_visible:
            previous.last_seen = now
            self._known_mdns[record.service_id] = previous
            await self._persist_mdns(previous)
            return

        state = previous.model_copy(update={"currently_visible": False, "last_seen": now})
        self._known_mdns[record.service_id] = state
        await self._persist_mdns(state)
        await self._emit_mdns_event(
            event_type="mdns.service_removed",
            state=state,
            message=f"mDNS service {state.instance_name} removed",
            debounce_key=f"{state.service_id}:mdns.service_removed",
            initial_observation=False,
        )

        if is_trel_service_type(record.service_type):
            trel_previous = self._known_trel.get(record.service_id)
            if trel_previous is not None:
                trel_state = trel_previous.model_copy(
                    update={"currently_visible": False, "last_seen": now}
                )
                self._known_trel[record.service_id] = trel_state
                await self._persist_trel(trel_state)
                await self._emit_trel_event(
                    event_type="trel.service_removed",
                    state=trel_state,
                    message=f"TREL service {trel_state.instance_name} removed",
                    debounce_key=f"{trel_state.service_id}:trel.service_removed",
                    initial_observation=False,
                )

    async def list_mdns_services(self) -> list[MdnsServiceState]:
        return list(self._known_mdns.values())

    async def list_trel_services(self) -> list[TrelServiceState]:
        return list(self._known_trel.values())

    async def _load_cache(self) -> None:
        for payload in await self._repository.list_current_state(CurrentStateType.MDNS_SERVICE):
            state = _payload_to_model(payload, MdnsServiceState)
            self._known_mdns[state.service_id] = state
        for payload in await self._repository.list_current_state(CurrentStateType.TREL_SERVICE):
            state = _payload_to_model(payload, TrelServiceState)
            self._known_trel[state.service_id] = state

    async def _upsert_trel(
        self,
        record: NormalizedMdnsRecord,
        mdns_state: MdnsServiceState,
        *,
        now: datetime,
        visible: bool,
        changed: bool,
        is_new: bool,
    ) -> None:
        previous = self._known_trel.get(record.service_id)
        trel_state = build_trel_state(
            mdns_state,
            record=record,
            previous=previous,
            now=now,
            visible=visible,
            changed=changed,
        )
        self._known_trel[record.service_id] = trel_state
        await self._persist_trel(trel_state)

        if is_new:
            event_type = "trel.service_added"
        elif changed:
            event_type = "trel.service_changed"
        else:
            return

        await self._emit_trel_event(
            event_type=event_type,
            state=trel_state,
            message=f"TREL service {trel_state.instance_name} {event_type.split('.')[-1]}",
            debounce_key=f"{trel_state.service_id}:{event_type}",
            initial_observation=(event_type == "trel.service_added" and previous is None),
        )

    async def _persist_mdns(self, state: MdnsServiceState) -> None:
        await self._repository.upsert_model_state(
            CurrentStateType.MDNS_SERVICE,
            state.service_id,
            state,
        )

    async def _persist_trel(self, state: TrelServiceState) -> None:
        await self._repository.upsert_model_state(
            CurrentStateType.TREL_SERVICE,
            state.service_id,
            state,
        )

    async def _emit_mdns_event(
        self,
        *,
        event_type: str,
        state: MdnsServiceState,
        message: str,
        debounce_key: str,
        initial_observation: bool = False,
    ) -> None:
        if not self._debouncer.should_emit(debounce_key):
            return
        await self._repository.insert_event(
            Event(
                id=str(uuid.uuid4()),
                timestamp=utc_now(),
                source_type=EventSourceType.MDNS,
                source_id=state.service_id,
                event_type=event_type,
                severity=EventSeverity.INFO,
                subject_type=EventSubjectType.MDNS_SERVICE,
                subject_id=f"mdns_service:{state.service_id}",
                message=message,
                data={
                    "service_type": state.service_type,
                    "instance_name": state.instance_name,
                    "currently_visible": state.currently_visible,
                    "initial_observation": initial_observation,
                },
            )
        )

    async def _emit_trel_event(
        self,
        *,
        event_type: str,
        state: TrelServiceState,
        message: str,
        debounce_key: str,
        initial_observation: bool = False,
    ) -> None:
        if not self._debouncer.should_emit(debounce_key):
            return
        await self._repository.insert_event(
            Event(
                id=str(uuid.uuid4()),
                timestamp=utc_now(),
                source_type=EventSourceType.MDNS,
                source_id=state.service_id,
                event_type=event_type,
                severity=EventSeverity.INFO,
                subject_type=EventSubjectType.TREL_SERVICE,
                subject_id=f"trel_service:{state.service_id}",
                message=message,
                data={
                    "instance_name": state.instance_name,
                    "ext_pan_id": state.ext_pan_id,
                    "currently_visible": state.currently_visible,
                    "initial_observation": initial_observation,
                },
            )
        )


class _AsyncMdnsListener:
    """Bridge zeroconf sync ServiceListener callbacks to async observer methods."""

    def __init__(self, observer: MdnsObserver, loop: asyncio.AbstractEventLoop) -> None:
        self._observer = observer
        self._loop = loop

    def add_service(self, zc: Any, type_: str, name: str) -> None:
        self._schedule(self.async_add_service(zc, type_, name))

    def update_service(self, zc: Any, type_: str, name: str) -> None:
        self._schedule(self.async_update_service(zc, type_, name))

    def remove_service(self, zc: Any, type_: str, name: str) -> None:
        self._schedule(self.async_remove_service(zc, type_, name))

    def _schedule(self, coro: Any) -> None:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is self._loop:
            self._loop.create_task(coro)
            return
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def async_add_service(self, zc: Any, type_: str, name: str) -> None:
        info = await zc.async_get_service_info(type_, name)
        if info is not None:
            await self._observer.on_service_added(info)

    async def async_update_service(self, zc: Any, type_: str, name: str) -> None:
        info = await zc.async_get_service_info(type_, name)
        if info is not None:
            await self._observer.on_service_updated(info)

    async def async_remove_service(self, zc: Any, type_: str, name: str) -> None:
        await self._observer.on_service_removed(type_, name)


def _record_changed(previous: MdnsServiceState, record: NormalizedMdnsRecord) -> bool:
    candidate = MdnsServiceState(
        service_id=record.service_id,
        service_type=record.service_type,
        instance_name=record.instance_name,
        hostname=record.hostname,
        addresses=record.addresses,
        port=record.port,
        txt_records=record.txt_records,
        currently_visible=True,
    )
    return _meaningful_snapshot(previous) != _meaningful_snapshot(candidate)


def _payload_to_model(
    payload: dict[str, Any], model_type: type[MdnsServiceState | TrelServiceState]
):
    clean = {key: value for key, value in payload.items() if not key.startswith("_")}
    return model_type.model_validate(clean)
