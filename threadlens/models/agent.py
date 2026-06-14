"""ThreadLens Agent API and state models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from threadlens.models.health import HealthState


class AgentApiCapabilities(BaseModel):
    """Capabilities exposed by the v1 ThreadLens agent API."""

    available: bool = True
    version: str = "0.1.0"
    mode: str = "agent"
    local_process: bool = True
    otbr_local_diagnostics: bool = False
    otbr_internal_trel_peer_table: bool = False
    otbr_internal_trel_counters: bool = False
    local_log_evidence: bool = False
    docker_socket_available: bool = False
    ssh_available: bool = False
    mutation_allowed: bool = False


def default_agent_capabilities(version: str) -> AgentApiCapabilities:
    return AgentApiCapabilities(version=version)


class AgentHealthResponse(BaseModel):
    service: str = "threadlens-agent"
    version: str
    mode: str = "agent"
    site: str
    state: HealthState = HealthState.HEALTHY
    reasons: list[str] = Field(default_factory=list)


class AgentStatusResponse(BaseModel):
    service: str = "threadlens-agent"
    version: str
    mode: str = "agent"
    site: str
    started_at: datetime | None = None
    capabilities: AgentApiCapabilities = Field(default_factory=AgentApiCapabilities)


class AgentCapabilitiesResponse(BaseModel):
    agent: AgentApiCapabilities = Field(default_factory=AgentApiCapabilities)
    site: dict[str, str] = Field(default_factory=dict)


class AgentInfoResponse(BaseModel):
    service: str = "threadlens-agent"
    version: str
    mode: str = "agent"
    site: str
    description: str = "Optional co-located read-only ThreadLens diagnostics agent"
    mutation_allowed: bool = False


class AgentState(BaseModel):
    """Server-side view of a configured OTBR agent endpoint."""

    otbr_id: str
    agent_url: str
    reachable: bool = False
    last_seen: datetime | None = None
    last_error: str | None = None
    capabilities: AgentApiCapabilities = Field(default_factory=AgentApiCapabilities)
    status: dict[str, object] | None = None
