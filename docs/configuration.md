# Configuration

ThreadLens reads `config.yaml` from `/config/config.yaml` by default. Override with `THREADLENS_CONFIG_PATH` or `threadlens --config`.

## Environment overrides

| Variable | Effect |
|----------|--------|
| `THREADLENS_CONFIG_PATH` | Path to YAML config |
| `THREADLENS_MODE` | `server`, `agent`, or `both` |
| `THREADLENS_SITE_NAME` | Site display name |
| `THREADLENS_SERVER_PORT` | Server API port (default 8128) |
| `THREADLENS_AGENT_PORT` | Agent API port (default 8129) |

CLI `--mode` overrides config `mode` for a single run.

## Core sections

### `site`

```yaml
site:
  name: "Home"
```

Used in reports, health output, and MQTT device names.

### `server` / `agent`

```yaml
server:
  host: "0.0.0.0"
  port: 8128

agent:
  host: "0.0.0.0"
  port: 8129
```

Bind `0.0.0.0` in containers. On trusted LANs only — see [security.md](security.md).

### `storage`

```yaml
storage:
  sqlite_path: "/data/threadlens.db"
  event_retention_days: 30
```

Mount `/data` as a Docker volume for persistence.

### `flapping`

Debounce and threshold settings for health rollups (Matter node availability, OTBR role changes, mDNS service flaps). Defaults are sensible for home environments.

### `otbr` (polling settings)

```yaml
otbr:
  poll_interval_seconds: 60
  request_timeout_seconds: 5
  allow_read_only_actions: false
  use_legacy_node_fallback: true
```

`allow_read_only_actions` must remain `false` in v1.

`use_legacy_node_fallback` (default `true`) polls legacy read-only `GET /node` on the same OTBR REST port and reconciles stale JSON:API `GET /api/node` responses. Disable only if your OTBR does not expose `/node`.

### `otbrs` (instances)

```yaml
otbrs:
  - id: "study"
    name: "Study OTBR"
    rest_url: "http://192.168.100.4:8081"
    agent_url: null  # optional, e.g. http://192.168.100.4:8129
```

URLs must be reachable from the ThreadLens host/container.

### `matter` / `matter_servers`

```yaml
matter:
  reconnect_initial_seconds: 5
  reconnect_max_seconds: 60
  request_timeout_seconds: 10

matter_servers:
  - id: "study_matter"
    name: "Study Matter Server"
    websocket_url: "ws://192.168.100.4:5580/ws"
    variant: "python"
```

ThreadLens only uses read-only websocket commands (`start_listening`, `get_nodes`, `server_info`).

### `mdns`

```yaml
mdns:
  enabled: true
  services:
    - "_trel._udp.local."
    - "_meshcop._udp.local."
    - "_matter._tcp.local."
    - "_matterc._udp.local."
```

Disable if running without multicast visibility and you only need OTBR/Matter REST paths.

### `mqtt`

```yaml
mqtt:
  enabled: false
  host: "homeassistant.local"
  port: 1883
  discovery_prefix: "homeassistant"
  topic_prefix: "threadlens"
  per_trel_service_entities: false
  per_node_entities: true
```

Do not commit broker passwords to git. Use environment-specific config or secrets management.

For live deployments, copy `examples/live/study-both.config.yaml` to a local file (for example `study-both.config.local.yaml`, gitignored) and set `mqtt.username` and `mqtt.password` there. The committed example uses `null` placeholders only.

### `homeassistant`

```yaml
homeassistant:
  mqtt_discovery_enabled: true
```

Controls Home Assistant MQTT Discovery publishing independently of `mqtt.enabled`.

| Setting | Default | Purpose |
|---------|---------|---------|
| `mqtt_discovery_enabled` | `true` | Publish HA discovery config and entity state/attribute topics |

When `mqtt.enabled: true` and `mqtt_discovery_enabled: false`, ThreadLens may still connect to MQTT and publish the minimal `threadlens/status` topic, but it will not create Home Assistant devices or entities.

### `reports`

```yaml
reports:
  redact_secrets: true
```

Keep enabled. Redaction is defensive — reports may still include operational metadata.

## Example files

- `examples/config/config.yaml` — safe starter with commented OTBR/Matter examples
- `tests/fixtures/example_config.yaml` — test fixture with sample OTBR/Matter entries

## Validation

```bash
python -c "from threadlens.config import load_config; load_config('examples/config/config.yaml')"
```

Or run `pytest tests/test_config.py tests/test_packaging.py`.
