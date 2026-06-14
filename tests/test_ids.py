"""ID normalisation tests."""

from __future__ import annotations

from threadlens.utils.ids import (
    normalize_ext_pan_id,
    normalize_extended_address,
    normalize_mac_address,
    normalize_mdns_service_id,
    slugify_id,
)


def test_normalize_ext_pan_id_variants() -> None:
    assert normalize_ext_pan_id("D6F401F0227E1EC0") == "d6f401f0227e1ec0"
    assert normalize_ext_pan_id("0xD6F401F0227E1EC0") == "d6f401f0227e1ec0"
    assert normalize_ext_pan_id("d6:f4:01:f0:22:7e:1e:c0") == "d6f401f0227e1ec0"
    assert normalize_ext_pan_id("too-short") is None
    assert normalize_ext_pan_id(None) is None


def test_normalize_extended_address() -> None:
    assert normalize_extended_address("AABBCCDDEEFF0011") == "aabbccddeeff0011"
    assert normalize_extended_address("invalid") is None


def test_normalize_mac_address() -> None:
    assert normalize_mac_address("AABBCCDDEEFF") == "aa:bb:cc:dd:ee:ff"
    assert normalize_mac_address("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"
    assert normalize_mac_address("bad") is None


def test_slugify_id() -> None:
    assert slugify_id("Living Blind 3") == "living_blind_3"
    assert slugify_id("Study OTBR!", prefix="otbr") == "otbr_study_otbr"
    assert slugify_id("@@@", prefix="node") == "node_unknown"


def test_normalize_mdns_service_id() -> None:
    service_id = normalize_mdns_service_id(
        "example-host._trel._udp.local.",
        "_trel._udp.local.",
    )
    assert service_id.startswith("trel_udp__")
    assert " " not in service_id
