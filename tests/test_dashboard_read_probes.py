"""Dashboard read probe integration tests."""

from __future__ import annotations

from threadlens.server.dashboard import (
    _build_read_probe_block,
    _node_entry,
    classify_matter_node,
)


def _node(**overrides) -> dict:
    base = {
        "node_id": 24,
        "server_id": "study",
        "available": True,
        "friendly_name": "Living Blind 3",
        "read_probe_diagnostics_available": False,
    }
    base.update(overrides)
    return base


def test_classify_matter_node_unchanged_without_probe_diagnostics() -> None:
    assert classify_matter_node(_node(), []) == "healthy"


def test_classify_read_probe_failure_as_recently_unstable() -> None:
    node = _node(
        read_probe_diagnostics_available=True,
        last_read_probe_ok=False,
        read_probe_failures_24h=1,
    )
    assert classify_matter_node(node, []) == "recently_unstable"


def test_classify_repeated_read_probe_failures_as_needs_attention() -> None:
    node = _node(
        read_probe_diagnostics_available=True,
        last_read_probe_ok=False,
        read_probe_failures_24h=3,
    )
    assert classify_matter_node(node, []) == "needs_attention"


def test_classify_unsupported_read_probe_as_diagnostics_limited() -> None:
    node = _node(
        read_probe_diagnostics_available=True,
        last_read_probe_ok=None,
        last_read_probe_limited=True,
    )
    assert classify_matter_node(node, []) == "diagnostics_limited"


def test_unavailable_remains_dominant_over_probe_failure() -> None:
    node = _node(
        available=False,
        read_probe_diagnostics_available=True,
        last_read_probe_ok=False,
        read_probe_failures_24h=5,
    )
    assert classify_matter_node(node, []) == "unavailable"


def test_read_probe_block_exposes_friendly_overview_labels() -> None:
    ok_block = _build_read_probe_block(
        _node(
            read_probe_diagnostics_available=True,
            last_read_probe_ok=True,
            last_probe_label="Basic read check",
        )
    )
    assert ok_block["overview_label"] == "Read checks OK"
    assert ok_block["probe_label"] == "Basic read check"

    limited_block = _build_read_probe_block(
        _node(
            read_probe_diagnostics_available=True,
            last_read_probe_limited=True,
            last_probe_label="Blind status read check",
        )
    )
    assert limited_block["overview_label"] == "Read diagnostics limited"


def test_node_entry_includes_read_probe_block() -> None:
    node = _node(
        read_probe_diagnostics_available=True,
        last_read_probe_ok=False,
        last_read_probe_attribute_path="0/40/5",
        last_read_probe_duration_ms=842,
        read_probe_failures_24h=2,
        read_probe_successes_24h=5,
    )
    entry = _node_entry(node, [])
    assert entry["read_probe"]["diagnostics_available"] is True
    assert entry["read_probe"]["last_ok"] is False
    assert entry["read_probe"]["attribute_path"] == "0/40/5"
    assert "read probe" in entry["read_probe"]["summary"].lower()
    assert "command failed" not in entry["read_probe"]["summary"].lower()


def test_read_probe_summary_uses_careful_wording() -> None:
    block = _build_read_probe_block(
        {
            "available": True,
            "read_probe_diagnostics_available": True,
            "last_read_probe_ok": False,
            "read_probe_failures_24h": 1,
        }
    )
    assert block["summary"] is not None
    assert "does not prove commands are failing" in block["summary"]
