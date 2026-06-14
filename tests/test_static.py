"""Static dashboard UI serving tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from threadlens.config import MdnsConfig, RuntimeMode, ThreadLensConfig
from threadlens.server.app import create_server_app
from threadlens.server.static import api_landing_page, resolve_static_dir

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_STATIC = REPO_ROOT / "static"


def _config(tmp_path: Path) -> ThreadLensConfig:
    return ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_server_app(_config(tmp_path), active_mode=RuntimeMode.SERVER))


def _write_static(static_dir: Path, *, with_assets: bool = False) -> None:
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "index.html").write_text(
        "<html><body>ThreadLens Dashboard placeholder</body></html>",
        encoding="utf-8",
    )
    if with_assets:
        assets = static_dir / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log('threadlens');", encoding="utf-8")


def test_core_starts_when_no_static_assets_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "threadlens.server.static.resolve_static_dir",
        lambda: None,
    )
    with _client(tmp_path) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200


def test_api_routes_work_when_static_assets_present(tmp_path: Path, monkeypatch) -> None:
    static = tmp_path / "static"
    _write_static(static)
    monkeypatch.setenv("THREADLENS_STATIC_DIR", str(static))
    with _client(tmp_path) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        dashboard = client.get("/api/v1/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.headers["content-type"].startswith("application/json")


def test_root_serves_index_when_static_assets_exist(tmp_path: Path, monkeypatch) -> None:
    static = tmp_path / "static"
    _write_static(static)
    monkeypatch.setenv("THREADLENS_STATIC_DIR", str(static))
    with _client(tmp_path) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "ThreadLens Dashboard placeholder" in response.text


def test_root_serves_api_landing_when_static_assets_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "threadlens.server.static.resolve_static_dir",
        lambda: None,
    )
    with _client(tmp_path) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Dashboard static assets are not installed" in response.text
        assert "/api/v1/dashboard" in response.text


def test_unknown_frontend_route_falls_back_to_index(tmp_path: Path, monkeypatch) -> None:
    static = tmp_path / "static"
    _write_static(static)
    monkeypatch.setenv("THREADLENS_STATIC_DIR", str(static))
    with _client(tmp_path) as client:
        response = client.get("/nodes/example")
        assert response.status_code == 200
        assert "ThreadLens Dashboard placeholder" in response.text


def test_api_health_not_swallowed_by_spa_fallback(tmp_path: Path, monkeypatch) -> None:
    static = tmp_path / "static"
    _write_static(static)
    monkeypatch.setenv("THREADLENS_STATIC_DIR", str(static))
    with _client(tmp_path) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert "ThreadLens Dashboard placeholder" not in response.text


def test_missing_api_route_returns_api_style_404(tmp_path: Path, monkeypatch) -> None:
    static = tmp_path / "static"
    _write_static(static)
    monkeypatch.setenv("THREADLENS_STATIC_DIR", str(static))
    with _client(tmp_path) as client:
        response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")
        assert "ThreadLens Dashboard placeholder" not in response.text


def test_docs_redoc_and_openapi_not_swallowed(tmp_path: Path, monkeypatch) -> None:
    static = tmp_path / "static"
    _write_static(static)
    monkeypatch.setenv("THREADLENS_STATIC_DIR", str(static))
    with _client(tmp_path) as client:
        docs = client.get("/docs")
        assert docs.status_code == 200
        assert "ThreadLens Dashboard placeholder" not in docs.text

        redoc = client.get("/redoc")
        assert redoc.status_code == 200
        assert "ThreadLens Dashboard placeholder" not in redoc.text

        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        assert openapi.headers["content-type"].startswith("application/json")
        assert "ThreadLens Dashboard placeholder" not in openapi.text


def test_threadlens_static_dir_override(tmp_path: Path, monkeypatch) -> None:
    custom = tmp_path / "custom-static"
    _write_static(custom, with_assets=True)
    monkeypatch.setenv("THREADLENS_STATIC_DIR", str(custom))
    assert resolve_static_dir() == custom

    with _client(tmp_path) as client:
        assert client.get("/assets/app.js").status_code == 200
        assert "ThreadLens Dashboard placeholder" in client.get("/").text


def test_repo_static_index_exists_for_packaging() -> None:
    index = REPO_STATIC / "index.html"
    assert index.is_file()
    content = index.read_text(encoding="utf-8")
    assert "ThreadLens Dashboard" in content
    assert 'href="dashboard.css"' in content
    assert 'src="dashboard.js"' in content
    assert 'id="tl-app"' in content


def test_api_landing_page_includes_core_links() -> None:
    page = api_landing_page(version="0.2.0")
    assert "Dashboard static assets are not installed" in page
    assert "/api/v1/dashboard" in page
    assert "/docs" in page
