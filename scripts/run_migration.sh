#!/bin/bash
# Wrapper pour charger .env et lancer la migration

set -a  # Export automatiquement toutes les variables
source "$(dirname "$0")/../dev/.env"
set +a

python3 "$(dirname "$0")/migrate_to_couchdb.py"
