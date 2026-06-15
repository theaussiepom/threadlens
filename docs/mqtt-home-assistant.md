# MQTT and Home Assistant

ThreadLens integrates with Home Assistant via optional **MQTT Discovery** summary entities.

**Backward compatibility:** Phase 3C intentionally replaces the previous MQTT entity model. After deploying, delete stale retained discovery configs and remove old HA entities (see [Migration](#migration)).

## Lens family MQTT conventions

Shared rules across [ThreadLens](https://github.com/theaussiepom/threadlens) and [ZigbeeLens](https://github.com/theaussiepom/zigbeelens). See [lens-family.md](lens-family.md).

| Rule | Detail |
|------|--------|
| **Global summary by default** | Seven summary sensors on one HA device |
| **No per-device spam** | `per_node_entities: false` by default |
| **Unknown vs zero** | `unknown` when not observable; `0` only for observed zero |
| **Diagnostic naming** | Names describe status, not control — no command-failure wording |
| **Availability** | `threadlens/status` with `online` / `offline` |
| **No secrets** | Passwords and keys never appear in discovery payloads |

ZigbeeLens equivalent: [mqtt-discovery.md](https://github.com/theaussiepom/zigbeelens/blob/main/docs/mqtt-discovery.md).

## Clean summary entities (default)

All entities group under one Home Assistant device: **ThreadLens**.

| HA entity | State topic | Purpose |
|-----------|-------------|---------|
| ThreadLens Health | `threadlens/summary/health/state` | Overall Lens bucket |
| ThreadLens Issues | `threadlens/summary/issues/state` | Total issue count |
| ThreadLens Unavailable Nodes | `threadlens/summary/unavailable/state` | Unavailable Matter node count |
| ThreadLens Needs Attention | `threadlens/summary/needs_attention/state` | Needs attention count |
| ThreadLens Recently Unstable | `threadlens/summary/recently_unstable/state` | Recently unstable count |
| ThreadLens Diagnostics Limited | `threadlens/summary/diagnostics_limited/state` | Diagnostics limited count |
| ThreadLens Matter Read Probe Issues | `threadlens/summary/matter_read_probe_issues/state` | Read probe issue count |

Attributes publish to matching `.../attributes` topics and include Lens bucket metadata (`product`, `version`, `lens_bucket`, counts, `redaction_profile`).

## Topic patterns

| Kind | Pattern |
|------|---------|
| Discovery config | `homeassistant/sensor/threadlens/<entity_key>/config` |
| State | `threadlens/summary/<entity_key>/state` |
| Attributes | `threadlens/summary/<entity_key>/attributes` |
| Availability | `threadlens/status` |

## Unknown vs zero

| Situation | MQTT state |
|-----------|------------|
| Read probe diagnostics unavailable | Matter Read Probe Issues → `unknown` |
| Read probe diagnostics available, no issues | `0` |
| Read probe diagnostics available, one issue | `1` |
| Observation unreliable (no collectors/nodes) | Count entities → `unknown` |

## Optional per-node entities

Per-node Matter entities (including read probe OK/failures) publish only when explicitly enabled:

```yaml
mqtt:
  per_node_entities: true
```

Default is `false` to avoid entity spam on large fabrics.

## Configuration

```yaml
mqtt:
  enabled: true
  host: "homeassistant.local"
  port: 1883
  discovery_prefix: "homeassistant"
  topic_prefix: "threadlens"
  per_node_entities: false

homeassistant:
  mqtt_discovery_enabled: true
```

| `mqtt.enabled` | `homeassistant.mqtt_discovery_enabled` | Behaviour |
|----------------|----------------------------------------|-----------|
| `false` | any | No MQTT connection |
| `true` | `true` | Clean summary entities + availability |
| `true` | `false` | `threadlens/status` only |

## Migration

After deploying the clean Lens MQTT model:

1. Stop ThreadLens (publishes `offline` on `threadlens/status`).
2. Clear stale retained discovery configs, for example:

```bash
mosquitto_pub -h broker.mqtt -t 'homeassistant/sensor/threadlens_health/config' -r -n
mosquitto_pub -h broker.mqtt -t 'homeassistant/sensor/threadlens_environment_health/config' -r -n
# repeat for other old threadlens_* discovery topics
```

Or call `publish_legacy_discovery_cleanup()` when MQTT discovery is enabled.

3. In Home Assistant: **Settings → Devices & services → MQTT → Entities** — delete stale ThreadLens entities (including old per-OTBR/per-node entities if present).
4. Restart ThreadLens and reload the MQTT integration if needed.

Old discovery topics are listed in `threadlens.mqtt.topics.LEGACY_DISCOVERY_TOPICS`.

## HACS integration

MQTT Discovery does not supply Home Assistant device names on the dashboard. For familiar Matter names, use the [ThreadLens HACS integration](home-assistant-integration.md).
