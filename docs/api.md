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

## Dashboard UI (React, served by Core)

ThreadLens Core serves the canonical dashboard UI at `/`. It is a **React + TypeScript** app (built with Vite) whose source lives in `web/`. The production bundle is built into `static/` and shipped inside the Docker image — **no Node is required at runtime**, and the dashboard uses **no external CDN**. The same React build serves both desktop and mobile; the layout is mobile-first and responsive.

The dashboard consumes only the read-only `api/v1/dashboard` payload via path-safe relative URLs (`new URL("api/v1/dashboard", new URL(".", location.href))`). It works unchanged when hosted at the root, behind a reverse proxy subpath, or under a Home Assistant Ingress path prefix. It does not call Home Assistant, `hass.callWS`, or any HA report proxy.

The dashboard shows an incident summary (OK / Watch / Incident / Unknown), at-a-glance Matter node health grouped by severity with a full node drilldown, OTBR / Thread network / Matter server status, mDNS/TREL observation, MQTT state, report links, and expandable raw diagnostics. Report YAML/JSON links open directly from Core using relative `api/v1/report.yaml` and `api/v1/report.json` URLs. Reconciled OTBR endpoint mismatches are informational (details-only), and foreign TREL visibility alone is informational.

Core serves the dashboard from a configurable directory (`THREADLENS_STATIC_DIR`, default `/app/static` in the container image). Unknown frontend routes fall back to the dashboard shell for SPA routing, while `/api/...`, `/docs`, `/redoc`, and `/openapi.json` are never swallowed. API-only mode still works when built assets are absent — `GET /` returns an HTML link page and all `/api/v1/...` routes behave as before.

### Building the dashboard locally

The built bundle is generated (not committed). For local non-Docker runs:

```bash
npm --prefix web ci
npm --prefix web run build   # emits static/index.html + static/assets/
```

The Docker image build runs this automatically in a Node build stage. See [`web/README.md`](../web/README.md).

The HACS integration dashboard remains the current production UI for Home Assistant users until the HACS migration pass; this Core dashboard does not depend on Home Assistant or HACS. The HAOS add-on Ingress integration follows after Core `0.2.0` is released.

## Related docs

- [Reports](reports.md)
- [Configuration](configuration.md)
- [Security](security.md)
