"""Plan safe read-only Matter probe candidates from node data and config."""

from __future__ import annotations

from dataclasses import dataclass

from threadlens.config import MatterProbeConfig, ProbeMode
from threadlens.models.state import MatterNodeState

WINDOW_COVERING_CLUSTER = 258
BASIC_INFORMATION_CLUSTER = 40
DESCRIPTOR_CLUSTER = 29
WINDOW_COVERING_STATUS_ATTRIBUTE = 10


@dataclass(frozen=True)
class ProbeCandidate:
    kind: str
    label: str
    attribute_path: str
    required: bool = False
    health_weight: str = "generic"


def parse_attribute_path(path: str) -> tuple[int, int, int] | None:
    parts = str(path).strip().split("/")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None


def endpoints_with_cluster(attribute_keys: frozenset[str] | set[str], cluster_id: int) -> list[int]:
    endpoints: set[int] = set()
    for key in attribute_keys:
        parsed = parse_attribute_path(key)
        if parsed is not None and parsed[1] == cluster_id:
            endpoints.add(parsed[0])
    return sorted(endpoints)


def infer_device_types(
    *,
    attribute_keys: frozenset[str] | set[str] | None,
    product_name: str | None,
) -> list[str]:
    types: list[str] = []
    keys = attribute_keys or frozenset()
    if endpoints_with_cluster(keys, WINDOW_COVERING_CLUSTER):
        types.append("Window Covering")
    elif product_name and "blind" in product_name.lower():
        types.append("Window Covering")
    elif product_name and "shade" in product_name.lower():
        types.append("Window Covering")
    return types


def _dedupe_candidates(candidates: list[ProbeCandidate]) -> list[ProbeCandidate]:
    seen: set[str] = set()
    ordered: list[ProbeCandidate] = []
    for candidate in candidates:
        if candidate.attribute_path in seen:
            continue
        seen.add(candidate.attribute_path)
        ordered.append(candidate)
    return ordered


class MatterProbePlanner:
    """Choose ordered read probe candidates for a Matter node."""

    def plan(
        self,
        node: MatterNodeState,
        *,
        attribute_keys: frozenset[str] | None,
        config: MatterProbeConfig,
    ) -> list[ProbeCandidate]:
        mode = config.effective_mode
        if mode == ProbeMode.OFF:
            return []

        keys = attribute_keys or frozenset(node.matter_attribute_keys or [])
        unsupported = set(node.last_unsupported_probe_paths or [])
        advanced = config.advanced
        node_key = str(node.node_id)
        per_node = advanced.per_node.get(node_key)
        if per_node is not None and per_node.disabled:
            return []

        candidates: list[ProbeCandidate] = []

        if per_node is not None:
            for path in per_node.preferred:
                candidates.append(
                    ProbeCandidate(
                        kind="override",
                        label="Configured read check",
                        attribute_path=path,
                        required=True,
                        health_weight="override",
                    )
                )

        if node.last_successful_probe_path and node.last_successful_probe_path not in unsupported:
            candidates.append(
                ProbeCandidate(
                    kind=node.last_successful_probe_kind or "cached",
                    label=node.last_probe_label or "Previous read check",
                    attribute_path=node.last_successful_probe_path,
                    required=False,
                    health_weight="generic",
                )
            )

        for path in advanced.attributes.fallback:
            candidates.append(
                ProbeCandidate(
                    kind="basic_information",
                    label="Basic read check",
                    attribute_path=path,
                    required=False,
                    health_weight="generic",
                )
            )

        descriptor_endpoints = endpoints_with_cluster(keys, DESCRIPTOR_CLUSTER)
        if descriptor_endpoints:
            for endpoint in descriptor_endpoints:
                candidates.append(
                    ProbeCandidate(
                        kind="descriptor",
                        label="Descriptor read check",
                        attribute_path=f"{endpoint}/{DESCRIPTOR_CLUSTER}/0",
                        required=False,
                        health_weight="generic",
                    )
                )
        elif mode == ProbeMode.DIAGNOSTIC:
            candidates.append(
                ProbeCandidate(
                    kind="descriptor",
                    label="Descriptor read check",
                    attribute_path=f"0/{DESCRIPTOR_CLUSTER}/0",
                    required=False,
                    health_weight="generic",
                )
            )

        if mode in {ProbeMode.STANDARD, ProbeMode.DIAGNOSTIC}:
            candidates.extend(
                self._device_specific_candidates(
                    node=node,
                    attribute_keys=keys,
                    config=config,
                )
            )

        filtered = [
            candidate
            for candidate in _dedupe_candidates(candidates)
            if candidate.attribute_path not in unsupported
        ]
        return filtered

    def _device_specific_candidates(
        self,
        *,
        node: MatterNodeState,
        attribute_keys: frozenset[str],
        config: MatterProbeConfig,
    ) -> list[ProbeCandidate]:
        candidates: list[ProbeCandidate] = []
        device_types = infer_device_types(
            attribute_keys=attribute_keys,
            product_name=node.product,
        )
        if node.inferred_device_types:
            device_types = list(dict.fromkeys([*node.inferred_device_types, *device_types]))

        window_endpoints = endpoints_with_cluster(attribute_keys, WINDOW_COVERING_CLUSTER)
        is_window_covering = "Window Covering" in device_types

        if window_endpoints:
            for endpoint in window_endpoints:
                candidates.append(
                    ProbeCandidate(
                        kind="window_covering_status",
                        label="Blind status read check",
                        attribute_path=(
                            f"{endpoint}/{WINDOW_COVERING_CLUSTER}/"
                            f"{WINDOW_COVERING_STATUS_ATTRIBUTE}"
                        ),
                        required=False,
                        health_weight="device_specific",
                    )
                )
        elif is_window_covering:
            for path in config.attributes.window_covering:
                candidates.append(
                    ProbeCandidate(
                        kind="window_covering_status",
                        label="Blind status read check",
                        attribute_path=path,
                        required=False,
                        health_weight="device_specific",
                    )
                )

        return candidates


def first_probe_candidate(
    *,
    node: MatterNodeState,
    attribute_keys: frozenset[str] | None,
    config: MatterProbeConfig,
) -> ProbeCandidate | None:
    candidates = MatterProbePlanner().plan(node, attribute_keys=attribute_keys, config=config)
    return candidates[0] if candidates else None
