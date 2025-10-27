#!/bin/bash
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/home/kitsui/backups/$DATE"

mkdir -p $BACKUP_DIR

# Copy JSON files directly from volumes
docker run --rm -v cozy-bot-voice-data-dev:/data -v $BACKUP_DIR:/backup alpine cp /data/voice_time_data.json /backup/ 2>/dev/null || echo "voice_time_data.json not found"

# Copy any other JSON files if they exist
docker run --rm -v cozy-bot-voice-data-dev:/data -v $BACKUP_DIR:/backup alpine sh -c 'find /data -name "*.json" -exec cp {} /backup/ \;' 2>/dev/null

# Cleanup old backups (keep 30 days)
find /home/kitsui/backups -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;

echo "Backup completed in $BACKUP_DIR"