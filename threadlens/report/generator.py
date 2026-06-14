"""ThreadLens diagnostic report generator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from threadlens import __version__
from threadlens.collectors.matter_server import MatterCollector
from threadlens.collectors.mdns import MdnsObserver
from threadlens.collectors.otbr_rest import OtbrCollector
from threadlens.config import ThreadLensConfig
from threadlens.health import HealthEngine
from threadlens.health.engine import HealthContext
from threadlens.models.agent import AgentState
from threadlens.models.events import Event, EventSeverity
from threadlens.models.health import HealthState, HealthStatus
from threadlens.models.reports import (
    EventAggregates,
    RedactionSummary,
    ReportAgentEntry,
    ReportCapabilitiesSummary,
    ReportEventsSection,
    ReportFocusSection,
    ReportHealthSection,
    ReportMatterNodeEntry,
    ReportMatterServerEntry,
    ReportOtbrEntry,
    ReportSite,
    ReportSummary,
    ThreadLensReport,
    TrelMdnsReportSection,
)
from threadlens.models.state import (
    MatterNodeState,
    MatterServerState,
    MdnsServiceState,
    OtbrState,
    ThreadNetworkState,
    TrelServiceState,
)
from threadlens.report.redaction import DEFAULT_SECRETS_REMOVED
from threadlens.report.window import parse_window
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.time import utc_now

RECENT_EVENT_LIMIT = 100
WARNING_SEVERITIES = (
    EventSeverity.WARNING.value,
    EventSeverity.ERROR.value,
    EventSeverity.CRITICAL.value,
)


@dataclass(frozen=True)
class ReportContext:
    config: ThreadLensConfig
    repository: StorageRepository
    mdns_observer: MdnsObserver | None = None
    otbr_collector: OtbrCollector | None = None
    matter_collector: MatterCollector | None = None


class ReportGenerator:
    """Build comprehensive factual reports from stored state and events."""

    def __init__(self, context: ReportContext) -> None:
        self._context = context

    async def generate(
        self,
        *,
        window: str = "24h",
        focus_node: str | None = None,
        focus_device: str | None = None,
        version: str = __version__,
    ) -> ThreadLensReport:
        delta = parse_window(window)
        now = utc_now()
        since = now - delta

        health_report = await HealthEngine(
            HealthContext(
                config=self._context.config,
                repository=self._context.repository,
                mdns_observer=self._context.mdns_observer,
                otbr_collector=self._context.otbr_collector,
                matter_collector=self._context.matter_collector,
            )
        ).build_report(version=version, mode="server")

        otbr_states = await self._load_states(CurrentStateType.OTBR, OtbrState)
        matter_servers = await self._load_states(CurrentStateType.MATTER_SERVER, MatterServerState)
        matter_nodes = await self._load_states(CurrentStateType.MATTER_NODE, MatterNodeState)
        thread_networks = await self._load_states(
            CurrentStateType.THREAD_NETWORK, ThreadNetworkState
        )
        mdns_services = await self._load_states(CurrentStateType.MDNS_SERVICE, MdnsServiceState)
        trel_services = await self._load_states(CurrentStateType.TREL_SERVICE, TrelServiceState)
        agent_states = await self._load_states(CurrentStateType.AGENT, AgentState)

        all_events = await self._context.repository.get_events(since=since)
        aggregates = self._build_aggregates(all_events)
        focus = self._resolve_focus(
            focus_node=focus_node,
            focus_device=focus_device,
            matter_nodes=matter_nodes,
            otbr_states=otbr_states,
            matter_servers=matter_servers,
            mdns_services=mdns_services,
            trel_services=trel_services,
        )
        recent_events = self._prioritise_events(all_events, focus)

        capabilities = self._build_capabilities(
            otbr_states=otbr_states,
            matter_servers=matter_servers,
            matter_nodes=matter_nodes,
            mdns_services=mdns_services,
            trel_services=trel_services,
            agent_states=agent_states,
        )
        if capabilities.matter_read_probe_diagnostics:
            aggregates.extra["read_probe_note"] = (
                "Safe read probes check Matter-layer read reachability. "
                "They do not prove open/close or other commands are working."
            )

        foreign_trel = sum(
            1 for service in trel_services if service.is_foreign and service.currently_visible
        )

        report = ThreadLensReport(
            generated_at=now,
            version=version,
            window=window,
            site=ReportSite(name=self._context.config.site.name),
            summary=ReportSummary(
                health=health_report.overall.state,
                thread_networks_seen=health_report.summary.thread_networks_seen,
                foreign_thread_networks_seen=ThreadLensReport.foreign_network_count(
                    thread_networks
                ),
                otbrs_configured=health_report.summary.otbrs_configured,
                otbrs_reachable=health_report.summary.otbrs_reachable,
                matter_servers_configured=health_report.summary.matter_servers_configured,
                matter_servers_connected=health_report.summary.matter_servers_connected,
                matter_nodes_seen=health_report.summary.matter_nodes_seen,
                unavailable_matter_nodes=health_report.summary.matter_nodes_unavailable,
                events_in_window=len(all_events),
                warnings_in_window=sum(
                    1 for event in all_events if event.severity.value in WARNING_SEVERITIES
                ),
            ),
            capabilities=capabilities,
            health=ReportHealthSection(
                overall=health_report.overall,
                environment=health_report.environment,
                mdns=health_report.mdns,
                trel=health_report.trel,
            ),
            thread_networks=thread_networks,
            otbrs=self._build_otbr_entries(otbr_states, health_report),
            mdns_services=mdns_services,
            trel_services=trel_services,
            matter_servers=self._build_matter_server_entries(matter_servers, health_report),
            matter_nodes=self._build_matter_node_entries(matter_nodes, health_report),
            agents=self._build_agent_entries(agent_states),
            trel_mdns=TrelMdnsReportSection(
                services_seen=len(trel_services),
                foreign_services_seen=foreign_trel,
                mdns_observation_degraded=(
                    self._context.mdns_observer.observation_degraded
                    if self._context.mdns_observer
                    else None
                ),
                services=trel_services,
            ),
            aggregates=aggregates,
            events=ReportEventsSection(recent=recent_events),
            redaction=RedactionSummary(
                enabled=self._context.config.reports.redact_secrets,
                secrets_removed=list(DEFAULT_SECRETS_REMOVED),
            ),
            focus=focus,
        )

        await self._context.repository.set_metadata("report_last_generated_at", now.isoformat())
        await self._context.repository.set_metadata("report_last_window", window)
        return report

    async def _load_states(self, object_type: CurrentStateType, model_type: type[Any]) -> list[Any]:
        payloads = await self._context.repository.list_current_state(object_type)
        results: list[Any] = []
        for payload in payloads:
            clean = {key: value for key, value in payload.items() if not key.startswith("_")}
            results.append(model_type.model_validate(clean))
        return results

    def _build_capabilities(
        self,
        *,
        otbr_states: list[OtbrState],
        matter_servers: list[MatterServerState],
        matter_nodes: list[MatterNodeState],
        mdns_services: list[MdnsServiceState],
        trel_services: list[TrelServiceState],
        agent_states: list[AgentState],
    ) -> ReportCapabilitiesSummary:
        observer = self._context.mdns_observer
        mdns_available = bool(observer and observer.running) or bool(mdns_services or trel_services)
        otbr_rest = any(state.capabilities.rest_available for state in otbr_states)
        internal_trel = next((state.internal_trel for state in otbr_states), None)
        matter_ws = any(state.capabilities.websocket_available for state in matter_servers)
        matter_availability = any(
            state.capabilities.node_availability_available for state in matter_servers
        )
        agent_api = any(state.reachable for state in agent_states)
        agent_local_diagnostics = any(
            state.reachable and state.capabilities.otbr_local_diagnostics for state in agent_states
        )
        return ReportCapabilitiesSummary(
            mdns_observation=mdns_available,
            mdns_observation_degraded=observer.observation_degraded if observer else None,
            trel_mdns_observation=bool(trel_services) or mdns_available,
            otbr_rest=otbr_rest,
            otbr_internal_trel_peer_table=(
                internal_trel.peer_table_available if internal_trel else False
            ),
            otbr_internal_trel_counters=(
                internal_trel.counters_available if internal_trel else False
            ),
            matter_server_websocket=matter_ws,
            matter_node_availability=matter_availability,
            matter_subscription_diagnostics=False,
            matter_case_diagnostics=False,
            matter_command_diagnostics=False,
            matter_read_probe_diagnostics=any(
                node.read_probe_diagnostics_available for node in matter_nodes
            ),
            agent_api_available=agent_api,
            agent_local_diagnostics=agent_local_diagnostics,
            agent_ssh_available=False,
            agent_docker_socket_available=False,
            agent_mutation_allowed=False,
        )

    def _build_agent_entries(self, agent_states: list[AgentState]) -> list[ReportAgentEntry]:
        return [
            ReportAgentEntry(
                otbr_id=state.otbr_id,
                agent_url=state.agent_url,
                reachable=state.reachable,
                last_seen=state.last_seen,
                last_error=state.last_error,
                capabilities=state.capabilities.model_dump(mode="json"),
            )
            for state in agent_states
        ]

    def _build_otbr_entries(
        self,
        otbr_states: list[OtbrState],
        health_report: Any,
    ) -> list[ReportOtbrEntry]:
        health_by_id = {item.id: item for item in health_report.otbrs}
        configured_ids = {otbr.id for otbr in self._context.config.otbrs}
        entries: list[ReportOtbrEntry] = []
        for otbr_config in self._context.config.otbrs:
            state = next((item for item in otbr_states if item.id == otbr_config.id), None)
            health = health_by_id.get(otbr_config.id)
            if state is None:
                entries.append(
                    ReportOtbrEntry(
                        id=otbr_config.id,
                        name=otbr_config.name,
                        health=HealthStatus(
                            state=HealthState.UNKNOWN,
                            reasons=["otbr_not_observed"],
                        ),
                    )
                )
                continue
            entries.append(
                ReportOtbrEntry(
                    id=state.id,
                    name=state.name,
                    reachable=state.reachable,
                    thread_state=state.thread_state,
                    thread_state_source=state.thread_state_source,
                    json_api_thread_state=state.json_api_thread_state,
                    legacy_node_thread_state=state.legacy_node_thread_state,
                    rest_endpoint_mismatch=state.rest_endpoint_mismatch,
                    role=state.role,
                    network_name=state.network_name,
                    channel=state.channel,
                    ext_pan_id=state.ext_pan_id,
                    pan_id=state.pan_id,
                    last_seen=state.last_seen,
                    last_error=state.last_error,
                    health=HealthStatus(
                        state=health.state if health else HealthState.UNKNOWN,
                        reasons=health.reasons if health else [],
                    ),
                    capabilities=state.capabilities.model_dump(mode="json"),
                )
            )
        for state in otbr_states:
            if state.id not in configured_ids:
                health = health_by_id.get(state.id)
                entries.append(
                    ReportOtbrEntry(
                        id=state.id,
                        name=state.name,
                        reachable=state.reachable,
                        thread_state=state.thread_state,
                        thread_state_source=state.thread_state_source,
                        json_api_thread_state=state.json_api_thread_state,
                        legacy_node_thread_state=state.legacy_node_thread_state,
                        rest_endpoint_mismatch=state.rest_endpoint_mismatch,
                        role=state.role,
                        network_name=state.network_name,
                        channel=state.channel,
                        ext_pan_id=state.ext_pan_id,
                        pan_id=state.pan_id,
                        last_seen=state.last_seen,
                        last_error=state.last_error,
                        health=HealthStatus(
                            state=health.state if health else HealthState.UNKNOWN,
                            reasons=health.reasons if health else [],
                        ),
                        capabilities=state.capabilities.model_dump(mode="json"),
                    )
                )
        return entries

    def _build_matter_server_entries(
        self,
        matter_servers: list[MatterServerState],
        health_report: Any,
    ) -> list[ReportMatterServerEntry]:
        health_by_id = {item.id: item for item in health_report.matter_servers}
        entries: list[ReportMatterServerEntry] = []
        for server_config in self._context.config.matter_servers:
            state = next((item for item in matter_servers if item.id == server_config.id), None)
            health = health_by_id.get(server_config.id)
            if state is None:
                entries.append(
                    ReportMatterServerEntry(
                        id=server_config.id,
                        name=server_config.name,
                        health=HealthStatus(
                            state=HealthState.UNKNOWN,
                            reasons=["matter_server_not_observed"],
                        ),
                    )
                )
                continue
            entries.append(
                ReportMatterServerEntry(
                    id=state.id,
                    name=state.name,
                    connected=state.connected,
                    node_count=state.node_count,
                    unavailable_node_count=state.unavailable_node_count,
                    variant=state.variant,
                    last_seen=state.last_seen,
                    last_error=state.last_error,
                    health=HealthStatus(
                        state=health.state if health else HealthState.UNKNOWN,
                        reasons=health.reasons if health else [],
                    ),
                    capabilities=state.capabilities.model_dump(mode="json"),
                )
            )
        return entries

    def _build_matter_node_entries(
        self,
        matter_nodes: list[MatterNodeState],
        health_report: Any,
    ) -> list[ReportMatterNodeEntry]:
        health_by_id = {item.id: item for item in health_report.matter_nodes}
        entries: list[ReportMatterNodeEntry] = []
        for node in matter_nodes:
            subject_id = f"matter_node:{node.server_id}:{node.node_id}"
            health = health_by_id.get(subject_id)
            entries.append(
                ReportMatterNodeEntry(
                    node_id=node.node_id,
                    server_id=node.server_id,
                    friendly_name=node.friendly_name,
                    vendor=node.vendor,
                    product=node.product,
                    serial=node.serial,
                    firmware=node.firmware,
                    available=node.available,
                    availability_flaps_24h=node.availability_flaps_24h,
                    subscription_flaps_24h=node.subscription_flaps_24h,
                    subscription_diagnostics_available=node.subscription_diagnostics_available,
                    case_diagnostics_available=node.case_diagnostics_available,
                    command_diagnostics_available=node.command_diagnostics_available,
                    read_probe_diagnostics_available=node.read_probe_diagnostics_available,
                    last_read_probe_at=node.last_read_probe_at,
                    last_read_probe_ok=node.last_read_probe_ok,
                    last_read_probe_limited=node.last_read_probe_limited,
                    last_read_probe_attribute_path=node.last_read_probe_attribute_path,
                    last_read_probe_duration_ms=node.last_read_probe_duration_ms,
                    last_read_probe_error_code=node.last_read_probe_error_code,
                    read_probe_failures_24h=node.read_probe_failures_24h,
                    read_probe_successes_24h=node.read_probe_successes_24h,
                    ping_diagnostics_available=node.ping_diagnostics_available,
                    last_ping_at=node.last_ping_at,
                    last_ping_ok=node.last_ping_ok,
                    ping_failures_24h=node.ping_failures_24h,
                    ping_successes_24h=node.ping_successes_24h,
                    health=HealthStatus(
                        state=health.state if health else HealthState.UNKNOWN,
                        reasons=health.reasons if health else [],
                    ),
                )
            )
        return entries

    def _build_aggregates(self, events: list[Event]) -> EventAggregates:
        by_type: dict[str, int] = {}
        by_subject_type: dict[str, int] = {}
        for event in events:
            by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
            subject_key = (
                event.subject_type.value
                if hasattr(event.subject_type, "value")
                else str(event.subject_type)
            )
            by_subject_type[subject_key] = by_subject_type.get(subject_key, 0) + 1
        return EventAggregates(
            events_by_type=by_type,
            events_by_subject_type=by_subject_type,
        )

    def _resolve_focus(
        self,
        *,
        focus_node: str | None,
        focus_device: str | None,
        matter_nodes: list[MatterNodeState],
        otbr_states: list[OtbrState],
        matter_servers: list[MatterServerState],
        mdns_services: list[MdnsServiceState],
        trel_services: list[TrelServiceState],
    ) -> ReportFocusSection | None:
        if not focus_node and not focus_device:
            return None

        prioritised: list[str] = []
        matched = False
        message: str | None = None

        if focus_node:
            subject_ids = self._parse_focus_node(focus_node, matter_nodes)
            prioritised.extend(subject_ids)
            matched = bool(subject_ids)
            if not matched:
                message = f"No Matter node match for focus_node={focus_node!r}"

        if focus_device:
            device_matches = self._match_focus_device(
                focus_device,
                matter_nodes=matter_nodes,
                otbr_states=otbr_states,
                matter_servers=matter_servers,
                mdns_services=mdns_services,
                trel_services=trel_services,
            )
            prioritised.extend(device_matches)
            if device_matches:
                matched = True
            elif message is None:
                message = f"No match found for focus_device={focus_device!r}"

        return ReportFocusSection(
            focus_node=focus_node,
            focus_device=focus_device,
            matched=matched,
            message=message,
            prioritised_subject_ids=list(dict.fromkeys(prioritised)),
        )

    def _parse_focus_node(
        self,
        focus_node: str,
        matter_nodes: list[MatterNodeState],
    ) -> list[str]:
        raw = focus_node.strip()
        if raw.startswith("matter_node:"):
            return (
                [raw]
                if any(
                    f"matter_node:{node.server_id}:{node.node_id}" == raw for node in matter_nodes
                )
                else []
            )

        if ":" in raw:
            server_id, node_part = raw.split(":", 1)
            try:
                node_id = int(node_part)
            except ValueError:
                return []
            subject = f"matter_node:{server_id}:{node_id}"
            return (
                [subject]
                if any(
                    node.server_id == server_id and node.node_id == node_id for node in matter_nodes
                )
                else []
            )

        try:
            node_id = int(raw)
        except ValueError:
            return []
        matches = [
            f"matter_node:{node.server_id}:{node.node_id}"
            for node in matter_nodes
            if node.node_id == node_id
        ]
        return matches

    def _match_focus_device(
        self,
        focus_device: str,
        *,
        matter_nodes: list[MatterNodeState],
        otbr_states: list[OtbrState],
        matter_servers: list[MatterServerState],
        mdns_services: list[MdnsServiceState],
        trel_services: list[TrelServiceState],
    ) -> list[str]:
        needle = focus_device.strip().lower()
        matches: list[str] = []
        for node in matter_nodes:
            subject = f"matter_node:{node.server_id}:{node.node_id}"
            candidates = [
                str(node.node_id),
                subject,
                f"{node.server_id}:{node.node_id}",
                (node.friendly_name or "").lower(),
                (node.serial or "").lower(),
            ]
            if any(needle == value or needle in value for value in candidates if value):
                matches.append(subject)
        for otbr in otbr_states:
            if needle in {otbr.id.lower(), otbr.name.lower()}:
                matches.append(f"otbr:{otbr.id}")
        for server in matter_servers:
            if needle in {server.id.lower(), server.name.lower()}:
                matches.append(f"matter_server:{server.id}")
        for service in mdns_services:
            if needle in {
                service.service_id.lower(),
                service.instance_name.lower(),
                (service.hostname or "").lower(),
            }:
                matches.append(f"mdns_service:{service.service_id}")
        for service in trel_services:
            if needle in {
                service.service_id.lower(),
                service.instance_name.lower(),
                (service.hostname or "").lower(),
            }:
                matches.append(f"trel_service:{service.service_id}")
        return list(dict.fromkeys(matches))

    def _prioritise_events(
        self,
        events: list[Event],
        focus: ReportFocusSection | None,
    ) -> list[Event]:
        if focus is None or not focus.prioritised_subject_ids:
            return events[-RECENT_EVENT_LIMIT:]

        priority_ids = set(focus.prioritised_subject_ids)
        priority = [event for event in events if event.subject_id in priority_ids]
        remainder = [event for event in events if event.subject_id not in priority_ids]
        combined = priority + remainder
        if len(combined) <= RECENT_EVENT_LIMIT:
            return combined
        if len(priority) >= RECENT_EVENT_LIMIT:
            return priority[-RECENT_EVENT_LIMIT:]
        remaining_slots = RECENT_EVENT_LIMIT - len(priority)
        return priority + remainder[-remaining_slots:]
