"""Server process lifecycle helpers."""

from __future__ import annotations

import uvicorn

from threadlens.config import RuntimeMode, ThreadLensConfig
from threadlens.server.app import create_server_app


def run_server(config: ThreadLensConfig, *, active_mode: RuntimeMode) -> None:
    app = create_server_app(config, active_mode=active_mode)
    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )
