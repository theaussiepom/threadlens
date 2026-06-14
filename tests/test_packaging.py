"""Packaging, docs-adjacent config, and version tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from threadlens import __version__
from threadlens.config import RuntimeMode, load_config
from threadlens.server.app import create_server_app

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_CONFIG = REPO_ROOT / "examples" / "config" / "config.yaml"
BRIDGE_COMPOSE = REPO_ROOT / "docker-compose.example.yml"
HOST_COMPOSE = REPO_ROOT / "docker-compose.host-network.example.yml"
DOCKERFILE = REPO_ROOT / "Dockerfile"


def test_examples_config_validates() -> None:
    config = load_config(EXAMPLES_CONFIG)
    assert config.site.name == "Home"
    assert config.server.port == 8128
    assert config.agent.port == 8129
    assert config.mqtt.enabled is False
    assert config.mdns.enabled is True
    assert config.reports.redact_secrets is True
    assert config.homeassistant.mqtt_discovery_enabled is True
    assert config.otbrs == []
    assert config.matter_servers == []


def test_docker_compose_bridge_ports_and_paths() -> None:
    compose = yaml.safe_load(BRIDGE_COMPOSE.read_text(encoding="utf-8"))
    service = compose["services"]["threadlens"]
    assert service["ports"] == ["8128:8128", "8129:8129"]
    assert "./examples/config:/config:ro" in service["volumes"]
    assert service["environment"]["THREADLENS_CONFIG_PATH"] == "/config/config.yaml"


def test_docker_compose_host_network_mode() -> None:
    compose = yaml.safe_load(HOST_COMPOSE.read_text(encoding="utf-8"))
    service = compose["services"]["threadlens"]
    assert service["network_mode"] == "host"
    assert "ports" not in service
    assert service["environment"]["THREADLENS_MODE"] == "both"


def test_dockerfile_exposes_ports_and_healthcheck() -> None:
    content = DOCKERFILE.read_text(encoding="utf-8")
    assert "python:3.12-slim" in content
    assert "EXPOSE 8128 8129" in content
    assert "THREADLENS_CONFIG_PATH=/config/config.yaml" in content
    assert "/api/v1/health" in content
    assert "USER threadlens" in content


def test_api_version_endpoint(tmp_path: Path) -> None:
    from threadlens.config import MdnsConfig, ThreadLensConfig

    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        response = client.get("/api/v1/version")
        assert response.status_code == 200
        assert response.json() == {"tool": "ThreadLens", "version": __version__}


def test_version_is_consistent_across_package_metadata() -> None:
    import tomllib

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__


def test_cli_version_flag() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "threadlens.main", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert f"ThreadLens {__version__}" in result.stdout
