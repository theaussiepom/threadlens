"""Serialize ThreadLens reports."""

from __future__ import annotations

import json
from typing import Any

import yaml

from threadlens.models.reports import ThreadLensReport
from threadlens.presentation.lens_reports import (
    build_active_incidents,
    build_collector_status,
    build_domain_details,
    build_executive_summary,
    build_health_summary,
    build_limitations,
    redaction_profile_for_report,
)
from threadlens.report.redaction import DEFAULT_SECRETS_REMOVED, redact_structure


def report_to_dict(report: ThreadLensReport, *, apply_redaction: bool = True) -> dict[str, Any]:
    payload = {
        "product": report.product,
        "version": report.version,
        "generated_at": report.generated_at.isoformat(),
        "site": report.site.model_dump(mode="json"),
        "mode": report.mode,
        "redaction_profile": redaction_profile_for_report(report),
        "executive_summary": build_executive_summary(report),
        "health_summary": build_health_summary(report),
        "active_incidents": build_active_incidents(report),
        "collector_status": build_collector_status(report),
        "limitations": build_limitations(report),
        "domain_details": build_domain_details(report),
        "events_or_timeline": {
            "recent": [event.model_dump(mode="json") for event in report.events.recent],
        },
        "report": {
            "generated_at": report.generated_at.isoformat(),
            "product": report.product,
            "tool": report.tool,
            "version": report.version,
            "window": report.window,
            "mode": report.mode,
        },
        "summary": report.summary.model_dump(mode="json"),
        "capabilities": report.capabilities.model_dump(mode="json"),
        "health": report.health.model_dump(mode="json"),
        "thread_networks": [item.model_dump(mode="json") for item in report.thread_networks],
        "otbrs": [item.model_dump(mode="json") for item in report.otbrs],
        "mdns_services": [item.model_dump(mode="json") for item in report.mdns_services],
        "trel_services": [item.model_dump(mode="json") for item in report.trel_services],
        "matter_servers": [item.model_dump(mode="json") for item in report.matter_servers],
        "matter_nodes": [item.model_dump(mode="json") for item in report.matter_nodes],
        "trel_mdns": report.trel_mdns.model_dump(mode="json"),
        "aggregates": report.aggregates.model_dump(mode="json"),
        "events": {
            "recent": [event.model_dump(mode="json") for event in report.events.recent],
        },
        "redaction": report.redaction.model_dump(mode="json"),
    }
    if report.focus is not None:
        payload["focus"] = report.focus.model_dump(mode="json")
    if apply_redaction and report.redaction.enabled:
        payload = redact_structure(payload)
        payload["redaction"] = report.redaction.model_dump(mode="json")
    return payload


def report_to_json(report: ThreadLensReport, *, apply_redaction: bool = True) -> str:
    return json.dumps(report_to_dict(report, apply_redaction=apply_redaction), indent=2)


def report_to_yaml(report: ThreadLensReport, *, apply_redaction: bool = True) -> str:
    return yaml.safe_dump(
        report_to_dict(report, apply_redaction=apply_redaction),
        sort_keys=False,
        default_flow_style=False,
    )


def default_redaction_summary(enabled: bool = True) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "profile": "public_safe" if enabled else "none",
        "secrets_removed": list(DEFAULT_SECRETS_REMOVED),
    }
