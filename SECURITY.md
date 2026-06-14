# Security Policy

ThreadLens v1 has **no authentication**. Run it only on a trusted LAN or behind appropriate network controls.

## Reporting a vulnerability

**Do not include secrets in issues, pull requests, or public comments.**

Redact before sharing:

- Thread network credentials, PSKc, network keys
- Matter fabric secrets, commissioning codes, device credentials
- MQTT broker usernames and passwords
- API tokens, SSH keys, or host passwords

### Preferred: GitHub private vulnerability reporting

If enabled for this repository:

1. Open the repository on GitHub
2. Go to **Security** → **Report a vulnerability**
3. Submit a private report without secrets

### Alternative

Open a minimal public issue asking for a private contact path. Do not paste logs or configs containing secrets.

To enable private reporting (maintainers): **Settings** → **Security** → **Private vulnerability reporting** → Enable.

## Scope notes

ThreadLens is read-only observability. It does not commission Thread devices, mutate OTBR/Matter state, or execute `ot-ctl`, SSH, or Docker socket operations in normal code paths.

Report issues about accidental secret exposure in reports, MQTT payloads, or API responses as high priority.
