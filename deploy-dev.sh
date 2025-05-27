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
echo -e "${CYAN}🚀 Development Deployment Starting...${NC}"
echo "================================================="

# Environment validation
echo -e "${BLUE}🔍 Validating environment...${NC}"
if [ ! -f ".env.dev" ]; then
    echo -e "${RED}❌ .env.dev not found!${NC}"
    echo -e "${YELLOW}📝 Copy .env.example to .env.dev and configure it${NC}"
    exit 1
fi
echo -e "${GREEN}✅ .env.dev found${NC}"

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
CONTAINER_NAME=$(grep CONTAINER_NAME .env.dev | cut -d'=' -f2 | tr -d '"')
NETWORK_NAME=$(grep NETWORK_NAME .env.dev | cut -d'=' -f2 | tr -d '"')
ENVIRONMENT=$(grep ENVIRONMENT .env.dev | cut -d'=' -f2 | tr -d '"')
RESTART_POLICY=$(grep RESTART_POLICY .env.dev | cut -d'=' -f2 | tr -d '"')

# Check if container is already running
echo -e "${BLUE}🔍 Checking existing containers...${NC}"
EXISTING_CONTAINER=$(docker ps -q --filter name=${CONTAINER_NAME} 2>/dev/null || echo "")
if [ ! -z "$EXISTING_CONTAINER" ]; then
    echo -e "${YELLOW}⚠️  Container ${CONTAINER_NAME} is currently running${NC}"
    echo -e "${PURPLE}👉 Container ID: ${EXISTING_CONTAINER}${NC}"
else
    echo -e "${GREEN}✅ No existing container found${NC}"
fi

# Stop existing containers
echo -e "${BLUE}🛑 Stopping existing development container...${NC}"
STOPPED_CONTAINERS=$(docker compose --env-file .env.dev down --remove-orphans 2>&1 || true)
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

# Build and start container
echo -e "${BLUE}🏗️  Building and starting development container...${NC}"
echo -e "${PURPLE}👉 Building with hot-reload enabled${NC}"
echo -e "${PURPLE}👉 Source code will be mounted for live editing${NC}"

BUILD_OUTPUT=$(docker compose --env-file .env.dev up -d --build 2>&1)
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
sleep 2
CONTAINER_STATUS=$(docker ps --filter name=${CONTAINER_NAME} --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | tail -n +2)
if [ ! -z "$CONTAINER_STATUS" ]; then
    echo -e "${GREEN}✅ Container is running${NC}"
    echo -e "${PURPLE}👉 Status: $CONTAINER_STATUS${NC}"
else
    echo -e "${RED}❌ Container failed to start${NC}"
    echo -e "${YELLOW}🔍 Checking logs for errors...${NC}"
    docker compose --env-file .env.dev logs --tail=20 discord-bot
    exit 1
fi

# Final summary
echo ""
echo -e "${CYAN}🎉 Development Deployment Complete!${NC}"
echo "================================================="
echo -e "${GREEN}📋 Container: ${CONTAINER_NAME}${NC}"
echo -e "${GREEN}🔗 Network: ${NETWORK_NAME}${NC}"
echo -e "${GREEN}🔄 Hot-reload: Enabled (code changes will restart bot)${NC}"
echo -e "${GREEN}💻 Environment: Development${NC}"
echo ""
echo -e "${BLUE}📝 Useful commands:${NC}"
echo -e "${PURPLE}👉 View logs: make logs-dev${NC}"
echo -e "${PURPLE}👉 Stop container: make stop-dev${NC}"
echo -e "${PURPLE}👉 Check status: make status${NC}"
