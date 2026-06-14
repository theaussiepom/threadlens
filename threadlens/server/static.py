"""Static dashboard UI serving for Core and container deployments."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

_RESERVED_PATHS = frozenset({"docs", "redoc", "openapi.json"})


def resolve_static_dir() -> Path | None:
    """Return the directory containing a built dashboard UI, if available."""
    candidates: list[Path] = []
    env_dir = os.environ.get("THREADLENS_STATIC_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.extend(
        [
            Path("/app/static"),
            Path(__file__).resolve().parents[2] / "static",
        ]
    )
    for candidate in candidates:
        index = candidate / "index.html"
        if index.is_file():
            return candidate
    return None


def _is_reserved_path(full_path: str) -> bool:
    normalized = full_path.strip("/")
    if not normalized:
        return False
    if normalized in _RESERVED_PATHS:
        return True
    return normalized == "api" or normalized.startswith("api/")


def api_landing_page(*, version: str) -> str:
    """HTML landing page when dashboard static assets are not installed."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>ThreadLens</title></head>
<body>
  <h1>ThreadLens</h1>
  <p>ThreadLens is running (v{version}). Dashboard static assets are not installed.</p>
  <p>API-only mode is active. Use the REST endpoints below or install built dashboard assets.</p>
  <ul>
    <li><a href="/api/v1/dashboard">/api/v1/dashboard</a></li>
    <li><a href="/api/v1/health">/api/v1/health</a></li>
    <li><a href="/api/v1/status">/api/v1/status</a></li>
    <li><a href="/api/v1/capabilities">/api/v1/capabilities</a></li>
    <li><a href="/api/v1/state">/api/v1/state</a></li>
    <li><a href="/api/v1/events">/api/v1/events</a></li>
    <li><a href="/api/v1/otbrs">/api/v1/otbrs</a></li>
    <li><a href="/api/v1/networks">/api/v1/networks</a></li>
    <li><a href="/api/v1/matter-servers">/api/v1/matter-servers</a></li>
    <li><a href="/api/v1/matter-nodes">/api/v1/matter-nodes</a></li>
    <li><a href="/api/v1/mdns/services">/api/v1/mdns/services</a></li>
    <li><a href="/api/v1/trel/services">/api/v1/trel/services</a></li>
    <li><a href="/api/v1/report.yaml">/api/v1/report.yaml</a></li>
    <li><a href="/api/v1/report.json">/api/v1/report.json</a></li>
    <li><a href="/docs">/docs</a></li>
    <li><a href="/redoc">/redoc</a></li>
  </ul>
</body>
</html>"""


def mount_static_ui(app: FastAPI) -> bool:
    """Serve the dashboard UI from Core when static assets are present."""
    static_dir = resolve_static_dir()
    if static_dir is None:
        return False

    index_path = static_dir / "index.html"
    assets_dir = static_dir / "assets"

    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="static-assets")

    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    async def spa_root() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        if _is_reserved_path(full_path):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = static_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)

    return True
