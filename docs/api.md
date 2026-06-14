# REST API

ThreadLens server API base: `http://<host>:8128/api/v1`

No authentication in v1. Trusted LAN only.

## Core endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard UI when static assets are installed; API link page otherwise |
| GET | `/version` | Tool name and version |
| GET | `/dashboard` | Dashboard payload for Core UI (read-only, HA-agnostic) |
| GET | `/health` | Structured health report |
| GET | `/status` | Collector and runtime status |
| GET | `/capabilities` | Capability summary (report-aligned) |
| GET | `/state` | Grouped current state from SQLite |
| GET | `/events` | Recent events (`window=24h\|7d`, optional filters) |
| GET | `/report` | Diagnostic report (YAML default, JSON via Accept) |
| GET | `/report.yaml` | Diagnostic report (YAML) |
| GET | `/report.json` | Diagnostic report (JSON) |

## Data endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/otbrs` | OTBR current state |
| GET | `/networks` | Thread network current state |
| GET | `/matter-servers` | Matter Server current state |
| GET | `/matter-nodes` | Matter node current state |
| GET | `/mdns/services` | Observed mDNS services |
| GET | `/trel/services` | Observed TREL services |

## Agent endpoints (port 8129)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/agent/health` | Agent process health |
| GET | `/api/v1/agent/status` | Agent capability summary |
| GET | `/api/v1/agent/capabilities` | Agent capabilities |
| GET | `/api/v1/agent/info` | Agent metadata |

## Examples

```bash
curl http://localhost:8128/api/v1/dashboard
curl http://localhost:8128/api/v1/health
curl http://localhost:8128/api/v1/capabilities
curl http://localhost:8128/api/v1/state
curl "http://localhost:8128/api/v1/events?window=7d&limit=50"
curl http://localhost:8128/api/v1/report.yaml
```

## Events query parameters

| Parameter | Values | Description |
|-----------|--------|-------------|
| `window` | `24h`, `7d` | Time window (default `24h`) |
| `limit` | 1–500 | Maximum events returned (default 100) |
| `subject_type` | string | Optional subject type filter |
| `subject_id` | string | Optional subject id filter |
| `event_type` | string | Optional event type filter |

## Dashboard endpoint

`GET /api/v1/dashboard` returns a read-only, bounded JSON payload intended for the future Core-served dashboard UI. It aggregates health, OTBR, Matter, mDNS, TREL, MQTT status, recent events, and report links from Core storage — without Home Assistant device/entity registry enrichment.

During the migration period, the HACS integration may still serve its own dashboard panel; this endpoint is the canonical Core-side data source.

## Dashboard UI (static assets)

ThreadLens Core serves the canonical dashboard UI at `/`. The dashboard is dependency-free vanilla HTML/CSS/JS (no Node/Vite build, no external CDN) shipped in `static/` and consumes the read-only `api/v1/dashboard` payload via path-safe relative URLs. It works when hosted at the root, behind a reverse proxy, or under a Home Assistant Ingress path prefix.

The dashboard shows an incident summary, at-a-glance Matter node health with drilldown, OTBR/Thread network/Matter server status, mDNS/TREL observation, MQTT state, report links, and expandable raw diagnostics. Report YAML/JSON links open directly from Core using relative `api/v1/report.yaml` and `api/v1/report.json` URLs (no Home Assistant signed-path proxy).

Core serves the dashboard from a configurable directory (`THREADLENS_STATIC_DIR`, default `/app/static` in the container image). Unknown frontend routes fall back to the dashboard shell for SPA routing, while `/api/...`, `/docs`, `/redoc`, and `/openapi.json` are never swallowed. API-only mode still works when static assets are absent — `GET /` returns an HTML link page and all `/api/v1/...` routes behave as before.

The HACS integration dashboard remains the current production UI for Home Assistant users until the HACS migration pass; this Core dashboard does not depend on Home Assistant or HACS.

## Related docs

- [Reports](reports.md)
- [Configuration](configuration.md)
- [Security](security.md)
