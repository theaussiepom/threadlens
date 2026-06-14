# ThreadLens

**Open source** (MIT License) — read-only observability for Thread, OpenThread Border Routers (OTBR), TREL, mDNS/DNS-SD, Matter Server, and Matter-over-Thread node health.

ThreadLens is **early / pre-1.0 software**. Pin a specific image tag (for example `ghcr.io/theaussiepom/threadlens:0.1.1`) for deployments rather than floating `latest`.

ThreadLens is designed for Home Assistant environments but is not hard-coupled to Home Assistant Core.

## Open source

- Licensed under the [MIT License](LICENSE)
- Read-only observability — does **not** commission devices or mutate Thread, Matter, or OTBR state
- Does **not** use SSH, Docker socket access, or log scraping in normal operation
- Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md)
- Security reports — see [SECURITY.md](SECURITY.md)

## What ThreadLens is

- A **read-only** diagnostics and observability suite
- Collects OTBR REST state, Matter Server websocket inventory, and optional mDNS/TREL visibility
- Publishes Home Assistant MQTT Discovery entities (optional)
- Generates factual YAML/JSON diagnostic reports
- Exposes a local REST API for health, status, and reports

## What ThreadLens is not

- Not a Thread network manager — it does not commission, join, or mutate networks
- Not a Matter controller — it does not issue commands or change node state
- Not authenticated in v1 — intended for trusted LANs only
- Not a root-cause engine — it reports observations and health rollups, not causal claims
- Not an HAOS add-on or HACS integration yet (planned for later passes)

## What it observes

| Source | Examples |
|--------|----------|
| OTBR REST | role, network name, channel, device inventory |
| Matter Server websocket | server info, node inventory, availability |
| mDNS/DNS-SD | `_trel._udp`, `_meshcop._udp`, `_matter._tcp`, `_matterc._udp` |
| Optional ThreadLens agent | co-located capability metadata (v1 is minimal) |
| Internal health engine | environment, OTBR, Matter, mDNS/TREL rollups |

## What it cannot observe yet

- OTBR internal TREL peer tables or counters (unless future agent support is added)
- Matter subscription, CASE, or command diagnostics
- Host logs or Docker-internal state
- SSH or privileged host inspection
- Mutating operations of any kind

Unavailable metrics are reported as `null` or explicit capability flags — not inferred as zero.

## Quick start (Docker Compose)

Pull the published image (recommended):

```bash
docker pull ghcr.io/theaussiepom/threadlens:0.1.1
docker compose -f docker-compose.study-both.example.yml up -d
```

Or build locally for development:

```bash
docker build -t ghcr.io/theaussiepom/threadlens:local .
docker compose -f docker-compose.example.yml up
```

Validate:

```bash
curl http://127.0.0.1:8128/api/v1/health
curl http://127.0.0.1:8128/api/v1/status
curl http://127.0.0.1:8128/api/v1/version
curl http://127.0.0.1:8128/api/v1/report.yaml
```

Copy and edit `examples/config/config.yaml`, then mount it at `/config/config.yaml`.

## mDNS / TREL and Docker networking

Docker **bridge** mode often cannot see LAN multicast DNS. If OTBR REST and Matter work but `/api/v1/mdns/services` and `/api/v1/trel/services` stay empty, this is usually a **network visibility** issue — not proof that TREL is absent on your LAN.

On Linux, use host networking for reliable mDNS observation:

```bash
docker compose -f docker-compose.host-network.example.yml up
```

See [docs/mdns-networking.md](docs/mdns-networking.md) for host networking, macvlan/ipvlan, and HAOS notes.

## Runtime modes

| Mode | Ports | Purpose |
|------|-------|---------|
| `server` | 8128 | Main API, collectors, MQTT, reports |
| `agent` | 8129 | Optional co-located diagnostics agent |
| `both` | 8128 + 8129 | Server and agent in one process |

```bash
threadlens --mode server
threadlens --mode agent
threadlens --mode both
threadlens --version
```

Docker defaults to `--mode server`. Set `THREADLENS_MODE=both` in compose when needed.

## Configuration

Default config path: `/config/config.yaml` (override with `THREADLENS_CONFIG_PATH`).

Example OTBR entries (uncomment in `examples/config/config.yaml`):

```yaml
otbrs:
  - id: "study"
    name: "Study OTBR"
    rest_url: "http://192.168.100.4:8081"
    agent_url: null
  - id: "lounge"
    name: "Lounge OTBR"
    rest_url: "http://192.168.100.7:8081"
    agent_url: null
```

Example Matter Server:

```yaml
matter_servers:
  - id: "study_matter"
    name: "Study Matter Server"
    websocket_url: "ws://192.168.100.4:5580/ws"
    variant: "python"
```

Full reference: [docs/configuration.md](docs/configuration.md)

## Home Assistant / MQTT Discovery

1. Enable Home Assistant's MQTT integration and broker.
2. Set `mqtt.enabled: true` in config with broker host/port.
3. Set `homeassistant.mqtt_discovery_enabled: true` (default) for MQTT Discovery entities.

Entities include environment health, OTBR health, Matter server/node sensors, report URL, and last report timestamp. Per-node entities are enabled by default; per-TREL-service entities are disabled by default.

Details: [docs/mqtt-home-assistant.md](docs/mqtt-home-assistant.md)

## Report API

```bash
curl http://localhost:8128/api/v1/report.yaml
curl -H "Accept: application/json" http://localhost:8128/api/v1/report
curl "http://localhost:8128/api/v1/report.yaml?window=7d&focus_node=24"
```

Reports redact secrets defensively but still include operational metadata (network names, node IDs, health reasons). See [docs/reports.md](docs/reports.md).

## Health API

```bash
curl http://localhost:8128/api/v1/health
```

Returns structured health for overall environment, OTBRs, Matter servers/nodes, and mDNS/TREL observation. Reason codes explain degraded states without claiming root cause.

## Security model

- **No authentication in v1** — bind to trusted LAN only
- **Do not expose publicly** without a reverse proxy and auth
- Reports redact passwords/tokens/keys but still contain operational metadata
- MQTT credentials are used only for broker connection and must not appear in reports
- No SSH, Docker socket access, or mutating Thread/Matter operations

Details: [docs/security.md](docs/security.md)

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| No mDNS/TREL services | Docker bridge networking; try host networking on Linux |
| OTBR unreachable | Wrong `rest_url`, firewall, or OTBR not on same network |
| Matter Server disconnected | Wrong websocket URL, server down, or network issue |
| MQTT not connecting | Broker host/port/credentials; integration not enabled in HA |
| Report mostly empty | Collectors not configured or no observations yet |

More: [docs/troubleshooting.md](docs/troubleshooting.md)

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

export THREADLENS_CONFIG_PATH=./examples/config/config.yaml
threadlens --mode server
pytest -q
ruff check .
ruff format --check .
./scripts/smoke.sh
```

Docker build:

```bash
docker build -t ghcr.io/theaussiepom/threadlens:local .
```

Release checklist: [RELEASE.md](RELEASE.md)  
Changelog: [CHANGELOG.md](CHANGELOG.md)

Published image: `ghcr.io/theaussiepom/threadlens:0.1.1`

## Live test (Ben Home topology — example)

For a two-Pi live test with Study (`.4`) running `both` mode and Lounge (`.7`) running `agent` mode:

- Runbook: [LIVE_TEST_0.1.0.md](LIVE_TEST_0.1.0.md)
- Study config: [examples/live/study-both.config.yaml](examples/live/study-both.config.yaml)
- Lounge config: [examples/live/lounge-agent.config.yaml](examples/live/lounge-agent.config.yaml)
- Study compose: [docker-compose.study-both.example.yml](docker-compose.study-both.example.yml)
- Lounge compose: [docker-compose.lounge-agent.example.yml](docker-compose.lounge-agent.example.yml)

Set MQTT broker host and credentials in your local copy only — do not commit passwords. The committed example uses `broker.mqtt` with `username`/`password: null`.

## Documentation

- [Configuration](docs/configuration.md)
- [REST API](docs/api.md)
- [Docker](docs/docker.md)
- [Live test 0.1.0 (example topology)](../LIVE_TEST_0.1.0.md)
- [mDNS networking](docs/mdns-networking.md)
- [MQTT / Home Assistant](docs/mqtt-home-assistant.md)
- [Reports](docs/reports.md)
- [Security](docs/security.md)
- [Troubleshooting](docs/troubleshooting.md)

## Home Assistant OS add-on

For Home Assistant OS, use the separate [threadlens-ha-addon](https://github.com/theaussiepom/threadlens-ha-addon) repository.

## HACS integration

For API/dashboard polish in Home Assistant, use the [threadlens-ha-integration](https://github.com/theaussiepom/threadlens-ha-integration) custom integration. MQTT Discovery remains the primary entity surface.

## License

MIT
