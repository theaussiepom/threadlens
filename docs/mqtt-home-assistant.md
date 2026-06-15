# MQTT and Home Assistant

ThreadLens integrates with Home Assistant in two ways:

1. **MQTT Discovery** (optional) — health and inventory entities via the MQTT broker. See below.
2. **HACS integration** — familiar Matter **device names** pushed to Core. See [home-assistant-integration.md](home-assistant-integration.md).

MQTT Discovery does **not** supply `ha_device_name` on Matter nodes. For blind names on the ThreadLens dashboard, install and configure the [ThreadLens HACS integration](https://github.com/theaussiepom/threadlens-ha-integration).

## Lens family MQTT conventions

Shared rules across [ThreadLens](https://github.com/theaussiepom/threadlens) and [ZigbeeLens](https://github.com/theaussiepom/zigbeelens). See [lens-family.md](lens-family.md).

| Rule | Detail |
|------|--------|
| **Global summary by default** | Overall health, environment counts, collector status — grouped HA devices |
| **Avoid per-device spam** | `per_node_entities: false` and `per_trel_service_entities: false` for large fabrics |
| **Unknown vs zero** | Use `null` / capability flags when unobserved; use `0` only for observed zero |
| **Diagnostic naming** | Entity names describe status (“health”, “unavailable count”), not control |
| **Availability** | Product liveness via availability topic (`online` / `offline`) |
| **No secrets** | Passwords, keys, and broker credentials never appear in discovery payloads |

ZigbeeLens equivalent: [mqtt-discovery.md](https://github.com/theaussiepom/zigbeelens/blob/main/docs/mqtt-discovery.md).

## MQTT Discovery (entities)

## Prerequisites

1. Home Assistant **MQTT integration** enabled
2. MQTT broker reachable from ThreadLens (often the HA add-on broker or Mosquitto)
3. `mqtt.enabled: true` in ThreadLens config
4. `homeassistant.mqtt_discovery_enabled: true` to publish Home Assistant entities

```yaml
mqtt:
  enabled: true
  host: "homeassistant.local"
  port: 1883
  discovery_prefix: "homeassistant"
  topic_prefix: "threadlens"
  per_trel_service_entities: false
  per_node_entities: true

homeassistant:
  mqtt_discovery_enabled: true
```

## MQTT vs Home Assistant Discovery

| `mqtt.enabled` | `homeassistant.mqtt_discovery_enabled` | Behaviour |
|----------------|----------------------------------------|-----------|
| `false` | any | No MQTT connection; no HA entities |
| `true` | `true` | Connect; publish HA Discovery + entity state (default) |
| `true` | `false` | Connect; publish minimal `threadlens/status` only |

Use `mqtt.enabled` for broker transport. Use `homeassistant.mqtt_discovery_enabled` to control whether Home Assistant devices and entities are created.

## Topic layout

| Setting | Default | Purpose |
|---------|---------|---------|
| `discovery_prefix` | `homeassistant` | HA discovery topic root |
| `topic_prefix` | `threadlens` | State and availability topics |

Discovery messages are published under `{discovery_prefix}/sensor/.../config`.

State is published under `{topic_prefix}/...`.

## Devices created

### ThreadLens Diagnostics

Overall product status.

Entities include:

- `sensor.threadlens_health`
- `sensor.threadlens_report_url`
- `sensor.threadlens_last_report_generated_at`
- `sensor.threadlens_event_count_24h`
- `sensor.threadlens_warning_count_24h`
- `binary_sensor.threadlens_running`

### Thread Environment Health

- `sensor.threadlens_environment_health`
- `sensor.threadlens_thread_network_count`
- `sensor.threadlens_foreign_trel_service_count`
- `sensor.threadlens_matter_node_count`
- `sensor.threadlens_unavailable_matter_node_count`
- `sensor.threadlens_matter_read_probe_issues` — count of nodes with read probe issues (when read diagnostics are available)

### Per Matter Node (optional)

Controlled by `mqtt.per_node_entities` (default `true`). Disable to reduce entity count on large fabrics.

When a node exposes read probe diagnostics (`read_probe_diagnostics_available`), per-node entities may also include:

- `binary_sensor` — read probe OK
- `sensor` — read probe failures 24h

`None` maps to `unknown` (not observed zero). `0` means an observed zero failure count. Names use “read probe” wording — they do not claim command failures.

See [matter-read-probes.md](matter-read-probes.md).

### Per Thread Network (Extended PAN ID)

Example device: `Thread Network - d6f401f0227e1ec0`

Health, channel, visibility, and foreign-network sensors per observed network.

### Per OTBR

Health, role, network name, and reachability sensors per configured OTBR.

### Per Matter Server

Connection health, node count, and availability sensors.

### Per TREL service (disabled by default)

`mqtt.per_trel_service_entities: false` by default to avoid hundreds of entities. Enable only if you need per-service HA entities.

## Report sensors

- **Report URL** — link to `http://<host>:8128/api/v1/report.yaml`
- **Last report generated** — timestamp of last report generation via API

## Secrets

ThreadLens does **not** publish MQTT passwords, tokens, network keys, or other secrets to discovery or state topics.

Broker credentials in config are used only for the MQTT client connection.

## Availability

ThreadLens publishes an availability topic. Entities show unavailable when the publisher is offline.

## Status API

Check MQTT collector state:

```bash
curl http://127.0.0.1:8128/api/v1/status | jq .collectors.mqtt
```

## Troubleshooting

- Verify broker host resolves from the container
- Check firewall between ThreadLens and broker
- Confirm discovery prefix matches your HA setup (default `homeassistant`)
- See [troubleshooting.md](troubleshooting.md)

## HACS integration (device names)

For Home Assistant blind/device names on the ThreadLens dashboard, use the [ThreadLens HACS integration](home-assistant-integration.md). It pushes names to Core; MQTT Discovery alone does not.
