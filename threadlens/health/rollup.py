"""Health rollup helpers."""

from __future__ import annotations

from threadlens.models.health import HealthState, HealthStatus

_STATE_RANK: dict[HealthState, int] = {
    HealthState.CRITICAL: 0,
    HealthState.DEGRADED: 1,
    HealthState.WARNING: 2,
    HealthState.UNKNOWN: 3,
    HealthState.HEALTHY: 4,
}


def state_rank(state: HealthState) -> int:
    return _STATE_RANK[state]


def pick_worst(*states: HealthState) -> HealthState:
    if not states:
        return HealthState.UNKNOWN
    return min(states, key=state_rank)


def merge_health(*statuses: HealthStatus) -> HealthStatus:
    """Roll up child health using worst-state wins semantics."""
    if not statuses:
        return HealthStatus(state=HealthState.UNKNOWN, reasons=["insufficient_data"])

    worst_state = pick_worst(*(status.state for status in statuses))
    reasons: list[str] = []
    for status in statuses:
        if status.state == worst_state:
            for reason in status.reasons:
                if reason not in reasons:
                    reasons.append(reason)
    return HealthStatus(state=worst_state, reasons=reasons)


def health_from_candidates(candidates: list[tuple[HealthState, list[str]]]) -> HealthStatus:
    """Pick the worst matching rule from an ordered candidate list."""
    if not candidates:
        return HealthStatus(state=HealthState.UNKNOWN, reasons=["insufficient_data"])

    worst_state = pick_worst(*(state for state, _ in candidates))
    reasons: list[str] = []
    for state, state_reasons in candidates:
        if state == worst_state:
            for reason in state_reasons:
                if reason not in reasons:
                    reasons.append(reason)
    return HealthStatus(state=worst_state, reasons=reasons)
