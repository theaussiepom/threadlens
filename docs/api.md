# REST API

ThreadLens server API base: `http://<host>:8128/api/v1`

No authentication in v1. Trusted LAN only.

## Core endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | HTML index with API links |
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

## Related docs

- [Reports](reports.md)
- [Configuration](configuration.md)
- [Security](security.md)
