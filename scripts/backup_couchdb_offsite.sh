#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

ENV_FILE="${ENV_FILE:-${REPO_ROOT}/stack/infra/.env}"
RESTIC_ENV_FILE="${RESTIC_ENV_FILE:-/root/.restic-couchdb.env}"
TMP_DIR="${TMP_DIR:-/tmp}"

KEEP_DAILY="${KEEP_DAILY:-7}"
KEEP_WEEKLY="${KEEP_WEEKLY:-4}"
KEEP_MONTHLY="${KEEP_MONTHLY:-12}"
RUN_CHECK="${RUN_CHECK:-1}"
CHECK_SUBSET="${CHECK_SUBSET:-5%}"
PAGE_SIZE="${PAGE_SIZE:-1000}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: missing ENV_FILE: ${ENV_FILE}" >&2
  exit 1
fi

if [[ ! -f "${RESTIC_ENV_FILE}" ]]; then
  echo "ERROR: missing RESTIC_ENV_FILE: ${RESTIC_ENV_FILE}" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl not found" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq not found" >&2
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

: "${COUCHDB_USER:?COUCHDB_USER is required in ${ENV_FILE}}"
: "${COUCHDB_PASSWORD:?COUCHDB_PASSWORD is required in ${ENV_FILE}}"
: "${COUCHDB_PORT:?COUCHDB_PORT is required in ${ENV_FILE}}"
: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required in ${RESTIC_ENV_FILE}}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD is required in ${RESTIC_ENV_FILE}}"

COUCHDB_BACKUP_URL="${COUCHDB_BACKUP_URL:-http://127.0.0.1:${COUCHDB_PORT}}"
AUTH=(--user "${COUCHDB_USER}:${COUCHDB_PASSWORD}")

mkdir -p "${TMP_DIR}"
TS="$(date +%F-%H%M%S)"
WORK_DIR="$(mktemp -d "${TMP_DIR}/couchdb-logical-${TS}-XXXX")"
EXPORT_DIR="${WORK_DIR}/export"
ARCHIVE="${TMP_DIR}/couchdb-logical-${TS}.tar.gz"

cleanup() {
  rm -rf "${WORK_DIR}"
  [[ -f "${ARCHIVE}" ]] && rm -f "${ARCHIVE}"
}
trap cleanup EXIT INT TERM

mkdir -p "${EXPORT_DIR}/dbs"

urlencode() {
  jq -rn --arg v "$1" '$v|@uri'
}

echo "[1/6] Checking CouchDB availability (no downtime backup)..."
curl -fsS "${AUTH[@]}" "${COUCHDB_BACKUP_URL}/_up" >/dev/null

echo "[2/6] Listing databases..."
DBS_JSON="${EXPORT_DIR}/db_list.json"
curl -fsS "${AUTH[@]}" "${COUCHDB_BACKUP_URL}/_all_dbs" > "${DBS_JSON}"

jq -n \
  --arg created_at "$(date -Iseconds)" \
  --arg couchdb_url "${COUCHDB_BACKUP_URL}" \
  --argjson databases "$(cat "${DBS_JSON}")" \
  '{created_at: $created_at, couchdb_url: $couchdb_url, databases: $databases}' \
  > "${EXPORT_DIR}/manifest.json"

echo "[3/6] Exporting documents for each database..."
while IFS= read -r db; do
  db_uri="$(urlencode "${db}")"
  out_file="${EXPORT_DIR}/dbs/${db_uri}.ndjson"
  : > "${out_file}"

  last_id=""
  while :; do
    query="include_docs=true&limit=${PAGE_SIZE}"
    if [[ -n "${last_id}" ]]; then
      startkey="$(jq -rn --arg v "${last_id}" '$v|tojson|@uri')"
      startkey_docid="$(urlencode "${last_id}")"
      query+="&startkey=${startkey}&startkey_docid=${startkey_docid}&skip=1"
    fi

    resp_file="${WORK_DIR}/resp.json"
    curl -fsS "${AUTH[@]}" "${COUCHDB_BACKUP_URL}/${db_uri}/_all_docs?${query}" > "${resp_file}"

    rows_len="$(jq '.rows | length' "${resp_file}")"
    if [[ "${rows_len}" -eq 0 ]]; then
      break
    fi

    jq -c '.rows[].doc' "${resp_file}" >> "${out_file}"
    last_id="$(jq -r '.rows[-1].id' "${resp_file}")"

    if [[ "${rows_len}" -lt "${PAGE_SIZE}" ]]; then
      break
    fi
  done

  gzip -f "${out_file}"
  echo "  - exported ${db}"
done < <(jq -r '.[]' "${DBS_JSON}")

echo "[4/6] Creating archive..."
tar -czf "${ARCHIVE}" -C "${EXPORT_DIR}" .

echo "[5/6] Sending encrypted backup to offsite repository..."
restic backup "${ARCHIVE}" --tag couchdb --tag cozy --tag logical

echo "[6/6] Applying retention policy..."
restic forget \
  --keep-daily "${KEEP_DAILY}" \
  --keep-weekly "${KEEP_WEEKLY}" \
  --keep-monthly "${KEEP_MONTHLY}" \
  --prune

if [[ "${RUN_CHECK}" == "1" ]]; then
  restic check --read-data-subset="${CHECK_SUBSET}"
fi

echo "Backup completed successfully (no CouchDB stop/start)."
