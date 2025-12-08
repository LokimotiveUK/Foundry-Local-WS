#!/bin/bash
#
# Mac Assistant - Combined Launcher
# Starts both the backend API and desktop UI
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║       Mac Assistant Launcher             ║"
echo "║   Local AI with RAG Capabilities         ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

# Check for Node.js
if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: Node.js/npm is required but not installed.${NC}"
    echo "Install with: brew install node"
    exit 1
fi

# Check for Foundry Local
if ! command -v foundry &> /dev/null; then
    echo -e "${YELLOW}Warning: Foundry Local not found in PATH.${NC}"
    echo "Install with: brew install microsoft/foundrylocal/foundrylocal"
fi

# Check Python dependencies
echo -e "${BLUE}Checking Python dependencies...${NC}"
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip install -e . --quiet
fi

# Check Electron dependencies
echo -e "${BLUE}Checking Electron dependencies...${NC}"
if [ ! -d "desktop/electron/node_modules" ]; then
    echo -e "${YELLOW}Installing Electron dependencies...${NC}"
    cd desktop/electron
    npm install --silent
    cd ../..
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down Mac Assistant...${NC}"
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}Goodbye!${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend
echo -e "${GREEN}Starting backend API server...${NC}"
python3 -m src.api.main &
BACKEND_PID=$!

# Wait for backend to start
echo -e "${BLUE}Waiting for API to be ready...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}Backend ready!${NC}"
        break
    fi
    sleep 1
done

# Check if backend started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}Failed to start backend. Check logs above.${NC}"
    exit 1
fi

# Start desktop UI
echo -e "${GREEN}Starting desktop UI...${NC}"
cd desktop/electron
npm start &
FRONTEND_PID=$!
cd ../..

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════╗"
echo "║   Mac Assistant is running!              ║"
echo "║                                          ║"
echo "║   API:     http://localhost:8000         ║"
echo "║   Docs:    http://localhost:8000/docs    ║"
echo "║                                          ║"
echo "║   Press Ctrl+C to stop                   ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# Wait for either process to exit
wait $BACKEND_PID $FRONTEND_PID
