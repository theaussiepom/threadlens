"""Health and status API smoke tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from threadlens.agent.app import create_agent_app
from threadlens.config import MdnsConfig, RuntimeMode, ThreadLensConfig
from threadlens.server.app import create_server_app


def test_server_health_and_status(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        body = health.json()
        assert body["service"] == "threadlens-server"
        assert "overall" in body
        assert "environment" in body
        assert "state" in body["overall"]

        status = client.get("/api/v1/status")
        assert status.status_code == 200
        status_body = status.json()
        assert status_body["status"] == "running"
        assert status_body["storage"]["ready"] is True


def test_agent_health() -> None:
    config = ThreadLensConfig()
    with TestClient(create_agent_app(config)) as client:
        health = client.get("/api/v1/agent/health")
        assert health.status_code == 200
        body = health.json()
        assert body["service"] == "threadlens-agent"
        assert body["state"] == "healthy"
        assert body["reasons"] == []


def test_server_status_includes_agents_block(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        status = client.get("/api/v1/status")
        assert status.status_code == 200
        assert status.json()["agents"] == {"configured": 0}
