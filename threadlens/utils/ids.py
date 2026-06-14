"""ID normalisation helpers."""

from __future__ import annotations

import re
import unicodedata

_HEX_ONLY = re.compile(r"[^0-9a-fA-F]")
_SLUG_INVALID = re.compile(r"[^a-z0-9_]+")
_SERVICE_ID_INVALID = re.compile(r"[^a-z0-9._-]+")


def _strip_hex_prefix(value: str) -> str:
    cleaned = value.strip()
    if cleaned.lower().startswith("0x"):
        return cleaned[2:]
    return cleaned


def normalize_ext_pan_id(value: str | None) -> str | None:
    """Normalise Extended PAN ID to lowercase compact 16-hex when valid."""
    if value is None:
        return None
    compact = _HEX_ONLY.sub("", _strip_hex_prefix(value)).lower()
    if len(compact) != 16:
        return None
    return compact


def normalize_extended_address(value: str | None) -> str | None:
    """Normalise a Thread/MAC extended address to lowercase compact 16-hex."""
    if value is None:
        return None
    compact = _HEX_ONLY.sub("", _strip_hex_prefix(value)).lower()
    if len(compact) != 16:
        return None
    return compact


def normalize_mac_address(value: str | None) -> str | None:
    """Normalise MAC address to lowercase colon-separated form when valid."""
    if value is None:
        return None
    compact = _HEX_ONLY.sub("", _strip_hex_prefix(value)).lower()
    if len(compact) != 12:
        return None
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2))


def slugify_id(value: str, *, max_length: int = 64, prefix: str = "") -> str:
    """Create a safe slug for entity IDs and internal keys."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_INVALID.sub("_", ascii_value).strip("_")
    if not slug:
        slug = "unknown"
    if prefix:
        slug = f"{prefix}_{slug}" if not slug.startswith(f"{prefix}_") else slug
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("_")
    return slug


def normalize_mdns_service_id(instance_name: str, service_type: str) -> str:
    """Normalise an mDNS/TREL service into a stable service ID."""
    instance_slug = slugify_id(instance_name, max_length=48)
    type_slug = slugify_id(service_type.replace(".local.", "").replace("._", "_"), max_length=32)
    service_id = f"{type_slug}__{instance_slug}"
    service_id = _SERVICE_ID_INVALID.sub("_", service_id.lower())
    return service_id[:96].rstrip("_")
