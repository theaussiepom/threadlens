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
| `off` | No active read probes |
| `conservative` | Infrequent generic/root Matter read checks only. Best default for Thread networks |
| `standard` | Generic/root checks plus safe device-type checks when ThreadLens can confidently infer them |
| `diagnostic` | More frequent read checks and more detail, still read-only |

### Mode timing defaults

When `advanced.interval_seconds` is not set explicitly:

| Mode | Default interval |
|------|------------------|
| `conservative` | 3600 seconds |
| `standard` | 1800 seconds |
| `diagnostic` | 900 seconds |

**Caution:** Start with `conservative` and `max_concurrent: 1` on Thread networks.

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

ThreadLens uses a probe planner with this ladder:

1. Per-node advanced override, if configured
2. Last known successful probe for this node, if still valid
3. Generic/root Basic Information read
4. Descriptor/root structure read if needed
5. Device-specific safe read when mode allows and endpoint/cluster data supports it
6. Optional ping when enabled

For Window Covering devices, ThreadLens prefers the actual endpoint where cluster `258` appears in Matter Server node data instead of assuming endpoint `1`.

Unsupported device-specific reads fall back to generic reads where possible and do **not** make a node unhealthy when a generic read succeeds.

## Health and dashboard semantics

- **Read checks OK** — a generic safe read succeeded recently
- **Read probe issue** — generic safe reads failed while the node is available
- **Read diagnostics limited** — unsupported or inconclusive attribute; informational only

The dashboard overview shows friendly labels only. Node drilldown shows the probe type first and the technical path as advanced detail.

## Related documentation

- [Configuration](configuration.md) — full `matter.probes` reference
- [Future command diagnostics](matter-command-diagnostics-future.md) — passive Matter Server command events (Option 2)
