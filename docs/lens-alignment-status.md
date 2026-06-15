# Lens family alignment — status

**Status:** Complete for the current alignment stream (Phases 1–3D, closure 2026-06-16).

ThreadLens and [ZigbeeLens](https://github.com/theaussiepom/zigbeelens) remain **separate repositories and runtimes**. Shared conventions live in [lens-family.md](lens-family.md).

---

## Completed

| Area | ThreadLens | ZigbeeLens |
|------|------------|------------|
| Shared docs / conventions | [lens-family.md](lens-family.md) | Links to lens-family; product MQTT/API docs |
| API `/api/v1` surface | Native | PR #8 — aliases, capabilities, status |
| Presentation `lens_bucket` | Native | PR #9 — dashboard/API payloads |
| Release checklist parity | PR #33 | [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) |
| Report / export structure | PR #34 open | PR #10 open |
| Clean MQTT summary entities | **v0.2.18** | **v0.1.13** (tag) / `edge` deployed |
| Live deployment notes | [deployments/lens-alignment-live-state.md](deployments/lens-alignment-live-state.md) | Same doc in ZigbeeLens repo |

---

## Live MQTT model (summary)

- **Global summary entities only** by default (ThreadLens: 7 incl. read probe issues; ZigbeeLens: 6)
- **Lens bucket** health state + count attributes on MQTT
- **`unknown` vs `0`** semantics documented and tested
- **No backward compatibility** required for MQTT discovery redesign (documented migration)
- **HACS entities preserved** — MQTT summary is additive/companion, not a replacement

---

## Intentionally deferred

- ThreadLens `/how-it-works` → `/monitoring` route rename
- HACS visual smoke / screenshot matrix (browser validation pass)
- Optional ZigbeeLens UI migration to `/api/v1` exclusively
- Optional network-level `lens_bucket` on ZigbeeLens
- Shared library extraction / monorepo (only if duplication later justifies it)
- ZigbeeLens + ThreadLens **report/export PRs** (#10 / #34) — open, not in this closure tag

---

## Recommended next pass

1. Merge open report-alignment PRs (#34 ThreadLens, #10 ZigbeeLens) when ready
2. Pin BenBeast ZigbeeLens from `:edge` to **`:0.1.13`** after release
3. Optional HA entity ID cleanup (`sensor.zigbeelens_zigbeelens_*` → shorter names)
4. HACS visual smoke pass when convenient
