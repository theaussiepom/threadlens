"""Tests for Lens-family MQTT summary presentation."""

from __future__ import annotations

from threadlens.models.health import EnvironmentSummary, HealthReport, HealthState, HealthStatus
from threadlens.models.state import MatterNodeState
from threadlens.presentation.lens_mqtt import build_summary_entities, count_state, issue_count


def _health(**overrides) -> HealthReport:
    base = HealthReport(
        version="0.0.0",
        mode="server",
        site="Home",
        overall=HealthStatus(),
        environment=HealthStatus(),
        summary=EnvironmentSummary(),
    )
    return base.model_copy(update=overrides)


def test_read_probe_issues_unknown_without_diagnostics() -> None:
    summaries = build_summary_entities(
        health=_health(),
        matter_nodes=[
            MatterNodeState(
                node_id=1,
                server_id="home",
                available=True,
                read_probe_diagnostics_available=False,
            )
        ],
        version="0.0.0",
        site="Home",
    )
    read_probe = next(item for item in summaries if item.key == "matter_read_probe_issues")
    assert read_probe.state == "unknown"


def test_read_probe_issues_zero_when_no_failures() -> None:
    summaries = build_summary_entities(
        health=_health(),
        matter_nodes=[
            MatterNodeState(
                node_id=1,
                server_id="home",
                available=True,
                read_probe_diagnostics_available=True,
                last_read_probe_ok=True,
                read_probe_failures_24h=0,
            )
        ],
        version="0.0.0",
        site="Home",
    )
    read_probe = next(item for item in summaries if item.key == "matter_read_probe_issues")
    assert read_probe.state == "0"


def test_health_entity_includes_lens_bucket_attributes() -> None:
    summaries = build_summary_entities(
        health=_health(
            version="1.2.3",
            overall=HealthStatus(state=HealthState.WARNING, reasons=["matter_node_flapping"]),
        ),
        matter_nodes=[
            MatterNodeState(
                node_id=2,
                server_id="home",
                available=False,
            )
        ],
        version="1.2.3",
        site="Home",
    )
    health = next(item for item in summaries if item.key == "health")
    assert health.state == "recently_unstable"
    assert health.attributes["product"] == "threadlens"
    assert health.attributes["lens_bucket_label"] == "Recently unstable"
    assert health.attributes["redaction_profile"] == "public_safe"


def test_issue_count_unknown_if_any_bucket_unknown() -> None:
    counts = {"unavailable": "unknown", "needs_attention": 0}
    assert issue_count(counts) == "unknown"
    assert count_state("unknown") == "unknown"
    assert count_state(0) == "0"
