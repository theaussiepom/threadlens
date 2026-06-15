"""Dashboard read probe integration tests."""

from __future__ import annotations

from threadlens.server.dashboard import (
    _build_read_probe_block,
    _node_entry,
    classify_matter_node,
)


def _node(**overrides) -> dict:
    base = {
        "node_id": 24,
        "server_id": "study",
        "available": True,
        "friendly_name": "Living Blind 3",
        "read_probe_diagnostics_available": False,
    }
    base.update(overrides)
    return base


def test_classify_matter_node_unchanged_without_probe_diagnostics() -> None:
    assert classify_matter_node(_node(), []) == "healthy"


def test_classify_read_probe_failure_as_recently_unstable() -> None:
    node = _node(
        read_probe_diagnostics_available=True,
        last_read_probe_ok=False,
        read_probe_failures_24h=1,
    )
    assert classify_matter_node(node, []) == "recently_unstable"


def test_classify_repeated_read_probe_failures_as_needs_attention() -> None:
    node = _node(
        read_probe_diagnostics_available=True,
        last_read_probe_ok=False,
        read_probe_failures_24h=3,
    )
    assert classify_matter_node(node, []) == "needs_attention"


def test_classify_unsupported_read_probe_as_diagnostics_limited() -> None:
    node = _node(
        read_probe_diagnostics_available=True,
        last_read_probe_ok=None,
        last_read_probe_limited=True,
    )
    assert classify_matter_node(node, []) == "diagnostics_limited"


def test_unavailable_remains_dominant_over_probe_failure() -> None:
    node = _node(
        available=False,
        read_probe_diagnostics_available=True,
        last_read_probe_ok=False,
        read_probe_failures_24h=5,
    )
    assert classify_matter_node(node, []) == "unavailable"


def test_read_probe_block_exposes_friendly_overview_labels() -> None:
    ok_block = _build_read_probe_block(
        _node(
            read_probe_diagnostics_available=True,
            last_read_probe_ok=True,
            last_probe_label="Basic read check",
        )
    )
    assert ok_block["overview_label"] == "Read checks OK"
    assert ok_block["probe_label"] == "Basic read check"

    limited_block = _build_read_probe_block(
        _node(
            read_probe_diagnostics_available=True,
            last_read_probe_limited=True,
            last_probe_label="Window covering read check",
        )
    )
    assert limited_block["overview_label"] == "Read checks unavailable"
    assert "unsupported attribute path" not in (limited_block["summary"] or "").lower()


def test_node_entry_includes_read_probe_block() -> None:
    node = _node(
        read_probe_diagnostics_available=True,
        last_read_probe_ok=False,
        last_read_probe_attribute_path="0/40/5",
        last_read_probe_duration_ms=842,
        read_probe_failures_24h=2,
        read_probe_successes_24h=5,
    )
    entry = _node_entry(node, [])
    assert entry["read_probe"]["diagnostics_available"] is True
    assert entry["read_probe"]["last_ok"] is False
    assert entry["read_probe"]["attribute_path"] == "0/40/5"
    assert "read probe" in entry["read_probe"]["summary"].lower()
    assert "command failed" not in entry["read_probe"]["summary"].lower()


def test_node_entry_exposes_classification_reason_for_read_probe_unstable() -> None:
    node = _node(
        read_probe_diagnostics_available=True,
        last_read_probe_ok=False,
        read_probe_failures_24h=2,
        health={"state": "warning", "reasons": ["matter_node_read_probe_failed"]},
        thread_extended_address="3ec12f62981d06e3",
        thread_ipv6_address="fd22:c1b2:8661:1:a87b:2dbb:e992:5426",
    )
    entry = _node_entry(node, [], otbr_ids=["study", "lounge"])
    assert entry["classification"] == "recently_unstable"
    assert entry["classification_reason"] == "Read probe issue"
    assert entry["health_reason"] == "Safe read probe failed recently"
    assert entry["otbr_ids"] == ["study", "lounge"]
    assert entry["thread_extended_address"] == "3ec12f62981d06e3"
    assert entry["thread_ipv6_address"] == "fd22:c1b2:8661:1:a87b:2dbb:e992:5426"
    assert entry["thread_identity_available"] is True


def test_incident_summary_explains_read_probe_only_unstable() -> None:
    from threadlens.server.dashboard import build_incident_summary

    nodes = [
        {
            "name": "Living Blind 3",
            "classification": "recently_unstable",
            "classification_reason": "Read probe issue",
            "recent_unavailable_count": 0,
            "recent_recovered_count": 0,
            "availability_flaps_24h": 0,
            "read_probe": {
                "diagnostics_available": True,
                "last_ok": False,
                "limited": False,
                "failures_24h": 2,
            },
        }
    ]
    incident = build_incident_summary(
        nodes=nodes,
        otbr_entries=[],
        matter_servers=[{"connected": True}],
        mdns_health="healthy",
        mdns_observation_degraded=False,
        trel_display_health="healthy",
        has_events=False,
    )
    assert incident["state"] == "watch"
    assert "safe read probes" in incident["detail"].lower()
    assert incident["affected_nodes"][0]["reason"] == "Read probe issue"


def test_matter_section_exposes_health_reasons() -> None:
    from threadlens.server.dashboard import build_dashboard_payload

    payload = build_dashboard_payload(
        connected=True,
        health={
            "overall": {"state": "warning", "reasons": ["matter_nodes_unavailable"]},
            "matter_servers": [
                {"id": "m1", "state": "warning", "reasons": ["matter_nodes_unavailable"]},
            ],
            "matter_nodes": [
                {
                    "node_id": 1,
                    "state": "degraded",
                    "reasons": ["matter_node_unavailable"],
                }
            ],
        },
        matter_servers=[{"id": "m1", "connected": True}],
        matter_nodes=[{"node_id": 1, "server_id": "m1", "available": False}],
    )
    reasons = payload["matter"]["reasons"]
    assert any(r["code"] == "matter_nodes_unavailable" for r in reasons)
    assert any(r["code"] == "matter_node_unavailable" for r in payload["matter"]["reasons_all"])


def test_build_node_detail_for_diagnostics_limited() -> None:
    from threadlens.server.dashboard import build_node_detail

    node = {
        "subject_id": "matter_node:study:24",
        "classification": "diagnostics_limited",
        "recent_unavailable_count": 0,
        "recent_recovered_count": 0,
        "read_probe": {
            "limited": True,
            "summary": (
                "ThreadLens tried several read-only Matter attributes but could not find "
                "one this device accepts."
            ),
        },
    }
    detail = build_node_detail(node=node, all_nodes=[node], events=[])
    assert detail["assessment_kind"] == "individual"
    assert "read-only Matter attributes" in detail["assessment"]


def test_read_probe_summary_uses_careful_wording() -> None:
    block = _build_read_probe_block(
        {
            "available": True,
            "read_probe_diagnostics_available": True,
            "last_read_probe_ok": False,
            "read_probe_failures_24h": 1,
        }
    )
    assert block["summary"] is not None
    assert "does not prove commands are failing" in block["summary"]
