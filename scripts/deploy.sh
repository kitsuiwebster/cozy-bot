#!/bin/bash
set -e

# Check argument
if [ -z "$1" ]; then
    echo "❌ Usage: $0 <dev|prod>"
    exit 1
fi

ENV=$1
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "❌ Invalid environment: $ENV. Use 'dev' or 'prod'"
    exit 1
fi

# Header
echo ""
echo "🚀 ${ENV^^} Deployment Starting..."
echo "================================================="
echo "╔═════════════════════════════════════════════════════════════════╗"
echo "║                                                                 ║"
echo "║   ██████╗ ██████╗ ███████╗██╗   ██╗██████╗  ██████╗ ████████╗   ║"
echo "║  ██╔════╝██╔═══██╗╚══███╔╝╚██╗ ██╔╝██╔══██╗██╔═══██╗╚══██╔══╝   ║"
echo "║  ██║     ██║   ██║  ███╔╝  ╚████╔╝ ██████╔╝██║   ██║   ██║      ║"
echo "║  ██║     ██║   ██║ ███╔╝    ╚██╔╝  ██╔══██╗██║   ██║   ██║      ║"
echo "║  ╚██████╗╚██████╔╝███████╗   ██║   ██████╔╝╚██████╔╝   ██║      ║"
echo "║   ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═════╝  ╚═════╝    ╚═╝      ║"
echo "║                                                                 ║"
echo "║                      Version 2.0.1                              ║"
echo "║            by @kitsuiwebster & @BubbleXGum                      ║"
echo "║                                                                 ║"
echo "╚═════════════════════════════════════════════════════════════════╝"
echo "================================================="

echo ""
# Change to environment directory
cd "$(dirname "$0")/../stack/infra" || exit 1
echo "📁 Working directory: $(pwd)"

# Environment validation
echo ""
echo "🔍 Validating environment..."
if [ ! -f ".env" ]; then
    echo "❌ .env not found!"
    echo "📝 Create .env in $ENV/ directory and configure it"
    exit 1
fi
echo "✅ .env found"

# Check Docker availability
echo ""
echo "🐳 Checking Docker availability..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found!"
    exit 1
fi
echo "✅ Docker is available"

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose not found!"
    exit 1
fi
echo "✅ Docker Compose is available"

# Load and display environment configuration
echo ""
echo "📋 Loading environment configuration..."
CONTAINER_NAME=$(grep "^CONTAINER_NAME=" .env | cut -d'=' -f2 | tr -d '"')
NETWORK_NAME=$(grep "^NETWORK_NAME=" .env | cut -d'=' -f2 | tr -d '"')
ENVIRONMENT=$(grep "^ENVIRONMENT=" .env | cut -d'=' -f2 | tr -d '"')
RESTART_POLICY=$(grep "^RESTART_POLICY=" .env | cut -d'=' -f2 | tr -d '"')
API_PORT=$(grep "^API_PORT=" .env | cut -d'=' -f2 | tr -d '"')
BOT_API_PORT=$(grep "^BOT_API_PORT=" .env | cut -d'=' -f2 | tr -d '"')

# Fallback to default if API_PORT not found
if [ -z "$API_PORT" ]; then
    API_PORT=8000
fi
if [ -z "$BOT_API_PORT" ]; then
    BOT_API_PORT=8002
fi

echo "👉 Container: ${CONTAINER_NAME}"
echo "👉 API Port: ${API_PORT}"
echo "👉 Live API Port: ${BOT_API_PORT}"

# Check if container is already running
echo ""
echo "🔍 Checking existing containers..."
EXISTING_CONTAINER=$(docker ps -q --filter name=${CONTAINER_NAME} 2>/dev/null || echo "")
if [ ! -z "$EXISTING_CONTAINER" ]; then
    echo "⚠️  Container ${CONTAINER_NAME} is currently running"
    echo "👉 Container ID: ${EXISTING_CONTAINER}"

    # Get current version
    VERSION=$(./../apps/bot/utils/deployment/get-version.sh 2>/dev/null || echo "latest")

    # Check Live API health before proceeding
    echo ""
    echo "🔍 Checking Live API availability..."
    set +e
    API_HEALTH=$(curl -s "http://localhost:${BOT_API_PORT}/api/live/bot/health" 2>/dev/null)
    API_EXIT_CODE=$?
    set -e

    if [ $API_EXIT_CODE -eq 0 ] && echo "$API_HEALTH" | grep -q '"status":"ok"'; then
        echo "✅ Live API is available"
        echo "📢 Sending pre-deployment notification to users..."
        NOTIFICATION_RESULT=$(curl -s -X POST "http://localhost:${BOT_API_PORT}/api/live/deployment/simple-notify" \
        -H "Content-Type: application/json" \
        -d "{\"version\":\"${VERSION}\",\"delay_seconds\":30}" 2>/dev/null)

        if [ $? -eq 0 ]; then
            USERS_FOUND=$(echo "$NOTIFICATION_RESULT" | grep -o '"users_found":[0-9]*' | cut -d':' -f2 2>/dev/null || echo "0")
            PROCEED_IMMEDIATELY=$(echo "$NOTIFICATION_RESULT" | grep -o '"proceed_immediately":[a-z]*' | cut -d':' -f2 2>/dev/null || echo "false")

            if [ "$PROCEED_IMMEDIATELY" = "true" ]; then
                echo "✅ No active users found, proceeding immediately"
            elif [ "$USERS_FOUND" -gt 0 ]; then
                echo "📢 Notification sent to ${USERS_FOUND} users, waiting 30s..."
                sleep 30
            fi

            # Finalize user sessions before shutdown
            echo ""
            echo "📊 Finalizing user sessions..."
            SESSION_FINALIZE_RESULT=$(curl -s -X POST "http://localhost:${BOT_API_PORT}/api/live/audio/finalize-sessions" 2>/dev/null)
            if echo "$SESSION_FINALIZE_RESULT" | grep -q '"success":true'; then
                SESSIONS_FINALIZED=$(echo "$SESSION_FINALIZE_RESULT" | grep -o '"sessions_finalized":[0-9]*' | cut -d':' -f2 2>/dev/null || echo "0")
                echo "📊 Finalized ${SESSIONS_FINALIZED} user sessions"
            fi

            # Save audio state before shutdown
            echo ""
            echo "🎵 Saving current audio state..."
            AUDIO_SAVE_RESULT=$(curl -s -X POST "http://localhost:${BOT_API_PORT}/api/live/audio/save-state" 2>/dev/null)
            if echo "$AUDIO_SAVE_RESULT" | grep -q '"success":true'; then
                SESSIONS_SAVED=$(echo "$AUDIO_SAVE_RESULT" | grep -o '"sessions_saved":[0-9]*' | cut -d':' -f2 2>/dev/null || echo "0")
                echo "💾 Saved ${SESSIONS_SAVED} audio sessions"
                echo "⏳ Waiting 3s for audio state to be written..."
                sleep 3
            else
                echo "⚠️ No audio sessions to save"
            fi
        fi
    else
        echo "⚠️ Live API unavailable - proceeding without notifications"
    fi
else
    echo "✅ No existing container found"
fi

# Stop only the bot container
echo ""
echo "🛑 Stopping only the bot container..."
docker compose --env-file .env stop discord-bot 2>/dev/null || true
REMOVED_CONTAINER=$(docker compose --env-file .env rm -f discord-bot 2>&1 || true)
if echo "$REMOVED_CONTAINER" | grep -q "discord-bot"; then
    echo "✅ Bot container stopped successfully"
else
    echo "ℹ️  No bot container to stop"
fi

# Clean up unused images
echo ""
echo "🧹 Cleaning old images..."
CLEANUP_RESULT=$(docker image prune -f 2>&1)
if echo "$CLEANUP_RESULT" | grep -q "Total reclaimed space"; then
    RECLAIMED_SPACE=$(echo "$CLEANUP_RESULT" | grep "Total reclaimed space" | awk '{print $4 $5}')
    echo "✅ Cleanup complete"
    echo "👉 Reclaimed space: ${RECLAIMED_SPACE}"
else
    echo "ℹ️  No images to clean"
fi

# Create necessary directories
echo ""
echo "📁 Creating required directories..."
mkdir -p /tmp/empty

# Fix data directory permissions
echo ""
echo "🔧 Setting up data directory permissions..."
mkdir -p data
sudo chown -R $USER:$USER data/ 2>/dev/null || chown -R $USER:$USER data/

# Build and start only bot container (don't touch other services)
echo ""
echo "🏗️  Building and starting bot container only..."
echo "👉 Building with configured mode"

echo ""
echo "🔍 Starting Docker build process (no-cache)..."
docker compose --env-file .env build --no-cache discord-bot 2>&1 | \
  stdbuf -oL -eL grep -v "transferring context\|transferring dockerfile\|naming to docker.io" | \
  stdbuf -oL -eL grep -E "^#|^\[|Built|Created|Started|Error|FAILED|COPY|RUN|exporting" | \
  stdbuf -oL -eL grep -v "CACHED.*apt-get\|CACHED.*WORKDIR\|CACHED.*requirements\|CACHED.*pip install" || true
BUILD_EXIT_CODE=${PIPESTATUS[0]}

if [ $BUILD_EXIT_CODE -eq 0 ]; then
    echo "✅ Image built successfully"
else
    echo "❌ Failed to build image (exit code: $BUILD_EXIT_CODE)"
    exit 1
fi

echo ""
echo "🚀 Starting new container..."
docker compose --env-file .env up -d --no-deps --force-recreate discord-bot

# Verify container is running
echo ""
echo "🔍 Verifying container status..."
echo "⏳ Waiting 8s for bot to fully start and process audio restoration..."
sleep 8
CONTAINER_STATUS=$(docker ps --filter name=${CONTAINER_NAME} --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | tail -n +2)
if [ ! -z "$CONTAINER_STATUS" ]; then
    echo "✅ Container is running"
    echo "👉 Status: $CONTAINER_STATUS"

    # Restore user sessions after deployment
    echo ""
    echo "👉 Restoring user sessions..."
    sleep 2  # Give the bot a moment to fully initialize
    set +e  # Don't exit on curl error
    SESSION_RESTORE_RESULT=$(curl -s -X POST "http://localhost:${BOT_API_PORT}/api/live/audio/restore-sessions" 2>/dev/null || echo '{}')
    set -e  # Re-enable exit on error
    if echo "$SESSION_RESTORE_RESULT" | grep -q '"success":true'; then
        SESSIONS_RESTORED=$(echo "$SESSION_RESTORE_RESULT" | grep -o '"sessions_restored":[0-9]*' | cut -d':' -f2 2>/dev/null || echo "0")
        echo "👉 Restored ${SESSIONS_RESTORED} user sessions"
    else
        echo "⚠️ Could not restore user sessions (API might not be ready yet)"
    fi

    # Users have been notified and everything is restored
    echo ""
    echo "✅ Deployment complete! Users notified, audio restored, sessions restarted."
else
    echo "❌ Container failed to start"
    echo "🔍 Checking bot logs for errors..."
    docker compose --env-file .env logs discord-bot
    exit 1
fi

# Final summary
echo ""
echo "🎉 ${ENV^^} Deployment Complete!"
echo "================================================="
echo ""
echo "📋 Container: ${CONTAINER_NAME}"
echo "🔗 Network: ${NETWORK_NAME}"
echo "💻 Environment: ${ENVIRONMENT}"
echo "📝 Useful commands:"
echo "👉 View logs: make logs"
echo "👉 Stop container: make stop"
echo "👉 Check status: make status"
echo "✅ Deployment completed!"
