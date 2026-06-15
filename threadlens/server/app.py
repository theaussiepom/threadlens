"""FastAPI application factory for ThreadLens server mode."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from threadlens import __version__
from threadlens.collectors.agent_client import AgentCollector
from threadlens.collectors.matter_server import MatterCollector
from threadlens.collectors.mdns import MdnsObserver
from threadlens.collectors.otbr_rest import OtbrCollector
from threadlens.config import RuntimeMode, ThreadLensConfig
from threadlens.mqtt import MqttPublisher
from threadlens.server.routes import create_router
from threadlens.server.static import api_landing_page, mount_static_ui
from threadlens.storage.db import Database
from threadlens.storage.repositories import StorageRepository


def create_server_app(config: ThreadLensConfig, *, active_mode: RuntimeMode) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(config.storage.sqlite_path)
        repository = StorageRepository(database)
        observer: MdnsObserver | None = None
        otbr_collector: OtbrCollector | None = None
        matter_collector: MatterCollector | None = None
        agent_collector: AgentCollector | None = None
        mqtt_publisher: MqttPublisher | None = None
        try:
            await repository.initialize()
            app.state.database = database
            app.state.storage = repository
            app.state.storage_ready = True

            if config.mdns.enabled:
                observer = MdnsObserver(config, repository)
                await observer.start()
                app.state.mdns_observer = observer

            if config.otbrs:
                otbr_collector = OtbrCollector(config, repository)
                await otbr_collector.start()
                app.state.otbr_collector = otbr_collector

            if config.matter_servers:
                matter_collector = MatterCollector(config, repository)
                await matter_collector.start()
                app.state.matter_collector = matter_collector

            if any(otbr.agent_url for otbr in config.otbrs):
                agent_collector = AgentCollector(config, repository)
                await agent_collector.start()
                app.state.agent_collector = agent_collector

            if config.mqtt.enabled:
                mqtt_publisher = MqttPublisher(
                    config,
                    repository,
                    version=__version__,
                    mode=active_mode.value,
                    mdns_observer=observer,
                    otbr_collector=otbr_collector,
                    matter_collector=matter_collector,
                )
                await mqtt_publisher.start()
                app.state.mqtt_publisher = mqtt_publisher

            yield
        finally:
            if mqtt_publisher is not None:
                await mqtt_publisher.stop()
                app.state.mqtt_publisher = None
            if matter_collector is not None:
                await matter_collector.stop()
                app.state.matter_collector = None
            if agent_collector is not None:
                await agent_collector.stop()
                app.state.agent_collector = None
            if otbr_collector is not None:
                await otbr_collector.stop()
                app.state.otbr_collector = None
            if observer is not None:
                await observer.stop()
                app.state.mdns_observer = None
            app.state.storage_ready = False
            await database.close()

    app = FastAPI(
        title="ThreadLens",
        description="Read-only Thread and Matter-over-Thread observability",
        version=__version__,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def allow_embedded_ui(request: Request, call_next):
        """Allow Core dashboard iframe embedding from Home Assistant companion panel."""
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/assets"):
            response.headers["Content-Security-Policy"] = "frame-ancestors *"
        return response

    app.state.config = config
    app.state.storage_ready = False
    app.state.mdns_observer = None
    app.state.otbr_collector = None
    app.state.matter_collector = None
    app.state.agent_collector = None
    app.state.mqtt_publisher = None
    app.state.report_last_generated_at = None
    app.state.report_last_window = None

    app.include_router(create_router(config, active_mode=active_mode), prefix="/api/v1")

    if not mount_static_ui(app):

        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def root() -> str:
            return api_landing_page(version=__version__)

    return app
