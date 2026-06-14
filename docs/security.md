# Security

ThreadLens v1 is designed for **trusted local networks**. It is not safe to expose directly to the public internet.

## No authentication

v1 has **no API authentication**. Anyone who can reach the server port can read health, status, reports, and collector state.

**Do:**

- Bind to LAN interfaces or container networks you control
- Use firewall rules to limit access
- Put a reverse proxy with authentication in front if remote access is required

**Do not:**

- Port-forward 8128/8129 to the internet without additional controls
- Run on untrusted shared networks without isolation

## Trusted LAN assumption

ThreadLens expects the same trust model as many home automation tools: operators on the LAN are trusted. This matches typical Home Assistant deployment patterns.

## Report redaction

`reports.redact_secrets: true` (default) recursively redacts fields whose names suggest secrets.

Redacted categories include passwords, tokens, API keys, and network keys.

Redaction does **not** remove:

- Extended PAN IDs, node IDs, IP addresses
- Network names and health reason codes
- Operational timestamps and event metadata

Treat reports as sensitive operational data, not as anonymised exports.

## MQTT credentials

Broker `username` and `password` in config are used only for the MQTT client connection. They must not appear in reports or published MQTT payloads.

Do not commit real credentials to git.

## What ThreadLens does not do

| Capability | Status |
|------------|--------|
| SSH | Not implemented; agent reports `ssh_available: false` |
| Docker socket | Not implemented; agent reports `docker_socket_available: false` |
| Log scraping | Not implemented |
| Thread/Matter mutation | Not implemented; read-only observers only |
| OTBR write actions | Disabled (`allow_read_only_actions: false`) |

## Agent mode

The optional ThreadLens agent (port 8129) is also unauthenticated in v1. Treat it like the server API.

v1 agent capabilities are conservative — deep host diagnostics are not exposed.

## Docker

- Run as non-root user `threadlens`
- Mount config read-only where possible
- Do not mount Docker socket or host `/var/run` into the container

## Future improvements

Authentication, TLS termination, and HAOS add-on ingress patterns may be added in later passes. v1 prioritises simple LAN deployment.
