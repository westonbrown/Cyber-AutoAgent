# CAA Test Harness

A comprehensive testing framework for evaluating the Cyber-AutoAgent (CAA) against XBOW vulnerability benchmarks.

## Overview

The CAA Test Harness provides an automated environment for testing cybersecurity agents against standardized vulnerability benchmarks. When built on AWS CDK, it provisions a Kali Linux EC2 instance optimized for security testing and agent evaluation.

## Architecture

```mermaid
graph TB
    %% ───────────────────────── AWS FOOTPRINT ─────────────────────────
    subgraph "AWS Cloud"
        %% VPC + networking
        subgraph "VPC"
            subgraph "Public Subnet"
                SG[Security Group<br/>SSH Ingress]

                %% EC2 host with internal Docker Engine
                subgraph EC2_ENV["Kali Linux EC2 Instance<br/>(t3.large • 100 GB EBS)"]
                    EC2OS[Kali Linux OS]

                    %% Docker Engine & containers live INSIDE the EC2 instance
                    subgraph "Docker Engine"
                        XBEN1[XBEN-001-24<br/>Vulnerability Benchmark]
                        XBEN2[XBEN-002-24<br/>Vulnerability Benchmark]
                        XBENN[XBEN-XXX-XX<br/>Additional Benchmarks]
                    end
                end
            end
            IGW[Internet Gateway]
        end

        %% IAM permissions the instance can assume
        subgraph "IAM"
            ROLE[EC2 Instance Role]
            BEDROCK[Bedrock Permissions]
            CW[CloudWatch Logs]
            SSM[SSM Managed Instance]
        end

        %% Parameter Store
        subgraph "Parameter Store"
            KEY[SSH Private Key]
        end
    end

    %% ───────────────────────── SOFTWARE LAYERS ─────────────────────────
    subgraph "Agent Framework (on EC2)"
        VENV[Python Virtual Env<br/>Dependencies]
        CAA[Cyber-AutoAgent<br/>Python Application]
    end

    subgraph "Results"
        JSON[JSON Results]
        LOGS[Execution Logs]
        SUMMARY[Summary Report]
    end

    subgraph "Scripts"
        SETUP[setup_environment.sh]
        RUN[run_benchmarks.py]
        CLEAN[clean_environment.sh]
    end

    %% ───────────────────────── RELATIONSHIPS / FLOWS ─────────────────────────
    SG --> EC2OS
    KEY --> EC2OS
    EC2OS --> ROLE
    ROLE --> BEDROCK
    ROLE --> CW
    ROLE --> SSM

    %% Agent ↔ Benchmarks inside Docker
    CAA --> XBEN1
    CAA --> XBEN2
    CAA --> XBENN

    %% Scripts lifecycle
    SETUP --> VENV
    SETUP --> CAA
    RUN --> CAA
    RUN --> JSON
    RUN --> LOGS
    JSON --> SUMMARY
    CLEAN --> XBEN1
    CLEAN --> XBEN2
    CLEAN --> XBENN
```

## Features

- **Automated Benchmarking**: Python-based orchestration of XBOW vulnerability benchmarks
- **Scalable Testing**: Containerized benchmark environments with Docker
- **Comprehensive Reporting**: JSON-based results with detailed execution metrics
- **Security-First Design**: Kali Linux with pre-installed security tools and AWS Bedrock integration

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate permissions
- AWS CDK v2 installed
- Python 3.8+ with pip

### 1. Deploy Infrastructure

```bash
# Install dependencies
pip install -r requirements.txt

# Deploy the CDK stack
cdk deploy

# Retrieve SSH key (if auto-generated)
aws ssm get-parameter --name /caa-test-harness/ssh-key --with-decryption --query Parameter.Value --output text > ~/.ssh/caa-test-key.pem
chmod 600 ~/.ssh/caa-test-key.pem
```

### 2. Connect to Instance

```bash
# SSH into the Kali instance
ssh -i ~/.ssh/caa-test-key.pem kali@<INSTANCE_PUBLIC_IP>
```

### 3. Setup Environment

```bash
# Run the setup script to install all requirements
./scripts/setup_environment.sh
```

### 4. Execute Benchmarks

```bash
# Run all available benchmarks
./scripts/run_benchmarks.py

# Run specific benchmarks
./scripts/run_benchmarks.py --benchmarks XBEN-001-24,XBEN-002-24

# List available benchmarks
./scripts/run_benchmarks.py --list
```

### 5. Cleanup

```bash
# Clean Docker resources and results
./scripts/clean_environment.sh --all
```

## Scripts Reference

### `setup_environment.sh`

Prepares the Kali Linux environment with all necessary dependencies:

- Updates system packages
- Installs security tools (nmap, nikto, sqlmap, gobuster, etc.)
- Configures Docker and Docker Compose
- Sets up Python virtual environment
- Clones required repositories (validation-benchmarks, Cyber-AutoAgent)
- Installs Cyber-AutoAgent with dependencies

### `run_benchmarks.py`

Orchestrates the benchmark testing process:

**Usage:**
```bash
python run_benchmarks.py [OPTIONS]

Options:
  --benchmarks BENCHMARK_IDS    Comma-separated list of benchmark IDs
  --list                       List all available benchmarks
  --flag FLAG_VALUE           Custom flag value for benchmarks
```

**Features:**
- Automated Docker container management
- Parallel benchmark execution
- Real-time progress monitoring
- Comprehensive result collection
- JSON-formatted output with metadata

### `clean_environment.sh`

Manages cleanup of Docker resources and test artifacts:

**Usage:**
```bash
./clean_environment.sh [OPTIONS]

Options:
  -a, --all         Remove all Docker resources and results
  -c, --containers  Remove only stopped containers
  -i, --images      Remove dangling images
  -v, --volumes     Remove unused volumes
  -r, --results     Clean results directory
```

## Results and Reporting

### Output Structure

```
~/cyber-autoagent-test/results/
├── XBEN-001-24_result.json
├── XBEN-002-24_result.json
├── summary_20241201_143022.json
└── benchmark_results.log
```

### Result Format

Each benchmark generates a detailed JSON result:

```json
{
  "benchmark_id": "XBEN-001-24",
  "target_url": "http://localhost:8080",
  "timestamp": "2024-12-01T14:30:22",
  "metadata": {
    "title": "SQL Injection Vulnerability",
    "description": "Test SQL injection detection and exploitation",
    "tags": "sql-injection,web-security"
  },
  "success": true,
  "flag_found": true,
  "extracted_flag": "caa_flag{a1b2c3d4-e5f6-7890-abcd-ef1234567890}",
  "duration": 45.67,
  "return_code": 0
}
```

### Summary Reports

Aggregate reports provide:
- Overall success rates
- Performance metrics
- Vulnerability type breakdown
- Execution statistics

## Infrastructure Details

### EC2 Instance Specifications

- **Instance Type**: t3.large (2 vCPU, 8 GB RAM)
- **Storage**: 100 GB GP3 EBS volume
- **OS**: Kali Linux (latest AMI)
- **Network**: Public subnet with Internet Gateway

### Security Configuration

- **IAM Role**: EC2 instance role with Bedrock and CloudWatch permissions
- **Security Group**: SSH access (port 22) from any IP
- **SSM**: Managed instance for secure access
- **Key Management**: SSH keys stored in Parameter Store

### Cost Optimization

- Single AZ deployment
- No NAT Gateway (public subnet only)
- GP3 storage for cost-effective performance
- Instance can be stopped when not in use

## Development and Customization

### Adding New Benchmarks

1. Place benchmark in `~/cyber-autoagent-test/validation-benchmarks/benchmarks/`
2. Ensure `benchmark.json` metadata file exists
3. Include `docker-compose.yml` for containerization
4. Run `./scripts/run_benchmarks.py --list` to verify detection

### Modifying Agent Configuration

Edit the agent execution parameters in `run_benchmarks.py`:

```python
# Adjust timeout, iterations, or other parameters
process = subprocess.run([
    python_exe,
    cyberautoagent_path,
    "--target", target_url,
    "--objective", objective,
    "--iterations", "50"  # Modify as needed
], ...)
```

### Custom Flag Values

Use custom flags for benchmark testing:

```bash
./scripts/run_benchmarks.py --flag "custom_flag{test-value}"
```

## Troubleshooting

### Common Issues

1. **Docker Permission Denied**
   ```bash
   sudo usermod -aG docker $USER
   # Log out and log back in
   ```

2. **Python Module Not Found**
   ```bash
   source ~/cyber-autoagent-test/venv/bin/activate
   pip install -e ~/cyber-autoagent-test/Cyber-AutoAgent
   ```

3. **Benchmark Container Fails to Start**
   ```bash
   # Check Docker logs
   docker-compose logs
   
   # Rebuild container
   make build
   ```

### Logs and Debugging

- **Benchmark Logs**: `~/cyber-autoagent-test/benchmark_results.log`
- **Docker Logs**: `docker-compose logs` in benchmark directory
- **Agent Output**: Captured in individual result JSON files