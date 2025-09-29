#!/bin/bash
# Deploy all benchmarks to Kubernetes cluster

set -e

SCRIPT_DIR="$(dirname "$0")"
DEPLOYMENTS_DIR="$SCRIPT_DIR/../deployments"

echo "=== Deploying CAA Benchmark Harness ==="

# Check if kubectl is configured
if ! kubectl cluster-info &>/dev/null; then
    echo "❌ kubectl is not configured or cluster is not accessible"
    echo "Please run: aws eks update-kubeconfig --region us-east-1 --name benchmark-harness-cluster"
    exit 1
fi

# Get cluster info
CLUSTER_NAME=$(kubectl config current-context | cut -d'/' -f2 2>/dev/null || echo "unknown")
echo "📋 Current cluster: $CLUSTER_NAME"

# Check if namespace exists, create if not
if ! kubectl get namespace benchmark-harness &>/dev/null; then
    echo "📦 Creating benchmark-harness namespace..."
    kubectl create namespace benchmark-harness
else
    echo "📦 Using existing benchmark-harness namespace"
fi

# Generate deployment manifests
echo "🔧 Generating deployment manifests..."
cd "$DEPLOYMENTS_DIR"
python3 generate_all_deployments.py

# Apply the manifests
echo "🚀 Deploying all 104 benchmarks..."
kubectl apply -f all-benchmarks-corrected.yaml

# Wait for deployments to be created
echo "⏳ Waiting for deployments to be created..."
sleep 10

# Check deployment status
echo "📊 Checking deployment status..."
TOTAL_DEPLOYMENTS=$(kubectl get deployments -n benchmark-harness --no-headers | wc -l)
READY_DEPLOYMENTS=$(kubectl get deployments -n benchmark-harness --no-headers | awk '$2 ~ /^[1-9]/ && $2 == $3 {count++} END {print count+0}')

echo ""
echo "=== Deployment Summary ==="
echo "Total Deployments: $TOTAL_DEPLOYMENTS"
echo "Ready Deployments: $READY_DEPLOYMENTS"
echo ""

# Show pod status
echo "📋 Pod Status Summary:"
kubectl get pods -n benchmark-harness --no-headers | awk '{print $3}' | sort | uniq -c | sort -nr

echo ""
echo "🎯 Deployment complete!"
echo ""
echo "To monitor the deployment:"
echo "  kubectl get pods -n benchmark-harness"
echo "  kubectl get deployments -n benchmark-harness"
echo "  kubectl get services -n benchmark-harness"
echo ""
echo "To check a specific benchmark:"
echo "  kubectl describe pod <pod-name> -n benchmark-harness"
echo "  kubectl logs <pod-name> -n benchmark-harness"