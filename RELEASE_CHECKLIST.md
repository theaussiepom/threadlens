# Release checklist — ThreadLens

Use this checklist before tagging a ThreadLens release. See [RELEASE.md](RELEASE.md) for publish workflow and [docs/lens-family.md](docs/lens-family.md) for shared Lens family release language.

## Automated tests and validation

Run all automated checks:

```bash
./scripts/run-release-checks.sh
```

- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] `pytest -q` passes
- [ ] Version alignment passes (`pyproject.toml`, `threadlens/__init__.py`, `web/package.json`, `/api/v1/version`)
- [ ] Web lint passes (`npm --prefix web run lint`)
- [ ] Web typecheck passes (`npm --prefix web run typecheck`)
- [ ] Web production build passes (`npm --prefix web run build`)
- [ ] Built dashboard assets present (`static/index.html`, `static/assets/`)
- [ ] Example configs keep Matter read probes disabled/commented
- [ ] Forbidden overclaiming wording scan passes (no “command failed” style copy in product paths)
- [ ] Docker build passes locally **or** CI `docker` job green (local Docker optional)

---

## 1. Version and release metadata

- [ ] `pyproject.toml` `version` updated
- [ ] `threadlens/__init__.py` `__version__` matches
- [ ] `web/package.json` `version` matches (dashboard bundle metadata)
- [ ] `GET /api/v1/version` returns the same version after deploy
- [ ] [CHANGELOG.md](CHANGELOG.md) updated for the release
- [ ] Git tag planned (`vX.Y.Z`) — do not tag until checklist complete

---

## 2. Read-only guardrails

Confirm ThreadLens remains **read-only observability**:

- [ ] No Matter control commands in normal operation
- [ ] No `write_attribute` or commissioning flows
- [ ] No Thread dataset changes
- [ ] No mutating OTBR actions (`ot-ctl`, POST commissioning, resets)
- [ ] No blind/device movement commands
- [ ] No SSH or log scraping requirement in normal operation
- [ ] No Docker socket requirement

See [SECURITY.md](SECURITY.md) and [docs/security.md](docs/security.md).

---

## 3. Matter read probe release gates

Read probes are **optional** and must ship conservatively:

- [ ] Default config keeps probes disabled (`matter.probes.mode: disabled` or section commented)
- [ ] Public examples use `mode: disabled | conservative | standard | diagnostic` — **not** `enabled: true`
- [ ] No committed example enables probes without explicit review
- [ ] `conservative` / `standard` / `diagnostic` modes documented in [docs/matter-read-probes.md](docs/matter-read-probes.md)
- [ ] Standard mode attempts device-specific paths then generic fallback (no control commands)
- [ ] Unsupported/fallback paths classify as **diagnostics limited**, not unavailable
- [ ] UI/docs avoid “command failed”, “open/close failed”, “blind command failed” overclaims
- [ ] Dashboard overview hides raw probe paths; node detail shows probe type/path
- [ ] Reports include limitations for probe gaps
- [ ] MQTT/HACS copy uses “read probe” / “read check” wording

---

## 4. Core runtime verification

- [ ] Core starts in `mode: server` on port **8128** (default)
- [ ] Optional agent starts on port **8129** when configured
- [ ] `/api/v1/health` returns JSON summary
- [ ] `/api/v1/dashboard` returns incident summary + node groups
- [ ] `/api/v1/capabilities` returns stable flags (no secrets)
- [ ] `/api/v1/status` returns collector summary (no secrets)
- [ ] `/api/v1/events/stream` connects (SSE or polling fallback in UI)
- [ ] Reports generate: `/api/v1/report.yaml` and `/api/v1/report.json`
- [ ] Report redaction spot-checked (`reports.redact_secrets: true`)

---

## 5. Live validation smoke (deployment examples)

Replace `<core-host>` with your Core host (LAN IP or HTTPS hostname).

```bash
curl -s http://<core-host>:8128/api/v1/version | jq
curl -s http://<core-host>:8128/api/v1/health | jq '.summary'
curl -s http://<core-host>:8128/api/v1/dashboard | jq '.summary'
curl -s http://<core-host>:8128/api/v1/capabilities | jq
curl -s http://<core-host>:8128/api/v1/status | jq
```

### Example homelab (Study Pi / Pironman — adjust for your site)

These are **examples**, not requirements for all users:

- [ ] Core reachable at e.g. `http://192.168.100.4:8128`
- [ ] Agent reachable at e.g. `http://192.168.100.4:8129` when agent mode used
- [ ] mDNS/TREL visible when using host networking ([docs/mdns-networking.md](docs/mdns-networking.md))
- [ ] Matter nodes appear with expected counts for your fabric
- [ ] Dashboard loads on phone-width viewport (~360–430px)

---

## 6. Docker / GHCR image gates

- [ ] CI `docker` job green on release PR
- [ ] GitHub Actions publish workflow succeeds for tag
- [ ] GHCR image published: `ghcr.io/theaussiepom/threadlens:X.Y.Z`
- [ ] Multi-arch manifest includes `linux/amd64` and `linux/arm64` (when CI matrix enabled)
- [ ] Container boots and serves dashboard at `/`
- [ ] `static/index.html` and `static/assets/` present in image
- [ ] Container logs contain no secrets

Pin tags in production — avoid floating `latest` unless intentional.

---

## 7. HACS integration gates (external repo)

HACS integration lives in [threadlens-ha-integration](https://github.com/theaussiepom/threadlens-ha-integration).

- [ ] Compatible HACS / HA version noted in integration README
- [ ] Config flow accepts Core URL reachable from Home Assistant
- [ ] Native companion panel loads (cards, not raw JSON)
- [ ] **Open full ThreadLens dashboard** opens Core in new tab
- [ ] Optional embed safe when HA/Core schemes match ([docs/hacs-embedded-view.md](docs/hacs-embedded-view.md))
- [ ] HA Matter device names pushed to Core when configured
- [ ] HACS diagnostics download is redacted (no secrets)
- [ ] Summary MQTT/HACS entities match Core health (no entity spam by default)
- [ ] **No run-probe / control / repair actions** in companion panel

---

## 8. HAOS add-on gates (deferred live validation)

Add-on packaging may exist before live HAOS validation is complete.

- [ ] Add-on version/image pin documented and matches Core release
- [ ] Ingress config structurally valid
- [ ] `host_network` + Ingress live validation completed **before** declaring HAOS-supported release
- [ ] Do **not** declare HAOS release-ready if live Ingress validation incomplete

---

## 9. Security and release notes

- [ ] No built-in authentication warning remains documented ([docs/security.md](docs/security.md))
- [ ] Core intended for trusted LAN or authenticated reverse proxy
- [ ] No secrets in committed examples, logs, or sample reports
- [ ] GitHub Release notes mention known limitations honestly
- [ ] Read probe behaviour and diagnostics-limited states explained if probes enabled in release notes

---

## Security acknowledgement

- [ ] I understand ThreadLens Core has **no built-in authentication** in pre-1.0 releases.
- [ ] I understand ThreadLens is read-only for Matter/Thread control in normal operation.
- [ ] I understand Matter read probes perform **read-only attribute checks** only when explicitly enabled.
- [ ] If Core is reachable beyond networks I trust, I have added suitable access control or accepted the risk.
- [ ] If using HTTPS, I understand TLS is not authentication.

---

## Final sign-off

- [ ] `./scripts/run-release-checks.sh` passed locally or equivalent CI jobs green
- [ ] Manual live validation completed for this release scope
- [ ] CHANGELOG and GitHub Release notes ready
- [ ] Tag `vX.Y.Z` created and publish workflow completed
