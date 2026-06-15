"""OTBR REST collector."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from threadlens.collectors.otbr_parse import (
    OtbrReconciliationResult,
    ParsedOtbrSnapshot,
    ParsedThreadDevice,
    merge_snapshots,
    parse_legacy_node_response,
    parse_otbr_device_inventory,
    parse_otbr_devices_response,
    parse_otbr_node_response,
    reconcile_otbr_snapshots,
    thread_stack_active,
)
from threadlens.config import OtbrConfig, ThreadLensConfig
from threadlens.enrichment.thread_matter import apply_thread_identity_correlation
from threadlens.models.capabilities import OtbrInternalTrelCapabilities, OtbrRestCapabilities
from threadlens.models.events import Event, EventSeverity, EventSourceType, EventSubjectType
from threadlens.models.health import HealthState, HealthStatus
from threadlens.models.state import (
    OtbrState,
    ThreadDeviceState,
    ThreadNetworkClassification,
    ThreadNetworkState,
    TrelServiceState,
)
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.debounce import EventDebouncer
from threadlens.utils.time import utc_now

ALLOWED_GET_PATHS = ("/api/node", "/api/devices", "/node")
ALLOWED_READ_ONLY_ACTIONS = frozenset({"getNetworkDiagnosticTask", "updateDeviceCollectionTask"})
FORBIDDEN_ACTIONS = frozenset({"resetNetworkDiagCounterTask"})


@dataclass(frozen=True)
class PollResult:
    otbr_id: str
    state: OtbrState


class OtbrCollector:
    """Poll configured OTBR REST endpoints and persist state/events."""

    def __init__(
        self,
        config: ThreadLensConfig,
        repository: StorageRepository,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._repository = repository
        self._debouncer = EventDebouncer(config.flapping.debounce_seconds)
        self._client = client
        self._owns_client = client is None
        self._known_otbrs: dict[str, OtbrState] = {}
        self._known_networks: dict[str, ThreadNetworkState] = {}
        self._last_device_collection_at: dict[str, datetime] = {}
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self.last_poll_at: datetime | None = None
        self.reachable_count = 0
        self.unreachable_count = 0

    @property
    def running(self) -> bool:
        return self._running

    @property
    def configured_count(self) -> int:
        return len(self._config.otbrs)

    async def start(self) -> None:
        if self._running or not self._config.otbrs:
            return
        if self._client is None:
            timeout = self._config.otbr.request_timeout_seconds
            self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        await self._load_cache()
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="otbr-collector")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def poll_all(self) -> list[PollResult]:
        self.last_poll_at = utc_now()
        results: list[PollResult] = []
        configured_ext_pan_ids: dict[str, set[str]] = {}

        for otbr_config in self._config.otbrs:
            try:
                result = await self.poll_one(otbr_config)
            except Exception as exc:  # noqa: BLE001 - isolate per-OTBR failures
                result = await self._mark_unreachable(
                    otbr_config,
                    last_error=str(exc),
                )
            results.append(result)
            if result.state.reachable and result.state.ext_pan_id:
                configured_ext_pan_ids.setdefault(result.state.ext_pan_id, set()).add(
                    result.state.id
                )

        self.reachable_count = sum(1 for result in results if result.state.reachable)
        self.unreachable_count = len(results) - self.reachable_count
        await self._sync_thread_networks(configured_ext_pan_ids)
        await self._correlate_trel_services(set(configured_ext_pan_ids.keys()))
        return results

    async def poll_one(self, otbr_config: OtbrConfig) -> PollResult:
        assert self._client is not None
        base_url = otbr_config.rest_url.rstrip("/")
        node_ok = False
        devices_ok = False
        node_snapshot = ParsedOtbrSnapshot()
        devices_snapshot = ParsedOtbrSnapshot()
        last_error: str | None = None

        try:
            node_response = await self._client.get(f"{base_url}/api/node")
            if node_response.status_code == 200:
                node_ok = True
                node_snapshot = parse_otbr_node_response(node_response.json())
            else:
                last_error = f"/api/node returned {node_response.status_code}"
        except httpx.HTTPError as exc:
            return await self._mark_unreachable(otbr_config, last_error=str(exc))

        try:
            devices_response = await self._client.get(f"{base_url}/api/devices")
            if devices_response.status_code == 200:
                devices_ok = True
                devices_snapshot = parse_otbr_devices_response(devices_response.json())
            elif last_error is None:
                last_error = f"/api/devices returned {devices_response.status_code}"
        except httpx.HTTPError:
            devices_ok = False

        if not node_ok:
            return await self._mark_unreachable(otbr_config, last_error=last_error or "unreachable")

        legacy_snapshot: ParsedOtbrSnapshot | None = None
        legacy_ok = False
        if self._config.otbr.use_legacy_node_fallback:
            try:
                legacy_response = await self._client.get(f"{base_url}/node")
                if legacy_response.status_code == 200:
                    legacy_ok = True
                    legacy_snapshot = parse_legacy_node_response(legacy_response.json())
                elif last_error is None:
                    last_error = f"/node returned {legacy_response.status_code}"
            except httpx.HTTPError:
                legacy_ok = False

        merged_json_api = merge_snapshots(node_snapshot, devices_snapshot)
        reconciliation = reconcile_otbr_snapshots(
            merged_json_api,
            legacy_snapshot,
            legacy_available=legacy_ok,
            use_legacy_fallback=self._config.otbr.use_legacy_node_fallback,
        )
        snapshot = reconciliation.snapshot
        result = await self._apply_reachable_state(
            otbr_config,
            snapshot=snapshot,
            reconciliation=reconciliation,
            capabilities=OtbrRestCapabilities(
                rest_available=True,
                network_dataset_available=snapshot.ext_pan_id is not None,
                thread_stack_active=thread_stack_active(snapshot.thread_state),
                legacy_node_available=reconciliation.legacy_node_available,
                json_api_state_stale=reconciliation.json_api_state_stale,
                topology_available=devices_ok,
                network_diagnostics_available=False,
                device_inventory_available=devices_ok and snapshot.device_count is not None,
            ),
            last_error=last_error,
        )
        if (
            self._config.otbr.allow_read_only_actions
            and devices_ok
            and thread_stack_active(snapshot.thread_state)
        ):
            await self._maybe_refresh_device_inventory(
                otbr_config,
                ext_pan_id=snapshot.ext_pan_id,
            )
        return result

    async def _poll_loop(self) -> None:
        while self._running:
            await self.poll_all()
            await asyncio.sleep(self._config.otbr.poll_interval_seconds)

    async def _mark_unreachable(self, otbr_config: OtbrConfig, *, last_error: str) -> PollResult:
        previous = self._known_otbrs.get(otbr_config.id)
        state = OtbrState(
            id=otbr_config.id,
            name=otbr_config.name,
            rest_url=otbr_config.rest_url,
            reachable=False,
            health=HealthStatus(
                state=HealthState.CRITICAL,
                reasons=["otbr_unreachable"],
            ),
            last_seen=previous.last_seen if previous else None,
            last_error=last_error,
            capabilities=previous.capabilities if previous else OtbrRestCapabilities(),
            internal_trel=previous.internal_trel if previous else OtbrInternalTrelCapabilities(),
        )
        if previous:
            state = previous.model_copy(
                update={
                    "reachable": False,
                    "health": HealthStatus(
                        state=HealthState.CRITICAL,
                        reasons=["otbr_unreachable"],
                    ),
                    "last_error": last_error,
                }
            )
        self._known_otbrs[otbr_config.id] = state
        await self._repository.upsert_model_state(CurrentStateType.OTBR, otbr_config.id, state)
        if previous is None or previous.reachable:
            await self._emit_otbr_event(
                event_type="otbr.unreachable",
                otbr_id=otbr_config.id,
                message=f"OTBR {otbr_config.name} is unreachable",
                severity=EventSeverity.WARNING,
                data={"last_error": last_error},
            )
        return PollResult(otbr_id=otbr_config.id, state=state)

    async def _apply_reachable_state(
        self,
        otbr_config: OtbrConfig,
        *,
        snapshot: ParsedOtbrSnapshot,
        reconciliation: OtbrReconciliationResult,
        capabilities: OtbrRestCapabilities,
        last_error: str | None,
    ) -> PollResult:
        previous = self._known_otbrs.get(otbr_config.id)
        now = utc_now()
        state = OtbrState(
            id=otbr_config.id,
            name=otbr_config.name,
            rest_url=otbr_config.rest_url,
            reachable=True,
            health=HealthStatus(state=HealthState.UNKNOWN),
            thread_state=snapshot.thread_state,
            thread_state_source=reconciliation.thread_state_source,
            json_api_thread_state=reconciliation.json_api_thread_state,
            legacy_node_thread_state=reconciliation.legacy_node_thread_state,
            rest_endpoint_mismatch=reconciliation.rest_endpoint_mismatch,
            role=snapshot.role,
            network_name=snapshot.network_name,
            channel=snapshot.channel,
            ext_pan_id=snapshot.ext_pan_id,
            pan_id=snapshot.pan_id,
            rloc16=snapshot.rloc16,
            last_seen=now,
            last_error=last_error,
            capabilities=capabilities,
        )
        if previous:
            state = previous.model_copy(
                update={
                    "reachable": True,
                    "health": HealthStatus(state=HealthState.UNKNOWN),
                    "thread_state": snapshot.thread_state,
                    "thread_state_source": reconciliation.thread_state_source,
                    "json_api_thread_state": reconciliation.json_api_thread_state,
                    "legacy_node_thread_state": reconciliation.legacy_node_thread_state,
                    "rest_endpoint_mismatch": reconciliation.rest_endpoint_mismatch,
                    "role": snapshot.role,
                    "network_name": snapshot.network_name,
                    "channel": snapshot.channel,
                    "ext_pan_id": snapshot.ext_pan_id,
                    "pan_id": snapshot.pan_id,
                    "rloc16": snapshot.rloc16,
                    "last_seen": now,
                    "last_error": last_error,
                    "capabilities": capabilities,
                }
            )

        self._known_otbrs[otbr_config.id] = state
        await self._repository.upsert_model_state(CurrentStateType.OTBR, otbr_config.id, state)

        if previous is None or not previous.reachable:
            await self._emit_otbr_event(
                event_type="otbr.reachable",
                otbr_id=otbr_config.id,
                message=f"OTBR {otbr_config.name} is reachable",
                severity=EventSeverity.INFO,
            )
        if (
            previous
            and previous.reachable
            and previous.role != state.role
            and state.role is not None
        ):
            await self._emit_otbr_event(
                event_type="otbr.role_changed",
                otbr_id=otbr_config.id,
                message=f"OTBR {otbr_config.name} role changed to {state.role}",
                severity=EventSeverity.INFO,
                data={"previous_role": previous.role, "role": state.role},
            )
        if previous and previous.reachable and _dataset_changed(previous, state):
            await self._emit_otbr_event(
                event_type="otbr.dataset_changed",
                otbr_id=otbr_config.id,
                message=f"OTBR {otbr_config.name} dataset/network changed",
                severity=EventSeverity.WARNING,
                data={
                    "previous_ext_pan_id": previous.ext_pan_id,
                    "ext_pan_id": state.ext_pan_id,
                    "previous_channel": previous.channel,
                    "channel": state.channel,
                },
            )
        return PollResult(otbr_id=otbr_config.id, state=state)

    async def _sync_thread_networks(self, configured_ext_pan_ids: dict[str, set[str]]) -> None:
        now = utc_now()
        primary_ext_pan_id, primary_class = classify_primary_network(
            set(configured_ext_pan_ids.keys())
        )
        seen_ids: set[str] = set()

        for ext_pan_id, otbr_ids in configured_ext_pan_ids.items():
            seen_ids.add(ext_pan_id)
            previous = self._known_networks.get(ext_pan_id)
            sample_otbr = next(
                (
                    self._known_otbrs[otbr_id]
                    for otbr_id in otbr_ids
                    if otbr_id in self._known_otbrs
                ),
                None,
            )
            classification = (
                ThreadNetworkClassification.PRIMARY
                if ext_pan_id == primary_ext_pan_id
                and primary_class == ThreadNetworkClassification.PRIMARY
                else ThreadNetworkClassification.UNKNOWN
                if primary_class == ThreadNetworkClassification.UNKNOWN
                else ThreadNetworkClassification.OBSERVED_OTHER
            )
            network = ThreadNetworkState(
                ext_pan_id=ext_pan_id,
                name=sample_otbr.network_name
                if sample_otbr
                else previous.name
                if previous
                else None,
                channel=sample_otbr.channel
                if sample_otbr
                else previous.channel
                if previous
                else None,
                pan_id=sample_otbr.pan_id if sample_otbr else previous.pan_id if previous else None,
                classification=classification,
                currently_visible=True,
                border_router_count=len(otbr_ids),
                source_otbr_ids=sorted(otbr_ids),
                first_seen=previous.first_seen if previous and previous.first_seen else now,
                last_seen=now,
            )
            self._known_networks[ext_pan_id] = network
            await self._repository.upsert_model_state(
                CurrentStateType.THREAD_NETWORK,
                ext_pan_id,
                network,
            )
            if previous is None or not previous.currently_visible:
                await self._emit_network_event(
                    event_type="thread_network.seen",
                    network=network,
                    message=f"Thread network {ext_pan_id} seen",
                )

        for ext_pan_id, previous in list(self._known_networks.items()):
            if ext_pan_id in seen_ids:
                continue
            if not previous.currently_visible:
                continue
            lost = previous.model_copy(update={"currently_visible": False, "last_seen": now})
            self._known_networks[ext_pan_id] = lost
            await self._repository.upsert_model_state(
                CurrentStateType.THREAD_NETWORK,
                ext_pan_id,
                lost,
            )
            await self._emit_network_event(
                event_type="thread_network.lost",
                network=lost,
                message=f"Thread network {ext_pan_id} lost",
                severity=EventSeverity.WARNING,
            )

    async def _correlate_trel_services(self, configured_ext_pan_ids: set[str]) -> None:
        primary_ext_pan_id, primary_class = classify_primary_network(configured_ext_pan_ids)
        payloads = await self._repository.list_current_state(CurrentStateType.TREL_SERVICE)
        for payload in payloads:
            clean = {key: value for key, value in payload.items() if not key.startswith("_")}
            trel = TrelServiceState.model_validate(clean)
            is_foreign, classification = classify_trel_service(
                trel.ext_pan_id,
                configured_ext_pan_ids=configured_ext_pan_ids,
                primary_ext_pan_id=primary_ext_pan_id,
                primary_class=primary_class,
            )
            updated = trel.model_copy(
                update={
                    "is_foreign": is_foreign,
                    "network_classification": classification,
                }
            )
            await self._repository.upsert_model_state(
                CurrentStateType.TREL_SERVICE,
                updated.service_id,
                updated,
            )

    async def _load_cache(self) -> None:
        for payload in await self._repository.list_current_state(CurrentStateType.OTBR):
            state = _payload_to_otbr(payload)
            self._known_otbrs[state.id] = state
        for payload in await self._repository.list_current_state(CurrentStateType.THREAD_NETWORK):
            state = _payload_to_network(payload)
            self._known_networks[state.ext_pan_id] = state

    async def _emit_otbr_event(
        self,
        *,
        event_type: str,
        otbr_id: str,
        message: str,
        severity: EventSeverity = EventSeverity.INFO,
        data: dict[str, Any] | None = None,
    ) -> None:
        if not self._debouncer.should_emit(f"{otbr_id}:{event_type}"):
            return
        await self._repository.insert_event(
            Event(
                id=str(uuid.uuid4()),
                timestamp=utc_now(),
                source_type=EventSourceType.OTBR,
                source_id=otbr_id,
                event_type=event_type,
                severity=severity,
                subject_type=EventSubjectType.OTBR,
                subject_id=f"otbr:{otbr_id}",
                message=message,
                data=data or {},
            )
        )

    async def _emit_network_event(
        self,
        *,
        event_type: str,
        network: ThreadNetworkState,
        message: str,
        severity: EventSeverity = EventSeverity.INFO,
    ) -> None:
        if not self._debouncer.should_emit(f"{network.ext_pan_id}:{event_type}"):
            return
        await self._repository.insert_event(
            Event(
                id=str(uuid.uuid4()),
                timestamp=utc_now(),
                source_type=EventSourceType.OTBR,
                source_id=network.ext_pan_id,
                event_type=event_type,
                severity=severity,
                subject_type=EventSubjectType.THREAD_NETWORK,
                subject_id=f"thread_network:{network.ext_pan_id}",
                message=message,
                data={
                    "ext_pan_id": network.ext_pan_id,
                    "classification": network.classification.value,
                },
            )
        )

    async def _maybe_refresh_device_inventory(
        self,
        otbr_config: OtbrConfig,
        *,
        ext_pan_id: str | None,
    ) -> None:
        now = utc_now()
        last_run = self._last_device_collection_at.get(otbr_config.id)
        if (
            last_run is not None
            and (now - last_run).total_seconds()
            < self._config.otbr.device_collection_interval_seconds
        ):
            return

        assert self._client is not None
        base_url = otbr_config.rest_url.rstrip("/")
        try:
            action_id = await self._start_device_collection_task(base_url)
            if action_id is None:
                return
            completed = await self._wait_for_action(
                base_url,
                action_id,
                timeout_seconds=self._config.otbr.device_collection_timeout_seconds,
            )
            if not completed:
                return
            devices_response = await self._client.get(f"{base_url}/api/devices")
            if devices_response.status_code != 200:
                return
            inventory = parse_otbr_device_inventory(devices_response.json())
            await self._persist_device_inventory(
                otbr_config.id,
                inventory,
                ext_pan_id=ext_pan_id,
            )
            self._last_device_collection_at[otbr_config.id] = now
            await apply_thread_identity_correlation(self._repository)
        except httpx.HTTPError:
            return

    async def _start_device_collection_task(self, base_url: str) -> str | None:
        assert self._client is not None
        response = await self._client.post(
            f"{base_url}/api/actions",
            headers={"Content-Type": "application/vnd.api+json"},
            json={
                "data": [
                    {
                        "type": "updateDeviceCollectionTask",
                        "attributes": {
                            "maxAge": 30,
                            "maxRetries": 5,
                            "deviceCount": 50,
                            "timeout": self._config.otbr.device_collection_timeout_seconds,
                        },
                    }
                ]
            },
        )
        if response.status_code not in {200, 201, 202}:
            return None
        payload = response.json()
        data = payload.get("data")
        if isinstance(data, list) and data:
            item = data[0]
            if isinstance(item, dict) and item.get("id"):
                return str(item["id"])
        if isinstance(data, dict) and data.get("id"):
            return str(data["id"])
        return None

    async def _wait_for_action(
        self,
        base_url: str,
        action_id: str,
        *,
        timeout_seconds: int,
    ) -> bool:
        assert self._client is not None
        deadline = utc_now().timestamp() + timeout_seconds
        while utc_now().timestamp() < deadline:
            response = await self._client.get(f"{base_url}/api/actions/{action_id}")
            if response.status_code != 200:
                return False
            payload = response.json()
            data = payload.get("data")
            attributes = data.get("attributes") if isinstance(data, dict) else None
            if not isinstance(attributes, dict) and isinstance(data, list) and data:
                item = data[0]
                attributes = item.get("attributes") if isinstance(item, dict) else None
            status = (
                str(attributes.get("status") or "").lower() if isinstance(attributes, dict) else ""
            )
            if status in {"completed", "stopped"}:
                return True
            if status == "failed":
                return False
            await asyncio.sleep(2)
        return False

    async def _persist_device_inventory(
        self,
        otbr_id: str,
        inventory: list[ParsedThreadDevice],
        *,
        ext_pan_id: str | None,
    ) -> None:
        now = utc_now()
        seen_ids: set[str] = set()
        for device in inventory:
            object_id = f"{otbr_id}:{device.extended_address}"
            seen_ids.add(object_id)
            state = ThreadDeviceState(
                id=object_id,
                extended_address=device.extended_address,
                ipv6_address=device.ipv6_address,
                rloc_address=device.rloc_address,
                role=device.role,
                device_type=device.device_type,
                hostname=device.hostname,
                source_otbr_id=otbr_id,
                ext_pan_id=ext_pan_id,
                last_seen=now,
            )
            await self._repository.upsert_model_state(
                CurrentStateType.THREAD_DEVICE,
                object_id,
                state,
            )

        stored = await self._repository.list_current_state(CurrentStateType.THREAD_DEVICE)
        for raw in stored:
            if not isinstance(raw, dict):
                continue
            object_id = str(raw.get("id") or "")
            source_otbr_id = str(raw.get("source_otbr_id") or "")
            if source_otbr_id == otbr_id and object_id and object_id not in seen_ids:
                await self._repository.delete_current_state(
                    CurrentStateType.THREAD_DEVICE,
                    object_id,
                )


def classify_primary_network(
    ext_pan_ids: set[str],
) -> tuple[str | None, ThreadNetworkClassification]:
    if not ext_pan_ids:
        return None, ThreadNetworkClassification.UNKNOWN
    if len(ext_pan_ids) == 1:
        return next(iter(ext_pan_ids)), ThreadNetworkClassification.PRIMARY
    return None, ThreadNetworkClassification.UNKNOWN


def classify_trel_service(
    ext_pan_id: str | None,
    *,
    configured_ext_pan_ids: set[str],
    primary_ext_pan_id: str | None,
    primary_class: ThreadNetworkClassification,
) -> tuple[bool | None, ThreadNetworkClassification | None]:
    if ext_pan_id is None:
        return None, ThreadNetworkClassification.UNKNOWN
    if ext_pan_id in configured_ext_pan_ids:
        if (
            primary_class == ThreadNetworkClassification.PRIMARY
            and ext_pan_id == primary_ext_pan_id
        ):
            return False, ThreadNetworkClassification.PRIMARY
        return False, ThreadNetworkClassification.OBSERVED_OTHER
    return True, ThreadNetworkClassification.OBSERVED_OTHER


def _dataset_changed(previous: OtbrState, current: OtbrState) -> bool:
    return (
        previous.ext_pan_id != current.ext_pan_id
        or previous.channel != current.channel
        or previous.network_name != current.network_name
        or previous.pan_id != current.pan_id
    )


def _payload_to_otbr(payload: dict[str, Any]) -> OtbrState:
    clean = {key: value for key, value in payload.items() if not key.startswith("_")}
    return OtbrState.model_validate(clean)


def _payload_to_network(payload: dict[str, Any]) -> ThreadNetworkState:
    clean = {key: value for key, value in payload.items() if not key.startswith("_")}
    return ThreadNetworkState.model_validate(clean)
