# Changelog

All notable changes to ThreadLens are documented in this file.

## [Unreleased]

## [0.2.19] - 2026-06-16

### Changed

- Version metadata aligned to **0.2.19** in package sources and `/api/v1/version` (cosmetic fix; no functional change from v0.2.18 clean MQTT release)

## [0.2.18] - 2026-06-16

### Changed

- **MQTT Discovery:** clean Lens-family global summary entities (health, issues, bucket counts, Matter read probe issues)
- **MQTT Discovery:** `per_node_entities` defaults to `false`; per-node entities only when explicitly enabled
- **MQTT Discovery:** new topic layout under `homeassistant/sensor/threadlens/<entity_key>/config` and `threadlens/summary/<entity_key>/state`
- **MQTT Discovery:** backward compatibility intentionally not preserved; migration docs for clearing old retained discovery configs
- **Release process:** [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) aligned with Lens family release language ([docs/lens-family.md](docs/lens-family.md))

### Notes

- Matter read probe **behaviour is unchanged** from the validated model; read probe issues remain a global summary entity only
- No Matter control commands in normal operation
- HACS companion entities are separate from MQTT summary entities and were preserved during Ben's deployment migration
- HACS UI was source-validated; full browser visual smoke was not part of this release

## [0.2.15] - 2026-06-15

### Added

- **How it works** dashboard page — read-only scope, data sources, health classification, HA paths
- SSE live updates at `/api/v1/events/stream` with 30s polling fallback when EventSource is unavailable
- [docs/style-guide.md](docs/style-guide.md) and [docs/hacs-embedded-view.md](docs/hacs-embedded-view.md)

### Changed

- Dashboard connection indicator shows Live / Connecting / Polling based on SSE state

## [0.2.14] - 2026-06-15

### Changed

- Dashboard responses set `Content-Security-Policy: frame-ancestors *` on `/` and `/assets/*` so Home Assistant can embed the Core UI in the companion panel iframe

## [0.2.13] - 2026-06-15

### Changed

- Classification badges no longer wrap on device cards (`Needs attention`, `Recently unstable`, etc.)
- Clearer read-probe classification reasons: `Last read check failed` instead of `Read probe issue`
- Device detail restores ping diagnostics and fuller read-probe fields (unsupported paths, duration, notes)

## [0.2.12] - 2026-06-15

### Changed

- Devices page always shows healthy Matter nodes (removed Show/Hide toggle)

### Removed

- Legacy single-page dashboard components and CSS (`theme.css`, `app.css`, modal drilldown, infra column layout) superseded by the 0.2.11 router UI

## [0.2.11] - 2026-06-15

### Changed

- Core dashboard refactored to ZigbeeLens-style sibling UI: Tailwind v4 dark `zl-*` theme, sidebar + React Router pages (Overview, Devices, Infrastructure, Timeline, Reports, Diagnostics), and routed device detail views
- IBM Plex fonts bundled in the dashboard build (no external font URLs in production assets)

## [0.2.10] - 2026-06-15

### Added

- Document that Home Assistant Matter device names are supplied by the HACS integration (`docs/home-assistant-integration.md`)

### Changed

- Matter node list: slimmer rows (no Thread/IPv6/OTBR on dashboard list), status legend open by default, read-check badges only when unhealthy
- Clearer Matter health reason labels; removed TREL parentage footnote

## [0.2.9] - 2026-06-15

### Fixed

- Dashboard ignores stale persisted limited flags when the last read check succeeded

## [0.2.8] - 2026-06-15

### Fixed

- Devices that respond to a fallback read check are no longer marked diagnostics limited or shown probe-internal fallback notes

## [0.2.7] - 2026-06-14

### Added

- Read probe planner discovers candidate attribute paths from each node's own Matter attribute keys before falling back to generic paths
- Matter servers section shows health reason chips when Matter health is not OK
- Collapsible status legend on Matter node health defines what "Recently unstable", "Diagnostics limited", and "24h" mean

### Changed

- Clearer read-probe limited messaging explaining why identical devices can differ by Matter endpoint
- Drilldown shows working probe path and unsupported paths; diagnostics-limited nodes no longer get the "insufficient event history" assessment
- TREL section no longer shows confusing "raw health" when it differs from display health

## [0.2.6] - 2026-06-15

### Fixed

- Capture Thread IPv6 for all available Matter nodes on Matter Server connect, not only during the slow read-probe round-robin

## [0.2.5] - 2026-06-15

### Added

- OTBR read-only device inventory collection (`updateDeviceCollectionTask`) stores Thread extended addresses and OMR IPv6 per mesh device
- Matter node thread identity via safe `ping_node` IPv6 capture, correlated to OTBR inventory without inferring parentage
- Dashboard list and drilldown show Thread extended address and Thread IPv6 when observed

## [0.2.4] - 2026-06-15

### Changed

- Matter node list and drilldown always show the Matter server name (`friendly_name`), not only when it differs from the HA label
- Drilldown shows configured OTBR ids, HA name, and read probe evidence (failures, path, last result) in the primary details table
- Node rows include `otbr_ids` from configured OTBRs on the dashboard payload

## [0.2.3] - 2026-06-15

Dashboard and HA enrichment release after Study Pi read-probe validation.

### Added

- Home Assistant Matter device name enrichment API (`POST /api/v1/integrations/homeassistant/matter-names`)
- Per-node `classification_reason` on the dashboard payload so unstable nodes explain read probe vs availability causes
- Per-node read probe failure counters in the Core web UI (`N read failures (24h)`)

### Changed

- Incident summary uses read-probe-specific wording when instability is probe-only; affected nodes show per-node reasons
- Node drilldown assessment covers read-probe-only instability without availability events
- Dashboard prefers `ha_device_name` for node labels when enriched from Home Assistant

### Notes

- Requires ThreadLens HACS integration **0.1.19+** to push HA device names to Core

## [0.2.2] - 2026-06-15

Post-validation tuning release for Matter read probes (PR #15).

### Changed

- Public probe disabled mode is now `disabled` instead of `off`; `"off"` and YAML `false` map to `disabled` to avoid YAML parser footguns
- Standard mode tries inferred device-specific read probes (e.g. Window Covering `*/258/10`) before generic Basic Information fallback
- Unsupported or failing blind-specific probes with successful generic fallback surface as diagnostics limited, not unavailable
- Docs include temporary validation interval example and updated mode guidance

### Notes

- Intended for final Matter read probe validation on Study Pi after v0.2.1 `PASS WITH TUNING`

## [0.2.1] - 2026-06-15

Validation build for the Matter read probe feature stream (PRs #9–#13). Intended for live validation on Study Pi before a final probe release declaration.

### Added

- Matter websocket request manager for correlated read-only Matter Server requests
- Matter read probe foundation: config, models, manual runner, and scheduler
- Read probe health, dashboard, and report surfacing with friendly labels
- MQTT read probe summary entities and documentation (`matter-read-probes.md`, Future Option 2 docs)
- `MatterProbePlanner` with user-facing probe modes (`off`, `conservative`, `standard`, `diagnostic`)
- Advanced-only raw attribute path overrides under `matter.probes.advanced`
- Per-node unsupported-path learning and last-successful-probe reuse

### Changed

- Probe config is mode-only; legacy `enabled` and top-level probe tuning keys are rejected

### Notes

- Default probe mode is `off` — probes must be enabled explicitly for live validation
- This release does not declare live probe validation complete

## [0.2.0] - 2026-06-14

### Added

- `GET /api/v1/dashboard` — Core-native dashboard payload aggregation (read-only, Home Assistant agnostic)
- Dashboard semantics for reconciled OTBR endpoint mismatch, informational foreign TREL, Matter node health classification, incident summary, and relative report URLs
- Core static dashboard serving foundation (`THREADLENS_STATIC_DIR`, SPA fallback, API route guard)
- Canonical Core-owned **React + TypeScript dashboard** (source in `web/`, built with Vite into `static/`) — the first Core-owned React/mobile dashboard release. Mobile-first and desktop-friendly, served by Core at `/`, consuming `api/v1/dashboard` via path-safe relative URLs (works under root, reverse-proxy subpaths, and Home Assistant Ingress prefixes). Includes incident summary, at-a-glance Matter node health grouped by severity with full-screen/side-panel node drilldown, OTBR/network/Matter/mDNS/TREL/MQTT sections, relative report links, raw diagnostics, light/dark themes, and loading/error/stale/empty states. No Node at runtime, no external CDN, no Home Assistant dependency.
- Multi-stage Docker build adds a Node stage that compiles the dashboard and copies built assets into `/app/static`; CI validates the frontend lint/typecheck/build alongside Python checks and the Docker image build

## [0.1.2] - 2026-06-14

Patch release — mDNS flap health semantics and public-release documentation polish.

### Fixed

- mDNS/TREL flap health counts only non-initial `service_added` and `service_removed` events
- Normal `service_changed` refresh churn no longer escalates to `mdns_service_flapping_degraded`
- Multi-arch GHCR publish (`linux/amd64`, `linux/arm64`) for Raspberry Pi deployments

### Changed

- Committed example configs use generic `192.168.1.x` placeholders and `username`/`password: null`
- README and release docs updated for first-time Home Assistant users
- Release deployment examples pin `ghcr.io/theaussiepom/threadlens:0.1.2`

### Known expected warnings

- `otbr_rest_endpoint_mismatch` when OTBR JSON:API `/api/node` is stale while `/node` is active
- `foreign_trel_services_observed` when foreign Apple/HomePod TREL services are visible

## [0.1.1] - 2026-06-14

Live-test hardening release after Ben Home validation (Study Pi + Lounge OTBR topology).

### Fixed

- mDNS/TREL zeroconf listener callback crash (`_AsyncMdnsListener` AttributeError)
- Startup mDNS/TREL discovery no longer counted as service flapping degradation
- Home Assistant MQTT Discovery respects `homeassistant.mqtt_discovery_enabled`
- OTBR live JSON:API parser tolerance for flattened and nested response shapes
- OTBR `thread_state` and `thread_stack_active` semantics for disabled vs active stacks
- `/api/v1/otbrs` embedded health alignment with `/api/v1/health`
- Stale OTBR JSON:API `/api/node` reconciled against legacy read-only `/node` fallback

### Added

- `otbr.use_legacy_node_fallback` config (default `true`)
- OTBR reconciliation fields: `thread_state_source`, `json_api_thread_state`, `legacy_node_thread_state`, `rest_endpoint_mismatch`
- Health warning `otbr_rest_endpoint_mismatch` when JSON:API is stale but Thread is active
- GitHub Actions container publish workflow for `ghcr.io/theaussiepom/threadlens`

### Validated (Ben Home live environment)

- MQTT connected and publishing Home Assistant Discovery topics
- mDNS count 30, TREL count 8, Matter nodes 12 / 0 unavailable
- Study OTBR effective state `leader`, Lounge `router` via legacy `/node` reconciliation
- Clean-start DB validation: no false `mdns_service_flapping_degraded` or `otbr_thread_stack_disabled`

### Known expected warnings

- `otbr_rest_endpoint_mismatch` when OTBR JSON:API `/api/node` is stale while `/node` is active
- `foreign_trel_services_observed` when foreign Apple/HomePod TREL services are visible
- `mdns_service_flapping_warning` may appear from true add/remove instability — monitor only unless it escalates to degraded

## [0.1.0] - 2026-06-13

Initial live-testable release.

- Read-only OTBR REST, Matter Server websocket, mDNS/TREL observers
- SQLite storage, health engine, MQTT Discovery publisher, report API
- Docker packaging and example compose files
- Agent mode (minimal v1)
