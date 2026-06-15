"""Tests for the canonical Core React dashboard source and built assets.

The dashboard is a React/Vite app under ``web/``. Its production bundle is built
into ``static/`` (by ``npm --prefix web run build``, the Docker image build, or
CI) and is intentionally not committed. These tests validate the committed
source for path-safety and Home-Assistant independence, and validate the built
output only when it is present (so the Python test job does not require Node).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from threadlens.config import MdnsConfig, RuntimeMode, ThreadLensConfig
from threadlens.server.app import create_server_app

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = REPO_ROOT / "web"
WEB_SRC = WEB_DIR / "src"
REPO_STATIC = REPO_ROOT / "static"
BUILT_INDEX = REPO_STATIC / "index.html"


def _config(tmp_path: Path) -> ThreadLensConfig:
    return ThreadLensConfig(
        storage={"sqlite_path": str(tmp_path / "threadlens.db")},
        mdns=MdnsConfig(enabled=False),
    )


def _source_text(*suffixes: str) -> str:
    parts: list[str] = []
    for path in sorted(WEB_SRC.rglob("*")):
        if path.is_file() and path.suffix in suffixes:
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_web_app_source_exists() -> None:
    assert (WEB_DIR / "package.json").is_file()
    assert (WEB_DIR / "index.html").is_file()
    assert (WEB_DIR / "vite.config.ts").is_file()
    assert (WEB_SRC / "main.tsx").is_file()
    assert (WEB_SRC / "App.tsx").is_file()


def test_vite_uses_relative_base_and_static_outdir() -> None:
    cfg = (WEB_DIR / "vite.config.ts").read_text(encoding="utf-8")
    assert 'base: "./"' in cfg
    assert 'outDir: "../static"' in cfg


def test_source_calls_relative_dashboard_endpoint() -> None:
    src = _source_text(".ts", ".tsx")
    assert "api/v1/dashboard" in src
    # Path-safe resolution against the document location (not an absolute path).
    assert "new URL(" in src
    assert '"/api/v1/dashboard"' not in src


def test_source_report_urls_relative() -> None:
    src = _source_text(".ts", ".tsx")
    assert "api/v1/report.yaml" in src
    assert "api/v1/report.json" in src


def test_source_has_no_home_assistant_websocket() -> None:
    src = _source_text(".ts", ".tsx")
    assert "callWS" not in src
    assert "hass" not in src
    assert "threadlens/dashboard" not in src


def test_source_has_no_ha_report_proxy() -> None:
    src = _source_text(".ts", ".tsx")
    assert "auth/sign_path" not in src
    assert "report_proxy_url" not in src
    assert "hassio_ingress" not in src


def test_source_has_no_external_origins() -> None:
    for path in sorted(WEB_SRC.rglob("*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx", ".css"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "http://" not in text, path
        assert "https://" not in text, path
        assert "cdn." not in text, path


def test_source_uses_dark_zl_theme() -> None:
    css = (WEB_SRC / "index.css").read_text(encoding="utf-8")
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert "--color-zl-bg" in css
    assert "color-scheme: dark" in html


def test_source_is_mobile_first_responsive() -> None:
    app_shell = (WEB_SRC / "components" / "AppShell.tsx").read_text(encoding="utf-8")
    # Mobile nav + desktop sidebar; Tailwind min-width enhancements.
    assert "lg:hidden" in app_shell
    assert "lg:flex" in app_shell
    assert "sm:px-6" in app_shell


def test_source_uses_router_pages_not_single_scroll_layout() -> None:
    app = (WEB_SRC / "App.tsx").read_text(encoding="utf-8")
    assert "BrowserRouter" in app
    assert "AppShell" in app
    assert "OverviewPage" in app
    assert "HowItWorksPage" in app
    assert "InfrastructurePage" in app
    assert "ReportsPage" in app
    assert "InfraColumnLayout" not in app


def test_source_has_sse_live_updates() -> None:
    src = _source_text(".ts", ".tsx")
    assert "api/v1/events/stream" in src
    assert "EventSource" in src
    assert "liveConnection" in src


def test_how_it_works_page_explains_read_only_scope() -> None:
    page = (WEB_SRC / "pages" / "HowItWorksPage.tsx").read_text(encoding="utf-8")
    guide = (WEB_SRC / "lib" / "monitoringGuide.ts").read_text(encoding="utf-8")
    assert "How monitoring works" in page
    assert "monitoringGuide" in page
    assert "GuideTable" in page
    assert "Read-only guarantee" in page
    assert "nodeClassificationRows" in guide
    assert "thresholdRows" in guide


def test_reports_page_uses_keyvalue_and_relative_links() -> None:
    reports = (WEB_SRC / "pages" / "ReportsPage.tsx").read_text(encoding="utf-8")
    assert "KeyValue" in reports
    assert "resolveUrl" in reports
    assert "REPORT_YAML_PATH" in reports


# ---- Built-output checks (run only when the dashboard has been built) ----


@pytest.mark.skipif(not BUILT_INDEX.is_file(), reason="dashboard not built into static/")
def test_built_index_uses_relative_assets() -> None:
    content = BUILT_INDEX.read_text(encoding="utf-8")
    assert "./assets/" in content
    assert "./favicon.svg" in content
    assert "./favicon.ico" in content
    assert "./apple-touch-icon.png" in content
    assert "http://" not in content
    assert "https://" not in content
    # No root-absolute asset URLs (would break under a path prefix / Ingress).
    assert 'src="/' not in content
    assert 'href="/' not in content


@pytest.mark.skipif(not BUILT_INDEX.is_file(), reason="dashboard not built into static/")
def test_built_dashboard_served_at_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("THREADLENS_STATIC_DIR", str(REPO_STATIC))
    with TestClient(create_server_app(_config(tmp_path), active_mode=RuntimeMode.SERVER)) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert 'id="root"' in response.text
        # API routes are not swallowed by the SPA fallback.
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.headers["content-type"].startswith("application/json")
        missing = client.get("/api/v1/nope")
        assert missing.status_code == 404


@pytest.mark.skipif(not BUILT_INDEX.is_file(), reason="dashboard not built into static/")
def test_unknown_frontend_route_falls_back_to_dashboard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("THREADLENS_STATIC_DIR", str(REPO_STATIC))
    with TestClient(create_server_app(_config(tmp_path), active_mode=RuntimeMode.SERVER)) as client:
        response = client.get("/some/spa/route")
        assert response.status_code == 200
        assert 'id="root"' in response.text
