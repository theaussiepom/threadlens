# ThreadLens UI style guide

ThreadLens Core dashboard and the HACS companion panel are part of the **Lens family**, alongside [ZigbeeLens](https://github.com/theaussiepom/zigbeelens). They share visual language but remain separate repositories — no shared `lens-ui` package.

Family-wide principles and health vocabulary: [lens-family.md](lens-family.md).

## Design goals

- **Read-only observability** — calm, evidence-first copy; no repair or control affordances
- **Incident-first** — answer *is anything broken, where, and what does the evidence say?*
- **Honest limitations** — unavailable metrics stay null; never infer zero or causal claims
- **Mobile-first** — touch targets `min-h-11`, horizontal nav on small screens, sidebar on desktop

## Theme tokens (`zl-*`)

Defined in `web/src/index.css` via Tailwind v4 `@theme`:

| Token | Use |
|-------|-----|
| `zl-bg`, `zl-surface`, `zl-surface-2` | Page and card backgrounds |
| `zl-text`, `zl-muted` | Primary and secondary text |
| `zl-border` | Dividers and card outlines |
| `zl-accent` | Links, active nav, primary actions |
| `zl-healthy`, `zl-watch`, `zl-critical` | Severity colours |

IBM Plex Sans and Mono are bundled via `@fontsource` — no external font URLs in production assets.

## Layout shell

- `AppShell` — sidebar (desktop) + horizontal nav (mobile) + mode banner + refresh
- Router pages under `web/src/pages/`
- Routed device detail at `/devices/:serverId/:nodeId` (not a modal)

## Primitives (`web/src/components/ui.tsx`)

Reuse these before inventing new patterns:

- `Card`, `SectionHeading`, `Badge`, `StatTile`, `KeyValue`
- `EmptyState`, `ErrorState`, `LoadingState`, `SeverityBadge`, `ClassificationBadge`
- `StaleBanner`

Domain-specific cards live in `web/src/components/cards.tsx`.

## Copy and classification

- Matter node badges use `NODE_STATUS_LEGEND` in `web/src/utils/health.ts`
- **Presentation layer** uses Lens family buckets (`healthy`, `recently_unstable`, `needs_attention`, …) — see [lens-family.md](lens-family.md)
- Read-probe failures: **Last read check failed** (not “Read probe issue”)
- Foreign TREL / observed-other networks: **Informational**, not “competing”
- Classification badges: `whitespace-nowrap shrink-0` so labels stay on one line
- Avoid “caused by” unless structured evidence supports it

## Live updates

- Prefer SSE (`/api/v1/events/stream`) with debounced dashboard refetch
- Fall back to 30s polling when EventSource is disconnected (some Ingress proxies block SSE)
- Header dot: **Live** / **Connecting** / **Polling**

## Monitoring transparency

- In-app guide at **`/how-it-works`** — `HowItWorksPage` + `monitoringGuide.ts`
- Documents thresholds, read probes, and observation sources

## Ingress and path safety

- Vite `base: "./"` — relative asset URLs
- API paths via `web/src/api/paths.ts` — never hard-code `/api/v1/...`
- HA Ingress basename detection in `web/src/lib/base.ts`

## HACS companion panel

- Lightweight native summary — not a duplicate of the full Core UI
- **Open full ThreadLens dashboard** — primary action, new tab, always reliable
- Auto-embed Core UI when HA and Core use the same protocol (HTTP+HTTP or HTTPS+HTTPS)
- Mixed content (HTTPS HA + HTTP Core) → calm blocked screen + Open Full Dashboard
- Follows Lens family embed decision tree — see [hacs-embedded-view.md](hacs-embedded-view.md)

## What not to add

- Repair, reset, commission, or control buttons
- Causal language (“because”, “caused by”) without structured evidence
- Parentage inference from mDNS/TREL visibility alone
- External CDN fonts, scripts, or analytics
- Per-device MQTT entity explosion in default configs

## Related

- [lens-family.md](lens-family.md)
- [hacs-embedded-view.md](hacs-embedded-view.md)
- [mqtt-home-assistant.md](mqtt-home-assistant.md)
- ZigbeeLens style guide: [docs/style-guide.md](https://github.com/theaussiepom/zigbeelens/blob/main/docs/style-guide.md)
