# Models Module

Model creation, capability detection, and models.dev API integration.

## Files

### factory.py
Model instance creation for all providers.

**Functions:**
- `create_bedrock_model(model_id, region, provider)` - Create AWS Bedrock model
- `create_ollama_model(model_id, provider)` - Create Ollama local model
- `create_litellm_model(model_id, region, provider)` - Create LiteLLM proxy model

**Features:**
- Five-tier prompt token limit resolution
- Context window fallback support
- Swarm specialist configuration
- Defensive validation with safe defaults

```python
from modules.config.models import create_bedrock_model

model = create_bedrock_model(
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name="us-east-1",
    provider="bedrock"
)
```

### capabilities.py
Model capability detection and limit resolution.

**Functions:**
- `supports_reasoning_model(model_id)` - Check for extended reasoning support
- `get_capabilities(model_id, default_provider)` - Get model capabilities from models.dev
- `get_model_input_limit(model_id, provider)` - Get context window limit
- `get_provider_default_limit(provider)` - Get provider-specific default limits

**Reasoning Models:**
- OpenAI: GPT-5 family, O-series (o3/o4, mini variants)
- Anthropic: Claude Sonnet 4/4.5, Opus
- Moonshot: Kimi K2 thinking variants

```python
from modules.config.models import supports_reasoning_model

if supports_reasoning_model("azure/gpt-5"):
    # Enable extended reasoning features
    pass
```

### dev_client.py
Models.dev API client with caching and fallback for authoritative model metadata.

**Three-Tier System:**
1. **Memory cache** - Already loaded data (fastest)
2. **Disk cache** - `~/.cache/cyber-autoagent/models.json` (24h TTL)
3. **Live API** - `https://models.dev/api.json` (requires internet)
4. **Snapshot fallback** - `models_snapshot.json` (bundled, works offline)

**Data Provided:**
- Token limits (context window, max output tokens)
- Capabilities (reasoning, tool calling, attachments)
- Pricing (per million tokens)
- Modalities (text, image, audio, video)

**API:**
```python
from modules.config.models.dev_client import get_models_client

client = get_models_client()

# Get token limits
limits = client.get_limits("azure/gpt-5")
print(f"Context: {limits.context}, Output: {limits.output}")
# Output: Context: 272000, Output: 128000

# Get capabilities
caps = client.get_capabilities("moonshot/kimi-k2-thinking")
print(f"Reasoning: {caps.reasoning}, Tools: {caps.tool_call}")
# Output: Reasoning: True, Tools: True

# Get pricing
pricing = client.get_pricing("anthropic/claude-sonnet-4-5-20250929")
print(f"Input: ${pricing.input}, Output: ${pricing.output}")
# Output: Input: $3.0, Output: $15.0
```

### models_snapshot.json
Embedded snapshot of models.dev database for offline operation.

**Contents:**
- 58 providers (Azure, Bedrock, OpenAI, Anthropic, Moonshot, etc.)
- 1,100+ models
- Updated weekly

**Purpose:**
- Enables offline operation
- Provides fallback when API fails
- Ensures first-run works without internet
- Accurate token limit detection

**Update Process:**
```bash
# Manual update
curl -o src/modules/config/models/models_snapshot.json \
     https://models.dev/api.json

# Verify
python3 -c "import json; json.load(open('src/modules/config/models/models_snapshot.json'))"
```

## Usage Examples

### Creating Models

```python
from modules.config.models import (
    create_bedrock_model,
    create_ollama_model,
    create_litellm_model,
)

# Bedrock
bedrock_model = create_bedrock_model(
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name="us-east-1"
)

# Ollama
ollama_model = create_ollama_model(
    model_id="qwen3-coder:30b-a3b-q4_K_M"
)

# LiteLLM (Azure)
litellm_model = create_litellm_model(
    model_id="azure/gpt-5",
    region_name="eastus"
)
```

### Checking Capabilities

```python
from modules.config.models import supports_reasoning_model, get_capabilities

# Quick reasoning check
if supports_reasoning_model("azure/gpt-5"):
    print("Extended reasoning available")

# Comprehensive capabilities
caps = get_capabilities("azure/gpt-5", "litellm")
if caps:
    print(f"Tools: {caps.tool_call}, Attachments: {caps.attachment}")
```

### Getting Model Limits

```python
from modules.config.models.dev_client import get_models_client

client = get_models_client()

# Get limits for safe token allocation
limits = client.get_limits("azure/gpt-5")
safe_max = int(limits.output * 0.5)  # Use 50% for safety margin
print(f"Safe max_tokens: {safe_max}")
# Output: Safe max_tokens: 64000
```

## Token Limit Resolution

The factory uses a **five-tier precedence** for prompt token limits:

1. Explicit override: `CYBER_CONTEXT_WINDOW` environment variable
2. Models.dev API: Authoritative model registry
3. Context window fallbacks: `CYBER_CONTEXT_WINDOW_FALLBACKS` mappings
4. Capability detection: Provider-specific defaults
5. Safe fallback: 128,000 tokens (works for most models)

This ensures accurate token limits for all 300+ supported providers.

## Offline Support

The `models_snapshot.json` file enables offline operation. Without it, the application requires internet connectivity for initial model capability detection.
