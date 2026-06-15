"""Report models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from threadlens.models.events import Event
from threadlens.models.health import HealthState, HealthStatus
from threadlens.models.state import (
    MdnsServiceState,
    ThreadNetworkClassification,
    ThreadNetworkState,
    TrelServiceState,
)


class ReportSite(BaseModel):
    name: str = "Home"


class ReportSummary(BaseModel):
    health: HealthState = HealthState.UNKNOWN
    thread_networks_seen: int = 0
    foreign_thread_networks_seen: int = 0
    otbrs_configured: int = 0
    otbrs_reachable: int = 0
    matter_servers_configured: int = 0
    matter_servers_connected: int = 0
    matter_nodes_seen: int = 0
    unavailable_matter_nodes: int = 0
    events_in_window: int = 0
    warnings_in_window: int = 0


class ReportCapabilitiesSummary(BaseModel):
    mdns_observation: bool = False
    mdns_observation_degraded: bool | None = None
    trel_mdns_observation: bool = False
    otbr_rest: bool = False
    otbr_internal_trel_peer_table: bool = False
    otbr_internal_trel_counters: bool = False
    matter_server_websocket: bool = False
    matter_node_availability: bool = False
    matter_subscription_diagnostics: bool = False
    matter_case_diagnostics: bool = False
    matter_command_diagnostics: bool = False
    matter_read_probe_diagnostics: bool = False
    agent_api_available: bool = False
    agent_local_diagnostics: bool = False
    agent_ssh_available: bool = False
    agent_docker_socket_available: bool = False
    agent_mutation_allowed: bool = False


class ReportAgentEntry(BaseModel):
    otbr_id: str
    agent_url: str
    reachable: bool = False
    last_seen: datetime | None = None
    last_error: str | None = None
    capabilities: dict[str, object] = Field(default_factory=dict)


class ReportHealthSection(BaseModel):
    overall: HealthStatus = Field(default_factory=HealthStatus)
    environment: HealthStatus = Field(default_factory=HealthStatus)
    mdns: HealthStatus = Field(default_factory=HealthStatus)
    trel: HealthStatus = Field(default_factory=HealthStatus)


class ReportOtbrEntry(BaseModel):
    id: str
    name: str
    reachable: bool = False
    thread_state: str | None = None
    thread_state_source: str | None = None
    json_api_thread_state: str | None = None
    legacy_node_thread_state: str | None = None
    rest_endpoint_mismatch: bool = False
    role: str | None = None
    network_name: str | None = None
    channel: int | None = None
    ext_pan_id: str | None = None
    pan_id: str | None = None
    last_seen: datetime | None = None
    last_error: str | None = None
    health: HealthStatus = Field(default_factory=HealthStatus)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class ReportMatterServerEntry(BaseModel):
    id: str
    name: str
    connected: bool = False
    node_count: int = 0
    unavailable_node_count: int = 0
    variant: str = "python"
    last_seen: datetime | None = None
    last_error: str | None = None
    health: HealthStatus = Field(default_factory=HealthStatus)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class ReportMatterNodeEntry(BaseModel):
    node_id: int
    server_id: str
    friendly_name: str | None = None
    vendor: str | None = None
    product: str | None = None
    serial: str | None = None
    firmware: str | None = None
    available: bool = False
    availability_flaps_24h: int | None = None
    subscription_flaps_24h: int | None = None
    subscription_diagnostics_available: bool = False
    case_diagnostics_available: bool = False
    command_diagnostics_available: bool = False
    read_probe_diagnostics_available: bool = False
    last_read_probe_at: datetime | None = None
    last_read_probe_ok: bool | None = None
    last_read_probe_limited: bool = False
    last_read_probe_attribute_path: str | None = None
    last_read_probe_duration_ms: int | None = None
    last_read_probe_error_code: int | str | None = None
    read_probe_failures_24h: int | None = None
    read_probe_successes_24h: int | None = None
    last_probe_label: str | None = None
    last_successful_probe_kind: str | None = None
    last_successful_probe_path: str | None = None
    last_read_probe_note: str | None = None
    ping_diagnostics_available: bool = False
    last_ping_at: datetime | None = None
    last_ping_ok: bool | None = None
    ping_failures_24h: int | None = None
    ping_successes_24h: int | None = None
    health: HealthStatus = Field(default_factory=HealthStatus)


class TrelMdnsReportSection(BaseModel):
    services_seen: int | None = None
    foreign_services_seen: int | None = None
    service_flaps_1h: int | None = None
    service_flaps_24h: int | None = None
    mdns_observation_degraded: bool | None = None
    services: list[TrelServiceState] = Field(default_factory=list)


class EventAggregates(BaseModel):
    events_by_type: dict[str, int] = Field(default_factory=dict)
    events_by_subject_type: dict[str, int] = Field(default_factory=dict)
    availability_flaps_by_node: dict[str, int] = Field(default_factory=dict)
    mdns_service_flaps_by_service: dict[str, int] = Field(default_factory=dict)
    trel_service_flaps_by_service: dict[str, int] = Field(default_factory=dict)
    otbr_role_changes_by_otbr: dict[str, int] = Field(default_factory=dict)
    matter_server_disconnects_by_server: dict[str, int] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class ReportEventsSection(BaseModel):
    recent: list[Event] = Field(default_factory=list)


class RedactionSummary(BaseModel):
    enabled: bool = True
    profile: str = "public_safe"
    secrets_removed: list[str] = Field(default_factory=list)


class ReportFocusSection(BaseModel):
    focus_node: str | None = None
    focus_device: str | None = None
    matched: bool = False
    message: str | None = None
    prioritised_subject_ids: list[str] = Field(default_factory=list)


class ThreadLensReport(BaseModel):
    generated_at: datetime
    product: str = "ThreadLens"
    tool: str = "ThreadLens"
    version: str
    mode: str = "server"
    window: str = "24h"
    site: ReportSite = Field(default_factory=ReportSite)
    summary: ReportSummary = Field(default_factory=ReportSummary)
    capabilities: ReportCapabilitiesSummary = Field(default_factory=ReportCapabilitiesSummary)
    health: ReportHealthSection = Field(default_factory=ReportHealthSection)
    thread_networks: list[ThreadNetworkState] = Field(default_factory=list)
    otbrs: list[ReportOtbrEntry] = Field(default_factory=list)
    mdns_services: list[MdnsServiceState] = Field(default_factory=list)
    trel_services: list[TrelServiceState] = Field(default_factory=list)
    matter_servers: list[ReportMatterServerEntry] = Field(default_factory=list)
    matter_nodes: list[ReportMatterNodeEntry] = Field(default_factory=list)
    agents: list[ReportAgentEntry] = Field(default_factory=list)
    trel_mdns: TrelMdnsReportSection = Field(default_factory=TrelMdnsReportSection)
    aggregates: EventAggregates = Field(default_factory=EventAggregates)
    events: ReportEventsSection = Field(default_factory=ReportEventsSection)
    redaction: RedactionSummary = Field(default_factory=RedactionSummary)
    focus: ReportFocusSection | None = None

    @staticmethod
    def foreign_network_count(networks: list[ThreadNetworkState]) -> int:
        return sum(
            1
            for network in networks
            if network.classification == ThreadNetworkClassification.OBSERVED_OTHER
            and network.currently_visible
        )
