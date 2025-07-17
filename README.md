![Cyber-AutoAgent Cover Art](docs/cover_art.png)

<div align="center">

![GitHub License](https://img.shields.io/github/license/westonbrown/Cyber-AutoAgent?style=flat-square)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/westonbrown/Cyber-AutoAgent?style=flat-square)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/westonbrown/Cyber-AutoAgent/ci.yml?branch=main&style=flat-square)
![GitHub issues](https://img.shields.io/github/issues/westonbrown/Cyber-AutoAgent?style=flat-square)
![GitHub pull requests](https://img.shields.io/github/issues-pr/westonbrown/Cyber-AutoAgent?style=flat-square)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/westonbrown/Cyber-AutoAgent?style=flat-square)
![GitHub contributors](https://img.shields.io/github/contributors/westonbrown/Cyber-AutoAgent?style=flat-square)
![GitHub stars](https://img.shields.io/github/stars/westonbrown/Cyber-AutoAgent?style=flat-square)
![GitHub forks](https://img.shields.io/github/forks/westonbrown/Cyber-AutoAgent?style=flat-square)

**[!] EXPERIMENTAL SOFTWARE - USE ONLY IN AUTHORIZED, SAFE, SANDBOXED ENVIRONMENTS [!]**

<h3>Proactive Cybersecurity Autonomous Agent Powered by AI</h3>

<p>
  <strong>Cyber-AutoAgent</strong> is a proactive security assessment tool that autonomously conducts intelligent penetration testing with natural language reasoning, dynamic tool selection, and evidence collection using AWS Bedrock or local Ollama models with the Strands framework.
</p>

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker&style=for-the-badge)](https://hub.docker.com/r/cyberautoagent/cyber-autoagent)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow?logo=python&style=for-the-badge)](https://www.python.org)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-orange?logo=amazon-aws&style=for-the-badge)](https://aws.amazon.com/bedrock/)
[![Ollama](https://img.shields.io/badge/Ollama-Local_AI-green?style=for-the-badge)](https://ollama.ai)

</div>

---

![Demo GIF](docs/agent_demo.gif)

<div align="center">
  <em>Cyber-AutoAgent in action - Autonomous security assessment with AI reasoning</em>
</div>

---

## Table of Contents

- [Important Disclaimer](#important-disclaimer)
- [Features](#features)
- [Architecture](#architecture)
- [Model Providers](#model-providers)
- [Observability](#observability)
- [Installation & Deployment](#installation--deployment)
- [Quick Start](#quick-start)
- [Development & Testing](#development--testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Documentation

- **[Agent Architecture](docs/architecture.md)** - Strands framework, tools, and metacognitive design
- **[Memory System](docs/memory.md)** - Mem0 backends, storage, and evidence management  
- **[Observability & Evaluation](docs/observability-evaluation.md)** - Langfuse tracing, Ragas metrics, and performance monitoring
- **[Deployment Guide](docs/deployment.md)** - Docker, Kubernetes, and production setup

---

## Quick Start

```bash
# Using Docker (Recommended)
docker run --rm \
  -v ~/.aws:/home/cyberagent/.aws:ro \
  -v $(pwd)/outputs:/app/outputs \
  cyber-autoagent \
  --target "http://testphp.vulnweb.com" \
  --objective "Identify SQL injection vulnerabilities"

# Using Python
git clone https://github.com/cyber-autoagent/cyber-autoagent.git
cd cyber-autoagent
pip install -e .
python src/cyberautoagent.py --target "192.168.1.100" --objective "Comprehensive security assessment"
```

## Important Disclaimer

**THIS TOOL IS FOR EDUCATIONAL AND AUTHORIZED SECURITY TESTING PURPOSES ONLY.**

- [+] Use only on systems you own or have explicit written permission to test
- [+] Deploy in safe, sandboxed environments isolated from production systems  
- [+] Ensure compliance with all applicable laws and regulations
- [-] Never use on unauthorized systems or networks
- [-] Users are fully responsible for legal and ethical use

## Features

- **Autonomous Operation**: Conducts security assessments with minimal human intervention
- **Intelligent Tool Selection**: Automatically chooses appropriate security tools (nmap, sqlmap, nikto, etc.)
- **Natural Language Reasoning**: Uses Strands framework with metacognitive architecture
- **Evidence Collection**: Automatically stores findings with Mem0 memory (category="finding")
- **Meta-Tool Creation**: Dynamically creates custom exploitation tools when needed
- **Adaptive Execution**: Metacognitive assessment guides strategy based on confidence levels
- **Professional Reporting**: Generates comprehensive assessment reports
- **Swarm Intelligence**: Deploy parallel agents with shared memory for complex tasks

## Architecture

> **[Full Architecture Guide](docs/architecture.md)** - Complete technical deep dive into Strands framework, tools, and metacognitive design

### System Architecture

```mermaid
graph LR
    A[User Input<br/>Target & Objective] --> B[Cyber-AutoAgent]
    B --> C[AI Models<br/>Remote/Local]
    B --> D[Agent Tools<br/>shell, swarm, editior, etc.]
    B --> E[Evidence Storage<br/>Memory System]
    B --> O[Observability<br/>Langfuse + Ragas]
    
    C --> B
    D --> E
    E --> F[Final Report<br/>AI Generated]
    O --> G[Performance<br/>Metrics]
    
    style A fill:#e3f2fd
    style F fill:#e8f5e8
    style B fill:#f3e5f5
    style C fill:#fff3e0
    style O fill:#e1f5fe
    style G fill:#f1f8e9
```

**Key Components:**
- **User Interface**: Command-line interface with target and objective specification
- **Agent Core**: Strands framework orchestration with metacognitive reasoning and tool selection
- **AI Models**: GenAI tool use models (AWS Bedrock remote) or local models (Ollama) 
- **Security Tools**: Pentesting tools (nmap, sqlmap, nikto, metasploit, custom tools, etc.)
- **Evidence Storage**: Persistent memory with FAISS, OpenSearch, or Mem0 Platform backends
- **Observability**: Real-time tracing with Langfuse and automated evaluation with Ragas metrics

### Assessment Execution Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent
    participant M as AI Model
    participant T as Tools
    participant E as Evidence
    participant L as Observability
    participant R as Evaluator

    U->>A: Start Assessment
    A->>L: Initialize Trace
    A->>E: Initialize Storage
    
    loop Assessment Steps
        A->>M: Analyze Situation
        M-->>A: Next Action
        A->>L: Log Decision
        A->>T: Execute Tool
        T-->>A: Results
        A->>L: Log Tool Execution
        A->>E: Store Findings
        A->>L: Log Evidence Storage
        
        alt Critical Discovery
            A->>T: Exploit Immediately
            T-->>A: Access Gained
            A->>E: Store Evidence
            A->>L: Log Exploitation
        end
        
        A->>A: Check Progress
        
        alt Success
            break Complete
                A->>U: Report Success
            end
        end
    end
    
    A->>M: Generate Report
    M-->>A: Final Analysis
    A->>L: Complete Trace
    A->>R: Trigger Evaluation
    R-->>L: Upload Scores
    A->>U: Deliver Report
```

**Enhanced Execution Pattern:**
- **Real-time Monitoring**: Every action traced for complete visibility
- **Intelligent Analysis**: Agent continuously analyzes situation using metacognitive reasoning
- **Dynamic Tool Selection**: Chooses appropriate tools based on confidence and findings
- **Evidence Collection**: All discoveries stored in persistent memory with categorization
- **Immediate Exploitation**: Critical vulnerabilities trigger immediate exploitation attempts
- **Automated Evaluation**: System scores tool selection, evidence quality, and methodology
- **Comprehensive Reporting**: Final analysis combines findings with performance metrics

### Metacognitive Assessment Cycle

```mermaid
flowchart TD
    A[Think: Analyze Current State] --> B{Select Tool Type}
    
    B --> |Basic Task| C[Shell Commands]
    B --> |Security Task| D[Cyber Tools via Shell]
    B --> |Complex Task| E[Create Meta-Tool]
    B --> |Parallel Task| P[Swarm Orchestration]
    
    C --> F[Reflect: Evaluate Results]
    D --> F
    E --> F
    P --> F
    
    F --> G{Findings?}
    
    G --> |Critical| H[Exploit Immediately]
    G --> |Informational| I[Store & Continue]
    G --> |None| J[Try Different Approach]
    
    H --> K[Document Evidence]
    I --> L{Objective Met?}
    J --> A
    K --> L
    
    L --> |Yes| M[Complete Assessment]
    L --> |No| A
    
    style A fill:#e3f2fd
    style C fill:#e8f5e8
    style D fill:#fff3e0
    style E fill:#f3e5f5
    style P fill:#fce4ec
    style H fill:#ffcdd2
```

**Metacognitive Process:**

***Design Philosophy: Meta-Everything Architecture***

At the core of Cyber-AutoAgent is a "meta-everything" design philosophy that enables dynamic adaptation and scaling:

- **Meta-Agent**: The swarm capability deploys dynamic agents as tools, each tailored for specific subtasks with their own reasoning loops
- **Meta-Tooling**: Through the editor and load_tool capabilities, the agent can create, modify, and deploy new tools at runtime to address novel challenges
- **Meta-Learning**: Continuous memory storage and retrieval enables cross-session learning, building expertise over time
- **Meta-Cognition**: Self-reflection and confidence assessment drives strategic decisions about tool selection and approach (Note: This aspect is still being expanded for deeper reasoning capabilities)

This meta-architecture allows the system to transcend static tool limitations and evolve its capabilities during execution.

**Process Flow:**
- **Assess Confidence**: Evaluate current knowledge and confidence level (High >80%, Medium 50-80%, Low <50%)
- **Adaptive Strategy**: 
  - High confidence → Use specialized tools directly
  - Medium confidence → Deploy swarm for parallel exploration
  - Low confidence → Gather more information, try alternatives
- **Execute**: Tool hierarchy based on confidence:
  - Professional security tools for known vulnerabilities (sqlmap, nikto, nmap)
  - Swarm deployment when multiple approaches needed (with memory access)
  - Parallel shell for rapid reconnaissance (up to 7 commands)
  - Meta-tool creation only when no existing tool suffices
- **Learn & Store**: Store findings with category="finding" for memory persistence

**Tool Selection Hierarchy (Confidence-Based):**
1. Specialized cyber tools (sqlmap, nikto, metasploit) - when vulnerability type is known
2. Swarm deployment - when confidence <70% or need multiple perspectives (includes memory)
3. Parallel shell execution - for rapid multi-command reconnaissance
4. Meta-tool creation - only for novel exploits when existing tools fail

## Model Providers

Cyber-AutoAgent supports two model providers for maximum flexibility:

### Remote Mode (AWS Bedrock)
- **Best for**: Production use, high-quality results, no local GPU requirements
- **Requirements**: AWS account with Bedrock access
- **Default Model**: Claude Sonnet 4 (us.anthropic.claude-sonnet-4-20250514-v1:0)
- **Benefits**: Latest models, reliable performance, managed infrastructure

### Local Mode (Ollama)
- **Best for**: Privacy, offline use, cost control, local development
- **Requirements**: Local Ollama installation
- **Default Models**: `llama3.2:3b` (LLM), `mxbai-embed-large` (embeddings)
- **Benefits**: No cloud dependencies, complete privacy, no API costs

### Comparison

| Feature | Remote (AWS Bedrock) | Local (Ollama) |
|---------|---------------------|----------------|
| Cost | Pay per API call | One-time setup |
| Performance | High (managed) | Depends on hardware |
| Offline Use | No | Yes |
| Setup Complexity | Moderate | Higher |
| Model Quality | Highest | Low |

## Observability & Evaluation

> **[Complete Observability & Evaluation Guide](docs/observability-evaluation.md)** - Langfuse tracing, Ragas metrics, and automated performance evaluation

Cyber-AutoAgent includes **built-in observability and evaluation** using self-hosted Langfuse for tracing and Ragas for automated performance metrics. This provides complete visibility into agent operations and continuous assessment of cybersecurity effectiveness.

### Key Features

**Observability (Langfuse)**:
- **Complete operation traces**: Every penetration test operation is traced end-to-end
- **Tool execution timeline**: Visual timeline of nmap, sqlmap, nikto usage
- **Token usage metrics**: Track LLM token consumption and costs
- **Memory operations**: Monitor agent memory storage and retrieval patterns
- **Error tracking**: Failed tool executions and error analysis

**Evaluation (Ragas)**:
- **Tool Selection Accuracy**: How well the agent chooses appropriate cybersecurity tools
- **Evidence Quality**: Assessment of collected security findings and documentation
- **Answer Relevancy**: Alignment of agent actions with stated objectives
- **Context Precision**: Effective use of memory and tool outputs
- **Automated scoring**: Every operation receives performance metrics automatically

### Quick Start

When running with Docker Compose, observability and evaluation are enabled by default:

```bash
# Start with observability and evaluation
docker-compose up -d

# Access Langfuse UI at http://localhost:3000
# Login: admin@cyber-autoagent.com / changeme

# Enable evaluation for your operations
export ENABLE_AUTO_EVALUATION=true
```

### Configuration

**Essential Environment Variables**:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_OBSERVABILITY` | `true` | Enable/disable Langfuse tracing |
| `ENABLE_AUTO_EVALUATION` | `false` | Enable automatic Ragas evaluation |
| `LANGFUSE_HOST` | `http://langfuse-web:3000` | Langfuse server URL |
| `RAGAS_EVALUATOR_MODEL` | `us.anthropic.claude-3-5-sonnet-20241022-v2:0` | Model for evaluation |

### Evaluation Metrics

The system automatically evaluates four key metrics after each operation:

1. **Tool Selection Accuracy** (0.0-1.0): Strategic tool choice and sequencing
2. **Evidence Quality** (0.0-1.0): Comprehensive vulnerability documentation  
3. **Answer Relevancy** (0.0-1.0): Alignment with security objectives
4. **Context Precision** (0.0-1.0): Effective use of previous findings

### Production Security

For production deployments, update security keys:

```bash
LANGFUSE_ENCRYPTION_KEY=$(openssl rand -hex 32)
LANGFUSE_SALT=$(openssl rand -hex 16)
LANGFUSE_ADMIN_PASSWORD=strong-password-here
```

## Installation & Deployment

> **[Complete Deployment Guide](docs/deployment.md)** - Docker, Kubernetes, production setup, and troubleshooting

### Prerequisites

**Remote Mode (AWS Bedrock)**
```bash
# Configure AWS credentials
aws configure
# Or set environment variables:
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=your_region
```

**Local Mode (Ollama)**
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start service and pull models
ollama serve
ollama pull llama3.2:3b
ollama pull mxbai-embed-large
```

### Docker Deployment (Recommended)

```bash
# Clone repository
git clone https://github.com/cyber-autoagent/cyber-autoagent.git
cd cyber-autoagent

# Build image
docker build -t cyber-autoagent .

# Using environment variables
docker run --rm \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -e AWS_REGION=${AWS_REGION:-us-east-1} \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/tools:/app/tools \
  cyber-autoagent \
  --target "x.x.x.x" \
  --objective "Identify vulnerabilities" \
  --iterations 50
```

### Local Installation

```bash
# Clone repository
git clone https://github.com/cyber-autoagent/cyber-autoagent.git
cd cyber-autoagent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Optional: Install security tools (non-exhaustive list)
sudo apt install nmap nikto sqlmap gobuster  # Debian/Ubuntu
brew install nmap nikto sqlmap gobuster      # macOS

# Run
python src/cyberautoagent.py \
  --target "http://testphp.vulnweb.com" \
  --objective "Comprehensive security assessment"
```

### Data Storage

| Data Type | Location |
|-----------|----------|
| Evidence  | `./outputs/<target>/OP_<id>/` |
| Logs      | `./outputs/<target>/OP_<id>/logs/` |
| Reports   | `./outputs/<target>/OP_<id>/` |
| Tools     | `./tools/` |
| Utils     | `./outputs/<target>/OP_<id>/utils/` |
| Memory    | `./outputs/<target>/memory/` |

Directories are created automatically on first run.

### Command-Line Arguments

**Required Arguments**:
- `--objective`: Security assessment objective
- `--target`: Target system/network to assess (ensure you have permission!)

**Optional Arguments**: 
- `--server`: Model provider - `remote` (AWS Bedrock) or `local` (Ollama), default: remote
- `--iterations`: Maximum tool executions before stopping, default: 100
- `--model`: Model ID to use (default: remote=claude-sonnet, local=llama3.2:3b)
- `--region`: AWS region for Bedrock, default: us-east-1
- `--verbose`: Enable verbose output with detailed debug logging
- `--confirmations`: Enable tool confirmation prompts (default: disabled)
- `--memory-path`: Path to existing FAISS memory store to load past memories
- `--keep-memory`: Keep memory data after operation completes (default: remove)

### Usage Examples

```bash
# Basic Python Usage (Remote Mode)
python src/cyberautoagent.py \
  --target "http://testphp.vulnweb.com" \
  --objective "Find SQL injection vulnerabilities" \
  --iterations 50

# Docker with full observability, evaluation and root access (for package installation)
docker run --rm \
  --user root \ 
  --network cyber-autoagent_default \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -e AWS_REGION=${AWS_REGION:-us-east-1} \
  -e LANGFUSE_HOST=http://langfuse-web:3000 \
  -e LANGFUSE_PUBLIC_KEY=cyber-public \
  -e LANGFUSE_SECRET_KEY=cyber-secret \
  -e ENABLE_AUTO_EVALUATION=true \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/tools:/app/tools \
  cyber-autoagent:dev \
  --target "http://testphp.vulnweb.com" \
  --objective "Comprehensive SQL injection and XSS assessment" \
  --iterations 25
```

## Security

By default, the agent runs as a non-root user (`cyberagent`) for security. This limits the agent's ability to install additional tools on the fly during execution. If you need the agent to install packages dynamically, you can override this at container start:

```bash
# Small example, full command above
docker run --user root cyber-autoagent
```

**Note**: Running as root reduces security isolation but enables full system access for tool installation.

## Configuration

The agent uses a centralized configuration system defined in `src/modules/config.py`. All settings can be customized through environment variables, with sensible defaults provided.

Copy the example environment file and customize it for your needs:

```bash
cp .env.example .env
```

The `.env.example` file contains detailed configuration options with inline comments for all supported features including model providers, memory systems, and observability settings. Key environment variables include:

- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` for remote mode (AWS Bedrock)
- `OLLAMA_HOST` for local mode (Ollama)
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` for observability
- `MEM0_API_KEY` or `OPENSEARCH_HOST` for memory backends

See `.env.example` for complete configuration options and usage examples.

## Development & Testing

### Running Tests

This project uses `uv` for dependency management and testing:

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_agent.py

# Run tests with verbose output
uv run pytest -v

# Run tests with coverage
uv run pytest --cov=src
```

## Project Structure

```
cyber-autoagent/
├── src/                       # Source code
│   ├── cyberautoagent.py      # Main entry point and CLI
│   └── modules/               # Core modules
│       ├── agent.py           # Agent creation (Strands + models)
│       ├── config.py          # Centralized configuration system
│       ├── memory_tools.py    # Mem0 memory management
│       ├── system_prompts.py  # AI prompts and configurations
│       ├── agent_handlers.py  # Reasoning and callback handlers
│       ├── environment.py     # Tool discovery and logging
│       ├── evaluation.py      # Ragas evaluation system
│       └── utils.py           # UI utilities and analysis
├── docs/                      # Documentation
│   ├── architecture.md       # Agent architecture and tools
│   ├── memory.md             # Memory system (Mem0 backends)
│   ├── observability.md      # Langfuse monitoring setup
│   └── deployment.md         # Docker and production deployment
├── docker-compose.yml        # Full stack (agent + Langfuse)
├── Dockerfile                # Agent container build
├── pyproject.toml            # Dependencies and project config
├── uv.lock                   # Dependency lockfile
├── .env.example              # Environment configuration template
├── outputs/                  # Unified output directory (auto-created)
│   ├── <target>/            # Target-specific organization
│   │   ├── OP_<id>/        # Operation-specific files
│   │   │   ├── evidence/   # Security findings
│   │   │   ├── utils/      # Tool outputs
│   │   │   └── logs/       # Operation logs
│   │   └── memory/         # Cross-operation memory
│   └── tools/              # Custom tools created by agent
└── README.md                 # This file
```

### Key Files

| File | Purpose |
|------|---------|
| `src/cyberautoagent.py` | CLI entry point, observability setup |
| `src/modules/agent.py` | Strands agent creation, model configuration |
| `src/modules/config.py` | Centralized configuration system |
| `src/modules/memory_tools.py` | Unified Mem0 tool (FAISS/OpenSearch/Platform) |
| `src/modules/evaluation.py` | Ragas evaluation system |
| `.env.example` | Environment configuration template |
| `docker-compose.yml` | Complete observability stack |
| `docs/architecture.md` | Technical architecture deep dive |

## Troubleshooting

### Common Issues

#### AWS Credentials Not Found
```bash
# Configure AWS CLI
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1
```

#### Model Access Denied
```bash
# Request model access in AWS Console
# Navigate to: Amazon Bedrock > Model access > Request model access
```

#### Memory System Errors

> **See [Memory System Guide](docs/memory.md)** for complete backend configuration and troubleshooting
```bash
# For local FAISS backend (default)
pip install faiss-cpu  # or faiss-gpu for CUDA

# For Mem0 Platform
export MEM0_API_KEY=your_api_key

# For OpenSearch backend
export OPENSEARCH_HOST=your_host
export AWS_REGION=your_region

# Check memory storage location
ls -la ./mem0_faiss_OP_*/
```

#### Tool Not Found Errors
```bash
# Install missing security tools
sudo apt install nmap nikto sqlmap gobuster  # Debian/Ubuntu
brew install nmap nikto sqlmap gobuster      # macOS
```

#### Ollama Issues (Local Mode)

**Ollama Server Not Running**
```bash
# Start Ollama service
ollama serve

# Check if running
curl http://localhost:11434/api/version
```

**Required Models Missing**
```bash
# Pull required models
ollama pull llama3.2:3b
ollama pull mxbai-embed-large

# List available models
ollama list
```

**Connection Errors**
```bash
# Check Ollama is accessible
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2:3b", "prompt": "test", "stream": false}'
```

**Docker Networking (Local Mode)**
Cyber-AutoAgent automatically detects the correct Ollama host for your environment:

```bash
# Ensure Ollama is running on your host
ollama serve

# Test connection from host
curl http://localhost:11434/api/version
```


**Performance Issues**
```bash
# Monitor resource usage
htop  # Check CPU/Memory during execution

# For better performance, consider:
# - Using smaller models (e.g., llama3.1:8b instead of 70b)
# - Allocating more RAM to Ollama
# - Using GPU acceleration if available
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Legal Notice

This tool is provided for educational and authorized security testing purposes only. Users are solely responsible for ensuring they have proper authorization before testing any systems. The authors assume no liability for misuse or any damages that may result from using this software.

## Acknowledgments

- [Strands Framework](https://github.com/anthropics/strands) - Agent orchestration & swarm intelligence
- [AWS Bedrock](https://aws.amazon.com/bedrock/) - Foundation model access
- [Ollama](https://ollama.ai) - Local model inference
- [Mem0](https://github.com/mem0ai/mem0) - Advanced memory management with FAISS/OpenSearch/Platform backends
---

**Remember: With great power comes great responsibility. Use this tool ethically and legally.**
