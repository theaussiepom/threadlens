# Home Assistant integration (device names)

ThreadLens **Core does not** read the Home Assistant device or entity registry. Matter node labels in Core storage and the Core dashboard come from Matter Server observations (`friendly_name`, serial, vendor, product) unless enriched by an external integration.

**Home Assistant device names are supplied by the [ThreadLens HACS integration](https://github.com/theaussiepom/threadlens-ha-integration).** That integration maps Matter nodes in ThreadLens to devices/entities in Home Assistant and pushes the familiar names (for example blind or cover names) to Core.

## What Core stores

When enrichment succeeds, each `MatterNodeState` may include:

| Field | Source |
|-------|--------|
| `friendly_name` | Matter Server websocket observer |
| `ha_device_name` | HACS integration push |
| `ha_entity_id` | HACS integration push (preferred cover entity when available) |

The dashboard and reports prefer **`ha_device_name`** for the primary node label when present, then fall back to `friendly_name` / Matter serial.

## Enrichment API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/integrations/homeassistant/matter-names` | Apply HA device names to stored Matter nodes |

### Request body

```json
{
  "source": "homeassistant",
  "devices": [
    {
      "server_id": "study_matter",
      "node_id": 17,
      "ha_device_name": "Study Blind",
      "ha_entity_id": "cover.study_blind"
    }
  ]
}
```

- **`server_id`** — must match a configured Matter Server id in ThreadLens config.
- **`node_id`** — Matter node id as observed by ThreadLens (integer).
- **`ha_device_name`** — Home Assistant device or entity friendly name to show in the dashboard.
- **`ha_entity_id`** — optional; typically the primary `cover.*` entity when the device is a blind.

### Response

```json
{
  "matched_devices": 12,
  "last_push_at": "2026-06-15T06:00:00+00:00",
  "source": "homeassistant"
}
```

`matched_devices` counts nodes updated in Core storage. Entries that do not match a known `(server_id, node_id)` pair are skipped silently.

## What Core does not do

- Does not call Home Assistant APIs or websocket
- Does not scrape the entity registry on its own
- Does not infer HA names from MQTT Discovery entity names
- Does not guess device names from mDNS or TREL

If the HACS integration is not installed, not configured, or has not pushed yet, Matter nodes display Matter Server names (often serials such as `SCM-MT-2507-0099`).

## Requirements

- ThreadLens Core **0.2.3+** (enrichment endpoint and dashboard `ha_device_name` support)
- [ThreadLens HACS integration](https://github.com/theaussiepom/threadlens-ha-integration) **0.1.19+** (automatic push on startup and registry updates)

## MQTT Discovery vs HACS names

MQTT Discovery exposes ThreadLens health and inventory entities in Home Assistant. That path does **not** populate `ha_device_name` on Matter nodes in Core.

For familiar blind/device names on the ThreadLens dashboard, use the **HACS integration** — not MQTT alone.

## Troubleshooting missing HA names

1. Confirm the HACS integration is configured with the correct Core API URL.
2. Confirm Core shows the node under `/api/v1/matter-nodes` with the expected `node_id`.
3. In Home Assistant, confirm the Matter device exists in the device registry and has the name you expect.
4. Reload the ThreadLens integration or restart Home Assistant to trigger another name push.
5. Check Core logs for `POST /api/v1/integrations/homeassistant/matter-names` activity after integration startup.

See the HACS repository doc [ha-matter-device-names.md](https://github.com/theaussiepom/threadlens-ha-integration/blob/main/docs/ha-matter-device-names.md) for matching rules and integration-side troubleshooting.

## Related docs

- [REST API](api.md) — full endpoint list
- [MQTT and Home Assistant](mqtt-home-assistant.md) — MQTT Discovery entities (separate from name enrichment)
