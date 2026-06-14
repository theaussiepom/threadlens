"""Home Assistant MQTT Discovery payload generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from threadlens.config import ThreadLensConfig
from threadlens.models.health import (
    HealthReport,
    HealthState,
)
from threadlens.models.state import (
    MatterNodeState,
    MatterServerState,
    OtbrState,
    ThreadNetworkClassification,
    ThreadNetworkState,
)
from threadlens.mqtt.topics import TopicBuilder
from threadlens.utils.ids import slugify_id

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
    otbr_states: list[OtbrState]
    matter_servers: list[MatterServerState]
    matter_nodes: list[MatterNodeState]
    thread_networks: list[ThreadNetworkState]
    collector_status: dict[str, Any]
    report_url: str = "http://127.0.0.1:8128/api/v1/report.yaml"
    report_last_generated_at: str | None = None


def build_publications(snapshot: PublishSnapshot) -> list[EntityPublication]:
    topics = TopicBuilder(snapshot.config.mqtt)
    publications: list[EntityPublication] = []
    publications.extend(_diagnostics_entities(snapshot, topics))
    publications.extend(_environment_entities(snapshot, topics))
    publications.extend(_thread_network_entities(snapshot, topics))
    publications.extend(_otbr_entities(snapshot, topics))
    publications.extend(_matter_server_entities(snapshot, topics))
    if snapshot.config.mqtt.per_node_entities:
        publications.extend(_matter_node_entities(snapshot, topics))
    return publications


def discovery_cleanup_payload() -> str:
    """Empty retained payload to remove a discovery entity in Home Assistant."""
    return ""


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


def _diagnostics_entities(
    snapshot: PublishSnapshot,
    topics: TopicBuilder,
) -> list[EntityPublication]:
    device = _device(["threadlens_diagnostics"], "ThreadLens Diagnostics", version=snapshot.version)
    availability = _availability_block(topics)
    base_attrs = {
        "version": snapshot.version,
        "mode": snapshot.mode,
        "site": snapshot.config.site.name,
        "storage_ready": snapshot.storage_ready,
        "health_reasons": snapshot.health.overall.reasons,
        "collectors": snapshot.collector_status,
    }
    return [
        EntityPublication(
            component="sensor",
            object_id="threadlens_health",
            discovery={
                "name": "ThreadLens Health",
                "unique_id": "threadlens_health",
                "state_topic": topics.diagnostics("health"),
                "json_attributes_topic": topics.diagnostics("health", part="attributes"),
                **availability,
                "device": device,
            },
            state=_health_state_value(snapshot.health.overall.state),
            attributes=base_attrs,
        ),
        EntityPublication(
            component="sensor",
            object_id="threadlens_event_count_24h",
            discovery={
                "name": "ThreadLens Event Count 24h",
                "unique_id": "threadlens_event_count_24h",
                "state_topic": topics.diagnostics("event_count_24h"),
                "json_attributes_topic": topics.diagnostics("event_count_24h", part="attributes"),
                **availability,
                "device": device,
            },
            state=str(snapshot.health.summary.events_24h),
            attributes=base_attrs,
        ),
        EntityPublication(
            component="sensor",
            object_id="threadlens_warning_count_24h",
            discovery={
                "name": "ThreadLens Warning Count 24h",
                "unique_id": "threadlens_warning_count_24h",
                "state_topic": topics.diagnostics("warning_count_24h"),
                "json_attributes_topic": topics.diagnostics("warning_count_24h", part="attributes"),
                **availability,
                "device": device,
            },
            state=str(snapshot.health.summary.warnings_24h),
            attributes=base_attrs,
        ),
        EntityPublication(
            component="binary_sensor",
            object_id="threadlens_running",
            discovery={
                "name": "ThreadLens Running",
                "unique_id": "threadlens_running",
                "state_topic": topics.diagnostics("running"),
                "json_attributes_topic": topics.diagnostics("running", part="attributes"),
                "payload_on": "ON",
                "payload_off": "OFF",
                **availability,
                "device": device,
            },
            state="ON",
            attributes=base_attrs,
        ),
        EntityPublication(
            component="sensor",
            object_id="threadlens_report_url",
            discovery={
                "name": "ThreadLens Report URL",
                "unique_id": "threadlens_report_url",
                "state_topic": topics.diagnostics("report_url"),
                "json_attributes_topic": topics.diagnostics("report_url", part="attributes"),
                **availability,
                "device": device,
            },
            state=snapshot.report_url,
            attributes={**base_attrs, "report_url": snapshot.report_url},
        ),
        EntityPublication(
            component="sensor",
            object_id="threadlens_last_report_generated_at",
            discovery={
                "name": "ThreadLens Last Report Generated At",
                "unique_id": "threadlens_last_report_generated_at",
                "state_topic": topics.diagnostics("last_report_generated_at"),
                "json_attributes_topic": topics.diagnostics(
                    "last_report_generated_at", part="attributes"
                ),
                **availability,
                "device": device,
            },
            state=snapshot.report_last_generated_at or "unknown",
            attributes={
                **base_attrs,
                "last_report_generated_at": snapshot.report_last_generated_at,
            },
        ),
    ]


def _environment_entities(
    snapshot: PublishSnapshot,
    topics: TopicBuilder,
) -> list[EntityPublication]:
    device = _device(
        ["threadlens_environment"],
        "Thread Environment Health",
        version=snapshot.version,
    )
    availability = _availability_block(topics)
    attrs = {
        "health_reasons": snapshot.health.environment.reasons,
        "otbrs_configured": snapshot.health.summary.otbrs_configured,
        "otbrs_reachable": snapshot.health.summary.otbrs_reachable,
        "matter_servers_configured": snapshot.health.summary.matter_servers_configured,
        "matter_servers_connected": snapshot.health.summary.matter_servers_connected,
        "mdns": snapshot.collector_status.get("mdns"),
        "trel_health_state": snapshot.health.trel.state.value,
        "trel_health_reasons": snapshot.health.trel.reasons,
        "mdns_health_state": snapshot.health.mdns.state.value,
        "mdns_health_reasons": snapshot.health.mdns.reasons,
    }
    return [
        EntityPublication(
            component="sensor",
            object_id="threadlens_environment_health",
            discovery={
                "name": "Thread Environment Health",
                "unique_id": "threadlens_environment_health",
                "state_topic": topics.environment("health"),
                "json_attributes_topic": topics.environment("health", part="attributes"),
                **availability,
                "device": device,
            },
            state=_health_state_value(snapshot.health.environment.state),
            attributes=attrs,
        ),
        EntityPublication(
            component="sensor",
            object_id="threadlens_thread_network_count",
            discovery={
                "name": "Thread Network Count",
                "unique_id": "threadlens_thread_network_count",
                "state_topic": topics.environment("thread_network_count"),
                "json_attributes_topic": topics.environment(
                    "thread_network_count", part="attributes"
                ),
                **availability,
                "device": device,
            },
            state=str(snapshot.health.summary.thread_networks_seen),
            attributes=attrs,
        ),
        EntityPublication(
            component="sensor",
            object_id="threadlens_foreign_trel_service_count",
            discovery={
                "name": "Foreign TREL Service Count",
                "unique_id": "threadlens_foreign_trel_service_count",
                "state_topic": topics.environment("foreign_trel_service_count"),
                "json_attributes_topic": topics.environment(
                    "foreign_trel_service_count", part="attributes"
                ),
                **availability,
                "device": device,
            },
            state=str(snapshot.health.summary.foreign_trel_services_seen),
            attributes=attrs,
        ),
        EntityPublication(
            component="sensor",
            object_id="threadlens_matter_node_count",
            discovery={
                "name": "Matter Node Count",
                "unique_id": "threadlens_matter_node_count",
                "state_topic": topics.environment("matter_node_count"),
                "json_attributes_topic": topics.environment("matter_node_count", part="attributes"),
                **availability,
                "device": device,
            },
            state=str(snapshot.health.summary.matter_nodes_seen),
            attributes=attrs,
        ),
        EntityPublication(
            component="sensor",
            object_id="threadlens_unavailable_matter_node_count",
            discovery={
                "name": "Unavailable Matter Node Count",
                "unique_id": "threadlens_unavailable_matter_node_count",
                "state_topic": topics.environment("unavailable_matter_node_count"),
                "json_attributes_topic": topics.environment(
                    "unavailable_matter_node_count", part="attributes"
                ),
                **availability,
                "device": device,
            },
            state=str(snapshot.health.summary.matter_nodes_unavailable),
            attributes=attrs,
        ),
    ]


def _thread_network_entities(
    snapshot: PublishSnapshot,
    topics: TopicBuilder,
) -> list[EntityPublication]:
    publications: list[EntityPublication] = []
    health_by_id = {item.ext_pan_id: item for item in snapshot.health.thread_networks}
    for network in snapshot.thread_networks:
        network_slug = slugify_id(network.ext_pan_id, max_length=32)
        device = _device(
            [f"threadlens_network_{network_slug}"],
            f"Thread Network - {network.ext_pan_id}",
            version=snapshot.version,
        )
        availability = _availability_block(topics)
        health = health_by_id.get(network.ext_pan_id)
        attrs = {
            "ext_pan_id": network.ext_pan_id,
            "network_name": network.name,
            "pan_id": network.pan_id,
            "classification": network.classification.value,
            "source_otbr_ids": network.source_otbr_ids,
            "first_seen": _iso(network.first_seen),
            "last_seen": _iso(network.last_seen),
            "health_reasons": health.reasons if health else [],
        }
        publications.extend(
            [
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_network_{network_slug}_health",
                    discovery={
                        "name": f"Thread Network {network.ext_pan_id} Health",
                        "unique_id": f"threadlens_network_{network_slug}_health",
                        "state_topic": topics.thread_network(network.ext_pan_id, "health"),
                        "json_attributes_topic": topics.thread_network(
                            network.ext_pan_id, "health", part="attributes"
                        ),
                        **availability,
                        "device": device,
                    },
                    state=_health_state_value(health.state if health else HealthState.UNKNOWN),
                    attributes=attrs,
                ),
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_network_{network_slug}_channel",
                    discovery={
                        "name": f"Thread Network {network.ext_pan_id} Channel",
                        "unique_id": f"threadlens_network_{network_slug}_channel",
                        "state_topic": topics.thread_network(network.ext_pan_id, "channel"),
                        "json_attributes_topic": topics.thread_network(
                            network.ext_pan_id, "channel", part="attributes"
                        ),
                        **availability,
                        "device": device,
                    },
                    state=str(network.channel) if network.channel is not None else "unknown",
                    attributes=attrs,
                ),
                EntityPublication(
                    component="binary_sensor",
                    object_id=f"threadlens_network_{network_slug}_visible",
                    discovery={
                        "name": f"Thread Network {network.ext_pan_id} Visible",
                        "unique_id": f"threadlens_network_{network_slug}_visible",
                        "state_topic": topics.thread_network(network.ext_pan_id, "visible"),
                        "json_attributes_topic": topics.thread_network(
                            network.ext_pan_id, "visible", part="attributes"
                        ),
                        "payload_on": "ON",
                        "payload_off": "OFF",
                        **availability,
                        "device": device,
                    },
                    state="ON" if network.currently_visible else "OFF",
                    attributes=attrs,
                ),
                EntityPublication(
                    component="binary_sensor",
                    object_id=f"threadlens_network_{network_slug}_foreign",
                    discovery={
                        "name": f"Thread Network {network.ext_pan_id} Foreign",
                        "unique_id": f"threadlens_network_{network_slug}_foreign",
                        "state_topic": topics.thread_network(network.ext_pan_id, "foreign"),
                        "json_attributes_topic": topics.thread_network(
                            network.ext_pan_id, "foreign", part="attributes"
                        ),
                        "payload_on": "ON",
                        "payload_off": "OFF",
                        **availability,
                        "device": device,
                    },
                    state=(
                        "ON"
                        if network.classification == ThreadNetworkClassification.OBSERVED_OTHER
                        else "OFF"
                    ),
                    attributes=attrs,
                ),
            ]
        )
    return publications


def _otbr_entities(
    snapshot: PublishSnapshot,
    topics: TopicBuilder,
) -> list[EntityPublication]:
    publications: list[EntityPublication] = []
    health_by_id = {item.id: item for item in snapshot.health.otbrs}
    state_by_id = {item.id: item for item in snapshot.otbr_states}
    for otbr_config in snapshot.config.otbrs:
        state = state_by_id.get(otbr_config.id)
        health = health_by_id.get(otbr_config.id)
        otbr_slug = slugify_id(otbr_config.id, max_length=32)
        device = _device(
            [f"threadlens_otbr_{otbr_slug}"],
            f"OTBR - {otbr_config.name}",
            version=snapshot.version,
        )
        availability = _availability_block(topics)
        attrs = {
            "rest_url": otbr_config.rest_url,
            "thread_state": state.thread_state if state else None,
            "thread_state_source": state.thread_state_source if state else None,
            "json_api_thread_state": state.json_api_thread_state if state else None,
            "legacy_node_thread_state": state.legacy_node_thread_state if state else None,
            "rest_endpoint_mismatch": state.rest_endpoint_mismatch if state else None,
            "pan_id": state.pan_id if state else None,
            "rloc16": state.rloc16 if state else None,
            "last_seen": _iso(state.last_seen) if state else None,
            "last_error": state.last_error if state else None,
            "capabilities": state.capabilities.model_dump(mode="json") if state else None,
            "health_reasons": health.reasons if health else ["otbr_not_observed"],
        }
        publications.extend(
            [
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_otbr_{otbr_slug}_health",
                    discovery={
                        "name": f"OTBR {otbr_config.name} Health",
                        "unique_id": f"threadlens_otbr_{otbr_slug}_health",
                        "state_topic": topics.otbr(otbr_config.id, "health"),
                        "json_attributes_topic": topics.otbr(
                            otbr_config.id, "health", part="attributes"
                        ),
                        **availability,
                        "device": device,
                    },
                    state=_health_state_value(health.state if health else HealthState.UNKNOWN),
                    attributes=attrs,
                ),
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_otbr_{otbr_slug}_role",
                    discovery={
                        "name": f"OTBR {otbr_config.name} Role",
                        "unique_id": f"threadlens_otbr_{otbr_slug}_role",
                        "state_topic": topics.otbr(otbr_config.id, "role"),
                        "json_attributes_topic": topics.otbr(
                            otbr_config.id, "role", part="attributes"
                        ),
                        **availability,
                        "device": device,
                    },
                    state=state.role if state and state.role else "unknown",
                    attributes=attrs,
                ),
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_otbr_{otbr_slug}_network_name",
                    discovery={
                        "name": f"OTBR {otbr_config.name} Network Name",
                        "unique_id": f"threadlens_otbr_{otbr_slug}_network_name",
                        "state_topic": topics.otbr(otbr_config.id, "network_name"),
                        "json_attributes_topic": topics.otbr(
                            otbr_config.id, "network_name", part="attributes"
                        ),
                        **availability,
                        "device": device,
                    },
                    state=state.network_name if state and state.network_name else "unknown",
                    attributes=attrs,
                ),
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_otbr_{otbr_slug}_channel",
                    discovery={
                        "name": f"OTBR {otbr_config.name} Channel",
                        "unique_id": f"threadlens_otbr_{otbr_slug}_channel",
                        "state_topic": topics.otbr(otbr_config.id, "channel"),
                        "json_attributes_topic": topics.otbr(
                            otbr_config.id, "channel", part="attributes"
                        ),
                        **availability,
                        "device": device,
                    },
                    state=str(state.channel) if state and state.channel is not None else "unknown",
                    attributes=attrs,
                ),
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_otbr_{otbr_slug}_ext_pan_id",
                    discovery={
                        "name": f"OTBR {otbr_config.name} Extended PAN ID",
                        "unique_id": f"threadlens_otbr_{otbr_slug}_ext_pan_id",
                        "state_topic": topics.otbr(otbr_config.id, "ext_pan_id"),
                        "json_attributes_topic": topics.otbr(
                            otbr_config.id, "ext_pan_id", part="attributes"
                        ),
                        **availability,
                        "device": device,
                    },
                    state=state.ext_pan_id if state and state.ext_pan_id else "unknown",
                    attributes=attrs,
                ),
                EntityPublication(
                    component="binary_sensor",
                    object_id=f"threadlens_otbr_{otbr_slug}_reachable",
                    discovery={
                        "name": f"OTBR {otbr_config.name} Reachable",
                        "unique_id": f"threadlens_otbr_{otbr_slug}_reachable",
                        "state_topic": topics.otbr(otbr_config.id, "reachable"),
                        "json_attributes_topic": topics.otbr(
                            otbr_config.id, "reachable", part="attributes"
                        ),
                        "payload_on": "ON",
                        "payload_off": "OFF",
                        **availability,
                        "device": device,
                    },
                    state="ON" if state and state.reachable else "OFF",
                    attributes=attrs,
                ),
            ]
        )
    return publications


def _matter_server_entities(
    snapshot: PublishSnapshot,
    topics: TopicBuilder,
) -> list[EntityPublication]:
    publications: list[EntityPublication] = []
    health_by_id = {item.id: item for item in snapshot.health.matter_servers}
    state_by_id = {item.id: item for item in snapshot.matter_servers}
    for server_config in snapshot.config.matter_servers:
        state = state_by_id.get(server_config.id)
        health = health_by_id.get(server_config.id)
        server_slug = slugify_id(server_config.id, max_length=32)
        device = _device(
            [f"threadlens_matter_server_{server_slug}"],
            f"Matter Server - {server_config.name}",
            version=snapshot.version,
        )
        availability = _availability_block(topics)
        attrs = {
            "websocket_url": server_config.websocket_url,
            "variant": str(server_config.variant),
            "last_seen": _iso(state.last_seen) if state else None,
            "last_error": state.last_error if state else None,
            "capabilities": state.capabilities.model_dump(mode="json") if state else None,
            "health_reasons": health.reasons if health else ["matter_server_not_observed"],
        }
        publications.extend(
            [
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_matter_server_{server_slug}_health",
                    discovery={
                        "name": f"Matter Server {server_config.name} Health",
                        "unique_id": f"threadlens_matter_server_{server_slug}_health",
                        "state_topic": topics.matter_server(server_config.id, "health"),
                        "json_attributes_topic": topics.matter_server(
                            server_config.id, "health", part="attributes"
                        ),
                        **availability,
                        "device": device,
                    },
                    state=_health_state_value(health.state if health else HealthState.UNKNOWN),
                    attributes=attrs,
                ),
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_matter_server_{server_slug}_node_count",
                    discovery={
                        "name": f"Matter Server {server_config.name} Node Count",
                        "unique_id": f"threadlens_matter_server_{server_slug}_node_count",
                        "state_topic": topics.matter_server(server_config.id, "node_count"),
                        "json_attributes_topic": topics.matter_server(
                            server_config.id, "node_count", part="attributes"
                        ),
                        **availability,
                        "device": device,
                    },
                    state=str(state.node_count if state else 0),
                    attributes=attrs,
                ),
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_matter_server_{server_slug}_unavailable_node_count",
                    discovery={
                        "name": f"Matter Server {server_config.name} Unavailable Node Count",
                        "unique_id": (
                            f"threadlens_matter_server_{server_slug}_unavailable_node_count"
                        ),
                        "state_topic": topics.matter_server(
                            server_config.id, "unavailable_node_count"
                        ),
                        "json_attributes_topic": topics.matter_server(
                            server_config.id, "unavailable_node_count", part="attributes"
                        ),
                        **availability,
                        "device": device,
                    },
                    state=str(state.unavailable_node_count if state else 0),
                    attributes=attrs,
                ),
                EntityPublication(
                    component="binary_sensor",
                    object_id=f"threadlens_matter_server_{server_slug}_connected",
                    discovery={
                        "name": f"Matter Server {server_config.name} Connected",
                        "unique_id": f"threadlens_matter_server_{server_slug}_connected",
                        "state_topic": topics.matter_server(server_config.id, "connected"),
                        "json_attributes_topic": topics.matter_server(
                            server_config.id, "connected", part="attributes"
                        ),
                        "payload_on": "ON",
                        "payload_off": "OFF",
                        **availability,
                        "device": device,
                    },
                    state="ON" if state and state.connected else "OFF",
                    attributes=attrs,
                ),
            ]
        )
    return publications


def _matter_node_entities(
    snapshot: PublishSnapshot,
    topics: TopicBuilder,
) -> list[EntityPublication]:
    publications: list[EntityPublication] = []
    health_by_id = {item.id: item for item in snapshot.health.matter_nodes}
    warning_threshold = snapshot.config.flapping.matter_node_availability_warning_24h
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
        flapping = (
            node.availability_flaps_24h is not None
            and node.availability_flaps_24h >= warning_threshold
        )
        attrs = {
            "node_id": node.node_id,
            "server_id": node.server_id,
            "friendly_name": node.friendly_name,
            "vendor_id": node.vendor_id,
            "vendor_name": node.vendor,
            "product_id": node.product_id,
            "product_name": node.product,
            "serial_number": node.serial,
            "software_version": node.firmware,
            "last_unavailable": _iso(node.last_unavailable),
            "health_reasons": health.reasons if health else [],
            "subscription_diagnostics_available": node.subscription_diagnostics_available,
            "subscription_flaps_24h": node.subscription_flaps_24h,
            "case_diagnostics_available": node.case_diagnostics_available,
            "command_diagnostics_available": node.command_diagnostics_available,
        }
        publications.extend(
            [
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
                EntityPublication(
                    component="binary_sensor",
                    object_id=f"threadlens_matter_node_{node_slug}_available",
                    discovery={
                        "name": f"Matter Node {display} Available",
                        "unique_id": f"threadlens_matter_node_{node_slug}_available",
                        "state_topic": topics.matter_node(
                            node.server_id, node.node_id, "available"
                        ),
                        "json_attributes_topic": topics.matter_node(
                            node.server_id, node.node_id, "available", part="attributes"
                        ),
                        "payload_on": "ON",
                        "payload_off": "OFF",
                        **availability,
                        "device": device,
                    },
                    state="ON" if node.available else "OFF",
                    attributes=attrs,
                ),
                EntityPublication(
                    component="binary_sensor",
                    object_id=f"threadlens_matter_node_{node_slug}_flapping",
                    discovery={
                        "name": f"Matter Node {display} Flapping",
                        "unique_id": f"threadlens_matter_node_{node_slug}_flapping",
                        "state_topic": topics.matter_node(node.server_id, node.node_id, "flapping"),
                        "json_attributes_topic": topics.matter_node(
                            node.server_id, node.node_id, "flapping", part="attributes"
                        ),
                        "payload_on": "ON",
                        "payload_off": "OFF",
                        **availability,
                        "device": device,
                    },
                    state="ON" if flapping else "OFF",
                    attributes=attrs,
                ),
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_matter_node_{node_slug}_availability_flaps_24h",
                    discovery={
                        "name": f"Matter Node {display} Availability Flaps 24h",
                        "unique_id": (f"threadlens_matter_node_{node_slug}_availability_flaps_24h"),
                        "state_topic": topics.matter_node(
                            node.server_id, node.node_id, "availability_flaps_24h"
                        ),
                        "json_attributes_topic": topics.matter_node(
                            node.server_id,
                            node.node_id,
                            "availability_flaps_24h",
                            part="attributes",
                        ),
                        **availability,
                        "device": device,
                    },
                    state=(
                        str(node.availability_flaps_24h)
                        if node.availability_flaps_24h is not None
                        else "unknown"
                    ),
                    attributes=attrs,
                ),
                EntityPublication(
                    component="sensor",
                    object_id=f"threadlens_matter_node_{node_slug}_last_seen",
                    discovery={
                        "name": f"Matter Node {display} Last Seen",
                        "unique_id": f"threadlens_matter_node_{node_slug}_last_seen",
                        "state_topic": topics.matter_node(
                            node.server_id, node.node_id, "last_seen"
                        ),
                        "json_attributes_topic": topics.matter_node(
                            node.server_id, node.node_id, "last_seen", part="attributes"
                        ),
                        **availability,
                        "device": device,
                    },
                    state=_iso(node.last_seen) or "unknown",
                    attributes=attrs,
                ),
            ]
        )
    return publications
