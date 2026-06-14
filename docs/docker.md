# Docker

## Published image (GHCR)

Released images are published by GitHub Actions to:

```text
ghcr.io/theaussiepom/threadlens:0.1.2
```

Pin a specific tag for deployments. `latest` exists but is not recommended for production.

Pull and run without a local build (Linux host networking recommended):

```bash
docker pull ghcr.io/theaussiepom/threadlens:0.1.2
docker compose -f docker-compose.host-network.example.yml up -d
```

See [RELEASE.md](../RELEASE.md) for the tag-driven publish workflow.

## Build (local development only)

```bash
docker build -t ghcr.io/theaussiepom/threadlens:local .
```

Do not use local builds for releases — GHCR publish is automated on version tags.

Image details:

- Python 3.12 slim
- Runs as non-root user `threadlens`
- Creates `/config` and `/data`
- Exposes ports `8128` (server) and `8129` (agent)
- Default env: `THREADLENS_CONFIG_PATH=/config/config.yaml`, `PYTHONUNBUFFERED=1`
- Multi-arch: `linux/amd64`, `linux/arm64`

## Run (bridge networking)

```bash
docker compose -f docker-compose.example.yml up
```

Good for REST/API, OTBR polling, Matter websocket, MQTT, and reports.

**mDNS/TREL may be empty** in bridge mode — see [mdns-networking.md](mdns-networking.md).

## Run (host networking — Linux)

```bash
docker compose -f docker-compose.host-network.example.yml up -d
```

Do not use `ports:` with `network_mode: host`.

## Volumes

| Mount | Purpose |
|-------|---------|
| `./examples/config:/config:ro` | Config file at `/config/config.yaml` |
| `./data:/data` | SQLite database and persistence |

Use a local config override (gitignored) for MQTT credentials — see [configuration.md](configuration.md).

## Healthcheck

The image healthcheck calls:

```text
GET http://127.0.0.1:8128/api/v1/health
```

This assumes default **server** or **both** mode. For **agent-only** containers, override the healthcheck to target port 8129:

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8129/api/v1/agent/health', timeout=3)"]
```

## Runtime modes in Docker

| `THREADLENS_MODE` | APIs |
|-------------------|------|
| `server` | `:8128` |
| `agent` | `:8129` |
| `both` | `:8128` + `:8129` |

Default image `CMD` is `--mode server`.

## Smoke validation

```bash
curl http://127.0.0.1:8128/api/v1/health
curl http://127.0.0.1:8128/api/v1/status
curl http://127.0.0.1:8128/api/v1/version
curl http://127.0.0.1:8128/api/v1/report.yaml
```

With `THREADLENS_MODE=both`:

```bash
curl http://127.0.0.1:8129/api/v1/agent/health
```

## .env example

Copy `.env.example` to `.env` for local compose overrides. `.env` is gitignored.

## Home Assistant OS add-on

A Home Assistant OS add-on repository is available separately:

- Repository: https://github.com/theaussiepom/threadlens-ha-addon
- Wraps `ghcr.io/theaussiepom/threadlens` with host networking for mDNS/TREL
- Default mode: `both`

See the add-on `DOCS.md` for installation and configuration on HAOS.

## Example compose files

| File | Purpose |
|------|---------|
| `deploy/docker/docker-compose.pironman.example.yaml` | **Pironman (Study Pi)** host-network deployment |
| `deploy/traefik/threadlens-router.yaml.example` | **Beast Traefik** `conf.d` router → Pironman |
| `docker-compose.host-network.example.yml` | Generic Linux host-network deployment |
| `docker-compose.study-both.example.yml` | Study Pi both-mode example (same topology as Pironman) |
| `docker-compose.lounge-agent.example.yml` | Agent-only example |
| `docker-compose.example.yml` | Local bridge-mode development build |

See [deploy/docker/README.md](../deploy/docker/README.md) for the Pironman + Beast Traefik setup.

## Maintainer live-test runbook

For a labelled private home topology runbook, see [LIVE_TEST_0.1.0.md](../LIVE_TEST_0.1.0.md). That document is not the default public deployment path.

Published image: `ghcr.io/theaussiepom/threadlens:0.1.2`
