# Changelog

All notable changes to ThreadLens are documented in this file.

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
- `mdns_service_flapping_warning` may appear from `mdns.service_changed` events — monitor only unless it escalates to degraded

## [0.1.0] - 2026-06-13

Initial live-testable release.

- Read-only OTBR REST, Matter Server websocket, mDNS/TREL observers
- SQLite storage, health engine, MQTT Discovery publisher, report API
- Docker packaging and example compose files
- Agent mode (minimal v1)
