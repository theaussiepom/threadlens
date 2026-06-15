"""SSE event stream tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from threadlens.config import MdnsConfig, RuntimeMode, ThreadLensConfig
from threadlens.server.app import create_server_app


def _config(tmp_path: Path) -> ThreadLensConfig:
    return ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_server_app(_config(tmp_path), active_mode=RuntimeMode.SERVER))


def test_events_stream_openapi_documents_sse(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        spec = client.get("/openapi.json").json()
    assert "/api/v1/events/stream" in spec["paths"]
    assert "get" in spec["paths"]["/api/v1/events/stream"]
