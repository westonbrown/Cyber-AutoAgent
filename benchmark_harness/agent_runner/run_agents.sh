#!/bin/bash

# CAA Agent Runner - Shell wrapper script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🐉 CAA Agent Runner"
echo "=================="

# Check if Python script exists
if [ ! -f "$SCRIPT_DIR/run_agents.py" ]; then
    echo "❌ run_agents.py not found in $SCRIPT_DIR"
    exit 1
fi

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed or not in PATH"
    exit 1
fi

# Check if we can connect to cluster
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster"
    echo "Please run: aws eks update-kubeconfig --region us-east-1 --name benchmark-harness-cluster"
    exit 1
fi

# Check if bedrock credentials exist
if [ ! -f "$SCRIPT_DIR/.env.bedrock" ]; then
    echo "❌ .env.bedrock file not found"
    echo "Please create $SCRIPT_DIR/.env.bedrock with your AWS credentials"
    exit 1
fi

# Run the Python script with all arguments
echo "🚀 Starting agent runner..."
python3 "$SCRIPT_DIR/run_agents.py" "$@"