#!/bin/bash

# Debug deployment script - DO NOT use 'set -e' to avoid immediate exit on errors
# This allows us to capture and analyze errors properly

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
ORANGE='\033[0;33m'
NC='\033[0m' # No Color

# Global error tracking
ERRORS_FOUND=0
DEBUG_LOG="/tmp/deploy-dev-debug-$(date +%Y%m%d_%H%M%S).log"

# Function to log debug information
debug_log() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $message" >> "$DEBUG_LOG"
    echo -e "${ORANGE}[DEBUG] $message${NC}"
}

# Function to track errors without exiting
track_error() {
    local error_msg="$1"
    local exit_code="$2"
    ERRORS_FOUND=$((ERRORS_FOUND + 1))
    debug_log "ERROR #$ERRORS_FOUND: $error_msg (Exit Code: $exit_code)"
    echo -e "${RED}❌ ERROR #$ERRORS_FOUND: $error_msg${NC}"
    echo -e "${RED}    Exit Code: $exit_code${NC}"
}

# Function to check command success
check_command() {
    local cmd="$1"
    local description="$2"
    local exit_code=$3
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ $description - SUCCESS${NC}"
        debug_log "SUCCESS: $description (Command: $cmd)"
        return 0
    else
        track_error "$description failed" "$exit_code"
        debug_log "FAILED: $description (Command: $cmd, Exit Code: $exit_code)"
        return 1
    fi
}

# Header
echo -e "${CYAN}🐛 DEBUG Development Deployment Starting...${NC}"
echo -e "${ORANGE}Debug log file: $DEBUG_LOG${NC}"
echo "============================================================="

debug_log "Starting debug deployment process"

# System information collection
echo -e "${BLUE}🖥️  Collecting system information...${NC}"
debug_log "=== SYSTEM INFORMATION ==="

# Current user and permissions
CURRENT_USER=$(whoami)
USER_GROUPS=$(groups)
debug_log "Current user: $CURRENT_USER"
debug_log "User groups: $USER_GROUPS"
echo -e "${PURPLE}👤 User: $CURRENT_USER${NC}"
echo -e "${PURPLE}👥 Groups: $USER_GROUPS${NC}"

# Working directory
CURRENT_DIR=$(pwd)
debug_log "Working directory: $CURRENT_DIR"
echo -e "${PURPLE}📂 Working directory: $CURRENT_DIR${NC}"

# System resources
echo -e "${BLUE}💾 Checking system resources...${NC}"
debug_log "=== SYSTEM RESOURCES ==="

# Disk space
DISK_USAGE=$(df -h . 2>/dev/null || echo "Unable to check disk space")
debug_log "Disk usage: $DISK_USAGE"
echo -e "${PURPLE}💿 Disk space:${NC}"
echo "$DISK_USAGE" | tail -n +2 | while read line; do
    echo -e "   ${PURPLE}👉 $line${NC}"
done

# Available space in bytes for more precise checking
AVAILABLE_SPACE_KB=$(df . | tail -1 | awk '{print $4}')
AVAILABLE_SPACE_MB=$((AVAILABLE_SPACE_KB / 1024))
debug_log "Available space: ${AVAILABLE_SPACE_MB}MB"

if [ $AVAILABLE_SPACE_MB -lt 1000 ]; then
    track_error "Low disk space: ${AVAILABLE_SPACE_MB}MB available" "0"
else
    echo -e "${GREEN}✅ Sufficient disk space: ${AVAILABLE_SPACE_MB}MB available${NC}"
fi

# Memory information
MEMORY_INFO=$(free -h 2>/dev/null || echo "Unable to check memory")
debug_log "Memory info: $MEMORY_INFO"
echo -e "${PURPLE}🧠 Memory usage:${NC}"
echo "$MEMORY_INFO" | while read line; do
    echo -e "   ${PURPLE}👉 $line${NC}"
done

# Load average
LOAD_AVG=$(uptime 2>/dev/null | awk -F'load average:' '{print $2}' || echo "Unable to check load")
debug_log "Load average: $LOAD_AVG"
echo -e "${PURPLE}⚡ Load average:$LOAD_AVG${NC}"

# Environment validation with detailed checking
echo -e "${BLUE}🔍 Validating environment files...${NC}"
debug_log "=== ENVIRONMENT VALIDATION ==="

# Check .env.dev existence and readability
if [ -f ".env.dev" ]; then
    echo -e "${GREEN}✅ .env.dev found${NC}"
    debug_log ".env.dev file exists"
    
    # Check file permissions
    ENV_PERMS=$(ls -la .env.dev)
    debug_log ".env.dev permissions: $ENV_PERMS"
    echo -e "${PURPLE}👉 Permissions: $ENV_PERMS${NC}"
    
    # Check file size
    ENV_SIZE=$(wc -c < .env.dev)
    debug_log ".env.dev size: $ENV_SIZE bytes"
    echo -e "${PURPLE}👉 File size: $ENV_SIZE bytes${NC}"
    
    if [ $ENV_SIZE -eq 0 ]; then
        track_error ".env.dev file is empty" "0"
    fi
else
    track_error ".env.dev not found" "1"
    echo -e "${YELLOW}📝 Copy .env.example to .env.dev and configure it${NC}"
    
    # Check if .env.example exists as reference
    if [ -f ".env.example" ]; then
        echo -e "${BLUE}💡 .env.example found for reference${NC}"
        debug_log ".env.example exists for reference"
    else
        echo -e "${YELLOW}⚠️  .env.example also not found${NC}"
        debug_log ".env.example not found"
    fi
fi

# Docker availability with version information
echo -e "${BLUE}🐳 Checking Docker installation...${NC}"
debug_log "=== DOCKER VALIDATION ==="

# Check Docker command
docker --version > /dev/null 2>&1
DOCKER_CHECK_EXIT=$?
if check_command "docker --version" "Docker availability check" $DOCKER_CHECK_EXIT; then
    DOCKER_VERSION=$(docker --version 2>/dev/null)
    debug_log "Docker version: $DOCKER_VERSION"
    echo -e "${PURPLE}👉 $DOCKER_VERSION${NC}"
    
    # Check Docker daemon
    docker info > /dev/null 2>&1
    DOCKER_DAEMON_EXIT=$?
    if check_command "docker info" "Docker daemon connectivity" $DOCKER_DAEMON_EXIT; then
        echo -e "${GREEN}✅ Docker daemon is running${NC}"
        debug_log "Docker daemon is accessible"
    else
        track_error "Docker daemon not accessible" "$DOCKER_DAEMON_EXIT"
    fi
else
    track_error "Docker not found or not accessible" "$DOCKER_CHECK_EXIT"
fi

# Check Docker Compose
docker compose version > /dev/null 2>&1
COMPOSE_CHECK_EXIT=$?
if check_command "docker compose version" "Docker Compose availability check" $COMPOSE_CHECK_EXIT; then
    COMPOSE_VERSION=$(docker compose version 2>/dev/null)
    debug_log "Docker Compose version: $COMPOSE_VERSION"
    echo -e "${PURPLE}👉 $COMPOSE_VERSION${NC}"
else
    track_error "Docker Compose not found or not accessible" "$COMPOSE_CHECK_EXIT"
fi

# Load environment configuration with validation
echo -e "${BLUE}📋 Loading and validating environment configuration...${NC}"
debug_log "=== ENVIRONMENT CONFIGURATION ==="

if [ -f ".env.dev" ]; then
    # Load environment variables with error checking
    CONTAINER_NAME=$(grep '^CONTAINER_NAME=' .env.dev | cut -d'=' -f2 | tr -d '"' 2>/dev/null || echo "")
    NETWORK_NAME=$(grep '^NETWORK_NAME=' .env.dev | cut -d'=' -f2 | tr -d '"' 2>/dev/null || echo "")
    ENVIRONMENT=$(grep '^ENVIRONMENT=' .env.dev | cut -d'=' -f2 | tr -d '"' 2>/dev/null || echo "")
    RESTART_POLICY=$(grep '^RESTART_POLICY=' .env.dev | cut -d'=' -f2 | tr -d '"' 2>/dev/null || echo "")
    DISCORD_BOT_TOKEN=$(grep '^DISCORD_BOT_TOKEN=' .env.dev | cut -d'=' -f2 | tr -d '"' 2>/dev/null || echo "")
    BOT_MODE=$(grep '^BOT_MODE=' .env.dev | cut -d'=' -f2 | tr -d '"' 2>/dev/null || echo "")
    DEV_CODE_MOUNT=$(grep '^DEV_CODE_MOUNT=' .env.dev | cut -d'=' -f2 | tr -d '"' 2>/dev/null || echo "")
    
    # Display and validate each variable
    echo -e "${PURPLE}📋 Environment variables:${NC}"
    
    # Container name validation
    if [ -n "$CONTAINER_NAME" ]; then
        echo -e "${PURPLE}  👉 CONTAINER_NAME: $CONTAINER_NAME${NC}"
        debug_log "CONTAINER_NAME: $CONTAINER_NAME"
    else
        track_error "CONTAINER_NAME not found or empty in .env.dev" "1"
    fi
    
    # Network name validation
    if [ -n "$NETWORK_NAME" ]; then
        echo -e "${PURPLE}  👉 NETWORK_NAME: $NETWORK_NAME${NC}"
        debug_log "NETWORK_NAME: $NETWORK_NAME"
    else
        track_error "NETWORK_NAME not found or empty in .env.dev" "1"
    fi
    
    # Environment validation
    if [ -n "$ENVIRONMENT" ]; then
        echo -e "${PURPLE}  👉 ENVIRONMENT: $ENVIRONMENT${NC}"
        debug_log "ENVIRONMENT: $ENVIRONMENT"
    else
        track_error "ENVIRONMENT not found or empty in .env.dev" "1"
    fi
    
    # Bot mode validation
    if [ -n "$BOT_MODE" ]; then
        echo -e "${PURPLE}  👉 BOT_MODE: $BOT_MODE${NC}"
        debug_log "BOT_MODE: $BOT_MODE"
    else
        track_error "BOT_MODE not found or empty in .env.dev" "1"
    fi
    
    # Discord token validation (check presence, not actual value)
    if [ -n "$DISCORD_BOT_TOKEN" ]; then
        TOKEN_LENGTH=${#DISCORD_BOT_TOKEN}
        echo -e "${PURPLE}  👉 DISCORD_BOT_TOKEN: [PRESENT - $TOKEN_LENGTH chars]${NC}"
        debug_log "DISCORD_BOT_TOKEN: present, length $TOKEN_LENGTH"
        
        if [ $TOKEN_LENGTH -lt 50 ]; then
            track_error "Discord bot token seems too short ($TOKEN_LENGTH chars)" "0"
        fi
    else
        track_error "DISCORD_BOT_TOKEN not found or empty in .env.dev" "1"
    fi
    
    # Development mount validation
    if [ -n "$DEV_CODE_MOUNT" ]; then
        echo -e "${PURPLE}  👉 DEV_CODE_MOUNT: $DEV_CODE_MOUNT${NC}"
        debug_log "DEV_CODE_MOUNT: $DEV_CODE_MOUNT"
    else
        echo -e "${YELLOW}  ⚠️  DEV_CODE_MOUNT not set${NC}"
        debug_log "DEV_CODE_MOUNT not set"
    fi
    
    # Restart policy validation
    if [ -n "$RESTART_POLICY" ]; then
        echo -e "${PURPLE}  👉 RESTART_POLICY: $RESTART_POLICY${NC}"
        debug_log "RESTART_POLICY: $RESTART_POLICY"
    else
        echo -e "${YELLOW}  ⚠️  RESTART_POLICY not set, will use default${NC}"
        debug_log "RESTART_POLICY not set"
    fi
else
    track_error "Cannot load environment variables - .env.dev not accessible" "1"
fi

# Check existing containers with detailed information
echo -e "${BLUE}🔍 Checking existing containers...${NC}"
debug_log "=== EXISTING CONTAINERS CHECK ==="

if [ -n "$CONTAINER_NAME" ]; then
    # Check running containers
    EXISTING_CONTAINER=$(docker ps -q --filter name=${CONTAINER_NAME} 2>/dev/null || echo "")
    EXISTING_CONTAINER_EXIT=$?
    
    if [ $EXISTING_CONTAINER_EXIT -eq 0 ]; then
        if [ -n "$EXISTING_CONTAINER" ]; then
            echo -e "${YELLOW}⚠️  Container ${CONTAINER_NAME} is currently running${NC}"
            debug_log "Found running container: $EXISTING_CONTAINER"
            
            # Get detailed container information
            CONTAINER_INFO=$(docker inspect $EXISTING_CONTAINER 2>/dev/null || echo "Unable to inspect container")
            if [ "$CONTAINER_INFO" != "Unable to inspect container" ]; then
                CONTAINER_STATE=$(echo "$CONTAINER_INFO" | grep '"Status"' | head -1 | awk -F'"' '{print $4}')
                CONTAINER_STARTED=$(echo "$CONTAINER_INFO" | grep '"StartedAt"' | head -1 | awk -F'"' '{print $4}')
                echo -e "${PURPLE}  👉 Container ID: $EXISTING_CONTAINER${NC}"
                echo -e "${PURPLE}  👉 Status: $CONTAINER_STATE${NC}"
                echo -e "${PURPLE}  👉 Started: $CONTAINER_STARTED${NC}"
                debug_log "Container state: $CONTAINER_STATE, started: $CONTAINER_STARTED"
            fi
        else
            echo -e "${GREEN}✅ No running container found${NC}"
            debug_log "No running containers with name $CONTAINER_NAME"
        fi
        
        # Check stopped containers too
        STOPPED_CONTAINERS=$(docker ps -aq --filter name=${CONTAINER_NAME} 2>/dev/null || echo "")
        if [ -n "$STOPPED_CONTAINERS" ] && [ "$STOPPED_CONTAINERS" != "$EXISTING_CONTAINER" ]; then
            echo -e "${BLUE}ℹ️  Found stopped containers with same name${NC}"
            debug_log "Found stopped containers: $STOPPED_CONTAINERS"
        fi
    else
        track_error "Failed to check existing containers" "$EXISTING_CONTAINER_EXIT"
    fi
else
    track_error "Cannot check containers - CONTAINER_NAME not set" "1"
fi

# Check Docker Compose file
echo -e "${BLUE}📄 Validating Docker Compose configuration...${NC}"
debug_log "=== DOCKER COMPOSE VALIDATION ==="

if [ -f "docker-compose.yml" ]; then
    echo -e "${GREEN}✅ docker-compose.yml found${NC}"
    debug_log "docker-compose.yml exists"
    
    # Validate compose file syntax
    docker compose --env-file .env.dev config > /dev/null 2>&1
    COMPOSE_VALIDATION_EXIT=$?
    
    if check_command "docker compose config" "Docker Compose file validation" $COMPOSE_VALIDATION_EXIT; then
        echo -e "${GREEN}✅ Docker Compose configuration is valid${NC}"
        debug_log "Docker Compose configuration validation passed"
        
        # Show resolved configuration (for debugging)
        echo -e "${BLUE}🔍 Resolved Docker Compose configuration:${NC}"
        RESOLVED_CONFIG=$(docker compose --env-file .env.dev config 2>/dev/null || echo "Unable to resolve config")
        if [ "$RESOLVED_CONFIG" != "Unable to resolve config" ]; then
            # Just show the service definition for brevity
            echo "$RESOLVED_CONFIG" | grep -A 20 "services:" | head -25 | while read line; do
                echo -e "${PURPLE}  $line${NC}"
            done
            debug_log "Resolved configuration retrieved successfully"
        fi
    else
        track_error "Docker Compose configuration validation failed" "$COMPOSE_VALIDATION_EXIT"
        
        # Try to get validation errors
        VALIDATION_ERRORS=$(docker compose --env-file .env.dev config 2>&1 || echo "Unable to get validation errors")
        echo -e "${RED}Validation errors:${NC}"
        echo -e "${RED}$VALIDATION_ERRORS${NC}"
        debug_log "Compose validation errors: $VALIDATION_ERRORS"
    fi
else
    track_error "docker-compose.yml not found" "1"
fi

# Check required directories
echo -e "${BLUE}📁 Checking required directories...${NC}"
debug_log "=== DIRECTORY VALIDATION ==="

# Create /tmp/empty if it doesn't exist (commonly used in volumes)
if [ ! -d "/tmp/empty" ]; then
    echo -e "${BLUE}📁 Creating /tmp/empty directory...${NC}"
    mkdir -p /tmp/empty
    MKDIR_EXIT=$?
    if check_command "mkdir -p /tmp/empty" "Create /tmp/empty directory" $MKDIR_EXIT; then
        debug_log "Created /tmp/empty directory"
    else
        track_error "Failed to create /tmp/empty directory" "$MKDIR_EXIT"
    fi
else
    echo -e "${GREEN}✅ /tmp/empty directory exists${NC}"
    debug_log "/tmp/empty directory already exists"
fi

# Check if the source code mount point exists (for development)
if [ -n "$DEV_CODE_MOUNT" ] && [ "$DEV_CODE_MOUNT" != "/tmp/empty" ]; then
    if [ -d "$DEV_CODE_MOUNT" ] || [ "$DEV_CODE_MOUNT" = "." ]; then
        echo -e "${GREEN}✅ Development code mount point accessible${NC}"
        debug_log "Development code mount point $DEV_CODE_MOUNT is accessible"
    else
        track_error "Development code mount point $DEV_CODE_MOUNT not accessible" "1"
    fi
fi

# Stopping existing containers (with full output capture)
echo -e "${BLUE}🛑 Stopping existing development containers...${NC}"
debug_log "=== STOPPING EXISTING CONTAINERS ==="

if [ -f ".env.dev" ]; then
    echo -e "${ORANGE}[DEBUG] Running: docker compose --env-file .env.dev down --remove-orphans${NC}"
    STOPPED_CONTAINERS=$(docker compose --env-file .env.dev down --remove-orphans 2>&1)
    STOP_EXIT=$?
    
    debug_log "Stop command exit code: $STOP_EXIT"
    debug_log "Stop command output: $STOPPED_CONTAINERS"
    
    echo -e "${PURPLE}📝 Stop command output:${NC}"
    echo "$STOPPED_CONTAINERS" | while read line; do
        echo -e "${PURPLE}  👉 $line${NC}"
    done
    
    if [ $STOP_EXIT -eq 0 ]; then
        echo -e "${GREEN}✅ Stop command completed successfully${NC}"
        if echo "$STOPPED_CONTAINERS" | grep -q "Removed\|Stopped"; then
            echo -e "${GREEN}✅ Containers stopped/removed${NC}"
        else
            echo -e "${YELLOW}ℹ️  No containers were running${NC}"
        fi
    else
        track_error "Failed to stop existing containers" "$STOP_EXIT"
    fi
else
    track_error "Cannot stop containers - .env.dev not available" "1"
fi

# Clean up unused images (with detailed output)
echo -e "${BLUE}🧹 Cleaning unused Docker images...${NC}"
debug_log "=== IMAGE CLEANUP ==="

echo -e "${ORANGE}[DEBUG] Running: docker image prune -f${NC}"
CLEANUP_RESULT=$(docker image prune -f 2>&1)
CLEANUP_EXIT=$?

debug_log "Cleanup command exit code: $CLEANUP_EXIT"
debug_log "Cleanup command output: $CLEANUP_RESULT"

echo -e "${PURPLE}📝 Cleanup command output:${NC}"
echo "$CLEANUP_RESULT" | while read line; do
    echo -e "${PURPLE}  👉 $line${NC}"
done

if [ $CLEANUP_EXIT -eq 0 ]; then
    if echo "$CLEANUP_RESULT" | grep -q "Total reclaimed space"; then
        RECLAIMED_SPACE=$(echo "$CLEANUP_RESULT" | grep "Total reclaimed space" | awk '{print $4 $5}')
        echo -e "${GREEN}✅ Cleanup completed successfully${NC}"
        echo -e "${GREEN}  👉 Reclaimed space: ${RECLAIMED_SPACE}${NC}"
        debug_log "Cleanup successful, reclaimed: $RECLAIMED_SPACE"
    else
        echo -e "${YELLOW}ℹ️  No images to clean${NC}"
        debug_log "No images to clean"
    fi
else
    track_error "Image cleanup failed" "$CLEANUP_EXIT"
fi

# Building and starting container (with comprehensive output capture)
echo -e "${BLUE}🏗️  Building and starting development container...${NC}"
debug_log "=== BUILD AND START PROCESS ==="

if [ $ERRORS_FOUND -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Warning: $ERRORS_FOUND error(s) found during prerequisites check${NC}"
    echo -e "${YELLOW}⚠️  Continuing with build process for debugging...${NC}"
    debug_log "Proceeding with build despite $ERRORS_FOUND errors for debugging"
fi

if [ -f ".env.dev" ]; then
    echo -e "${PURPLE}👉 Building with hot-reload enabled${NC}"
    echo -e "${PURPLE}👉 Source code will be mounted for live editing${NC}"
    
    # Show the exact command that will be executed
    BUILD_COMMAND="docker compose --env-file .env.dev up -d --build"
    echo -e "${ORANGE}[DEBUG] Running: $BUILD_COMMAND${NC}"
    debug_log "Executing build command: $BUILD_COMMAND"
    
    # Execute with full output capture and timestamps
    echo -e "${BLUE}📝 Build process output (real-time):${NC}"
    echo "----------------------------------------"
    
    # Use a more sophisticated approach to capture both stdout and stderr with timestamps
    BUILD_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
    debug_log "Build started at: $BUILD_START_TIME"
    
    # Create a temporary file to capture the full output
    BUILD_OUTPUT_FILE="/tmp/build_output_$$"
    
    # Run the build command and capture all output
    docker compose --env-file .env.dev up -d --build > "$BUILD_OUTPUT_FILE" 2>&1
    BUILD_EXIT=$?
    
    BUILD_END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
    debug_log "Build ended at: $BUILD_END_TIME"
    debug_log "Build exit code: $BUILD_EXIT"
    
    # Display the captured output with formatting
    if [ -f "$BUILD_OUTPUT_FILE" ]; then
        BUILD_OUTPUT=$(cat "$BUILD_OUTPUT_FILE")
        debug_log "Build output: $BUILD_OUTPUT"
        
        echo "$BUILD_OUTPUT" | while read line; do
            echo -e "${CYAN}$(date '+%H:%M:%S') | $line${NC}"
        done
        
        # Clean up temporary file
        rm -f "$BUILD_OUTPUT_FILE"
    fi
    
    echo "----------------------------------------"
    
    if check_command "$BUILD_COMMAND" "Container build and start" $BUILD_EXIT; then
        echo -e "${GREEN}✅ Container built and started successfully${NC}"
        debug_log "Build process completed successfully"
        
        # Extract and display build information
        if echo "$BUILD_OUTPUT" | grep -q "Built\|Created\|Started\|Pulled"; then
            echo -e "${BLUE}📋 Build summary:${NC}"
            echo "$BUILD_OUTPUT" | grep "Built\|Created\|Started\|Pulled" | while read line; do
                echo -e "${GREEN}  ✅ $line${NC}"
            done
        fi
        
        # Check for warnings in build output
        if echo "$BUILD_OUTPUT" | grep -qi "warning\|warn"; then
            echo -e "${YELLOW}⚠️  Warnings found in build output:${NC}"
            echo "$BUILD_OUTPUT" | grep -i "warning\|warn" | while read line; do
                echo -e "${YELLOW}  👉 $line${NC}"
            done
            debug_log "Build warnings found"
        fi
    else
        track_error "Container build/start failed" "$BUILD_EXIT"
        echo -e "${RED}❌ Build process failed${NC}"
        echo -e "${RED}📋 Full build output above${NC}"
        
        # Additional debugging for build failures
        echo -e "${BLUE}🔍 Additional debugging information:${NC}"
        
        # Check for common error patterns
        if echo "$BUILD_OUTPUT" | grep -qi "no space left"; then
            echo -e "${RED}  👉 Possible cause: Insufficient disk space${NC}"
        fi
        
        if echo "$BUILD_OUTPUT" | grep -qi "permission denied"; then
            echo -e "${RED}  👉 Possible cause: Permission issues${NC}"
        fi
        
        if echo "$BUILD_OUTPUT" | grep -qi "network\|connection\|timeout"; then
            echo -e "${RED}  👉 Possible cause: Network connectivity issues${NC}"
        fi
        
        if echo "$BUILD_OUTPUT" | grep -qi "dockerfile\|build context"; then
            echo -e "${RED}  👉 Possible cause: Dockerfile or build context issues${NC}"
        fi
    fi
else
    track_error "Cannot start build - .env.dev not available" "1"
fi

# Verify container is running (with detailed status)
echo -e "${BLUE}🔍 Verifying container status...${NC}"
debug_log "=== CONTAINER STATUS VERIFICATION ==="

if [ -n "$CONTAINER_NAME" ]; then
    echo -e "${BLUE}⏱️  Waiting 3 seconds for container to initialize...${NC}"
    sleep 3
    
    # Check if container exists and is running
    CONTAINER_STATUS=$(docker ps --filter name=${CONTAINER_NAME} --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "")
    CONTAINER_CHECK_EXIT=$?
    
    debug_log "Container status check exit code: $CONTAINER_CHECK_EXIT"
    debug_log "Container status output: $CONTAINER_STATUS"
    
    if [ $CONTAINER_CHECK_EXIT -eq 0 ] && [ -n "$CONTAINER_STATUS" ]; then
        # Remove header line and check if we have actual data
        CONTAINER_DATA=$(echo "$CONTAINER_STATUS" | tail -n +2)
        if [ -n "$CONTAINER_DATA" ]; then
            echo -e "${GREEN}✅ Container is running${NC}"
            echo -e "${PURPLE}👉 Status details:${NC}"
            echo "$CONTAINER_DATA" | while read line; do
                echo -e "${PURPLE}     $line${NC}"
            done
            debug_log "Container is running successfully"
            
            # Get additional container information
            echo -e "${BLUE}📋 Additional container information:${NC}"
            
            # Container health (if health check is enabled)
            HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' ${CONTAINER_NAME} 2>/dev/null || echo "no-healthcheck")
            if [ "$HEALTH_STATUS" != "no-healthcheck" ]; then
                echo -e "${PURPLE}  👉 Health Status: $HEALTH_STATUS${NC}"
                debug_log "Container health status: $HEALTH_STATUS"
            fi
            
            # Container resource usage
            CONTAINER_STATS=$(docker stats ${CONTAINER_NAME} --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || echo "Unable to get stats")
            if [ "$CONTAINER_STATS" != "Unable to get stats" ]; then
                echo -e "${PURPLE}  👉 Resource usage:${NC}"
                echo "$CONTAINER_STATS" | tail -1 | while read line; do
                    echo -e "${PURPLE}     CPU/Memory: $line${NC}"
                done
                debug_log "Container stats: $CONTAINER_STATS"
            fi
            
        else
            track_error "Container not found in running containers list" "1"
        fi
    else
        track_error "Container failed to start or is not running" "$CONTAINER_CHECK_EXIT"
        
        echo -e "${YELLOW}🔍 Checking container logs for errors...${NC}"
        
        # Get container logs if container exists (even if stopped)
        ALL_CONTAINERS=$(docker ps -a --filter name=${CONTAINER_NAME} --format "{{.Names}}" 2>/dev/null || echo "")
        if [ -n "$ALL_CONTAINERS" ]; then
            echo -e "${BLUE}📋 Container logs (last 20 lines):${NC}"
            CONTAINER_LOGS=$(docker logs --tail 20 ${CONTAINER_NAME} 2>&1 || echo "Unable to get logs")
            echo "$CONTAINER_LOGS" | while read line; do
                echo -e "${RED}  👉 $line${NC}"
            done
            debug_log "Container logs: $CONTAINER_LOGS"
            
            # Try to get container inspect information for more details
            echo -e "${BLUE}🔍 Container inspect information:${NC}"
            INSPECT_INFO=$(docker inspect ${CONTAINER_NAME} 2>/dev/null || echo "Unable to inspect")
            if [ "$INSPECT_INFO" != "Unable to inspect" ]; then
                # Extract key information
                CONTAINER_STATE=$(echo "$INSPECT_INFO" | grep '"Status"' | head -1 | awk -F'"' '{print $4}')
                CONTAINER_ERROR=$(echo "$INSPECT_INFO" | grep '"Error"' | head -1 | awk -F'"' '{print $4}')
                EXIT_CODE=$(echo "$INSPECT_INFO" | grep '"ExitCode"' | head -1 | awk -F':' '{print $2}' | awk -F',' '{print $1}' | tr -d ' ')
                
                echo -e "${PURPLE}  👉 Status: $CONTAINER_STATE${NC}"
                if [ -n "$CONTAINER_ERROR" ] && [ "$CONTAINER_ERROR" != "null" ] && [ "$CONTAINER_ERROR" != "" ]; then
                    echo -e "${RED}  👉 Error: $CONTAINER_ERROR${NC}"
                    debug_log "Container error: $CONTAINER_ERROR"
                fi
                if [ -n "$EXIT_CODE" ] && [ "$EXIT_CODE" != "0" ] && [ "$EXIT_CODE" != "null" ]; then
                    echo -e "${RED}  👉 Exit Code: $EXIT_CODE${NC}"
                    debug_log "Container exit code: $EXIT_CODE"
                fi
            fi
        else
            echo -e "${RED}  👉 Container not found in any state${NC}"
            debug_log "Container not found in docker ps -a"
        fi
        
        # Show compose logs as well
        echo -e "${BLUE}📋 Docker Compose logs:${NC}"
        COMPOSE_LOGS=$(docker compose --env-file .env.dev logs 2>&1 || echo "Unable to get compose logs")
        echo "$COMPOSE_LOGS" | tail -20 | while read line; do
            echo -e "${ORANGE}  👉 $line${NC}"
        done
        debug_log "Compose logs: $COMPOSE_LOGS"
    fi
else
    track_error "Cannot verify container - CONTAINER_NAME not set" "1"
fi

# Network verification
if [ -n "$NETWORK_NAME" ]; then
    echo -e "${BLUE}🌐 Verifying Docker network...${NC}"
    debug_log "=== NETWORK VERIFICATION ==="
    
    NETWORK_EXISTS=$(docker network ls --filter name=${NETWORK_NAME} --format "{{.Name}}" 2>/dev/null || echo "")
    if [ -n "$NETWORK_EXISTS" ]; then
        echo -e "${GREEN}✅ Network ${NETWORK_NAME} exists${NC}"
        debug_log "Network $NETWORK_NAME exists"
        
        # Get network details
        NETWORK_INFO=$(docker network inspect ${NETWORK_NAME} 2>/dev/null || echo "Unable to inspect network")
        if [ "$NETWORK_INFO" != "Unable to inspect network" ]; then
            NETWORK_DRIVER=$(echo "$NETWORK_INFO" | grep '"Driver"' | head -1 | awk -F'"' '{print $4}')
            echo -e "${PURPLE}  👉 Driver: $NETWORK_DRIVER${NC}"
            debug_log "Network driver: $NETWORK_DRIVER"
        fi
    else
        echo -e "${YELLOW}⚠️  Network ${NETWORK_NAME} not found${NC}"
        debug_log "Network $NETWORK_NAME not found"
    fi
fi

# Final summary with error report
echo ""
echo "============================================================="
if [ $ERRORS_FOUND -eq 0 ]; then
    echo -e "${GREEN}🎉 DEBUG Development Deployment Analysis Complete!${NC}"
    echo -e "${GREEN}✅ No errors detected during the process${NC}"
else
    echo -e "${YELLOW}🔍 DEBUG Development Deployment Analysis Complete!${NC}"
    echo -e "${RED}❌ Total errors found: $ERRORS_FOUND${NC}"
    echo -e "${YELLOW}⚠️  Check the debug log for detailed analysis${NC}"
fi
echo "============================================================="

# Display summary information
if [ -n "$CONTAINER_NAME" ]; then
    echo -e "${GREEN}📋 Configuration Summary:${NC}"
    echo -e "${GREEN}  👉 Container: ${CONTAINER_NAME:-'Not set'}${NC}"
    echo -e "${GREEN}  👉 Network: ${NETWORK_NAME:-'Not set'}${NC}"
    echo -e "${GREEN}  👉 Environment: ${ENVIRONMENT:-'Not set'}${NC}"
    echo -e "${GREEN}  👉 Bot Mode: ${BOT_MODE:-'Not set'}${NC}"
    if [ "$BOT_MODE" = "dev" ]; then
        echo -e "${GREEN}  👉 Hot-reload: Enabled (code changes will restart bot)${NC}"
    fi
fi

echo ""
echo -e "${BLUE}📝 Debug Information:${NC}"
echo -e "${ORANGE}  👉 Debug log: $DEBUG_LOG${NC}"
echo -e "${PURPLE}  👉 View full log: cat $DEBUG_LOG${NC}"

if [ $ERRORS_FOUND -gt 0 ]; then
    echo ""
    echo -e "${RED}🔧 Troubleshooting:${NC}"
    echo -e "${RED}  👉 Review the debug log for detailed error analysis${NC}"
    echo -e "${RED}  👉 Check system resources (disk space, memory)${NC}"
    echo -e "${RED}  👉 Verify Docker installation and permissions${NC}"
    echo -e "${RED}  👉 Validate .env.dev configuration${NC}"
fi

echo ""
echo -e "${BLUE}📝 Useful commands:${NC}"
echo -e "${PURPLE}  👉 View logs: make logs-dev${NC}"
echo -e "${PURPLE}  👉 Stop container: make stop-dev${NC}"
echo -e "${PURPLE}  👉 Check status: make status${NC}"
echo -e "${PURPLE}  👉 View debug log: cat $DEBUG_LOG${NC}"
echo -e "${PURPLE}  👉 Run normal deployment: ./deploy-dev.sh${NC}"

debug_log "Debug deployment script completed with $ERRORS_FOUND errors"

# Exit with error code if any errors were found (but only at the very end)
if [ $ERRORS_FOUND -gt 0 ]; then
    exit 1
else
    exit 0
fi