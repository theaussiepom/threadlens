# Troubleshooting

## No mDNS or TREL services visible

**Symptoms:** `/api/v1/mdns/services` and `/api/v1/trel/services` are empty; status may show `observation_degraded`.

**Likely causes:**

- Docker bridge networking blocks multicast
- ThreadLens host cannot see the same LAN segment as Thread devices
- `mdns.enabled: false` in config

**Actions:**

1. On Linux, try `docker-compose.host-network.example.yml`
2. Consider macvlan/ipvlan — see [mdns-networking.md](mdns-networking.md)
3. Confirm OTBR REST still works — empty mDNS with working OTBR usually means networking visibility, not absent TREL

ThreadLens does not infer topology from missing mDNS data.

## OTBR unreachable

**Symptoms:** `/api/v1/otbrs` shows `reachable: false`; health includes OTBR reason codes.

**Likely causes:**

- Wrong `rest_url` (IP, port, or path)
- OTBR container/service not running
- Firewall between ThreadLens and OTBR
- Docker bridge cannot reach host LAN IP (use host IP reachable from container)

**Actions:**

1. `curl http://<otbr-host>:8081/api/node` from the ThreadLens host/container
2. Verify `otbrs` config IDs and URLs in [configuration.md](configuration.md)
3. Check `/api/v1/status` → `collectors.otbr`

## OTBR JSON:API shows disabled but Thread is active

**Symptoms:** `/api/v1/otbrs` shows `json_api_thread_state: disabled` while `thread_state` is `leader` or `router`; `rest_endpoint_mismatch: true`; health warning `otbr_rest_endpoint_mismatch` instead of `otbr_thread_stack_disabled`.

**Likely causes:**

- Some OTBR builds (for example `openthread/border-router:latest`) expose stale state on JSON:API `GET /api/node` while legacy `GET /node` on the same port reflects live Thread role
- Container restart left JSON:API fields at boot-time `disabled` even though OpenThread is participating

**Actions:**

1. Compare endpoints from the OTBR host: `curl http://127.0.0.1:8081/api/node` and `curl http://127.0.0.1:8081/node`
2. Confirm `ot-ctl state` if you have shell access — ThreadLens does not run `ot-ctl`
3. Leave `otbr.use_legacy_node_fallback: true` (default) so ThreadLens reconciles with legacy `/node`
4. Treat `otbr_rest_endpoint_mismatch` as a REST reporting issue, not proof that Thread is down

ThreadLens reports endpoint mismatch rather than assuming the Thread stack is disabled when only JSON:API is stale.

## Matter Server disconnected

**Symptoms:** `/api/v1/matter-servers` shows disconnected; nodes stale or missing.

**Likely causes:**

- Wrong `websocket_url`
- Matter Server not running or not listening on expected port
- Network/firewall blocking websocket

**Actions:**

1. Confirm websocket URL (Python Matter Server default often `ws://<host>:5580/ws`)
2. Check Matter Server logs on the host
3. Review `/api/v1/status` → `collectors.matter`

## MQTT not connecting

**Symptoms:** `/api/v1/status` → `collectors.mqtt.connected: false`

**Likely causes:**

- `mqtt.enabled: false`
- Wrong broker host/port
- Broker credentials incorrect
- HA MQTT integration not running

**Actions:**

1. Enable MQTT in config
2. Test broker with `mosquitto_pub` from same network as ThreadLens
3. Match `discovery_prefix` to HA (default `homeassistant`)
4. See [mqtt-home-assistant.md](mqtt-home-assistant.md)

## Report empty or sparse

**Symptoms:** Report has few OTBRs, nodes, or events.

**Likely causes:**

- No `otbrs` or `matter_servers` configured
- Collectors still warming up
- New install with no events in window

**Actions:**

1. Uncomment/configure examples in `examples/config/config.yaml`
2. Wait for collector poll cycles (default 60s for OTBR)
3. Generate report after collectors show data in `/api/v1/status`
4. Try `window=7d` if you expect older events

## Agent unreachable

**Symptoms:** `/api/v1/status` → `agents.unreachable > 0`

**Likely causes:**

- `agent_url` configured but agent not running
- Wrong port (default 8129)
- Firewall

**Actions:**

1. Run `threadlens --mode agent` or `THREADLENS_MODE=both`
2. `curl http://<host>:8129/api/v1/agent/health`
3. Agent unavailability does not block server startup or OTBR collection

## Docker healthcheck failing

**Symptoms:** Container marked unhealthy.

**Likely causes:**

- Running agent-only mode but healthcheck targets port 8128
- Server still starting (increase `start-period`)
- Storage path not writable

**Actions:**

1. Use server or both mode, or override healthcheck — see [docker.md](docker.md)
2. Ensure `/data` volume is writable
3. `curl http://127.0.0.1:8128/api/v1/health` inside container

## Runtime validation checklist

```bash
threadlens --version
threadlens --mode server
curl http://127.0.0.1:8128/api/v1/health
curl http://127.0.0.1:8128/api/v1/status
curl http://127.0.0.1:8128/api/v1/version
curl http://127.0.0.1:8128/api/v1/report.yaml
```

Docker:

```bash
docker build -t ghcr.io/theaussiepom/threadlens:local .
docker compose -f docker-compose.example.yml up
```

Host networking (Linux):

```bash
docker compose -f docker-compose.host-network.example.yml up
```

Live test (example two-Pi topology): [LIVE_TEST_0.1.0.md](../LIVE_TEST_0.1.0.md)
