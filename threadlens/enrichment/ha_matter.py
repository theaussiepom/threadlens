"""Home Assistant Matter device name enrichment."""

from __future__ import annotations

from typing import Any

from threadlens.models.state import MatterNodeState
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.time import utc_now

MAX_DEVICES = 500


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if not key.startswith("_")}


async def apply_ha_matter_device_names(
    repository: StorageRepository,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Apply Home Assistant device names to stored Matter node state."""
    devices = payload.get("devices") or []
    if not isinstance(devices, list):
        raise ValueError("devices must be a list")
    if len(devices) > MAX_DEVICES:
        raise ValueError(f"devices payload exceeds limit of {MAX_DEVICES}")

    stored = await repository.list_current_state(CurrentStateType.MATTER_NODE)
    nodes_by_key: dict[tuple[str, int], MatterNodeState] = {}
    for raw in stored:
        node = MatterNodeState.model_validate(_clean_payload(raw))
        nodes_by_key[(node.server_id, node.node_id)] = node

    updated = 0
    for entry in devices:
        if not isinstance(entry, dict):
            continue
        server_id = entry.get("server_id")
        node_id = entry.get("node_id")
        ha_device_name = entry.get("ha_device_name")
        if not server_id or node_id is None or not ha_device_name:
            continue
        try:
            node_key = (str(server_id), int(node_id))
        except (TypeError, ValueError):
            continue

        node = nodes_by_key.get(node_key)
        if node is None:
            continue

        ha_entity_id = entry.get("ha_entity_id")
        entity_id = str(ha_entity_id).strip() if ha_entity_id else None
        updated_node = node.model_copy(
            update={
                "ha_device_name": str(ha_device_name).strip(),
                "ha_entity_id": entity_id or None,
            }
        )
        await repository.upsert_model_state(
            CurrentStateType.MATTER_NODE,
            f"matter_node:{node_key[0]}:{node_key[1]}",
            updated_node,
        )
        nodes_by_key[node_key] = updated_node
        updated += 1

    now = utc_now()
    return {
        "matched_devices": updated,
        "last_push_at": now.isoformat(),
        "source": str(payload.get("source") or "homeassistant"),
    }
