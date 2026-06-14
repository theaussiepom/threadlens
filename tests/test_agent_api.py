"""ThreadLens agent API tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from threadlens import __version__
from threadlens.agent.app import create_agent_app
from threadlens.config import MdnsConfig, OtbrConfig, RuntimeMode, ThreadLensConfig
from threadlens.main import main
from threadlens.models.health import HealthState
from threadlens.server.app import create_server_app

PRIVILEGED_KEYS = {
    "hostname",
    "host",
    "uname",
    "docker",
    "docker_socket",
    "ssh_key",
    "private_key",
    "passwd",
    "shadow",
    "process_list",
    "mounts",
    "filesystem",
}


def _collect_keys(payload: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.add(str(key).lower())
            keys.update(_collect_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            keys.update(_collect_keys(item))
    return keys


@pytest.fixture
def agent_client() -> TestClient:
    config = ThreadLensConfig(site={"name": "Home"})
    with TestClient(create_agent_app(config)) as client:
        yield client


def test_agent_health_returns_healthy_running_agent(agent_client: TestClient) -> None:
    response = agent_client.get("/api/v1/agent/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "service": "threadlens-agent",
        "version": __version__,
        "mode": "agent",
        "site": "Home",
        "state": HealthState.HEALTHY.value,
        "reasons": [],
    }


def test_agent_status_returns_capability_summary(agent_client: TestClient) -> None:
    response = agent_client.get("/api/v1/agent/status")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "threadlens-agent"
    assert body["mode"] == "agent"
    assert body["site"] == "Home"
    assert body["started_at"] is not None
    capabilities = body["capabilities"]
    assert capabilities["local_process"] is True
    assert capabilities["otbr_local_diagnostics"] is False
    assert capabilities["otbr_internal_trel_peer_table"] is False
    assert capabilities["otbr_internal_trel_counters"] is False
    assert capabilities["local_log_evidence"] is False


def test_agent_capabilities_marks_privileged_features_unavailable(agent_client: TestClient) -> None:
    response = agent_client.get("/api/v1/agent/capabilities")
    assert response.status_code == 200
    agent = response.json()["agent"]
    assert agent["available"] is True
    assert agent["docker_socket_available"] is False
    assert agent["ssh_available"] is False
    assert agent["mutation_allowed"] is False
    assert agent["local_log_evidence"] is False
    assert agent["otbr_local_diagnostics"] is False


def test_agent_api_does_not_expose_privileged_host_data(agent_client: TestClient) -> None:
    endpoints = (
        "/api/v1/agent/health",
        "/api/v1/agent/status",
        "/api/v1/agent/capabilities",
        "/api/v1/agent/info",
    )
    for endpoint in endpoints:
        payload = agent_client.get(endpoint).json()
        keys = _collect_keys(payload)
        assert keys.isdisjoint(PRIVILEGED_KEYS), endpoint


def test_agent_info_endpoint(agent_client: TestClient) -> None:
    response = agent_client.get("/api/v1/agent/info")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "threadlens-agent"
    assert body["mutation_allowed"] is False


def test_agent_mode_starts_via_cli_parser() -> None:
    config_path = str(Path(__file__).parent / "fixtures" / "example_config.yaml")
    with patch("threadlens.main.run_agent") as run_agent:
        assert main(["--mode", "agent", "--config", config_path]) == 0
        run_agent.assert_called_once()


def test_both_mode_starts_via_cli_parser() -> None:
    config_path = str(Path(__file__).parent / "fixtures" / "example_config.yaml")
    with patch("threadlens.main.run_agent"), patch("threadlens.main.run_server") as run_server:
        assert main(["--mode", "both", "--config", config_path]) == 0
        run_server.assert_called_once()


def test_server_status_includes_agents_block_when_none_configured(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
        otbrs=[],
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        status = client.get("/api/v1/status").json()
        assert status["agents"] == {"configured": 0}


def test_server_status_includes_agents_block_when_configured(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
        otbrs=[
            OtbrConfig(
                id="study",
                name="Study OTBR",
                rest_url="http://127.0.0.1:8081",
                agent_url="http://127.0.0.1:8129",
            )
        ],
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        status = client.get("/api/v1/status").json()
        assert status["agents"]["configured"] == 1
        assert "reachable" in status["agents"]
        assert "unreachable" in status["agents"]
        assert "last_poll_at" in status["agents"]


def test_both_mode_server_and_agent_apps_respond(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.BOTH)) as server_client:
        server_health = server_client.get("/api/v1/health")
        assert server_health.status_code == 200
        server_status = server_client.get("/api/v1/status")
        assert server_status.status_code == 200
        assert server_status.json()["mode"] == "both"

    with TestClient(create_agent_app(config)) as agent_client:
        agent_health = agent_client.get("/api/v1/agent/health")
        assert agent_health.status_code == 200
        assert agent_health.json()["mode"] == "agent"
