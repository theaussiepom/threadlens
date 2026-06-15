"""Network helper tests."""

from __future__ import annotations

from threadlens.utils.network import extract_ping_ipv6, normalize_ipv6


def test_normalize_ipv6() -> None:
    assert (
        normalize_ipv6("FD22:C1B2:8661:1:A87B:2DBB:E992:5426")
        == "fd22:c1b2:8661:1:a87b:2dbb:e992:5426"
    )
    assert normalize_ipv6("::") is None


def test_extract_ping_ipv6() -> None:
    assert (
        extract_ping_ipv6({"fd22:c1b2:8661:1:a87b:2dbb:e992:5426": True})
        == "fd22:c1b2:8661:1:a87b:2dbb:e992:5426"
    )
    assert extract_ping_ipv6({"fd22:c1b2:8661:1:a87b:2dbb:e992:5426": False}) is None
