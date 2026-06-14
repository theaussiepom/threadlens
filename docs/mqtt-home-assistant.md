# MQTT and Home Assistant

ThreadLens integrates with Home Assistant via **MQTT Discovery**. No custom integration is required for baseline entity exposure.

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

### Per Thread Network (Extended PAN ID)

Example device: `Thread Network - d6f401f0227e1ec0`

Health, channel, visibility, and foreign-network sensors per observed network.

### Per OTBR

Health, role, network name, and reachability sensors per configured OTBR.

### Per Matter Server

Connection health, node count, and availability sensors.

### Per Matter Node (optional)

Controlled by `mqtt.per_node_entities` (default `true`). Disable to reduce entity count on large fabrics.

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

## HACS dashboard (future)

A HACS integration for richer dashboards is planned separately. MQTT Discovery remains the baseline v1 integration.
