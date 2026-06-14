"""Parse python-matter-server node payloads into normalised metadata.

Node metadata is sourced from the Matter Basic Information cluster (cluster
id 40 / 0x28) on the root endpoint. Attribute paths use the
``<endpoint>/<cluster>/<attribute>`` string form emitted by
python-matter-server.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Basic Information cluster attribute paths on the root endpoint (endpoint 0).
ATTR_VENDOR_NAME = "0/40/1"
ATTR_VENDOR_ID = "0/40/2"
ATTR_PRODUCT_NAME = "0/40/3"
ATTR_PRODUCT_ID = "0/40/4"
ATTR_NODE_LABEL = "0/40/5"
ATTR_SOFTWARE_VERSION = "0/40/9"
ATTR_SOFTWARE_VERSION_STRING = "0/40/10"
ATTR_SERIAL_NUMBER = "0/40/15"


@dataclass(frozen=True)
class ParsedMatterNode:
    """Normalised view of a single Matter node payload.

    ``available`` is ``None`` when the payload did not carry an availability
    field at all; callers must treat that as "unchanged / unknown", never as
    unavailable.
    """

    node_id: int
    available: bool | None
    node_label: str | None = None
    vendor: str | None = None
    vendor_id: int | None = None
    product: str | None = None
    product_id: int | None = None
    serial: str | None = None
    firmware: str | None = None

    @property
    def friendly_name(self) -> str | None:
        if self.node_label:
            return self.node_label
        if self.serial:
            return self.serial
        return None


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0) if value.lower().startswith("0x") else int(value)
        except ValueError:
            return None
    return None


def parse_matter_node(payload: dict[str, Any]) -> ParsedMatterNode | None:
    """Parse a python-matter-server node dict.

    Returns ``None`` when the payload lacks a usable ``node_id``.
    """
    node_id = _clean_int(payload.get("node_id"))
    if node_id is None:
        return None

    available: bool | None = None
    if "available" in payload:
        raw = payload.get("available")
        if isinstance(raw, bool):
            available = raw

    attributes = payload.get("attributes")
    attrs: dict[str, Any] = attributes if isinstance(attributes, dict) else {}

    firmware = _clean_str(attrs.get(ATTR_SOFTWARE_VERSION_STRING))
    if firmware is None:
        sw_version = attrs.get(ATTR_SOFTWARE_VERSION)
        if sw_version is not None:
            firmware = _clean_str(sw_version)

    return ParsedMatterNode(
        node_id=node_id,
        available=available,
        node_label=_clean_str(attrs.get(ATTR_NODE_LABEL)),
        vendor=_clean_str(attrs.get(ATTR_VENDOR_NAME)),
        vendor_id=_clean_int(attrs.get(ATTR_VENDOR_ID)),
        product=_clean_str(attrs.get(ATTR_PRODUCT_NAME)),
        product_id=_clean_int(attrs.get(ATTR_PRODUCT_ID)),
        serial=_clean_str(attrs.get(ATTR_SERIAL_NUMBER)),
        firmware=firmware,
    )
