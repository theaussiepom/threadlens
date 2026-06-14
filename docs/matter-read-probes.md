# Matter read probes

Matter read probes are **optional read-only diagnostics**. They help detect nodes that Matter Server reports as available but do not respond to safe attribute reads.

Read probes are **disabled by default**. They do not prove Home Assistant open/close/write commands work.

## What read probes measure

ThreadLens can periodically (or manually) call Matter Server:

- `read_attribute` — safe read-only attribute read on a configured cluster/attribute path
- `ping_node` — optional; disabled by default (`ping_enabled: false`)

These are **active safe reads initiated by ThreadLens** (Option 3). They measure **read reachability**, not command outcomes.

## What read probes do not measure

- Home Assistant cover open/close commands
- `write_attribute` or other mutating Matter commands
- Whether a blind or lock will accept your next automation command

Until [future passive command diagnostics](matter-command-diagnostics-future.md) exist, ThreadLens must not claim command failures based on read probes alone.

## Configuration

```yaml
matter:
  probes:
    enabled: true
    schedule_enabled: true
    interval_seconds: 1800
    timeout_seconds: 10
    max_concurrent: 1
    jitter_seconds: 300
    ping_enabled: false
    attributes:
      window_covering:
        - "1/258/10"
      fallback:
        - "0/40/5"
```

### Defaults (conservative)

| Setting | Default | Notes |
|---------|---------|-------|
| `enabled` | `false` | Master switch for probe runner |
| `manual_enabled` | `true` | Manual probes via API when `enabled` |
| `schedule_enabled` | `false` | Scheduled loop off until you opt in |
| `interval_seconds` | `3600` | Use a long interval on Thread networks |
| `max_concurrent` | `1` | Keep at 1 on Thread to avoid bursts |
| `ping_enabled` | `false` | Optional ping diagnostic |

**Caution:** Start with a long `interval_seconds` and `max_concurrent: 1` on Thread networks. Sleepy devices and unsupported attributes can produce inconclusive or limited results.

### Attribute paths

Paths use the Matter Server form `endpoint/cluster_id/attribute_id` (for example `1/258/10` for a window-covering attribute). ThreadLens tries device-type-specific paths first, then `fallback`.

Unsupported attributes set `last_read_probe_limited` and do **not** count as probe failures.

## Health and dashboard semantics

When probes are enabled and diagnostics are available:

- **Available + read probe failed** — Matter Server reports the node available, but recent safe read probes failed. This is read reachability, not a command failure claim.
- **Read diagnostics limited** — attribute unsupported or inconclusive; informational only.
- **Unavailable** — availability signal from Matter Server inventory; separate from read probes.

## MQTT and Home Assistant

When `mqtt.per_node_entities` is enabled and a node exposes read probe diagnostics, ThreadLens publishes:

- `binary_sensor` — read probe OK (per node)
- `sensor` — read probe failures 24h (per node)

A global environment sensor reports total Matter read probe issues. See [mqtt-home-assistant.md](mqtt-home-assistant.md).

## Manual probes

With `matter.probes.enabled: true`, operators can trigger a manual read probe via the Core API (`POST /api/v1/matter-nodes/{server_id}/{node_id}/read-probe`). There is no public “run probe” action in the HACS integration.

## Related documentation

- [Configuration](configuration.md) — full `matter.probes` reference
- [Future command diagnostics](matter-command-diagnostics-future.md) — passive Matter Server command events (Option 2)
