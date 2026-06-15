"""Tests for the pure dashboard aggregation logic."""

from __future__ import annotations

from threadlens.server.dashboard import (
    DASHBOARD_REPORT_URLS,
    build_dashboard_payload,
    build_disconnected_payload,
    humanize_reason,
)

VERSION = {"tool": "ThreadLens", "version": "0.2.18"}

HEALTHY_HEALTH = {
    "overall": {"state": "healthy", "reasons": []},
    "environment": {"state": "healthy", "reasons": []},
    "mdns": {"state": "healthy", "reasons": []},
    "trel": {"state": "healthy", "reasons": []},
    "matter_servers": [{"id": "m1", "state": "healthy", "reasons": []}],
    "matter_nodes": [{"node_id": 1, "state": "healthy", "reasons": []}],
    "thread_networks": [{"ext_pan_id": "ABCD", "state": "healthy"}],
}

STATUS = {
    "collectors": {
        "mqtt": {
            "enabled": True,
            "connected": True,
            "homeassistant_discovery_enabled": True,
            "last_publish_at": "2026-06-14T12:00:00+00:00",
            "last_error": None,
        },
        "mdns": {"observer_running": True, "observation_degraded": False},
    },
    "reports": {"last_generated_at": "2026-06-14T12:00:00+00:00"},
}


def _healthy_payload():
    return build_dashboard_payload(
        connected=True,
        last_update="2026-06-14T12:00:00+00:00",
        version=VERSION,
        status=STATUS,
        health=HEALTHY_HEALTH,
        otbrs=[
            {
                "id": "otbr1",
                "name": "Study OTBR",
                "reachable": True,
                "health": {"state": "healthy", "reasons": []},
                "thread_state": "active",
                "role": "leader",
                "network_name": "MyThread",
                "rloc16": "0x4400",
                "ext_pan_id": "ABCD",
                "thread_state_source": "json_api",
                "rest_endpoint_mismatch": False,
            }
        ],
        networks=[
            {
                "ext_pan_id": "ABCD",
                "name": "MyThread",
                "channel": 15,
                "pan_id": "0x1234",
                "border_router_count": 1,
                "classification": "primary",
            }
        ],
        matter_servers=[{"id": "m1", "name": "Matter", "connected": True}],
        matter_nodes=[
            {"node_id": 1, "server_id": "m1", "available": True, "friendly_name": "Light"}
        ],
        mdns_services=[
            {"service_type": "_matter._tcp.local.", "service_id": "a"},
            {"service_type": "_matter._tcp.local.", "service_id": "b"},
            {"service_type": "_meshcop._udp.local.", "service_id": "c"},
        ],
        trel_services=[{"service_id": "t1", "is_foreign": False}],
    )


def test_healthy_payload_shape():
    payload = _healthy_payload()
    assert payload["threadlens"]["api_connected"] is True
    assert payload["threadlens"]["version"] == "0.2.18"
    assert payload["threadlens"]["overall_health"] == "healthy"
    assert payload["threadlens"]["environment_health"] == "healthy"
    assert payload["threadlens"]["reasons"] == []
    assert payload["error"] is None

    assert len(payload["otbrs"]) == 1
    assert payload["otbrs"][0]["extended_pan_id"] == "ABCD"
    assert payload["otbrs"][0]["rest_endpoint_mismatch"] is False

    assert len(payload["networks"]) == 1
    assert payload["networks"][0]["classification"] == "primary"
    assert payload["networks"][0]["health"] == "healthy"

    assert payload["matter"]["servers"] == 1
    assert payload["matter"]["servers_connected"] == 1
    assert payload["matter"]["node_count"] == 1
    assert payload["matter"]["unavailable_count"] == 0
    assert payload["matter"]["health"] == "healthy"

    assert payload["mdns"]["service_count"] == 3
    assert payload["mdns"]["top_service_types"][0] == {
        "service_type": "_matter._tcp.local.",
        "count": 2,
    }
    assert payload["trel"]["service_count"] == 1
    assert payload["trel"]["foreign_service_count"] == 0

    assert payload["mqtt"]["connected"] is True
    assert payload["report"]["report_url"] == "api/v1/report.yaml"
    assert payload["report"]["report_url_json"] == "api/v1/report.json"
    assert payload["report"]["last_generated_at"] == "2026-06-14T12:00:00+00:00"


def test_dashboard_payload_includes_expected_top_level_sections():
    payload = _healthy_payload()
    assert set(payload.keys()) >= {
        "threadlens",
        "incident",
        "otbrs",
        "networks",
        "matter",
        "mdns",
        "trel",
        "events",
        "report",
    }


def test_warning_reasons_are_friendly():
    health = {
        "overall": {"state": "warning", "reasons": ["mdns_service_flapping_degraded"]},
        "environment": {
            "state": "warning",
            "reasons": ["foreign_trel_services_observed"],
        },
    }
    payload = build_dashboard_payload(
        connected=True,
        version=VERSION,
        status=STATUS,
        health=health,
    )
    assert payload["threadlens"]["overall_health"] == "warning"
    labels = {r["label"] for r in payload["threadlens"]["reasons"]}
    assert "mDNS service add/remove instability" in labels
    assert "Other Thread/TREL services visible" not in labels
    codes = {r["code"] for r in payload["threadlens"]["reasons"]}
    assert "mdns_service_flapping_degraded" in codes
    all_codes = {r["code"] for r in payload["threadlens"]["reasons_all"]}
    assert "foreign_trel_services_observed" in all_codes


def test_otbr_endpoint_mismatch_reconciled_hides_prominent_warning():
    health = {
        "overall": {
            "state": "warning",
            "reasons": ["otbr_rest_endpoint_mismatch", "foreign_trel_services_observed"],
        },
        "environment": {
            "state": "warning",
            "reasons": ["otbr_rest_endpoint_mismatch", "foreign_trel_services_observed"],
        },
    }
    otbrs = [
        {
            "id": "study",
            "name": "Study OTBR",
            "reachable": True,
            "health": {"state": "warning", "reasons": ["otbr_rest_endpoint_mismatch"]},
            "thread_state": "leader",
            "role": "leader",
            "thread_state_source": "legacy_node",
            "rest_endpoint_mismatch": True,
            "json_api_thread_state": "disabled",
            "legacy_node_thread_state": "active",
        },
        {
            "id": "lounge",
            "name": "Lounge OTBR",
            "reachable": True,
            "health": {"state": "warning", "reasons": ["otbr_rest_endpoint_mismatch"]},
            "thread_state": "router",
            "role": "router",
            "thread_state_source": "legacy_node",
            "rest_endpoint_mismatch": True,
            "json_api_thread_state": "disabled",
            "legacy_node_thread_state": "active",
        },
    ]
    payload = build_dashboard_payload(
        connected=True,
        version=VERSION,
        status=STATUS,
        health=health,
        otbrs=otbrs,
    )

    prominent_codes = {r["code"] for r in payload["threadlens"]["reasons"]}
    all_codes = {r["code"] for r in payload["threadlens"]["reasons_all"]}
    assert "otbr_rest_endpoint_mismatch" not in prominent_codes
    assert "foreign_trel_services_observed" not in prominent_codes
    assert "otbr_rest_endpoint_mismatch" in all_codes
    assert "foreign_trel_services_observed" in all_codes

    study = payload["otbrs"][0]
    assert study["mismatch_reconciled"] is True
    assert study["display_health"] == "healthy"
    assert study["effective_state"] == "leader"
    assert study["state_source_label"] == "/node"
    assert study["reasons"] == []
    assert any(r["code"] == "otbr_rest_endpoint_mismatch" for r in study["reasons_all"])
    assert study["mismatch_detail"]
    assert "No action is required" in study["mismatch_detail"]


def test_otbr_endpoint_mismatch_unreconciled_stays_prominent():
    health = {
        "overall": {"state": "warning", "reasons": ["otbr_rest_endpoint_mismatch"]},
        "environment": {"state": "warning", "reasons": ["otbr_rest_endpoint_mismatch"]},
    }
    payload = build_dashboard_payload(
        connected=True,
        version=VERSION,
        status=STATUS,
        health=health,
        otbrs=[
            {
                "id": "study",
                "reachable": False,
                "health": {"state": "warning", "reasons": ["otbr_rest_endpoint_mismatch"]},
                "thread_state": "disabled",
                "role": None,
                "rest_endpoint_mismatch": True,
                "json_api_thread_state": "disabled",
                "legacy_node_thread_state": "disabled",
            }
        ],
    )
    prominent_codes = {r["code"] for r in payload["threadlens"]["reasons"]}
    assert "otbr_rest_endpoint_mismatch" in prominent_codes
    otbr = payload["otbrs"][0]
    assert otbr["mismatch_reconciled"] is False
    assert otbr["display_health"] == "warning"


def test_otbr_endpoint_mismatch_raw_fields_preserved():
    payload = build_dashboard_payload(
        connected=True,
        version=VERSION,
        status=STATUS,
        health=HEALTHY_HEALTH,
        otbrs=[
            {
                "id": "otbr1",
                "name": "Study OTBR",
                "reachable": True,
                "health": {"state": "warning", "reasons": ["otbr_rest_endpoint_mismatch"]},
                "thread_state": "leader",
                "role": "leader",
                "thread_state_source": "legacy_node",
                "rest_endpoint_mismatch": True,
                "json_api_thread_state": "disabled",
                "legacy_node_thread_state": "active",
            }
        ],
    )
    otbr = payload["otbrs"][0]
    assert otbr["rest_endpoint_mismatch"] is True
    assert otbr["thread_state_source"] == "legacy_node"
    assert otbr["json_api_thread_state"] == "disabled"
    assert any(r["code"] == "otbr_rest_endpoint_mismatch" for r in otbr["reasons_all"])


def test_unavailable_matter_nodes_listed():
    payload = build_dashboard_payload(
        connected=True,
        version=VERSION,
        status=STATUS,
        health=HEALTHY_HEALTH,
        matter_servers=[{"id": "m1", "connected": True}],
        matter_nodes=[
            {"node_id": 1, "server_id": "m1", "available": True},
            {"node_id": 2, "server_id": "m1", "available": False, "friendly_name": "Sensor"},
        ],
    )
    assert payload["matter"]["unavailable_count"] == 1
    assert payload["matter"]["unavailable_nodes"][0]["node_id"] == 2


def test_disconnected_payload_is_structured():
    payload = build_disconnected_payload(
        version=VERSION,
        last_update="2026-06-14T12:00:00+00:00",
        error="Cannot reach the ThreadLens API",
    )
    assert payload["threadlens"]["api_connected"] is False
    assert payload["threadlens"]["overall_health"] == "unknown"
    assert payload["error"] == "Cannot reach the ThreadLens API"
    assert payload["otbrs"] == []
    assert payload["matter"]["node_count"] == 0
    assert payload["report"]["report_url"] == DASHBOARD_REPORT_URLS["yaml"]


def test_no_mqtt_dependency():
    status_no_mqtt = {
        "collectors": {"mdns": {"observation_degraded": False}},
        "reports": {"last_generated_at": None},
    }
    payload = build_dashboard_payload(
        connected=True,
        version=VERSION,
        status=status_no_mqtt,
        health=HEALTHY_HEALTH,
    )
    assert payload["mqtt"] is None
    assert payload["threadlens"]["overall_health"] == "healthy"
    assert payload["mdns"]["service_count"] == 0


def test_foreign_trel_alone_is_informational():
    health = {
        "overall": {"state": "warning", "reasons": ["foreign_trel_services_observed"]},
        "environment": {"state": "warning", "reasons": ["foreign_trel_services_observed"]},
        "trel": {"state": "warning", "reasons": ["foreign_trel_services_observed"]},
    }
    payload = build_dashboard_payload(
        connected=True,
        version=VERSION,
        status=STATUS,
        health=health,
        trel_services=[{"service_id": f"t{i}", "is_foreign": True} for i in range(6)],
    )
    trel = payload["trel"]
    assert trel["health"] == "healthy"
    assert trel["health_raw"] == "warning"
    assert trel["informational"] is True
    assert trel["foreign_service_count"] == 6
    assert trel["reasons"] == []
    assert any(r["code"] == "foreign_trel_services_observed" for r in trel["reasons_all"])
    assert payload["threadlens"]["overall_health"] == "healthy"
    assert payload["threadlens"]["overall_health_raw"] == "warning"
    informational = payload["threadlens"]["informational_reasons"]
    assert any(r["code"] == "foreign_trel_services_observed" for r in informational)
    assert trel["info"]["foreign_trel_observed"] is True
    assert trel["info"]["message"]


def test_trel_real_instability_stays_warning():
    health = {
        "overall": {"state": "warning", "reasons": ["mdns_service_flapping_degraded"]},
        "environment": {"state": "warning", "reasons": []},
        "trel": {
            "state": "warning",
            "reasons": ["foreign_trel_services_observed", "mdns_service_flapping_degraded"],
        },
    }
    payload = build_dashboard_payload(
        connected=True,
        version=VERSION,
        status=STATUS,
        health=health,
        trel_services=[{"service_id": "t1", "is_foreign": True}],
    )
    assert payload["trel"]["health"] == "warning"
    assert payload["trel"]["informational"] is False


def test_humanize_unknown_reason():
    assert humanize_reason("some_new_reason_code") == "Some new reason code"
    assert humanize_reason("otbr_thread_stack_disabled") == "OTBR Thread stack disabled"


def test_report_urls_are_relative_and_path_safe():
    payload = _healthy_payload()
    assert payload["report"]["report_url"] == "api/v1/report.yaml"
    assert payload["report"]["report_url_json"] == "api/v1/report.json"
    assert "://" not in payload["report"]["report_url"]
    assert "://" not in payload["report"]["report_url_json"]
