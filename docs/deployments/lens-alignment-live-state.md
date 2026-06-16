# Lens alignment — live deployment state

Documentation of Ben's production Lens deployments (last validated 2026-06-16).

**Do not commit secrets.** Hostnames and image tags only.

---

## ThreadLens (Pironman)

| Field | Value |
|-------|--------|
| Host | Pironman / `192.168.100.4` |
| Compose | `~/threadlens/docker-compose.pironman.yml` |
| Image | `ghcr.io/theaussiepom/threadlens:0.2.20` |
| `/api/v1/version` | `0.2.20` |
| Report/export alignment | **Live** (v0.2.20) |
| MQTT discovery | **7** clean Lens summary discovery configs |
| Old flat MQTT topics | **0** (116 legacy topics cleared 2026-06-15) |
| `per_node_entities` | `false` |
| HACS | ThreadLens API companion entities **preserved** |

Traefik on BenBeast routes `threadlens.<domain>` → `http://192.168.100.4:8128`.

**History:** Clean MQTT shipped as **v0.2.18** (`v0.2.3` tag already existed). Version metadata aligned in **v0.2.19**. Report/export alignment live in **v0.2.20**.

---

## ZigbeeLens (BenBeast)

| Field | Value |
|-------|--------|
| Host | BenBeast / `192.168.100.5` |
| Compose | `/mnt/nas/docker/automation/docker-compose.yml` (service `zigbeelens`) |
| Live image channel | `ghcr.io/theaussiepom/zigbeelens:edge` (rolling — **not** pinned to semver) |
| Validated edge content | v0.1.13-era / commit `9a52470` |
| Edge digest (last check) | `sha256:54ace1377477…` |
| Semver image (exists, not Beast live channel) | `ghcr.io/theaussiepom/zigbeelens:0.1.13` |
| `/api/version`, `/api/v1/version` | `0.1.13` |
| MQTT discovery | **enabled** |
| MQTT summary entities | **6** clean Lens summary discovery configs |
| Old flat MQTT topics | **0** |
| Per-network / per-device MQTT | **none** by default |
| HACS | ZigbeeLens companion entities **preserved** |

Traefik routes `zigbeelens.<domain>` → BenBeast `:8377`.

Config backups: `*.bak-pre-zigbeelens-mqtt-*` on NAS under `zigbeelens/`.

---

## Home Assistant (BenBeast)

| Field | Value |
|-------|--------|
| Container | `hass` |
| MQTT broker | `automation-mosquitto-1` / `broker.mqtt:1883` |

| Integration | MQTT summary | HACS preserved |
|-------------|--------------|----------------|
| ThreadLens | 7 entities, `threadlens_summary` device | Yes |
| ZigbeeLens | 6 entities, `zigbeelens_core` device | Yes |

**Known cosmetic:** HA may auto-prefix entity IDs (e.g. `sensor.zigbeelens_zigbeelens_health`). `unique_id` values are correct Lens-family IDs.

No per-device MQTT entity spam. No Home Assistant `.storage` edits for Lens migration.

---

## Rollback pointers

| Product | Rollback |
|---------|----------|
| ThreadLens | Pin compose to previous image tag; restore compose backup (`*.bak-hygiene-*`) |
| ZigbeeLens | Keep `:edge` and pull previous digest, or set `features.mqtt_discovery: false`; config/DB backups under `*.bak-pre-zigbeelens-mqtt-*` |

See [RELEASE.md](../RELEASE.md) / [ZigbeeLens release docs](https://github.com/theaussiepom/zigbeelens/blob/main/docs/release.md).
