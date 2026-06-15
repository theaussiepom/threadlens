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
    config = MatterProbeConfig(mode=ProbeMode.CONSERVATIVE)
    node = _node(product="Living Blind")
    planner = MatterProbePlanner()
    candidates = planner.plan(
        node,
        attribute_keys=frozenset({"2/258/10", "0/40/2"}),
        config=config,
    )
    kinds = [candidate.kind for candidate in candidates]
    assert "window_covering_status" not in kinds
    assert candidates[0].kind == "discovered"
    assert candidates[0].attribute_path == "0/40/2"
    assert "0/40/2" in [candidate.attribute_path for candidate in candidates]


def test_standard_mode_adds_window_covering_from_endpoint_data() -> None:
    config = MatterProbeConfig(mode=ProbeMode.STANDARD)
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
    assert candidates[0].kind == "window_covering_status"
    assert candidates[0].attribute_path == "2/258/10"


def test_standard_mode_device_specific_before_generic_fallback() -> None:
    config = MatterProbeConfig(mode=ProbeMode.STANDARD)
    node = _node(product="Dendo SCM Matter Shade")
    candidates = MatterProbePlanner().plan(
        node,
        attribute_keys=frozenset({"0/40/2"}),
        config=config,
    )
    assert candidates[0].kind == "window_covering_status"
    assert candidates[0].attribute_path == "1/258/10"
    assert any(candidate.kind == "basic_information" for candidate in candidates)


def test_standard_mode_uses_inferred_window_covering_fallback_path() -> None:
    config = MatterProbeConfig(mode=ProbeMode.STANDARD)
    node = _node(product="Living Shade", inferred_device_types=["Window Covering"])
    candidates = MatterProbePlanner().plan(
        node,
        attribute_keys=frozenset({"0/40/2"}),
        config=config,
    )
    assert candidates[0].attribute_path == "1/258/10"


def test_conservative_mode_excludes_descriptor_reads() -> None:
    config = MatterProbeConfig(mode=ProbeMode.CONSERVATIVE)
    candidates = MatterProbePlanner().plan(
        _node(),
        attribute_keys=frozenset({"0/29/0", "0/40/2"}),
        config=config,
    )
    assert all(candidate.kind != "descriptor" for candidate in candidates)


def test_per_node_override_is_first_candidate() -> None:
    config = MatterProbeConfig(
        mode=ProbeMode.CONSERVATIVE,
        advanced=MatterProbeAdvancedConfig(
            per_node={"24": MatterProbePerNodeOverride(preferred=["0/40/4"])}
        ),
    )
    candidates = MatterProbePlanner().plan(_node(), attribute_keys=frozenset(), config=config)
    assert candidates[0].attribute_path == "0/40/4"
    assert candidates[0].health_weight == "override"


def test_last_successful_probe_is_reused_before_generic_fallback() -> None:
    config = MatterProbeConfig(mode=ProbeMode.CONSERVATIVE)
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
    config = MatterProbeConfig(mode=ProbeMode.CONSERVATIVE)
    candidates = MatterProbePlanner().plan(
        _node(last_unsupported_probe_paths=["1/258/10"]),
        attribute_keys=frozenset({"1/258/10", "0/40/2"}),
        config=config,
    )
    assert "1/258/10" not in [candidate.attribute_path for candidate in candidates]


def test_per_node_disabled_returns_no_candidates() -> None:
    config = MatterProbeConfig(
        mode=ProbeMode.STANDARD,
        advanced=MatterProbeAdvancedConfig(
            per_node={"24": MatterProbePerNodeOverride(disabled=True)}
        ),
    )
    candidates = MatterProbePlanner().plan(_node(), attribute_keys=frozenset(), config=config)
    assert candidates == []


def test_legacy_top_level_fields_are_rejected() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MatterProbeConfig.model_validate(
            {
                "mode": "conservative",
                "interval_seconds": 1800,
                "attributes": {"fallback": ["0/40/5"]},
            }
        )


def test_discovered_candidates_use_node_attribute_keys() -> None:
    config = MatterProbeConfig(mode=ProbeMode.CONSERVATIVE)
    keys = frozenset({"2/258/10", "2/258/0", "0/40/2", "0/40/5"})
    candidates = MatterProbePlanner().plan(
        _node(),
        attribute_keys=keys,
        config=config,
    )
    paths = [candidate.attribute_path for candidate in candidates]
    assert "0/40/2" in paths
    assert "2/258/10" in paths
    assert paths.index("0/40/2") < paths.index("2/258/10")


def test_discovered_candidates_skip_unsupported_paths() -> None:
    config = MatterProbeConfig(mode=ProbeMode.STANDARD)
    candidates = MatterProbePlanner().plan(
        _node(last_unsupported_probe_paths=["2/258/10"]),
        attribute_keys=frozenset({"2/258/10", "2/258/0", "0/40/2"}),
        config=config,
    )
    paths = [candidate.attribute_path for candidate in candidates]
    assert "2/258/10" not in paths
    assert "2/258/0" in paths


def test_discovered_candidates_support_non_covering_devices() -> None:
    config = MatterProbeConfig(mode=ProbeMode.CONSERVATIVE)
    keys = frozenset({"0/40/2", "0/40/5", "0/6/0"})
    candidates = MatterProbePlanner().plan(
        _node(product="Kitchen Light"),
        attribute_keys=keys,
        config=config,
    )
    kinds = [candidate.kind for candidate in candidates]
    paths = [candidate.attribute_path for candidate in candidates]
    assert "window_covering_status" not in kinds
    assert "0/40/2" in paths
    assert candidates[0].kind == "discovered"
    assert candidates[0].label == "Device info read check"


def test_infer_device_types_from_cluster_keys() -> None:
    assert infer_device_types(
        attribute_keys=frozenset({"2/258/10"}),
        product_name=None,
    ) == ["Window Covering"]
