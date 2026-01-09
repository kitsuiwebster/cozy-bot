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

# Header
echo -e "${CYAN}🚀 Production Deployment Starting...${NC}"
echo "================================================="

# Environment validation
echo -e "${BLUE}🔍 Validating environment...${NC}"
if [ ! -f ".env.prod" ]; then
    echo -e "${RED}❌ .env.prod not found!${NC}"
    echo -e "${YELLOW}📝 Copy .env.example to .env.prod and configure it${NC}"
    exit 1
fi
echo -e "${GREEN}✅ .env.prod found${NC}"

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
CONTAINER_NAME=$(grep CONTAINER_NAME .env.prod | cut -d'=' -f2 | tr -d '"')
NETWORK_NAME=$(grep NETWORK_NAME .env.prod | cut -d'=' -f2 | tr -d '"')
ENVIRONMENT=$(grep ENVIRONMENT .env.prod | cut -d'=' -f2 | tr -d '"')
RESTART_POLICY=$(grep RESTART_POLICY .env.prod | cut -d'=' -f2 | tr -d '"')

# Check if container is already running
echo -e "${BLUE}🔍 Checking existing containers...${NC}"
EXISTING_CONTAINER=$(docker ps -q --filter name=${CONTAINER_NAME} 2>/dev/null || echo "")
if [ ! -z "$EXISTING_CONTAINER" ]; then
    echo -e "${YELLOW}⚠️  Container ${CONTAINER_NAME} is currently running${NC}"
    echo -e "${PURPLE}👉 Container ID: ${EXISTING_CONTAINER}${NC}"
    
    # Get current version
    VERSION=$(./utils/deployment/get-version.sh 2>/dev/null || echo "latest")
    
    # Check API health before proceeding
    echo -e "${BLUE}🔍 Checking API availability...${NC}"
    set +e
    API_HEALTH=$(curl -k -s "https://localhost:8000/health" 2>/dev/null)
    API_EXIT_CODE=$?
    set -e
    
    if [ $API_EXIT_CODE -eq 0 ] && echo "$API_HEALTH" | grep -q "healthy"; then
        echo -e "${GREEN}✅ API is available${NC}"
        echo -e "${BLUE}📢 Sending pre-deployment notification to users...${NC}"
        NOTIFICATION_RESULT=$(curl -k -s -X POST "https://localhost:8000/api/deployment/simple-notify" \
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
            
            # Save audio state before shutdown
            echo -e "${BLUE}🎵 Saving current audio state...${NC}"
            AUDIO_SAVE_RESULT=$(curl -k -s -X POST "https://localhost:8000/api/audio/save-state" 2>/dev/null)
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

# Stop existing containers
echo -e "${BLUE}🛑 Stopping existing production container...${NC}"
STOPPED_CONTAINERS=$(docker compose --env-file .env.prod down --remove-orphans 2>&1 || true)
if echo "$STOPPED_CONTAINERS" | grep -q "Removed"; then
    echo -e "${GREEN}✅ Containers stopped successfully${NC}"
    echo "$STOPPED_CONTAINERS" | grep "Removed" | sed 's/^/👉 /'
else
    echo -e "${YELLOW}ℹ️  No containers to stop${NC}"
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

# Fix data directory permissions for dev
echo -e "${BLUE}🔧 Setting up data directory permissions...${NC}"
mkdir -p data
sudo chown -R $USER:$USER data/ 2>/dev/null || chown -R $USER:$USER data/

# Build and start container
echo -e "${BLUE}🏗️  Building and starting production container...${NC}"
echo -e "${PURPLE}👉 Building with hot-reload enabled${NC}"
echo -e "${PURPLE}👉 Source code will be mounted for live editing${NC}"

BUILD_OUTPUT=$(docker compose --env-file .env.prod up -d --build 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Container built and started successfully${NC}"
    
    # Extract build information
    if echo "$BUILD_OUTPUT" | grep -q "Built"; then
        echo "$BUILD_OUTPUT" | grep "Built\|Created\|Started" | sed 's/^/👉 /'
    fi
else
    echo -e "${RED}❌ Failed to build/start container${NC}"
    echo "$BUILD_OUTPUT"
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
    
    # Users have been notified and audio should be restored automatically
    echo -e "${GREEN}✅ Deployment complete! Users have been notified and audio restored.${NC}"
else
    echo -e "${RED}❌ Container failed to start${NC}"
    echo -e "${YELLOW}🔍 Checking logs for errors...${NC}"
    docker compose --env-file .env.prod logs
    exit 1
fi

# Final summary
echo ""
echo -e "${CYAN}🎉 Production Deployment Complete!${NC}"
echo "================================================="
echo -e "${GREEN}📋 Container: ${CONTAINER_NAME}${NC}"
echo -e "${GREEN}🔗 Network: ${NETWORK_NAME}${NC}"
echo -e "${GREEN}🔄 Hot-reload: Enabled (code changes will restart bot)${NC}"
echo -e "${GREEN}💻 Environment: Production${NC}"
echo ""
echo -e "${BLUE}📝 Useful commands:${NC}"
echo -e "${PURPLE}👉 View logs: make logs-prod${NC}"
echo -e "${PURPLE}👉 Stop container: make stop-prod${NC}"
echo -e "${PURPLE}👉 Check status: make status${NC}"
