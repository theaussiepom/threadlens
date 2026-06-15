"""SSE event stream tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from threadlens.config import MdnsConfig, RuntimeMode, ThreadLensConfig
from threadlens.server.app import create_server_app

REPO_ROOT = Path(__file__).resolve().parents[1]


def _config(tmp_path: Path) -> ThreadLensConfig:
    return ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_server_app(_config(tmp_path), active_mode=RuntimeMode.SERVER))


def _api_paths(app) -> list[str]:
    paths: list[str] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            paths.append(path)
        subroutes = getattr(route, "routes", None)
        if subroutes:
            prefix = path or ""
            for sub in subroutes:
                subpath = getattr(sub, "path", None)
                if subpath:
                    paths.append(f"{prefix}{subpath}")
    return paths


def test_events_stream_route_registered(tmp_path: Path) -> None:
    app = create_server_app(_config(tmp_path), active_mode=RuntimeMode.SERVER)
    paths = _api_paths(app)
    assert "/api/v1/events/stream" in paths


def test_events_stream_openapi_documents_sse(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        spec = client.get("/openapi.json").json()
    assert "/api/v1/events/stream" in spec["paths"]
