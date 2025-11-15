# User Guide

Cyber-AutoAgent is an autonomous security assessment tool with a React-based terminal interface providing real-time operation monitoring and interactive configuration.

## Prerequisites

| Requirement | Purpose |
|-------------|---------|
| Node.js 20+ | React interface runtime |
| Docker Desktop | Containerized agent execution |
| AWS credentials or Ollama | Model provider access |
| Authorization | Written permission to test targets |

**Legal Notice:** Only test systems you own or have explicit written permission to assess. Unauthorized testing is illegal. Users assume full responsibility for legal and ethical use.

## Installation

```bash
cd src/modules/interfaces/react
npm install
npm run build
npm start
```

First launch guides you through Docker setup, deployment mode selection, and provider configuration.

## Deployment Modes

| Mode | Execution | Observability | Use Case |
|------|-----------|---------------|----------|
| Local CLI | Direct Python | None | Development |
| Single Container | Docker isolated | None | Basic assessments |
| Full Stack | Docker Compose | Langfuse included | Production |

Select during setup or change via `/setup` command.

## Configuration

Cyber-AutoAgent offers **3 configuration methods**:

### Method 1: Config Editor UI (Recommended)

Launch the React interface to configure via UI:

```bash
cd src/modules/interfaces/react
npm start
```

**In the Terminal:**
1. Type `/config` to open Config Editor
2. Select **Provider**: `litellm` (supports 300+ models)
3. Configure **LLM Settings**:
   - Model ID: `azure/gpt-5`, `moonshot/kimi-k2-thinking`, `openrouter/openrouter/polaris-alpha`
   - Temperature: `1.0` (for reasoning models) or `0.95` (default)
   - Max Tokens: `32000`
   - Reasoning Effort: `medium` (for GPT-5/o1 models)
4. Configure **Embedding Model**: `azure/text-embedding-3-large`
5. Add **Provider Credentials**:
   - Azure: API Key, API Base, API Version
   - Moonshot: API Key
   - OpenRouter: API Key
6. Save settings - persists to `~/.cyber-autoagent/config.json`
7. Type `/help` for available commands

**Using Saved Config:**
```bash
# Auto-run uses saved config
npm start -- --auto-run --target https://example.com --iterations 50
```

### Method 2: Environment Variables

Direct configuration for Python CLI:

**Azure OpenAI (GPT-5):**
```bash
export AZURE_API_KEY=your_key
export AZURE_API_BASE=https://your-endpoint.openai.azure.com/
export AZURE_API_VERSION=2024-12-01-preview
export CYBER_AGENT_LLM_MODEL=azure/gpt-5
export CYBER_AGENT_EMBEDDING_MODEL=azure/text-embedding-3-large
export REASONING_EFFORT=medium
```

**AWS Bedrock:**
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1
```

**OpenRouter:**
```bash
export OPENROUTER_API_KEY=your_key
export CYBER_AGENT_LLM_MODEL=openrouter/openrouter/polaris-alpha
export CYBER_AGENT_EMBEDDING_MODEL=azure/text-embedding-3-large
```

**Moonshot AI:**
```bash
export MOONSHOT_API_KEY=your_key
export CYBER_AGENT_LLM_MODEL=moonshot/kimi-k2-thinking
export CYBER_AGENT_EMBEDDING_MODEL=azure/text-embedding-3-large
export MEM0_LLM_MODEL=azure/gpt-4o  # Separate LLM for memory system
```

**Ollama (Local):**
```bash
ollama serve
ollama pull qwen3-coder:30b-a3b-q4_K_M
ollama pull mxbai-embed-large
```

**LiteLLM:**
```bash
export OPENAI_API_KEY=your_key
# or
export ANTHROPIC_API_KEY=your_key
```

### Method 3: Config File (Direct Edit)

Advanced users can directly edit `~/.cyber-autoagent/config.json`:

```json
{
  "modelProvider": "litellm",
  "modelId": "azure/gpt-5",
  "embeddingModel": "azure/text-embedding-3-large",
  "temperature": 1.0,
  "maxTokens": 32000,
  "reasoningEffort": "medium",
  "azureApiKey": "your_key",
  "azureApiBase": "https://your-endpoint.openai.azure.com/",
  "azureApiVersion": "2024-12-01-preview",
  "observability": false,
  "autoEvaluation": false
}
```

**Supported Providers:** `bedrock`, `ollama`, `litellm` (300+ models)

### Configuration Commands

| Command | Function |
|---------|----------|
| `/config` | View current settings |
| `/config edit` | Interactive editor |
| `/provider` | Change model provider |
| `/setup` | Re-run initial setup |
| `/health` | System status check |

## Running Assessments

### Interactive Mode

```bash
# In interface
/module              # Select general or ctf
target: https://testphp.vulnweb.com
objective: Identify SQL injection vulnerabilities
execute              # Start assessment
```

### Command Line Mode

```bash
cyber-react \
  --target "https://testphp.vulnweb.com" \
  --objective "Identify OWASP Top 10 vulnerabilities" \
  --module general \
  --iterations 50 \
  --auto-run
```

### Command Line Flags

| Flag                   | Default   | Description                             |
|------------------------|-----------|-----------------------------------------|
| `--target, -t`         | Required  | Target system URL or IP                 |
| `--objective, -o`      | Required  | Assessment objective                    |
| `--module, -m`         | `general` | Security module: general, ctf           |
| `--iterations, -i`     | `100`     | Maximum tool executions                 |
| `--provider`           | `bedrock` | Model provider                          |
| `--auto-run`           | `false`   | Skip interactive prompts                |
| `--auto-approve`       | `false`   | Auto-approve tool executions            |
| `--memory-mode`        | `auto`    | Memory: auto or fresh                   |
| `--deployment-mode`    | Auto      | local-cli, single-container, full-stack |
| `--mcp-enabled`        | `false`   | Enable MCP Tools                        |
| `--mcp-conns` '[...]'  | None      | Configure MCP Tools                     |

### Configuration Loading Priority

When using `--auto-run` mode, configuration is loaded and merged in the following priority order:

1. **Default Configuration** (lowest priority) - Built-in defaults from the application
2. **Saved Configuration** (medium priority) - User settings from `~/.cyber-autoagent/config.json`
3. **Command Line Flags** (highest priority) - Flags specified on the command line

This means:
- Your saved configuration from the React UI is automatically loaded and used
- Command line flags override any saved settings
- Defaults are only used for values not specified in saved config or CLI flags

**Example:**
```bash
# If your config.json has modelProvider: "ollama" and observability: true
# This command will use:
# - modelProvider: "bedrock" (from CLI flag, overrides saved config)
# - observability: true (from saved config)
# - iterations: 50 (from CLI flag)
# - All other settings from saved config or defaults

cyber-react \
  --target "https://example.com" \
  --provider bedrock \
  --iterations 50 \
  --auto-run
```

## Operation Modules

| Module | Purpose | Key Features |
|--------|---------|--------------|
| **general** | Web application security | Advanced recon, payload testing, auth analysis |
| **ctf** | CTF challenges | Flag recognition, exploit chains, success detection |

## Monitoring

### Interface Display

| Section | Information |
|---------|-------------|
| Header | Operation ID, target, module, deployment mode |
| Main | Agent reasoning, tool executions, outputs, findings |
| Footer | Step progress, tokens, costs, memory ops, time |

### Observability (Full Stack)

```
URL: http://localhost:3000
Login: admin@cyber-autoagent.com / changeme
```

## Output Structure

```
outputs/
└── <target>/
    ├── OP_<timestamp>/
    │   ├── report.md              # Assessment report
    │   ├── logs/
    │   │   └── cyber_operations.log
    │   └── utils/
    └── memory/                    # Persistent across operations
```

## Memory System

| Mode | Behavior | Use Case |
|------|----------|----------|
| **auto** | Loads existing memory, stores new findings | Iterative testing |
| **fresh** | Empty memory, no historical context | Baseline assessments |

Control via `/config edit` or `--memory-mode` flag.

## MCP Configuration

The configuration block in `~/.cyber-autoagent/config.json` for MCP servers looks like the following. The terminal UI
can be used to configure, command line options or environment variables.

```json
{
  "mcp": {
    "enabled": true,
    "connections": [
      {
         "id": "htb-mcp-server",
         "transport": "stdio",  // or "sse", "streamable-http"
         "command": ["./htb-mcp-server"],
         "plugins": ["general"]  // or ["*"]
      },
      {
         "id": "shyhurricane",
         "transport": "streamable-http",
         "server_url": "https://127.0.0.1:8000/mcp",
         "plugins": ["*"], 
         "timeoutSeconds": 900,
         "allowedTools": ["port_scan", "directory_buster"]  // or ["*"]
      }
    ]
  }
}
```

Environment variable substitution is performed in the `headers` and `command` values, so that sensitive information is not stored in the configuration.

The command line option `--mcp-conns` or environment variable `CYBER_MCP_CONNECTIONS` provides the `connections` block as a string.

Examples:

- `CYBER_MCP_ENABLED=true`
- `CYBER_MCP_CONNECTIONS='[{"id":"...","transport":"..."}]'`
- `--mcp-enabled --mcp-conns '[{"id":"...","transport":"..."}]'`

### HackTheBox CTF MCP Configuration

This is an example configuration for the HackTheBox CTF MCP server. Export your API key before running.

```shell
export HTB_TOKEN=xxx.yyy.zzz
```

```json
{
   "mcp": {
      "enabled": true,
      "connections": [
         {
            "id": "htbctf",
            "transport": "sse",
            "server_url": "https://mcp.ai.hackthebox.com/v1/ctf/sse",
            "plugins": ["ctf"],
            "headers": {"Authorization": "Bearer ${HTB_TOKEN}"}
         }
      ]
   }
}
```

### HexStrike AI

```json
{
   "mcp": {
      "enabled": true,
      "connections": [
         {
            "id": "hex",
            "transport": "stdio",
            "command": ["python3", "/path/to/hexstrike-ai/hexstrike_mcp.py", "--server", "http://localhost:8888"],
            "plugins": ["general"],
            "timeoutSeconds": 300
         }
      ]
   }
}
```


## Docker Management

```bash
# Start full stack
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Reset all data
docker-compose down -v
```

## Alternative Execution

### Python Direct

```bash
python src/cyberautoagent.py \
  --target "http://testphp.vulnweb.com" \
  --objective "SQL injection assessment" \
  --provider bedrock \
  --module general \
  --iterations 50
```

Requirements: Python 3.10+, dependencies installed

### Docker Standalone

```bash
docker build -t cyber-autoagent .

docker run --rm \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -v $(pwd)/outputs:/app/outputs \
  cyber-autoagent \
  --target "http://example.com" \
  --objective "Security assessment"
```

## Troubleshooting

### Application Issues

| Problem | Solution |
|---------|----------|
| React app won't start | `rm -rf node_modules && npm install && npm run build` |
| Configuration errors | `rm ~/.cyber-autoagent/config.json && cyber-react` |
| Docker connectivity | `docker info` to verify daemon running |
| Node version issues | Verify Node.js 20+ with `node --version` |

### Provider Issues

| Provider | Verification Command |
|----------|---------------------|
| Bedrock | `aws sts get-caller-identity` |
| Ollama | `curl http://localhost:11434/api/version` |
| LiteLLM | `echo $OPENAI_API_KEY` |

### Operation Issues

| Issue | Resolution |
|-------|------------|
| Assessment not starting | Check provider credentials, Docker status, target accessibility |
| Assessment stuck | Review step in footer, check tool outputs for errors |
| Out of memory | Reduce iterations, use fresh memory mode, clear old outputs |
| Port conflicts | Change ports in docker-compose.yml or stop conflicting services |

## Examples

### Web Application Assessment

```bash
cyber-react \
  -m general \
  -t "https://testphp.vulnweb.com" \
  -o "OWASP Top 10 assessment" \
  -i 50
```

### API Security Testing

```bash
cyber-react \
  -m general \
  -t "https://api.example.com" \
  -o "Authentication testing" \
  -i 75 \
  --auto-approve
```

### CTF Challenge

```bash
cyber-react \
  -m ctf \
  -t "http://challenge.ctf:8080" \
  -o "Extract flag" \
  -i 100
```

### Automated Scan

```bash
cyber-react \
  -t "192.168.1.100" \
  -o "Network security assessment" \
  --auto-run \
  --auto-approve \
  --headless
```

## Best Practices

### Assessment Workflow

| Phase | Actions |
|-------|---------|
| **Before** | Obtain written authorization, verify Docker running, check provider connectivity, test target accessibility |
| **During** | Monitor real-time outputs, review tool effectiveness, track token usage, check finding severity |
| **After** | Review complete report, verify findings accuracy, document methodology, archive outputs |

### Configuration Guidelines

| Setting | Recommendation |
|---------|---------------|
| Iterations | Start with 25-50, increase to 100-200 for comprehensive testing |
| Module | Use general for web apps, ctf for competitions |
| Auto-approve | Only for trusted environments |
| Observability | Enable for production assessments |
| Memory mode | Auto for iterative testing, fresh for baselines |

## Legal and Ethical Use

### Required Before Use

| Requirement | Description |
|-------------|-------------|
| Written authorization | Explicit permission to test target systems |
| Legal compliance | Understanding of applicable laws and regulations |
| Impact assessment | Ensure testing won't affect production services |
| Scope documentation | Clearly defined testing boundaries |
| Disclosure practices | Responsible vulnerability reporting procedures |

### Responsible Disclosure

If vulnerabilities are discovered during authorized testing:

| Step | Action |
|------|--------|
| 1 | Report to system owner promptly with clear reproduction steps |
| 2 | Allow reasonable remediation time (typically 90 days) |
| 3 | Do not publicly disclose until patched |
| 4 | Follow coordinated disclosure practices |

**Open Source Notice:** This software is provided "as is" without warranty. Contributors and maintainers assume no liability for misuse or damages.

## Additional Resources

| Resource | Location |
|----------|----------|
| Architecture Guide | [architecture.md](architecture.md) |
| Memory System | [memory.md](memory.md) |
| Deployment Guide | [deployment.md](deployment.md) |
| Module Development | [../src/modules/operation_plugins/README.md](../src/modules/operation_plugins/README.md) |
| Terminal Architecture | [terminal-frontend.md](terminal-frontend.md) |
| GitHub Issues | Report bugs and request features |
