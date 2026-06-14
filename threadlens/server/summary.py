"""Helpers for read-only summary API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from threadlens.config import ThreadLensConfig
from threadlens.models.agent import AgentState
from threadlens.models.reports import ReportCapabilitiesSummary
from threadlens.models.state import (
    MatterNodeState,
    MatterServerState,
    MdnsServiceState,
    OtbrState,
    TrelServiceState,
)
from threadlens.report.generator import ReportContext, ReportGenerator
from threadlens.report.window import SUPPORTED_WINDOWS, parse_window
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


async def build_capabilities_payload(
    request: Request,
    config: ThreadLensConfig,
    repository: StorageRepository,
) -> dict[str, Any]:
    """Build capability summary aligned with report capabilities."""
    context = ReportContext(
        config=config,
        repository=repository,
        mdns_observer=getattr(request.app.state, "mdns_observer", None),
        otbr_collector=getattr(request.app.state, "otbr_collector", None),
        matter_collector=getattr(request.app.state, "matter_collector", None),
    )
    generator = ReportGenerator(context)
    otbr_states = await _list_states(repository, CurrentStateType.OTBR, OtbrState)
    matter_servers = await _list_states(
        repository, CurrentStateType.MATTER_SERVER, MatterServerState
    )
    matter_nodes = await _list_states(repository, CurrentStateType.MATTER_NODE, MatterNodeState)
    mdns_services = await _list_states(repository, CurrentStateType.MDNS_SERVICE, MdnsServiceState)
    trel_services = await _list_states(repository, CurrentStateType.TREL_SERVICE, TrelServiceState)
    agent_states = await _list_states(repository, CurrentStateType.AGENT, AgentState)
    capabilities: ReportCapabilitiesSummary = generator._build_capabilities(
        otbr_states=otbr_states,
        matter_servers=matter_servers,
        matter_nodes=matter_nodes,
        mdns_services=mdns_services,
        trel_services=trel_services,
        agent_states=agent_states,
    )
    return capabilities.model_dump(mode="json")


async def build_state_payload(repository: StorageRepository) -> dict[str, Any]:
    """Return grouped current state objects from SQLite."""
    payloads = await repository.list_current_state()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for payload in payloads:
        object_type = str(payload.get("_object_type", "unknown"))
        entry = _clean_payload(payload)
        entry["id"] = payload.get("_object_id")
        entry["updated_at"] = payload.get("_updated_at")
        grouped.setdefault(object_type, []).append(entry)
    return {
        "generated_at": utc_now().isoformat(),
        "count": len(payloads),
        "objects": grouped,
    }


async def build_events_payload(
    repository: StorageRepository,
    *,
    window: str,
    limit: int,
    subject_type: str | None = None,
    subject_id: str | None = None,
    event_type: str | None = None,
) -> dict[str, Any]:
    """Return recent events for the requested window."""
    if window not in SUPPORTED_WINDOWS:
        raise HTTPException(status_code=400, detail=f"Unsupported window: {window}")
    bounded_limit = max(1, min(limit, 500))
    since = utc_now() - parse_window(window)
    events = await repository.get_events(
        since=since,
        limit=bounded_limit,
        subject_type=subject_type,
        subject_id=subject_id,
        event_type=event_type,
    )
    return {
        "window": window,
        "since": since.isoformat(),
        "count": len(events),
        "events": [event.model_dump(mode="json") for event in events],
    }
