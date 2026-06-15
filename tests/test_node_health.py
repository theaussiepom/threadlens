"""Tests for Matter node health, incident summary, and node-detail assessment."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from threadlens.server import dashboard as dashboard_module
from threadlens.server.dashboard import (
    build_dashboard_payload,
    build_node_detail,
    classify_matter_node,
)

VERSION = {"tool": "ThreadLens", "version": "0.2.16"}
STATUS = {
    "collectors": {"mdns": {"observation_degraded": False}},
    "reports": {"last_generated_at": None},
}
HEALTHY_HEALTH = {
    "overall": {"state": "healthy", "reasons": []},
    "environment": {"state": "healthy", "reasons": []},
    "mdns": {"state": "healthy", "reasons": []},
    "trel": {"state": "healthy", "reasons": []},
}

SERVER = "study_matter"


def _recent_iso(*, hours_ago: float = 0, minutes_ago: float = 0) -> str:
    t = datetime.now(UTC) - timedelta(hours=hours_ago, minutes=minutes_ago)
    return t.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _subj(node_id: int) -> str:
    return f"matter_node:{SERVER}:{node_id}"


def _event(node_id: int, event_type: str, ts: str, severity: str = "warning") -> dict:
    return {
        "subject_id": _subj(node_id),
        "subject_type": "matter_node",
        "source_id": SERVER,
        "event_type": event_type,
        "timestamp": ts,
        "severity": severity,
        "message": f"node {node_id} {event_type}",
    }


def _node(node_id: int, available, **extra) -> dict:
    base = {
        "node_id": node_id,
        "server_id": SERVER,
        "available": available,
        "friendly_name": f"Node {node_id}",
    }
    base.update(extra)
    return base


HEALTHY_OTBR = [
    {
        "id": "study",
        "name": "Study OTBR",
        "reachable": True,
        "health": {"state": "healthy", "reasons": []},
        "thread_state": "leader",
        "role": "leader",
        "rest_endpoint_mismatch": False,
    }
]


def _payload(nodes, events=None, otbrs=None, servers=None, health=None):
    return build_dashboard_payload(
        connected=True,
        version=VERSION,
        status=STATUS,
        health=health or HEALTHY_HEALTH,
        otbrs=otbrs if otbrs is not None else HEALTHY_OTBR,
        matter_servers=servers if servers is not None else [{"id": SERVER, "connected": True}],
        matter_nodes=nodes,
        events=events or [],
    )


def test_classify_unavailable():
    assert classify_matter_node(_node(1, False), []) == "unavailable"


def test_classify_recently_unstable_via_events():
    node = _node(1, True)
    events = [_event(1, "matter_node.recovered", "2026-06-14T01:00:00Z")]
    assert classify_matter_node(node, events) == "recently_unstable"


def test_classify_recently_unstable_via_flaps():
    node = _node(1, True, availability_flaps_24h=2)
    assert classify_matter_node(node, []) == "recently_unstable"


def test_classify_healthy():
    node = _node(1, True, availability_flaps_24h=0)
    assert classify_matter_node(node, []) == "healthy"


def test_classify_unknown():
    assert classify_matter_node(_node(1, None), []) == "unknown"


def test_unavailable_node_classifies_as_unavailable():
    payload = _payload([_node(2, False)])
    node = payload["matter"]["nodes"][0]
    assert node["classification"] == "unavailable"
    assert node["health"] == "Unavailable"
    assert payload["matter"]["unavailable_count"] == 1


def test_recovered_node_flagged_when_available():
    events = [_event(5, "matter_node.recovered", "2026-06-14T02:00:00Z")]
    payload = _payload([_node(5, True)], events=events)
    node = payload["matter"]["nodes"][0]
    assert node["classification"] == "recently_unstable"
    assert node["health"] == "Recently unstable"
    assert node["recent_recovered_count"] == 1
    assert payload["matter"]["unstable_count"] == 1


def test_healthy_node_classified_healthy():
    payload = _payload([_node(7, True, availability_flaps_24h=0)])
    node = payload["matter"]["nodes"][0]
    assert node["classification"] == "healthy"
    assert node["health"] == "Healthy"
    assert payload["matter"]["healthy_count"] == 1


def test_incident_when_node_unavailable():
    payload = _payload([_node(2, False), _node(3, True)])
    assert payload["incident"]["state"] == "incident"
    assert "Node 2" in payload["incident"]["affected_node_names"]


def test_watch_when_recently_unstable_but_available():
    events = [_event(4, "matter_node.recovered", "2026-06-14T02:00:00Z")]
    payload = _payload([_node(4, True), _node(5, True)], events=events)
    assert payload["incident"]["state"] == "watch"
    assert "Node 4" in payload["incident"]["affected_node_names"]


def test_ok_when_all_available_and_infra_healthy():
    payload = _payload([_node(1, True), _node(2, True)])
    assert payload["incident"]["state"] == "ok"
    assert payload["incident"]["affected_node_names"] == []


def test_node_sorting_puts_unhealthy_first():
    nodes = [
        _node(10, True, availability_flaps_24h=0),
        _node(11, None),
        _node(12, False),
        _node(13, True, availability_flaps_24h=3),
    ]
    payload = _payload(nodes)
    order = [n["classification"] for n in payload["matter"]["nodes"]]
    assert order == ["unavailable", "recently_unstable", "unknown", "healthy"]


def test_individual_node_assessment():
    events = [_event(1, "matter_node.recovered", "2026-06-14T02:00:00Z")]
    payload = _payload([_node(1, True), _node(2, True)], events=events)
    nodes = payload["matter"]["nodes"]
    target = next(n for n in nodes if n["node_id"] == 1)
    detail = build_node_detail(node=target, all_nodes=nodes, events=payload["events"]["items"])
    assert detail["assessment_kind"] == "individual"
    assert "isolated to this node" in detail["assessment"]


def test_group_network_assessment():
    events = [
        _event(1, "matter_node.recovered", "2026-06-14T02:00:00Z"),
        _event(2, "matter_node.recovered", "2026-06-14T02:01:00Z"),
    ]
    payload = _payload([_node(1, True), _node(2, True)], events=events)
    nodes = payload["matter"]["nodes"]
    target = next(n for n in nodes if n["node_id"] == 1)
    detail = build_node_detail(node=target, all_nodes=nodes, events=payload["events"]["items"])
    assert detail["assessment_kind"] == "group"
    assert "Multiple Matter nodes" in detail["assessment"]


def test_node_detail_includes_metadata_and_events():
    events = [_event(9, "matter_node.unavailable", "2026-06-14T03:00:00Z")]
    payload = _payload(
        [_node(9, True, vendor="Dendo Systems", product="Matter Shade")], events=events
    )
    target = payload["matter"]["nodes"][0]
    detail = build_node_detail(
        node=target, all_nodes=payload["matter"]["nodes"], events=payload["events"]["items"]
    )
    assert detail["node"]["vendor"] == "Dendo Systems"
    assert detail["node"]["product"] == "Matter Shade"
    assert any(e["event_type"] == "matter_node.unavailable" for e in detail["events"])


def test_events_payload_bounded_and_windowed():
    payload = _payload([_node(1, True)], events=[])
    assert payload["events"]["window"] == "24h"
    assert payload["events"]["items"] == []


def test_node_availability_metrics_median_offline():
    compute_node_availability_metrics = dashboard_module.compute_node_availability_metrics
    now = datetime(2026, 6, 14, 12, 0, 0, tzinfo=UTC)
    events = [
        _event(1, "matter_node.unavailable", "2026-06-14T10:00:00Z"),
        _event(1, "matter_node.recovered", "2026-06-14T10:10:00Z"),
        _event(1, "matter_node.unavailable", "2026-06-14T11:00:00Z"),
        _event(1, "matter_node.recovered", "2026-06-14T11:30:00Z"),
    ]
    metrics = compute_node_availability_metrics(
        events,
        available=True,
        availability_flaps_24h=2,
        now=now,
    )
    assert metrics["unsubscribe_count_24h"] == 2
    assert metrics["resubscribe_count_24h"] == 2
    assert metrics["availability_cycles_24h"] == 2
    assert metrics["median_offline_seconds_24h"] == 1200
    assert metrics["total_offline_seconds_24h"] == 2400


def test_node_availability_metrics_include_ongoing_outage():
    compute_node_availability_metrics = dashboard_module.compute_node_availability_metrics
    now = datetime(2026, 6, 14, 12, 0, 0, tzinfo=UTC)
    events = [_event(2, "matter_node.unavailable", "2026-06-14T11:30:00Z")]
    metrics = compute_node_availability_metrics(
        events,
        available=False,
        now=now,
    )
    assert metrics["unsubscribe_count_24h"] == 1
    assert metrics["resubscribe_count_24h"] == 0
    assert metrics["median_offline_seconds_24h"] == 1800
    assert metrics["offline_episodes_24h"] == 1


def test_payload_includes_availability_metrics_on_nodes():
    events = [
        _event(3, "matter_node.unavailable", _recent_iso(minutes_ago=30)),
        _event(3, "matter_node.recovered", _recent_iso(minutes_ago=25)),
    ]
    payload = _payload(
        [_node(3, True, availability_flaps_24h=1)],
        events=events,
    )
    node = payload["matter"]["nodes"][0]
    assert node["resubscribe_count_24h"] == 1
    assert node["unsubscribe_count_24h"] == 1
    assert node["median_offline_seconds_24h"] == 300
