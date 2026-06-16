# Lens family alignment — status

**Status:** Complete (alignment stream closed 2026-06-16).

ThreadLens and [ZigbeeLens](https://github.com/theaussiepom/zigbeelens) remain **separate repositories and runtimes**. Shared conventions: [lens-family.md](lens-family.md).

---

## Complete

| Area | ThreadLens | ZigbeeLens |
|------|------------|------------|
| Shared docs / conventions | [lens-family.md](lens-family.md) | Stub → ThreadLens canonical |
| API `/api/v1` surface | Native | Aliases, capabilities, status (**v0.1.13**) |
| Presentation `lens_bucket` | Native | Dashboard/API payloads (**v0.1.13**) |
| Release checklist parity | [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) | [RELEASE_CHECKLIST.md](https://github.com/theaussiepom/zigbeelens/blob/main/RELEASE_CHECKLIST.md) |
| Report / export alignment | PR #34 | PR #10 |
| Clean MQTT summary entities | **v0.2.19** live (7 global) | **edge** @ v0.1.13-era (6 global) |
| Deployment / version hygiene | Pironman `:0.2.19` | BenBeast rolling `:edge` |
| Live deployment notes | [deployments/lens-alignment-live-state.md](deployments/lens-alignment-live-state.md) | Same doc in ZigbeeLens repo |

---

## Live MQTT model (summary)

- **Global summary entities only** by default (ThreadLens: 7 incl. read probe; ZigbeeLens: 6)
- **Lens bucket** health state + count attributes on MQTT
- **`unknown` vs `0`** semantics documented and tested
- **HACS entities preserved** — MQTT summary is companion, not a replacement

---

## Still deferred

- HACS visual smoke / screenshot matrix
- ThreadLens `/how-it-works` → `/monitoring` route rename
- Optional ZigbeeLens UI migration to `/api/v1` exclusively
- Optional network-level `lens_bucket` on ZigbeeLens
- Shared library extraction (only if future duplication justifies it)
- Optional HA entity ID cosmetic rename (`sensor.zigbeelens_zigbeelens_*`)

---

## Recommended next pass

1. HACS browser visual smoke when convenient
2. Optional HA entity ID cleanup
3. Future semver tags when report alignment or other changes warrant a release
