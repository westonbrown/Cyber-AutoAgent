# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cyber-AutoAgent is an autonomous cybersecurity assessment tool powered by the Strands framework. It conducts authorized penetration testing with intelligent tool selection, natural language reasoning, and evidence collection capabilities. The system uses a **Single Agent Meta-Everything Architecture** where one primary agent dynamically extends its capabilities through meta-operations rather than deploying multiple competing agents.

**⚠️ IMPORTANT: This tool is for authorized security testing only. Use only in safe, sandboxed environments.**

## Development Commands

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_agent.py

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=src

# Run specific test by name
uv run pytest tests/test_agent.py::test_name -v
```

### Running the Agent

**React Terminal Interface (Recommended):**
```bash
# Build and run the React UI
cd src/modules/interfaces/react
npm install
npm run build
npm start

# Or run directly with parameters
node dist/index.js \
  --target "http://testphp.vulnweb.com" \
  --objective "Security assessment" \
  --auto-run
```

**Python CLI:**
```bash
# Basic usage with Bedrock
python src/cyberautoagent.py \
  --target "http://target.com" \
  --objective "Find SQL injection vulnerabilities" \
  --provider bedrock \
  --iterations 50

# Using Ollama (local)
python src/cyberautoagent.py \
  --target "http://target.com" \
  --objective "Security assessment" \
  --provider ollama \
  --model "llama3.2:3b"

# Using LiteLLM (universal provider)
python src/cyberautoagent.py \
  --target "http://target.com" \
  --objective "Security assessment" \
  --provider litellm \
  --model "openai/gpt-4o"
```

**Docker:**
```bash
# Build image
docker build -f docker/Dockerfile -t cyber-autoagent .

# Run with full stack (includes Langfuse observability)
cd docker
docker-compose up -d

# Run assessment in container
docker-compose run --rm cyber-autoagent

# With root access for dynamic tool installation
docker-compose run --user root --rm cyber-autoagent
```

### Code Quality
```bash
# Format code
black src tests

# Sort imports
isort src tests

# Type checking
mypy src

# Linting
pylint src
ruff check src
```

## Architecture Overview

### Core Design: Single Agent Meta-Everything

The system uses **one primary agent** that dynamically extends its capabilities through:

1. **Meta-Agent**: Swarm tool deploys sub-agents for parallel tasks, each with their own reasoning loops
2. **Meta-Tooling**: Editor and load_tool capabilities create custom tools at runtime
3. **Meta-Learning**: Continuous memory storage enables cross-session learning
4. **Meta-Cognition**: Self-reflection and confidence assessment drives strategic decisions

This avoids the coordination complexity of multi-agent systems while maintaining adaptability.

### Key Components

**Agent Core** (`src/modules/agents/`):
- `cyber_autoagent.py`: Main Strands agent creation, model configuration, and tool registration
- `report_agent.py`: Dedicated agent for generating security assessment reports

**Configuration** (`src/modules/config/`):
- `manager.py`: Centralized configuration system for all models, memory, and output settings
- `environment.py`: Environment setup, validation, and auto-discovery of security tools

**Tools** (`src/modules/tools/`):
- `memory.py`: Mem0 memory management (supports FAISS, OpenSearch, Mem0 Platform)
- `prompt_optimizer.py`: Automated prompt optimization system

**Handlers** (`src/modules/handlers/`):
- `callback.py`: Main ReasoningHandler for UI events and step tracking
- `react/react_bridge_handler.py`: Event bridge for React terminal interface
- `report_generator.py`: Report generation utilities

**Operation Plugins** (`src/modules/operation_plugins/`):
- `general/`: Web application security testing (SQL injection, XSS, etc.)
- `ctf/`: CTF challenge solving mode
- Each module has `execution_prompt.md` and `report_prompt.md`

**Evaluation** (`src/modules/evaluation/`):
- `evaluation.py`: Automated Ragas metrics evaluation
- `manager.py`: Langfuse integration and score tracking

**React Interface** (`src/modules/interfaces/react/`):
- TypeScript/React terminal UI with real-time operation monitoring
- Event protocol: `__CYBER_EVENT__` for Python→React communication

### Tool Hierarchy (Confidence-Based)

The agent selects tools based on confidence and task complexity:

1. **Specialized Security Tools** (via shell): nmap, sqlmap, nikto, metasploit - when vulnerability type is known
2. **Swarm Deployment**: Multiple approaches needed, medium confidence, parallel reconnaissance
3. **Meta-Tool Creation** (via editor + load_tool): Novel exploits, no existing tool fits

### Memory System

**Backend Selection Priority:**
1. Mem0 Platform (if `MEM0_API_KEY` set) - cloud-based
2. OpenSearch (if `OPENSEARCH_HOST` set) - remote service
3. FAISS (default) - local vector storage

**Memory Storage Structure:**
- Cross-operation: `./outputs/<target>/memory/` (persists across operations)
- Operation-specific: `./outputs/<target>/OP_<timestamp>/`

**Evidence Categories:**
- `finding`: Security vulnerabilities and evidence
- `plan`: Strategy and approach decisions
- `reflection`: Metacognitive assessments

### Strands Framework Integration

**Core Tools Available:**
- `shell`: Execute system commands (primary interface to security tools)
- `editor`: Create/modify files and custom tools
- `swarm`: Deploy parallel sub-agents
- `http_request`: Make HTTP requests for web testing
- `mem0_memory`: Store/retrieve findings and knowledge
- `load_tool`: Dynamically load created tools
- `stop`: Terminate execution

**Tool Router Hook:**
- Automatically maps unknown tool names to shell commands
- Location: `src/modules/agents/cyber_autoagent.py::_ToolRouterHook`
- Example: `nmap` tool use → `shell("nmap ...")`

### Observability & Evaluation

**Langfuse Tracing** (enabled in docker-compose):
- Endpoint: http://localhost:3000 (login: admin@cyber-autoagent.com / changeme)
- Tracks all tool executions, token usage, memory operations
- Environment: `ENABLE_OBSERVABILITY=true`

**Ragas Evaluation Metrics:**
- Tool Selection Accuracy (0.0-1.0)
- Evidence Quality (0.0-1.0)
- Answer Relevancy (0.0-1.0)
- Context Precision (0.0-1.0)
- Environment: `ENABLE_AUTO_EVALUATION=true`

## Configuration System

All configuration is centralized in `src/modules/config/manager.py`:

**Key Classes:**
- `ModelProvider`: Enum for bedrock, ollama, litellm
- `LLMConfig`, `EmbeddingConfig`, `MemoryConfig`: Type-safe model configurations
- `ServerConfig`: Complete provider configuration
- `ConfigManager`: Central manager with caching and validation

**Environment Variable Overrides:**
```bash
# Provider selection
CYBER_AGENT_PROVIDER=bedrock|ollama|litellm

# Model overrides
CYBER_AGENT_LLM_MODEL=model-id
CYBER_AGENT_EMBEDDING_MODEL=model-id
CYBER_AGENT_EVALUATION_MODEL=model-id
CYBER_AGENT_SWARM_MODEL=model-id

# LLM parameters
CYBER_AGENT_TEMPERATURE=0.95
CYBER_AGENT_MAX_TOKENS=32000
CYBER_AGENT_TOP_P=0.999

# Memory backend
MEM0_API_KEY=your_key  # For Mem0 Platform
OPENSEARCH_HOST=your_host  # For OpenSearch
# (No env var needed for FAISS - it's the default)

# Output configuration
CYBER_AGENT_OUTPUT_DIR=./outputs
CYBER_AGENT_ENABLE_UNIFIED_OUTPUT=true

# Observability
ENABLE_OBSERVABILITY=true
ENABLE_AUTO_EVALUATION=true
LANGFUSE_HOST=http://langfuse-web:3000
```

**Unified Output Structure:**
```
./outputs/
└── <target>/
    ├── OP_<timestamp>/          # Operation-specific files
    │   ├── report.md            # Security findings
    │   ├── cyber_operations.log # Operation log
    │   ├── artifacts/           # Tool outputs
    │   └── tools/               # Custom created tools
    └── memory/                   # Cross-operation memory
        ├── mem0.faiss
        └── mem0.pkl
```

## Model Providers

### Bedrock (AWS)
- Default model: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
- Supports thinking models with extended reasoning
- Authentication: AWS credentials or bearer token (`AWS_BEARER_TOKEN_BEDROCK`)
- Configuration in `manager.py::_default_configs["bedrock"]`

### Ollama (Local)
- Default model: `llama3.2:3b`
- Host auto-detection: localhost or host.docker.internal
- Models must be pulled before use: `ollama pull model-name`
- Configuration in `manager.py::_default_configs["ollama"]`

### LiteLLM (Universal)
- Supports 100+ providers (OpenAI, Anthropic, Google, Azure, X.AI, etc.)
- Model format: `provider/model-name` (e.g., `openai/gpt-4o`, `xai/grok-4-latest`)
- Auto-caps max_tokens via `litellm.get_max_tokens()`
- Configuration in `manager.py::_default_configs["litellm"]`

**Important:** LiteLLM does NOT support AWS bearer tokens - use standard credentials only.

### Anthropic OAuth (Claude Max Billing)
- Default model: `claude-opus-4-latest` with automatic fallback to `claude-sonnet-4-latest`
- **Uses `-latest` aliases for automatic model updates** (or specify exact versions for reproducibility)
- **Bills against Claude Max unlimited quota** instead of per-token API usage
- **Automatic fallback on rate limits**: Opus → Sonnet → Haiku (configurable)
- Authentication: OAuth flow (interactive browser-based)
- First run prompts for authentication, token stored in `~/.config/cyber-autoagent/.claude_oauth`
- Auto-refresh token when expired (human-in-loop fallback if refresh fails)
- Spoofs Claude Code to ensure requests count against Claude Max
- Configuration in `manager.py::_default_configs["anthropic_oauth"]`
- **Note:** Anthropic doesn't provide embeddings - defaults to `multi-qa-MiniLM-L6-cos-v1` (local)

**Usage:**
```bash
# Set provider
export CYBER_AGENT_PROVIDER=anthropic_oauth

# Install sentence-transformers for local embeddings (recommended)
pip install sentence-transformers

# Run - will prompt for OAuth on first use
python src/cyberautoagent.py \
  --provider anthropic_oauth \
  --target "http://testphp.vulnweb.com" \
  --objective "Security assessment"
```

**Model Selection:**
Uses Anthropic's model aliases that automatically point to the latest version:
- `claude-opus-4-latest` - Latest Opus 4 (most capable, default)
- `claude-sonnet-4-latest` - Latest Sonnet 4 (balanced)
- `claude-3-7-sonnet-latest` - Latest Sonnet 3.7
- `claude-3-5-haiku-latest` - Latest Haiku (fastest)

Or specify exact versions for reproducibility:
- `claude-opus-4-20250514`, `claude-sonnet-4-20250514`, etc.

**Automatic Model Fallback:**
The OAuth provider includes intelligent fallback to handle rate limits:
- **Default**: Opus (best) → Sonnet (balanced) → Haiku (fast)
- Uses `-latest` aliases to automatically get newest versions
- Retries primary model up to 3 times with exponential backoff
- Automatically switches to fallback model when rate limited
- Logs all fallback events for visibility
- Configure via environment variables:
  - `ANTHROPIC_OAUTH_FALLBACK_ENABLED=true` (default)
  - `ANTHROPIC_OAUTH_FALLBACK_MODEL=claude-sonnet-4-latest`
  - `ANTHROPIC_OAUTH_MAX_RETRIES=3`
  - `ANTHROPIC_OAUTH_RETRY_DELAY=1.0`

**OAuth Implementation Details:**
- Client ID: `9d1c250a-e61b-44d9-88ed-5944d1962f5e` (Claude Code's official ID)
- Uses PKCE for security
- Adds headers: `Authorization: Bearer {token}`, `anthropic-beta: oauth-2025-04-20`, `User-Agent: ai-sdk/anthropic`
- System message: "You are Claude Code, Anthropic's official CLI for Claude."
- Implementation: `src/modules/auth/anthropic_oauth.py`, `src/modules/models/anthropic_oauth_model.py`, `src/modules/models/anthropic_oauth_fallback.py`

## Event System (React UI)

The React terminal interface receives structured events via stdout:

**Event Protocol:**
```python
# Events are emitted with prefix: __CYBER_EVENT__
{
  "type": "tool_start|tool_end|reasoning|step_header|metrics_update|operation_init",
  "data": {...}
}
```

**Key Event Types:**
- `operation_init`: Operation metadata and configuration
- `step_header`: Iteration tracking (step X/max_steps)
- `tool_start`: Tool invocation with parameters
- `tool_end`: Tool completion with results
- `reasoning`: Agent decision-making context
- `metrics_update`: Token usage, cost, duration
- `termination_reason`: Why the operation ended

**Implementation:**
- `src/modules/handlers/react/react_bridge_handler.py`: Event emitter
- `src/modules/handlers/react/tool_emitters.py`: Tool-specific events

## Testing Considerations

**Key Test Files:**
- `tests/test_agent.py`: Core agent functionality
- `tests/test_config.py`: Configuration system
- `tests/test_memory_*.py`: Memory system integration
- `tests/test_prompt_*.py`: Prompt management

**Test Fixtures:**
- Use pytest fixtures for configuration mocking
- Memory system tests expect specific path structures
- Mock AWS/Bedrock calls to avoid credential requirements

**Common Patterns:**
```python
# Mock configuration
@pytest.fixture
def mock_config(mocker):
    return mocker.patch('modules.config.manager.get_config_manager')

# Mock memory client
@pytest.fixture
def mock_memory(mocker):
    return mocker.patch('modules.tools.memory.get_memory_client')
```

## Security Tool Integration

**Auto-Discovery:**
- `src/modules/config/environment.py::auto_setup()` discovers available tools
- Uses `which` command to check for: nmap, nikto, sqlmap, gobuster, etc.
- Tools accessed via `shell` tool, not as direct Strands tools

**Dynamic Installation:**
- Agent can install packages at runtime if running as root
- Docker default: non-root user (`cyberagent`) for security
- Override: `docker run --user root` to enable installation

## Prompt Management

**Module-Based System:**
- Each operation plugin has `execution_prompt.md` and `report_prompt.md`
- Location: `src/modules/operation_plugins/<module>/`
- Loader: `src/modules/prompts/factory.py::ModulePromptLoader`

**Langfuse Integration:**
- Dynamic prompt updates via Langfuse API
- Environment: `ENABLE_LANGFUSE_PROMPTS=true`
- Label: `LANGFUSE_PROMPT_LABEL=production|staging|dev`
- Cache TTL: `LANGFUSE_PROMPT_CACHE_TTL=300` (seconds)

**Prompt Optimization:**
- `src/modules/tools/prompt_optimizer.py` auto-optimizes prompts
- Stores optimized version in `<operation_root>/execution_prompt_optimized.txt`
- Uses feedback loop for continuous improvement

## Key Implementation Patterns

### Adding a New Operation Plugin

1. Create directory: `src/modules/operation_plugins/<module_name>/`
2. Add prompts: `execution_prompt.md`, `report_prompt.md`
3. (Optional) Add tools: `tools/__init__.py`
4. Update CLI: Add to `--module` choices in `cyberautoagent.py`

### Adding a New Tool

**For Strands SDK tools:**
```python
# In cyber_autoagent.py
from strands_tools.my_tool import my_tool

tools = [shell, editor, swarm, my_tool, ...]
```

**For custom meta-tools:**
```python
# Agent creates at runtime using editor tool
# Then loads with load_tool
# Stored in outputs/<target>/OP_<id>/tools/
```

### Adding Configuration Options

1. Add dataclass field in `src/modules/config/manager.py`
2. Add environment variable parsing in `_apply_environment_overrides()`
3. Update `.env.example` with documentation
4. Add to `ServerConfig` dataclass

### Extending Memory Backend

1. Add configuration in `MemoryVectorStoreConfig`
2. Update `get_mem0_service_config()` in `ConfigManager`
3. Add initialization in `src/modules/tools/memory.py`

## Common Development Tasks

### Adding a New Model Provider

1. Add enum to `ModelProvider` in `manager.py`
2. Add default configs in `_initialize_default_configs()`
3. Add validation in `validate_requirements()`
4. Update CLI `--provider` choices

### Modifying Agent Behavior

- Main loop: `src/cyberautoagent.py::main()`
- Agent creation: `src/modules/agents/cyber_autoagent.py::create_agent()`
- Step tracking: `src/modules/handlers/callback.py::ReasoningHandler`
- Tool routing: `src/modules/agents/cyber_autoagent.py::_ToolRouterHook`

### Debugging Issues

**Enable verbose logging:**
```bash
python src/cyberautoagent.py --verbose ...
```

**Check logs:**
- Operation log: `./outputs/<target>/OP_<timestamp>/cyber_operations.log`
- React UI: Browser console for frontend events

**Common issues:**
- Memory path mismatches: Check `sanitize_target_name()` output
- Tool not found: Verify with `which <tool>` in container
- Provider errors: Check credentials and model access
- Swarm failures: Enable SDK logging in `configure_sdk_logging()`

## Dependencies

**Core:**
- `strands-agents==1.11.0`: Agent framework
- `strands-agents-tools==0.2.9`: Standard tools
- `mem0ai`: Memory management
- `boto3>=1.39.10`: AWS Bedrock
- `ollama>=0.1.0`: Local models
- `litellm`: Universal provider gateway

**Observability:**
- `langfuse>=2.0.0`: Tracing
- `ragas>=0.3.0`: Evaluation metrics
- `opentelemetry-*`: OTLP export

**AI/ML:**
- `langchain-aws>=0.2.0`: AWS integrations
- `langchain-ollama>=0.2.0`: Ollama integrations
- `faiss-cpu`: Vector storage

## Project Structure Notes

- `src/cyberautoagent.py`: CLI entry point with telemetry setup
- `src/modules/`: All core functionality (modular architecture since v0.1.2)
- `docker/`: Containerization and docker-compose stack
- `tests/`: Pytest test suite
- `benchmark_harness/`: Performance benchmarking (separate subsystem)
- `docs/`: Detailed documentation (architecture, deployment, memory, etc.)

## Important Caveats

1. **Memory Paths**: Sanitization must be consistent. Use `sanitize_target_name()` from `handlers.utils`
2. **Provider Switching**: LiteLLM and native Bedrock have different auth - bearer tokens work only with native Bedrock
3. **Thinking Models**: Require specific config with `anthropic_beta` flags and thinking budgets
4. **Swarm Operations**: Sub-agents inherit memory access but operate independently
5. **Tool Timeouts**: Default shell timeout is 600s - adjust via `SHELL_DEFAULT_TIMEOUT`
6. **React UI Mode**: Detected via `CYBER_UI_MODE=react` env var, suppresses CLI banner/output
