#!/bin/bash
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/home/kitsui/backups/$DATE"

mkdir -p $BACKUP_DIR/dev $BACKUP_DIR/prod

# Backup dev environment
echo "Backing up dev environment..."
docker run --rm -v cozy-bot-voice-data-dev:/data -v $BACKUP_DIR/dev:/backup alpine sh -c 'find /data \( -name "*.json" -o -name "*.enc" \) -exec cp {} /backup/ \; || echo "No data files in dev"'

# Backup prod environment
echo "Backing up prod environment..."
docker run --rm -v cozy-bot-voice-data-prod:/data -v $BACKUP_DIR/prod:/backup alpine sh -c 'find /data \( -name "*.json" -o -name "*.enc" \) -exec cp {} /backup/ \; || echo "No data files in prod"'

# Cleanup old backups (keep 30 days)
find /home/kitsui/backups -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;

echo "Backup completed in $BACKUP_DIR"