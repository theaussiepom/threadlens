"""Tests for the canonical Core dashboard UI assets and serving."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from threadlens.config import MdnsConfig, RuntimeMode, ThreadLensConfig
from threadlens.server.app import create_server_app

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_STATIC = REPO_ROOT / "static"
INDEX_HTML = REPO_STATIC / "index.html"
DASHBOARD_JS = REPO_STATIC / "dashboard.js"
DASHBOARD_CSS = REPO_STATIC / "dashboard.css"


def _config(tmp_path: Path) -> ThreadLensConfig:
    return ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("THREADLENS_STATIC_DIR", str(REPO_STATIC))
    return TestClient(create_server_app(_config(tmp_path), active_mode=RuntimeMode.SERVER))


def test_dashboard_assets_exist() -> None:
    assert INDEX_HTML.is_file()
    assert DASHBOARD_JS.is_file()
    assert DASHBOARD_CSS.is_file()


def test_static_root_serves_real_dashboard_index(tmp_path: Path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "ThreadLens Dashboard" in response.text
        assert 'id="tl-app"' in response.text
        assert 'src="dashboard.js"' in response.text


def test_dashboard_js_and_css_assets_served(tmp_path: Path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        js = client.get("/dashboard.js")
        assert js.status_code == 200
        assert "javascript" in js.headers["content-type"]
        css = client.get("/dashboard.css")
        assert css.status_code == 200
        assert "css" in css.headers["content-type"]


def test_index_references_only_relative_local_assets() -> None:
    content = INDEX_HTML.read_text(encoding="utf-8")
    assert 'href="dashboard.css"' in content
    assert 'src="dashboard.js"' in content
    # No absolute or external asset references.
    assert "http://" not in content
    assert "https://" not in content
    assert 'href="/' not in content
    assert 'src="/' not in content


def test_dashboard_js_calls_relative_dashboard_endpoint() -> None:
    content = DASHBOARD_JS.read_text(encoding="utf-8")
    assert 'apiUrl("api/v1/dashboard")' in content
    assert "new URL(" in content


def test_dashboard_js_has_no_home_assistant_websocket() -> None:
    content = DASHBOARD_JS.read_text(encoding="utf-8")
    assert "callWS" not in content
    assert "hass" not in content
    assert "threadlens/dashboard" not in content


def test_dashboard_js_has_no_ha_report_proxy() -> None:
    content = DASHBOARD_JS.read_text(encoding="utf-8")
    assert "auth/sign_path" not in content
    assert "report_proxy_url" not in content
    assert "/api/hassio_ingress" not in content


def test_dashboard_js_opens_report_yaml_relative() -> None:
    content = DASHBOARD_JS.read_text(encoding="utf-8")
    assert "api/v1/report.yaml" in content
    assert "api/v1/report.json" in content


def test_dashboard_assets_have_no_external_imports() -> None:
    js = DASHBOARD_JS.read_text(encoding="utf-8")
    css = DASHBOARD_CSS.read_text(encoding="utf-8")
    for content in (js, css):
        assert "http://" not in content
        assert "https://" not in content
        assert "cdn." not in content
    # No bare ES module imports or CommonJS requires (no build/runtime deps).
    assert "import " not in js
    assert "require(" not in js


def test_api_routes_not_swallowed_with_real_dashboard(tmp_path: Path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.headers["content-type"].startswith("application/json")
        missing = client.get("/api/v1/nope")
        assert missing.status_code == 404
        assert missing.headers["content-type"].startswith("application/json")


def test_unknown_frontend_route_falls_back_to_dashboard(tmp_path: Path, monkeypatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        response = client.get("/some/spa/route")
        assert response.status_code == 200
        assert 'id="tl-app"' in response.text
