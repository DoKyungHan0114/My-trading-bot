#!/bin/bash

# TQQQ Trading System - Production Start Script
# Builds frontend and runs FastAPI serving static files

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  TQQQ Trading System (Production)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Cleanup
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    echo -e "${GREEN}Stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Check dependencies
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# Install Python dependencies
echo -e "${YELLOW}Checking Python dependencies...${NC}"
pip3 install fastapi uvicorn --quiet 2>/dev/null || true

# Build frontend if dist doesn't exist or --build flag
if [ ! -d "frontend/dist" ] || [ "$1" == "--build" ]; then
    echo -e "${YELLOW}Building frontend...${NC}"
    cd frontend
    npm install
    npm run build
    cd ..
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Server running on http://localhost:8000${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  Dashboard: ${YELLOW}http://localhost:8000${NC}"
echo -e "  API Docs:  ${YELLOW}http://localhost:8000/docs${NC}"
echo ""
echo -e "  Press ${RED}Ctrl+C${NC} to stop"
echo ""

# Run server
python3 api.py
