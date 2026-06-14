"""Agent REST API routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from threadlens import __version__
from threadlens.config import ThreadLensConfig
from threadlens.models.agent import (
    AgentCapabilitiesResponse,
    AgentHealthResponse,
    AgentInfoResponse,
    AgentStatusResponse,
    default_agent_capabilities,
)
from threadlens.models.health import HealthState


def create_router(config: ThreadLensConfig) -> APIRouter:
    router = APIRouter()
    capabilities = default_agent_capabilities(__version__)

    @router.get("/health")
    async def health() -> AgentHealthResponse:
        return AgentHealthResponse(
            version=__version__,
            site=config.site.name,
            state=HealthState.HEALTHY,
            reasons=[],
        )

    @router.get("/status")
    async def status(request: Request) -> AgentStatusResponse:
        started_at = getattr(request.app.state, "started_at", None)
        return AgentStatusResponse(
            version=__version__,
            site=config.site.name,
            started_at=started_at,
            capabilities=capabilities,
        )

    @router.get("/capabilities")
    async def capabilities_endpoint() -> AgentCapabilitiesResponse:
        return AgentCapabilitiesResponse(
            agent=capabilities,
            site={"name": config.site.name},
        )

    @router.get("/info")
    async def info() -> AgentInfoResponse:
        return AgentInfoResponse(
            version=__version__,
            site=config.site.name,
        )

    return router
