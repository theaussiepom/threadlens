"""Health state models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class HealthState(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class HealthStatus(BaseModel):
    """Factual health with explainable reasons."""

    state: HealthState = HealthState.UNKNOWN
    reasons: list[str] = Field(default_factory=list)

    def with_reason(self, reason: str) -> HealthStatus:
        if reason in self.reasons:
            return self
        return self.model_copy(update={"reasons": [*self.reasons, reason]})


class EntityHealthResult(BaseModel):
    """Health result for a single tracked entity."""

    state: HealthState = HealthState.UNKNOWN
    reasons: list[str] = Field(default_factory=list)


class OtbrHealthResult(EntityHealthResult):
    id: str


class MatterServerHealthResult(EntityHealthResult):
    id: str


class MatterNodeHealthResult(EntityHealthResult):
    id: str
    node_id: int
    server_id: str | None = None


class ThreadNetworkHealthResult(EntityHealthResult):
    ext_pan_id: str
    classification: str | None = None


class EnvironmentSummary(BaseModel):
    otbrs_configured: int = 0
    otbrs_reachable: int = 0
    matter_servers_configured: int = 0
    matter_servers_connected: int = 0
    matter_nodes_seen: int = 0
    matter_nodes_unavailable: int = 0
    thread_networks_seen: int = 0
    foreign_trel_services_seen: int = 0
    events_24h: int = 0
    warnings_24h: int = 0


class HealthReport(BaseModel):
    """Structured factual health output for /api/v1/health."""

    service: str = "threadlens-server"
    version: str
    mode: str
    site: str
    overall: HealthStatus
    environment: HealthStatus
    summary: EnvironmentSummary
    otbrs: list[OtbrHealthResult] = Field(default_factory=list)
    matter_servers: list[MatterServerHealthResult] = Field(default_factory=list)
    matter_nodes: list[MatterNodeHealthResult] = Field(default_factory=list)
    thread_networks: list[ThreadNetworkHealthResult] = Field(default_factory=list)
    mdns: HealthStatus = Field(default_factory=HealthStatus)
    trel: HealthStatus = Field(default_factory=HealthStatus)
