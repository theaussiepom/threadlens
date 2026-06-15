"""OTBR REST JSON:API response parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from threadlens.utils.ids import normalize_ext_pan_id, normalize_extended_address
from threadlens.utils.network import normalize_ipv6

_OPERATIONAL_ROLES = frozenset({"detached", "child", "router", "leader"})
_THREAD_STATES = frozenset({"disabled", "detached", "child", "router", "leader"})
_NESTED_ATTRIBUTE_KEYS = (
    "leaderData",
    "activeDataset",
    "dataset",
    "network",
    "pendingDataset",
)


@dataclass(frozen=True)
class ParsedThreadDevice:
    extended_address: str
    ipv6_address: str | None = None
    rloc_address: str | None = None
    role: str | None = None
    device_type: str | None = None
    hostname: str | None = None


@dataclass(frozen=True)
class ParsedOtbrSnapshot:
    thread_state: str | None = None
    role: str | None = None
    network_name: str | None = None
    channel: int | None = None
    ext_pan_id: str | None = None
    pan_id: str | None = None
    rloc16: str | None = None
    partition_id: int | None = None
    device_count: int | None = None


@dataclass(frozen=True)
class OtbrReconciliationResult:
    snapshot: ParsedOtbrSnapshot
    thread_state_source: str
    json_api_thread_state: str | None
    legacy_node_thread_state: str | None
    rest_endpoint_mismatch: bool
    legacy_node_available: bool
    json_api_state_stale: bool


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _attributes_from_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    if isinstance(data, dict):
        attributes = data.get("attributes")
        return attributes if isinstance(attributes, dict) else {}
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("type") == "threadBorderRouter":
                attributes = item.get("attributes")
                return attributes if isinstance(attributes, dict) else {}
        if data and isinstance(data[0], dict):
            attributes = data[0].get("attributes")
            return attributes if isinstance(attributes, dict) else {}
    if any(key in payload for key in ("role", "networkName", "extPanId", "state", "channel")):
        return payload
    return {}


def _attribute_sources(attributes: dict[str, Any]) -> list[dict[str, Any]]:
    sources = [attributes]
    for key in _NESTED_ATTRIBUTE_KEYS:
        nested = attributes.get(key)
        if not isinstance(nested, dict):
            continue
        sources.append(nested)
        if key == "pendingDataset":
            active = nested.get("activeDataset")
            if isinstance(active, dict):
                sources.append(active)
    return sources


def _first_value(sources: list[dict[str, Any]], *keys: str) -> Any:
    for source in sources:
        for key in keys:
            if key not in source:
                continue
            value = _blank_to_none(source[key])
            if value is not None:
                return value
    return None


def _normalise_role(value: Any) -> str | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    return str(value).strip().lower()


def _parse_role(sources: list[dict[str, Any]]) -> str | None:
    role = _normalise_role(_first_value(sources, "role", "Role"))
    if role in _OPERATIONAL_ROLES:
        return role
    state = _normalise_role(_first_value(sources, "state", "State"))
    if state in _OPERATIONAL_ROLES:
        return state
    if role in {"disabled"} or state in {"disabled"}:
        return None
    return role


def _normalise_pan_id(value: Any) -> str | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    if isinstance(value, int):
        return f"{value:04x}"
    text = str(value).strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    if len(text) == 4 and all(ch in "0123456789abcdef" for ch in text):
        return text
    return str(value)


def _normalise_rloc16(value: Any) -> str | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    if isinstance(value, int):
        return f"{value:04x}"
    text = str(value).strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    return text or None


def _parse_channel(value: Any) -> int | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_partition_id(sources: list[dict[str, Any]]) -> int | None:
    value = _first_value(sources, "partitionId", "PartitionId")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_thread_state(attributes: dict[str, Any]) -> str | None:
    value = _normalise_role(_blank_to_none(attributes.get("state") or attributes.get("State")))
    if value in _THREAD_STATES:
        return value
    return None


def thread_stack_active(thread_state: str | None) -> bool:
    return thread_state in _OPERATIONAL_ROLES


def _snapshot_from_attributes(attributes: dict[str, Any]) -> ParsedOtbrSnapshot:
    sources = _attribute_sources(attributes)
    ext_pan_id = normalize_ext_pan_id(
        _first_value(sources, "extPanId", "extendedPanId", "ExtPanId", "xp")
    )
    return ParsedOtbrSnapshot(
        thread_state=_parse_thread_state(attributes),
        role=_parse_role(sources),
        network_name=_first_value(sources, "networkName", "NetworkName", "name"),
        channel=_parse_channel(_first_value(sources, "channel", "Channel")),
        ext_pan_id=ext_pan_id,
        pan_id=_normalise_pan_id(_first_value(sources, "panId", "panid", "PanId")),
        rloc16=_normalise_rloc16(_first_value(sources, "rloc16", "rloc", "Rloc16")),
        partition_id=_parse_partition_id(sources),
    )


def parse_otbr_node_response(payload: Any) -> ParsedOtbrSnapshot:
    return _snapshot_from_attributes(_attributes_from_payload(payload))


def parse_legacy_node_response(payload: Any) -> ParsedOtbrSnapshot:
    """Parse legacy flattened ``GET /node`` OTBR REST responses."""
    if isinstance(payload, dict):
        return _snapshot_from_attributes(payload)
    return ParsedOtbrSnapshot()


def _materially_differs(
    json_api_state: str | None,
    legacy_state: str | None,
) -> bool:
    if json_api_state is None or legacy_state is None:
        return False
    return json_api_state != legacy_state


def _prefer_legacy_snapshot(
    json_api: ParsedOtbrSnapshot,
    legacy: ParsedOtbrSnapshot,
) -> ParsedOtbrSnapshot:
    legacy_role = legacy.role or (
        legacy.thread_state if legacy.thread_state in _OPERATIONAL_ROLES else None
    )
    return ParsedOtbrSnapshot(
        thread_state=legacy.thread_state,
        role=legacy_role,
        network_name=legacy.network_name or json_api.network_name,
        channel=legacy.channel if legacy.channel is not None else json_api.channel,
        ext_pan_id=legacy.ext_pan_id or json_api.ext_pan_id,
        pan_id=legacy.pan_id or json_api.pan_id,
        rloc16=legacy.rloc16 or json_api.rloc16,
        partition_id=(
            legacy.partition_id if legacy.partition_id is not None else json_api.partition_id
        ),
        device_count=json_api.device_count,
    )


def reconcile_otbr_snapshots(
    json_api: ParsedOtbrSnapshot,
    legacy: ParsedOtbrSnapshot | None,
    *,
    legacy_available: bool,
    use_legacy_fallback: bool,
) -> OtbrReconciliationResult:
    json_state = json_api.thread_state
    legacy_state = legacy.thread_state if legacy is not None else None
    mismatch = _materially_differs(json_state, legacy_state)
    source = "json_api"
    effective = json_api
    json_api_state_stale = False

    if legacy_available and legacy is not None and use_legacy_fallback:
        if json_state == "disabled" and legacy_state in _OPERATIONAL_ROLES:
            effective = _prefer_legacy_snapshot(json_api, legacy)
            source = "legacy_node"
            json_api_state_stale = True
        elif (
            json_state in _OPERATIONAL_ROLES
            and legacy_state in _OPERATIONAL_ROLES
            and json_state != legacy_state
        ):
            effective = _prefer_legacy_snapshot(json_api, legacy)
            source = "legacy_node"
    elif json_state is None:
        source = "unknown"

    return OtbrReconciliationResult(
        snapshot=effective,
        thread_state_source=source,
        json_api_thread_state=json_state,
        legacy_node_thread_state=legacy_state,
        rest_endpoint_mismatch=mismatch,
        legacy_node_available=legacy_available,
        json_api_state_stale=json_api_state_stale,
    )


def parse_otbr_devices_response(payload: Any) -> ParsedOtbrSnapshot:
    attributes = _attributes_from_payload(payload)
    device_count = None
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        device_count = len(payload["data"])
    if not attributes and isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            border_routers = [
                item
                for item in data
                if isinstance(item, dict) and item.get("type") == "threadBorderRouter"
            ]
            if border_routers:
                item_attributes = border_routers[0].get("attributes")
                if isinstance(item_attributes, dict):
                    attributes = item_attributes
    snapshot = _snapshot_from_attributes(attributes)
    if device_count is not None:
        return ParsedOtbrSnapshot(
            thread_state=snapshot.thread_state,
            role=snapshot.role,
            network_name=snapshot.network_name,
            channel=snapshot.channel,
            ext_pan_id=snapshot.ext_pan_id,
            pan_id=snapshot.pan_id,
            rloc16=snapshot.rloc16,
            partition_id=snapshot.partition_id,
            device_count=device_count,
        )
    return snapshot


def merge_snapshots(*snapshots: ParsedOtbrSnapshot) -> ParsedOtbrSnapshot:
    merged = ParsedOtbrSnapshot()
    for snapshot in snapshots:
        merged = ParsedOtbrSnapshot(
            thread_state=merged.thread_state or snapshot.thread_state,
            role=merged.role or snapshot.role,
            network_name=merged.network_name or snapshot.network_name,
            channel=merged.channel if merged.channel is not None else snapshot.channel,
            ext_pan_id=merged.ext_pan_id or snapshot.ext_pan_id,
            pan_id=merged.pan_id or snapshot.pan_id,
            rloc16=merged.rloc16 or snapshot.rloc16,
            partition_id=(
                merged.partition_id if merged.partition_id is not None else snapshot.partition_id
            ),
            device_count=merged.device_count
            if merged.device_count is not None
            else snapshot.device_count,
        )
    return merged


def _normalise_ipv6_field(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            normalized = _normalise_ipv6_field(item)
            if normalized:
                return normalized
        return None
    return normalize_ipv6(str(value))


def parse_otbr_device_inventory(payload: Any) -> list[ParsedThreadDevice]:
    """Parse per-device Thread inventory from ``GET /api/devices``."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []

    devices: list[ParsedThreadDevice] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            continue
        ext_address = normalize_extended_address(
            str(attributes.get("extAddress") or item.get("id") or "")
        )
        if ext_address is None:
            continue
        devices.append(
            ParsedThreadDevice(
                extended_address=ext_address,
                ipv6_address=_normalise_ipv6_field(attributes.get("omrIpv6Address")),
                rloc_address=_normalise_ipv6_field(attributes.get("rlocAddress")),
                role=_normalise_role(_blank_to_none(attributes.get("role"))),
                device_type=str(item.get("type") or "").strip() or None,
                hostname=_blank_to_none(attributes.get("hostName") or attributes.get("hostname")),
            )
        )
    return devices
