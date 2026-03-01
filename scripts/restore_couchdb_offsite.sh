#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

ENV_FILE="${ENV_FILE:-${REPO_ROOT}/stack/infra/.env}"
RESTIC_ENV_FILE="${RESTIC_ENV_FILE:-/root/.restic-couchdb.env}"
SNAPSHOT="${SNAPSHOT:-latest}"
BULK_SIZE="${BULK_SIZE:-500}"
CONFIRMED=0

usage() {
  cat <<'EOF_USAGE'
Usage:
  restore_couchdb_offsite.sh [--snapshot <id|latest>] --yes

Description:
  Restores CouchDB from a logical restic backup.
  WARNING: this drops and recreates databases from the snapshot.
EOF_USAGE
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

for cmd in curl jq restic tar gzip; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "ERROR: ${cmd} not found" >&2
    exit 1
  fi
done

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
# shellcheck disable=SC1090
source "${RESTIC_ENV_FILE}"
set +a

: "${COUCHDB_USER:?COUCHDB_USER is required in ${ENV_FILE}}"
: "${COUCHDB_PASSWORD:?COUCHDB_PASSWORD is required in ${ENV_FILE}}"
: "${COUCHDB_PORT:?COUCHDB_PORT is required in ${ENV_FILE}}"
: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required in ${RESTIC_ENV_FILE}}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD is required in ${RESTIC_ENV_FILE}}"

COUCHDB_BACKUP_URL="${COUCHDB_BACKUP_URL:-http://127.0.0.1:${COUCHDB_PORT}}"
AUTH=(--user "${COUCHDB_USER}:${COUCHDB_PASSWORD}")
WORK_DIR="$(mktemp -d)"
EXTRACT_DIR="${WORK_DIR}/extract"

cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT INT TERM

urlencode() {
  jq -rn --arg v "$1" '$v|@uri'
}

api_status() {
  local method="$1"
  local url="$2"
  local data_file="${3:-}"
  if [[ -n "${data_file}" ]]; then
    curl -sS -o /dev/null -w "%{http_code}" "${AUTH[@]}" -H "Content-Type: application/json" -X "${method}" "${url}" --data-binary "@${data_file}"
  else
    curl -sS -o /dev/null -w "%{http_code}" "${AUTH[@]}" -H "Content-Type: application/json" -X "${method}" "${url}"
  fi
}

echo "[1/6] Checking CouchDB availability..."
curl -fsS "${AUTH[@]}" "${COUCHDB_BACKUP_URL}/_up" >/dev/null

echo "[2/6] Restoring snapshot ${SNAPSHOT} into workspace..."
restic restore "${SNAPSHOT}" --target "${WORK_DIR}"

ARCHIVE="$(find "${WORK_DIR}" -type f -name 'couchdb-logical-*.tar.gz' | head -n 1)"
if [[ -z "${ARCHIVE}" ]]; then
  echo "ERROR: no logical backup archive found in snapshot ${SNAPSHOT}" >&2
  exit 1
fi

echo "[3/6] Extracting archive..."
mkdir -p "${EXTRACT_DIR}"
tar -xzf "${ARCHIVE}" -C "${EXTRACT_DIR}"

MANIFEST="${EXTRACT_DIR}/manifest.json"
if [[ ! -f "${MANIFEST}" ]]; then
  echo "ERROR: manifest.json missing in backup archive" >&2
  exit 1
fi

echo "[4/6] Recreating databases from backup..."
while IFS= read -r db; do
  db_uri="$(urlencode "${db}")"
  db_url="${COUCHDB_BACKUP_URL}/${db_uri}"

  del_code="$(api_status DELETE "${db_url}")"
  if [[ "${del_code}" != "200" && "${del_code}" != "404" ]]; then
    echo "ERROR: failed to drop db ${db} (HTTP ${del_code})" >&2
    exit 1
  fi

  put_code="$(api_status PUT "${db_url}")"
  if [[ "${put_code}" != "201" && "${put_code}" != "202" && "${put_code}" != "412" ]]; then
    echo "ERROR: failed to create db ${db} (HTTP ${put_code})" >&2
    exit 1
  fi

  dump_file="${EXTRACT_DIR}/dbs/${db_uri}.ndjson.gz"
  if [[ ! -f "${dump_file}" ]]; then
    echo "  - restored ${db} (empty)"
    continue
  fi

  chunk_file="${WORK_DIR}/chunk.ndjson"
  payload_file="${WORK_DIR}/bulk.json"
  : > "${chunk_file}"
  count=0

  flush_chunk() {
    if [[ "${count}" -eq 0 ]]; then
      return
    fi

    jq -s '{docs: .}' "${chunk_file}" > "${payload_file}"
    code="$(api_status POST "${db_url}/_bulk_docs" "${payload_file}")"
    if [[ "${code}" != "201" && "${code}" != "202" ]]; then
      echo "ERROR: bulk import failed for ${db} (HTTP ${code})" >&2
      exit 1
    fi

    : > "${chunk_file}"
    count=0
  }

  while IFS= read -r doc; do
    if [[ -z "${doc}" ]]; then
      continue
    fi
    echo "${doc}" | jq -c 'del(._rev)' >> "${chunk_file}"
    count=$((count + 1))
    if [[ "${count}" -ge "${BULK_SIZE}" ]]; then
      flush_chunk
    fi
  done < <(gzip -dc "${dump_file}")

  flush_chunk
  echo "  - restored ${db}"
done < <(jq -r '.databases[]' "${MANIFEST}")

echo "[5/6] Restore finished."

echo "[6/6] Post-check:"
echo "- run: make logs-db"
echo "- check: ${COUCHDB_BACKUP_URL}/_up"
