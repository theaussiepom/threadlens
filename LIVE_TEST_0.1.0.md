# ThreadLens 0.1.0 — Live test checklist (Ben Home topology)

This document is a **manual live-test runbook** for ThreadLens `0.1.0` on Ben's two-Pi topology. It is an example deployment — not a generic production guide.

Related files:

- Study config: [examples/live/study-both.config.yaml](examples/live/study-both.config.yaml)
- Lounge config: [examples/live/lounge-agent.config.yaml](examples/live/lounge-agent.config.yaml)
- Study compose: [docker-compose.study-both.example.yml](docker-compose.study-both.example.yml)
- Lounge compose: [docker-compose.lounge-agent.example.yml](docker-compose.lounge-agent.example.yml)

---

## 1. Purpose

Validate ThreadLens `0.1.0` end-to-end on a real home network:

- Study Pi (`.4`) runs the **main collector** in `both` mode (server API + co-located agent).
- Lounge Pi (`.7`) runs a **remote agent** only.
- Study Pi polls **both OTBR REST endpoints** (`.4` and `.7`).
- Study Pi connects to the **Matter Server websocket** on `.4`.
- Study Pi publishes **MQTT Discovery** entities when the broker is configured.
- Study Pi observes **mDNS/TREL** when host networking allows multicast visibility.

ThreadLens is read-only. It does not commission, join, mutate, or command Thread/Matter/OTBR state. It reports observations and health rollups — not causal claims. It does not infer Thread parentage from mDNS/TREL visibility.

**During this live test:** do not add features. Only fix observed breakages, packaging issues, or live data-shape mismatches.

---

## 2. Target topology

| Host | IP | Role | APIs |
|------|-----|------|------|
| Study Pi | `192.168.100.4` | `both` mode — main collector | Server `http://192.168.100.4:8128`, Agent `http://192.168.100.4:8129` |
| Lounge Pi | `192.168.100.7` | `agent` mode only | Agent `http://192.168.100.7:8129` |

**Study Pi collectors:**

| Source | URL |
|--------|-----|
| Study OTBR REST | `http://192.168.100.4:8081` |
| Lounge OTBR REST | `http://192.168.100.7:8081` |
| Study agent | `http://192.168.100.4:8129` |
| Lounge agent | `http://192.168.100.7:8129` |
| Matter Server websocket | `ws://192.168.100.4:5580/ws` |
| MQTT broker | Ben to configure (placeholder in config) |

**OTBR config on Study Pi:**

```yaml
otbrs:
  - id: study
    name: Study OTBR
    rest_url: http://192.168.100.4:8081
    agent_url: http://192.168.100.4:8129
  - id: lounge
    name: Lounge OTBR
    rest_url: http://192.168.100.7:8081
    agent_url: http://192.168.100.7:8129
```

---

## 3. Prerequisites

Before starting containers:

- [ ] **Docker** running on both Pis (Linux; host networking required for reliable mDNS/TREL)
- [ ] **Core image** available on both Pis: `ghcr.io/theaussiepom/threadlens:0.1.2` (pull from GHCR after release tag)
- [ ] **Network reachability** between `.4` and `.7` on the LAN
- [ ] **OTBR REST** reachable: `curl http://192.168.100.4:8081/node/state` and `curl http://192.168.100.7:8081/node/state` (or equivalent OTBR health endpoint)
- [ ] **Matter Server** reachable: websocket at `ws://192.168.100.4:5580/ws`
- [ ] **MQTT broker** host/IP known — edit `examples/live/study-both.config.yaml` before starting Study Pi
- [ ] **Host networking** configured in compose files (recommended for mDNS/TREL on Linux/HAOS)
- [ ] **Data directories** writable: `data/study` on `.4`, `data/lounge-agent` on `.7`

Security reminder: ThreadLens v1 has **no API authentication**. Trusted LAN only. Do not expose ports `8128`/`8129` publicly without reverse proxy and auth.

---

## 4. Build commands

On either Pi (or a build machine), from the `threadlens` repo:

```bash
docker build -t ghcr.io/theaussiepom/threadlens:0.1.0 .
```

If building on one Pi and the other lacks the image, save and load:

```bash
docker save ghcr.io/theaussiepom/threadlens:0.1.0 | gzip > threadlens-0.1.0.tar.gz
# copy to other Pi, then:
gunzip -c threadlens-0.1.0.tar.gz | docker load
```

---

## 5. Optional image push/tag commands

If publishing to GitHub Container Registry:

```bash
docker tag ghcr.io/theaussiepom/threadlens:0.1.0 ghcr.io/theaussiepom/threadlens:0.1.0
docker push ghcr.io/theaussiepom/threadlens:0.1.0
```

On each Pi:

```bash
docker pull ghcr.io/theaussiepom/threadlens:0.1.0
```

---

## 6. Lounge Pi (`.7`) — agent-only config

Copy [examples/live/lounge-agent.config.yaml](examples/live/lounge-agent.config.yaml) to the Lounge Pi repo checkout.

Key settings:

- `mode: agent`
- `mqtt.enabled: false`
- `mdns.enabled: false`
- `otbrs: []`
- `matter_servers: []`

---

## 7. Study Pi (`.4`) — both-mode config

Copy [examples/live/study-both.config.yaml](examples/live/study-both.config.yaml) to the Study Pi repo checkout.

**Before starting:** set MQTT broker host to `broker.mqtt` (or your broker hostname) and configure `mqtt.username` / `mqtt.password` in your local config copy only — do not commit secrets.

---

## 8. Docker run — Lounge Pi (`.7`)

From the `threadlens` repo on the Lounge Pi:

```bash
mkdir -p data/lounge-agent
docker compose -f docker-compose.lounge-agent.example.yml up -d
```

Equivalent `docker run`:

```bash
mkdir -p data/lounge-agent
docker run -d \
  --name threadlens-agent \
  --restart unless-stopped \
  --network host \
  -v "$(pwd)/examples/live/lounge-agent.config.yaml:/config/config.yaml:ro" \
  -v "$(pwd)/data/lounge-agent:/data" \
  -e TZ=Australia/Brisbane \
  -e THREADLENS_CONFIG_PATH=/config/config.yaml \
  ghcr.io/theaussiepom/threadlens:0.1.0 \
  --mode agent
```

---

## 9. Docker run — Study Pi (`.4`)

From the `threadlens` repo on the Study Pi (after editing MQTT host in config):

```bash
mkdir -p data/study
docker compose -f docker-compose.study-both.example.yml up -d
```

Equivalent `docker run`:

```bash
mkdir -p data/study
docker run -d \
  --name threadlens \
  --restart unless-stopped \
  --network host \
  -v "$(pwd)/examples/live/study-both.config.yaml:/config/config.yaml:ro" \
  -v "$(pwd)/data/study:/data" \
  -e TZ=Australia/Brisbane \
  -e THREADLENS_CONFIG_PATH=/config/config.yaml \
  ghcr.io/theaussiepom/threadlens:0.1.0 \
  --mode both
```

**Start order:** Lounge agent (`.7`) first, then Study collector (`.4`).

---

## 10. Validation commands (exact order)

Run from any machine on the LAN that can reach both Pis.

### Step 1 — Agent health/status on `.4` and `.7`

```bash
curl -s http://192.168.100.4:8129/api/v1/agent/health | jq .
curl -s http://192.168.100.4:8129/api/v1/agent/status | jq .
curl -s http://192.168.100.7:8129/api/v1/agent/health | jq .
curl -s http://192.168.100.7:8129/api/v1/agent/status | jq .
```

### Step 2 — Server version/status/health on `.4:8128`

```bash
curl -s http://192.168.100.4:8128/api/v1/version | jq .
curl -s http://192.168.100.4:8128/api/v1/status | jq .
curl -s http://192.168.100.4:8128/api/v1/health | jq .
```

### Step 3 — Collector endpoints

```bash
curl -s http://192.168.100.4:8128/api/v1/otbrs | jq .
curl -s http://192.168.100.4:8128/api/v1/networks | jq .
curl -s http://192.168.100.4:8128/api/v1/matter-servers | jq .
curl -s http://192.168.100.4:8128/api/v1/matter-nodes | jq .
curl -s http://192.168.100.4:8128/api/v1/mdns/services | jq .
curl -s http://192.168.100.4:8128/api/v1/trel/services | jq .
curl -s http://192.168.100.4:8128/api/v1/capabilities | jq .
curl -s http://192.168.100.4:8128/api/v1/events?window=24h&limit=50 | jq .
curl -s http://192.168.100.4:8128/api/v1/report.yaml
```

Without `jq`, omit `| jq .`.

---

## 11. Expected success criteria

| Check | Expected |
|-------|----------|
| Agent `.4` health | `state: healthy`, version `0.1.0` |
| Agent `.7` health | `state: healthy`, version `0.1.0` |
| Server version | `{"tool":"ThreadLens","version":"0.1.0"}` |
| Server health | `overall.state` is `healthy`, `warning`, or `degraded` — not stuck `critical` due to startup failure |
| `/otbrs` | Two entries: `study` and `lounge`; `reachable: true` when OTBR REST responds |
| `/networks` | Thread network observations from OTBR data (may be sparse initially) |
| `/matter-servers` | `study_matter` entry; connected when websocket is up |
| `/matter-nodes` | Node inventory when Matter Server reports nodes |
| `/mdns/services` | May populate over time with host networking; empty is a networking visibility issue, not proof of absence |
| `/trel/services` | Same as mDNS — depends on multicast visibility |
| `/capabilities` | Capability flags reflecting configured collectors |
| `/events` | Recent events array (may be empty early on) |
| `/report.yaml` | YAML report with site name, capabilities, health summary |
| MQTT (if configured) | Discovery entities appear in Home Assistant under `threadlens/` |

---

## 12. Known likely failure modes

| Symptom | Likely cause | What to check |
|---------|--------------|---------------|
| Image pull fails | Image not built/pushed to GHCR | Build locally or `docker load` from tarball |
| Agent `.7` unreachable from `.4` | Firewall or wrong IP | `curl` from `.4` to `192.168.100.7:8129` |
| OTBR `reachable: false` | Wrong REST URL or OTBR down | `curl http://192.168.100.x:8081/...` directly |
| OTBR data partial/null | OTBR REST response shape mismatch | Compare raw OTBR JSON vs ThreadLens logs |
| Matter Server disconnected | Wrong websocket URL or server down | Check `ws://192.168.100.4:5580/ws` |
| Matter nodes empty | Websocket shape mismatch or no commissioned nodes | Matter Server logs |
| MQTT not connecting | Wrong broker host or missing credentials | Verify `broker.mqtt` resolves and `mqtt.username` / `mqtt.password` are set locally |
| mDNS/TREL empty | Bridge networking or macOS Docker Desktop | Confirm `network_mode: host` on Linux |
| `/data` permission errors | Volume not writable by `threadlens` user | `chown` or recreate `data/study`, `data/lounge-agent` dirs |
| Healthcheck failing on `.7` | Agent-only container using server healthcheck | Lounge compose overrides healthcheck to port 8129 |

---

## 13. Outputs to capture

Save these for debugging (redact MQTT passwords if present):

```bash
curl -s http://192.168.100.4:8128/api/v1/status > study-status.json
curl -s http://192.168.100.4:8128/api/v1/health > study-health.json
curl -s http://192.168.100.4:8128/api/v1/otbrs > study-otbrs.json
curl -s http://192.168.100.4:8128/api/v1/networks > study-networks.json
curl -s http://192.168.100.4:8128/api/v1/matter-servers > study-matter-servers.json
curl -s http://192.168.100.4:8128/api/v1/matter-nodes > study-matter-nodes.json
curl -s http://192.168.100.4:8128/api/v1/trel/services > study-trel.json
curl -s http://192.168.100.4:8128/api/v1/report.yaml > study-report.yaml
docker logs threadlens > study-container.log 2>&1        # on .4
docker logs threadlens-agent > lounge-container.log 2>&1  # on .7
```

---

## 14. Live test rule

During this live test:

- **Do not** add product features.
- **Do not** refactor collectors, storage, or MQTT.
- **Only** fix observed breakages, packaging issues, or live data-shape mismatches.

---

## Quick reference — first validation curls

After both containers are up:

```bash
curl http://192.168.100.7:8129/api/v1/agent/health
curl http://192.168.100.4:8129/api/v1/agent/health
curl http://192.168.100.4:8128/api/v1/version
curl http://192.168.100.4:8128/api/v1/health
```

If those four succeed, proceed with the full validation sequence in section 10.
