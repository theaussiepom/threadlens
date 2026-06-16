"""Lens family report presentation helpers (no health-engine changes)."""

from __future__ import annotations

from typing import Any

from threadlens.models.health import HealthState, HealthStatus
from threadlens.models.reports import ThreadLensReport

LENS_BUCKET_LABELS: dict[str, str] = {
    "healthy": "Healthy",
    "recently_unstable": "Recently unstable",
    "needs_attention": "Needs attention",
    "unavailable": "Unavailable",
    "diagnostics_limited": "Diagnostics limited",
    "informational": "Informational",
    "unknown": "Unknown",
}

_HEALTH_STATE_TO_LENS: dict[HealthState, str] = {
    HealthState.HEALTHY: "healthy",
    HealthState.WARNING: "recently_unstable",
    HealthState.DEGRADED: "needs_attention",
    HealthState.CRITICAL: "needs_attention",
    HealthState.UNKNOWN: "unknown",
}


def health_state_to_lens_bucket(state: HealthState) -> str:
    return _HEALTH_STATE_TO_LENS.get(state, "unknown")


def lens_bucket_label(bucket: str) -> str:
    return LENS_BUCKET_LABELS.get(bucket, bucket.replace("_", " ").title())


def _primary_reason(status: HealthStatus) -> str:
    if status.reasons:
        return status.reasons[0].replace("_", " ")
    return lens_bucket_label(health_state_to_lens_bucket(status.state))


def build_health_summary(report: ThreadLensReport) -> dict[str, Any]:
    counts = {key: 0 for key in LENS_BUCKET_LABELS}
    for node in report.matter_nodes:
        bucket = health_state_to_lens_bucket(node.health.state)
        counts[bucket] = counts.get(bucket, 0) + 1
    for otbr in report.otbrs:
        bucket = health_state_to_lens_bucket(otbr.health.state)
        counts[bucket] = counts.get(bucket, 0) + 1
    for server in report.matter_servers:
        bucket = health_state_to_lens_bucket(server.health.state)
        counts[bucket] = counts.get(bucket, 0) + 1
    overall_bucket = health_state_to_lens_bucket(report.health.overall.state)
    labels = {bucket: lens_bucket_label(bucket) for bucket, count in counts.items() if count > 0}
    return {
        "vocabulary": "lens_family",
        "overall_state": overall_bucket,
        "overall_label": lens_bucket_label(overall_bucket),
        "bucket_counts": counts,
        "bucket_labels": labels,
    }


def build_executive_summary(report: ThreadLensReport) -> str:
    overall = report.health.overall
    summary = report.summary
    if overall.state == HealthState.HEALTHY:
        return (
            f"Thread/Matter environment looks healthy for site {report.site.name}. "
            f"{summary.matter_nodes_seen} Matter node(s) observed in the report window."
        )
    if overall.reasons:
        reason_text = ", ".join(reason.replace("_", " ") for reason in overall.reasons[:3])
        return (
            f"ThreadLens observed health concerns at site {report.site.name}: {reason_text}. "
            "Review affected entities and collector status below; this report describes "
            "observed evidence only."
        )
    return (
        f"ThreadLens report for site {report.site.name} with overall health "
        f"{lens_bucket_label(health_state_to_lens_bucket(overall.state))}."
    )


def build_active_incidents(report: ThreadLensReport) -> list[dict[str, Any]]:
    incidents: list[dict[str, Any]] = []

    def _append_entity_incident(
        *,
        title: str,
        headline: str,
        entity_name: str,
        classification: str,
        reason: str,
        evidence: list[str],
        limitations: list[str],
    ) -> None:
        incidents.append(
            {
                "title": title,
                "headline": headline,
                "affected_entities": [
                    {
                        "name": entity_name,
                        "classification": classification,
                        "reason": reason,
                    }
                ],
                "evidence": evidence,
                "limitations": limitations,
            }
        )

    for node in report.matter_nodes:
        if node.health.state == HealthState.HEALTHY:
            continue
        bucket = health_state_to_lens_bucket(node.health.state)
        name = node.friendly_name or f"Node {node.node_id}"
        limitations: list[str] = []
        if not node.read_probe_diagnostics_available:
            limitations.append("Read probe diagnostics unavailable for this node.")
        elif node.last_read_probe_limited:
            limitations.append("Read probe diagnostics limited for this node.")
        _append_entity_incident(
            title=f"{name} — {lens_bucket_label(bucket)}",
            headline=f"Matter node {name} is classified {lens_bucket_label(bucket).lower()}.",
            entity_name=name,
            classification=bucket,
            reason=_primary_reason(node.health),
            evidence=[reason.replace("_", " ") for reason in node.health.reasons],
            limitations=limitations,
        )

    for otbr in report.otbrs:
        if otbr.health.state == HealthState.HEALTHY:
            continue
        bucket = health_state_to_lens_bucket(otbr.health.state)
        _append_entity_incident(
            title=f"{otbr.name} — {lens_bucket_label(bucket)}",
            headline=f"OTBR {otbr.name} is classified {lens_bucket_label(bucket).lower()}.",
            entity_name=otbr.name,
            classification=bucket,
            reason=_primary_reason(otbr.health),
            evidence=[reason.replace("_", " ") for reason in otbr.health.reasons],
            limitations=[] if otbr.reachable else ["OTBR REST was not reachable when observed."],
        )

    for server in report.matter_servers:
        if server.health.state == HealthState.HEALTHY:
            continue
        bucket = health_state_to_lens_bucket(server.health.state)
        _append_entity_incident(
            title=f"{server.name} — {lens_bucket_label(bucket)}",
            headline=(
                f"Matter server {server.name} is classified {lens_bucket_label(bucket).lower()}."
            ),
            entity_name=server.name,
            classification=bucket,
            reason=_primary_reason(server.health),
            evidence=[reason.replace("_", " ") for reason in server.health.reasons],
            limitations=(
                [] if server.connected else ["Matter server was not connected when observed."]
            ),
        )

    return incidents


def build_collector_status(report: ThreadLensReport) -> dict[str, Any]:
    caps = report.capabilities
    foreign_trel = report.trel_mdns.foreign_services_seen or 0
    return {
        "mode": report.mode,
        "mdns_observation": "available" if caps.mdns_observation else "unavailable",
        "mdns_observation_degraded": caps.mdns_observation_degraded,
        "otbr_rest": "reachable" if caps.otbr_rest else "not_reachable",
        "matter_server_websocket": "connected" if caps.matter_server_websocket else "disconnected",
        "matter_node_availability": "available" if caps.matter_node_availability else "limited",
        "read_probe_diagnostics": (
            "available" if caps.matter_read_probe_diagnostics else "limited_or_unavailable"
        ),
        "foreign_trel": "informational" if foreign_trel else "none_observed",
        "agent_api": "reachable" if caps.agent_api_available else "not_reachable",
    }


def build_limitations(report: ThreadLensReport) -> list[str]:
    items = [
        "ThreadLens describes observed Thread/Matter evidence; it does not prove root cause.",
        "Reports distinguish observed zero from unavailable metrics.",
    ]
    caps = report.capabilities
    if not caps.otbr_rest:
        items.append("OTBR REST was not reachable — Thread stack details may be limited.")
    if not caps.matter_server_websocket:
        items.append("Matter server WebSocket was not connected — node inventory may be stale.")
    if not caps.matter_read_probe_diagnostics:
        items.append("Read probe diagnostics are limited or unavailable for all observed nodes.")
    if report.trel_mdns.foreign_services_seen:
        items.append(
            "Foreign TREL services are informational and may belong to neighbouring networks."
        )
    if caps.mdns_observation_degraded:
        items.append("mDNS observation is degraded — service visibility may be incomplete.")
    return items


def build_domain_details(report: ThreadLensReport) -> dict[str, Any]:
    return {
        "thread_networks": [item.model_dump(mode="json") for item in report.thread_networks],
        "otbr": [item.model_dump(mode="json") for item in report.otbrs],
        "matter_nodes": [item.model_dump(mode="json") for item in report.matter_nodes],
        "matter_servers": [item.model_dump(mode="json") for item in report.matter_servers],
        "read_probes": [
            {
                "node_id": node.node_id,
                "server_id": node.server_id,
                "friendly_name": node.friendly_name,
                "read_probe_diagnostics_available": node.read_probe_diagnostics_available,
                "last_read_probe_ok": node.last_read_probe_ok,
                "last_read_probe_limited": node.last_read_probe_limited,
                "last_read_probe_note": node.last_read_probe_note,
            }
            for node in report.matter_nodes
        ],
        "mdns": [item.model_dump(mode="json") for item in report.mdns_services],
        "trel": [item.model_dump(mode="json") for item in report.trel_services],
    }


def redaction_profile_for_report(report: ThreadLensReport) -> str:
    return "public_safe" if report.redaction.enabled else "none"
