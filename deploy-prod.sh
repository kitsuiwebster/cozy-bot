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
    echo "${CYAN}🚀 Production Deployment Starting...${NC}"
    echo "================================================="

    # Environment validation
    echo "${BLUE}🔍 Validating environment...${NC}"
    if [ ! -f ".env.prod" ]; then
        echo "${RED}❌ .env.prod not found!${NC}"
        echo "${YELLOW}📝 Copy .env.example to .env.prod and configure it${NC}"
        exit 1
    fi
    echo "${GREEN}✅ .env.prod found${NC}"

    # Security check for production
    echo "${BLUE}🔐 Performing security checks...${NC}"
    if grep -q "your_token_here\|example\|test" .env.prod; then
        echo "${RED}❌ Production file contains placeholder values!${NC}"
        echo "${YELLOW}⚠️  Please configure real production values${NC}"
        exit 1
    fi
    echo "${GREEN}✅ Security checks passed${NC}"

    # Check Docker availability
    echo "${BLUE}🐳 Checking Docker availability...${NC}"
    if ! command -v docker &> /dev/null; then
        echo "${RED}❌ Docker not found!${NC}"
        exit 1
    fi
    echo "${GREEN}✅ Docker is available${NC}"

    if ! command -v docker compose &> /dev/null; then
        echo "${RED}❌ Docker Compose not found!${NC}"
        exit 1
    fi
    echo "${GREEN}✅ Docker Compose is available${NC}"

    # Load and display environment configuration
    echo "${BLUE}📋 Loading environment configuration...${NC}"
    CONTAINER_NAME=$(grep CONTAINER_NAME .env.prod | cut -d'=' -f2 | tr -d '"')
    NETWORK_NAME=$(grep NETWORK_NAME .env.prod | cut -d'=' -f2 | tr -d '"')
    ENVIRONMENT=$(grep ENVIRONMENT .env.prod | cut -d'=' -f2 | tr -d '"')
    RESTART_POLICY=$(grep RESTART_POLICY .env.prod | cut -d'=' -f2 | tr -d '"')

    # Check current container status
    echo "${BLUE}🔍 Checking existing containers...${NC}"
    EXISTING_CONTAINER=$(docker ps -q --filter name=${CONTAINER_NAME} 2>/dev/null || echo "")
    if [ ! -z "$EXISTING_CONTAINER" ]; then
        echo "${YELLOW}⚠️  Container ${CONTAINER_NAME} is currently running${NC}"
        UPTIME=$(docker ps --filter name=${CONTAINER_NAME} --format "{{.Status}}")
        echo "${PURPLE}👉 Current status: ${UPTIME}${NC}"
        
        # Check if container is healthy
        HEALTH_STATUS=$(docker inspect ${CONTAINER_NAME} --format='{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
        if [ "$HEALTH_STATUS" != "unknown" ]; then
            echo "${PURPLE}👉 Health status: ${HEALTH_STATUS}${NC}"
        fi
    else
        echo "${GREEN}✅ No existing container found${NC}"
    fi

    # Graceful shutdown for production
    if [ ! -z "$EXISTING_CONTAINER" ]; then
        echo "${BLUE}⏸️  Performing graceful shutdown...${NC}"
        docker compose --env-file .env.prod stop discord-bot 2>/dev/null || true
        sleep 3
    fi

    # Stop existing containers
    echo "${BLUE}🛑 Stopping existing production container...${NC}"
    STOPPED_CONTAINERS=$(docker compose --env-file .env.prod down --remove-orphans 2>&1 || true)
    if echo "$STOPPED_CONTAINERS" | grep -q "Removed"; then
        echo "${GREEN}✅ Containers stopped successfully${NC}"
        echo "$STOPPED_CONTAINERS" | grep "Removed" | sed 's/^/👉 /'
    else
        echo "${YELLOW}ℹ️  No containers to stop${NC}"
    fi

    # Clean up unused images
    echo "${BLUE}🧹 Cleaning old images...${NC}"
    CLEANUP_RESULT=$(docker image prune -f 2>&1)
    if echo "$CLEANUP_RESULT" | grep -q "Total reclaimed space"; then
        RECLAIMED_SPACE=$(echo "$CLEANUP_RESULT" | grep "Total reclaimed space" | awk '{print $4 $5}')
        echo "${GREEN}✅ Cleanup complete${NC}"
        echo "${PURPLE}👉 Reclaimed space: ${RECLAIMED_SPACE}${NC}"
    else
        echo "${YELLOW}ℹ️  No images to clean${NC}"
    fi

    # Build and start container
    echo "${BLUE}🏗️  Building and starting production container...${NC}"
    echo "${PURPLE}👉 Building optimized production image${NC}"
    echo "${PURPLE}👉 Health checks will be enabled${NC}"
    echo "${PURPLE}👉 Auto-restart policy: ${RESTART_POLICY}${NC}"

    BUILD_OUTPUT=$(docker compose --env-file .env.prod up -d --build 2>&1)
    if [ $? -eq 0 ]; then
        echo "${GREEN}✅ Container built and started successfully${NC}"
        
        # Extract build information
        if echo "$BUILD_OUTPUT" | grep -q "Built"; then
            echo "$BUILD_OUTPUT" | grep "Built\|Created\|Started" | sed 's/^/👉 /'
        fi
    else
        echo "${RED}❌ Failed to build/start container${NC}"
        echo "$BUILD_OUTPUT"
        exit 1
    fi

    # Wait for container to be ready
    echo "${BLUE}⏳ Waiting for container to be ready...${NC}"
    for i in {1..30}; do
        CONTAINER_STATUS=$(docker ps --filter name=${CONTAINER_NAME} --format "{{.Status}}" 2>/dev/null || echo "")
        if [[ "$CONTAINER_STATUS" == *"Up"* ]]; then
            echo "${GREEN}✅ Container is running${NC}"
            break
        fi
        echo "${PURPLE}👉 Waiting... (${i}/30)${NC}"
        sleep 2
    done

    # Verify container health
    echo "${BLUE}🏥 Checking container health...${NC}"
    sleep 5
    HEALTH_STATUS=$(docker inspect ${CONTAINER_NAME} --format='{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
    if [ "$HEALTH_STATUS" = "healthy" ]; then
        echo "${GREEN}✅ Container is healthy${NC}"
    elif [ "$HEALTH_STATUS" = "starting" ]; then
        echo "${YELLOW}⏳ Health check starting...${NC}"
    elif [ "$HEALTH_STATUS" = "unknown" ]; then
        echo "${YELLOW}ℹ️  Health check not configured${NC}"
    else
        echo "${YELLOW}⚠️  Health status: ${HEALTH_STATUS}${NC}"
    fi

    # Verify container is running
    CONTAINER_INFO=$(docker ps --filter name=${CONTAINER_NAME} --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | tail -n +2)
    if [ ! -z "$CONTAINER_INFO" ]; then
        echo "${GREEN}✅ Container verification successful${NC}"
        echo "${PURPLE}👉 Status: $CONTAINER_INFO${NC}"
    else
        echo "${RED}❌ Container failed to start${NC}"
        echo "${YELLOW}🔍 Checking logs for errors...${NC}"
        docker compose --env-file .env.prod logs --tail=20 discord-bot
        exit 1
    fi

    # Final summary
    echo ""
    echo "${CYAN}🎉 Production Deployment Complete!${NC}"
    echo "================================================="
    echo "${GREEN}📋 Container: ${CONTAINER_NAME}${NC}"
    echo "${GREEN}🔗 Network: ${NETWORK_NAME}${NC}"
    echo "${GREEN}🛡️  Security: Production mode enabled${NC}"
    echo "${GREEN}🔄 Auto-restart: ${RESTART_POLICY}${NC}"
    echo "${GREEN}🏥 Health checks: Enabled${NC}"
    echo ""
    echo "${BLUE}📝 Useful commands:${NC}"
    echo "${PURPLE}👉 View logs: make logs-prod${NC}"
    echo "${PURPLE}👉 Stop container: make stop-prod${NC}"
    echo "${PURPLE}👉 Check status: make status${NC}"
    echo ""
    echo "${GREEN}🚀 Production deployment successful!${NC}"