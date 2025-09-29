#!/bin/bash
# Deploy the EKS infrastructure using CDK

set -e

SCRIPT_DIR="$(dirname "$0")"
INFRASTRUCTURE_DIR="$SCRIPT_DIR/../infrastructure"

echo "=== Deploying CAA Benchmark Harness Infrastructure ==="

# Check if CDK is installed
if ! command -v cdk &> /dev/null; then
    echo "❌ AWS CDK is not installed"
    echo "Please install it with: npm install -g aws-cdk"
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ AWS credentials are not configured"
    echo "Please configure AWS credentials with: aws configure"
    exit 1
fi

# Get AWS account and region
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")

echo "📋 AWS Account: $AWS_ACCOUNT"
echo "📋 AWS Region: $AWS_REGION"

# Navigate to infrastructure directory
cd "$INFRASTRUCTURE_DIR"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Bootstrap CDK if needed
echo "🔧 Bootstrapping CDK (if needed)..."
cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION

# Deploy the stack
echo "🚀 Deploying infrastructure stack..."
cdk deploy --require-approval never --context account=$AWS_ACCOUNT --context region=$AWS_REGION

# Get cluster name from CDK output
CLUSTER_NAME="benchmark-harness-cluster"

echo ""
echo "=== Infrastructure Deployment Complete ==="
echo ""
echo "🎯 EKS Cluster: $CLUSTER_NAME"
echo "🌐 Region: $AWS_REGION"
echo ""
echo "To configure kubectl:"
echo "  aws eks update-kubeconfig --region $AWS_REGION --name $CLUSTER_NAME"
echo ""
echo "To check cluster status:"
echo "  kubectl cluster-info"
echo "  kubectl get nodes"
echo ""
echo "Next steps:"
echo "  1. Configure kubectl (command above)"
echo "  2. Build container images: ./scripts/build_all_containers.sh"
echo "  3. Deploy benchmarks: ./scripts/deploy_benchmarks.sh"