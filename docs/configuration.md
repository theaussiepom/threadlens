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
  - id: "primary"
    name: "Primary OTBR"
    rest_url: "http://192.168.1.10:8081"
    agent_url: null  # optional co-located agent, e.g. http://192.168.1.10:8129
```

URLs must be reachable from the ThreadLens host/container.

### `matter` / `matter_servers`

```yaml
matter:
  reconnect_initial_seconds: 5
  reconnect_max_seconds: 60
  request_timeout_seconds: 10
  probes:
    mode: off
    manual_enabled: true
    schedule_enabled: false

matter_servers:
  - id: "home"
    name: "Home Matter Server"
    websocket_url: "ws://192.168.1.10:5580/ws"
    variant: "python"
```

ThreadLens uses read-only websocket commands for inventory (`start_listening`, `get_nodes`, `server_info`). Optional **Matter read probes** use `read_attribute` and optionally `ping_node` when probes are active. Read probes are disabled by default and do not prove Home Assistant commands work. See [matter-read-probes.md](matter-read-probes.md).

Most users only need a mode:

```yaml
matter:
  probes:
    mode: conservative
    schedule_enabled: true
```

Supported modes: `off`, `conservative`, `standard`, `diagnostic`.

Timing, ping, attribute overrides, and per-node settings live under `matter.probes.advanced`.

Example with advanced overrides:

```yaml
matter:
  probes:
    mode: standard
    schedule_enabled: true
    advanced:
      interval_seconds: 1800
      timeout_seconds: 10
      max_concurrent: 1
      jitter_seconds: 300
      ping_enabled: false
      attributes:
        window_covering:
          - "1/258/10"
        fallback:
          - "0/40/2"
          - "0/40/4"
      per_node:
        "24":
          preferred:
            - "0/40/2"
```

Future passive command diagnostics from Matter Server are documented separately in [matter-command-diagnostics-future.md](matter-command-diagnostics-future.md).

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
  enabled: true
  host: "homeassistant.local"  # or broker.mqtt, or your broker IP
  port: 1883
  username: null
  password: null
  discovery_prefix: "homeassistant"
  topic_prefix: "threadlens"
  per_trel_service_entities: false
  per_node_entities: true
```

Replace `host` with your MQTT broker hostname or IP. `broker.mqtt` is a valid example only if that name resolves on your LAN.

Do not commit broker passwords to git. Use environment-specific config or secrets management.

For live deployments, copy an example config to a local file (for example `config.local.yaml`, gitignored) and set `mqtt.username` and `mqtt.password` there. Committed examples use `null` placeholders only.

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
