#!/bin/bash

# Terminal Stream Tests Runner
# 
# Executes terminal stream logic tests with real PTY output
# to validate event processing and display formatting.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../../../../../.." && pwd)"
VENV_PATH="$PROJECT_ROOT/.venv"

echo "═══════════════════════════════════════════════════════════"
echo "   Terminal Stream Logic Test Suite"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Project Root: $PROJECT_ROOT"
echo "Virtual Environment: $VENV_PATH"
echo ""

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at $VENV_PATH"
    echo "   Please set up the Python environment first."
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating Python virtual environment..."
source "$VENV_PATH/bin/activate"

# Install Node dependencies if needed
echo "🔧 Checking Node.js dependencies..."
cd "$SCRIPT_DIR/../.."
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node.js dependencies..."
    npm install
fi

# Run the terminal stream tests
echo ""
echo "🚀 Running Terminal Stream Tests..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Execute the test suite with verbose output
node "$SCRIPT_DIR/terminal-stream-tests.js" --verbose

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All terminal stream tests passed!"
else
    echo ""
    echo "❌ Some tests failed. Please review the output above."
    exit 1
fi