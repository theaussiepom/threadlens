#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${THREADLENS_BASE_URL:-http://127.0.0.1:8128}"

check() {
  local path="$1"
  echo "GET ${BASE_URL}${path}"
  curl --fail --silent --show-error "${BASE_URL}${path}" >/dev/null
}

check "/api/v1/health"
check "/api/v1/status"
check "/api/v1/version"
check "/api/v1/capabilities"
check "/api/v1/state"
check "/api/v1/events"
check "/api/v1/report.yaml"

echo "ThreadLens smoke checks passed against ${BASE_URL}"
