#!/bin/bash
# Start the Mac Assistant backend server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"

# Activate virtual environment if it exists
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

# Start the server
cd "$PROJECT_DIR"

# Parse arguments
HOST="${MAC_ASSISTANT_API_HOST:-127.0.0.1}"
PORT="${MAC_ASSISTANT_API_PORT:-8000}"
MODEL="${MAC_ASSISTANT_DEFAULT_MODEL:-qwen2.5-1.5b-instruct}"

echo "Starting Mac Assistant Backend..."
echo "  Host: $HOST"
echo "  Port: $PORT"
echo "  Model: $MODEL"
echo

# Ensure Foundry service is running
echo "Checking Foundry Local service..."
foundry service start 2>/dev/null || true

# Start the API server
exec python -m src.api.main
