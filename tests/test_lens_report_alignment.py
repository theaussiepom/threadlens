"""Tests for Lens family report presentation helpers."""

from threadlens.models.health import HealthState, HealthStatus
from threadlens.models.reports import (
    RedactionSummary,
    ReportHealthSection,
    ReportMatterNodeEntry,
    ReportSite,
    ReportSummary,
    ThreadLensReport,
)
from threadlens.presentation.lens_reports import (
    build_active_incidents,
    build_collector_status,
    build_health_summary,
    health_state_to_lens_bucket,
    redaction_profile_for_report,
)
from threadlens.utils.time import utc_now


def test_health_state_maps_to_lens_bucket() -> None:
    assert health_state_to_lens_bucket(HealthState.HEALTHY) == "healthy"
    assert health_state_to_lens_bucket(HealthState.WARNING) == "recently_unstable"
    assert health_state_to_lens_bucket(HealthState.DEGRADED) == "needs_attention"


def test_active_incident_includes_affected_entity_fields() -> None:
    report = ThreadLensReport(
        generated_at=utc_now(),
        version="0.0.0-test",
        site=ReportSite(name="Lab"),
        summary=ReportSummary(matter_nodes_seen=1),
        health=ReportHealthSection(
            overall=HealthStatus(state=HealthState.DEGRADED, reasons=["matter_node_unavailable"])
        ),
        matter_nodes=[
            ReportMatterNodeEntry(
                node_id=24,
                server_id="study_matter",
                friendly_name="Kitchen Blind",
                health=HealthStatus(state=HealthState.DEGRADED, reasons=["read_probe_failed"]),
            )
        ],
        redaction=RedactionSummary(enabled=True, profile="public_safe"),
    )
    incidents = build_active_incidents(report)
    assert incidents
    entity = incidents[0]["affected_entities"][0]
    assert entity["name"] == "Kitchen Blind"
    assert entity["classification"] == "needs_attention"
    assert entity["reason"] == "read probe failed"


def test_collector_status_and_redaction_profile() -> None:
    report = ThreadLensReport(
        generated_at=utc_now(),
        version="0.0.0-test",
        redaction=RedactionSummary(enabled=True, profile="public_safe"),
    )
    status = build_collector_status(report)
    assert status["mode"] == "server"
    assert status["read_probe_diagnostics"] in {"available", "limited_or_unavailable"}
    assert redaction_profile_for_report(report) == "public_safe"
    summary = build_health_summary(report)
    assert summary["vocabulary"] == "lens_family"
