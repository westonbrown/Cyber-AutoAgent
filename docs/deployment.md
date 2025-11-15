# Deployment Guide

This guide covers deployment options for Cyber-AutoAgent in various environments.

## Invocation Methods

Cyber-AutoAgent supports **4 invocation methods**, each with different use cases:

### 1. Python CLI (Direct Execution)

Best for: Automation, scripting, CI/CD pipelines

```bash
# Configure via environment variables
export AZURE_API_KEY="your_key"
export AZURE_API_BASE="https://your-endpoint.openai.azure.com/"
export AZURE_API_VERSION="2024-12-01-preview"
export CYBER_AGENT_LLM_MODEL="azure/gpt-5"
export CYBER_AGENT_EMBEDDING_MODEL="azure/text-embedding-3-large"
export REASONING_EFFORT="medium"

# Run with uv (recommended)
uv run python src/cyberautoagent.py \
  --target "https://example.com" \
  --objective "Bug bounty assessment" \
  --iterations 150 \
  --provider litellm
```

### 2. NPM Auto-Run (Config File)

Best for: Repeated testing with saved config, development

```bash
# Uses ~/.cyber-autoagent/config.json for settings
cd src/modules/interfaces/react
npm start -- --auto-run \
  --target "https://example.com" \
  --objective "Security assessment" \
  --iterations 50
```

**Configure via** `~/.cyber-autoagent/config.json`:
```json
{
  "modelProvider": "litellm",
  "modelId": "azure/gpt-5",
  "embeddingModel": "azure/text-embedding-3-large",
  "azureApiKey": "your_key",
  "azureApiBase": "https://your-endpoint.openai.azure.com/",
  "azureApiVersion": "2024-12-01-preview",
  "reasoningEffort": "medium"
}
```

### 3. Docker (Standalone Container)

Best for: Isolated environments, clean tooling, reproducibility

**With Interactive React Terminal:**
```bash
docker run -it --rm \
  -e AZURE_API_KEY=your_key \
  -e AZURE_API_BASE=https://your-endpoint.openai.azure.com/ \
  -e CYBER_AGENT_LLM_MODEL=azure/gpt-5 \
  -v $(pwd)/outputs:/app/outputs \
  cyberautoagent:latest
```

**Direct Python Execution (Override Entrypoint):**
```bash
docker run --rm --entrypoint python \
  -e AZURE_API_KEY=your_key \
  -e AZURE_API_BASE=https://your-endpoint.openai.azure.com/ \
  -e AZURE_API_VERSION=2024-12-01-preview \
  -e CYBER_AGENT_LLM_MODEL=azure/gpt-5 \
  -e CYBER_AGENT_EMBEDDING_MODEL=azure/text-embedding-3-large \
  -e REASONING_EFFORT=medium \
  -v $(pwd)/outputs:/app/outputs \
  cyberautoagent:latest \
  src/cyberautoagent.py \
  --target https://example.com \
  --objective "Security assessment" \
  --iterations 50 \
  --provider litellm
```

### 4. Docker Compose (Full Stack)

Best for: Observability, team deployments, production monitoring

```bash
# Uses docker/.env for configuration
docker compose -f docker/docker-compose.yml up -d
```

## Universal Provider Support

Cyber-AutoAgent supports **300+ LLM providers** via LiteLLM. Examples:

**Azure OpenAI:**
```bash
-e AZURE_API_KEY=your_key
-e AZURE_API_BASE=https://your-endpoint.openai.azure.com/
-e AZURE_API_VERSION=2024-12-01-preview
-e CYBER_AGENT_LLM_MODEL=azure/gpt-5
-e CYBER_AGENT_EMBEDDING_MODEL=azure/text-embedding-3-large
```

**AWS Bedrock:**
```bash
-e AWS_ACCESS_KEY_ID=your_key
-e AWS_SECRET_ACCESS_KEY=your_secret
-e CYBER_AGENT_LLM_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
-e CYBER_AGENT_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
```

**OpenRouter:**
```bash
-e OPENROUTER_API_KEY=your_key
-e CYBER_AGENT_LLM_MODEL=openrouter/openrouter/polaris-alpha
-e CYBER_AGENT_EMBEDDING_MODEL=azure/text-embedding-3-large
```

**Moonshot AI:**
```bash
-e MOONSHOT_API_KEY=your_key
-e OPENAI_API_KEY=your_key  # Required for Mem0 OpenAI-compatible providers
-e CYBER_AGENT_LLM_MODEL=moonshot/kimi-k2-thinking
-e CYBER_AGENT_EMBEDDING_MODEL=azure/text-embedding-3-large
-e MEM0_LLM_MODEL=azure/gpt-4o  # Memory system LLM (use Azure/Anthropic/Bedrock for Mem0)
-e AZURE_API_KEY=azure_key  # Required for embeddings and Mem0
-e AZURE_API_BASE=https://your-endpoint.openai.azure.com/
-e AZURE_API_VERSION=2024-12-01-preview
```

**Note:** When using OpenAI-compatible providers (Moonshot, OpenRouter, etc.) with Mem0, you must:
1. Set `OPENAI_API_KEY` to the provider's API key for Mem0 compatibility
2. Use a supported Mem0 provider (Azure, OpenAI, Anthropic, Bedrock) for `MEM0_LLM_MODEL`

**Mixed Providers:** You can combine any LLM with any embedding model!

## Quick Start

### Using Docker

```bash
# Clone the repository
git clone https://github.com/cyber-autoagent/cyber-autoagent.git
cd cyber-autoagent

# Build and run with Docker Compose (includes observability)
cd docker
docker-compose up -d

# Run a penetration test
docker run --rm \
  --network cyber-autoagent_default \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -e LANGFUSE_HOST=http://langfuse-web:3000 \
  -e LANGFUSE_PUBLIC_KEY=cyber-public \
  -e LANGFUSE_SECRET_KEY=cyber-secret \
  -v $(pwd)/outputs:/app/outputs \
  cyber-autoagent \
  --target "example.com" \
  --objective "Web application security assessment"
```

### Standalone Docker

For just the agent without observability:

```bash
# Build the image
docker build -t cyber-autoagent -f docker/Dockerfile .

# Run with AWS Bedrock
docker run --rm \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -e AWS_REGION=${AWS_REGION:-us-east-1} \
  -v $(pwd)/outputs:/app/outputs \
  cyber-autoagent \
  --target "192.168.1.100" \
  --objective "Network security assessment" \
  --provider bedrock

# Run with Ollama (local)
docker run --rm \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -v $(pwd)/outputs:/app/outputs \
  cyber-autoagent \
  --target "testsite.local" \
  --objective "Basic security scan" \
  --provider ollama \
  --model qwen3-coder:30b-a3b-q4_K_M
```

## Production Deployment

### Security Considerations

1. **Network Isolation**: Deploy in an isolated network segment
2. **Resource Limits**: Set memory and CPU limits in docker-compose.yml
3. **Secure Keys**: Generate proper encryption keys for Langfuse:
   ```bash
   # Generate secure keys
   openssl rand -hex 32  # For ENCRYPTION_KEY
   openssl rand -base64 32  # For SALT
   openssl rand -base64 32  # For NEXTAUTH_SECRET
   ```

## Configuration System

### Architecture

Cyber-AutoAgent uses a **modular, three-tier configuration system** with automatic model detection and safe token limit allocation.

**Configuration Modules:**
```
config/
├── manager.py           # Core orchestration (ConfigManager)
├── types.py             # Type definitions and dataclasses
├── models/              # Model creation and capabilities
├── system/              # Environment, logging, validation
└── providers/           # Provider-specific helpers
```

See `src/modules/config/README.md` for complete module documentation.

### Configuration Precedence

Settings are applied in this priority order:

```
1. CLI/API Arguments (Highest)
   └─ Flags: --provider, --model, --iterations
   └─ Direct parameters to create_agent()

2. Environment Variables (Override)
   └─ CYBER_AGENT_LLM_MODEL
   └─ CYBER_AGENT_EMBEDDING_MODEL
   └─ REASONING_EFFORT
   └─ Provider-specific: AZURE_API_KEY, AWS_REGION, etc.

3. Provider Defaults (Fallback)
   └─ Safe defaults for all providers
   └─ Automatically selected based on provider
```

**Example:**
```bash
# Default: temperature=0.95 (from provider defaults)
# Override via environment: CYBER_LLM_TEMPERATURE=0.8
# Override via CLI: create_agent(..., temperature=0.7)
# Result: Uses 0.7 (CLI has highest priority)
```

### Models.dev Integration

Token limits are automatically detected using the **models.dev API** with resilient fallback:

**Three-Tier Fallback:**
1. Disk cache (`~/.cache/cyber-autoagent/models.json`, 24h TTL)
2. Live API (`https://models.dev/api.json`)
3. Embedded snapshot (`models_snapshot.json`, 432KB bundled)

**Benefits:**
- Accurate limits for 1,100+ models across 58 providers
- Works offline (embedded snapshot)
- Safe token allocation (50% of actual limit by default)
- Automatic capability detection (reasoning, tools, attachments)

**Safe Token Limits:**
```python
# Specialist tools use 50% of model's output limit for reliability
safe_max = model_output_limit * 0.5

# Example: Bedrock Claude 3.5 Sonnet v2
# Actual limit: 8,192 tokens
# Safe allocation: 4,096 tokens
```

### Token Limit Resolution

Token limits use **five-tier precedence**:

1. **Explicit override** - `CYBER_CONTEXT_WINDOW` environment variable
2. **Models.dev API** - Authoritative registry (preferred)
3. **Fallback mappings** - `CYBER_CONTEXT_WINDOW_FALLBACKS` (JSON)
4. **Provider defaults** - Safe defaults per provider
5. **Universal fallback** - 128,000 tokens

**Example fallback configuration:**
```bash
export CYBER_CONTEXT_WINDOW_FALLBACKS='[
  {"azure/gpt-5": ["azure/gpt-4o", "azure/gpt-4"]},
  {"anthropic/claude-opus": ["anthropic/claude-sonnet-4-5"]}
]'
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `CYBER_AGENT_PROVIDER` | Provider choice (bedrock/ollama/litellm) | No (auto-detected) |
| `CYBER_AGENT_LLM_MODEL` | Main LLM model ID | Yes |
| `CYBER_AGENT_EMBEDDING_MODEL` | Embedding model ID | No (provider default) |
| `REASONING_EFFORT` | Reasoning effort (low/medium/high) | No (default: medium) |
| `CYBER_LLM_MAX_TOKENS` | Override LLM max tokens | No (models.dev default) |
| `CYBER_SWARM_MAX_TOKENS` | Override specialist max tokens | No (models.dev default) |
| `CYBER_CONTEXT_WINDOW` | Override prompt token limit | No (auto-detected) |
| `AWS_ACCESS_KEY_ID` | AWS credentials for Bedrock | For Bedrock provider |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for Bedrock | For Bedrock provider |
| `AWS_REGION` | AWS region (default: us-east-1) | For Bedrock provider |
| `OLLAMA_HOST` | Ollama API endpoint | For Ollama provider |
| `AZURE_API_KEY` | Azure OpenAI API key | For Azure/LiteLLM |
| `AZURE_API_BASE` | Azure endpoint URL | For Azure/LiteLLM |
| `AZURE_API_VERSION` | Azure API version | For Azure/LiteLLM |
| `MEM0_API_KEY` | Mem0 Platform API key | For cloud memory backend |
| `MEM0_LLM_MODEL` | Memory system LLM | No (auto-aligned) |
| `OPENSEARCH_HOST` | OpenSearch endpoint | For OpenSearch memory backend |
| `LANGFUSE_HOST` | Langfuse observability endpoint | For observability |
| `LANGFUSE_PUBLIC_KEY` | Langfuse API public key | For observability |
| `LANGFUSE_SECRET_KEY` | Langfuse API secret key | For observability |
| `ENABLE_AUTO_EVALUATION` | Enable automatic Ragas evaluation | For evaluation |

### Kubernetes Deployment

Example deployment manifest:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cyber-autoagent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: cyber-autoagent
  template:
    metadata:
      labels:
        app: cyber-autoagent
    spec:
      containers:
      - name: cyber-autoagent
        image: cyber-autoagent:latest
        env:
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: aws-credentials
              key: access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: aws-credentials
              key: secret-access-key
        volumeMounts:
        - name: outputs
          mountPath: /app/outputs
      volumes:
      - name: outputs
        persistentVolumeClaim:
          claimName: outputs-pvc
```

## Monitoring

- Access Langfuse UI at http://localhost:3000
- Default credentials: admin@cyber-autoagent.com / changeme
- View real-time traces of agent operations
- Export results for reporting

## React Interface Deployment

The React terminal interface provides interactive configuration and real-time monitoring:

```bash
# Install and build
cd src/modules/interfaces/react
npm install
npm run build

# Start the interface
npm start

# The interface will guide you through:
# 1. Docker environment setup
# 2. Deployment mode selection (local-cli, single-container, full-stack)
# 3. Model provider configuration (Bedrock, Ollama, LiteLLM)
# 4. First assessment execution
```

Access the interface at `http://localhost:3000` when using full-stack deployment with observability.

## Memory Backend Configuration

Cyber-AutoAgent supports three memory backends with automatic selection:

| Backend | Priority | Environment Variable | Use Case |
|---------|----------|---------------------|----------|
| Mem0 Platform | 1 | `MEM0_API_KEY` | Cloud-hosted, managed service |
| OpenSearch | 2 | `OPENSEARCH_HOST` | AWS managed search, production scale |
| FAISS | 3 | None (default) | Local vector storage, development |

Memory persists in `outputs/<target>/memory/` for cross-operation learning.

## Configuration Examples

### Azure OpenAI with Reasoning
```bash
export AZURE_API_KEY=your_key
export AZURE_API_BASE=https://your-endpoint.openai.azure.com/
export AZURE_API_VERSION=2024-12-01-preview
export CYBER_AGENT_LLM_MODEL=azure/gpt-5
export CYBER_AGENT_EMBEDDING_MODEL=azure/text-embedding-3-large
export REASONING_EFFORT=high
export CYBER_LLM_MAX_TOKENS=8000  # Optional: Override default
```

### AWS Bedrock with Memory
```bash
export AWS_REGION=us-east-1
export CYBER_AGENT_LLM_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
export CYBER_AGENT_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
export MEM0_API_KEY=your_mem0_key  # Cloud memory backend
export REASONING_EFFORT=medium
```

### Moonshot AI (Mixed Providers)
```bash
export MOONSHOT_API_KEY=your_key
export CYBER_AGENT_LLM_MODEL=moonshot/kimi-k2-thinking
export CYBER_AGENT_EMBEDDING_MODEL=azure/text-embedding-3-large
export AZURE_API_KEY=your_azure_key  # For embeddings
export AZURE_API_BASE=https://your-endpoint.openai.azure.com/
export AZURE_API_VERSION=2024-12-01-preview
export MEM0_LLM_MODEL=azure/gpt-4o  # Memory system uses Azure
export OPENAI_API_KEY=your_moonshot_key  # Mem0 compatibility
```

### Ollama with Context Window Fallbacks
```bash
export OLLAMA_HOST=http://localhost:11434
export CYBER_AGENT_LLM_MODEL=qwen3-coder:30b-a3b-q4_K_M
export CYBER_AGENT_EMBEDDING_MODEL=nomic-embed-text
export CYBER_CONTEXT_WINDOW_FALLBACKS='[
  {"qwen3-coder:30b": ["qwen3-coder:14b", "llama3.2:3b"]}
]'
```

## Troubleshooting

Common deployment issues:

1. **Container fails to start**: Check Docker logs with `docker logs cyber-autoagent`
2. **AWS credentials error**: Ensure IAM role has Bedrock access and correct region
3. **Ollama connection failed**: Verify Ollama is running and accessible at specified host
4. **Out of memory**: Increase Docker memory limits or reduce `--iterations` parameter
5. **React interface issues**: Run `npm run build` after any code changes
6. **Memory backend errors**: Verify environment variables and network connectivity
7. **Model not found**: Check model ID format (use `provider/model` for LiteLLM)
8. **Token limit errors**: Verify models.dev snapshot exists at `src/modules/config/models/models_snapshot.json`
9. **Specialist failures**: Check swarm max_tokens configuration (should be >100 tokens)
