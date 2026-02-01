#!/bin/bash
# Extract version from main.py or use git commit as fallback

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
MAIN_PATH="$SCRIPT_DIR/../../main.py"

# Try to get version from main.py
VERSION=$(grep -o "Version [0-9]\+\.[0-9]\+\.[0-9]\+" "$MAIN_PATH" | head -1 | cut -d' ' -f2 2>/dev/null)

# Fallback to git commit hash if no version found
if [ -z "$VERSION" ]; then
    VERSION=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
fi

echo "$VERSION"
