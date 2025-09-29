# CAA Agent Runner

A simple system to run CAA (Cyber Auto Agent) against benchmark challenges with proper concurrency control and result collection.

## Features

- ✅ Run CAA agents against specific benchmarks
- ✅ Concurrency control (default: 5 concurrent jobs)
- ✅ Automatic result collection and log preservation
- ✅ Job cleanup after completion
- ✅ Kubernetes secret management for Bedrock credentials
- ✅ Simple command-line interface

## Prerequisites

1. **Kubernetes cluster** with benchmark deployments running
2. **kubectl** configured to access the cluster
3. **Python 3** installed
4. **Bedrock credentials** in `.env.bedrock` file

## Setup

1. **Create Bedrock credentials file**:
   ```bash
   cat > .env.bedrock << EOF
   export AWS_ACCESS_KEY_ID=your_access_key_here
   export AWS_SECRET_ACCESS_KEY=your_secret_key_here
   EOF
   ```

2. **Ensure cluster access**:
   ```bash
   aws eks update-kubeconfig --region us-east-1 --name benchmark-harness-cluster
   kubectl get pods -n benchmark-harness
   ```

## Usage

### Basic Usage

Run agents against specific benchmarks:

```bash
# Run against single benchmark
./run_agents.sh XBEN-001-24

# Run against multiple benchmarks
./run_agents.sh XBEN-001-24 XBEN-002-24 XBEN-003-24

# Run with custom concurrency
./run_agents.sh --max-concurrent 3 XBEN-001-24 XBEN-002-24

# Run sample benchmarks with hints (easier testing)
make run-sample
# or
python3 run_agents.py --sample-run XBEN-001-24 XBEN-002-24
```

### Python Script Direct Usage

```bash
# Basic usage
python3 run_agents.py XBEN-001-24 XBEN-002-24

# With options
python3 run_agents.py --max-concurrent 3 --namespace benchmark-harness XBEN-001-24
```

### Command Line Options

- `--max-concurrent N` - Maximum concurrent jobs (default: 5)
- `--namespace NAME` - Kubernetes namespace (default: benchmark-harness)
- `--sample-run` - Enable sample run mode with hints for easier testing

## How It Works

1. **Job Creation**: Creates a Kubernetes Job for each benchmark
2. **Target Resolution**: Looks up internal endpoint from `ctf_endpoints_internal.json`
3. **Objective Generation**: Creates detailed objectives including:
   - Benchmark description from endpoints JSON
   - Proper tags and context
   - Hints for sample runs (XBEN-001-24, XBEN-002-24)
4. **Credential Injection**: Creates Kubernetes secret with Bedrock credentials
5. **Execution**: Runs CAA agent with proper objective and parameters
6. **Result Collection**: Collects logs and results before cleanup
7. **Cleanup**: Removes completed jobs to keep cluster clean

### Sample Run Mode

When using `--sample-run` or `make run-sample`, the system adds helpful hints:

- **XBEN-001-24**: Includes credentials (test:test) and flag path (/order/300401/receipt)
- **XBEN-002-24**: Includes credentials (test:test) and IDOR guidance
- **Other benchmarks**: No hints added (normal difficulty)

## Job Naming

Jobs are named using the pattern: `{benchmark-id-lower}-agent`

Examples:
- `XBEN-001-24` → `xben-001-24-agent`
- `XBEN-002-24` → `xben-002-24-agent`

## Results

Results are saved in the `results/` directory:

```
results/
├── XBEN-001-24-logs.txt           # Agent stdout logs
├── XBEN-001-24-result.json        # Result summary
├── XBEN-002-24-logs.txt
├── XBEN-002-24-result.json
├── xben-001-24-agent-job.yaml     # Job manifest
├── xben-002-24-agent-job.yaml
└── run-summary.json               # Overall run summary
```

### Result JSON Format

```json
{
  "benchmark_id": "XBEN-001-24",
  "status": "completed",
  "timestamp": 1234567890.123,
  "logs": "Full agent output...",
  "results_files": []
}
```

### Run Summary Format

```json
{
  "timestamp": 1234567890.123,
  "total_benchmarks": 2,
  "completed": 2,
  "failed": 0,
  "results": [...]
}
```

## Configuration

Edit `config.yaml` to customize:

- Agent image and settings
- Bedrock model and parameters
- Resource limits
- Kubernetes settings

## Troubleshooting

### Common Issues

1. **"Cannot connect to Kubernetes cluster"**
   ```bash
   aws eks update-kubeconfig --region us-east-1 --name benchmark-harness-cluster
   ```

2. **"No endpoint found for benchmark"**
   - Check that the benchmark ID exists in `ctf_endpoints_internal.json`
   - Ensure the benchmark is deployed and running

3. **"Failed to create job"**
   - Check cluster resources: `kubectl top nodes`
   - Verify namespace exists: `kubectl get namespace benchmark-harness`

4. **Jobs timeout**
   - Check agent logs: `kubectl logs -n benchmark-harness -l app=caa-agent`
   - Verify benchmark targets are accessible from within cluster

### Monitoring

```bash
# Check running jobs
kubectl get jobs -n benchmark-harness -l app=caa-agent

# Check job pods
kubectl get pods -n benchmark-harness -l app=caa-agent

# View agent logs (while running)
kubectl logs -n benchmark-harness -l app=caa-agent -f

# Check cluster resources
kubectl top nodes
kubectl top pods -n benchmark-harness
```

## Examples

### Run a single benchmark
```bash
./run_agents.sh XBEN-001-24
```

### Run multiple benchmarks with limited concurrency
```bash
./run_agents.sh --max-concurrent 2 XBEN-001-24 XBEN-002-24 XBEN-003-24
```

### Run all IDOR benchmarks (example)
```bash
./run_agents.sh XBEN-001-24 XBEN-002-24 XBEN-003-24 XBEN-027-24 XBEN-043-24
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   run_agents.py │───▶│ Kubernetes Jobs  │───▶│ CAA Agent Pods  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Results Storage │    │ Bedrock Secret   │    │ Benchmark Pods  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

The system creates individual Kubernetes Jobs for each benchmark, with proper resource limits, credential injection, and result collection.