# Configuration Module

Configuration system for Cyber-AutoAgent with support for AWS Bedrock, Ollama, and LiteLLM (300+ providers).

## Directory Structure

```
config/
├── __init__.py          # Public API exports
├── manager.py           # Core configuration orchestration
├── types.py             # Type definitions and constants
├── models/              # Model creation and capabilities
│   ├── factory.py       # Model instance creation
│   ├── capabilities.py  # Model capability detection
│   └── dev_client.py    # Models.dev API client
├── system/              # System utilities
│   ├── environment.py   # Environment setup and initialization
│   ├── env_reader.py    # Environment variable reading
│   ├── logger.py        # Logging configuration
│   ├── defaults.py      # Default configurations
│   └── validation.py    # Provider validation
└── providers/           # Provider-specific configuration
    ├── bedrock_config.py
    ├── ollama_config.py
    └── litellm_config.py
```

## Quick Start

```python
from modules.config import (
    ConfigManager,
    get_config_manager,
    AgentConfig,
)

# Get configuration manager instance
config = get_config_manager()

# Get server configuration for a provider
server_config = config.get_server_config("bedrock")

# Get LLM configuration with overrides
llm_config = config.get_llm_config(server_config, temperature=0.8)

# Create agent configuration
agent_config = AgentConfig(
    target="example.com",
    objective="Security assessment",
    provider="bedrock",
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
)
```

## Configuration Precedence

The configuration system uses a **three-tier precedence hierarchy**:

1. **CLI/API Arguments** (Highest priority)
   - Command-line flags: `--provider`, `--model`, `--iterations`
   - Direct API parameters passed to configuration methods

2. **Environment Variables** (Override defaults)
   - `CYBER_AGENT_LLM_MODEL` - Main model ID
   - `CYBER_AGENT_EMBEDDING_MODEL` - Embedding model
   - `REASONING_EFFORT` - Reasoning configuration (low/medium/high)
   - Provider-specific: `AZURE_API_KEY`, `AWS_REGION`, etc.

3. **Provider Defaults** (Fallback)
   - Built by `system/defaults.py`
   - Provider-specific safe defaults
   - Always available as fallback

## Providers

### AWS Bedrock
```bash
export AWS_REGION=us-east-1
export CYBER_AGENT_LLM_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

### Ollama (Local)
```bash
export OLLAMA_HOST=http://localhost:11434
export CYBER_AGENT_LLM_MODEL=qwen3-coder:30b-a3b-q4_K_M
```

### LiteLLM (300+ Providers)
```bash
export AZURE_API_KEY=your_key
export AZURE_API_BASE=https://your-endpoint.openai.azure.com/
export CYBER_AGENT_LLM_MODEL=azure/gpt-5
```

## Key Components

### ConfigManager (`manager.py`)
Central orchestration class that:
- Manages provider-specific configurations
- Handles environment variable reading
- Validates provider requirements
- Provides safe token limits via models.dev integration

### Type Definitions (`types.py`)
All configuration dataclasses and enums:
- `ServerConfig`, `LLMConfig`, `EmbeddingConfig`
- `MemoryConfig`, `SwarmConfig`, `AgentConfig`
- `ModelProvider` enum

### Model Factory (`models/factory.py`)
Creates model instances for all providers:
- `create_bedrock_model()` - AWS Bedrock models
- `create_ollama_model()` - Local Ollama models
- `create_litellm_model()` - LiteLLM proxy for 300+ providers

### Validation (`system/validation.py`)
Provider requirement validation:
- Bedrock: AWS credentials + region + model access
- Ollama: Server connectivity + model availability
- LiteLLM: Provider-specific API keys

## Environment Variables

### Core Configuration
- `CYBER_AGENT_PROVIDER` - Provider choice (bedrock/ollama/litellm)
- `CYBER_AGENT_LLM_MODEL` - Main LLM model ID
- `CYBER_AGENT_EMBEDDING_MODEL` - Embedding model ID
- `REASONING_EFFORT` - Reasoning configuration (low/medium/high)

### Model Limits
- `CYBER_LLM_MAX_TOKENS` - Override LLM max tokens
- `CYBER_SWARM_MAX_TOKENS` - Override swarm specialist max tokens
- `CYBER_CONTEXT_WINDOW_FALLBACKS` - Model fallback mappings (JSON)

### Memory Configuration
- `MEM0_API_KEY` - Mem0 Platform API key
- `MEM0_LLM_MODEL` - Memory system LLM
- `OPENSEARCH_HOST` - OpenSearch endpoint
- `MEMORY_BACKEND` - Force backend (mem0/opensearch/faiss)

### Provider Keys
- `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MOONSHOT_API_KEY`
- `OPENROUTER_API_KEY`, etc.

See individual subfolder READMEs for detailed documentation.
