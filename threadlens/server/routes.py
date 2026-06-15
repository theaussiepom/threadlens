"""Server REST API routes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from threadlens import __version__
from threadlens.collectors.agent_client import AgentCollector
from threadlens.collectors.matter_server import MatterCollector
from threadlens.collectors.mdns import MdnsObserver
from threadlens.collectors.otbr_rest import OtbrCollector
from threadlens.config import RuntimeMode, ThreadLensConfig
from threadlens.enrichment.ha_matter import apply_ha_matter_device_names
from threadlens.health import HealthEngine
from threadlens.health.engine import HealthContext
from threadlens.models.ha_enrichment import HaMatterNamesPayload
from threadlens.models.health import HealthStatus
from threadlens.models.state import (
    MatterNodeState,
    MatterServerState,
    MdnsServiceState,
    OtbrState,
    ThreadNetworkState,
    TrelServiceState,
)
from threadlens.report import ReportGenerator
from threadlens.report.generator import ReportContext
from threadlens.report.serialize import report_to_dict, report_to_yaml
from threadlens.report.window import SUPPORTED_WINDOWS
from threadlens.server.dashboard_context import build_dashboard_response
from threadlens.server.events import DashboardBroadcaster
from threadlens.server.summary import (
    build_capabilities_payload,
    build_events_payload,
    build_state_payload,
)
from threadlens.storage.repositories import CurrentStateType, StorageRepository


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if not key.startswith("_")}


async def _list_states_from_storage(
    repository: StorageRepository,
    object_type: CurrentStateType,
    model_type: type[Any],
) -> list[Any]:
    payloads = await repository.list_current_state(object_type)
    return [model_type.model_validate(_clean_payload(payload)) for payload in payloads]


def _health_context(request: Request, config: ThreadLensConfig) -> HealthContext:
    repository: StorageRepository | None = getattr(request.app.state, "storage", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Storage not ready")
    return HealthContext(
        config=config,
        repository=repository,
        mdns_observer=getattr(request.app.state, "mdns_observer", None),
        otbr_collector=getattr(request.app.state, "otbr_collector", None),
        matter_collector=getattr(request.app.state, "matter_collector", None),
    )


async def _enrich_otbr_states_with_health(
    request: Request,
    config: ThreadLensConfig,
    *,
    active_mode: RuntimeMode,
    states: list[OtbrState],
) -> list[OtbrState]:
    engine = HealthEngine(_health_context(request, config))
    health_report = await engine.build_report(version=__version__, mode=active_mode.value)
    health_by_id = {item.id: item for item in health_report.otbrs}
    enriched: list[OtbrState] = []
    for state in states:
        health = health_by_id.get(state.id)
        if health is None:
            enriched.append(state)
            continue
        enriched.append(
            state.model_copy(
                update={
                    "health": HealthStatus(
                        state=health.state,
                        reasons=health.reasons,
                    )
                }
            )
        )
    return enriched


def _report_context(request: Request, config: ThreadLensConfig) -> ReportContext:
    repository: StorageRepository | None = getattr(request.app.state, "storage", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Storage not ready")
    return ReportContext(
        config=config,
        repository=repository,
        mdns_observer=getattr(request.app.state, "mdns_observer", None),
        otbr_collector=getattr(request.app.state, "otbr_collector", None),
        matter_collector=getattr(request.app.state, "matter_collector", None),
    )


async def _generate_report_response(
    request: Request,
    config: ThreadLensConfig,
    *,
    window: str,
    focus_node: str | None,
    focus_device: str | None,
    as_json: bool | None = None,
) -> Response:
    if window not in SUPPORTED_WINDOWS:
        raise HTTPException(status_code=400, detail=f"Unsupported window: {window}")

    generator = ReportGenerator(_report_context(request, config))
    report = await generator.generate(
        window=window,
        focus_node=focus_node,
        focus_device=focus_device,
        version=__version__,
    )
    request.app.state.report_last_generated_at = report.generated_at
    request.app.state.report_last_window = window

    use_json = as_json
    if use_json is None:
        accept = request.headers.get("accept", "")
        use_json = "application/json" in accept.lower()

    if use_json:
        return JSONResponse(report_to_dict(report))
    return Response(
        content=report_to_yaml(report),
        media_type="application/yaml",
    )


def create_router(config: ThreadLensConfig, *, active_mode: RuntimeMode) -> APIRouter:
    router = APIRouter()

    @router.get("/version")
    async def version() -> dict[str, str]:
        return {"tool": "ThreadLens", "version": __version__}

    @router.get("/dashboard")
    async def dashboard(request: Request) -> dict[str, object]:
        return await build_dashboard_response(request, config, active_mode=active_mode)

    @router.get("/health")
    async def health(request: Request) -> dict[str, object]:
        repository: StorageRepository | None = getattr(request.app.state, "storage", None)
        if repository is None or not getattr(request.app.state, "storage_ready", False):
            raise HTTPException(status_code=503, detail="Storage not ready")

        engine = HealthEngine(_health_context(request, config))
        report = await engine.build_report(version=__version__, mode=active_mode.value)
        return report.model_dump(mode="json")

    @router.get("/status")
    async def status(request: Request) -> dict[str, object]:
        storage_ready = bool(getattr(request.app.state, "storage_ready", False))
        observer: MdnsObserver | None = getattr(request.app.state, "mdns_observer", None)
        otbr_collector: OtbrCollector | None = getattr(request.app.state, "otbr_collector", None)
        matter_collector: MatterCollector | None = getattr(
            request.app.state, "matter_collector", None
        )
        mqtt_publisher = getattr(request.app.state, "mqtt_publisher", None)
        agent_collector: AgentCollector | None = getattr(request.app.state, "agent_collector", None)
        configured_agents = sum(1 for otbr in config.otbrs if otbr.agent_url)
        if configured_agents == 0:
            agents_status: dict[str, object] = {"configured": 0}
        else:
            agents_status = {
                "configured": configured_agents,
                "reachable": agent_collector.reachable_count if agent_collector else 0,
                "unreachable": agent_collector.unreachable_count if agent_collector else 0,
                "last_poll_at": (
                    agent_collector.last_poll_at.isoformat()
                    if agent_collector and agent_collector.last_poll_at
                    else None
                ),
            }
        mdns_status = {
            "enabled": config.mdns.enabled,
            "services_configured": len(config.mdns.services),
            "observer_running": bool(observer and observer.running),
            "observation_degraded": observer.observation_degraded if observer else None,
        }
        otbr_status = {
            "configured": len(config.otbrs),
            "collector_running": bool(otbr_collector and otbr_collector.running),
            "reachable": otbr_collector.reachable_count if otbr_collector else 0,
            "unreachable": otbr_collector.unreachable_count if otbr_collector else 0,
            "last_poll_at": (
                otbr_collector.last_poll_at.isoformat()
                if otbr_collector and otbr_collector.last_poll_at
                else None
            ),
        }
        if matter_collector is not None:
            matter_status = matter_collector.status()
        else:
            matter_status = {
                "configured": len(config.matter_servers),
                "collector_running": False,
                "connected": 0,
                "disconnected": len(config.matter_servers),
                "nodes_seen": 0,
                "unavailable_nodes": 0,
                "last_event_at": None,
            }
        if mqtt_publisher is not None:
            mqtt_status = mqtt_publisher.status()
        else:
            mqtt_status = {
                "enabled": config.mqtt.enabled,
                "connected": False,
                "publisher_running": False,
                "homeassistant_discovery_enabled": (config.homeassistant.mqtt_discovery_enabled),
                "last_publish_at": None,
                "last_error": None,
            }
        return {
            "status": "running",
            "service": "threadlens-server",
            "version": __version__,
            "mode": active_mode.value,
            "site": {"name": config.site.name},
            "collectors": {
                "otbr": otbr_status,
                "matter": matter_status,
                "mdns": mdns_status,
                "mqtt": mqtt_status,
            },
            "agents": agents_status,
            "storage": {
                "sqlite_path": config.storage.sqlite_path,
                "event_retention_days": config.storage.event_retention_days,
                "ready": storage_ready,
            },
            "flapping": {
                "debounce_seconds": config.flapping.debounce_seconds,
            },
            "reports": {
                "last_generated_at": (
                    last_generated.isoformat()
                    if (
                        last_generated := getattr(
                            request.app.state, "report_last_generated_at", None
                        )
                    )
                    is not None
                    else None
                ),
                "last_window": getattr(request.app.state, "report_last_window", None),
            },
        }

    @router.get("/capabilities")
    async def capabilities(request: Request) -> dict[str, object]:
        repository: StorageRepository | None = getattr(request.app.state, "storage", None)
        if repository is None or not getattr(request.app.state, "storage_ready", False):
            raise HTTPException(status_code=503, detail="Storage not ready")
        return await build_capabilities_payload(request, config, repository)

    @router.get("/state")
    async def state(request: Request) -> dict[str, object]:
        repository: StorageRepository | None = getattr(request.app.state, "storage", None)
        if repository is None or not getattr(request.app.state, "storage_ready", False):
            raise HTTPException(status_code=503, detail="Storage not ready")
        return await build_state_payload(repository)

    @router.get("/events")
    async def events(
        request: Request,
        window: str = "24h",
        limit: int = 100,
        subject_type: str | None = None,
        subject_id: str | None = None,
        event_type: str | None = None,
    ) -> dict[str, object]:
        repository: StorageRepository | None = getattr(request.app.state, "storage", None)
        if repository is None or not getattr(request.app.state, "storage_ready", False):
            raise HTTPException(status_code=503, detail="Storage not ready")
        return await build_events_payload(
            repository,
            window=window,
            limit=limit,
            subject_type=subject_type,
            subject_id=subject_id,
            event_type=event_type,
        )

    @router.get("/report")
    async def report(
        request: Request,
        window: str = "24h",
        focus_node: str | None = None,
        focus_device: str | None = None,
    ) -> Response:
        return await _generate_report_response(
            request,
            config,
            window=window,
            focus_node=focus_node,
            focus_device=focus_device,
        )

    @router.get("/report.yaml")
    async def report_yaml(
        request: Request,
        window: str = "24h",
        focus_node: str | None = None,
        focus_device: str | None = None,
    ) -> Response:
        return await _generate_report_response(
            request,
            config,
            window=window,
            focus_node=focus_node,
            focus_device=focus_device,
            as_json=False,
        )

    @router.get("/report.json")
    async def report_json(
        request: Request,
        window: str = "24h",
        focus_node: str | None = None,
        focus_device: str | None = None,
    ) -> Response:
        return await _generate_report_response(
            request,
            config,
            window=window,
            focus_node=focus_node,
            focus_device=focus_device,
            as_json=True,
        )

    @router.get("/otbrs")
    async def otbrs(request: Request) -> dict[str, object]:
        repository: StorageRepository | None = getattr(request.app.state, "storage", None)
        if repository is None:
            raise HTTPException(status_code=503, detail="Storage not ready")
        items = await _list_states_from_storage(repository, CurrentStateType.OTBR, OtbrState)
        items = await _enrich_otbr_states_with_health(
            request,
            config,
            active_mode=active_mode,
            states=items,
        )
        return {
            "count": len(items),
            "otbrs": [item.model_dump(mode="json") for item in items],
        }

    @router.get("/networks")
    async def networks(request: Request) -> dict[str, object]:
        repository: StorageRepository | None = getattr(request.app.state, "storage", None)
        if repository is None:
            raise HTTPException(status_code=503, detail="Storage not ready")
        items = await _list_states_from_storage(
            repository,
            CurrentStateType.THREAD_NETWORK,
            ThreadNetworkState,
        )
        return {
            "count": len(items),
            "networks": [item.model_dump(mode="json") for item in items],
        }

    @router.get("/matter-servers")
    async def matter_servers(request: Request) -> dict[str, object]:
        repository: StorageRepository | None = getattr(request.app.state, "storage", None)
        if repository is None:
            raise HTTPException(status_code=503, detail="Storage not ready")
        items = await _list_states_from_storage(
            repository,
            CurrentStateType.MATTER_SERVER,
            MatterServerState,
        )
        return {
            "count": len(items),
            "matter_servers": [item.model_dump(mode="json") for item in items],
        }

    @router.get("/matter-nodes")
    async def matter_nodes(request: Request) -> dict[str, object]:
        repository: StorageRepository | None = getattr(request.app.state, "storage", None)
        if repository is None:
            raise HTTPException(status_code=503, detail="Storage not ready")
        items = await _list_states_from_storage(
            repository,
            CurrentStateType.MATTER_NODE,
            MatterNodeState,
        )
        return {
            "count": len(items),
            "matter_nodes": [item.model_dump(mode="json") for item in items],
        }

    @router.get("/mdns/services")
    async def mdns_services(request: Request) -> dict[str, object]:
        repository: StorageRepository | None = getattr(request.app.state, "storage", None)
        if repository is None:
            raise HTTPException(status_code=503, detail="Storage not ready")
        services = await _list_states_from_storage(
            repository,
            CurrentStateType.MDNS_SERVICE,
            MdnsServiceState,
        )
        return {
            "count": len(services),
            "services": [service.model_dump(mode="json") for service in services],
        }

    @router.get("/trel/services")
    async def trel_services(request: Request) -> dict[str, object]:
        repository: StorageRepository | None = getattr(request.app.state, "storage", None)
        if repository is None:
            raise HTTPException(status_code=503, detail="Storage not ready")
        services = await _list_states_from_storage(
            repository,
            CurrentStateType.TREL_SERVICE,
            TrelServiceState,
        )
        return {
            "count": len(services),
            "services": [service.model_dump(mode="json") for service in services],
        }

    @router.post("/integrations/homeassistant/matter-names")
    async def homeassistant_matter_names(
        request: Request,
        body: HaMatterNamesPayload,
    ) -> dict[str, object]:
        repository: StorageRepository | None = getattr(request.app.state, "storage", None)
        if repository is None:
            raise HTTPException(status_code=503, detail="Storage not ready")
        try:
            return await apply_ha_matter_device_names(
                repository,
                body.model_dump(mode="json"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/events/stream")
    async def events_stream(request: Request) -> EventSourceResponse:
        broadcaster: DashboardBroadcaster | None = getattr(request.app.state, "broadcaster", None)
        if broadcaster is None:
            raise HTTPException(status_code=503, detail="Event stream not ready")

        async def generator() -> AsyncIterator[dict[str, Any]]:
            yield {
                "event": "message",
                "data": json.dumps({"type": "heartbeat"}),
            }
            yield {
                "event": "dashboard_update",
                "data": json.dumps({"type": "dashboard_update"}),
            }
            async for item in broadcaster.subscribe():
                yield {
                    "event": item["event"],
                    "data": json.dumps(item["data"]),
                }

        return EventSourceResponse(generator())

    return router
