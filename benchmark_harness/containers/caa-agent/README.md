# CAA Agent Container

This directory contains the Docker container configuration for the Cyber Auto Agent (CAA) used in the benchmark harness.

## Files

- `Dockerfile` - Container definition with all dependencies and security tools
- `entrypoint.sh` - Entry point script that sets up the environment and runs CAA
- `build.sh` - Build script for the container
- `README.md` - This file

## Building

To build the container locally:

```bash
./build.sh
```

To build and push to ECR:

```bash
export REGISTRY="980989823532.dkr.ecr.us-east-1.amazonaws.com"
./build.sh
docker push $REGISTRY/caa-agent:latest
```

## Usage

The container can be run in several modes:

### Help Mode (default)
```bash
docker run --rm caa-agent:latest
```

### Direct CAA execution
```bash
docker run --rm caa-agent:latest --target http://example.com --objective "Find vulnerabilities"
```

### Test Mode
```bash
docker run --rm caa-agent:latest test http://target.com "Custom objective"
```

### Benchmark Mode
```bash
docker run --rm caa-agent:latest benchmark XBEN-001-24
```

## Environment Variables

- `CYBER_UI_MODE` - UI mode (default: cli)
- `BYPASS_TOOL_CONSENT` - Bypass tool consent prompts (default: true)
- `DEV` - Development mode (default: true)
- `PYTHONPATH` - Python path (default: /app/src)

## Security Tools Included

- nmap - Network scanning
- nikto - Web vulnerability scanner
- sqlmap - SQL injection testing
- hydra - Password cracking
- dirb - Directory/file brute forcing
- Various Python security libraries

## Architecture

The container is based on Ubuntu 22.04 and includes:

1. Python 3.10 with security libraries
2. CAA source code from the feature/terminal_react_ink branch
3. Security tools and utilities
4. Non-root user (caa-agent) for security
5. Proper entrypoint handling for different execution modes