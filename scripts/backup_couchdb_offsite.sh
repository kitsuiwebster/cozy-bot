#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-${REPO_ROOT}/stack/infra/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/stack/infra/.env.prod}"
RESTIC_ENV_FILE="${RESTIC_ENV_FILE:-/root/.restic-couchdb.env}"
TMP_DIR="${TMP_DIR:-/tmp}"

KEEP_DAILY="${KEEP_DAILY:-7}"
KEEP_WEEKLY="${KEEP_WEEKLY:-4}"
KEEP_MONTHLY="${KEEP_MONTHLY:-12}"
RUN_CHECK="${RUN_CHECK:-1}"
CHECK_SUBSET="${CHECK_SUBSET:-5%}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: missing ENV_FILE: ${ENV_FILE}" >&2
  exit 1
fi

if [[ ! -f "${RESTIC_ENV_FILE}" ]]; then
  echo "ERROR: missing RESTIC_ENV_FILE: ${RESTIC_ENV_FILE}" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found" >&2
  exit 1
fi

if ! command -v restic >/dev/null 2>&1; then
  echo "ERROR: restic not found" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
# shellcheck disable=SC1090
source "${RESTIC_ENV_FILE}"
set +a

: "${COUCHDB_VOLUME:?COUCHDB_VOLUME is required in ${ENV_FILE}}"
: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required in ${RESTIC_ENV_FILE}}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD is required in ${RESTIC_ENV_FILE}}"

mkdir -p "${TMP_DIR}"
TS="$(date +%F-%H%M%S)"
ARCHIVE="${TMP_DIR}/couchdb-volume-${COUCHDB_VOLUME}-${TS}.tar.gz"
COUCHDB_STOPPED=0

cleanup() {
  if [[ "${COUCHDB_STOPPED}" -eq 1 ]]; then
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" start couchdb >/dev/null 2>&1 || true
  fi
  [[ -f "${ARCHIVE}" ]] && rm -f "${ARCHIVE}"
}
trap cleanup EXIT INT TERM

echo "[1/6] Stopping couchdb container..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" stop couchdb >/dev/null
COUCHDB_STOPPED=1

echo "[2/6] Creating local archive from volume ${COUCHDB_VOLUME}..."
docker run --rm \
  -v "${COUCHDB_VOLUME}:/from:ro" \
  -v "${TMP_DIR}:/to" \
  alpine sh -c "tar -czf /to/$(basename "${ARCHIVE}") -C /from ."

echo "[3/6] Restarting couchdb container..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" start couchdb >/dev/null
COUCHDB_STOPPED=0

echo "[4/6] Sending encrypted backup to offsite repository..."
restic backup "${ARCHIVE}" --tag couchdb --tag cozy

echo "[5/6] Applying retention policy..."
restic forget \
  --keep-daily "${KEEP_DAILY}" \
  --keep-weekly "${KEEP_WEEKLY}" \
  --keep-monthly "${KEEP_MONTHLY}" \
  --prune

if [[ "${RUN_CHECK}" == "1" ]]; then
  echo "[6/6] Verifying repository integrity..."
  restic check --read-data-subset="${CHECK_SUBSET}"
else
  echo "[6/6] Integrity check skipped (RUN_CHECK=${RUN_CHECK})."
fi

echo "Backup completed successfully."
