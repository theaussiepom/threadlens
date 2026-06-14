"""Current-state models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from threadlens.models.capabilities import (
    MatterServerCapabilities,
    OtbrInternalTrelCapabilities,
    OtbrRestCapabilities,
)
from threadlens.models.health import HealthState, HealthStatus


class ThreadNetworkClassification(StrEnum):
    PRIMARY = "primary"
    OBSERVED_OTHER = "observed_other"
    UNKNOWN = "unknown"


class ThreadNetworkState(BaseModel):
    ext_pan_id: str
    name: str | None = None
    channel: int | None = None
    pan_id: str | None = None
    classification: ThreadNetworkClassification = ThreadNetworkClassification.UNKNOWN
    currently_visible: bool = False
    border_router_count: int | None = None
    source_otbr_ids: list[str] = Field(default_factory=list)
    last_seen: datetime | None = None
    first_seen: datetime | None = None


class ThreadEnvironmentState(BaseModel):
    health: HealthStatus = Field(default_factory=lambda: HealthStatus(state=HealthState.UNKNOWN))
    thread_network_count: int = 0
    foreign_network_count: int = 0
    trel_service_count: int = 0
    foreign_trel_service_count: int = 0
    matter_node_count: int = 0
    unavailable_matter_node_count: int = 0
    primary_ext_pan_id: str | None = None
    networks: list[ThreadNetworkState] = Field(default_factory=list)


class OtbrState(BaseModel):
    id: str
    name: str
    rest_url: str | None = None
    reachable: bool = False
    health: HealthStatus = Field(default_factory=lambda: HealthStatus(state=HealthState.UNKNOWN))
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
    rloc16: str | None = None
    last_error: str | None = None
    role_changes_1h: int | None = None
    capabilities: OtbrRestCapabilities = Field(default_factory=OtbrRestCapabilities)
    internal_trel: OtbrInternalTrelCapabilities = Field(
        default_factory=OtbrInternalTrelCapabilities
    )
    last_seen: datetime | None = None


class MdnsServiceState(BaseModel):
    service_id: str
    service_type: str
    instance_name: str
    hostname: str | None = None
    addresses: list[str] = Field(default_factory=list)
    port: int | None = None
    txt_records: dict[str, str] = Field(default_factory=dict)
    currently_visible: bool = False
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    last_changed: datetime | None = None
    change_count: int = 0
    flaps_1h: int | None = None
    flaps_24h: int | None = None


class TrelServiceState(BaseModel):
    service_id: str
    instance_name: str
    hostname: str | None = None
    addresses: list[str] = Field(default_factory=list)
    port: int | None = None
    txt_records: dict[str, str] = Field(default_factory=dict)
    ext_pan_id: str | None = None
    ext_address: str | None = None
    currently_visible: bool = False
    is_foreign: bool | None = None
    network_classification: ThreadNetworkClassification | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    last_changed: datetime | None = None
    change_count: int = 0
    flaps_1h: int | None = None
    flaps_24h: int | None = None


class MatterServerState(BaseModel):
    id: str
    name: str
    websocket_url: str | None = None
    variant: str = "python"
    connected: bool = False
    health: HealthStatus = Field(default_factory=lambda: HealthStatus(state=HealthState.UNKNOWN))
    node_count: int = 0
    unavailable_node_count: int = 0
    connection_flaps_24h: int | None = None
    capabilities: MatterServerCapabilities = Field(default_factory=MatterServerCapabilities)
    last_seen: datetime | None = None
    last_connected: datetime | None = None
    last_disconnected: datetime | None = None
    last_error: str | None = None


class MatterNodeState(BaseModel):
    node_id: int
    server_id: str
    friendly_name: str | None = None
    vendor: str | None = None
    vendor_id: int | None = None
    product: str | None = None
    product_id: int | None = None
    serial: str | None = None
    firmware: str | None = None
    available: bool = False
    health: HealthStatus = Field(default_factory=lambda: HealthStatus(state=HealthState.UNKNOWN))
    last_seen: datetime | None = None
    last_unavailable: datetime | None = None
    availability_flaps_1h: int | None = None
    availability_flaps_24h: int | None = None
    subscription_flaps_24h: int | None = None
    subscription_diagnostics_available: bool = False
    case_diagnostics_available: bool = False
    command_diagnostics_available: bool = False
    case_failures_24h: int | None = None
    command_failures_24h: int | None = None
    read_probe_diagnostics_available: bool = False
    last_read_probe_at: datetime | None = None
    last_read_probe_ok: bool | None = None
    last_read_probe_attribute_path: str | None = None
    last_read_probe_duration_ms: int | None = None
    last_read_probe_error_code: int | str | None = None
    read_probe_failures_24h: int | None = None
    read_probe_successes_24h: int | None = None
    ping_diagnostics_available: bool = False
    last_ping_at: datetime | None = None
    last_ping_ok: bool | None = None
    ping_failures_24h: int | None = None
    ping_successes_24h: int | None = None
