#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-${REPO_ROOT}/stack/infra/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/stack/infra/.env.prod}"
RESTIC_ENV_FILE="${RESTIC_ENV_FILE:-/root/.restic-couchdb.env}"
SNAPSHOT="${SNAPSHOT:-latest}"
CONFIRMED=0

usage() {
  cat <<'EOF'
Usage:
  restore_couchdb_offsite.sh [--snapshot <id|latest>] --yes

Description:
  Restores CouchDB Docker volume data from a restic snapshot.
  WARNING: this replaces all data in the CouchDB volume.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --snapshot)
      SNAPSHOT="${2:-}"
      shift 2
      ;;
    --yes)
      CONFIRMED=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "${CONFIRMED}" -ne 1 ]]; then
  echo "ERROR: destructive restore blocked. Re-run with --yes." >&2
  exit 1
fi

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

WORK_DIR="$(mktemp -d)"
COUCHDB_STOPPED=0

cleanup() {
  if [[ "${COUCHDB_STOPPED}" -eq 1 ]]; then
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" start couchdb >/dev/null 2>&1 || true
  fi
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT INT TERM

echo "[1/6] Restoring snapshot ${SNAPSHOT} into temporary workspace..."
restic restore "${SNAPSHOT}" --target "${WORK_DIR}"

ARCHIVE="$(find "${WORK_DIR}" -type f -name 'couchdb-volume-*.tar.gz' | head -n 1)"
if [[ -z "${ARCHIVE}" ]]; then
  echo "ERROR: no CouchDB archive found in snapshot ${SNAPSHOT}" >&2
  exit 1
fi
ARCHIVE_REL="${ARCHIVE#${WORK_DIR}/}"

echo "[2/6] Stopping couchdb container..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" stop couchdb >/dev/null
COUCHDB_STOPPED=1

echo "[3/6] Cleaning target volume ${COUCHDB_VOLUME}..."
docker run --rm -v "${COUCHDB_VOLUME}:/to" alpine sh -c "find /to -mindepth 1 -delete"

echo "[4/6] Extracting restored archive into volume..."
docker run --rm \
  -v "${COUCHDB_VOLUME}:/to" \
  -v "${WORK_DIR}:/from:ro" \
  alpine sh -c "tar -xzf /from/${ARCHIVE_REL} -C /to"

echo "[5/6] Restarting couchdb container..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" start couchdb >/dev/null
COUCHDB_STOPPED=0

echo "[6/6] Restore completed."
echo "Tip: verify with 'make logs-db' and CouchDB /_up endpoint."
