#!/usr/bin/env bash
# Run automated pre-release checks for ThreadLens.
# Manual gates remain in RELEASE_CHECKLIST.md.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

section() {
  echo ""
  echo "==> $1"
}

warn() {
  echo "WARNING: $1" >&2
}

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

section "Version alignment"
PYPROJECT_VERSION="$(python3 - <<'PY'
import pathlib
import re
text = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
print(match.group(1) if match else "")
PY
)"
INIT_VERSION="$(python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("threadlens_init", "threadlens/__init__.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.__version__)
PY
)"
WEB_VERSION="$(python3 - <<'PY'
import json
print(json.load(open("web/package.json", encoding="utf-8"))["version"])
PY
)"
echo "  pyproject.toml:     ${PYPROJECT_VERSION}"
echo "  threadlens/__init__: ${INIT_VERSION}"
echo "  web/package.json:   ${WEB_VERSION}"
if [[ -z "${PYPROJECT_VERSION}" || -z "${INIT_VERSION}" || -z "${WEB_VERSION}" ]]; then
  fail "Could not read one or more version fields"
fi
if [[ "${PYPROJECT_VERSION}" != "${INIT_VERSION}" || "${PYPROJECT_VERSION}" != "${WEB_VERSION}" ]]; then
  fail "Version mismatch across pyproject.toml, threadlens/__init__.py, and web/package.json"
fi
echo "  Version alignment OK (${PYPROJECT_VERSION})"

section "Core lint (ruff)"
ruff check .
ruff format --check .

section "Core tests (pytest)"
pytest -q

section "Example config guardrails"
if grep -RE '^[^#[:space:]]*mode:[[:space:]]*(conservative|standard|diagnostic)' examples/ 2>/dev/null; then
  fail "Public example config must not enable probe modes; keep probes commented or mode: disabled"
fi
echo "  Example probe config OK (disabled/commented)"

section "Forbidden overclaiming wording"
FORBIDDEN_FILES="$(grep -rIE 'command failed|open/close failed|blind command failed' threadlens web/src docs \
  --exclude='matter-command-diagnostics-future.md' \
  --exclude='test_*' 2>/dev/null || true)"
if [[ -n "${FORBIDDEN_FILES}" ]]; then
  echo "${FORBIDDEN_FILES}"
  fail "Found forbidden causal/command-failure wording in product sources or docs"
fi
echo "  Wording guardrails OK"

section "Web dashboard checks"
if [[ ! -d web/node_modules ]]; then
  warn "web/node_modules missing — run: npm --prefix web ci"
  npm --prefix web ci
fi
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run build
if [[ ! -f static/index.html || ! -d static/assets ]]; then
  fail "Built dashboard assets missing under static/"
fi
echo "  Web build OK"

section "Docker image (optional)"
if command -v docker >/dev/null 2>&1; then
  docker build -t threadlens:release-check .
  echo "  Docker build OK"
else
  warn "Docker not available; skipping local docker build (CI docker job still required before release)"
fi

echo ""
echo "All automated release checks passed."
echo "Complete manual gates in RELEASE_CHECKLIST.md before tagging a release."
