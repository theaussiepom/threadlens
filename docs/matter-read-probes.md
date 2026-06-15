# Matter read probes

Matter read probes are **optional read-only diagnostics**. They help detect nodes that Matter Server reports as available but do not respond to safe attribute reads.

Read probes are **disabled by default**. They do not prove Home Assistant open/close/write commands work.

Most users should not need to configure probe paths. ThreadLens chooses safe read-only probes automatically from Matter Server node data.

## What read probes measure

ThreadLens can periodically (or manually) call Matter Server:

- `read_attribute` — safe read-only attribute read chosen by the probe planner
- `ping_node` — optional; disabled by default

These are **active safe reads initiated by ThreadLens** (Option 3). They measure **read reachability**, not command outcomes.

## User-facing configuration

Normal users configure intent with a mode:

```yaml
matter:
  probes:
    mode: conservative
    schedule_enabled: true
```

Supported modes:

| Mode | Behaviour |
|------|-----------|
| `disabled` | No active read probes |
| `conservative` | Infrequent generic/root Matter read checks only. Best default for Thread networks |
| `standard` | Inferred safe device-type checks first, then generic/root fallback |
| `diagnostic` | More frequent read checks and more detail, still read-only |

Use `mode: disabled` to turn probes off. Earlier validation builds also accepted `"off"`, but `disabled` is preferred because some YAML parsers treat unquoted `off` as a boolean.

### Mode timing defaults

When `advanced.interval_seconds` is not set explicitly:

| Mode | Default interval |
|------|------------------|
| `disabled` | 3600 seconds (unused while disabled) |
| `conservative` | 3600 seconds |
| `standard` | 1800 seconds |
| `diagnostic` | 900 seconds |

**Caution:** Start with `conservative` and `max_concurrent: 1` on Thread networks.

### Temporary validation interval

During live validation only, you may shorten the interval to rotate through nodes faster:

```yaml
matter:
  probes:
    mode: standard
    schedule_enabled: true
    advanced:
      interval_seconds: 120
      timeout_seconds: 10
      max_concurrent: 1
      jitter_seconds: 30
      ping_enabled: false
```

Return to a longer interval (for example `1800` or `3600` seconds) after validation.

## Advanced overrides

Raw Matter attribute paths are advanced-only. Most installs do not need them.

```yaml
matter:
  probes:
    mode: standard
    advanced:
      interval_seconds: 1800
      timeout_seconds: 10
      max_concurrent: 1
      jitter_seconds: 300
      ping_enabled: false
      attributes:
        fallback:
          - "0/40/2"
          - "0/40/4"
        window_covering:
          - "1/258/10"
      per_node:
        "24":
          preferred:
            - "0/40/2"
```

Top-level tuning keys such as `interval_seconds` or `attributes` are not accepted — use `advanced` only.

### How paths are chosen

ThreadLens uses a probe planner with mode-specific ordering.

**Conservative**

1. Per-node advanced override, if configured
2. Last known successful generic probe, if still valid
3. Generic/root Basic Information read

**Standard**

1. Per-node advanced override, if configured
2. Inferred safe device-specific read (for example blind/window-covering status) when confidently inferred
3. Last known successful probe, if still valid
4. Generic/root Basic Information fallback

**Diagnostic**

1. Overrides, device-specific, cached success, generic fallback, then descriptor reads when useful

For Window Covering devices, ThreadLens prefers the actual endpoint where cluster `258` appears in Matter Server node data instead of assuming endpoint `1`. When no cluster `258` keys are present but the node is confidently inferred as a blind/shade, `1/258/10` may be tried first and falls back to generic reads if unsupported.

Unsupported device-specific reads fall back to generic reads where possible and do **not** make a node unhealthy when a generic read succeeds.

## Health and dashboard semantics

- **Read checks OK** — a safe read succeeded recently
- **Read probe issue** — generic safe reads failed while the node is available
- **Read diagnostics limited** — a device-specific read was unsupported or inconclusive, but a generic read succeeded

When a node is classified **Recently unstable** only because of read probe failures (no recent availability changes), the dashboard and incident summary explain that explicitly via `classification_reason` and health reason code `matter_node_read_probe_failed`. The incident affected-node list includes the per-node reason (for example “Read probe issue” or “Safe read probe failed recently”) so it is clear why the node is flagged.

The dashboard overview shows friendly labels only. Node drilldown shows the probe type first and the technical path as advanced detail.

## Related documentation

- [Configuration](configuration.md) — full `matter.probes` reference
- [Future command diagnostics](matter-command-diagnostics-future.md) — passive Matter Server command events (Option 2)
