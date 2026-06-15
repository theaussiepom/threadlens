"""Thread/Matter identity correlation tests."""

from __future__ import annotations

from threadlens.enrichment.thread_matter import (
    build_thread_device_index,
    correlate_thread_identity,
)
from threadlens.models.state import MatterNodeState


def test_correlate_thread_identity_from_ipv6() -> None:
    index = build_thread_device_index(
        [
            {
                "extended_address": "3ec12f62981d06e3",
                "ipv6_address": "fd22:c1b2:8661:1:a87b:2dbb:e992:5426",
            }
        ]
    )
    node = MatterNodeState(
        node_id=27,
        server_id="study_matter",
        thread_ipv6_address="fd22:c1b2:8661:1:a87b:2dbb:e992:5426",
    )
    correlated = correlate_thread_identity(node, thread_index=index)
    assert correlated["thread_extended_address"] == "3ec12f62981d06e3"
    assert correlated["thread_identity_available"] is True
