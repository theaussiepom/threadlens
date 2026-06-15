"""Home Assistant MQTT Discovery payload generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from threadlens.config import ThreadLensConfig
from threadlens.models.health import HealthReport
from threadlens.models.state import MatterNodeState
from threadlens.mqtt.topics import TopicBuilder
from threadlens.presentation.lens_mqtt import SummaryEntityState, build_summary_entities

ComponentType = Literal["sensor", "binary_sensor"]

MANUFACTURER = "ThreadLens"


@dataclass(frozen=True)
class EntityPublication:
    """Discovery config plus current state/attributes for one HA entity."""

    component: ComponentType
    object_id: str
    discovery: dict[str, Any]
    state: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PublishSnapshot:
    """Inputs for MQTT publication."""

    config: ThreadLensConfig
    version: str
    mode: str
    storage_ready: bool
    health: HealthReport
    matter_nodes: list[MatterNodeState]
    collector_status: dict[str, Any]


def build_publications(snapshot: PublishSnapshot) -> list[EntityPublication]:
    topics = TopicBuilder(snapshot.config.mqtt)
    device = _device(["threadlens_summary"], "ThreadLens", version=snapshot.version)
    availability = _availability_block(topics)
    observable = _observation_reliable(snapshot)
    summaries = build_summary_entities(
        health=snapshot.health,
        matter_nodes=snapshot.matter_nodes,
        version=snapshot.version,
        site=snapshot.config.site.name,
        observable=observable,
    )
    publications: list[EntityPublication] = []
    for summary in summaries:
        publications.append(
            _summary_publication(
                summary=summary,
                topics=topics,
                device=device,
                availability=availability,
            )
        )

    if snapshot.config.mqtt.per_node_entities:
        publications.extend(_extended_node_publications(snapshot, topics))

    return publications


def discovery_cleanup_payload() -> str:
    """Empty retained payload to remove a discovery entity in Home Assistant."""
    return ""


def _observation_reliable(snapshot: PublishSnapshot) -> bool:
    collectors = snapshot.collector_status
    matter = collectors.get("matter") or {}
    otbr = collectors.get("otbr") or {}
    if matter.get("collector_running") or otbr.get("collector_running"):
        return True
    if matter.get("connected", 0) > 0 or otbr.get("reachable", 0) > 0:
        return True
    return bool(snapshot.matter_nodes)


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


def _summary_publication(
    *,
    summary: SummaryEntityState,
    topics: TopicBuilder,
    device: dict[str, Any],
    availability: dict[str, str],
) -> EntityPublication:
    object_id = f"threadlens_{summary.key}"
    return EntityPublication(
        component="sensor",
        object_id=object_id,
        discovery={
            "name": summary.name,
            "unique_id": object_id,
            "state_topic": topics.summary(summary.key, part="state"),
            "json_attributes_topic": topics.summary(summary.key, part="attributes"),
            **availability,
            "device": device,
        },
        state=summary.state,
        attributes=summary.attributes,
    )


def _extended_node_publications(
    snapshot: PublishSnapshot,
    topics: TopicBuilder,
) -> list[EntityPublication]:
    """Optional per-node entities (off by default)."""
    from threadlens.mqtt.discovery_extended import build_matter_node_publications

    return build_matter_node_publications(snapshot, topics)
