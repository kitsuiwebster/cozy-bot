#!/bin/sh
set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ENV_FILE="$SCRIPT_DIR/../.env"
VIEWS_FILE="$SCRIPT_DIR/views.json"

if [ -f "$ENV_FILE" ]; then
    set -a
    . "$ENV_FILE"
    set +a
else
    echo "❌ .env not found at $ENV_FILE"
    exit 1
fi

if [ ! -f "$VIEWS_FILE" ]; then
    echo "❌ Views file not found at $VIEWS_FILE"
    exit 1
fi

COUCHDB_PORT="${COUCHDB_PORT:-5984}"
COUCHDB_USER="${COUCHDB_USER:-admin}"
COUCHDB_PASSWORD="${COUCHDB_PASSWORD:-}"

if [ -z "$COUCHDB_PASSWORD" ]; then
    echo "❌ COUCHDB_PASSWORD is missing"
    exit 1
fi

DB_NAME="cozy_bot_data"
URL="http://localhost:${COUCHDB_PORT}/${DB_NAME}/_design/views"

echo "🔧 Seeding CouchDB views in ${DB_NAME}..."
HTTP_CODE=$(curl -sS -o /tmp/couchdb_views_out.json -w "%{http_code}" \
    -u "${COUCHDB_USER}:${COUCHDB_PASSWORD}" \
    -H "Content-Type: application/json" \
    -X PUT "$URL" \
    --data-binary "@${VIEWS_FILE}")

if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "202" ]; then
    echo "✅ Views created"
    VIEWS_OK=1
fi

if [ "$HTTP_CODE" = "409" ]; then
    echo "ℹ️  Views already exist"
    VIEWS_OK=1
fi

if [ "${VIEWS_OK:-0}" -ne 1 ]; then
    echo "❌ Failed to seed views (HTTP $HTTP_CODE)"
    cat /tmp/couchdb_views_out.json || true
    exit 1
fi

echo "📦 Seeding CouchDB data from stack/data..."
python3 "$SCRIPT_DIR/../../scripts/migrate_to_couchdb.py"
