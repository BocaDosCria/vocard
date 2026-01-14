#!/bin/bash

# Vocard Startup Script (Bash version)
# Simpler alternative to start.py

set -e

# Configuration
LAVALINK_HOST="localhost"
LAVALINK_PORT=2333
LAVALINK_PASSWORD="youshallnotpass"
MAX_WAIT_TIME=120
CHECK_INTERVAL=2

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Vocard Startup Script          ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo ""

# Function to check if port is in use
check_port() {
    nc -z "$LAVALINK_HOST" "$LAVALINK_PORT" 2>/dev/null
    return $?
}

# Function to check Lavalink health
check_lavalink_health() {
    curl -s -H "Authorization: $LAVALINK_PASSWORD" \
         "http://$LAVALINK_HOST:$LAVALINK_PORT/version" \
         --max-time 5 >/dev/null 2>&1
    return $?
}

# Check if requirements are installed
echo -e "${CYAN}📦 Checking Python environment...${NC}"
if ! python3 -c "import discord, voicelink" 2>/dev/null; then
    echo -e "${YELLOW}⚠ Dependencies might be missing${NC}"
    echo -e "  Run: python3 -m pip install -r requirements.txt"
    echo ""
    read -p "Install dependencies now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python3 -m pip install -r requirements.txt
    else
        echo -e "${RED}✗ Please install dependencies before continuing${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Python environment ready${NC}"
echo ""

# Check if Lavalink is running
if check_port; then
    echo -e "${GREEN}✓ Lavalink is already running on port $LAVALINK_PORT${NC}"
    
    if check_lavalink_health; then
        echo -e "${GREEN}✓ Lavalink health check passed${NC}"
    else
        echo -e "${YELLOW}⚠ Port is in use but health check failed${NC}"
        echo -e "  Continuing anyway..."
    fi
else
    echo -e "${YELLOW}⚠ Lavalink not detected on port $LAVALINK_PORT${NC}"
    echo -e "${CYAN}🐳 Starting Lavalink with Docker Compose...${NC}"
    
    # Check if docker is available
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker not found on system${NC}"
        echo -e "Please start Lavalink manually or install Docker"
        exit 1
    fi
    
    # Start Lavalink in detached mode
    docker compose up -d lavalink
    
    echo -e "${CYAN}⏳ Waiting for Lavalink to be ready...${NC}"
    
    # Wait for Lavalink to be ready
    elapsed=0
    while [ $elapsed -lt $MAX_WAIT_TIME ]; do
        if check_lavalink_health; then
            echo -e "${GREEN}✓ Lavalink is ready!${NC}"
            break
        fi
        
        sleep $CHECK_INTERVAL
        elapsed=$((elapsed + CHECK_INTERVAL))
        
        # Print progress every 10 seconds
        if [ $((elapsed % 10)) -eq 0 ]; then
            echo -e "${YELLOW}  Still waiting... (${elapsed}s / ${MAX_WAIT_TIME}s)${NC}"
        fi
    done
    
    if [ $elapsed -ge $MAX_WAIT_TIME ]; then
        echo -e "${RED}✗ Lavalink did not become ready within ${MAX_WAIT_TIME} seconds${NC}"
        echo -e "Check logs with: docker compose logs lavalink"
        exit 1
    fi
fi

# Start the bot
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}🤖 Starting Vocard Discord Bot...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

python3 main.py
