# Docker deployment examples

## Pironman + Beast Traefik (recommended for Ben Home)

ThreadLens needs **host networking** for mDNS/TREL. On Ben Home that means:

| Host | Role |
|------|------|
| **Pironman** (Study Pi, `192.168.100.4`) | ThreadLens `both` mode with `network_mode: host` |
| **Beast** (`192.168.100.5`) | Traefik HTTPS route via **file provider** `conf.d` → Pironman `:8128` |
| **Lounge Pi** (`192.168.100.7`) | Optional remote `agent` only |

ZigbeeLens runs on Beast in bridge mode with Docker Traefik labels. ThreadLens does **not** — host-network containers on Pironman are reached by a Traefik **router file** on Beast.

### 1. Pironman compose

```bash
# On Pironman
mkdir -p ~/threadlens/config ~/threadlens/data
cp deploy/docker/config.pironman.example.yaml ~/threadlens/config/config.yaml
# Edit ~/threadlens/config/config.yaml — set MQTT host/credentials locally

export THREADLENS_CONFIG_DIR=~/threadlens/config
export THREADLENS_DATA_DIR=~/threadlens/data
docker compose -f deploy/docker/docker-compose.pironman.example.yaml up -d
```

Verify:

```bash
curl -s http://127.0.0.1:8128/api/v1/health | jq
curl -s http://127.0.0.1:8128/api/v1/version | jq
```

### 2. Beast Traefik conf.d

Copy to Beast (adjust paths/domain/IP as needed):

| Source | Beast target |
|--------|----------------|
| `deploy/traefik/threadlens-router.yaml.example` | `/mnt/nas/docker/network/traefik/conf.d/routers/threadlens.yaml` |
| `deploy/traefik/security-headers-threadlens.yaml.example` | `/mnt/nas/docker/network/traefik/conf.d/middlewares/security-headers-threadlens.yaml` |

Update in `threadlens-router.yaml`:

- `Host(\`threadlens.theaussiepom.me\`)` — your subdomain
- `url: "http://192.168.100.4:8128"` — Pironman LAN address

Reload Traefik after copying files.

### 3. Home Assistant / HACS

| Use case | Core URL |
|----------|----------|
| Default (LAN, no reverse proxy) | `http://192.168.100.4:8128` |
| Optional HTTPS / iframe | `https://threadlens.theaussiepom.me` |

Native companion panel remains the default HACS experience. Optional `embed_dashboard` only works when browser security allows (HTTPS HA + HTTPS Core).

## Other compose files (repo root)

| File | Purpose |
|------|---------|
| `docker-compose.host-network.example.yml` | Generic Linux host-network deployment |
| `docker-compose.study-both.example.yml` | Legacy Study Pi example (same topology as Pironman) |
| `docker-compose.lounge-agent.example.yml` | Lounge Pi agent-only |
| `docker-compose.example.yml` | Bridge-mode local development |

## Container layout

| Path | Purpose |
|------|---------|
| `/config/config.yaml` | User configuration (mount read-only) |
| `/data/threadlens.db` | SQLite database |
| `/app/static` | Bundled Core React dashboard |

## Documentation

- [docs/docker.md](../../docs/docker.md) — install, networking, troubleshooting
- [docs/mdns-networking.md](../../docs/mdns-networking.md) — why host networking matters
