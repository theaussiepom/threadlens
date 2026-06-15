# ThreadLens

**Open source** (MIT License) — read-only observability for Thread, OpenThread Border Routers (OTBR), TREL, mDNS/DNS-SD, Matter Server, and Matter-over-Thread node health.

ThreadLens is **early / pre-1.0 software**. Pin a specific image tag (for example `ghcr.io/theaussiepom/threadlens:0.1.2`) for deployments rather than floating `latest`.

ThreadLens is part of the **Lens family** of read-only home-network observability tools, alongside [ZigbeeLens](https://github.com/theaussiepom/zigbeelens). See [docs/lens-family.md](docs/lens-family.md) for shared conventions.

## What problem it solves

Home Assistant Thread and Matter-over-Thread setups span OTBRs, Matter Server, mDNS/TREL visibility, and MQTT entities. When something looks wrong, it is hard to tell whether the OTBR is active, Matter nodes are unavailable, TREL is visible, or mDNS is simply not reachable from a container.

ThreadLens collects **read-only** observations from your LAN, rolls them into health status, publishes optional Home Assistant MQTT Discovery sensors, and generates factual YAML/JSON reports — without commissioning devices or changing network state.

## What ThreadLens observes

| Source | What you get |
|--------|----------------|
| OTBR REST | Role, network name, device inventory, reachability |
| Legacy `/node` fallback | Reconciles stale JSON:API `/api/node` when `use_legacy_node_fallback: true` |
| python-matter-server websocket | Server info, node inventory, availability |
| mDNS/DNS-SD | `_trel._udp`, `_meshcop._udp`, `_matter._tcp`, `_matterc._udp` |
| TREL service visibility | Local and foreign TREL services from mDNS |
| MQTT Discovery | Optional Home Assistant entities for health and inventory |

## What ThreadLens does not do

- Does **not** commission Thread devices or change Thread datasets
- Does **not** send Matter commands or mutate node state
- Does **not** run mutating OTBR actions (`ot-ctl`, POST commissioning, resets)
- Does **not** use SSH, Docker socket access, or log scraping in normal operation
- Does **not** make causal claims or infer device parentage from mDNS/TREL visibility

Unavailable metrics are reported as `null` or explicit capability flags — not inferred as zero.

## Security model

- **No authentication in v1** — run only on a trusted LAN
- Do not expose the API publicly without a reverse proxy and auth
- Reports redact passwords, tokens, and keys defensively (`reports.redact_secrets: true`)
- MQTT credentials are used only for broker connection and must not appear in committed configs or reports

See [SECURITY.md](SECURITY.md) and [docs/security.md](docs/security.md).

## Quick start (Docker)

Pull the published image and use **host networking on Linux** for reliable mDNS/TREL:

```bash
docker pull ghcr.io/theaussiepom/threadlens:0.1.2
mkdir -p data
docker compose -f docker-compose.host-network.example.yml up -d
```

Minimal compose shape:

```yaml
services:
  threadlens:
    image: ghcr.io/theaussiepom/threadlens:0.1.2
    network_mode: host
    volumes:
      - ./examples/config/config.yaml:/config/config.yaml:ro
      - ./data:/data
```

Validate:

```bash
curl http://127.0.0.1:8128/api/v1/health
curl http://127.0.0.1:8128/api/v1/status
curl http://127.0.0.1:8128/api/v1/version
```

Copy [examples/config/config.yaml](examples/config/config.yaml), adjust OTBR/Matter/MQTT hosts for your LAN, and mount at `/config/config.yaml`. For MQTT secrets, use a local override file (gitignored) — see [docs/configuration.md](docs/configuration.md).

## Dashboard

ThreadLens Core serves a **mobile-friendly React dashboard** at `/`. It is an incident console for Thread/Matter-over-Thread: open `http://<host>:8128/` to see the incident summary, at-a-glance Matter node health (with node drilldown), and OTBR/Thread/Matter/mDNS/TREL/MQTT status. The UI is built into the Docker image (no Node at runtime, no external CDN) and reads only the read-only `api/v1/dashboard` payload, so it also works behind a reverse proxy or Home Assistant Ingress.

**Familiar device names** (for example blind names from Home Assistant) are **not** discovered by Core. They are pushed by the [ThreadLens HACS integration](docs/home-assistant-integration.md) when configured. Without it, nodes usually show Matter serials.

The HACS integration companion panel remains available during migration; the HAOS add-on exposes this Core dashboard via Ingress after the Core `0.2.0` release. Dashboard source and build instructions live in [`web/`](web/README.md); see [docs/api.md](docs/api.md).

## Minimal sample config

```yaml
site:
  name: "My ThreadLens Site"

mqtt:
  enabled: true
  host: "homeassistant.local"  # replace with your broker hostname or IP
  port: 1883
  username: null
  password: null

homeassistant:
  mqtt_discovery_enabled: true

otbr:
  use_legacy_node_fallback: true

otbrs:
  - id: "primary"
    name: "Primary OTBR"
    rest_url: "http://192.168.1.10:8081"

matter_servers:
  - id: "home"
    name: "Home Matter Server"
    websocket_url: "ws://192.168.1.10:5580/ws"
    variant: "python"
```

Full sample: [examples/config/config.yaml](examples/config/config.yaml). Both-mode example: [examples/live/study-both.config.yaml](examples/live/study-both.config.yaml).

If you use `broker.mqtt` as the MQTT host, ensure that hostname resolves on your LAN or replace it with your broker IP.

## mDNS / TREL and host networking

Docker **bridge** mode often cannot see LAN multicast DNS. If OTBR REST and Matter work but `/api/v1/mdns/services` and `/api/v1/trel/services` stay empty, this is usually a **network visibility** issue.

On Linux, use host networking:

```bash
docker compose -f docker-compose.host-network.example.yml up -d
```

See [docs/mdns-networking.md](docs/mdns-networking.md) for host networking, macvlan/ipvlan, and HAOS notes.

## Configure OTBRs

Add one entry per border router. URLs must be reachable from the ThreadLens host/container:

```yaml
otbr:
  use_legacy_node_fallback: true

otbrs:
  - id: "primary"
    name: "Primary OTBR"
    rest_url: "http://192.168.1.10:8081"
    agent_url: null
```

ThreadLens uses read-only GET endpoints only. Legacy `/node` reconciliation helps when JSON:API `/api/node` is stale.

## Configure Matter Server

```yaml
matter_servers:
  - id: "home"
    name: "Home Matter Server"
    websocket_url: "ws://192.168.1.10:5580/ws"
    variant: "python"
```

ThreadLens observes inventory and availability — it does not issue Matter control commands. Optional [Matter read probes](docs/matter-read-probes.md) (disabled by default) use safe `read_attribute` reads for read reachability; they do not prove commands work. Future [passive command diagnostics](docs/matter-command-diagnostics-future.md) may observe actual command outcomes separately.

## Configure MQTT / Home Assistant Discovery

1. Enable Home Assistant's MQTT integration and broker.
2. Set `mqtt.enabled: true` with broker host/port.
3. Set credentials in a **local** config file only (`username`/`password` — never commit).
4. Keep `homeassistant.mqtt_discovery_enabled: true` for MQTT Discovery entities.

Details: [docs/mqtt-home-assistant.md](docs/mqtt-home-assistant.md)

## API endpoints

| Endpoint | Purpose |
|----------|---------|
| `/api/v1/health` | Structured health rollups |
| `/api/v1/status` | Collector connectivity and runtime status |
| `/api/v1/otbrs` | OTBR state and embedded health |
| `/api/v1/networks` | Observed Thread networks |
| `/api/v1/matter-nodes` | Matter node inventory |
| `/api/v1/mdns/services` | mDNS service inventory |
| `/api/v1/trel/services` | TREL service inventory |
| `/api/v1/report.yaml` | Factual diagnostic report (YAML) |

Full reference: [docs/api.md](docs/api.md)

## Expected warnings

These are common in real homes and are not necessarily faults:

| Reason | Meaning |
|--------|---------|
| `otbr_rest_endpoint_mismatch` | JSON:API `/api/node` is stale but legacy `/node` shows an active Thread stack |
| `foreign_trel_services_observed` | Foreign Apple/HomePod or other TREL services are visible on the LAN |

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| No mDNS/TREL services | Docker bridge networking — try host networking on Linux |
| OTBR unreachable | Wrong `rest_url`, firewall, or OTBR not on same network |
| Matter Server disconnected | Wrong websocket URL or server down |
| MQTT not connecting | Broker host/port/credentials; integration not enabled in HA |

More: [docs/troubleshooting.md](docs/troubleshooting.md)

## Runtime modes

| Mode | Ports | Purpose |
|------|-------|---------|
| `server` | 8128 | Main API, collectors, MQTT, reports |
| `agent` | 8129 | Optional co-located diagnostics agent |
| `both` | 8128 + 8129 | Server and agent in one process |

## Development

Build locally for development only — releases use GHCR:

```bash
docker build -t ghcr.io/theaussiepom/threadlens:local .
docker compose -f docker-compose.example.yml up
```

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
export THREADLENS_CONFIG_PATH=./examples/config/config.yaml
threadlens --mode server
pytest -q
ruff check .
```

Release checklist: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) — run `./scripts/run-release-checks.sh` before tagging.  
Changelog: [CHANGELOG.md](CHANGELOG.md)

Published image: `ghcr.io/theaussiepom/threadlens:0.1.2`

## Documentation

- [Configuration](docs/configuration.md)
- [Docker](docs/docker.md)
- [Style guide (ZigbeeLens sibling UI)](docs/style-guide.md)
- [HACS embedded view (HTTPS / Traefik)](docs/hacs-embedded-view.md)
- [Home Assistant integration (device names)](docs/home-assistant-integration.md)
- [MQTT / Home Assistant](docs/mqtt-home-assistant.md)
- [Troubleshooting](docs/troubleshooting.md)
- [REST API](docs/api.md)
- [mDNS networking](docs/mdns-networking.md)
- [Reports](docs/reports.md)
- [Security](docs/security.md)

## Contributing and license

- Contributions: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security reports: [SECURITY.md](SECURITY.md)
- License: [MIT](LICENSE)

## Home Assistant add-on and integration

- HAOS add-on: [threadlens-ha-addon](https://github.com/theaussiepom/threadlens-ha-addon)
- HACS integration: [threadlens-ha-integration](https://github.com/theaussiepom/threadlens-ha-integration)

MQTT Discovery remains the primary Home Assistant entity surface in v1.

## Maintainer live-test runbooks

Private live-test runbooks with a specific home topology are kept separately:

- [LIVE_TEST_0.1.0.md](LIVE_TEST_0.1.0.md) — labelled example topology (not the default public deployment path)

Use the published image and [examples/config/config.yaml](examples/config/config.yaml) for normal deployments.
