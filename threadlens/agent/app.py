"""FastAPI application factory for ThreadLens agent mode."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from threadlens import __version__
from threadlens.agent.routes import create_router
from threadlens.config import ThreadLensConfig
from threadlens.utils.time import utc_now


def create_agent_app(config: ThreadLensConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.started_at = utc_now()
        yield

    app = FastAPI(
        title="ThreadLens Agent",
        description="Optional co-located ThreadLens diagnostics agent",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.config = config
    app.include_router(create_router(config), prefix="/api/v1/agent")
    return app
