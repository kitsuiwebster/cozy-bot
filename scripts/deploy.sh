#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check argument
if [ -z "$1" ]; then
    echo -e "${RED}❌ Usage: $0 <dev|prod>${NC}"
    exit 1
fi

ENV=$1
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo -e "${RED}❌ Invalid environment: $ENV. Use 'dev' or 'prod'${NC}"
    exit 1
fi

# Header
echo -e "${CYAN}🚀 ${ENV^^} Deployment Starting...${NC}"
echo "================================================="

# Change to environment directory
cd "$(dirname "$0")/../$ENV" || exit 1
echo -e "${BLUE}📁 Working directory: $(pwd)${NC}"

# Environment validation
echo -e "${BLUE}🔍 Validating environment...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env not found!${NC}"
    echo -e "${YELLOW}📝 Create .env in $ENV/ directory and configure it${NC}"
    exit 1
fi
echo -e "${GREEN}✅ .env found${NC}"

# Check Docker availability
echo -e "${BLUE}🐳 Checking Docker availability...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker is available${NC}"

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker Compose is available${NC}"

# Load and display environment configuration
echo -e "${BLUE}📋 Loading environment configuration...${NC}"
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

echo -e "${PURPLE}👉 Container: ${CONTAINER_NAME}${NC}"
echo -e "${PURPLE}👉 API Port: ${API_PORT}${NC}"
echo -e "${PURPLE}👉 Live API Port: ${BOT_API_PORT}${NC}"

# Check if container is already running
echo -e "${BLUE}🔍 Checking existing containers...${NC}"
EXISTING_CONTAINER=$(docker ps -q --filter name=${CONTAINER_NAME} 2>/dev/null || echo "")
if [ ! -z "$EXISTING_CONTAINER" ]; then
    echo -e "${YELLOW}⚠️  Container ${CONTAINER_NAME} is currently running${NC}"
    echo -e "${PURPLE}👉 Container ID: ${EXISTING_CONTAINER}${NC}"

    # Get current version
    VERSION=$(./utils/deployment/get-version.sh 2>/dev/null || echo "latest")

    # Check Live API health before proceeding
    echo -e "${BLUE}🔍 Checking Live API availability...${NC}"
    set +e
    API_HEALTH=$(curl -s "http://localhost:${BOT_API_PORT}/api/live/bot/health" 2>/dev/null)
    API_EXIT_CODE=$?
    set -e

    if [ $API_EXIT_CODE -eq 0 ] && echo "$API_HEALTH" | grep -q '"status":"ok"'; then
        echo -e "${GREEN}✅ Live API is available${NC}"
        echo -e "${BLUE}📢 Sending pre-deployment notification to users...${NC}"
        NOTIFICATION_RESULT=$(curl -s -X POST "http://localhost:${BOT_API_PORT}/api/live/deployment/simple-notify" \
        -H "Content-Type: application/json" \
        -d "{\"version\":\"${VERSION}\",\"delay_seconds\":30}" 2>/dev/null)

        if [ $? -eq 0 ]; then
            USERS_FOUND=$(echo "$NOTIFICATION_RESULT" | grep -o '"users_found":[0-9]*' | cut -d':' -f2 2>/dev/null || echo "0")
            PROCEED_IMMEDIATELY=$(echo "$NOTIFICATION_RESULT" | grep -o '"proceed_immediately":[a-z]*' | cut -d':' -f2 2>/dev/null || echo "false")

            if [ "$PROCEED_IMMEDIATELY" = "true" ]; then
                echo -e "${GREEN}✅ No active users found, proceeding immediately${NC}"
            elif [ "$USERS_FOUND" -gt 0 ]; then
                echo -e "${GREEN}📢 Notification sent to ${USERS_FOUND} users, waiting 30s...${NC}"
                sleep 30
            fi

            # Finalize user sessions before shutdown
            echo -e "${BLUE}📊 Finalizing user sessions...${NC}"
            SESSION_FINALIZE_RESULT=$(curl -s -X POST "http://localhost:${BOT_API_PORT}/api/live/audio/finalize-sessions" 2>/dev/null)
            if echo "$SESSION_FINALIZE_RESULT" | grep -q '"success":true'; then
                SESSIONS_FINALIZED=$(echo "$SESSION_FINALIZE_RESULT" | grep -o '"sessions_finalized":[0-9]*' | cut -d':' -f2 2>/dev/null || echo "0")
                echo -e "${GREEN}📊 Finalized ${SESSIONS_FINALIZED} user sessions${NC}"
            fi

            # Save audio state before shutdown
            echo -e "${BLUE}🎵 Saving current audio state...${NC}"
            AUDIO_SAVE_RESULT=$(curl -s -X POST "http://localhost:${BOT_API_PORT}/api/live/audio/save-state" 2>/dev/null)
            if echo "$AUDIO_SAVE_RESULT" | grep -q '"success":true'; then
                SESSIONS_SAVED=$(echo "$AUDIO_SAVE_RESULT" | grep -o '"sessions_saved":[0-9]*' | cut -d':' -f2 2>/dev/null || echo "0")
                echo -e "${GREEN}💾 Saved ${SESSIONS_SAVED} audio sessions${NC}"
                echo -e "${BLUE}⏳ Waiting 3s for audio state to be written...${NC}"
                sleep 3
            else
                echo -e "${YELLOW}⚠️ No audio sessions to save${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}⚠️ API unavailable - proceeding without notifications${NC}"
    fi
else
    echo -e "${GREEN}✅ No existing container found${NC}"
fi

# Stop only the bot container (keep Kuma and CouchDB running)
echo -e "${BLUE}🛑 Stopping only the bot container (Kuma & CouchDB stay up)...${NC}"
docker compose --env-file .env stop discord-bot 2>/dev/null || true
REMOVED_CONTAINER=$(docker compose --env-file .env rm -f discord-bot 2>&1 || true)
if echo "$REMOVED_CONTAINER" | grep -q "discord-bot"; then
    echo -e "${GREEN}✅ Bot container stopped successfully${NC}"
else
    echo -e "${YELLOW}ℹ️  No bot container to stop${NC}"
fi

# Clean up unused images
echo -e "${BLUE}🧹 Cleaning old images...${NC}"
CLEANUP_RESULT=$(docker image prune -f 2>&1)
if echo "$CLEANUP_RESULT" | grep -q "Total reclaimed space"; then
    RECLAIMED_SPACE=$(echo "$CLEANUP_RESULT" | grep "Total reclaimed space" | awk '{print $4 $5}')
    echo -e "${GREEN}✅ Cleanup complete${NC}"
    echo -e "${PURPLE}👉 Reclaimed space: ${RECLAIMED_SPACE}${NC}"
else
    echo -e "${YELLOW}ℹ️  No images to clean${NC}"
fi

# Create necessary directories
echo -e "${BLUE}📁 Creating required directories...${NC}"
mkdir -p /tmp/empty

# Fix data directory permissions
echo -e "${BLUE}🔧 Setting up data directory permissions...${NC}"
mkdir -p data
sudo chown -R $USER:$USER data/ 2>/dev/null || chown -R $USER:$USER data/

# Build and start only bot container (don't touch other services)
echo -e "${BLUE}🏗️  Building and starting bot container only...${NC}"
echo -e "${PURPLE}👉 Building with configured mode${NC}"
echo -e "${CYAN}ℹ️  Kuma and CouchDB will remain running${NC}"

echo -e "${BLUE}🔍 Starting Docker build process...${NC}"
docker compose --env-file .env up -d --build --no-deps --force-recreate discord-bot 2>&1 | \
  stdbuf -oL -eL grep -v "transferring context\|transferring dockerfile\|naming to docker.io" | \
  stdbuf -oL -eL grep -E "^#|^\[|Built|Created|Started|Error|FAILED|COPY|RUN|exporting" | \
  stdbuf -oL -eL grep -v "CACHED.*apt-get\|CACHED.*WORKDIR\|CACHED.*requirements\|CACHED.*pip install" || true
BUILD_EXIT_CODE=${PIPESTATUS[0]}

if [ $BUILD_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Container built and started successfully${NC}"
else
    echo -e "${RED}❌ Failed to build/start container (exit code: $BUILD_EXIT_CODE)${NC}"
    exit 1
fi

# Verify container is running
echo -e "${BLUE}🔍 Verifying container status...${NC}"
echo -e "${BLUE}⏳ Waiting 8s for bot to fully start and process audio restoration...${NC}"
sleep 8
CONTAINER_STATUS=$(docker ps --filter name=${CONTAINER_NAME} --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | tail -n +2)
if [ ! -z "$CONTAINER_STATUS" ]; then
    echo -e "${GREEN}✅ Container is running${NC}"
    echo -e "${PURPLE}👉 Status: $CONTAINER_STATUS${NC}"

    # Restore user sessions after deployment
    echo -e "${BLUE}👉 Restoring user sessions...${NC}"
    sleep 2  # Give the bot a moment to fully initialize
    set +e  # Don't exit on curl error
    SESSION_RESTORE_RESULT=$(curl -s -X POST "http://localhost:${BOT_API_PORT}/api/live/audio/restore-sessions" 2>/dev/null || echo '{}')
    set -e  # Re-enable exit on error
    if echo "$SESSION_RESTORE_RESULT" | grep -q '"success":true'; then
        SESSIONS_RESTORED=$(echo "$SESSION_RESTORE_RESULT" | grep -o '"sessions_restored":[0-9]*' | cut -d':' -f2 2>/dev/null || echo "0")
        echo -e "${GREEN}👉 Restored ${SESSIONS_RESTORED} user sessions${NC}"
    else
        echo -e "${YELLOW}⚠️ Could not restore user sessions (API might not be ready yet)${NC}"
    fi

    # Users have been notified and everything is restored
    echo -e "${GREEN}✅ Deployment complete! Users notified, audio restored, sessions restarted.${NC}"
else
    echo -e "${RED}❌ Container failed to start${NC}"
    echo -e "${YELLOW}🔍 Checking bot logs for errors...${NC}"
    docker compose --env-file .env logs discord-bot
    exit 1
fi

# Final summary
echo ""
echo -e "${CYAN}🎉 ${ENV^^} Deployment Complete!${NC}"
echo "================================================="
echo -e "${GREEN}📋 Container: ${CONTAINER_NAME}${NC}"
echo -e "${GREEN}🔗 Network: ${NETWORK_NAME}${NC}"
echo -e "${GREEN}💻 Environment: ${ENVIRONMENT}${NC}"
echo ""
echo -e "${BLUE}📝 Useful commands:${NC}"
echo -e "${PURPLE}👉 View logs: make logs-${ENV}${NC}"
echo -e "${PURPLE}👉 Stop container: make stop-${ENV}${NC}"
echo -e "${PURPLE}👉 Check status: make status${NC}"
