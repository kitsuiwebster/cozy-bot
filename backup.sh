#!/bin/bash
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/home/kitsui/backups/$DATE"

mkdir -p $BACKUP_DIR

# Copy JSON files directly from volumes (use the exact volume name from .env.dev)
VOLUME_NAME="cozy-bot-voice-data-dev"
docker run --rm -v $VOLUME_NAME:/data -v $BACKUP_DIR:/backup alpine sh -c 'find /data -name "*.json" -exec cp {} /backup/ \; || echo "No JSON files found"'

# Cleanup old backups (keep 30 days)
find /home/kitsui/backups -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;

echo "Backup completed in $BACKUP_DIR"