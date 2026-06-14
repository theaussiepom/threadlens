# Contributing

Contributions are welcome — issues, documentation fixes, and pull requests.

## Before you submit

Run locally:

```bash
ruff check .
ruff format --check .
pytest -q
```

For Docker changes, confirm `docker build -t threadlens:test .` succeeds.

## Guidelines

- Keep collectors **read-only** unless a change is explicitly discussed and approved
- Do not add mutating OTBR, Matter, or Thread commands in normal code paths
- Do not commit secrets in fixtures, logs, live captures, or example configs
- Use `null` placeholders for MQTT credentials in committed YAML
- Match existing code style and test patterns
- Prefer focused PRs with a clear description and test plan

## Secrets

Never commit:

- MQTT passwords
- Thread network keys or PSKc
- Matter fabric credentials
- Live host-specific configs with real broker auth

Use local override files (gitignored) for live deployments. See `docs/configuration.md`.

## Questions

Open an issue for design questions before large refactors.
