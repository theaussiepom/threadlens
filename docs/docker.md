# Docker

## Published image (GHCR)

Released images are published by GitHub Actions to:

```text
ghcr.io/theaussiepom/threadlens:0.1.1
```

Pull and run without a local build:

```bash
docker pull ghcr.io/theaussiepom/threadlens:0.1.1
docker compose -f docker-compose.study-both.example.yml up -d
```

See [RELEASE.md](../RELEASE.md) for the tag-driven publish workflow.

## Build (local development)

```bash
docker build -t ghcr.io/theaussiepom/threadlens:local .
```

Image details:

- Python 3.12 slim
- Runs as non-root user `threadlens`
- Creates `/config` and `/data`
- Exposes ports `8128` (server) and `8129` (agent)
- Default env: `THREADLENS_CONFIG_PATH=/config/config.yaml`, `PYTHONUNBUFFERED=1`

## Run (bridge networking)

```bash
docker compose -f docker-compose.example.yml up
```

Good for REST/API, OTBR polling, Matter websocket, MQTT, and reports.

**mDNS/TREL may be empty** in bridge mode — see [mdns-networking.md](mdns-networking.md).

## Run (host networking — Linux)

```bash
docker compose -f docker-compose.host-network.example.yml up
```

Do not use `ports:` with `network_mode: host`.

## Volumes

| Mount | Purpose |
|-------|---------|
| `./examples/config:/config:ro` | Config file at `/config/config.yaml` |
| `./data:/data` | SQLite database and persistence |

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

Copy `.env.example` to `.env` for local compose overrides.

## Home Assistant OS add-on

A Home Assistant OS add-on repository is available separately:

- Repository: https://github.com/theaussiepom/threadlens-ha-addon
- Wraps `ghcr.io/theaussiepom/threadlens` with host networking for mDNS/TREL
- Default mode: `both`

See the add-on `DOCS.md` for installation and configuration on HAOS.

## Live test (example topology)

For a two-Pi deployment (Study `.4` in `both` mode, Lounge `.7` in `agent` mode), see:

- [LIVE_TEST_0.1.0.md](../LIVE_TEST_0.1.0.md) (runbook; image tag updated to `0.1.1` in compose files)
- [examples/live/study-both.config.yaml](../examples/live/study-both.config.yaml)
- [examples/live/lounge-agent.config.yaml](../examples/live/lounge-agent.config.yaml)
- [docker-compose.study-both.example.yml](../docker-compose.study-both.example.yml)
- [docker-compose.lounge-agent.example.yml](../docker-compose.lounge-agent.example.yml)

Published image: `ghcr.io/theaussiepom/threadlens:0.1.1`
