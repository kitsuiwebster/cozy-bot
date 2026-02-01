#!/bin/sh
set -e

echo "Starting status-page entrypoint..."

# Créer le dossier temporaire
mkdir -p /tmp/nginx-html

# Copier tous les fichiers sources
cp -r /usr/share/nginx/html-src/* /tmp/nginx-html/

# Remplacer le placeholder dans env-config.js
sed "s|__UPTIME_KUMA_API_KEY__|${UPTIME_KUMA_API_KEY}|g" \
    /tmp/nginx-html/env-config.template.js > /tmp/nginx-html/env-config.js

echo "✓ Configuration file generated"
echo "  API Key: ${UPTIME_KUMA_API_KEY:0:15}..."

# Vérifier que le fichier a été créé
if [ -f /tmp/nginx-html/env-config.js ]; then
    echo "✓ env-config.js exists"
    head -3 /tmp/nginx-html/env-config.js
else
    echo "✗ ERROR: env-config.js not created!"
    exit 1
fi

# Démarrer nginx
echo "Starting nginx..."
exec nginx -g 'daemon off;'
