# Providers Module

Provider-specific configuration helpers for AWS Bedrock, Ollama, and LiteLLM.

## Files

### bedrock_config.py
AWS Bedrock-specific configuration.

**Function:**
```python
get_default_region(env_reader) -> str
```

Returns default AWS region with environment override.

**Example:**
```python
from modules.config.providers.bedrock_config import get_default_region
from modules.config.system import EnvironmentReader

env = EnvironmentReader()
region = get_default_region(env)
```

### ollama_config.py
Ollama local server configuration with Docker-aware detection.

**Function:**
```python
get_ollama_host(env_reader) -> str
```

Returns Ollama server host with automatic Docker environment detection.

**Example:**
```python
from modules.config.providers.ollama_config import get_ollama_host
from modules.config.system import EnvironmentReader

env = EnvironmentReader()
host = get_ollama_host(env)
```

### litellm_config.py
LiteLLM proxy configuration for 300+ providers.

**Functions:**
- `split_litellm_model_id(model_id)` - Parse provider prefix from model ID
- `align_litellm_defaults(defaults, env_reader)` - Align configuration with environment
- `get_context_window_fallbacks(provider)` - Get fallback model mappings

**Features:**
- Model ID parsing: `azure/gpt-5` → `("azure", "gpt-5")`
- Embedding alignment: Match embedding dimensions to selected model
- Context window fallbacks: Define fallback chains for quota exhaustion
- Provider-specific defaults: Azure, OpenAI, Anthropic, Moonshot, etc.

**Example:**
```python
from modules.config.providers.litellm_config import split_litellm_model_id

provider, model = split_litellm_model_id("azure/gpt-5")
# Returns: ("azure", "gpt-5")

provider, model = split_litellm_model_id("gpt-4")
# Returns: ("", "gpt-4")
```

## Provider Configuration Overview

### AWS Bedrock

**Requirements:**
- AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- AWS region (`AWS_REGION` or default to us-east-1)
- Bedrock model access (IAM permissions)

**Model Format:**
```bash
us.anthropic.claude-sonnet-4-5-20250929-v1:0
amazon.titan-embed-text-v2:0
```

**Environment Variables:**
```bash
export AWS_REGION=us-east-1
export CYBER_AGENT_LLM_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
export CYBER_AGENT_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
```

### Ollama (Local)

**Requirements:**
- Ollama server running and accessible
- Models pulled locally (`ollama pull model_name`)

**Host Detection:**
- Environment: `OLLAMA_HOST=http://custom-host:11434`
- Default: `http://localhost:11434`
- Docker: `http://host.docker.internal:11434` (auto-detected)

**Model Format:**
```bash
qwen3-coder:30b-a3b-q4_K_M
llama3.2:3b
mistral:7b-instruct
```

**Environment Variables:**
```bash
export OLLAMA_HOST=http://localhost:11434
export CYBER_AGENT_LLM_MODEL=qwen3-coder:30b-a3b-q4_K_M
export CYBER_AGENT_EMBEDDING_MODEL=nomic-embed-text
```

### LiteLLM (Universal Proxy)

**Requirements:**
- Provider-specific API key (Azure, OpenAI, Anthropic, etc.)
- Provider-specific configuration (base URL, version, etc.)

**Model Format:**
```bash
provider/model_id

Examples:
- azure/gpt-5
- openai/gpt-4o
- anthropic/claude-sonnet-4-5-20250929
- moonshot/kimi-k2-thinking
- openrouter/openrouter/polaris-alpha
```

**Environment Variables (Azure Example):**
```bash
export AZURE_API_KEY=your_key
export AZURE_API_BASE=https://your-endpoint.openai.azure.com/
export AZURE_API_VERSION=2024-12-01-preview
export CYBER_AGENT_LLM_MODEL=azure/gpt-5
export CYBER_AGENT_EMBEDDING_MODEL=azure/text-embedding-3-large
```

**Environment Variables (OpenAI Example):**
```bash
export OPENAI_API_KEY=your_key
export CYBER_AGENT_LLM_MODEL=openai/gpt-4o
export CYBER_AGENT_EMBEDDING_MODEL=openai/text-embedding-3-large
```

## Configuration Alignment

### Embedding Dimensions
LiteLLM automatically aligns embedding dimensions based on the selected model:

```python
# If using azure/text-embedding-3-large
# Dimensions automatically set to 3072

# If using openai/text-embedding-ada-002
# Dimensions automatically set to 1536
```

### Memory System Alignment
When using Moonshot or other OpenAI-compatible providers, the memory system (Mem0) requires:

```bash
export OPENAI_API_KEY=your_moonshot_key  # For Mem0 compatibility
export MEM0_LLM_MODEL=azure/gpt-4o       # Use Azure/Bedrock for memory LLM
```

The `align_mem0_config()` function automatically handles this alignment.

## Context Window Fallbacks

Configure fallback model chains for quota exhaustion:

```bash
export CYBER_CONTEXT_WINDOW_FALLBACKS='[
  {"azure/gpt-5": ["azure/gpt-4o", "azure/gpt-4"]},
  {"anthropic/claude-opus": ["anthropic/claude-sonnet-4-5"]}
]'
```

If the primary model hits quota, the system automatically falls back to alternatives.

## Validation

All providers are validated before use:

**Bedrock Validation:**
- AWS credentials present
- Region configured
- Model access verified

**Ollama Validation:**
- Server reachable at configured host
- Model pulled and available
- Server health check passes

**LiteLLM Validation:**
- Required API keys present (Azure, OpenAI, etc.)
- Base URLs configured (for Azure)
- API versions set (for Azure)

Validation failures provide clear error messages with remediation steps.
