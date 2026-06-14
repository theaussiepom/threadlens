"""Pure dashboard aggregation for the ThreadLens Core API.

Home Assistant agnostic: composes a dashboard payload from Core storage, health,
and collector status. Does not poll, mutate, or infer device parentage.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from threadlens.report.redaction import redact_structure

# Friendly, non-causal labels for known health reason codes. Unknown codes are
# humanised generically so new core reasons still render acceptably.
REASON_LABELS: dict[str, str] = {
    "otbr_rest_endpoint_mismatch": "OTBR REST endpoints disagree",
    "foreign_trel_services_observed": "Other Thread/TREL services visible",
    "mdns_service_flapping_degraded": "mDNS service add/remove instability",
    "mdns_service_flapping_warning": "mDNS service add/remove churn",
    "otbr_thread_stack_disabled": "OTBR Thread stack disabled",
    "otbr_unreachable": "OTBR REST API unreachable",
    "matter_server_disconnected": "Matter server disconnected",
    "matter_node_unavailable": "Matter node unavailable",
    "matter_node_read_probe_failed": "Safe read probe failed recently",
    "matter_node_read_probe_failures_24h": "Repeated safe read probe failures (24h)",
    "matter_node_read_probe_diagnostics_limited": "Read diagnostics limited",
    "matter_node_ping_probe_failed": "Ping probe failed recently",
    "primary_thread_network_unknown": "Primary Thread network unknown",
    "configured_otbrs_disagree_on_ext_pan_id": "Configured OTBRs disagree on network",
}

FOREIGN_TREL_INFO_MESSAGE = (
    "Other Thread/TREL services are visible on the LAN. This is common when HomePods, "
    "Apple TVs, Nest devices, or other Thread fabrics are present. ThreadLens does not "
    "treat this as a fault by itself."
)

_CLASSIFICATION_HEALTH_LABEL = {
    "unavailable": "Unavailable",
    "needs_attention": "Needs attention",
    "recently_unstable": "Recently unstable",
    "diagnostics_limited": "Diagnostics limited",
    "healthy": "Healthy",
    "unknown": "Unknown",
}

_SEVERITY = {
    "healthy": 0,
    "unknown": 1,
    "warning": 2,
    "degraded": 3,
    "critical": 4,
}

_INACTIVE_STATES = frozenset({"disabled", "inactive", "unknown", ""})
_ACTIVE_EFFECTIVE_STATES = frozenset(
    {"active", "leader", "router", "child", "detached", "leader/router"}
)
_MISMATCH_ONLY_REASON = "otbr_rest_endpoint_mismatch"

# Reasons that are informational background observations on their own and should
# not, by themselves, make the dashboard look unhealthy. Raw codes remain in
# diagnostics/reasons_all.
_INFO_REASON_CODES = frozenset(
    {
        "foreign_trel_services_observed",
        "matter_node_read_probe_diagnostics_limited",
    }
)

# Event windowing for the node-health / incident view.
DEFAULT_EVENT_WINDOW = "24h"
MAX_EVENTS = 100

_NODE_UNAVAILABLE_EVENT = "matter_node.unavailable"
_NODE_RECOVERED_EVENT = "matter_node.recovered"

# Event types considered relevant for the incident/correlation view. Routine
# "seen"/"changed"/"added" observations are excluded to keep the timeline useful.
_RELEVANT_EVENT_TYPES = frozenset(
    {
        "matter_node.unavailable",
        "matter_node.recovered",
        "matter_node.removed",
        "matter_node.read_probe.succeeded",
        "matter_node.read_probe.failed",
        "matter_node.read_probe.timed_out",
        "matter_node.read_probe.unsupported",
        "matter_node.read_probe.skipped",
        "matter_node.ping.succeeded",
        "matter_node.ping.failed",
        "matter_node.ping.timed_out",
        "matter_server.connected",
        "matter_server.disconnected",
        "otbr.unreachable",
        "otbr.reachable",
        "otbr.role_changed",
        "otbr.dataset_changed",
        "thread_network.lost",
        "mdns.service_removed",
        "trel.service_removed",
    }
)

_INFRA_DEGRADED_EVENTS = frozenset(
    {
        "matter_server.disconnected",
        "otbr.unreachable",
        "thread_network.lost",
    }
)

DASHBOARD_REPORT_URLS = {
    "yaml": "api/v1/report.yaml",
    "json": "api/v1/report.json",
}


def humanize_reason(code: str) -> str:
    """Return a friendly label for a reason code."""
    if code in REASON_LABELS:
        return REASON_LABELS[code]
    return code.replace("_", " ").strip().capitalize()


def friendly_reasons(codes: Any) -> list[dict[str, str]]:
    """Map a list of reason codes to ``{code, label}`` dictionaries."""
    if not isinstance(codes, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for code in codes:
        if not isinstance(code, str) or code in seen:
            continue
        seen.add(code)
        result.append({"code": code, "label": humanize_reason(code)})
    return result


def _normalise_state(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _effective_state(raw: dict[str, Any]) -> str | None:
    """Return the effective Thread state ThreadLens is using."""
    for key in ("role", "thread_state"):
        value = _normalise_state(raw.get(key))
        if value and value not in _INACTIVE_STATES:
            return value
    return None


def _source_label(thread_state_source: Any) -> str | None:
    if not thread_state_source:
        return None
    source = str(thread_state_source).strip().lower()
    if source in {"legacy_node", "node"}:
        return "/node"
    if source == "json_api":
        return "JSON:API"
    return str(thread_state_source)


def is_reconciled_endpoint_mismatch(raw: dict[str, Any]) -> bool:
    """True when ThreadLens trusts an active /node state despite JSON:API disagreement."""
    if not raw.get("rest_endpoint_mismatch"):
        return False
    if not raw.get("reachable"):
        return False

    effective = _effective_state(raw)
    if not effective or effective in _INACTIVE_STATES:
        return False

    json_api = _normalise_state(raw.get("json_api_thread_state"))
    legacy = _normalise_state(raw.get("legacy_node_thread_state"))
    source = _normalise_state(raw.get("thread_state_source"))

    if json_api in _INACTIVE_STATES and legacy not in _INACTIVE_STATES:
        return True
    if source in {"legacy_node", "node"} and effective in _ACTIVE_EFFECTIVE_STATES:
        return True
    return effective in _ACTIVE_EFFECTIVE_STATES


def mismatch_detail_text(raw: dict[str, Any]) -> str | None:
    """Informational detail for reconciled endpoint mismatches."""
    if not raw.get("rest_endpoint_mismatch"):
        return None
    json_api = raw.get("json_api_thread_state") or "unknown"
    legacy = raw.get("legacy_node_thread_state") or "unknown"
    source = _source_label(raw.get("thread_state_source")) or "active endpoint"
    effective = _effective_state(raw) or raw.get("thread_state") or raw.get("role") or "unknown"
    return (
        "OTBR endpoint mismatch observed. JSON:API reported "
        f"{json_api}, while /node reported {legacy}. ThreadLens is using {source} "
        f"because it matches the observed active Thread role ({effective}). "
        "No action is required."
    )


def _all_mismatch_otbrs_reconciled(otbrs: list[dict[str, Any]]) -> bool:
    mismatched = [item for item in otbrs if item.get("rest_endpoint_mismatch")]
    if not mismatched:
        return False
    return all(is_reconciled_endpoint_mismatch(item) for item in mismatched)


def _filter_prominent_reason_codes(codes: list[str], otbrs: list[dict[str, Any]]) -> list[str]:
    """Hide reconciled mismatch and informational codes from prominent chips."""
    filtered = [code for code in codes if code not in _INFO_REASON_CODES]
    if _MISMATCH_ONLY_REASON in filtered and _all_mismatch_otbrs_reconciled(otbrs):
        filtered = [code for code in filtered if code != _MISMATCH_ONLY_REASON]
    return filtered


def _combined_reasons_filtered(
    otbrs: list[dict[str, Any]], *sections: Any
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return ``(prominent_reasons, all_reasons)`` for the dashboard header."""
    codes: list[str] = []
    for section in sections:
        codes.extend(_reasons(section))
    all_reasons = friendly_reasons(codes)
    prominent_codes = _filter_prominent_reason_codes(codes, otbrs)
    return friendly_reasons(prominent_codes), all_reasons


def _state(section: Any) -> str:
    if isinstance(section, dict):
        value = section.get("state")
        if isinstance(value, str):
            return value
    return "unknown"


def _reasons(section: Any) -> list[str]:
    if isinstance(section, dict):
        value = section.get("reasons")
        if isinstance(value, list):
            return [str(item) for item in value]
    return []


def _rollup(states: list[str]) -> str:
    """Return the worst state from a list, or ``unknown`` when empty."""
    worst = "unknown"
    worst_value = -1
    for state in states:
        value = _SEVERITY.get(state, 1)
        if value > worst_value:
            worst_value = value
            worst = state
    return worst


def _otbr_entry(raw: dict[str, Any]) -> dict[str, Any]:
    health = raw.get("health") if isinstance(raw.get("health"), dict) else {}
    health_state = _state(health)
    health_reason_codes = _reasons(health)
    reconciled = is_reconciled_endpoint_mismatch(raw)
    effective_state = _effective_state(raw)
    source_label = _source_label(raw.get("thread_state_source"))

    display_health = health_state
    if reconciled and set(health_reason_codes) <= {_MISMATCH_ONLY_REASON}:
        display_health = "healthy"

    prominent_reasons = friendly_reasons(health_reason_codes)
    if reconciled and set(health_reason_codes) <= {_MISMATCH_ONLY_REASON}:
        prominent_reasons = []

    capabilities = raw.get("capabilities")
    if not isinstance(capabilities, dict):
        capabilities = {}

    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "reachable": bool(raw.get("reachable")),
        "health": health_state,
        "display_health": display_health,
        "reasons": prominent_reasons,
        "reasons_all": friendly_reasons(health_reason_codes),
        "effective_state": effective_state,
        "state_source_label": source_label,
        "thread_state": raw.get("thread_state"),
        "role": raw.get("role"),
        "network_name": raw.get("network_name"),
        "extended_pan_id": raw.get("ext_pan_id"),
        "rloc16": raw.get("rloc16"),
        "channel": raw.get("channel"),
        "thread_state_source": raw.get("thread_state_source"),
        "rest_endpoint_mismatch": bool(raw.get("rest_endpoint_mismatch")),
        "mismatch_reconciled": reconciled,
        "mismatch_detail": mismatch_detail_text(raw),
        "json_api_thread_state": raw.get("json_api_thread_state"),
        "legacy_node_thread_state": raw.get("legacy_node_thread_state"),
        "capabilities": capabilities,
    }


def _network_entry(raw: dict[str, Any], health_by_pan: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ext_pan_id = raw.get("ext_pan_id")
    health_section = health_by_pan.get(ext_pan_id, {}) if ext_pan_id else {}
    return {
        "extended_pan_id": ext_pan_id,
        "name": raw.get("name"),
        "channel": raw.get("channel"),
        "pan_id": raw.get("pan_id"),
        "border_router_count": raw.get("border_router_count"),
        "classification": raw.get("classification"),
        "health": _state(health_section) if health_section else "unknown",
    }


def _matter_section(
    matter_servers: list[dict[str, Any]],
    matter_nodes: list[dict[str, Any]],
    health: dict[str, Any] | None,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    servers_total = len(matter_servers)
    servers_connected = sum(1 for server in matter_servers if server.get("connected"))

    nodes = [_node_entry(node, events) for node in matter_nodes if isinstance(node, dict)]
    nodes = _sort_nodes(nodes)

    groups = {
        "unavailable": [],
        "needs_attention": [],
        "recently_unstable": [],
        "diagnostics_limited": [],
        "unknown": [],
        "healthy": [],
    }
    for node in nodes:
        groups.setdefault(node["classification"], []).append(node)

    unavailable_nodes = groups["unavailable"]
    recent_unavailable_count = sum(n.get("recent_unavailable_count", 0) for n in nodes)
    recent_recovered_count = sum(n.get("recent_recovered_count", 0) for n in nodes)
    affected_nodes = [
        {
            "node_id": n["node_id"],
            "name": n["name"],
            "health": n["health"],
            "unavailable_count": n.get("recent_unavailable_count", 0),
            "recovered_count": n.get("recent_recovered_count", 0),
            "last_event_at": n.get("last_event_at"),
        }
        for n in nodes
        if n.get("recent_unavailable_count") or n.get("recent_recovered_count")
    ]

    health_states: list[str] = []
    if isinstance(health, dict):
        for entry in health.get("matter_servers", []) or []:
            health_states.append(_state(entry))
        for entry in health.get("matter_nodes", []) or []:
            health_states.append(_state(entry))

    return {
        "health": _rollup(health_states) if health_states else "unknown",
        "servers": servers_total,
        "servers_connected": servers_connected,
        "node_count": len(matter_nodes),
        "unavailable_count": len(unavailable_nodes),
        "unavailable_nodes": [
            {"node_id": n["node_id"], "server_id": n["server_id"], "friendly_name": n["name"]}
            for n in unavailable_nodes
        ],
        "unstable_count": len(groups["recently_unstable"]) + len(groups["needs_attention"]),
        "needs_attention_count": len(groups["needs_attention"]),
        "diagnostics_limited_count": len(groups["diagnostics_limited"]),
        "healthy_count": len(groups["healthy"]),
        "unknown_count": len(groups["unknown"]),
        "recent_unavailable_count": recent_unavailable_count,
        "recent_recovered_count": recent_recovered_count,
        "affected_nodes_24h": affected_nodes,
        "nodes": nodes,
        "groups": groups,
    }


def _top_service_types(mdns_services: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for service in mdns_services:
        service_type = service.get("service_type")
        if isinstance(service_type, str) and service_type:
            counter[service_type] += 1
    return [
        {"service_type": service_type, "count": count}
        for service_type, count in counter.most_common(limit)
    ]


def _node_subject_id(node: dict[str, Any]) -> str | None:
    server_id = node.get("server_id")
    node_id = node.get("node_id")
    if server_id is None or node_id is None:
        return None
    return f"matter_node:{server_id}:{node_id}"


def _node_label(node: dict[str, Any]) -> str:
    name = node.get("friendly_name") or node.get("name")
    if name:
        return str(name)
    node_id = node.get("node_id")
    return f"Node {node_id}" if node_id is not None else "Matter node"


def _normalise_events(events: Any) -> list[dict[str, Any]]:
    """Coerce the raw events list/object into a bounded list of event dicts."""
    if isinstance(events, dict):
        items = events.get("events") or events.get("items")
    else:
        items = events
    if not isinstance(items, list):
        return []
    cleaned = [item for item in items if isinstance(item, dict)]
    cleaned.sort(key=lambda e: str(e.get("timestamp") or ""), reverse=True)
    return cleaned[:MAX_EVENTS]


def _slim_event(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    slim: dict[str, Any] = {
        "timestamp": event.get("timestamp"),
        "event_type": event.get("event_type"),
        "severity": event.get("severity"),
        "source": event.get("source_id") or event.get("source_type"),
        "subject_id": event.get("subject_id"),
        "subject_type": event.get("subject_type"),
        "message": event.get("message"),
    }
    if data:
        slim["data"] = redact_structure(data)
    return slim


def _events_for_subject(
    events: list[dict[str, Any]], subject_id: str | None
) -> list[dict[str, Any]]:
    if not subject_id:
        return []
    return [event for event in events if event.get("subject_id") == subject_id]


def _parse_event_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _median_seconds(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def compute_node_availability_metrics(
    node_events: list[dict[str, Any]],
    *,
    available: bool | None,
    availability_flaps_24h: Any = None,
    subscription_flaps_24h: Any = None,
    subscription_diagnostics_available: bool = False,
    now: datetime | None = None,
    window_hours: int = 24,
) -> dict[str, Any]:
    """Derive per-node command-availability churn from ThreadLens node events."""
    now = now or datetime.now(UTC)
    window_start = now - timedelta(hours=window_hours)

    transitions: list[tuple[datetime, str]] = []
    for event in node_events:
        event_type = event.get("event_type")
        if event_type not in (_NODE_UNAVAILABLE_EVENT, _NODE_RECOVERED_EVENT):
            continue
        timestamp = _parse_event_timestamp(event.get("timestamp"))
        if timestamp is None or timestamp < window_start:
            continue
        transitions.append((timestamp, event_type))
    transitions.sort(key=lambda item: item[0])

    unavailable_count = sum(
        1 for _, event_type in transitions if event_type == _NODE_UNAVAILABLE_EVENT
    )
    recovered_count = sum(1 for _, event_type in transitions if event_type == _NODE_RECOVERED_EVENT)

    offline_durations: list[float] = []
    offline_start: datetime | None = None
    for timestamp, event_type in transitions:
        if event_type == _NODE_UNAVAILABLE_EVENT:
            if offline_start is None:
                offline_start = timestamp
            continue
        if offline_start is not None:
            offline_durations.append((timestamp - offline_start).total_seconds())
            offline_start = None

    if available is False and offline_start is not None:
        offline_durations.append((now - offline_start).total_seconds())

    median_offline = _median_seconds(offline_durations)

    if subscription_diagnostics_available and isinstance(subscription_flaps_24h, int):
        cycle_count = subscription_flaps_24h
        metric_source = "subscription"
    elif isinstance(availability_flaps_24h, int):
        cycle_count = availability_flaps_24h
        metric_source = "availability"
    else:
        cycle_count = unavailable_count
        metric_source = "availability"

    return {
        "unavailable_transitions_24h": unavailable_count,
        "recovered_transitions_24h": recovered_count,
        "unsubscribe_count_24h": unavailable_count,
        "resubscribe_count_24h": recovered_count,
        "availability_cycles_24h": cycle_count,
        "availability_metric_source": metric_source,
        "subscription_diagnostics_available": bool(subscription_diagnostics_available),
        "subscription_flaps_24h": subscription_flaps_24h,
        "availability_flaps_24h": availability_flaps_24h,
        "median_offline_seconds_24h": (int(median_offline) if median_offline is not None else None),
        "offline_episodes_24h": len(offline_durations),
        "total_offline_seconds_24h": int(sum(offline_durations)),
    }


_READ_PROBE_FAILURES_WARNING_24H = 1
_READ_PROBE_FAILURES_DEGRADED_24H = 3


def _build_read_probe_block(node: dict[str, Any]) -> dict[str, Any]:
    diagnostics_available = bool(node.get("read_probe_diagnostics_available"))
    limited = bool(node.get("last_read_probe_limited"))
    failures_24h = node.get("read_probe_failures_24h")
    successes_24h = node.get("read_probe_successes_24h")
    last_ok = node.get("last_read_probe_ok")
    available = node.get("available")

    summary: str | None = None
    if diagnostics_available:
        if limited:
            summary = "Read diagnostics are limited for this node (unsupported attribute path)."
        elif available is True and last_ok is False:
            summary = "Safe read probes failed recently. This does not prove commands are failing."
        elif isinstance(failures_24h, int) and failures_24h >= _READ_PROBE_FAILURES_DEGRADED_24H:
            summary = (
                "Matter Server reports this node as available, but recent safe read probes "
                "did not receive a successful response."
            )

    return {
        "diagnostics_available": diagnostics_available,
        "last_at": node.get("last_read_probe_at"),
        "last_ok": last_ok,
        "limited": limited,
        "attribute_path": node.get("last_read_probe_attribute_path"),
        "duration_ms": node.get("last_read_probe_duration_ms"),
        "error_code": node.get("last_read_probe_error_code"),
        "failures_24h": failures_24h,
        "successes_24h": successes_24h,
        "summary": summary,
    }


def _build_ping_block(node: dict[str, Any]) -> dict[str, Any] | None:
    if not node.get("ping_diagnostics_available"):
        return None
    return {
        "diagnostics_available": True,
        "last_at": node.get("last_ping_at"),
        "last_ok": node.get("last_ping_ok"),
        "failures_24h": node.get("ping_failures_24h"),
        "successes_24h": node.get("ping_successes_24h"),
    }


def classify_matter_node(node: dict[str, Any], node_events: list[dict[str, Any]]) -> str:
    """Classify a Matter node as unavailable / recently_unstable / healthy / unknown."""
    available = node.get("available")
    recent_unavailable = sum(
        1 for e in node_events if e.get("event_type") == _NODE_UNAVAILABLE_EVENT
    )
    recent_recovered = sum(1 for e in node_events if e.get("event_type") == _NODE_RECOVERED_EVENT)
    flaps = node.get("availability_flaps_24h") or 0
    flapping = isinstance(flaps, int) and flaps > 0
    unstable = recent_unavailable > 0 or recent_recovered > 0 or flapping

    if available is False:
        return "unavailable"

    read_probe = _build_read_probe_block(node)
    if available is True and read_probe.get("diagnostics_available"):
        if read_probe.get("limited"):
            return "diagnostics_limited"
        failures = read_probe.get("failures_24h")
        if isinstance(failures, int) and failures >= _READ_PROBE_FAILURES_DEGRADED_24H:
            return "needs_attention"
        if read_probe.get("last_ok") is False:
            return "recently_unstable"

    if available is True and unstable:
        return "recently_unstable"
    if available is True:
        return "healthy"
    return "unknown"


def _coerce_node_id(value: Any) -> int | None:
    """Normalise Matter node IDs for stable dashboard keys."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.lower().startswith("0x"):
            try:
                return int(raw, 16)
            except ValueError:
                return None
        lowered = raw.lower()
        if len(raw) == 16 and all(char in "0123456789abcdef" for char in lowered):
            try:
                return int(lowered, 16)
            except ValueError:
                return None
        if raw.isdigit():
            return int(raw)
        if all(char in "0123456789abcdef" for char in lowered):
            try:
                return int(lowered, 16)
            except ValueError:
                return None
    return None


def _node_health_reason(node: dict[str, Any]) -> str | None:
    health = node.get("health")
    if isinstance(health, dict):
        reasons = health.get("reasons")
        if isinstance(reasons, list) and reasons:
            return humanize_reason(str(reasons[0]))
    return None


def _node_entry(node: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    subject_id = _node_subject_id(node)
    node_events = _events_for_subject(events, subject_id)
    recent_unavailable = sum(
        1 for e in node_events if e.get("event_type") == _NODE_UNAVAILABLE_EVENT
    )
    recent_recovered = sum(1 for e in node_events if e.get("event_type") == _NODE_RECOVERED_EVENT)
    availability_metrics = compute_node_availability_metrics(
        node_events,
        available=node.get("available"),
        availability_flaps_24h=node.get("availability_flaps_24h"),
        subscription_flaps_24h=node.get("subscription_flaps_24h"),
        subscription_diagnostics_available=bool(node.get("subscription_diagnostics_available")),
    )
    last_event_at = node_events[0].get("timestamp") if node_events else None
    classification = classify_matter_node(node, node_events)
    display_name = _node_label(node)
    node_id = _coerce_node_id(node.get("node_id"))
    health_label = _CLASSIFICATION_HEALTH_LABEL.get(classification, "Unknown")
    read_probe = _build_read_probe_block(node)
    ping_probe = _build_ping_block(node)
    return {
        "node_id": node_id,
        "server_id": node.get("server_id"),
        "subject_id": subject_id,
        "name": display_name,
        "available": node.get("available"),
        "health": health_label,
        "health_reason": _node_health_reason(node),
        "classification": classification,
        "vendor": node.get("vendor"),
        "product": node.get("product"),
        "serial": node.get("serial"),
        "firmware": node.get("firmware"),
        "last_seen": node.get("last_seen"),
        "last_unavailable": node.get("last_unavailable"),
        "last_updated": node.get("last_updated"),
        "availability_flaps_24h": node.get("availability_flaps_24h"),
        "recent_unavailable_count": recent_unavailable,
        "recent_recovered_count": recent_recovered,
        "last_event_at": last_event_at,
        "sort_key": _NODE_SORT_ORDER.get(classification, 2),
        "read_probe": read_probe,
        "ping_probe": ping_probe,
        "events": [_slim_event(e) for e in node_events],
        **availability_metrics,
    }


_NODE_SORT_ORDER = {
    "unavailable": 0,
    "needs_attention": 1,
    "recently_unstable": 2,
    "diagnostics_limited": 3,
    "unknown": 4,
    "healthy": 5,
}


def _sort_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(node: dict[str, Any]) -> tuple[int, str]:
        order = _NODE_SORT_ORDER.get(node.get("classification", "unknown"), 2)
        label = str(node.get("name") or node.get("node_id") or "").lower()
        return (order, label)

    return sorted(nodes, key=key)


def _infrastructure_unhealthy(
    otbr_entries: list[dict[str, Any]],
    matter_servers: list[dict[str, Any]],
    mdns_health: str,
    mdns_observation_degraded: Any,
    trel_display_health: str,
) -> bool:
    """True when infra (not node-local) shows a real, non-informational problem."""
    for otbr in otbr_entries:
        if not otbr.get("reachable"):
            return True
        if not otbr.get("effective_state") and not otbr.get("mismatch_reconciled"):
            return True
    if matter_servers and not any(server.get("connected") for server in matter_servers):
        return True
    if mdns_observation_degraded:
        return True
    if _SEVERITY.get(mdns_health, 1) >= _SEVERITY["degraded"]:
        return True
    if _SEVERITY.get(trel_display_health, 1) >= _SEVERITY["degraded"]:
        return True
    return False


def _incident_infrastructure(
    *,
    otbr_entries: list[dict[str, Any]],
    matter_servers: list[dict[str, Any]],
    mdns_health: str,
    trel_display_health: str,
) -> dict[str, str]:
    otbr_states = [entry.get("display_health", "unknown") for entry in otbr_entries]
    matter_connected = any(server.get("connected") for server in matter_servers)
    return {
        "otbr": _rollup(otbr_states) if otbr_states else "unknown",
        "matter": "healthy" if matter_connected or not matter_servers else "degraded",
        "mdns": mdns_health,
        "trel": trel_display_health,
    }


def build_incident_summary(
    *,
    nodes: list[dict[str, Any]],
    otbr_entries: list[dict[str, Any]],
    matter_servers: list[dict[str, Any]],
    mdns_health: str,
    mdns_observation_degraded: Any,
    trel_display_health: str,
    has_events: bool,
) -> dict[str, Any]:
    """Compose a conservative incident assessment driven by node health + infra."""
    unavailable = [n for n in nodes if n.get("classification") == "unavailable"]
    needs_attention = [n for n in nodes if n.get("classification") == "needs_attention"]
    unstable = [n for n in nodes if n.get("classification") == "recently_unstable"]
    infra_unhealthy = _infrastructure_unhealthy(
        otbr_entries,
        matter_servers,
        mdns_health,
        mdns_observation_degraded,
        trel_display_health,
    )
    infrastructure = _incident_infrastructure(
        otbr_entries=otbr_entries,
        matter_servers=matter_servers,
        mdns_health=mdns_health,
        trel_display_health=trel_display_health,
    )

    def _affected_nodes(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "node_id": n.get("node_id"),
                "name": n.get("name"),
                "health": n.get("health"),
                "reason": n.get("health_reason"),
            }
            for n in targets
        ]

    if not nodes and not otbr_entries and not has_events:
        headline = "Not enough data to assess Matter-over-Thread health."
        detail = "ThreadLens has not reported nodes or events yet."
        return {
            "state": "unknown",
            "title": headline,
            "summary": detail,
            "headline": headline,
            "detail": detail,
            "affected_nodes": [],
            "affected_node_names": [],
            "infrastructure": infrastructure,
            "infrastructure_unhealthy": infra_unhealthy,
        }

    if unavailable or infra_unhealthy:
        names = [n["name"] for n in unavailable]
        if unavailable:
            headline = f"{len(unavailable)} Matter node(s) currently unavailable."
        else:
            headline = "Infrastructure issue detected."
        detail = (
            "Matter nodes are currently unavailable. Compare affected nodes and "
            "infrastructure events to narrow whether this is device-local or "
            "network-wide."
            if unavailable
            else "An infrastructure component (OTBR, Matter server, mDNS, or TREL) "
            "looks degraded. Review the relevant sections below."
        )
        return {
            "state": "incident",
            "title": headline,
            "summary": detail,
            "headline": headline,
            "detail": detail,
            "affected_nodes": _affected_nodes(unavailable),
            "affected_node_names": names,
            "infrastructure": infrastructure,
            "infrastructure_unhealthy": infra_unhealthy,
        }

    if needs_attention and not unavailable:
        names = [n["name"] for n in needs_attention]
        headline = f"{len(needs_attention)} Matter node(s) need attention: {', '.join(names)}."
        detail = (
            "Matter Server reports these nodes as available, but recent safe read probes "
            "did not receive a successful response. This does not prove commands are failing."
        )
        return {
            "state": "watch",
            "title": headline,
            "summary": detail,
            "headline": headline,
            "detail": detail,
            "affected_nodes": _affected_nodes(needs_attention),
            "affected_node_names": names,
            "infrastructure": infrastructure,
            "infrastructure_unhealthy": infra_unhealthy,
        }

    if unstable:
        names = [n["name"] for n in unstable]
        headline = f"{len(unstable)} Matter node(s) recently unstable: {', '.join(names)}."
        detail = (
            "No current outage, but recent Matter node changes were observed. Review affected "
            "nodes if symptoms continue."
        )
        return {
            "state": "watch",
            "title": headline,
            "summary": detail,
            "headline": headline,
            "detail": detail,
            "affected_nodes": _affected_nodes(unstable),
            "affected_node_names": names,
            "infrastructure": infrastructure,
            "infrastructure_unhealthy": infra_unhealthy,
        }

    if not nodes:
        headline = "No Matter nodes reported yet."
        detail = "ThreadLens has not reported any Matter nodes."
        return {
            "state": "unknown",
            "title": headline,
            "summary": detail,
            "headline": headline,
            "detail": detail,
            "affected_nodes": [],
            "affected_node_names": [],
            "infrastructure": infrastructure,
            "infrastructure_unhealthy": infra_unhealthy,
        }

    headline = "All Matter nodes are currently available."
    detail = (
        "No current Matter-over-Thread failure detected. OTBRs and Matter nodes "
        "appear available, and no recent node instability was observed."
    )
    return {
        "state": "ok",
        "title": headline,
        "summary": detail,
        "headline": headline,
        "detail": detail,
        "affected_nodes": [],
        "affected_node_names": [],
        "infrastructure": infrastructure,
        "infrastructure_unhealthy": infra_unhealthy,
    }


def build_node_detail(
    *,
    node: dict[str, Any],
    all_nodes: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a node detail payload with recent events and a conservative assessment."""
    subject_id = node.get("subject_id")
    node_events = _events_for_subject(events, subject_id)
    this_unstable = node.get("recent_unavailable_count", 0) or node.get("recent_recovered_count", 0)

    other_unstable = [
        n
        for n in all_nodes
        if n.get("subject_id") != subject_id
        and (n.get("recent_unavailable_count") or n.get("recent_recovered_count"))
    ]
    infra_events = [
        e
        for e in events
        if isinstance(e.get("event_type"), str) and e["event_type"] in _INFRA_DEGRADED_EVENTS
    ]

    if not node_events and not this_unstable:
        assessment_kind = "insufficient"
        assessment = (
            "There is not enough recent event history to classify this as "
            "device-local or network-wide."
        )
    elif other_unstable:
        assessment_kind = "group"
        assessment = (
            "Multiple Matter nodes changed state around the same time. This may "
            "indicate a wider Matter/Thread network issue."
        )
    elif infra_events:
        assessment_kind = "infrastructure"
        assessment = (
            "Infrastructure events were observed near this node change. Review OTBR, "
            "Matter server, mDNS, and TREL sections."
        )
    elif this_unstable:
        assessment_kind = "individual"
        assessment = (
            "This looks isolated to this node. ThreadLens does not see a wider "
            "Matter/Thread infrastructure issue at the same time."
        )
    else:
        assessment_kind = "insufficient"
        assessment = (
            "There is not enough recent event history to classify this as "
            "device-local or network-wide."
        )

    return {
        "node": node,
        "events": [_slim_event(e) for e in node_events],
        "assessment_kind": assessment_kind,
        "assessment": assessment,
    }


def compute_health_summary(
    *,
    connected: bool,
    health: dict[str, Any] | None,
    otbrs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the shared health view used by the dashboard payload."""
    otbrs = otbrs or []
    overall = health.get("overall") if isinstance(health, dict) else None
    environment = health.get("environment") if isinstance(health, dict) else None

    prominent_reasons, all_reasons = _combined_reasons_filtered(otbrs, overall, environment)
    prominent_codes = {reason["code"] for reason in prominent_reasons}
    informational_reasons = [
        reason for reason in all_reasons if reason["code"] not in prominent_codes
    ]

    overall_raw = _state(overall) if connected else "unknown"
    environment_raw = _state(environment) if connected else "unknown"
    overall_display = overall_raw
    environment_display = environment_raw
    if connected and not prominent_reasons:
        if overall_raw == "warning":
            overall_display = "healthy"
        if environment_raw == "warning":
            environment_display = "healthy"

    return {
        "overall_health": overall_display,
        "environment_health": environment_display,
        "overall_health_raw": overall_raw,
        "environment_health_raw": environment_raw,
        "reasons": prominent_reasons,
        "reasons_all": all_reasons,
        "informational_reasons": informational_reasons,
    }


def build_dashboard_payload(
    *,
    connected: bool,
    last_update: str | None = None,
    version: dict[str, Any] | None = None,
    status: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
    otbrs: list[dict[str, Any]] | None = None,
    networks: list[dict[str, Any]] | None = None,
    matter_servers: list[dict[str, Any]] | None = None,
    matter_nodes: list[dict[str, Any]] | None = None,
    mdns_services: list[dict[str, Any]] | None = None,
    trel_services: list[dict[str, Any]] | None = None,
    events: Any = None,
    event_window: str = DEFAULT_EVENT_WINDOW,
    report_urls: dict[str, str] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Compose the unified dashboard payload from ThreadLens Core observations."""
    otbrs = otbrs or []
    networks = networks or []
    matter_servers = matter_servers or []
    matter_nodes = matter_nodes or []
    mdns_services = mdns_services or []
    trel_services = trel_services or []
    report_urls = report_urls or DASHBOARD_REPORT_URLS
    event_list = _normalise_events(events)
    relevant_events = [e for e in event_list if e.get("event_type") in _RELEVANT_EVENT_TYPES]

    version_str = version.get("version") if isinstance(version, dict) else None

    mdns_health = health.get("mdns") if isinstance(health, dict) else None
    trel_health = health.get("trel") if isinstance(health, dict) else None

    collectors = status.get("collectors") if isinstance(status, dict) else None
    collectors = collectors if isinstance(collectors, dict) else {}
    mqtt_status = collectors.get("mqtt") if isinstance(collectors.get("mqtt"), dict) else None
    mdns_collector = collectors.get("mdns") if isinstance(collectors.get("mdns"), dict) else {}

    reports_status = status.get("reports") if isinstance(status, dict) else None
    last_generated_at = (
        reports_status.get("last_generated_at") if isinstance(reports_status, dict) else None
    )

    health_networks = health.get("thread_networks") if isinstance(health, dict) else None
    health_by_pan: dict[str, dict[str, Any]] = {}
    if isinstance(health_networks, list):
        for entry in health_networks:
            if isinstance(entry, dict) and entry.get("ext_pan_id"):
                health_by_pan[str(entry["ext_pan_id"])] = entry

    foreign_trel = sum(1 for service in trel_services if service.get("is_foreign"))

    otbr_entries = [_otbr_entry(item) for item in otbrs if isinstance(item, dict)]
    health_summary = compute_health_summary(
        connected=connected,
        health=health,
        otbrs=otbrs,
    )
    prominent_reasons = health_summary["reasons"]
    all_reasons = health_summary["reasons_all"]
    overall_display = health_summary["overall_health"]
    environment_display = health_summary["environment_health"]
    overall_raw = health_summary["overall_health_raw"]
    environment_raw = health_summary["environment_health_raw"]
    informational_reasons = health_summary["informational_reasons"]

    trel_state = _state(trel_health)
    trel_reason_codes = _reasons(trel_health)
    trel_real_reasons = [c for c in trel_reason_codes if c not in _INFO_REASON_CODES]
    trel_display_health = trel_state
    if not trel_real_reasons and trel_state == "warning":
        trel_display_health = "healthy"

    matter_section = _matter_section(matter_servers, matter_nodes, health, relevant_events)
    mdns_state = _state(mdns_health)
    mdns_observation_degraded = mdns_collector.get("observation_degraded")

    incident = build_incident_summary(
        nodes=matter_section["nodes"],
        otbr_entries=otbr_entries,
        matter_servers=matter_servers,
        mdns_health=mdns_state,
        mdns_observation_degraded=mdns_observation_degraded,
        trel_display_health=trel_display_health,
        has_events=bool(relevant_events),
    )

    mqtt_payload: dict[str, Any] | None = None
    if mqtt_status is not None:
        mqtt_payload = {
            "enabled": mqtt_status.get("enabled"),
            "connected": mqtt_status.get("connected"),
            "homeassistant_discovery_enabled": mqtt_status.get("homeassistant_discovery_enabled"),
            "last_publish_at": mqtt_status.get("last_publish_at"),
            "last_error": mqtt_status.get("last_error"),
        }

    trel_informational = bool(foreign_trel) and not trel_real_reasons
    return {
        "threadlens": {
            "version": version_str,
            "api_connected": bool(connected),
            "last_update": last_update,
            "overall_health": overall_display,
            "environment_health": environment_display,
            "overall_health_raw": overall_raw,
            "environment_health_raw": environment_raw,
            "reasons": prominent_reasons,
            "reasons_all": all_reasons,
            "informational_reasons": informational_reasons,
        },
        "incident": incident,
        "otbrs": otbr_entries,
        "networks": [
            _network_entry(item, health_by_pan) for item in networks if isinstance(item, dict)
        ],
        "matter": matter_section,
        "mdns": {
            "health": mdns_state,
            "health_raw": mdns_state,
            "service_count": len(mdns_services),
            "observation_degraded": mdns_observation_degraded,
            "top_service_types": _top_service_types(mdns_services),
        },
        "trel": {
            "health": trel_display_health,
            "health_raw": trel_state,
            "informational": trel_informational,
            "service_count": len(trel_services),
            "foreign_service_count": foreign_trel,
            "reasons": friendly_reasons(trel_real_reasons),
            "reasons_all": friendly_reasons(trel_reason_codes),
            "info": {
                "foreign_trel_observed": foreign_trel > 0,
                "message": FOREIGN_TREL_INFO_MESSAGE if trel_informational else None,
            },
        },
        "events": {
            "window": event_window,
            "items": [_slim_event(e) for e in relevant_events],
        },
        "mqtt": mqtt_payload,
        "report": {
            "report_url": report_urls.get("yaml"),
            "report_url_json": report_urls.get("json"),
            "last_generated_at": last_generated_at,
        },
        "error": error,
    }


def build_disconnected_payload(
    *,
    version: dict[str, Any] | None = None,
    last_update: str | None = None,
    report_urls: dict[str, str] | None = None,
    error: str = "Cannot reach the ThreadLens API",
) -> dict[str, Any]:
    """Return a structured payload when the API is unavailable."""
    return build_dashboard_payload(
        connected=False,
        last_update=last_update,
        version=version,
        report_urls=report_urls,
        error=error,
    )
