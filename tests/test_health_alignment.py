"""Ensure dashboard health semantics stay aligned with Core health output."""

from __future__ import annotations

from threadlens.server.dashboard import build_dashboard_payload, compute_health_summary

RECONCILED_HEALTH = {
    "overall": {
        "state": "warning",
        "reasons": ["otbr_rest_endpoint_mismatch", "foreign_trel_services_observed"],
    },
    "environment": {
        "state": "warning",
        "reasons": ["otbr_rest_endpoint_mismatch", "foreign_trel_services_observed"],
    },
}

RECONCILED_OTBRS = [
    {
        "id": "study",
        "reachable": True,
        "role": "leader",
        "thread_state": "active",
        "thread_state_source": "legacy_node",
        "rest_endpoint_mismatch": True,
        "json_api_thread_state": "disabled",
        "legacy_node_thread_state": "active",
    }
]


def test_compute_health_summary_downgrades_informational_only_warnings():
    summary = compute_health_summary(
        connected=True,
        health=RECONCILED_HEALTH,
        otbrs=RECONCILED_OTBRS,
    )
    assert summary["overall_health"] == "healthy"
    assert summary["overall_health_raw"] == "warning"
    assert summary["reasons"] == []
    assert any(
        r["code"] == "foreign_trel_services_observed" for r in summary["informational_reasons"]
    )


def test_dashboard_payload_and_compute_health_summary_agree():
    payload = build_dashboard_payload(
        connected=True,
        version={"tool": "ThreadLens", "version": "0.2.5"},
        status={"collectors": {}},
        health=RECONCILED_HEALTH,
        otbrs=RECONCILED_OTBRS,
    )
    summary = compute_health_summary(
        connected=True,
        health=RECONCILED_HEALTH,
        otbrs=RECONCILED_OTBRS,
    )
    tl = payload["threadlens"]
    assert tl["overall_health"] == summary["overall_health"] == "healthy"
    assert tl["overall_health_raw"] == summary["overall_health_raw"] == "warning"
    assert tl["informational_reasons"] == summary["informational_reasons"]
