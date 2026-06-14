"""Tests for Matter read probe planning."""

from __future__ import annotations

from threadlens.collectors.matter_probe_planner import MatterProbePlanner, infer_device_types
from threadlens.config import (
    MatterProbeAdvancedConfig,
    MatterProbeConfig,
    MatterProbePerNodeOverride,
    ProbeMode,
)
from threadlens.models.state import MatterNodeState


def _node(**overrides) -> MatterNodeState:
    base = {"node_id": 24, "server_id": "home", "available": True}
    base.update(overrides)
    return MatterNodeState(**base)


def test_conservative_mode_uses_generic_candidates_only() -> None:
    config = MatterProbeConfig(enabled=True, mode=ProbeMode.CONSERVATIVE)
    node = _node(product="Living Blind")
    planner = MatterProbePlanner()
    candidates = planner.plan(
        node,
        attribute_keys=frozenset({"2/258/10", "0/40/2"}),
        config=config,
    )
    kinds = [candidate.kind for candidate in candidates]
    assert "window_covering_status" not in kinds
    assert candidates[0].label == "Basic read check"
    assert "0/40/2" in [candidate.attribute_path for candidate in candidates]


def test_standard_mode_adds_window_covering_from_endpoint_data() -> None:
    config = MatterProbeConfig(enabled=True, mode=ProbeMode.STANDARD)
    node = _node()
    planner = MatterProbePlanner()
    candidates = planner.plan(
        node,
        attribute_keys=frozenset({"2/258/10", "0/40/2"}),
        config=config,
    )
    device_paths = [
        candidate.attribute_path
        for candidate in candidates
        if candidate.kind == "window_covering_status"
    ]
    assert "2/258/10" in device_paths


def test_per_node_override_is_first_candidate() -> None:
    config = MatterProbeConfig(
        enabled=True,
        mode=ProbeMode.CONSERVATIVE,
        advanced=MatterProbeAdvancedConfig(
            per_node={"24": MatterProbePerNodeOverride(preferred=["0/40/4"])}
        ),
    )
    candidates = MatterProbePlanner().plan(_node(), attribute_keys=frozenset(), config=config)
    assert candidates[0].attribute_path == "0/40/4"
    assert candidates[0].health_weight == "override"


def test_last_successful_probe_is_reused_before_generic_fallback() -> None:
    config = MatterProbeConfig(enabled=True, mode=ProbeMode.CONSERVATIVE)
    candidates = MatterProbePlanner().plan(
        _node(
            last_successful_probe_kind="basic_information",
            last_successful_probe_path="0/40/4",
            last_probe_label="Basic read check",
        ),
        attribute_keys=frozenset(),
        config=config,
    )
    assert candidates[0].attribute_path == "0/40/4"


def test_unsupported_paths_are_skipped() -> None:
    config = MatterProbeConfig(enabled=True, mode=ProbeMode.CONSERVATIVE)
    candidates = MatterProbePlanner().plan(
        _node(last_unsupported_probe_paths=["1/258/10"]),
        attribute_keys=frozenset({"1/258/10", "0/40/2"}),
        config=config,
    )
    assert "1/258/10" not in [candidate.attribute_path for candidate in candidates]


def test_per_node_disabled_returns_no_candidates() -> None:
    config = MatterProbeConfig(
        enabled=True,
        mode=ProbeMode.STANDARD,
        advanced=MatterProbeAdvancedConfig(
            per_node={"24": MatterProbePerNodeOverride(disabled=True)}
        ),
    )
    candidates = MatterProbePlanner().plan(_node(), attribute_keys=frozenset(), config=config)
    assert candidates == []


def test_legacy_top_level_attributes_remain_compatible() -> None:
    config = MatterProbeConfig.model_validate(
        {
            "enabled": True,
            "attributes": {
                "fallback": ["0/40/5"],
                "window_covering": ["3/258/10"],
            },
        }
    )
    assert config.attributes.fallback == ["0/40/5"]
    assert config.attributes.window_covering == ["3/258/10"]


def test_infer_device_types_from_cluster_keys() -> None:
    assert infer_device_types(
        attribute_keys=frozenset({"2/258/10"}),
        product_name=None,
    ) == ["Window Covering"]
