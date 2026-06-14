"""Health engine tests."""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from threadlens.collectors.mdns import MdnsObserver, NormalizedMdnsRecord
from threadlens.config import (
    FlappingConfig,
    MatterServerConfig,
    MdnsConfig,
    OtbrConfig,
    RuntimeMode,
    ThreadLensConfig,
)
from threadlens.health.engine import HealthContext, HealthEngine
from threadlens.models.capabilities import MatterServerCapabilities, OtbrRestCapabilities
from threadlens.models.events import Event, EventSeverity, EventSourceType, EventSubjectType
from threadlens.models.health import HealthState
from threadlens.models.state import (
    MatterNodeState,
    MatterServerState,
    OtbrState,
    TrelServiceState,
)
from threadlens.server.app import create_server_app
from threadlens.storage.db import Database
from threadlens.storage.repositories import CurrentStateType, StorageRepository
from threadlens.utils.ids import normalize_mdns_service_id
from threadlens.utils.time import utc_now


def _matter_record_named(index: int) -> NormalizedMdnsRecord:
    instance_name = f"matter-device-{index}._matter._tcp.local."
    service_type = "_matter._tcp.local."
    return NormalizedMdnsRecord(
        service_id=normalize_mdns_service_id(instance_name, service_type),
        service_type=service_type,
        instance_name=instance_name,
        hostname=f"matter-device-{index}.local.",
        addresses=[f"192.168.1.{index}"],
        port=5540,
        txt_records={"VP": "1234+5678"},
    )


async def _make_running_mdns_context(
    tmp_path: Path,
    *,
    db_name: str,
    flap_config: FlappingConfig | None = None,
) -> HealthContext:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / db_name)},
        flapping=flap_config or FlappingConfig(debounce_seconds=0),
        mdns=MdnsConfig(enabled=True),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    observer = MdnsObserver(config, repository)
    observer._running = True  # noqa: SLF001 - test stub
    observer.observation_degraded = False
    return HealthContext(config=config, repository=repository, mdns_observer=observer)


@pytest.fixture
async def health_context(tmp_path: Path):
    async def _make(
        *,
        config: ThreadLensConfig | None = None,
        mdns_observer: MdnsObserver | None = None,
    ) -> HealthContext:
        cfg = config or ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "threadlens.db")},
            flapping=FlappingConfig(debounce_seconds=0),
            mdns=MdnsConfig(enabled=False),
        )
        database = Database(cfg.storage.sqlite_path)
        repository = StorageRepository(database)
        await repository.initialize()
        return HealthContext(
            config=cfg,
            repository=repository,
            mdns_observer=mdns_observer,
        )

    yield _make


async def _insert_event(
    repository: StorageRepository,
    *,
    event_type: str,
    source_id: str = "study",
    subject_type: EventSubjectType = EventSubjectType.OTBR,
    subject_id: str = "otbr:study",
    severity: EventSeverity = EventSeverity.INFO,
    minutes_ago: float = 0,
) -> None:
    now = utc_now() - timedelta(minutes=minutes_ago)
    await repository.insert_event(
        Event(
            id=str(uuid.uuid4()),
            timestamp=now,
            source_type=EventSourceType.OTBR,
            source_id=source_id,
            event_type=event_type,
            severity=severity,
            subject_type=subject_type,
            subject_id=subject_id,
            message=event_type,
            data={},
        )
    )


@pytest.mark.asyncio
async def test_otbr_unreachable_is_critical(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "otbr-unreachable.db")},
            otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(id="study", name="Study", reachable=False),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    otbr = report.otbrs[0]
    assert otbr.state == HealthState.CRITICAL
    assert "otbr_unreachable" in otbr.reasons


@pytest.mark.asyncio
async def test_otbr_reachable_with_dataset_is_healthy(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "otbr-healthy.db")},
            otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(
            id="study",
            name="Study",
            reachable=True,
            thread_state="router",
            ext_pan_id="d6f401f0227e1ec0",
            capabilities=OtbrRestCapabilities(network_dataset_available=True),
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.otbrs[0].state == HealthState.HEALTHY


@pytest.mark.asyncio
async def test_otbr_dataset_unknown_is_warning(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "otbr-dataset.db")},
            otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(id="study", name="Study", reachable=True),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.otbrs[0].state == HealthState.WARNING
    assert "otbr_dataset_unknown" in report.otbrs[0].reasons


@pytest.mark.asyncio
async def test_otbr_thread_stack_disabled_is_degraded(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "otbr-disabled.db")},
            otbrs=[
                OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081"),
                OtbrConfig(id="lounge", name="Lounge", rest_url="http://127.0.0.1:8082"),
            ],
            mdns=MdnsConfig(enabled=False),
        )
    )
    for otbr_id in ("study", "lounge"):
        await ctx.repository.upsert_model_state(
            CurrentStateType.OTBR,
            otbr_id,
            OtbrState(
                id=otbr_id,
                name=otbr_id.title(),
                reachable=True,
                thread_state="disabled",
                ext_pan_id="3ca76a62d0c054c3",
                capabilities=OtbrRestCapabilities(
                    network_dataset_available=True,
                    thread_stack_active=False,
                ),
            ),
        )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert all(otbr.state == HealthState.DEGRADED for otbr in report.otbrs)
    assert all("otbr_thread_stack_disabled" in otbr.reasons for otbr in report.otbrs)
    assert report.environment.state == HealthState.DEGRADED
    assert "otbr_thread_stack_disabled" in report.environment.reasons


@pytest.mark.asyncio
async def test_otbr_role_flapping_warning_threshold(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "otbr-role-warn.db")},
            flapping=FlappingConfig(
                otbr_role_changes_warning_1h=2, otbr_role_changes_degraded_1h=5
            ),
            otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(
            id="study",
            name="Study",
            reachable=True,
            thread_state="router",
            ext_pan_id="d6f401f0227e1ec0",
            capabilities=OtbrRestCapabilities(network_dataset_available=True),
        ),
    )
    for _ in range(2):
        await _insert_event(ctx.repository, event_type="otbr.role_changed", source_id="study")
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.otbrs[0].state == HealthState.WARNING
    assert "otbr_role_flapping_warning" in report.otbrs[0].reasons


@pytest.mark.asyncio
async def test_otbr_role_flapping_degraded_threshold(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "otbr-role-deg.db")},
            flapping=FlappingConfig(
                otbr_role_changes_warning_1h=2, otbr_role_changes_degraded_1h=5
            ),
            otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(
            id="study",
            name="Study",
            reachable=True,
            thread_state="router",
            ext_pan_id="d6f401f0227e1ec0",
            capabilities=OtbrRestCapabilities(network_dataset_available=True),
        ),
    )
    for _ in range(5):
        await _insert_event(ctx.repository, event_type="otbr.role_changed", source_id="study")
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.otbrs[0].state == HealthState.DEGRADED
    assert "otbr_role_flapping_degraded" in report.otbrs[0].reasons


@pytest.mark.asyncio
async def test_matter_server_disconnected_is_critical(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "matter-disc.db")},
            matter_servers=[
                MatterServerConfig(
                    id="study_matter",
                    name="Study",
                    websocket_url="ws://127.0.0.1:5580/ws",
                )
            ],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(id="study_matter", name="Study", connected=False),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.matter_servers[0].state == HealthState.CRITICAL
    assert "matter_server_disconnected" in report.matter_servers[0].reasons


@pytest.mark.asyncio
async def test_matter_server_unavailable_nodes_warning(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "matter-unavail.db")},
            matter_servers=[
                MatterServerConfig(
                    id="study_matter",
                    name="Study",
                    websocket_url="ws://127.0.0.1:5580/ws",
                )
            ],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study",
            connected=True,
            node_count=2,
            unavailable_node_count=1,
            capabilities=MatterServerCapabilities(
                node_inventory_available=True,
                node_availability_available=True,
            ),
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.matter_servers[0].state == HealthState.WARNING
    assert "matter_nodes_unavailable" in report.matter_servers[0].reasons


@pytest.mark.asyncio
async def test_matter_server_connected_healthy(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "matter-healthy.db")},
            matter_servers=[
                MatterServerConfig(
                    id="study_matter",
                    name="Study",
                    websocket_url="ws://127.0.0.1:5580/ws",
                )
            ],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study",
            connected=True,
            node_count=2,
            unavailable_node_count=0,
            capabilities=MatterServerCapabilities(
                node_inventory_available=True,
                node_availability_available=True,
            ),
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.matter_servers[0].state == HealthState.HEALTHY


@pytest.mark.asyncio
async def test_matter_node_unavailable_is_degraded(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "node-unavail.db")},
            matter_servers=[
                MatterServerConfig(
                    id="study_matter",
                    name="Study",
                    websocket_url="ws://127.0.0.1:5580/ws",
                )
            ],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study",
            connected=True,
            capabilities=MatterServerCapabilities(node_availability_available=True),
        ),
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_NODE,
        "matter_node:study_matter:24",
        MatterNodeState(
            node_id=24,
            server_id="study_matter",
            available=False,
            last_unavailable=utc_now(),
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    node = report.matter_nodes[0]
    assert node.state == HealthState.DEGRADED
    assert "matter_node_unavailable" in node.reasons


@pytest.mark.asyncio
async def test_matter_node_unavailable_critical_minutes(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "node-critical.db")},
            flapping=FlappingConfig(matter_node_unavailable_critical_minutes=30),
            matter_servers=[
                MatterServerConfig(
                    id="study_matter",
                    name="Study",
                    websocket_url="ws://127.0.0.1:5580/ws",
                )
            ],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study",
            connected=True,
            capabilities=MatterServerCapabilities(node_availability_available=True),
        ),
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_NODE,
        "matter_node:study_matter:24",
        MatterNodeState(
            node_id=24,
            server_id="study_matter",
            available=False,
            last_unavailable=utc_now() - timedelta(minutes=45),
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.matter_nodes[0].state == HealthState.CRITICAL
    assert "matter_node_unavailable_critical" in report.matter_nodes[0].reasons


@pytest.mark.asyncio
async def test_matter_node_availability_flaps_warning(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "node-flap-warn.db")},
            flapping=FlappingConfig(
                matter_node_availability_warning_24h=3,
                matter_node_availability_degraded_24h=6,
            ),
            matter_servers=[
                MatterServerConfig(
                    id="study_matter",
                    name="Study",
                    websocket_url="ws://127.0.0.1:5580/ws",
                )
            ],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study",
            connected=True,
            capabilities=MatterServerCapabilities(node_availability_available=True),
        ),
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_NODE,
        "matter_node:study_matter:24",
        MatterNodeState(
            node_id=24,
            server_id="study_matter",
            available=True,
            availability_flaps_24h=3,
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.matter_nodes[0].state == HealthState.WARNING
    assert "matter_node_availability_flapping_warning" in report.matter_nodes[0].reasons


@pytest.mark.asyncio
async def test_matter_node_availability_flaps_degraded(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "node-flap-deg.db")},
            flapping=FlappingConfig(
                matter_node_availability_warning_24h=3,
                matter_node_availability_degraded_24h=6,
            ),
            matter_servers=[
                MatterServerConfig(
                    id="study_matter",
                    name="Study",
                    websocket_url="ws://127.0.0.1:5580/ws",
                )
            ],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study",
            connected=True,
            capabilities=MatterServerCapabilities(node_availability_available=True),
        ),
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_NODE,
        "matter_node:study_matter:24",
        MatterNodeState(
            node_id=24,
            server_id="study_matter",
            available=True,
            availability_flaps_24h=6,
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.matter_nodes[0].state == HealthState.DEGRADED
    assert "matter_node_availability_flapping_degraded" in report.matter_nodes[0].reasons


@pytest.mark.asyncio
async def test_subscription_diagnostics_unavailable_does_not_degrade_health(
    health_context, tmp_path: Path
) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "node-sub-unavail.db")},
            matter_servers=[
                MatterServerConfig(
                    id="study_matter",
                    name="Study",
                    websocket_url="ws://127.0.0.1:5580/ws",
                )
            ],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study",
            connected=True,
            capabilities=MatterServerCapabilities(node_availability_available=True),
        ),
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_NODE,
        "matter_node:study_matter:24",
        MatterNodeState(
            node_id=24,
            server_id="study_matter",
            available=True,
            subscription_flaps_24h=None,
            subscription_diagnostics_available=False,
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.matter_nodes[0].state == HealthState.HEALTHY
    assert "subscription_diagnostics_unavailable" not in report.matter_nodes[0].reasons


@pytest.mark.asyncio
async def test_matter_node_health_unchanged_when_read_probe_fields_present(
    health_context,
    tmp_path: Path,
) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "probe-health.db")},
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study",
            connected=True,
            capabilities=MatterServerCapabilities(
                node_inventory_available=True,
                node_availability_available=True,
            ),
        ),
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_NODE,
        "matter_node:study_matter:24",
        MatterNodeState(
            node_id=24,
            server_id="study_matter",
            available=True,
            availability_flaps_24h=0,
            read_probe_diagnostics_available=True,
            last_read_probe_ok=False,
            read_probe_failures_24h=12,
            read_probe_successes_24h=0,
        ),
    )

    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    node = report.matter_nodes[0]
    assert node.state == HealthState.HEALTHY
    assert "read_probe" not in " ".join(node.reasons)


@pytest.mark.asyncio
async def test_mdns_enabled_observer_not_running_warning(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "mdns-not-running.db")},
            mdns=MdnsConfig(enabled=True),
        )
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.mdns.state == HealthState.WARNING
    assert "mdns_observer_not_running" in report.mdns.reasons


@pytest.mark.asyncio
async def test_mdns_observation_degraded_warning(health_context, tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "mdns-degraded.db")},
        mdns=MdnsConfig(enabled=True),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    observer = MdnsObserver(config, repository)
    observer._running = True  # noqa: SLF001 - test stub
    observer.observation_degraded = True
    ctx = HealthContext(config=config, repository=repository, mdns_observer=observer)
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.mdns.state == HealthState.WARNING
    assert "mdns_observation_degraded" in report.mdns.reasons


@pytest.mark.asyncio
async def test_mdns_observation_degraded_null_not_healthy(health_context, tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "mdns-null.db")},
        mdns=MdnsConfig(enabled=True),
    )
    database = Database(config.storage.sqlite_path)
    repository = StorageRepository(database)
    await repository.initialize()
    observer = MdnsObserver(config, repository)
    observer._running = True  # noqa: SLF001 - test stub
    observer.observation_degraded = None
    ctx = HealthContext(config=config, repository=repository, mdns_observer=observer)
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.mdns.state == HealthState.UNKNOWN
    assert "mdns_observation_capability_unknown" in report.mdns.reasons


@pytest.mark.asyncio
async def test_foreign_trel_services_warning_not_critical(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "foreign-trel.db")},
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.TREL_SERVICE,
        "foreign-trel",
        TrelServiceState(
            service_id="foreign-trel",
            instance_name="foreign",
            currently_visible=True,
            is_foreign=True,
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.trel.state == HealthState.WARNING
    assert "foreign_trel_services_observed" in report.trel.reasons
    assert report.environment.state != HealthState.CRITICAL


@pytest.mark.asyncio
async def test_configured_otbrs_disagree_on_ext_pan_id(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "otbr-disagree.db")},
            otbrs=[
                OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081"),
                OtbrConfig(id="lounge", name="Lounge", rest_url="http://127.0.0.1:8082"),
            ],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(
            id="study",
            name="Study",
            reachable=True,
            ext_pan_id="aaaaaaaaaaaaaaaa",
            capabilities=OtbrRestCapabilities(network_dataset_available=True),
        ),
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.OTBR,
        "lounge",
        OtbrState(
            id="lounge",
            name="Lounge",
            reachable=True,
            ext_pan_id="bbbbbbbbbbbbbbbb",
            capabilities=OtbrRestCapabilities(network_dataset_available=True),
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.environment.state in (HealthState.WARNING, HealthState.DEGRADED)
    assert "configured_otbrs_disagree_on_ext_pan_id" in report.environment.reasons


@pytest.mark.asyncio
async def test_environment_rolls_up_critical_child(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "env-critical.db")},
            otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(id="study", name="Study", reachable=False),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.environment.state == HealthState.CRITICAL
    assert report.overall.state == HealthState.CRITICAL


@pytest.mark.asyncio
async def test_environment_rolls_up_degraded_child(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "env-degraded.db")},
            flapping=FlappingConfig(
                matter_node_availability_warning_24h=3,
                matter_node_availability_degraded_24h=6,
            ),
            matter_servers=[
                MatterServerConfig(
                    id="study_matter",
                    name="Study",
                    websocket_url="ws://127.0.0.1:5580/ws",
                )
            ],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_SERVER,
        "study_matter",
        MatterServerState(
            id="study_matter",
            name="Study",
            connected=True,
            capabilities=MatterServerCapabilities(node_availability_available=True),
        ),
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.MATTER_NODE,
        "matter_node:study_matter:24",
        MatterNodeState(
            node_id=24,
            server_id="study_matter",
            available=True,
            availability_flaps_24h=6,
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.environment.state == HealthState.DEGRADED
    assert report.overall.state == HealthState.DEGRADED


@pytest.mark.asyncio
async def test_initial_mdns_discovery_burst_does_not_degrade_health(
    tmp_path: Path,
) -> None:
    ctx = await _make_running_mdns_context(tmp_path, db_name="mdns-startup-burst.db")
    observer = ctx.mdns_observer
    assert observer is not None
    for index in range(20):
        await observer.process_service_added(_matter_record_named(index))

    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.mdns.state == HealthState.HEALTHY
    assert "mdns_service_flapping_warning" not in report.mdns.reasons
    assert "mdns_service_flapping_degraded" not in report.mdns.reasons


@pytest.mark.asyncio
async def test_post_baseline_mdns_readd_counts_as_flap(tmp_path: Path) -> None:
    ctx = await _make_running_mdns_context(
        tmp_path,
        db_name="mdns-readd-flap.db",
        flap_config=FlappingConfig(
            debounce_seconds=0,
            mdns_service_flaps_warning_1h=1,
            mdns_service_flaps_degraded_1h=2,
        ),
    )
    observer = ctx.mdns_observer
    assert observer is not None
    record = _matter_record_named(1)
    await observer.process_service_added(record)
    await observer.process_service_removed(record)
    await observer.process_service_added(record)

    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.mdns.state == HealthState.DEGRADED
    assert "mdns_service_flapping_degraded" in report.mdns.reasons


@pytest.mark.asyncio
async def test_mdns_service_changed_burst_does_not_degrade_health(tmp_path: Path) -> None:
    ctx = await _make_running_mdns_context(
        tmp_path,
        db_name="mdns-change-only.db",
        flap_config=FlappingConfig(
            debounce_seconds=0,
            mdns_service_flaps_warning_1h=5,
            mdns_service_flaps_degraded_1h=15,
        ),
    )
    now = utc_now()
    for index in range(20):
        await ctx.repository.insert_event(
            Event(
                id=str(uuid.uuid4()),
                timestamp=now,
                source_type=EventSourceType.MDNS,
                source_id="mdns",
                event_type="mdns.service_changed",
                severity=EventSeverity.INFO,
                subject_type=EventSubjectType.MDNS_SERVICE,
                subject_id=f"mdns:service:{index}",
                message=f"mDNS service changed {index}",
                data={"initial_observation": False},
            )
        )

    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.mdns.state == HealthState.HEALTHY
    assert "mdns_service_flapping_warning" not in report.mdns.reasons
    assert "mdns_service_flapping_degraded" not in report.mdns.reasons


@pytest.mark.asyncio
async def test_trel_service_changed_burst_does_not_degrade_trel_health(tmp_path: Path) -> None:
    ctx = await _make_running_mdns_context(
        tmp_path,
        db_name="trel-change-only.db",
        flap_config=FlappingConfig(
            debounce_seconds=0,
            mdns_service_flaps_warning_1h=5,
            mdns_service_flaps_degraded_1h=15,
        ),
    )
    now = utc_now()
    for index in range(20):
        await ctx.repository.insert_event(
            Event(
                id=str(uuid.uuid4()),
                timestamp=now,
                source_type=EventSourceType.MDNS,
                source_id="mdns",
                event_type="trel.service_changed",
                severity=EventSeverity.INFO,
                subject_type=EventSubjectType.TREL_SERVICE,
                subject_id=f"trel:service:{index}",
                message=f"TREL service changed {index}",
                data={"initial_observation": False},
            )
        )

    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert "mdns_service_flapping_degraded" not in report.trel.reasons
    assert "mdns_service_flapping_warning" not in report.trel.reasons


@pytest.mark.asyncio
async def test_foreign_trel_services_still_warn_when_change_events_dominate(
    tmp_path: Path,
) -> None:
    ctx = await _make_running_mdns_context(
        tmp_path,
        db_name="trel-foreign-warning.db",
        flap_config=FlappingConfig(debounce_seconds=0),
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.TREL_SERVICE,
        "trel:foreign-1",
        TrelServiceState(
            service_id="trel:foreign-1",
            instance_name="foreign-trel._trel._udp.local.",
            ext_pan_id="aabbccddeeff0011",
            is_foreign=True,
            currently_visible=True,
        ),
    )
    now = utc_now()
    await ctx.repository.insert_event(
        Event(
            id=str(uuid.uuid4()),
            timestamp=now,
            source_type=EventSourceType.MDNS,
            source_id="mdns",
            event_type="trel.service_changed",
            severity=EventSeverity.INFO,
            subject_type=EventSubjectType.TREL_SERVICE,
            subject_id="trel:foreign-1",
            message="TREL service changed",
            data={"initial_observation": False},
        )
    )

    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.trel.state == HealthState.WARNING
    assert "foreign_trel_services_observed" in report.trel.reasons
    assert "mdns_service_flapping_degraded" not in report.trel.reasons


def test_health_api_returns_structured_sections(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "health-api.db")},
        mdns=MdnsConfig(enabled=False),
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "threadlens-server"
        assert "overall" in body
        assert "environment" in body
        assert "summary" in body
        assert "otbrs" in body
        assert "matter_servers" in body
        assert "matter_nodes" in body
        assert "mdns" in body
        assert "trel" in body
        assert "state" in body["overall"]
        assert "reasons" in body["overall"]


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "otbr"


def _load_otbr_fixture(name: str) -> dict[str, object]:
    import json

    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


async def _seed_disabled_otbrs_from_live_fixtures(
    repository: StorageRepository,
    *,
    otbr_ids: tuple[str, str] = ("study", "lounge"),
    fixture_names: tuple[str, str] = ("study-api-node.live.json", "lounge-api-node.live.json"),
) -> None:
    from threadlens.collectors.otbr_parse import parse_otbr_node_response

    for otbr_id, fixture_name in zip(otbr_ids, fixture_names, strict=True):
        snapshot = parse_otbr_node_response(_load_otbr_fixture(fixture_name))
        await repository.upsert_model_state(
            CurrentStateType.OTBR,
            otbr_id,
            OtbrState(
                id=otbr_id,
                name=otbr_id.title(),
                reachable=True,
                thread_state=snapshot.thread_state,
                role=snapshot.role,
                network_name=snapshot.network_name,
                ext_pan_id=snapshot.ext_pan_id,
                capabilities=OtbrRestCapabilities(
                    network_dataset_available=snapshot.ext_pan_id is not None,
                    thread_stack_active=False,
                ),
            ),
        )


def _otbr_api_client(
    tmp_path: Path,
    *,
    db_name: str = "otbr-api-health.db",
) -> tuple[TestClient, ThreadLensConfig]:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / db_name)},
        otbrs=[
            OtbrConfig(id="study", name="Study OTBR", rest_url="http://192.168.100.4:8081"),
            OtbrConfig(id="lounge", name="Lounge OTBR", rest_url="http://192.168.100.7:8081"),
        ],
        mdns=MdnsConfig(enabled=False),
    )
    return TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)), config


@pytest.mark.asyncio
async def test_otbrs_api_embedded_health_degraded_for_disabled_thread_state(
    tmp_path: Path,
) -> None:
    client, config = _otbr_api_client(tmp_path)
    with client:
        repository: StorageRepository = client.app.state.storage
        await _seed_disabled_otbrs_from_live_fixtures(repository)

        response = client.get("/api/v1/otbrs")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 2
        for otbr in body["otbrs"]:
            assert otbr["thread_state"] == "disabled"
            assert otbr["health"]["state"] == HealthState.DEGRADED
            assert "otbr_thread_stack_disabled" in otbr["health"]["reasons"]


@pytest.mark.asyncio
async def test_otbrs_api_embedded_health_matches_health_endpoint(
    tmp_path: Path,
) -> None:
    client, _config = _otbr_api_client(tmp_path)
    with client:
        repository: StorageRepository = client.app.state.storage
        await _seed_disabled_otbrs_from_live_fixtures(repository)

        otbrs_body = client.get("/api/v1/otbrs").json()
        health_body = client.get("/api/v1/health").json()

        embedded_by_id = {item["id"]: item["health"] for item in otbrs_body["otbrs"]}
        for health_entry in health_body["otbrs"]:
            embedded = embedded_by_id[health_entry["id"]]
            assert embedded["state"] == health_entry["state"]
            assert embedded["reasons"] == health_entry["reasons"]


@pytest.mark.asyncio
async def test_otbrs_api_embedded_health_unreachable_matches_health_endpoint(
    tmp_path: Path,
) -> None:
    client, _config = _otbr_api_client(tmp_path, db_name="otbr-api-unreachable.db")
    with client:
        repository: StorageRepository = client.app.state.storage
        await repository.upsert_model_state(
            CurrentStateType.OTBR,
            "study",
            OtbrState(
                id="study",
                name="Study OTBR",
                reachable=False,
                last_error="connection refused",
            ),
        )

        otbrs_body = client.get("/api/v1/otbrs").json()
        health_body = client.get("/api/v1/health").json()

        study = next(item for item in otbrs_body["otbrs"] if item["id"] == "study")
        health_study = next(item for item in health_body["otbrs"] if item["id"] == "study")
        assert study["health"]["state"] == HealthState.CRITICAL
        assert "otbr_unreachable" in study["health"]["reasons"]
        assert study["health"]["state"] == health_study["state"]
        assert study["health"]["reasons"] == health_study["reasons"]


@pytest.mark.asyncio
async def test_otbr_rest_endpoint_mismatch_is_warning_not_disabled(
    health_context,
    tmp_path: Path,
) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "otbr-mismatch.db")},
            otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(
            id="study",
            name="Study",
            reachable=True,
            thread_state="leader",
            thread_state_source="legacy_node",
            json_api_thread_state="disabled",
            legacy_node_thread_state="leader",
            rest_endpoint_mismatch=True,
            role="leader",
            network_name="ha-thread-11",
            ext_pan_id="3ca76a62d0c054c3",
            capabilities=OtbrRestCapabilities(
                network_dataset_available=True,
                thread_stack_active=True,
                legacy_node_available=True,
                json_api_state_stale=True,
            ),
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.otbrs[0].state == HealthState.WARNING
    assert "otbr_rest_endpoint_mismatch" in report.otbrs[0].reasons
    assert "otbr_thread_stack_disabled" not in report.otbrs[0].reasons


@pytest.mark.asyncio
async def test_otbr_both_sources_disabled_stays_degraded(health_context, tmp_path: Path) -> None:
    ctx = await health_context(
        config=ThreadLensConfig(
            storage={"sqlite_path": str(tmp_path / "otbr-both-disabled.db")},
            otbrs=[OtbrConfig(id="study", name="Study", rest_url="http://127.0.0.1:8081")],
            mdns=MdnsConfig(enabled=False),
        )
    )
    await ctx.repository.upsert_model_state(
        CurrentStateType.OTBR,
        "study",
        OtbrState(
            id="study",
            name="Study",
            reachable=True,
            thread_state="disabled",
            json_api_thread_state="disabled",
            legacy_node_thread_state="disabled",
            rest_endpoint_mismatch=False,
            ext_pan_id="3ca76a62d0c054c3",
            capabilities=OtbrRestCapabilities(
                network_dataset_available=True,
                thread_stack_active=False,
                legacy_node_available=True,
            ),
        ),
    )
    report = await HealthEngine(ctx).build_report(version="0.1.0", mode="server")
    assert report.otbrs[0].state == HealthState.DEGRADED
    assert "otbr_thread_stack_disabled" in report.otbrs[0].reasons


@pytest.mark.asyncio
async def test_otbrs_api_exposes_reconciliation_fields(tmp_path: Path) -> None:
    client, _config = _otbr_api_client(tmp_path, db_name="otbr-api-reconcile.db")
    with client:
        repository: StorageRepository = client.app.state.storage
        await repository.upsert_model_state(
            CurrentStateType.OTBR,
            "study",
            OtbrState(
                id="study",
                name="Study OTBR",
                reachable=True,
                thread_state="leader",
                thread_state_source="legacy_node",
                json_api_thread_state="disabled",
                legacy_node_thread_state="leader",
                rest_endpoint_mismatch=True,
                role="leader",
                network_name="ha-thread-11",
                ext_pan_id="3ca76a62d0c054c3",
                capabilities=OtbrRestCapabilities(
                    network_dataset_available=True,
                    thread_stack_active=True,
                    legacy_node_available=True,
                    json_api_state_stale=True,
                ),
            ),
        )
        body = client.get("/api/v1/otbrs").json()
        study = body["otbrs"][0]
        assert study["thread_state"] == "leader"
        assert study["rest_endpoint_mismatch"] is True
        assert study["json_api_thread_state"] == "disabled"
        assert study["legacy_node_thread_state"] == "leader"
        assert study["capabilities"]["json_api_state_stale"] is True
