#!/bin/bash
# Sync prod → dev (simple)

cd /workspace

echo "📦 Backup dev..."
cp -r dev dev_backup

echo "🔄 Sync prod → dev..."
rsync -av --delete \
  --exclude='.env' \
  --exclude='docker-compose.yml' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='data/' \
  --exclude='logs/' \
  prod/ dev/

echo "✅ Done!"
echo "📦 Backup: dev_backup"
echo ""
echo "Rollback si besoin: rm -rf dev && mv dev_backup dev"
