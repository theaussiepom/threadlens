"""Plan safe read-only Matter probe candidates from node data and config."""

from __future__ import annotations

from dataclasses import dataclass

from threadlens.config import (
    MatterProbeAdvancedConfig,
    MatterProbeConfig,
    MatterProbePerNodeOverride,
    ProbeMode,
)
from threadlens.models.state import MatterNodeState

WINDOW_COVERING_CLUSTER = 258
BASIC_INFORMATION_CLUSTER = 40
DESCRIPTOR_CLUSTER = 29
WINDOW_COVERING_STATUS_ATTRIBUTE = 10

# Read-only attributes to try, in preference order, when discovered on a node.
_CLUSTER_READ_PRIORITIES: dict[int, tuple[int, ...]] = {
    BASIC_INFORMATION_CLUSTER: (2, 4, 5, 3, 1, 0, 7, 8),
    WINDOW_COVERING_CLUSTER: (10, 0, 7, 8, 11, 12),
    DESCRIPTOR_CLUSTER: (0, 1, 2),
}

# Additional clusters present in attribute keys that are generally safe to read.
_EXTRA_DISCOVERED_CLUSTERS = frozenset({6, 8, 3})

_CLUSTER_PROBE_LABELS: dict[int, str] = {
    BASIC_INFORMATION_CLUSTER: "Device info read check",
    WINDOW_COVERING_CLUSTER: "Device attribute read check",
    DESCRIPTOR_CLUSTER: "Descriptor read check",
}

_MAX_DISCOVERED_CANDIDATES = 12


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
        if mode == ProbeMode.DISABLED:
            return []

        keys = attribute_keys or frozenset(node.matter_attribute_keys or [])
        unsupported = set(node.last_unsupported_probe_paths or [])
        advanced = config.advanced
        per_node = advanced.per_node.get(str(node.node_id))
        if per_node is not None and per_node.disabled:
            return []

        overrides = self._override_candidates(per_node)
        cached = self._cached_success_candidate(node, unsupported)
        generics = self._generic_candidates(advanced)
        device_specific = (
            self._device_specific_candidates(node=node, attribute_keys=keys, config=config)
            if mode in {ProbeMode.STANDARD, ProbeMode.DIAGNOSTIC}
            else []
        )
        discovered = self._discovered_candidates(keys)
        descriptors = self._descriptor_candidates(keys) if mode == ProbeMode.DIAGNOSTIC else []

        if mode == ProbeMode.CONSERVATIVE:
            ordered = [*overrides, *cached, *discovered, *generics]
        elif mode == ProbeMode.STANDARD:
            ordered = [*overrides, *device_specific, *cached, *discovered, *generics]
        else:
            ordered = [
                *overrides,
                *device_specific,
                *cached,
                *discovered,
                *generics,
                *descriptors,
            ]

        return [
            candidate
            for candidate in _dedupe_candidates(ordered)
            if candidate.attribute_path not in unsupported
        ]

    def _override_candidates(
        self,
        per_node: MatterProbePerNodeOverride | None,
    ) -> list[ProbeCandidate]:
        if per_node is None:
            return []
        return [
            ProbeCandidate(
                kind="override",
                label="Configured read check",
                attribute_path=path,
                required=True,
                health_weight="override",
            )
            for path in per_node.preferred
        ]

    def _cached_success_candidate(
        self,
        node: MatterNodeState,
        unsupported: set[str],
    ) -> list[ProbeCandidate]:
        if not node.last_successful_probe_path or node.last_successful_probe_path in unsupported:
            return []
        return [
            ProbeCandidate(
                kind=node.last_successful_probe_kind or "cached",
                label=node.last_probe_label or "Previous read check",
                attribute_path=node.last_successful_probe_path,
                required=False,
                health_weight="generic",
            )
        ]

    def _discovered_candidates(self, attribute_keys: frozenset[str]) -> list[ProbeCandidate]:
        """Derive probe paths from the node's own Matter attribute keys."""
        parsed_keys: list[tuple[int, int, int]] = []
        for key in attribute_keys:
            parsed = parse_attribute_path(key)
            if parsed is not None:
                parsed_keys.append(parsed)
        if not parsed_keys:
            return []

        candidates: list[ProbeCandidate] = []
        seen_paths: set[str] = set()

        def add_candidate(*, endpoint: int, cluster_id: int, attribute_id: int) -> bool:
            path = f"{endpoint}/{cluster_id}/{attribute_id}"
            if path not in attribute_keys or path in seen_paths:
                return False
            label = _CLUSTER_PROBE_LABELS.get(cluster_id, "Discovered read check")
            candidates.append(
                ProbeCandidate(
                    kind="discovered",
                    label=label,
                    attribute_path=path,
                    required=False,
                    health_weight="generic",
                )
            )
            seen_paths.add(path)
            return len(candidates) >= _MAX_DISCOVERED_CANDIDATES

        cluster_order = (
            BASIC_INFORMATION_CLUSTER,
            WINDOW_COVERING_CLUSTER,
            DESCRIPTOR_CLUSTER,
        )
        for cluster_id in cluster_order:
            priorities = _CLUSTER_READ_PRIORITIES.get(cluster_id, ())
            endpoints = sorted(
                {endpoint for endpoint, cluster, _ in parsed_keys if cluster == cluster_id}
            )
            for attribute_id in priorities:
                for endpoint in endpoints:
                    if add_candidate(
                        endpoint=endpoint,
                        cluster_id=cluster_id,
                        attribute_id=attribute_id,
                    ):
                        return candidates

        for endpoint, cluster_id, attribute_id in sorted(parsed_keys):
            if cluster_id in cluster_order or cluster_id not in _EXTRA_DISCOVERED_CLUSTERS:
                continue
            if add_candidate(endpoint=endpoint, cluster_id=cluster_id, attribute_id=attribute_id):
                return candidates

        return candidates

    def _generic_candidates(self, advanced: MatterProbeAdvancedConfig) -> list[ProbeCandidate]:
        return [
            ProbeCandidate(
                kind="basic_information",
                label="Basic read check",
                attribute_path=path,
                required=False,
                health_weight="generic",
            )
            for path in advanced.attributes.fallback
        ]

    def _descriptor_candidates(self, attribute_keys: frozenset[str]) -> list[ProbeCandidate]:
        candidates: list[ProbeCandidate] = []
        for endpoint in endpoints_with_cluster(attribute_keys, DESCRIPTOR_CLUSTER):
            candidates.append(
                ProbeCandidate(
                    kind="descriptor",
                    label="Descriptor read check",
                    attribute_path=f"{endpoint}/{DESCRIPTOR_CLUSTER}/0",
                    required=False,
                    health_weight="generic",
                )
            )
        if not candidates:
            candidates.append(
                ProbeCandidate(
                    kind="descriptor",
                    label="Descriptor read check",
                    attribute_path=f"0/{DESCRIPTOR_CLUSTER}/0",
                    required=False,
                    health_weight="generic",
                )
            )
        return candidates

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
                        label="Window covering read check",
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
                        label="Window covering read check",
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
