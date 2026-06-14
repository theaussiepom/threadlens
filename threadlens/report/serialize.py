"""Serialize ThreadLens reports."""

from __future__ import annotations

import json
from typing import Any

import yaml

from threadlens.models.reports import ThreadLensReport
from threadlens.report.redaction import DEFAULT_SECRETS_REMOVED, redact_structure


def report_to_dict(report: ThreadLensReport, *, apply_redaction: bool = True) -> dict[str, Any]:
    payload = {
        "report": {
            "generated_at": report.generated_at.isoformat(),
            "tool": report.tool,
            "version": report.version,
            "window": report.window,
        },
        "site": report.site.model_dump(mode="json"),
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
        "secrets_removed": list(DEFAULT_SECRETS_REMOVED),
    }
