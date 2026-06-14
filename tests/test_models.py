"""Domain model tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from threadlens import __version__
from threadlens.models.capabilities import EnvironmentCapabilities, MatterServerCapabilities
from threadlens.models.events import (
    Event,
    EventSeverity,
    EventSourceType,
    EventSubjectType,
)
from threadlens.models.health import HealthState, HealthStatus
from threadlens.models.reports import ReportSite, ThreadLensReport
from threadlens.models.state import MatterNodeState
from threadlens.utils.time import utc_now


def test_capability_model_unavailable_metrics_are_null() -> None:
    node = MatterNodeState(
        node_id=24,
        server_id="study_matter",
        subscription_diagnostics_available=False,
        subscription_flaps_24h=None,
        case_failures_24h=None,
    )
    assert node.subscription_flaps_24h is None
    assert node.case_failures_24h is None
    assert node.subscription_diagnostics_available is False

    caps = EnvironmentCapabilities(
        matter_server=MatterServerCapabilities(
            websocket_available=True,
            subscription_diagnostics_available=False,
        )
    )
    assert caps.matter_server.subscription_diagnostics_available is False


def test_event_model_serialises_cleanly() -> None:
    event = Event(
        id="evt-1",
        timestamp=datetime(2026, 6, 12, 10, 30, tzinfo=UTC),
        source_type=EventSourceType.MATTER_SERVER,
        source_id="study_matter",
        event_type="matter_node.unavailable",
        severity=EventSeverity.WARNING,
        subject_type=EventSubjectType.MATTER_NODE,
        subject_id="matter_node:24",
        message="Matter node 24 became unavailable",
        data={"node_id": 24},
    )
    payload = event.model_dump(mode="json")
    assert payload["source_type"] == "matter_server"
    assert payload["severity"] == "warning"
    assert payload["data"]["node_id"] == 24
    json.dumps(payload)


def test_report_model_serialises_without_populated_collectors() -> None:
    report = ThreadLensReport(
        generated_at=utc_now(),
        version=__version__,
        site=ReportSite(name="Home"),
    )
    payload = report.model_dump(mode="json")
    assert payload["tool"] == "ThreadLens"
    assert payload["thread_networks"] == []
    assert payload["matter_nodes"] == []
    assert payload["capabilities"]["matter_subscription_diagnostics"] is False
    json.dumps(payload)


def test_health_status_with_reasons() -> None:
    health = HealthStatus(
        state=HealthState.DEGRADED, reasons=["availability_flaps_24h_above_threshold"]
    )
    assert health.state == HealthState.DEGRADED
    updated = health.with_reason("matter_node_unavailable")
    assert updated.reasons == [
        "availability_flaps_24h_above_threshold",
        "matter_node_unavailable",
    ]
