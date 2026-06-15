"""Dashboard API endpoint tests."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from threadlens.config import MdnsConfig, RuntimeMode, ThreadLensConfig
from threadlens.server.app import create_server_app

REPO_ROOT = Path(__file__).resolve().parents[1]
THREADLENS_PKG = REPO_ROOT / "threadlens"


def _client(tmp_path: Path) -> TestClient:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )
    return TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER))


def test_status_exposes_diagnostics_thresholds(tmp_path: Path) -> None:
    config = ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
        flapping={"matter_node_read_probe_failures_degraded_24h": 5},
        otbrs=[{"id": "otbr0", "name": "Study OTBR", "rest_url": "http://127.0.0.1:8081"}],
        matter_servers=[
            {"id": "matter0", "name": "Matter Server", "websocket_url": "ws://127.0.0.1:5580/ws"}
        ],
    )
    with TestClient(create_server_app(config, active_mode=RuntimeMode.SERVER)) as client:
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        body = response.json()
        diagnostics = body["diagnostics"]
        assert diagnostics["matter_node_read_probe_failures_degraded_24h"] == 5
        assert "matter_probe_mode" in diagnostics
        assert "otbr_poll_interval_seconds" in diagnostics
        assert body["configured_otbrs"][0]["id"] == "otbr0"
        assert body["configured_matter_servers"][0]["name"] == "Matter Server"
        assert body["features"]["mqtt_discovery"] is True
        assert body["configuration"]["mqtt_topic_prefix"] == "threadlens"


def test_dashboard_endpoint_exists_and_returns_json(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/api/v1/dashboard")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        body = response.json()
        assert body["threadlens"]["api_connected"] is True
        assert body["threadlens"]["version"] == "0.2.19"
        assert "incident" in body
        assert "matter" in body
        assert "otbrs" in body
        assert "report" in body
        assert body["report"]["report_url"] == "api/v1/report.yaml"
        assert body["report"]["report_url_json"] == "api/v1/report.json"


def test_no_home_assistant_imports_in_core_package() -> None:
    offenders: list[str] = []
    for path in THREADLENS_PKG.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("homeassistant"):
                        offenders.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("homeassistant"):
                    offenders.append(f"{path}: from {module}")
    assert offenders == []


def test_core_package_has_no_homeassistant_dependency() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib.metadata as m; print('homeassistant' in "
            "{d.metadata['Name'].lower() for d in m.distributions()})",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "False"
