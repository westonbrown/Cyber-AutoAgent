# CAA Benchmark Harness

A simplified platform for running 104 cybersecurity benchmarks (XBEN-001-24 through XBEN-104-24) on AWS EKS. This version removes Helm complexity and uses direct YAML deployments with CDK infrastructure.

## Quick Start

```bash
# 1. Install dependencies
make install

# 2. Deploy infrastructure (EKS cluster, VPC, ECR)
make deploy-infra

# 3. Build and push all container images
make build-containers

# 4. Deploy all benchmarks to Kubernetes
make deploy-benchmarks

# 5. Check status
make status
```

## Agent Runner

Run CAA agents against benchmarks and analyze results:

```bash
# List available benchmarks
make list-benchmarks

# Run agents against specific benchmarks
cd agent_runner && ./run_agents.sh XBEN-001-24 XBEN-002-24

# Analyze flag discovery results
make view-results DIR=agent_runner/results_1
```

## Prerequisites

- AWS CLI configured with appropriate permissions
- Docker installed and running
- Node.js and npm (for CDK)
- Python 3.8+
- kubectl

## Configuration

**NOTE:** You may need to update any hardcoded account IDs. Search for `123456789999` and replace with your account ID using this sed command:

```bash
# Replace all occurrences of placeholder account ID with your actual account ID
find . -type f \( -name "*.py" -o -name "*.sh" -o -name "*.yaml" -o -name "*.yml" -o -name "*.json" \) -exec sed -i 's/123456789999/YOUR_ACCOUNT_ID/g' {} +
```

Find your AWS account ID:
```bash
aws sts get-caller-identity --query Account --output text
```

## Monitoring

```bash
# Check deployment status
kubectl get deployments -n benchmark-harness

# View pod status
kubectl get pods -n benchmark-harness

# Debug issues
kubectl describe pod <pod-name> -n benchmark-harness
kubectl logs <pod-name> -n benchmark-harness
```

## Cleanup

```bash
make clean
```


For detailed setup instructions, see [GETTING_STARTED.md](GETTING_STARTED.md).

## Future Improvements

### 1. Kubernetes Management
Migrate from direct YAML deployments to Helm charts for improved management and simplified deployment workflows. This would provide better templating, versioning, and rollback capabilities.

### 2. Dynamic Pod Lifecycle
Implement on-demand pod provisioning where benchmark containers are only created when agents need to test them, rather than maintaining all 130 deployments continuously. This would reduce resource costs and improve cluster efficiency. 