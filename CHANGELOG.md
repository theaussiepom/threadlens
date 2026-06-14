# Changelog

All notable changes to ThreadLens are documented in this file.

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
