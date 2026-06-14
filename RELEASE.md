# Release process

Version target: `0.1.2`

ThreadLens container images are published to GHCR by GitHub Actions — not by manual `docker push`.

## Pre-merge checklist

- [ ] CI green on the release PR (`test` + `docker` jobs)
- [ ] `ruff check .` passes locally
- [ ] `ruff format --check .` passes locally
- [ ] `pytest -q` passes locally
- [ ] Version is `0.1.2` in `pyproject.toml`, `threadlens/__init__.py`, and `/api/v1/version`
- [ ] No live MQTT secrets committed
- [ ] Committed example configs use placeholders only (`username`/`password: null`, generic LAN IPs)

## Publish (after merge to `main`)

1. Merge the release PR via squash merge (branch protection requires green CI).
2. Check out `main` and tag:

   ```bash
   git checkout main
   git pull
   git tag v0.1.2
   git push origin v0.1.2
   ```

3. GitHub Actions workflow `.github/workflows/publish-container.yml` publishes:

   - `ghcr.io/theaussiepom/threadlens:0.1.2`
   - `ghcr.io/theaussiepom/threadlens:v0.1.2`
   - `ghcr.io/theaussiepom/threadlens:latest`

4. Create a GitHub Release from tag `v0.1.2` using notes from `CHANGELOG.md`.
5. Ensure the GHCR package visibility is **Public** (Settings → Packages → threadlens).

## Branch protection (main)

If not applied automatically, configure in GitHub → **Settings** → **Branches** → **Add branch protection rule** for `main`:

1. Require a pull request before merging
2. Require approvals: 0 or 1 (as you prefer)
3. Require status checks to pass: `test`, `docker`
4. Require branches to be up to date before merging
5. Do not allow bypassing the above settings
6. Restrict force pushes (disable force push)
7. Restrict deletions
8. Allow squash merge only (disable merge commits and rebase if desired)

Merging to `main` should be blocked until CI is green on the PR.

## Deploy published image

Pin a specific tag — do not rely on floating `latest` in production:

```bash
docker pull ghcr.io/theaussiepom/threadlens:0.1.2
docker compose -f docker-compose.host-network.example.yml up -d
```

Do not use manual `docker build` + `docker push` for releases. Local image tags (`:local`) are for development only.
