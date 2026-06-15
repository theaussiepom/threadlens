"""Correlate Matter nodes with observed Thread device inventory."""

from __future__ import annotations

from typing import Any

from threadlens.models.state import MatterNodeState, ThreadDeviceState
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.network import normalize_ipv6


def build_thread_device_index(
    devices: list[ThreadDeviceState | dict[str, Any]],
) -> dict[str, str]:
    """Map normalised Thread IPv6 addresses to extended addresses."""
    index: dict[str, str] = {}
    for device in devices:
        if isinstance(device, ThreadDeviceState):
            payload = device.model_dump(mode="json")
        elif isinstance(device, dict):
            payload = device
        else:
            continue
        ext_address = payload.get("extended_address")
        ipv6 = normalize_ipv6(payload.get("ipv6_address"))
        if ext_address and ipv6:
            index[ipv6] = str(ext_address)
    return index


def correlate_thread_identity(
    node: MatterNodeState | dict[str, Any],
    *,
    thread_index: dict[str, str],
) -> dict[str, Any]:
    """Return thread identity fields for a Matter node when observed data matches."""
    if isinstance(node, MatterNodeState):
        payload = node.model_dump(mode="json")
    else:
        payload = dict(node)

    ipv6 = normalize_ipv6(payload.get("thread_ipv6_address"))
    ext_address = payload.get("thread_extended_address")
    if ipv6 and not ext_address:
        ext_address = thread_index.get(ipv6)

    available = bool(ipv6 or ext_address)
    return {
        "thread_ipv6_address": ipv6,
        "thread_extended_address": ext_address,
        "thread_identity_available": available,
    }


async def apply_thread_identity_correlation(repository: StorageRepository) -> int:
    """Persist Thread extended addresses onto Matter nodes when IPv6 matches inventory."""
    thread_devices = await repository.list_current_state(CurrentStateType.THREAD_DEVICE)
    thread_index = build_thread_device_index(thread_devices)
    if not thread_index:
        return 0

    matter_nodes = await repository.list_current_state(CurrentStateType.MATTER_NODE)
    updated = 0
    for raw in matter_nodes:
        node = MatterNodeState.model_validate(raw)
        correlated = correlate_thread_identity(node, thread_index=thread_index)
        next_ext = correlated["thread_extended_address"]
        next_ipv6 = correlated["thread_ipv6_address"]
        if next_ext == node.thread_extended_address and next_ipv6 == node.thread_ipv6_address:
            continue
        await repository.upsert_model_state(
            CurrentStateType.MATTER_NODE,
            f"matter_node:{node.server_id}:{node.node_id}",
            node.model_copy(
                update={
                    "thread_extended_address": next_ext,
                    "thread_ipv6_address": next_ipv6,
                }
            ),
        )
        updated += 1
    return updated
