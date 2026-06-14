# mDNS and Docker networking

ThreadLens observes LAN multicast DNS for TREL, MeshCoP, and Matter service types. Docker networking strongly affects whether those services are visible inside the container.

## Service types observed

| Service type | Purpose |
|--------------|---------|
| `_trel._udp` | TREL tunnel endpoints |
| `_meshcop._udp` | Thread commissioning / MeshCoP |
| `_matter._tcp` | Matter commissioner |
| `_matterc._udp` | Matter commissioner (UDP) |

API endpoints:

- `GET /api/v1/mdns/services`
- `GET /api/v1/trel/services`

## Bridge mode (default)

`docker-compose.example.yml` uses bridge networking with published ports.

**Typical behaviour:**

- OTBR REST polling works if `rest_url` is reachable
- Matter Server websocket works if `websocket_url` is reachable
- MQTT publishing works if broker is reachable
- **mDNS/TREL observation is often degraded or unavailable**

If mDNS/TREL lists are empty but OTBR and Matter collectors work, treat this as a **network visibility** limitation — not proof that TREL services are absent on your LAN.

## Host networking (Linux — recommended for mDNS)

```bash
docker compose -f docker-compose.host-network.example.yml up
```

Requirements:

- Linux host (Docker Desktop on macOS does not provide equivalent host networking)
- Do not define `ports:` when using `network_mode: host`
- Container shares the host network stack and can receive multicast

## macvlan / ipvlan alternatives

If host networking is not suitable, attach the container to a macvlan or ipvlan network on the same LAN segment as your Thread/Matter devices. Multicast must reach the container interface.

Configuration is environment-specific; consult your platform's Docker networking docs.

## Home Assistant OS add-on

The [threadlens-ha-addon](https://github.com/theaussiepom/threadlens-ha-addon) repository packages ThreadLens for Home Assistant OS with **host networking** enabled by default for reliable mDNS/TREL observation.

## What ThreadLens does not infer

ThreadLens **must not** infer device parentage, OTBR ownership, or network topology from mDNS/TREL visibility alone. Empty mDNS results mean observation was unavailable or no matching services were seen — not that the LAN has no TREL.

## Troubleshooting checklist

1. Confirm `mdns.enabled: true` in config
2. Confirm service type list includes the types you expect
3. Try host networking on Linux
4. Compare with OTBR REST and Matter websocket status — if those work, focus on Docker networking
5. Check `/api/v1/status` → `collectors.mdns.observation_degraded`

See also [troubleshooting.md](troubleshooting.md).
