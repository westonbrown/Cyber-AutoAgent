# System Utilities Module

System-level utilities for environment management, logging, validation, and defaults.

## Files

### environment.py
Environment setup and initialization functions.

**Key Functions:**
- `auto_setup()` - Automatic environment configuration
- `setup_logging(debug)` - Configure application logging
- `clean_operation_memory(target, provider)` - Clean memory for target

### env_reader.py
Type-safe environment variable reading with change detection.

**API:**
```python
from modules.config.system import EnvironmentReader

env = EnvironmentReader()

# Type-safe reading
api_key = env.get("AZURE_API_KEY", "")
debug = env.get_bool("CYBER_DEBUG", False)
max_tokens = env.get_int("CYBER_LLM_MAX_TOKENS", 4096)
temperature = env.get_float("CYBER_LLM_TEMPERATURE", 0.95)

# Change detection (MD5-based)
if env.has_changed():
    print("Environment variables changed since last check")
```

**Features:**
- Type conversion (string, bool, int, float)
- Default value support
- Change detection for configuration reloading
- No side effects (read-only)

### logger.py
Logging factory and SDK logging configuration.

**Functions:**
- `get_logger(name)` - Get or create logger instance
- `configure_sdk_logging(enable_debug)` - Configure Strands SDK logging
- `initialize_logger_factory(level, format)` - Initialize logging system

**Features:**
- Logger registry (singleton pattern)
- Hierarchical logger names
- SDK warning suppression
- Configurable log levels

```python
from modules.config.system.logger import get_logger

logger = get_logger("MyModule")
logger.info("Processing started")
```

### defaults.py
Default configurations for all three providers.

**Functions:**
- `build_default_configs()` - Build all provider defaults
- `build_ollama_defaults()` - Ollama-specific defaults
- `build_bedrock_defaults()` - Bedrock-specific defaults
- `build_litellm_defaults()` - LiteLLM-specific defaults

**Default Values:**
- LLM: temperature=0.95, max_tokens=4096
- Embedding: dimensions=1536 (configurable per provider)
- Memory: FAISS backend, auto initialization
- Evaluation: Ragas with basic metrics
- Swarm: Small, fast model for specialists

```python
from modules.config.system.defaults import build_default_configs

defaults = build_default_configs()
ollama_config = defaults["ollama"]
bedrock_config = defaults["bedrock"]
litellm_config = defaults["litellm"]
```

### validation.py
Provider requirement validation.

**Function:**
```python
validate_provider(provider, env_reader, ollama_host, region, server_config)
```

**Validates:**
- **Bedrock**: AWS credentials, region, model access
- **Ollama**: Server connectivity, model availability
- **LiteLLM**: Provider-specific API keys (Azure, OpenAI, etc.)

**Example:**
```python
from modules.config.system import validate_provider, EnvironmentReader

env = EnvironmentReader()
validate_provider("bedrock", env, region="us-east-1")
# Raises EnvironmentError if requirements not met
```

**Error Handling:**
- Raises `EnvironmentError` with clear messages
- Provides remediation instructions
- Validates network connectivity
- Checks model availability

## Usage Patterns

### Environment Setup
```python
from modules.config.system import auto_setup

# Automatic environment configuration
auto_setup()
```

### Configuration Building
```python
from modules.config.system import build_default_configs, EnvironmentReader

# Get defaults for all providers
defaults = build_default_configs()

# Read environment
env = EnvironmentReader()
azure_key = env.get("AZURE_API_KEY")

# Merge: defaults + environment overrides + CLI args
```

### Logging Configuration
```python
from modules.config.system import setup_logging, configure_sdk_logging

# Setup application logging
setup_logging(debug=True)

# Configure SDK logging
configure_sdk_logging(enable_debug=False)
```

### Validation Before Use
```python
from modules.config.system import validate_provider, EnvironmentReader

env = EnvironmentReader()

try:
    validate_provider("bedrock", env, region="us-east-1")
    print("Bedrock configuration valid")
except EnvironmentError as e:
    print(f"Configuration error: {e}")
```

## Architecture

Each module has a single responsibility:
- `environment.py` - Setup and initialization
- `env_reader.py` - Environment variable reading
- `logger.py` - Logging configuration
- `defaults.py` - Default value provision
- `validation.py` - Requirement validation

All configurations use type-safe dataclasses, and validation provides actionable error messages.
