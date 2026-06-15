# Reports

ThreadLens generates factual diagnostic reports from stored state, events, and live collector context.

## Lens family report structure (target)

Shared section vocabulary across Lens products. Generators may differ; new exports should converge toward this shape. See [lens-family.md](lens-family.md).

| Section | Purpose |
|---------|---------|
| `product`, `version`, `generated_at` | Report identity |
| `site`, `mode` | Deployment context (collectors, agent mode) |
| **Executive summary** | One paragraph; evidence-first, no causal overclaiming |
| **Health summary** | Lens bucket or severity counts |
| **Active incidents** | Headline findings with affected nodes/devices |
| **Collector status** | OTBR, Matter, mDNS/TREL, MQTT, agent reachability |
| **Limitations** | Capability flags and observation gaps |
| **Redaction profile** | `reports.redact_secrets` and defensive field scrubbing |

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
