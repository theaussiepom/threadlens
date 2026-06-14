# Future Matter command diagnostics (Option 2)

This document describes **planned passive command diagnostics** from Matter Server. It is documentation only — ThreadLens does not observe these events today.

## Two diagnostic models

| Model | Source | What it measures | Status |
|-------|--------|------------------|--------|
| **Option 3 — read probes** | ThreadLens-initiated `read_attribute` / optional `ping_node` | Safe read reachability | Available (opt-in, disabled by default) |
| **Option 2 — command diagnostics** | Passive Matter Server diagnostic events | Actual Matter command outcomes | **Future** |

Read probes and command diagnostics answer different questions. When Option 2 exists, ThreadLens should prefer command diagnostics for command health but keep read probes as an independent reachability signal.

## Future Matter Server events

When Matter Server exposes passive diagnostic events, ThreadLens may subscribe to:

```text
diagnostic.command.started
diagnostic.command.succeeded
diagnostic.command.failed
diagnostic.command.timed_out
diagnostic.subscription.*
diagnostic.session.*
```

These would let ThreadLens report that **actual Matter commands failed** (for example a cover move rejected by the device), based on server-observed outcomes — not inferred from read probes.

## What ThreadLens does today

ThreadLens **does not** claim Home Assistant or Matter command failures today.

Placeholder fields remain separate from read probes:

- `command_diagnostics_available` — `false` until Option 2 events are wired
- `command_failures_24h` — `null` / not populated until Option 2 exists

Read probe fields (`read_probe_diagnostics_available`, `last_read_probe_ok`, `read_probe_failures_24h`, etc.) measure **read reachability only**.

## Wording guidance

**Use for read probes today:**

- read probe
- safe read probe
- read reachability
- read diagnostics

**Do not use for read probes:**

- command failed
- blind command failed
- open/close failed

When Option 2 is implemented, command-failure wording may apply only to nodes with `command_diagnostics_available: true` and observed `diagnostic.command.failed` / `timed_out` events.

## Related documentation

- [Matter read probes](matter-read-probes.md) — Option 3 active safe reads
