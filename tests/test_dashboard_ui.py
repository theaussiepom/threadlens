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


def test_source_supports_light_and_dark_theme() -> None:
    theme = (WEB_SRC / "styles" / "theme.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" in theme


def test_source_is_mobile_first_responsive() -> None:
    css = (WEB_SRC / "styles" / "app.css").read_text(encoding="utf-8")
    # Mobile-first: enhancements gated behind min-width breakpoints.
    assert "min-width: 600px" in css
    assert "min-width: 960px" in css


def test_source_infra_sections_use_column_flow_on_desktop() -> None:
    css = (WEB_SRC / "styles" / "app.css").read_text(encoding="utf-8")
    assert ".tl-infra-grid" in css
    # Mobile: single-column stack.
    assert "flex-direction: column" in css
    # Desktop: multi-column flow avoids row-major grid height gaps.
    assert "columns: 2" in css
    assert "columns: 3" in css
    assert "break-inside: avoid" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" not in css


# ---- Built-output checks (run only when the dashboard has been built) ----


@pytest.mark.skipif(not BUILT_INDEX.is_file(), reason="dashboard not built into static/")
def test_built_index_uses_relative_assets() -> None:
    content = BUILT_INDEX.read_text(encoding="utf-8")
    assert "./assets/" in content
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
