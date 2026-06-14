"""API surface and summary endpoint tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from threadlens.config import MdnsConfig, RuntimeMode, ThreadLensConfig
from threadlens.models.events import Event, EventSeverity, EventSourceType, EventSubjectType
from threadlens.server.app import create_server_app
from threadlens.storage.repositories import StorageRepository
from threadlens.utils.time import utc_now


def _client(tmp_path: Path) -> TestClient:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )
    return TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER))


def test_capabilities_state_and_events_endpoints(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        capabilities = client.get("/api/v1/capabilities")
        assert capabilities.status_code == 200
        body = capabilities.json()
        assert "mdns_observation" in body
        assert body["matter_subscription_diagnostics"] is False

        state = client.get("/api/v1/state")
        assert state.status_code == 200
        state_body = state.json()
        assert "objects" in state_body
        assert state_body["count"] == 0

        events = client.get("/api/v1/events")
        assert events.status_code == 200
        events_body = events.json()
        assert events_body["window"] == "24h"
        assert events_body["count"] == 0

        bad_window = client.get("/api/v1/events?window=30d")
        assert bad_window.status_code == 400


async def _seed_event(repository: StorageRepository) -> None:
    await repository.insert_event(
        Event(
            id="evt-1",
            timestamp=utc_now(),
            source_type=EventSourceType.THREADLENS,
            source_id="server",
            event_type="startup",
            severity=EventSeverity.INFO,
            subject_type=EventSubjectType.THREAD_NETWORK,
            subject_id="network-1",
            message="ThreadLens started",
            data={},
        )
    )


def test_events_endpoint_returns_recent_events(tmp_path: Path) -> None:
    import asyncio

    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )
    app = create_server_app(config, active_mode=RuntimeMode.SERVER)
    with TestClient(app) as client:
        repository: StorageRepository = app.state.storage
        asyncio.run(_seed_event(repository))
        response = client.get("/api/v1/events?limit=10")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert body["events"][0]["event_type"] == "startup"
