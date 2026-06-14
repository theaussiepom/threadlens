"""SQLite storage tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from threadlens.models.events import (
    Event,
    EventSeverity,
    EventSourceType,
    EventSubjectType,
)
from threadlens.models.state import MatterNodeState
from threadlens.storage.db import Database
from threadlens.storage.migrations import SCHEMA_VERSION, initialize_schema
from threadlens.storage.repositories import AggregateBucketSize, CurrentStateType, StorageRepository


@pytest.fixture
async def repository(tmp_path: Path) -> StorageRepository:
    db_path = tmp_path / "nested" / "threadlens.db"
    database = Database(db_path)
    repo = StorageRepository(database)
    await repo.initialize()
    yield repo
    await database.close()


async def test_database_initialises_and_creates_tables(repository: StorageRepository) -> None:
    database = repository._database
    connection = database.connection()
    tables = {
        row[0]
        for row in await (
            await connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ).fetchall()
    }
    assert {
        "aggregates",
        "current_state",
        "events",
        "metadata",
    }.issubset(tables)


async def test_metadata_set_get(repository: StorageRepository) -> None:
    await repository.set_metadata("schema_version", SCHEMA_VERSION)
    assert await repository.get_metadata("schema_version") == SCHEMA_VERSION


async def test_current_state_upsert_get_list(repository: StorageRepository) -> None:
    await repository.upsert_current_state(
        CurrentStateType.OTBR,
        "study",
        {"reachable": True, "role": "router"},
    )
    payload = await repository.get_current_state(CurrentStateType.OTBR, "study")
    assert payload is not None
    assert payload["reachable"] is True
    assert payload["role"] == "router"

    await repository.upsert_current_state(
        CurrentStateType.THREAD_NETWORK,
        "d6f401f0227e1ec0",
        {"name": "ha-thread"},
    )
    all_states = await repository.list_current_state()
    assert len(all_states) == 2
    otbr_states = await repository.list_current_state(CurrentStateType.OTBR)
    assert len(otbr_states) == 1


async def test_current_state_upsert_replaces_existing_payload(
    repository: StorageRepository,
) -> None:
    await repository.upsert_current_state(
        CurrentStateType.OTBR,
        "study",
        {"reachable": True, "role": "router"},
    )
    await repository.upsert_current_state(
        CurrentStateType.OTBR,
        "study",
        {"reachable": False, "role": "disabled"},
    )
    payload = await repository.get_current_state(CurrentStateType.OTBR, "study")
    assert payload is not None
    assert payload["reachable"] is False
    assert payload["role"] == "disabled"


async def test_event_insert_get(repository: StorageRepository) -> None:
    event = Event(
        id="evt-1",
        timestamp=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
        source_type=EventSourceType.MATTER_SERVER,
        source_id="study_matter",
        event_type="matter_node.unavailable",
        severity=EventSeverity.WARNING,
        subject_type=EventSubjectType.MATTER_NODE,
        subject_id="matter_node:24",
        message="Matter node 24 became unavailable",
        data={"node_id": 24},
    )
    await repository.insert_event(event)
    events = await repository.get_events()
    assert len(events) == 1
    assert events[0].id == "evt-1"
    assert events[0].data["node_id"] == 24


async def test_event_filters_by_subject(repository: StorageRepository) -> None:
    await repository.insert_event(_sample_event("evt-a", subject_id="matter_node:24"))
    await repository.insert_event(_sample_event("evt-b", subject_id="matter_node:25"))
    filtered = await repository.get_events(
        subject_type=EventSubjectType.MATTER_NODE.value,
        subject_id="matter_node:24",
    )
    assert len(filtered) == 1
    assert filtered[0].id == "evt-a"


async def test_event_filters_by_timestamp_window(repository: StorageRepository) -> None:
    old = _sample_event("evt-old", at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC))
    recent = _sample_event("evt-new", at=datetime(2026, 6, 12, 12, 0, tzinfo=UTC))
    await repository.insert_event(old)
    await repository.insert_event(recent)

    since = datetime(2026, 6, 1, tzinfo=UTC)
    until = datetime(2026, 6, 30, tzinfo=UTC)
    filtered = await repository.get_events(since=since, until=until)
    assert [event.id for event in filtered] == ["evt-new"]
    assert await repository.count_events(since=since, until=until) == 1


async def test_event_retention_deletes_old_events(repository: StorageRepository) -> None:
    old = _sample_event("evt-old", at=datetime(2026, 1, 1, tzinfo=UTC))
    recent = _sample_event("evt-new", at=datetime(2026, 6, 12, tzinfo=UTC))
    await repository.insert_event(old)
    await repository.insert_event(recent)

    cutoff = datetime(2026, 6, 1, tzinfo=UTC)
    deleted = await repository.delete_events_before(cutoff)
    assert deleted == 1
    remaining = await repository.get_events()
    assert len(remaining) == 1
    assert remaining[0].id == "evt-new"


async def test_cleanup_events_uses_retention_days(repository: StorageRepository) -> None:
    recent = _sample_event("evt-recent", at=datetime.now(UTC) - timedelta(days=1))
    old = _sample_event("evt-old", at=datetime.now(UTC) - timedelta(days=40))
    await repository.insert_event(recent)
    await repository.insert_event(old)

    deleted = await repository.cleanup_events(retention_days=30)
    assert deleted == 1
    remaining = await repository.get_events()
    assert len(remaining) == 1
    assert remaining[0].id == "evt-recent"


async def test_aggregate_increment_get(repository: StorageRepository) -> None:
    bucket = datetime(2026, 6, 12, 10, 0, tzinfo=UTC)
    await repository.increment_aggregate(
        bucket_start=bucket,
        bucket_size=AggregateBucketSize.HOUR,
        metric="matter_node.availability_flaps",
        subject_type=EventSubjectType.MATTER_NODE.value,
        subject_id="matter_node:24",
        amount=2,
    )
    await repository.increment_aggregate(
        bucket_start=bucket,
        bucket_size=AggregateBucketSize.HOUR,
        metric="matter_node.availability_flaps",
        subject_type=EventSubjectType.MATTER_NODE.value,
        subject_id="matter_node:24",
        amount=1,
    )
    aggregates = await repository.get_aggregates(
        metric="matter_node.availability_flaps",
        subject_id="matter_node:24",
    )
    assert len(aggregates) == 1
    assert aggregates[0]["count"] == 3


async def test_pydantic_payload_roundtrip_preserves_none_fields(
    repository: StorageRepository,
) -> None:
    node = MatterNodeState(
        node_id=24,
        server_id="study_matter",
        friendly_name="Living Blind 3",
        subscription_flaps_24h=None,
        case_failures_24h=None,
        subscription_diagnostics_available=False,
    )
    await repository.upsert_model_state(CurrentStateType.MATTER_NODE, "24", node)
    restored = await repository.get_model_state(
        CurrentStateType.MATTER_NODE,
        "24",
        MatterNodeState,
    )
    assert restored is not None
    assert restored.subscription_flaps_24h is None
    assert restored.case_failures_24h is None
    assert restored.subscription_diagnostics_available is False


async def test_schema_init_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "threadlens.db"
    database = Database(db_path)
    await database.connect()
    connection = database.connection()
    await initialize_schema(connection)
    await initialize_schema(connection)
    repo = StorageRepository(database)
    await repo.set_metadata("schema_version", SCHEMA_VERSION)
    assert await repo.get_metadata("schema_version") == SCHEMA_VERSION
    await database.close()


def _sample_event(
    event_id: str,
    *,
    at: datetime | None = None,
    subject_id: str = "matter_node:24",
) -> Event:
    return Event(
        id=event_id,
        timestamp=at or datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
        source_type=EventSourceType.MATTER_SERVER,
        source_id="study_matter",
        event_type="matter_node.unavailable",
        severity=EventSeverity.WARNING,
        subject_type=EventSubjectType.MATTER_NODE,
        subject_id=subject_id,
        message="Matter node became unavailable",
        data={"node_id": 24},
    )
