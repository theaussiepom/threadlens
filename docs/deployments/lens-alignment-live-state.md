# Lens alignment — live deployment state

Documentation of Ben's production Lens deployments after Phase 3D closure (2026-06-16).

**Do not commit secrets.** Hostnames and image tags only.

---

## ThreadLens (Pironman)

| Field | Value |
|-------|--------|
| Host | Pironman / `192.168.100.4` |
| Compose | `~/threadlens/docker-compose.pironman.yml` |
| Image | `ghcr.io/theaussiepom/threadlens:0.2.18` |
| Tag note | Clean MQTT release published as **v0.2.18** (`v0.2.3` already existed on an older commit) |
| MQTT summary entities | **7** global (health, issues, unavailable, needs_attention, recently_unstable, diagnostics_limited, matter_read_probe_issues) |
| `per_node_entities` | `false` |
| Old retained MQTT topics | **116** old flat ThreadLens discovery topics cleared (2026-06-15) |
| HACS | ThreadLens API companion entities **preserved** |

Traefik on BenBeast routes `threadlens.<domain>` → `http://192.168.100.4:8128`.

---

## ZigbeeLens (BenBeast)

| Field | Value |
|-------|--------|
| Host | BenBeast / `192.168.100.5` |
| Compose | `/mnt/nas/docker/automation/docker-compose.yml` (service `zigbeelens`) |
| Image | `ghcr.io/theaussiepom/zigbeelens:edge` (pre-release) or tagged release after **v0.1.13** |
| Commit reference | `23ee5fa` (PR #11 + #12 hotfix) at closure time |
| MQTT discovery | **enabled** (`features.mqtt_discovery` + `mqtt_discovery.enabled`) |
| MQTT summary entities | **6** global (health, issues, unavailable, needs_attention, recently_unstable, diagnostics_limited) |
| Per-network / per-device MQTT | **none** (not published by default) |
| Old retained MQTT topics | **none** found at enablement |
| HACS | ZigbeeLens companion entities **preserved** |

Traefik routes `zigbeelens.<domain>` → BenBeast `:8377`.

---

## Home Assistant (BenBeast)

| Field | Value |
|-------|--------|
| Container | `hass` |
| MQTT broker | `automation-mosquitto-1` / `broker.mqtt:1883` |

| Integration | MQTT summary | HACS preserved |
|-------------|--------------|----------------|
| ThreadLens | 7 entities, one `threadlens_summary` device | Yes (12 entities) |
| ZigbeeLens | 6 entities, one `zigbeelens_core` device | Yes (20 entities) |

**Known cosmetic:** HA may auto-prefix entity IDs (e.g. `sensor.zigbeelens_zigbeelens_health`). `unique_id` values are correct Lens-family IDs.

**ThreadLens rename applied:** `sensor.threadlens_matter_read_probe_issues` (was awkward auto-generated ID).

No per-device MQTT entity spam. No Home Assistant `.storage` edits were performed for this migration.

---

## Rollback pointers

| Product | Rollback |
|---------|----------|
| ThreadLens | Pin compose to previous image tag; restore config backup if changed |
| ZigbeeLens | Set `features.mqtt_discovery: false` and `mqtt_discovery.enabled: false`; restart container; config/DB backups under `*.bak-pre-zigbeelens-mqtt-*` on NAS |

See product [RELEASE.md](../RELEASE.md) / [docs/release.md](https://github.com/theaussiepom/zigbeelens/blob/main/docs/release.md) for semver tags and GHCR images.
