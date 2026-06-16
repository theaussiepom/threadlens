# Reports

ThreadLens generates factual diagnostic reports from stored state, events, and live collector context.

## Lens family report structure

Lens reports share a common high-level structure but preserve protocol-specific details. See [lens-family.md](lens-family.md) for shared vocabulary.

| Section | ThreadLens | Notes |
|---------|------------|-------|
| Identity | `product`, `version`, `generated_at` | Legacy nested `report.tool` retained |
| Context | `site`, `mode` | `mode` is typically `server` |
| Redaction | `redaction_profile` | `public_safe` when `reports.redact_secrets: true` |
| Executive summary | `executive_summary` | Evidence-first; no causal overclaiming |
| Health summary | `health_summary` | Maps domain `HealthState` to Lens bucket labels |
| Active incidents | `active_incidents` | Derived from unhealthy entities in the report window |
| Collector status | `collector_status` | OTBR, Matter, mDNS/TREL, read probes |
| Limitations | `limitations` | Calm explicit observation gaps |
| Domain details | `domain_details` | Thread networks, OTBR, Matter nodes, read probes, mDNS, TREL |
| Events / timeline | `events_or_timeline` | Legacy `events.recent` unchanged |

Existing top-level arrays (`otbrs`, `matter_nodes`, etc.) remain for backward compatibility.

ZigbeeLens stored reports: [reports.md](https://github.com/theaussiepom/zigbeelens/blob/main/docs/reports.md).

## Endpoints

| Endpoint | Format |
|----------|--------|
| `GET /api/v1/report` | YAML default; JSON with `Accept: application/json` |
| `GET /api/v1/report.yaml` | YAML |
| `GET /api/v1/report.json` | JSON |

## Examples

```bash
curl http://localhost:8128/api/v1/report.yaml
curl -H "Accept: application/json" http://localhost:8128/api/v1/report
curl "http://localhost:8128/api/v1/report.yaml?window=7d&focus_node=24"
curl "http://localhost:8128/api/v1/report.json?window=24h&focus_device=study"
```

## Query parameters

| Parameter | Values | Description |
|-----------|--------|-------------|
| `window` | `24h`, `7d` | Event and aggregate time window |
| `focus_node` | Matter node ID | Prioritises node-related events in report |
| `focus_device` | OTBR or server ID | Prioritises device-related events |

## Report contents

Reports include:

- Site and summary health counts
- Capability flags (what observation paths are available)
- OTBR, Matter, mDNS/TREL, and agent snapshots where configured
- Recent events and aggregates for the window
- Redaction summary

## Redaction

When `reports.redact_secrets: true` (default), fields matching sensitive names (`password`, `token`, `secret`, `network_key`, etc.) are replaced with `REDACTED`.

Redaction is **defensive**. Reports still include operational metadata such as:

- Network names and Extended PAN IDs
- Node IDs and availability state
- Health reason codes
- Collector reachability

Do not share reports outside your trust boundary without review.

## Unavailable and null metrics

ThreadLens distinguishes:

- **Observed zero** — a metric was available and counted zero
- **Unavailable** — the observation path does not exist or failed

Reports use capability flags and omit or null fields rather than guessing values.

## No causal claims

Reports describe **what was observed** and health rollups with reason codes. They do not claim root cause (e.g. "node flapped because router changed role").

## Status metadata

After generating a report via API, `/api/v1/status` includes:

```yaml
reports:
  last_generated_at: "..."
  last_window: "24h"
```

MQTT entities mirror report URL and last generated timestamp when MQTT is enabled.

## Empty reports

A sparse report usually means:

- No OTBRs or Matter servers configured yet
- Collectors have not completed a poll cycle
- New installation with no events in the retention window

Check `/api/v1/status` collector blocks and configure sources in [configuration.md](configuration.md).
