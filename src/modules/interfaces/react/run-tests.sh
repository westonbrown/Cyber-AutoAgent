#!/bin/bash

# Test Runner Script for Cyber-AutoAgent React CLI
# Handles ES module configuration and runs tests

echo "🧪 Running Cyber-AutoAgent UI Tests..."
echo "=================================="

# Set NODE_OPTIONS for ES modules
export NODE_OPTIONS="--experimental-vm-modules"

# Change to tests directory
cd tests

# Run specific test file if provided, otherwise run all
if [ -n "$1" ]; then
    echo "Running test: $1"
    npx jest "$1" --config jest.config.js --forceExit
else
    echo "Running all tests..."
    npx jest --config jest.config.js --forceExit
fi

echo "=================================="
echo "✅ Test run complete"