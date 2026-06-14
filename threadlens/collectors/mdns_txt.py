"""mDNS TXT record decoding helpers."""

from __future__ import annotations

from typing import Any

from threadlens.utils.ids import normalize_ext_pan_id, normalize_extended_address

TREL_SERVICE_SUFFIX = "_trel._udp.local."
TREL_TXT_EXT_PAN_ID_KEY = "xp"
TREL_TXT_EXT_ADDRESS_KEY = "xa"


def decode_txt_key(key: Any) -> str:
    if isinstance(key, bytes):
        return key.decode("utf-8", errors="replace")
    return str(key)


def decode_txt_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def decode_txt_properties(properties: dict[Any, Any] | None) -> dict[str, str]:
    """Decode zeroconf TXT properties safely without raising."""
    if not properties:
        return {}
    decoded: dict[str, str] = {}
    for key, value in properties.items():
        try:
            decoded[decode_txt_key(key)] = decode_txt_value(value)
        except Exception:
            continue
    return decoded


def ext_pan_id_from_txt(
    txt_records: dict[str, str], *, raw_properties: dict[Any, Any] | None = None
) -> str | None:
    """Extract and normalise Extended PAN ID from TREL TXT."""
    if raw_properties:
        raw = raw_properties.get(TREL_TXT_EXT_PAN_ID_KEY) or raw_properties.get(
            TREL_TXT_EXT_PAN_ID_KEY.encode()
        )
        if isinstance(raw, bytes) and len(raw) == 8:
            return normalize_ext_pan_id(raw.hex())
    value = txt_records.get(TREL_TXT_EXT_PAN_ID_KEY)
    if value is None:
        return None
    return normalize_ext_pan_id(value)


def ext_address_from_txt(
    txt_records: dict[str, str], *, raw_properties: dict[Any, Any] | None = None
) -> str | None:
    """Extract and normalise extended address from TREL TXT."""
    if raw_properties:
        raw = raw_properties.get(TREL_TXT_EXT_ADDRESS_KEY) or raw_properties.get(
            TREL_TXT_EXT_ADDRESS_KEY.encode()
        )
        if isinstance(raw, bytes) and len(raw) == 8:
            return normalize_extended_address(raw.hex())
    value = txt_records.get(TREL_TXT_EXT_ADDRESS_KEY)
    if value is None:
        return None
    return normalize_extended_address(value)


def is_trel_service_type(service_type: str) -> bool:
    normalised = service_type.strip().lower().rstrip(".")
    return normalised == "_trel._udp.local" or normalised.endswith("._trel._udp.local")
