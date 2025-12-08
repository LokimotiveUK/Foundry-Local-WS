#!/bin/bash
# Mac Assistant Installation Script

set -e

echo "==================================="
echo "  Mac Desktop AI Assistant Setup"
echo "==================================="
echo

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "Error: Homebrew not found. Please install Homebrew first:"
    echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Installing Python 3..."
    brew install python@3.11
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# Check Python version
if [[ $(echo "$PYTHON_VERSION < 3.10" | bc -l) -eq 1 ]]; then
    echo "Error: Python 3.10+ required. Found: $PYTHON_VERSION"
    exit 1
fi

# Check for Foundry Local
if ! command -v foundry &> /dev/null; then
    echo "Installing Foundry Local..."
    brew install microsoft/foundrylocal/foundrylocal
else
    echo "Foundry Local already installed"
fi

# Create virtual environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -e "$PROJECT_DIR"

# Create app directory
APP_DIR="$HOME/.mac-assistant"
mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/qdrant"

echo
echo "==================================="
echo "  Installation Complete!"
echo "==================================="
echo
echo "Next steps:"
echo
echo "1. Activate the virtual environment:"
echo "   source $VENV_DIR/bin/activate"
echo
echo "2. Download a model:"
echo "   foundry model download qwen2.5-1.5b-instruct"
echo
echo "3. Start the server:"
echo "   python -m src.api.main"
echo
echo "4. Or use the CLI:"
echo "   mac-assistant serve"
echo "   mac-assistant chat"
echo
