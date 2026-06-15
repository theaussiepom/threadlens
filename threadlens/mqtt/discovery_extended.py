"""Optional extended MQTT entities (per-node; off by default)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from threadlens.models.health import HealthState
from threadlens.models.state import MatterNodeState
from threadlens.mqtt.discovery import EntityPublication, PublishSnapshot
from threadlens.mqtt.topics import TopicBuilder
from threadlens.utils.ids import slugify_id

MANUFACTURER = "ThreadLens"


def _availability_block(topics: TopicBuilder) -> dict[str, str]:
    return {
        "availability_topic": topics.availability,
        "payload_available": "online",
        "payload_not_available": "offline",
    }


def _device(identifiers: list[str], name: str, *, version: str) -> dict[str, Any]:
    return {
        "identifiers": identifiers,
        "name": name,
        "manufacturer": MANUFACTURER,
        "model": "ThreadLens",
        "sw_version": version,
    }


def _health_state_value(state: HealthState) -> str:
    return state.value


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _read_probe_ok_state(node: MatterNodeState) -> str:
    if not node.read_probe_diagnostics_available:
        return "unknown"
    if node.last_read_probe_limited or node.last_read_probe_ok is None:
        return "unknown"
    return "ON" if node.last_read_probe_ok else "OFF"


def build_matter_node_publications(
    snapshot: PublishSnapshot,
    topics: TopicBuilder,
) -> list[EntityPublication]:
    publications: list[EntityPublication] = []
    health_by_id = {item.id: item for item in snapshot.health.matter_nodes}
    for node in snapshot.matter_nodes:
        subject_id = f"matter_node:{node.server_id}:{node.node_id}"
        health = health_by_id.get(subject_id)
        server_slug = slugify_id(node.server_id, max_length=32)
        node_slug = f"{server_slug}_{node.node_id}"
        display = node.friendly_name or f"Node {node.node_id}"
        device = _device(
            [f"threadlens_matter_node_{node_slug}"],
            f"Matter Node - {display}",
            version=snapshot.version,
        )
        availability = _availability_block(topics)
        attrs = {
            "node_id": node.node_id,
            "server_id": node.server_id,
            "friendly_name": node.friendly_name,
            "read_probe_diagnostics_available": node.read_probe_diagnostics_available,
            "last_read_probe_ok": node.last_read_probe_ok,
            "last_read_probe_limited": node.last_read_probe_limited,
            "read_probe_failures_24h": node.read_probe_failures_24h,
            "health_reasons": health.reasons if health else [],
        }
        node_entities: list[EntityPublication] = [
            EntityPublication(
                component="sensor",
                object_id=f"threadlens_matter_node_{node_slug}_health",
                discovery={
                    "name": f"Matter Node {display} Health",
                    "unique_id": f"threadlens_matter_node_{node_slug}_health",
                    "state_topic": topics.matter_node(node.server_id, node.node_id, "health"),
                    "json_attributes_topic": topics.matter_node(
                        node.server_id, node.node_id, "health", part="attributes"
                    ),
                    **availability,
                    "device": device,
                },
                state=_health_state_value(health.state if health else HealthState.UNKNOWN),
                attributes=attrs,
            ),
        ]
        if node.read_probe_diagnostics_available:
            node_entities.extend(
                [
                    EntityPublication(
                        component="binary_sensor",
                        object_id=f"threadlens_matter_node_{node_slug}_read_probe_ok",
                        discovery={
                            "name": f"Matter Node {display} Read Probe OK",
                            "unique_id": (f"threadlens_matter_node_{node_slug}_read_probe_ok"),
                            "state_topic": topics.matter_node(
                                node.server_id, node.node_id, "read_probe_ok"
                            ),
                            "json_attributes_topic": topics.matter_node(
                                node.server_id,
                                node.node_id,
                                "read_probe_ok",
                                part="attributes",
                            ),
                            "payload_on": "ON",
                            "payload_off": "OFF",
                            **availability,
                            "device": device,
                        },
                        state=_read_probe_ok_state(node),
                        attributes=attrs,
                    ),
                    EntityPublication(
                        component="sensor",
                        object_id=f"threadlens_matter_node_{node_slug}_read_probe_failures_24h",
                        discovery={
                            "name": f"Matter Node {display} Read Probe Failures 24h",
                            "unique_id": (
                                f"threadlens_matter_node_{node_slug}_read_probe_failures_24h"
                            ),
                            "state_topic": topics.matter_node(
                                node.server_id,
                                node.node_id,
                                "read_probe_failures_24h",
                            ),
                            "json_attributes_topic": topics.matter_node(
                                node.server_id,
                                node.node_id,
                                "read_probe_failures_24h",
                                part="attributes",
                            ),
                            **availability,
                            "device": device,
                        },
                        state=(
                            str(node.read_probe_failures_24h)
                            if node.read_probe_failures_24h is not None
                            else "unknown"
                        ),
                        attributes=attrs,
                    ),
                ]
            )
        publications.extend(node_entities)
    return publications
