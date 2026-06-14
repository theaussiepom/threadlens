"""Agent process lifecycle helpers."""

from __future__ import annotations

import uvicorn

from threadlens.agent.app import create_agent_app
from threadlens.config import ThreadLensConfig


def run_agent(config: ThreadLensConfig) -> None:
    app = create_agent_app(config)
    uvicorn.run(
        app,
        host=config.agent.host,
        port=config.agent.port,
        log_level="info",
    )
