#!/bin/sh
set -e

SEED_DB="/seed/kuma.db"
SEED_WAL="/seed/kuma.db-wal"
SEED_SHM="/seed/kuma.db-shm"
DATA_DB="/app/data/kuma.db"
DATA_WAL="/app/data/kuma.db-wal"
DATA_SHM="/app/data/kuma.db-shm"

if [ -f "$SEED_DB" ] && [ ! -f "$DATA_DB" ]; then
  echo "🌱 Kuma seed DB found. Initializing /app/data/kuma.db..."
  cp "$SEED_DB" "$DATA_DB"
  if [ -f "$SEED_WAL" ]; then
    cp "$SEED_WAL" "$DATA_WAL"
  fi
  if [ -f "$SEED_SHM" ]; then
    cp "$SEED_SHM" "$DATA_SHM"
  fi
else
  if [ ! -f "$SEED_DB" ]; then
    echo "ℹ️  No seed DB at $SEED_DB (first-run setup required)."
  else
    echo "ℹ️  Existing Kuma DB found; seed not applied."
  fi
fi

if command -v dumb-init >/dev/null 2>&1; then
  exec dumb-init -- node server/server.js
fi

exec node server/server.js
