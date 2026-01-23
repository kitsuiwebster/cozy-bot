#!/bin/bash
# Sync dev → prod (simple)

cd /workspace

echo "📦 Backup prod..."
cp -r prod prod_backup

echo "🔄 Sync dev → prod..."
rsync -av --delete \
  --exclude='.env' \
  --exclude='docker-compose.yml' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='data/' \
  --exclude='logs/' \
  dev/ prod/

echo "✅ Done!"
echo "📦 Backup: prod_backup"
echo ""
echo "Rollback si besoin: rm -rf prod && mv prod_backup prod"
