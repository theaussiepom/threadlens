# Lens family

ThreadLens and [ZigbeeLens](https://github.com/theaussiepom/zigbeelens) are **sibling products** in the Lens family of read-only home-network observability tools. They share UX conventions and documentation patterns but remain **separate repositories and runtimes**.

```text
ThreadLens  = Thread / Matter-over-Thread observability
ZigbeeLens  = Zigbee / Zigbee2MQTT observability
Shared      = Lens family conventions (this document)
```

There is no shared npm or Python package in Phase 1. Conventions are documented here so both products feel like related tools without coupling releases.

---

## Shared principles

| Principle | Meaning |
|-------------|---------|
| **Read-only observability** | Watch and explain; do not repair, reset, commission, or mutate network state |
| **Evidence-first diagnostics** | Show what was observed, when, and from which source |
| **No causal overclaiming** | Avoid “caused by” unless directly observed; prefer “may indicate”, “correlated with” |
| **Honest unknowns** | Use `unknown`, `null`, or explicit limitations — never infer zero or guess parentage |
| **Friendly default UI** | Overview answers “is anything wrong?”; drilldowns show technical detail |
| **Home Assistant companion** | Native panel + optional embed; not a replacement for HA or the underlying stack |
| **No entity spam by default** | MQTT Discovery publishes **global summary** entities unless explicitly configured otherwise |
| **Reports safe to share after redaction** | Use redaction profiles before posting to forums or support channels |

Product-specific safety audits and scope limits remain in each repo’s security and architecture docs.

---

## Shared health vocabulary (presentation layer)

Lens products use a **shared vocabulary for UI grouping, incident summaries, reports, HACS panels, and MQTT summary entities**. Domain health engines stay separate; reason codes stay domain-specific.

| Lens term | When to use |
|-----------|-------------|
| **Healthy** | No current concern; signals within normal bounds |
| **Recently unstable** | Flapping or repeated transitions; not hard down |
| **Needs attention** | Clear problem pattern, repeated failures, or elevated risk |
| **Unavailable** | Known down, unreachable, or collector gap blocks observation |
| **Diagnostics limited** | Cannot observe further (unsupported probe, missing path, OTBR offline) |
| **Informational** | Environmental or context signal — not a fault |
| **Unknown** | Insufficient evidence to classify |

### Mapping examples (ThreadLens)

| Domain signal | Typical Lens bucket |
|---------------|---------------------|
| Safe read probe failed recently | **Recently unstable** or **Needs attention** (threshold-dependent) |
| Read probe path unsupported | **Diagnostics limited** |
| Matter node unavailable | **Unavailable** |
| Foreign TREL / observed-other network | **Informational** |
| OTBR unreachable | **Unavailable** or **Needs attention** |

### Mapping examples (ZigbeeLens)

| Domain signal | Typical Lens bucket |
|---------------|---------------------|
| Router risk candidate | **Needs attention** |
| Bridge/coordinator offline | **Unavailable** or **Needs attention** (depends on evidence scope) |
| Repeated availability changes | **Recently unstable** |
| Low battery, weak link, interview issue | **Needs attention** (domain chip may still show specific reason) |

Do not force identical classification logic between products. Align **labels and sort order** in dashboards, docs, and summary MQTT entities.

---

## Shared UI and style

See [style-guide.md](style-guide.md) for ThreadLens-specific paths and components.

- Dark diagnostic UI with **`zl-*` design tokens** (shared palette name across Lens products)
- **IBM Plex** Sans and Mono via bundled fonts — no production CDN dependencies
- **Mobile-first** cards, `min-h-11` touch targets, horizontal nav on small screens
- **Calm incident language** — evidence bullets, limitations callouts
- **Overview** hides raw technical IDs where possible (HA names, network labels)
- **Drilldown** may show Matter node IDs, probe paths, OTBR REST details, mDNS records
- No repair/control affordances in Core or companion panel

---

## Home Assistant embedded view

See [hacs-embedded-view.md](hacs-embedded-view.md) for ThreadLens setup. The Lens family decision tree is identical across products:

1. **Native companion panel first** — status, incidents, summary counts
2. **Optional embedded Core dashboard** when browser security allows (matching HTTP/HTTPS scheme)
3. **If embedding blocked** — native panel + **Open full dashboard** (always works in a new tab)
4. **Keep HA menu/burger usable** — do not trap navigation in iframe-only UX
5. **No mutation/control buttons** in companion panel

---

## MQTT summary conventions

See [mqtt-home-assistant.md](mqtt-home-assistant.md) for ThreadLens configuration. Phase 3C uses a **clean global summary model** (backward compatibility not required):

| Pattern | Example |
|---------|---------|
| Discovery config | `homeassistant/sensor/threadlens/health/config` |
| State | `threadlens/summary/health/state` |
| Attributes | `threadlens/summary/health/attributes` |
| Availability | `threadlens/status` (`online` / `offline`) |

Shared rules:

- **Global summary entities by default** — health, issues, bucket counts (ThreadLens adds read probe issues)
- **Avoid per-device entity spam** unless explicitly enabled (`per_node_entities: false` default)
- **`unknown` for unobserved/unavailable** — `0` only for observed zero
- **Lens bucket attributes** on health entity (`lens_bucket`, `lens_bucket_label`, counts)
- **Entity names describe diagnostics**, not control
- **No secrets** in discovery payloads
- **Migration:** clear old retained discovery configs after deploy (see product MQTT docs)

---

## Report conventions (target structure)

Lens reports share a common high-level structure but preserve protocol-specific details. Both products expose aligned section names where practical:

| Section | Purpose |
|---------|---------|
| `product`, `version`, `generated_at` | Identity and freshness |
| `site`, `mode` | Deployment context |
| **Executive summary** | One paragraph; no causal overclaiming |
| **Health summary** | Lens bucket or severity counts |
| **Active incidents** | Evidence-backed findings with affected entities |
| **Collector status** | What was and was not observable |
| **Limitations** | Explicit gaps in evidence |
| **Redaction profile** | e.g. `public_safe`, `standard` |
| **Domain details** | Protocol-specific payloads (Zigbee networks/devices vs Thread OTBR/Matter) |
| **Events / timeline** | Recent events for the report window |

Exact JSON/YAML schemas are not identical between products. Legacy fields remain for compatibility.

See [reports.md](reports.md) for ThreadLens specifics.

---

## Release and readiness language

Both products follow a similar release posture:

- **No built-in authentication** in early versions — document and acknowledge before tagging
- **CI green** before merge; container image published via GitHub Actions
- **Redaction spot-check** on real or fixture data before release
- **HACS / companion panel smoke** on HTTP and, if used, HTTPS embed matrix
- **CHANGELOG** and GitHub Release notes for tagged versions

ThreadLens: [RELEASE.md](../RELEASE.md)  
ZigbeeLens: [RELEASE_CHECKLIST.md](https://github.com/theaussiepom/zigbeelens/blob/main/RELEASE_CHECKLIST.md)

Both projects provide `./scripts/run-release-checks.sh` for automated pre-release validation.

---

## Related docs

- [style-guide.md](style-guide.md)
- [hacs-embedded-view.md](hacs-embedded-view.md)
- [mqtt-home-assistant.md](mqtt-home-assistant.md)
- [reports.md](reports.md)
- ZigbeeLens lens family doc: [docs/lens-family.md](https://github.com/theaussiepom/zigbeelens/blob/main/docs/lens-family.md)
