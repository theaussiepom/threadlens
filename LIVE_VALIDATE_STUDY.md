# Study Pi live validation — Pass 17 & Pass 19

Operational helper for validating ThreadLens on the Study Pi (`192.168.100.4`). This is **not** a product feature.

Run these steps **on the Study Pi** from a ThreadLens core repo checkout. ThreadLens does not implement SSH or Docker socket access.

## Quick start

```bash
# Validate only (no rebuild)
./scripts/live_validate_study.sh

# Build, recreate container, validate
./scripts/live_validate_study.sh --redeploy

# Also capture OTBR REST fixtures for parser work
./scripts/live_validate_study.sh --capture-otbr

# Optional: move aside old SQLite DB if pre-fix flap events still degrade health
OPT_IN_DB_RESET=1 ./scripts/live_validate_study.sh --redeploy
```

## Prerequisites

- Docker installed on Study Pi (Linux, host networking)
- Repo checked out on Study Pi (e.g. `~/threadlens`)
- Live config present: `examples/live/study-both.config.yaml` (MQTT broker credentials are local-only)
- Data directory: `mkdir -p data/study`

## 1. Build image

```bash
docker build -t ghcr.io/theaussiepom/threadlens:0.1.0 .
```

## 2. Recreate container

**Ben Home live compose (recommended):**

```bash
docker compose -f docker-compose.study-both.example.yml up -d --force-recreate
```

**Generic host-network example (alternative):**

```bash
docker compose -f docker-compose.host-network.example.yml up -d --force-recreate
```

Environment overrides for the script:

| Variable | Default |
|----------|---------|
| `THREADLENS_API_BASE` | `http://192.168.100.4:8128` |
| `THREADLENS_COMPOSE_FILE` | `docker-compose.study-both.example.yml` |
| `THREADLENS_DATA_DIR` | `./data/study` |
| `THREADLENS_IMAGE_TAG` | `ghcr.io/theaussiepom/threadlens:0.1.0` |

## 3. Optional clean DB validation (opt-in)

If health still shows `mdns_service_flapping_degraded` because of **pre-Pass-17 events** in SQLite, move the DB aside and recreate:

```bash
docker compose -f docker-compose.study-both.example.yml down
mv ./data/study/threadlens.db ./data/study/threadlens.db.pre-pass17
docker compose -f docker-compose.study-both.example.yml up -d --force-recreate
```

Or use the script flag:

```bash
OPT_IN_DB_RESET=1 ./scripts/live_validate_study.sh --redeploy
```

This **does not delete** data — it renames the DB file. Only run when you intend to reset flap history.

## 4. Validation commands

```bash
curl -s http://192.168.100.4:8128/api/v1/health | jq
curl -s http://192.168.100.4:8128/api/v1/status | jq '.collectors.mdns'
curl -s http://192.168.100.4:8128/api/v1/mdns/services | jq '.count'
curl -s http://192.168.100.4:8128/api/v1/trel/services | jq '.count'
curl -s http://192.168.100.4:8128/api/v1/events?window=24h | jq
docker logs threadlens --since 5m
```

### Pass 17 expected results

- `/api/v1/mdns/services` count remains **> 0**
- `/api/v1/trel/services` count remains **> 0**
- `collectors.mdns.observation_degraded` is **`false`**
- No `_AsyncMdnsListener` `AttributeError` in recent logs
- `mdns_service_flapping_degraded` is **not** present purely from startup discovery
- `observation_degraded` remains **`false`**

### Pass 19 OTBR capture (fixtures)

Capture raw OTBR REST responses for parser fixtures:

```bash
mkdir -p live-captures
curl -s http://192.168.100.4:8128/api/v1/otbrs > live-captures/threadlens-otbrs.json
curl -s http://192.168.100.4:8081/api/node > live-captures/study-api-node.json
curl -s http://192.168.100.7:8081/api/node > live-captures/lounge-api-node.json
curl -s http://192.168.100.4:8081/api/devices > live-captures/study-api-devices.json
curl -s http://192.168.100.7:8081/api/devices > live-captures/lounge-api-devices.json
```

Copy reviewed captures into `tests/fixtures/otbr/` for unit tests. Redact any secret-like fields if present (OTBR `/api/node` and `/api/devices` should not include network key or PSKc).

### Pass 19 validation after parser deploy

```bash
curl -s http://192.168.100.4:8128/api/v1/otbrs | jq
curl -s http://192.168.100.4:8128/api/v1/networks | jq
curl -s http://192.168.100.4:8128/api/v1/health | jq
curl -s http://192.168.100.4:8128/api/v1/report.yaml | less
```

**Expected when Thread stacks are active:**

- Study OTBR: `role` = `leader`
- Lounge OTBR: `role` = `router`
- `network_name`, `channel`, `ext_pan_id`, `pan_id` populated when raw API provides them
- Thread network shows 2 source OTBRs when both share the same extended PAN ID
- Health reflects real OTBR state, not empty-field parsing gaps

**Note:** When OTBR Thread stack is `disabled`, raw `/api/node` may return empty `role` and `networkName`. ThreadLens normalises empty strings to `null` rather than exposing `""`.

## Related docs

- [LIVE_TEST_0.1.0.md](LIVE_TEST_0.1.0.md) — full Ben Home live test runbook
- [docker-compose.study-both.example.yml](docker-compose.study-both.example.yml) — Study Pi compose
- [examples/live/study-both.config.yaml](examples/live/study-both.config.yaml) — live config template
