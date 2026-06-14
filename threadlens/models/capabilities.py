"""Capability models — distinguish unavailable from observed zero."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ThreadLensRuntimeCapabilities(BaseModel):
    server_api_available: bool = True
    agent_api_available: bool = False
    storage_available: bool = False
    report_generation_available: bool = False
    mqtt_publisher_available: bool = False


class MdnsObservationCapabilities(BaseModel):
    mdns_observation_available: bool = False
    mdns_observation_degraded: bool = True
    trel_mdns_available: bool = False
    meshcop_mdns_available: bool = False
    matter_mdns_available: bool = False


class OtbrRestCapabilities(BaseModel):
    rest_available: bool = False
    network_dataset_available: bool = False
    thread_stack_active: bool = False
    legacy_node_available: bool = False
    json_api_state_stale: bool = False
    topology_available: bool = False
    network_diagnostics_available: bool = False
    device_inventory_available: bool = False


class OtbrInternalTrelCapabilities(BaseModel):
    peer_table_available: bool = False
    counters_available: bool = False
    reason: str | None = None


class MatterServerCapabilities(BaseModel):
    websocket_available: bool = False
    node_inventory_available: bool = False
    node_availability_available: bool = False
    subscription_diagnostics_available: bool = False
    case_diagnostics_available: bool = False
    command_diagnostics_available: bool = False
    variant: str = "python"


class AgentCapabilities(BaseModel):
    local_otbr_diagnostics: bool = False
    local_trel_diagnostics: bool = False
    log_evidence: bool = False


class EnvironmentCapabilities(BaseModel):
    """Aggregate capability view for reports and API."""

    threadlens: ThreadLensRuntimeCapabilities = Field(default_factory=ThreadLensRuntimeCapabilities)
    mdns: MdnsObservationCapabilities = Field(default_factory=MdnsObservationCapabilities)
    otbr: OtbrRestCapabilities = Field(default_factory=OtbrRestCapabilities)
    otbr_internal_trel: OtbrInternalTrelCapabilities = Field(
        default_factory=OtbrInternalTrelCapabilities
    )
    matter_server: MatterServerCapabilities = Field(default_factory=MatterServerCapabilities)
    agent: AgentCapabilities = Field(default_factory=AgentCapabilities)
