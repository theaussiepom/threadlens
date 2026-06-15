"""Lens-family MQTT summary presentation (no health-engine changes)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from threadlens.models.health import HealthReport, HealthState
from threadlens.models.state import MatterNodeState
from threadlens.utils.time import utc_now

PRODUCT = "threadlens"
REDACTION_PROFILE = "public_safe"

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


def _matter_read_probe_issue(node: MatterNodeState) -> bool:
    if not node.read_probe_diagnostics_available:
        return False
    if node.last_read_probe_limited:
        return False
    if node.last_read_probe_ok is False:
        return True
    failures = node.read_probe_failures_24h
    return isinstance(failures, int) and failures >= 1


def _count_matter_read_probe_issues(nodes: list[MatterNodeState]) -> int:
    return sum(1 for node in nodes if _matter_read_probe_issue(node))


def _any_read_probe_diagnostics(nodes: list[MatterNodeState]) -> bool:
    return any(node.read_probe_diagnostics_available for node in nodes)


def _node_lens_bucket(node: MatterNodeState) -> str:
    if not node.available:
        return "unavailable"
    if node.read_probe_diagnostics_available and not node.last_read_probe_limited:
        if node.last_read_probe_ok is False:
            return "recently_unstable"
        failures = node.read_probe_failures_24h
        if isinstance(failures, int) and failures >= 1:
            return "recently_unstable"
    if not node.read_probe_diagnostics_available:
        return "diagnostics_limited"
    return "healthy"


def lens_bucket_counts_from_nodes(
    nodes: list[MatterNodeState],
    *,
    observable: bool,
) -> dict[str, int | str]:
    keys = tuple(LENS_BUCKET_LABELS)
    if not observable:
        return dict.fromkeys(keys, "unknown")

    counts: dict[str, int] = dict.fromkeys(keys, 0)
    for node in nodes:
        bucket = _node_lens_bucket(node)
        counts[bucket] += 1
    return counts


def issue_count(counts: dict[str, int | str]) -> int | str:
    if any(value == "unknown" for value in counts.values()):
        return "unknown"
    total = 0
    for bucket in (
        "unavailable",
        "recently_unstable",
        "needs_attention",
        "diagnostics_limited",
        "unknown",
    ):
        total += int(counts.get(bucket, 0))
    return total


def count_state(value: int | str) -> str:
    if value == "unknown":
        return "unknown"
    return str(int(value))


@dataclass(frozen=True)
class SummaryEntityState:
    key: str
    name: str
    state: str
    attributes: dict[str, Any]


def build_summary_entities(
    *,
    health: HealthReport,
    matter_nodes: list[MatterNodeState],
    version: str,
    site: str,
    observable: bool = True,
) -> list[SummaryEntityState]:
    counts = lens_bucket_counts_from_nodes(matter_nodes, observable=observable)
    overall_bucket = health_state_to_lens_bucket(health.overall.state)
    overall_label = LENS_BUCKET_LABELS.get(overall_bucket, overall_bucket.title())
    issues = issue_count(counts)
    generated_at = utc_now().isoformat()

    read_probe_observable = _any_read_probe_diagnostics(matter_nodes)
    if read_probe_observable:
        read_probe_issues = _count_matter_read_probe_issues(matter_nodes)
    else:
        read_probe_issues = "unknown"

    base_attrs = {
        "product": PRODUCT,
        "version": version,
        "site": site,
        "lens_bucket": overall_bucket,
        "lens_bucket_label": overall_label,
        "issue_count": issues,
        "unavailable_count": counts["unavailable"],
        "needs_attention_count": counts["needs_attention"],
        "recently_unstable_count": counts["recently_unstable"],
        "diagnostics_limited_count": counts["diagnostics_limited"],
        "informational_count": counts["informational"],
        "unknown_count": counts["unknown"],
        "generated_at": generated_at,
        "redaction_profile": REDACTION_PROFILE,
        "observation_reliable": observable,
        "read_probe_diagnostics_available": read_probe_observable,
    }

    return [
        SummaryEntityState(
            key="health",
            name="ThreadLens Health",
            state=overall_bucket,
            attributes=base_attrs,
        ),
        SummaryEntityState(
            key="issues",
            name="ThreadLens Issues",
            state=count_state(issues),
            attributes={**base_attrs, "lens_bucket": overall_bucket},
        ),
        SummaryEntityState(
            key="unavailable",
            name="ThreadLens Unavailable Nodes",
            state=count_state(counts["unavailable"]),
            attributes=base_attrs,
        ),
        SummaryEntityState(
            key="needs_attention",
            name="ThreadLens Needs Attention",
            state=count_state(counts["needs_attention"]),
            attributes=base_attrs,
        ),
        SummaryEntityState(
            key="recently_unstable",
            name="ThreadLens Recently Unstable",
            state=count_state(counts["recently_unstable"]),
            attributes=base_attrs,
        ),
        SummaryEntityState(
            key="diagnostics_limited",
            name="ThreadLens Diagnostics Limited",
            state=count_state(counts["diagnostics_limited"]),
            attributes=base_attrs,
        ),
        SummaryEntityState(
            key="matter_read_probe_issues",
            name="ThreadLens Matter Read Probe Issues",
            state=count_state(read_probe_issues),
            attributes=base_attrs,
        ),
    ]
