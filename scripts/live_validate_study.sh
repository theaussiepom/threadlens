#!/usr/bin/env bash
# Study Pi live validation helper — Pass 17 mDNS/TREL startup discovery + Pass 19 OTBR parser.
#
# Intended to run ON the Study Pi from a ThreadLens core repo checkout.
# Does not use SSH. Does not mutate Thread/Matter/OTBR state.
#
# Usage:
#   ./scripts/live_validate_study.sh                 # validate only (curl checks)
#   ./scripts/live_validate_study.sh --redeploy      # build + recreate container, then validate
#   ./scripts/live_validate_study.sh --capture-otbr  # save OTBR fixtures for parser work
#   OPT_IN_DB_RESET=1 ./scripts/live_validate_study.sh --redeploy  # optional DB reset (destructive-ish)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

API_BASE="${THREADLENS_API_BASE:-http://192.168.100.4:8128}"
COMPOSE_FILE="${THREADLENS_COMPOSE_FILE:-docker-compose.study-both.example.yml}"
IMAGE_TAG="${THREADLENS_IMAGE_TAG:-ghcr.io/theaussiepom/threadlens:0.1.0}"
DATA_DIR="${THREADLENS_DATA_DIR:-./data/study}"
CAPTURE_DIR="${THREADLENS_CAPTURE_DIR:-./live-captures}"

REDEPLOY=0
CAPTURE_OTBR=0
for arg in "$@"; do
  case "${arg}" in
    --redeploy) REDEPLOY=1 ;;
    --capture-otbr) CAPTURE_OTBR=1 ;;
    -h|--help)
      sed -n '1,20p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      exit 2
      ;;
  esac
done

section() {
  echo
  echo "=== $* ==="
}

if [[ "${REDEPLOY}" -eq 1 ]]; then
  section "Build Docker image"
  docker build -t "${IMAGE_TAG}" .

  if [[ "${OPT_IN_DB_RESET:-0}" == "1" ]]; then
    section "Optional DB reset (opt-in)"
    echo "Stopping compose stack before moving aside SQLite DB..."
    docker compose -f "${COMPOSE_FILE}" down
    DB_PATH="${DATA_DIR}/threadlens.db"
    if [[ -f "${DB_PATH}" ]]; then
      mv "${DB_PATH}" "${DB_PATH}.pre-pass17"
      echo "Moved ${DB_PATH} -> ${DB_PATH}.pre-pass17"
    else
      echo "No DB at ${DB_PATH}; nothing to move."
    fi
  fi

  section "Recreate Study container"
  echo "Using compose file: ${COMPOSE_FILE}"
  echo "Alternative generic host-network compose:"
  echo "  docker compose -f docker-compose.host-network.example.yml up -d --force-recreate"
  docker compose -f "${COMPOSE_FILE}" up -d --force-recreate
  echo "Waiting 10s for collectors to start..."
  sleep 10
fi

if [[ "${CAPTURE_OTBR}" -eq 1 ]]; then
  section "Capture OTBR live responses (Pass 19 fixtures)"
  mkdir -p "${CAPTURE_DIR}"
  curl -s "${API_BASE}/api/v1/otbrs" > "${CAPTURE_DIR}/threadlens-otbrs.json"
  curl -s http://192.168.100.4:8081/api/node > "${CAPTURE_DIR}/study-api-node.json"
  curl -s http://192.168.100.7:8081/api/node > "${CAPTURE_DIR}/lounge-api-node.json"
  curl -s http://192.168.100.4:8081/api/devices > "${CAPTURE_DIR}/study-api-devices.json"
  curl -s http://192.168.100.7:8081/api/devices > "${CAPTURE_DIR}/lounge-api-devices.json"
  echo "Saved captures under ${CAPTURE_DIR}/"
fi

section "Pass 17 / general validation curls"
echo "GET ${API_BASE}/api/v1/health"
curl -s "${API_BASE}/api/v1/health" | jq .

echo "GET ${API_BASE}/api/v1/status (mdns collector)"
curl -s "${API_BASE}/api/v1/status" | jq '.collectors.mdns'

echo "GET ${API_BASE}/api/v1/mdns/services count"
curl -s "${API_BASE}/api/v1/mdns/services" | jq '.count'

echo "GET ${API_BASE}/api/v1/trel/services count"
curl -s "${API_BASE}/api/v1/trel/services" | jq '.count'

echo "GET ${API_BASE}/api/v1/events?window=24h (first 5)"
curl -s "${API_BASE}/api/v1/events?window=24h" | jq '.events[:5], .count'

section "Recent container logs (mDNS listener errors)"
docker logs threadlens --since 5m 2>&1 | tail -n 80 || echo "Could not read docker logs for container 'threadlens'."

section "Pass 19 OTBR validation curls"
echo "GET ${API_BASE}/api/v1/otbrs"
curl -s "${API_BASE}/api/v1/otbrs" | jq .

echo "GET ${API_BASE}/api/v1/networks"
curl -s "${API_BASE}/api/v1/networks" | jq .

echo "GET ${API_BASE}/api/v1/report.yaml (first 80 lines)"
curl -s "${API_BASE}/api/v1/report.yaml" | sed -n '1,80p'

section "Expected results (manual check)"
cat <<'EOF'
Pass 17 (mDNS/TREL startup discovery):
  - /api/v1/mdns/services count > 0
  - /api/v1/trel/services count > 0
  - collectors.mdns.observation_degraded == false
  - docker logs: no AttributeError from _AsyncMdnsListener
  - health: mdns_service_flapping_degraded NOT present from startup discovery alone
    (if still present with old DB events, retry with OPT_IN_DB_RESET=1)

Pass 19 (OTBR parser):
  - Study OTBR role == "leader" when Thread stack is active
  - Lounge OTBR role == "router" when Thread stack is active
  - network_name / channel / ext_pan_id / pan_id populated when raw API provides them
  - /api/v1/networks shows primary network with 2 source OTBRs when both share ext_pan_id
  - No POST/mutating OTBR calls are made by ThreadLens
EOF

echo
echo "Live validation helper finished."
