# Getting Started

This guide will help you deploy and use the CAA Benchmark Harness

## Prerequisites

Ensure you have these tools installed:

```bash
aws --version          # AWS CLI
docker --version       # Docker
node --version         # Node.js (for CDK)
python3 --version      # Python 3.8+
kubectl version        # kubectl
```

## Quick Setup

### 1. Install Dependencies
```bash
make install
```

### 2. Configure AWS Account

**NOTE:** You may need to update any hardcoded account IDs. Search for `123456789999` and replace with your account ID using this sed command:

```bash
# Replace all occurrences of placeholder account ID with your actual account ID
find . -type f \( -name "*.py" -o -name "*.sh" -o -name "*.yaml" -o -name "*.yml" -o -name "*.json" \) -exec sed -i 's/123456789999/YOUR_ACCOUNT_ID/g' {} +
```

Find your AWS account ID:
```bash
aws sts get-caller-identity --query Account --output text
```

### 3. Deploy Everything
```bash
# Deploy infrastructure (EKS cluster, VPC, ECR)
make deploy-infra

# Build and push container images
make build-containers

# Deploy benchmarks to Kubernetes
make deploy-benchmarks
```

### 4. Verify Deployment
```bash
make status
```

## Using the Agent Runner

### Run CAA Agents
```bash
# List available benchmarks
make list-benchmarks

# Run agents against specific benchmarks
cd agent_runner
./run_agents.sh XBEN-001-24 XBEN-002-24 XBEN-003-24
```

### Analyze Results
```bash
# View flag discovery analysis for a results directory
make view-results DIR=agent_runner/results_1

# Example output:
# ✅ XBEN-001-24: FLAG FOUND - Found pattern: flag{85c0d827-5e28-4577-be2b-319bdcbf872d}
# ❌ XBEN-003-24: FLAG NOT FOUND - Flag not found in logs
# 📊 Success rate: 45.5%
```

## What You Get

### Infrastructure
- **EKS Cluster**: Kubernetes 1.31 with auto-scaling (20-100 nodes)
- **VPC**: 10.0.0.0/8 with massive IP space (65,534 IPs per subnet)
- **ECR**: Container repositories for all benchmark images

### Benchmarks
- **104 Benchmarks**: XBEN-001-24 through XBEN-104-24
- **130 Deployments**: Individual deployments for each component
- **Automatic Scaling**: Based on resource demand

### Agent Analysis
- **Flag Discovery Tracking**: Automatically detects successful flag extractions
- **Success Rate Reporting**: Shows percentage of successful benchmark completions
- **Detailed Logs**: Full agent execution logs for debugging

## Common Commands

```bash
# Check deployment status
kubectl get deployments -n benchmark-harness

# View running pods
kubectl get pods -n benchmark-harness

# Debug a specific pod
kubectl describe pod <pod-name> -n benchmark-harness
kubectl logs <pod-name> -n benchmark-harness

# Scale node groups
aws eks update-nodegroup-config --cluster-name benchmark-harness-cluster \
  --nodegroup-name PrimaryNodes --scaling-config desiredSize=50
```

## Troubleshooting

### Pods Stuck in Pending
Check node capacity:
```bash
kubectl describe nodes
kubectl get pods -n benchmark-harness -o wide
```

### ImagePullBackOff Errors
Rebuild and push images:
```bash
make build-containers
```

### Agent Failures
Check agent logs:
```bash
cd agent_runner
cat results_1/XBEN-001-24-logs.txt
```

## Cleanup

When finished, remove all resources:
```bash
make clean
```
