# HACS embedded view — optional HTTPS dashboard address

## Lens family — embedded view decision tree

Shared across [ThreadLens](https://github.com/theaussiepom/threadlens) and [ZigbeeLens](https://github.com/theaussiepom/zigbeelens). See [lens-family.md](lens-family.md).

```text
1. Native companion panel first
      → status, incidents, summary counts, repairs/diagnostics

2. Optional embedded Core dashboard when safe
      → same HTTP/HTTPS scheme as Home Assistant; CSP/frame-ancestors allow embed

3. If embedding blocked or mixed-content unsafe
      → keep native panel + Open full dashboard button (new tab)

4. Keep HA menu/burger behaviour usable
      → iframe must not trap navigation; user can always return to HA chrome

5. No mutation/control buttons in companion panel
      → read-only observability only
```

Product-specific URLs and Traefik examples follow below.

---

The embedded dashboard view is **optional**. Most users do not need it. The default HACS experience is the native companion panel plus the **Open full ThreadLens dashboard** button.

Embedded view is useful if you want the full ThreadLens Core router UI to appear inside the Home Assistant sidebar. For browser security reasons, this usually requires Home Assistant and ThreadLens Core to **both be served over HTTPS**.

**HTTP is fine** for the native Home Assistant panel and **Open full ThreadLens dashboard**. You do not need a reverse proxy for normal HACS use.

An HTTPS Core URL may be **required** for the optional embedded dashboard view, but **HTTPS is not authentication**. If the HTTPS route is reachable by networks you do not trust, access-control remains your responsibility.

---

## Quick summary

| Home Assistant | ThreadLens Core | Embedded view |
|----------------|-----------------|---------------|
| HTTPS | HTTP | Blocked (expected) |
| HTTPS | HTTPS | Works when headers allow embedding |
| HTTP | HTTP | Works |

### Correct Core URLs (example homelab)

| Use | URL |
|-----|-----|
| Default HACS / LAN | `http://192.168.100.4:8128` |
| Optional HTTPS / iframe | `https://threadlens.theaussiepom.me` |
| **Wrong** | `https://threadlens.theaussiepom.me:8128` |

Traefik serves HTTPS on **port 443 only**. Appending `:8128` to an HTTPS hostname hits the container directly (HTTP), not the reverse proxy.

If Home Assistant uses HTTPS and Core uses `http://192.168.100.4:8128`, the panel shows a friendly blocked explanation — not a broken iframe. **Open full ThreadLens dashboard** still works in a new tab.

## When to use HTTPS in front of Core

Use an HTTPS dashboard address only if you **want** embedded view inside the HACS sidebar and accept the extra setup.

You do **not** need HTTPS or a reverse proxy for:

- Native companion panel (status, Matter summary, OTBR/mDNS/TREL)
- HACS sensors, repairs, diagnostics
- **Open full ThreadLens dashboard** in a new tab

Alternatives to reverse proxy for embedded full UI:

- **HAOS add-on + Ingress** — designed embedded path (same-origin through Home Assistant)
- **Open full ThreadLens dashboard** — no proxy

## Overview

```text
Home Assistant (HTTPS)
  └── HACS companion panel
        └── auto-embed or Try Embedded View
              └── https://threadlens.yourname.example  (HTTPS Core URL)
                        └── reverse proxy (TLS)
                              └── http://pironman:8128  (Core container)
```

After setup:

1. Core is reachable at an **HTTPS** URL from the browser running Home Assistant.
2. **Settings → Devices & services → ThreadLens → Configure** — set Core URL to that HTTPS address (no `:8128` suffix on Traefik hostnames).
3. The sidebar auto-embeds the Core router UI when schemes match.

Core sends `Content-Security-Policy: frame-ancestors *` on `/` and `/assets/*`. Your reverse proxy must not override this with a stricter policy unless you allow the Home Assistant origin explicitly.

---

## Technical note — mixed content and headers

Browsers block embedding an HTTP dashboard inside an HTTPS Home Assistant page (**mixed content**).

For embedded view through Traefik or another proxy, also check:

- `Content-Security-Policy: frame-ancestors` must allow your Home Assistant origin
- `X-Frame-Options: DENY` blocks embedding
- SSE may need proxy buffering disabled (`flush_interval -1` on Caddy, or equivalent) — the dashboard falls back to 30s polling if the event stream is blocked

---

## Beast / Traefik (homelab file provider)

ThreadLens runs on Pironman (Study Pi) with **host networking** for mDNS/TREL. Beast Traefik routes HTTPS to the Pironman LAN address.

Typical split (mirror ZigbeeLens / MASS pattern):

- **`threadlens-api`** — `PathPrefix(/api)`, priority 100, local middleware, **no Authentik** (HACS config flow calls `GET /api/v1/health`)
- **`threadlens`** — UI/dashboard on `threadlens.${DOMAIN}`, Authentik on UI paths only

Example HTTPS Core URL: `https://threadlens.theaussiepom.me` (no port suffix).

Traefik middleware should set `frame-ancestors` to your Home Assistant origin, for example `https://hass.theaussiepom.me`, rather than blocking all frames.

---

## Caddy (self-contained LAN example)

```caddyfile
threadlens.lan {
    tls internal
    reverse_proxy 192.168.100.4:8128 {
        flush_interval -1
    }
}
```

Trust Caddy's internal CA on devices that open Home Assistant, or use a public domain with Let's Encrypt.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Blank iframe | Mixed content | Use HTTPS Core URL or Open full dashboard |
| Config flow fails on HTTPS HA | Authentik on `/api` | Add API bypass router |
| Dashboard never updates live | SSE buffered by proxy | Disable proxy buffering; UI falls back to polling |
| `:8128` on HTTPS hostname fails | Wrong port | Use `https://host` without port on 443 |

---

## Related docs

- [lens-family.md](lens-family.md) — shared Lens conventions
- [style-guide.md](style-guide.md) — UI sibling conventions
- [home-assistant-integration.md](home-assistant-integration.md) — HA Matter device names
- [mdns-networking.md](mdns-networking.md) — host networking for mDNS/TREL
- HACS integration README — companion panel behaviour
