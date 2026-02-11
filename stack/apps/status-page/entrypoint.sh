#!/bin/sh
set -e

echo "Starting status-page entrypoint..."

# Create temporary directory
mkdir -p /tmp/nginx-html

# Copy all source files
cp -r /usr/share/nginx/html-src/* /tmp/nginx-html/

echo "✓ Static files copied"

# Start nginx
echo "Starting nginx..."
exec nginx -g 'daemon off;'
