"""Calculate factual health from stored state and events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from threadlens.collectors.matter_server import MatterCollector
from threadlens.collectors.mdns import MdnsObserver
from threadlens.collectors.otbr_rest import OtbrCollector, classify_primary_network
from threadlens.config import ThreadLensConfig
from threadlens.health.rollup import health_from_candidates, merge_health
from threadlens.models.events import EventSeverity
from threadlens.models.health import (
    EnvironmentSummary,
    HealthReport,
    HealthState,
    HealthStatus,
    MatterNodeHealthResult,
    MatterServerHealthResult,
    OtbrHealthResult,
    ThreadNetworkHealthResult,
)
from threadlens.models.state import (
    MatterNodeState,
    MatterServerState,
    OtbrState,
    ThreadNetworkClassification,
    ThreadNetworkState,
    TrelServiceState,
)
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.time import utc_now

# Service visibility instability for health uses add/remove cycles only.
# service_changed events remain in history for diagnostics but are not counted
# because mDNS update callbacks often reflect normal TXT/address refresh churn.
MDNS_FLAP_EVENTS = (
    "mdns.service_added",
    "mdns.service_removed",
)
TREL_FLAP_EVENTS = (
    "trel.service_added",
    "trel.service_removed",
)
WARNING_SEVERITIES = (
    EventSeverity.WARNING.value,
    EventSeverity.ERROR.value,
    EventSeverity.CRITICAL.value,
)


@dataclass(frozen=True)
class HealthContext:
    config: ThreadLensConfig
    repository: StorageRepository
    mdns_observer: MdnsObserver | None = None
    otbr_collector: OtbrCollector | None = None
    matter_collector: MatterCollector | None = None


class HealthEngine:
    """Factual, capability-aware health calculation."""

    def __init__(self, context: HealthContext) -> None:
        self._context = context

    @property
    def config(self) -> ThreadLensConfig:
        return self._context.config

    @property
    def repository(self) -> StorageRepository:
        return self._context.repository

    async def build_report(self, *, version: str, mode: str) -> HealthReport:
        now = utc_now()
        since_1h = now - timedelta(hours=1)
        since_24h = now - timedelta(hours=24)

        otbr_states = await self._load_otbr_states()
        matter_servers = await self._load_matter_servers()
        matter_nodes = await self._load_matter_nodes()
        thread_networks = await self._load_thread_networks()
        trel_services = await self._load_trel_services()

        otbr_health: list[OtbrHealthResult] = []
        for otbr_config in self.config.otbrs:
            state = next((item for item in otbr_states if item.id == otbr_config.id), None)
            if state is None:
                otbr_health.append(
                    OtbrHealthResult(
                        id=otbr_config.id,
                        state=HealthState.UNKNOWN,
                        reasons=["otbr_not_observed"],
                    )
                )
            else:
                otbr_health.append(await self._calculate_otbr_health(state, since_1h=since_1h))

        matter_server_health: list[MatterServerHealthResult] = []
        for server_config in self.config.matter_servers:
            state = next((item for item in matter_servers if item.id == server_config.id), None)
            if state is None:
                matter_server_health.append(
                    MatterServerHealthResult(
                        id=server_config.id,
                        state=HealthState.UNKNOWN,
                        reasons=["matter_server_not_observed"],
                    )
                )
            else:
                matter_server_health.append(self._calculate_matter_server_health(state))

        matter_node_health = [
            self._calculate_matter_node_health(
                node,
                server_by_id={server.id: server for server in matter_servers},
                now=now,
            )
            for node in matter_nodes
        ]
        thread_network_health = [
            self._calculate_thread_network_health(network, otbr_states)
            for network in thread_networks
        ]
        mdns_health = await self._calculate_mdns_health(since_1h=since_1h)
        trel_health = await self._calculate_trel_health(
            trel_services,
            since_1h=since_1h,
        )

        disagree_health = self._configured_otbr_disagreement_health(otbr_states)
        primary_unknown_health = self._primary_network_unknown_health(
            otbr_states,
            thread_networks,
        )

        env_statuses: list[HealthStatus] = [
            HealthStatus(state=item.state, reasons=item.reasons) for item in otbr_health
        ]
        env_statuses.extend(
            HealthStatus(state=item.state, reasons=item.reasons) for item in matter_server_health
        )
        env_statuses.extend(
            HealthStatus(state=item.state, reasons=item.reasons) for item in matter_node_health
        )
        for item in thread_network_health:
            if item.classification == ThreadNetworkClassification.OBSERVED_OTHER.value:
                env_statuses.append(
                    HealthStatus(
                        state=HealthState.WARNING,
                        reasons=["observed_other_thread_network_visible"],
                    )
                )
        env_statuses.extend([mdns_health, trel_health, disagree_health, primary_unknown_health])
        environment = (
            merge_health(*env_statuses)
            if env_statuses
            else HealthStatus(
                state=HealthState.UNKNOWN,
                reasons=["insufficient_data"],
            )
        )

        overall = merge_health(environment)

        summary = EnvironmentSummary(
            otbrs_configured=len(self.config.otbrs),
            otbrs_reachable=sum(1 for state in otbr_states if state.reachable),
            matter_servers_configured=len(self.config.matter_servers),
            matter_servers_connected=sum(1 for state in matter_servers if state.connected),
            matter_nodes_seen=len(matter_nodes),
            matter_nodes_unavailable=sum(1 for node in matter_nodes if not node.available),
            thread_networks_seen=sum(1 for network in thread_networks if network.currently_visible),
            foreign_trel_services_seen=sum(
                1 for service in trel_services if service.is_foreign and service.currently_visible
            ),
            events_24h=await self.repository.count_events(since=since_24h),
            warnings_24h=await self.repository.count_events(
                since=since_24h,
                severities=list(WARNING_SEVERITIES),
            ),
        )

        if self._insufficient_data(summary):
            environment = merge_health(
                environment,
                HealthStatus(state=HealthState.UNKNOWN, reasons=["insufficient_data"]),
            )
            overall = merge_health(environment)

        return HealthReport(
            version=version,
            mode=mode,
            site=self.config.site.name,
            overall=overall,
            environment=environment,
            summary=summary,
            otbrs=otbr_health,
            matter_servers=matter_server_health,
            matter_nodes=matter_node_health,
            thread_networks=thread_network_health,
            mdns=mdns_health,
            trel=trel_health,
        )

    async def _load_otbr_states(self) -> list[OtbrState]:
        return await self._load_states(CurrentStateType.OTBR, OtbrState)

    async def _load_matter_servers(self) -> list[MatterServerState]:
        return await self._load_states(CurrentStateType.MATTER_SERVER, MatterServerState)

    async def _load_matter_nodes(self) -> list[MatterNodeState]:
        return await self._load_states(CurrentStateType.MATTER_NODE, MatterNodeState)

    async def _load_thread_networks(self) -> list[ThreadNetworkState]:
        return await self._load_states(CurrentStateType.THREAD_NETWORK, ThreadNetworkState)

    async def _load_trel_services(self) -> list[TrelServiceState]:
        return await self._load_states(CurrentStateType.TREL_SERVICE, TrelServiceState)

    async def _load_states(self, object_type: CurrentStateType, model_type: type[Any]) -> list[Any]:
        payloads = await self.repository.list_current_state(object_type)
        results: list[Any] = []
        for payload in payloads:
            clean = {key: value for key, value in payload.items() if not key.startswith("_")}
            results.append(model_type.model_validate(clean))
        return results

    def _configured_otbr_states(self, states: list[OtbrState]) -> list[OtbrState]:
        configured_ids = {otbr.id for otbr in self.config.otbrs}
        by_id = {state.id: state for state in states}
        results: list[OtbrState] = []
        for otbr_id in configured_ids:
            if otbr_id in by_id:
                results.append(by_id[otbr_id])
        return results

    async def _calculate_otbr_health(
        self,
        state: OtbrState,
        *,
        since_1h: Any,
    ) -> OtbrHealthResult:
        role_changes = state.role_changes_1h
        if role_changes is None:
            role_changes = await self.repository.count_events(
                source_id=state.id,
                event_type="otbr.role_changed",
                since=since_1h,
            )

        candidates: list[tuple[HealthState, list[str]]] = []
        if not state.reachable:
            candidates.append((HealthState.CRITICAL, ["otbr_unreachable"]))
        elif state.thread_state == "disabled":
            candidates.append((HealthState.DEGRADED, ["otbr_thread_stack_disabled"]))
        else:
            if state.rest_endpoint_mismatch:
                candidates.append((HealthState.WARNING, ["otbr_rest_endpoint_mismatch"]))
            dataset_known = (
                state.ext_pan_id is not None or state.capabilities.network_dataset_available
            )
            if not dataset_known:
                candidates.append((HealthState.WARNING, ["otbr_dataset_unknown"]))
            if role_changes >= self.config.flapping.otbr_role_changes_degraded_1h:
                candidates.append((HealthState.DEGRADED, ["otbr_role_flapping_degraded"]))
            elif role_changes >= self.config.flapping.otbr_role_changes_warning_1h:
                candidates.append((HealthState.WARNING, ["otbr_role_flapping_warning"]))
            if not candidates:
                candidates.append((HealthState.HEALTHY, []))

        health = health_from_candidates(candidates)
        return OtbrHealthResult(id=state.id, state=health.state, reasons=health.reasons)

    def _calculate_matter_server_health(
        self,
        state: MatterServerState,
    ) -> MatterServerHealthResult:
        candidates: list[tuple[HealthState, list[str]]] = []
        if not state.connected:
            candidates.append((HealthState.CRITICAL, ["matter_server_disconnected"]))
        elif not state.capabilities.node_inventory_available:
            candidates.append((HealthState.WARNING, ["matter_node_inventory_unavailable"]))
            if state.unavailable_node_count > 0:
                candidates.append((HealthState.WARNING, ["matter_nodes_unavailable"]))
        elif state.unavailable_node_count > 0:
            candidates.append((HealthState.WARNING, ["matter_nodes_unavailable"]))
        else:
            candidates.append((HealthState.HEALTHY, []))

        health = health_from_candidates(candidates)
        return MatterServerHealthResult(id=state.id, state=health.state, reasons=health.reasons)

    def _calculate_matter_node_health(
        self,
        node: MatterNodeState,
        *,
        server_by_id: dict[str, MatterServerState],
        now: Any,
    ) -> MatterNodeHealthResult:
        subject_id = f"matter_node:{node.server_id}:{node.node_id}"
        server = server_by_id.get(node.server_id)
        availability_observable = (
            server is not None and server.capabilities.node_availability_available
        )

        candidates: list[tuple[HealthState, list[str]]] = []
        if not availability_observable:
            candidates.append((HealthState.UNKNOWN, ["matter_node_availability_unknown"]))
        elif not node.available:
            unavailable_minutes = 0.0
            if node.last_unavailable is not None:
                unavailable_minutes = (now - node.last_unavailable).total_seconds() / 60.0
            if unavailable_minutes >= self.config.flapping.matter_node_unavailable_critical_minutes:
                candidates.append((HealthState.CRITICAL, ["matter_node_unavailable_critical"]))
            else:
                candidates.append((HealthState.DEGRADED, ["matter_node_unavailable"]))
        else:
            flaps = node.availability_flaps_24h
            if flaps is not None:
                if flaps >= self.config.flapping.matter_node_availability_degraded_24h:
                    candidates.append(
                        (HealthState.DEGRADED, ["matter_node_availability_flapping_degraded"])
                    )
                elif flaps >= self.config.flapping.matter_node_availability_warning_24h:
                    candidates.append(
                        (HealthState.WARNING, ["matter_node_availability_flapping_warning"])
                    )

            if node.read_probe_diagnostics_available and not node.last_read_probe_limited:
                if node.last_read_probe_ok is False:
                    candidates.append((HealthState.WARNING, ["matter_node_read_probe_failed"]))

                probe_failures = node.read_probe_failures_24h
                if probe_failures is not None:
                    if (
                        probe_failures
                        >= self.config.flapping.matter_node_read_probe_failures_degraded_24h
                    ):
                        candidates.append(
                            (HealthState.DEGRADED, ["matter_node_read_probe_failures_24h"])
                        )
                    elif (
                        probe_failures
                        >= self.config.flapping.matter_node_read_probe_failures_warning_24h
                    ):
                        candidates.append(
                            (HealthState.WARNING, ["matter_node_read_probe_failures_24h"])
                        )

            if node.ping_diagnostics_available and node.last_ping_ok is False:
                candidates.append((HealthState.WARNING, ["matter_node_ping_probe_failed"]))

            if not candidates:
                candidates.append((HealthState.HEALTHY, []))

        health = health_from_candidates(candidates)
        return MatterNodeHealthResult(
            id=subject_id,
            node_id=node.node_id,
            server_id=node.server_id,
            state=health.state,
            reasons=health.reasons,
        )

    def _calculate_thread_network_health(
        self,
        network: ThreadNetworkState,
        otbr_states: list[OtbrState],
    ) -> ThreadNetworkHealthResult:
        reachable_sources = {
            state.id
            for state in otbr_states
            if state.reachable and state.id in network.source_otbr_ids
        }
        candidates: list[tuple[HealthState, list[str]]] = []
        if not network.currently_visible:
            candidates.append((HealthState.UNKNOWN, ["thread_network_not_visible"]))
        elif network.classification == ThreadNetworkClassification.PRIMARY and reachable_sources:
            candidates.append((HealthState.HEALTHY, []))
        elif network.classification == ThreadNetworkClassification.OBSERVED_OTHER:
            candidates.append((HealthState.WARNING, ["observed_other_thread_network_visible"]))
        elif network.classification == ThreadNetworkClassification.UNKNOWN:
            candidates.append((HealthState.WARNING, ["primary_thread_network_unknown"]))
        elif network.currently_visible:
            candidates.append((HealthState.WARNING, ["thread_network_source_otbrs_unreachable"]))
        else:
            candidates.append((HealthState.UNKNOWN, ["thread_network_not_observed"]))

        health = health_from_candidates(candidates)
        return ThreadNetworkHealthResult(
            ext_pan_id=network.ext_pan_id,
            classification=network.classification.value,
            state=health.state,
            reasons=health.reasons,
        )

    async def _calculate_mdns_health(self, *, since_1h: Any) -> HealthStatus:
        observer = self._context.mdns_observer
        candidates: list[tuple[HealthState, list[str]]] = []

        if not self.config.mdns.enabled:
            return HealthStatus(state=HealthState.UNKNOWN, reasons=["mdns_observation_disabled"])

        if observer is None or not observer.running:
            candidates.append((HealthState.WARNING, ["mdns_observer_not_running"]))
        elif observer.observation_degraded is True:
            candidates.append((HealthState.WARNING, ["mdns_observation_degraded"]))
        elif observer.observation_degraded is None:
            candidates.append((HealthState.UNKNOWN, ["mdns_observation_capability_unknown"]))
        else:
            flap_count = await self._count_service_flaps(MDNS_FLAP_EVENTS, since_1h)
            if flap_count >= self.config.flapping.mdns_service_flaps_degraded_1h:
                candidates.append((HealthState.DEGRADED, ["mdns_service_flapping_degraded"]))
            elif flap_count >= self.config.flapping.mdns_service_flaps_warning_1h:
                candidates.append((HealthState.WARNING, ["mdns_service_flapping_warning"]))
            else:
                candidates.append((HealthState.HEALTHY, []))

        return health_from_candidates(candidates)

    async def _calculate_trel_health(
        self,
        trel_services: list[TrelServiceState],
        *,
        since_1h: Any,
    ) -> HealthStatus:
        candidates: list[tuple[HealthState, list[str]]] = []
        foreign_visible = [
            service for service in trel_services if service.is_foreign and service.currently_visible
        ]
        if foreign_visible:
            candidates.append((HealthState.WARNING, ["foreign_trel_services_observed"]))

        flap_count = await self._count_service_flaps(TREL_FLAP_EVENTS, since_1h)
        if flap_count >= self.config.flapping.mdns_service_flaps_degraded_1h:
            candidates.append((HealthState.DEGRADED, ["mdns_service_flapping_degraded"]))
        elif flap_count >= self.config.flapping.mdns_service_flaps_warning_1h:
            candidates.append((HealthState.WARNING, ["mdns_service_flapping_warning"]))

        if not candidates:
            if not self.config.mdns.enabled:
                return HealthStatus(
                    state=HealthState.UNKNOWN, reasons=["mdns_observation_disabled"]
                )
            observer = self._context.mdns_observer
            if observer and observer.running and observer.observation_degraded is False:
                candidates.append((HealthState.HEALTHY, []))
            else:
                candidates.append((HealthState.UNKNOWN, ["mdns_observation_capability_unknown"]))

        return health_from_candidates(candidates)

    async def _count_service_flaps(self, event_types: tuple[str, ...], since: Any) -> int:
        total = 0
        for event_type in event_types:
            events = await self.repository.get_events(event_type=event_type, since=since)
            total += sum(1 for event in events if not _is_initial_observation_event(event))
        return total

    def _configured_otbr_disagreement_health(self, otbr_states: list[OtbrState]) -> HealthStatus:
        configured = self._configured_otbr_states(otbr_states)
        if len(configured) < 2:
            return HealthStatus(state=HealthState.HEALTHY, reasons=[])

        ext_pan_ids = {
            state.ext_pan_id for state in configured if state.reachable and state.ext_pan_id
        }
        if len(ext_pan_ids) <= 1:
            return HealthStatus(state=HealthState.HEALTHY, reasons=[])

        _, primary_class = classify_primary_network(ext_pan_ids)
        if primary_class == ThreadNetworkClassification.UNKNOWN:
            reachable_count = sum(1 for state in configured if state.reachable)
            if reachable_count >= 2:
                return HealthStatus(
                    state=HealthState.DEGRADED,
                    reasons=["configured_otbrs_disagree_on_ext_pan_id"],
                )
            return HealthStatus(
                state=HealthState.WARNING,
                reasons=["configured_otbrs_disagree_on_ext_pan_id"],
            )
        return HealthStatus(state=HealthState.HEALTHY, reasons=[])

    def _primary_network_unknown_health(
        self,
        otbr_states: list[OtbrState],
        thread_networks: list[ThreadNetworkState],
    ) -> HealthStatus:
        if not self.config.otbrs:
            return HealthStatus(state=HealthState.HEALTHY, reasons=[])

        configured = self._configured_otbr_states(otbr_states)
        ext_pan_ids = {
            state.ext_pan_id for state in configured if state.reachable and state.ext_pan_id
        }
        _, primary_class = classify_primary_network(ext_pan_ids)
        if primary_class == ThreadNetworkClassification.UNKNOWN and len(ext_pan_ids) > 1:
            return HealthStatus(
                state=HealthState.WARNING,
                reasons=["primary_thread_network_unknown"],
            )

        primary_networks = [
            network
            for network in thread_networks
            if network.classification == ThreadNetworkClassification.UNKNOWN
            and network.currently_visible
        ]
        if primary_networks and not ext_pan_ids:
            return HealthStatus(
                state=HealthState.WARNING,
                reasons=["primary_thread_network_unknown"],
            )
        return HealthStatus(state=HealthState.HEALTHY, reasons=[])

    def _insufficient_data(self, summary: EnvironmentSummary) -> bool:
        has_configured_sources = (
            summary.otbrs_configured > 0
            or summary.matter_servers_configured > 0
            or self.config.mdns.enabled
        )
        has_observations = (
            summary.otbrs_reachable > 0
            or summary.matter_servers_connected > 0
            or summary.matter_nodes_seen > 0
            or summary.thread_networks_seen > 0
            or summary.foreign_trel_services_seen > 0
            or summary.events_24h > 0
        )
        return not has_configured_sources and not has_observations


def _is_initial_observation_event(event: Any) -> bool:
    data = getattr(event, "data", None)
    return isinstance(data, dict) and data.get("initial_observation") is True
