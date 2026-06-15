"""Gather Core state for the dashboard aggregation endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from threadlens import __version__
from threadlens.collectors.agent_client import AgentCollector
from threadlens.collectors.matter_server import MatterCollector
from threadlens.collectors.mdns import MdnsObserver
from threadlens.collectors.otbr_rest import OtbrCollector
from threadlens.config import RuntimeMode, ThreadLensConfig
from threadlens.enrichment.thread_matter import build_thread_device_index, correlate_thread_identity
from threadlens.health import HealthEngine
from threadlens.health.engine import HealthContext
from threadlens.models.health import HealthStatus
from threadlens.models.state import (
    MatterNodeState,
    MatterServerState,
    MdnsServiceState,
    OtbrState,
    ThreadDeviceState,
    ThreadNetworkState,
    TrelServiceState,
)
from threadlens.server.dashboard import DASHBOARD_REPORT_URLS, build_dashboard_payload
from threadlens.server.summary import build_events_payload
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.time import utc_now


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if not key.startswith("_")}


async def _list_states(
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


async def _enrich_matter_nodes_with_health(
    health_report: Any,
    states: list[MatterNodeState],
) -> list[MatterNodeState]:
    health_by_id = {item.id: item for item in health_report.matter_nodes}
    enriched: list[MatterNodeState] = []
    for state in states:
        subject_id = f"matter_node:{state.server_id}:{state.node_id}"
        health = health_by_id.get(subject_id)
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


def _build_status_payload(
    request: Request,
    config: ThreadLensConfig,
    *,
    active_mode: RuntimeMode,
) -> dict[str, Any]:
    storage_ready = bool(getattr(request.app.state, "storage_ready", False))
    observer: MdnsObserver | None = getattr(request.app.state, "mdns_observer", None)
    otbr_collector: OtbrCollector | None = getattr(request.app.state, "otbr_collector", None)
    matter_collector: MatterCollector | None = getattr(request.app.state, "matter_collector", None)
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
            "homeassistant_discovery_enabled": config.homeassistant.mqtt_discovery_enabled,
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
        "reports": {
            "last_generated_at": (
                last_generated.isoformat()
                if (last_generated := getattr(request.app.state, "report_last_generated_at", None))
                is not None
                else None
            ),
            "last_window": getattr(request.app.state, "report_last_window", None),
        },
    }


async def build_dashboard_response(
    request: Request,
    config: ThreadLensConfig,
    *,
    active_mode: RuntimeMode,
) -> dict[str, Any]:
    """Build the full dashboard payload from live Core storage and collectors."""
    repository: StorageRepository | None = getattr(request.app.state, "storage", None)
    if repository is None or not getattr(request.app.state, "storage_ready", False):
        raise HTTPException(status_code=503, detail="Storage not ready")

    engine = HealthEngine(_health_context(request, config))
    health_report = await engine.build_report(version=__version__, mode=active_mode.value)
    health = health_report.model_dump(mode="json")

    otbr_states = await _list_states(repository, CurrentStateType.OTBR, OtbrState)
    otbr_states = await _enrich_otbr_states_with_health(
        request,
        config,
        active_mode=active_mode,
        states=otbr_states,
    )
    networks = await _list_states(repository, CurrentStateType.THREAD_NETWORK, ThreadNetworkState)
    matter_servers = await _list_states(
        repository, CurrentStateType.MATTER_SERVER, MatterServerState
    )
    matter_nodes = await _list_states(repository, CurrentStateType.MATTER_NODE, MatterNodeState)
    matter_nodes = await _enrich_matter_nodes_with_health(health_report, matter_nodes)
    thread_devices = await _list_states(
        repository, CurrentStateType.THREAD_DEVICE, ThreadDeviceState
    )
    thread_index = build_thread_device_index(
        [device.model_dump(mode="json") for device in thread_devices]
    )
    matter_node_payloads = []
    for node in matter_nodes:
        payload = node.model_dump(mode="json")
        payload.update(correlate_thread_identity(payload, thread_index=thread_index))
        matter_node_payloads.append(payload)
    mdns_services = await _list_states(repository, CurrentStateType.MDNS_SERVICE, MdnsServiceState)
    trel_services = await _list_states(repository, CurrentStateType.TREL_SERVICE, TrelServiceState)
    events_payload = await build_events_payload(repository, window="24h", limit=100)

    return build_dashboard_payload(
        connected=True,
        last_update=utc_now().isoformat(),
        version={"tool": "ThreadLens", "version": __version__},
        status=_build_status_payload(request, config, active_mode=active_mode),
        health=health,
        otbrs=[item.model_dump(mode="json") for item in otbr_states],
        networks=[item.model_dump(mode="json") for item in networks],
        matter_servers=[item.model_dump(mode="json") for item in matter_servers],
        matter_nodes=matter_node_payloads,
        mdns_services=[item.model_dump(mode="json") for item in mdns_services],
        trel_services=[item.model_dump(mode="json") for item in trel_services],
        events=events_payload,
        report_urls=DASHBOARD_REPORT_URLS,
    )
