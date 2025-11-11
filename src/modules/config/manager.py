#!/usr/bin/env python3
"""
Centralized model configuration management for Cyber-AutoAgent.

This module provides a unified configuration system for all model-related
settings, including LLM models, embedding models, and provider configurations.
It supports multiple providers (AWS Bedrock,Litellm, Ollama) and allows for easy
environment variable overrides.

Key Components:
- ModelProvider: Enum for supported providers
- Configuration dataclasses: Type-safe configuration objects
- ConfigManager: Central configuration management
- Environment variable support with fallbacks
- Validation and error handling
"""

import importlib.util
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Literal

import boto3
import litellm
import ollama
import requests

from modules.handlers.utils import get_output_path, sanitize_target_name
from modules.config.logger_factory import get_logger

litellm.drop_params = True
litellm.modify_params = True
litellm.num_retries = 5
litellm.respect_retry_after_header = True

logger = get_logger("Config.Manager")


LITELLM_EMBEDDING_DEFAULTS: Dict[str, Tuple[str, int]] = {
    "openai": ("openai/text-embedding-3-small", 1536),
    "azure": ("azure/text-embedding-3-small", 1536),
    "gemini": ("models/text-embedding-004", 768),
    "google": ("models/text-embedding-004", 768),
    "mistral": ("multi-qa-MiniLM-L6-cos-v1", 384),
    "sagemaker": ("multi-qa-MiniLM-L6-cos-v1", 384),
    "xai": ("multi-qa-MiniLM-L6-cos-v1", 384),
}
DEFAULT_LITELLM_EMBEDDING: Tuple[str, int] = ("multi-qa-MiniLM-L6-cos-v1", 384)

EMBEDDING_DIMENSIONS: Dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "azure/text-embedding-3-small": 1536,
    "azure/text-embedding-3-large": 3072,
    "azure/text-embedding-ada-002": 1536,
    "openai/text-embedding-3-small": 1536,
    "openai/text-embedding-3-large": 3072,
    "openai/text-embedding-ada-002": 1536,
    "models/text-embedding-004": 768,
    "text-embedding-004": 768,
    "gemini/text-embedding-004": 768,
    "amazon.titan-embed-text-v1": 1536,
    "amazon.titan-embed-text-v2:0": 1024,
    "cohere.embed-english-v3": 1024,
    "cohere.embed-multilingual-v3": 1024,
    "multi-qa-MiniLM-L6-cos-v1": 384,
}
MEM0_PROVIDER_MAP: Dict[str, str] = {
    "bedrock": "aws_bedrock",
    "openai": "openai",
    "azure": "azure_openai",
    "anthropic": "anthropic",
    "gemini": "gemini",
    "google": "gemini",
    "deepseek": "deepseek",
    "together": "together",
    "groq": "groq",
    "xai": "xai",
    "lmstudio": "lmstudio",
    "vllm": "vllm",
    "mistral": "huggingface",
    "sagemaker": "huggingface",
}


class ModelProvider(Enum):
    """Supported model providers."""

    AWS_BEDROCK = "aws_bedrock"
    OLLAMA = "ollama"
    LITELLM = "litellm"  # Universal provider gateway supporting 100+ model providers


@dataclass
class ModelConfig:
    """Base configuration for any model."""

    provider: ModelProvider
    model_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate model configuration."""
        if not self.model_id:
            raise ValueError("model_id cannot be empty")
        if not isinstance(self.provider, ModelProvider):
            raise ValueError(
                f"provider must be a ModelProvider enum, got {type(self.provider)}"
            )


@dataclass
class LLMConfig(ModelConfig):
    """Configuration for LLM models."""

    temperature: float = 0.95
    max_tokens: int = 4096
    top_p: Optional[float] = None

    def __post_init__(self):
        super().__post_init__()
        # Add LLM-specific parameters to the parameters dict
        params = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        # Only include top_p if explicitly set (some providers like Anthropic reject both temperature and top_p)
        if self.top_p is not None:
            params["top_p"] = self.top_p
        self.parameters.update(params)


@dataclass
class EmbeddingConfig(ModelConfig):
    """Configuration for embedding models."""

    dimensions: int = 1024

    def __post_init__(self):
        super().__post_init__()
        # Add embedding-specific parameters
        self.parameters.update({"dimensions": self.dimensions})


@dataclass
class VectorStoreConfig:
    """Configuration for vector storage."""

    provider: str = "faiss"
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryLLMConfig(ModelConfig):
    """Configuration for memory-specific LLM models."""

    temperature: float = 0.1
    max_tokens: int = 2000
    aws_region: str = "us-east-1"  # Default, can be overridden via environment

    def __post_init__(self):
        super().__post_init__()
        self.parameters.update(
            {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "aws_region": self.aws_region,
            }
        )


@dataclass
class MemoryEmbeddingConfig(ModelConfig):
    """Configuration for memory-specific embedding models."""

    aws_region: str = "us-east-1"  # Default, can be overridden via environment
    dimensions: int = 1024

    def __post_init__(self):
        super().__post_init__()
        self.parameters.update(
            {"aws_region": self.aws_region, "dimensions": self.dimensions}
        )


@dataclass
class MemoryVectorStoreConfig:
    """Configuration for memory vector store with provider-specific settings."""

    provider: str = "faiss"
    opensearch_config: Dict[str, Any] = field(
        default_factory=lambda: {
            "port": 443,
            "collection_name": "mem0_memories",
            "embedding_model_dims": 1024,
            "pool_maxsize": 20,
            "use_ssl": True,
            "verify_certs": True,
        }
    )
    faiss_config: Dict[str, Any] = field(
        default_factory=lambda: {
            "embedding_model_dims": 1024,
        }
    )

    def get_config_for_provider(self, provider: str, **overrides) -> Dict[str, Any]:
        """Get configuration for specific provider."""
        if provider == "opensearch":
            config = self.opensearch_config.copy()
            config.update(overrides)
            return config
        if provider == "faiss":
            config = self.faiss_config.copy()
            config.update(overrides)
            return config
        return overrides


@dataclass
class MemoryConfig:
    """Configuration for memory system."""

    embedder: MemoryEmbeddingConfig
    llm: MemoryLLMConfig
    vector_store: MemoryVectorStoreConfig = field(
        default_factory=MemoryVectorStoreConfig
    )


@dataclass
class EvaluationConfig:
    """Configuration for evaluation system."""

    llm: ModelConfig
    embedding: ModelConfig
    # LLM-driven evaluation tunables
    min_tool_calls: int = 3
    min_evidence: int = 1
    max_wait_secs: int = 30
    poll_interval_secs: int = 5
    summary_max_chars: int = 8000
    # Rubric judge controls
    rubric_enabled: bool = False
    judge_temperature: float = 0.2
    judge_max_tokens: int = 800
    rubric_profile: str = "default"
    judge_system_prompt: Optional[str] = None
    judge_user_template: Optional[str] = None
    skip_if_insufficient_evidence: bool = True
    rationale_persist_mode: str = "metadata"


@dataclass
class SwarmConfig:
    """Configuration for swarm system."""

    llm: ModelConfig


def get_default_base_dir() -> str:
    """Get the default base directory for outputs.

    Returns:
        Default base directory path, preferring project root if detectable
    """
    # Try to detect if we're in a project directory structure
    cwd = os.getcwd()

    # Check if we're in the project root (contains pyproject.toml)
    if os.path.exists(os.path.join(cwd, "pyproject.toml")):
        return os.path.join(cwd, "outputs")

    # Check if we're in a subdirectory of the project
    # Look for project root by traversing up the directory tree
    current = cwd
    while current != os.path.dirname(current):  # Stop at filesystem root
        if os.path.exists(os.path.join(current, "pyproject.toml")):
            return os.path.join(current, "outputs")
        current = os.path.dirname(current)

    # Fallback to current working directory
    return os.path.join(cwd, "outputs")


@dataclass
class SDKConfig:
    """Configuration for Strands SDK-specific features."""

    # Hook system configuration
    enable_hooks: bool = True
    hook_timeout_ms: int = 1000

    # Streaming configuration
    enable_streaming: bool = True
    stream_buffer_ms: int = 0  # No buffering for real-time streaming

    # Conversation management
    conversation_window_size: int = 100

    # Telemetry configuration
    enable_telemetry: bool = True
    telemetry_sample_rate: float = 1.0

    # Performance settings
    max_concurrent_tools: int = 5
    tool_timeout_seconds: int = 300


@dataclass
class OutputConfig:
    """Configuration for output directory management."""

    base_dir: str = field(default_factory=get_default_base_dir)
    target_name: Optional[str] = None
    enable_unified_output: bool = True  # Default to enabled for new unified structure
    operation_id: Optional[str] = None  # Current operation ID for path generation


@dataclass
class MCPConnection:
    id: str
    transport: Literal["stdio", "sse", "streamable-http"]
    command: Optional[List[str]] = None
    server_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    plugins: List[str] = field(default_factory=list)
    timeoutSeconds: Optional[int] = None
    allowed_tools: List[str] = field(default_factory=list)


@dataclass
class MCPConfig:
    enabled: bool = field(default_factory=lambda: False)
    connections: List[MCPConnection] = field(default_factory=list)


@dataclass
class ServerConfig:
    """Complete server configuration."""

    server_type: str  # "bedrock", "ollama", or "litellm"
    llm: LLMConfig
    embedding: EmbeddingConfig
    memory: MemoryConfig
    evaluation: EvaluationConfig
    swarm: SwarmConfig
    mcp: MCPConfig = field(default_factory=MCPConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    sdk: SDKConfig = field(default_factory=SDKConfig)
    host: Optional[str] = None
    region: str = "us-east-1"  # Default, can be overridden via environment


class ConfigManager:
    """Central manager for model, memory, and SDK configuration.

    Provides provider defaults with environment overrides and lightweight
    validation helpers. Caches computed ServerConfig objects per provider.

    Serves as the single source of truth for all configuration access,
    including environment variables. All env var access should go through
    this class to ensure consistent behavior and proper cache invalidation.
    """

    def __init__(self):
        """Initialize configuration manager."""
        self._config_cache = {}
        self._default_configs = self._initialize_default_configs()
        self._env_snapshot = self._capture_env_snapshot()

    def _capture_env_snapshot(self) -> int:
        """Capture hash of current environment state for cache invalidation."""
        import hashlib

        # Create a stable hash of relevant environment variables
        env_data = json.dumps(dict(sorted(os.environ.items())), sort_keys=True)
        return int(hashlib.md5(env_data.encode()).hexdigest(), 16)

    def _has_env_changed(self) -> bool:
        """Check if environment variables have changed since last snapshot."""
        current_snapshot = self._capture_env_snapshot()
        if current_snapshot != self._env_snapshot:
            self._env_snapshot = current_snapshot
            return True
        return False

    def getenv(self, key: str, default: str = "") -> str:
        """Get environment variable value.

        Centralized accessor for all environment variable reads.
        Provides consistent interface and enables cache invalidation.

        Args:
            key: Environment variable name
            default: Default value if variable not set

        Returns:
            Environment variable value or default
        """
        return os.getenv(key, default)

    def getenv_bool(self, key: str, default: bool = False) -> bool:
        """Get environment variable as boolean.

        Args:
            key: Environment variable name
            default: Default value if variable not set

        Returns:
            Boolean value (true for "true", "1", "yes"; false otherwise)
        """
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes")

    def getenv_int(self, key: str, default: int = 0) -> int:
        """Get environment variable as integer.

        Args:
            key: Environment variable name
            default: Default value if variable not set or invalid

        Returns:
            Integer value or default if conversion fails
        """
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            logger.warning(
                "Invalid integer value for %s: %s, using default %d",
                key,
                value,
                default,
            )
            return default

    def getenv_float(self, key: str, default: float = 0.0) -> float:
        """Get environment variable as float.

        Args:
            key: Environment variable name
            default: Default value if variable not set or invalid

        Returns:
            Float value or default if conversion fails
        """
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(
                "Invalid float value for %s: %s, using default %f", key, value, default
            )
            return default

    def get_default_region(self) -> str:
        """Get the default AWS region with environment override support."""
        return self.getenv("AWS_REGION", "us-east-1")

    def get_thinking_models(self) -> List[str]:
        """Get list of models that support thinking capabilities."""
        return [
            "us.anthropic.claude-opus-4-20250514-v1:0",
            "us.anthropic.claude-opus-4-1-20250805-v1:0",
            "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "us.anthropic.claude-sonnet-4-20250514-v1:0",
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        ]

    def is_thinking_model(self, model_id: str) -> bool:
        """Check if a model supports thinking capabilities."""
        return model_id in self.get_thinking_models()

    def get_thinking_model_config(
        self, model_id: str, region_name: str
    ) -> Dict[str, Any]:
        """Get configuration for thinking-enabled models."""
        # Base beta flags for thinking models
        beta_flags = ["interleaved-thinking-2025-05-14"]

        # Add 1M context flag for Claude Sonnet 4 and 4.5
        if (
            "claude-sonnet-4-20250514" in model_id
            or "claude-sonnet-4-5-20250929" in model_id
        ):
            beta_flags.append("context-1m-2025-08-07")

        # Claude Sonnet 4.5 supports extended thinking with higher token limits
        if "claude-sonnet-4-5-20250929" in model_id:
            default_max_tokens = 16000
            default_thinking_budget = 7000
        else:
            default_max_tokens = 32000
            default_thinking_budget = 10000

        # Allow override via environment variables
        max_tokens = self.getenv_int("MAX_TOKENS", default_max_tokens)
        thinking_budget = self.getenv_int("THINKING_BUDGET", default_thinking_budget)

        return {
            "model_id": model_id,
            "region_name": region_name,
            "temperature": 1.0,
            "max_tokens": max_tokens,
            "additional_request_fields": {
                "anthropic_beta": beta_flags,
                "thinking": {"type": "enabled", "budget_tokens": thinking_budget},
            },
        }

    def get_standard_model_config(
        self, model_id: str, region_name: str, provider: str
    ) -> Dict[str, Any]:
        """Get configuration for standard (non-thinking) models."""
        provider_config = self.get_server_config(provider)
        llm_config = provider_config.llm

        config = {
            "model_id": model_id,
            "region_name": region_name,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
        }

        # Only include top_p if set (avoid conflicts with providers like Anthropic)
        if llm_config.top_p is not None:
            config["top_p"] = llm_config.top_p

        # Add 1M context support for Claude Sonnet 4 and 4.5
        if (
            "claude-sonnet-4-20250514" in model_id
            or "claude-sonnet-4-5-20250929" in model_id
        ):
            config["additional_request_fields"] = {
                "anthropic_beta": ["context-1m-2025-08-07"]
            }

        return config

    def get_local_model_config(self, model_id: str, provider: str) -> Dict[str, Any]:
        """Get configuration for local Ollama models."""
        provider_config = self.get_server_config(provider)
        llm_config = provider_config.llm

        return {
            "model_id": model_id,
            "host": self.get_ollama_host(),
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
        }

    def _initialize_default_configs(self) -> Dict[str, Dict[str, Any]]:
        """Initialize default configurations for all provider types."""
        return {
            "ollama": {
                "llm": LLMConfig(
                    provider=ModelProvider.OLLAMA,
                    model_id="llama3.2:3b",
                    temperature=0.95,
                    max_tokens=65000,
                ),
                "embedding": EmbeddingConfig(
                    provider=ModelProvider.OLLAMA,
                    model_id="mxbai-embed-large",
                    dimensions=1024,
                ),
                "memory_llm": MemoryLLMConfig(
                    provider=ModelProvider.OLLAMA,
                    model_id="llama3.2:3b",
                    temperature=0.1,
                    max_tokens=2000,
                    aws_region="ollama",
                ),
                "evaluation_llm": LLMConfig(
                    provider=ModelProvider.OLLAMA,
                    model_id="llama3.2:3b",
                    temperature=0.1,
                    max_tokens=2000,
                ),
                "swarm_llm": LLMConfig(
                    provider=ModelProvider.OLLAMA,
                    model_id="llama3.2:3b",
                    temperature=0.7,
                    max_tokens=4096,
                ),
                "host": None,  # Will be resolved dynamically
                "region": "ollama",
            },
            "bedrock": {
                "llm": LLMConfig(
                    provider=ModelProvider.AWS_BEDROCK,
                    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                    temperature=0.95,
                    max_tokens=32000,
                    # top_p removed - global.* models reject both temperature and top_p
                ),
                "embedding": EmbeddingConfig(
                    provider=ModelProvider.AWS_BEDROCK,
                    model_id="amazon.titan-embed-text-v2:0",
                    dimensions=1024,
                ),
                "memory_llm": MemoryLLMConfig(
                    provider=ModelProvider.AWS_BEDROCK,
                    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    temperature=0.1,
                    max_tokens=2000,
                    aws_region="us-east-1",  # Will be overridden by environment
                ),
                "evaluation_llm": LLMConfig(
                    provider=ModelProvider.AWS_BEDROCK,
                    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    temperature=0.1,
                    max_tokens=2000,
                ),
                "swarm_llm": LLMConfig(
                    provider=ModelProvider.AWS_BEDROCK,
                    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    temperature=0.7,
                    max_tokens=4096,
                ),
                "host": None,
                "region": "us-east-1",  # Will be overridden by environment
            },
            "litellm": {
                "llm": LLMConfig(
                    provider=ModelProvider.LITELLM,
                    model_id="bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",  # Default to Bedrock via LiteLLM
                    temperature=0.95,
                    max_tokens=32000,  # LiteLLM auto-caps based on model limits
                    # top_p omitted - LiteLLM forwards to various providers; Anthropic rejects both temperature and top_p
                ),
                "embedding": EmbeddingConfig(
                    provider=ModelProvider.LITELLM,
                    model_id="bedrock/amazon.titan-embed-text-v2:0",  # Default to Bedrock embedding via LiteLLM
                    dimensions=1024,
                ),
                "memory_llm": MemoryLLMConfig(
                    provider=ModelProvider.LITELLM,
                    model_id="bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    temperature=0.1,
                    max_tokens=2000,
                    aws_region="us-east-1",  # Will be overridden by environment
                ),
                "evaluation_llm": LLMConfig(
                    provider=ModelProvider.LITELLM,
                    model_id="bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    temperature=0.1,
                    max_tokens=2000,
                ),
                "swarm_llm": LLMConfig(
                    provider=ModelProvider.LITELLM,
                    model_id="bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    temperature=0.7,
                    max_tokens=4096,
                ),
                "host": None,
                "region": "us-east-1",  # Will be overridden by environment
            },
        }

    def get_server_config(self, provider: str, **overrides) -> ServerConfig:
        """Get complete provider configuration with optional overrides."""
        logger.debug("Getting server config for provider: %s", provider)

        # Invalidate cache if environment has changed
        if self._has_env_changed():
            logger.debug("Environment changed, invalidating config cache")
            self._config_cache.clear()

        # Build stable cache key from known scalar overrides only
        allowed_keys = (
            "model_id",
            "enable_hooks",
            "enable_streaming",
            "conversation_window_size",
        )
        parts: list[str] = [f"provider={provider}"]
        unsupported: list[str] = []
        for key in allowed_keys:
            if key in overrides:
                val = overrides.get(key)
                if isinstance(val, (str, int, float, bool)) or val is None:
                    parts.append(f"{key}={val}")
                else:
                    unsupported.append(key)
        if unsupported:
            logger.debug(
                "Ignoring non-scalar override keys for cache: %s",
                ", ".join(unsupported),
            )
        cache_key = "|".join(parts)
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        if provider not in self._default_configs:
            logger.error(
                "Provider %s not in available configs: %s",
                provider,
                list(self._default_configs.keys()),
            )
            raise ValueError(f"Unsupported provider type: {provider}")

        defaults = self._default_configs[provider].copy()

        # Apply environment variable overrides
        defaults = self._apply_environment_overrides(provider, defaults)

        # Apply function parameter overrides
        defaults.update(overrides)

        # Special handling for model_id override - apply to LLM configs
        if "model_id" in overrides:
            user_model = overrides["model_id"]
            # Update main LLM
            if "llm" in defaults and isinstance(defaults["llm"], LLMConfig):
                defaults["llm"].model_id = user_model
            # Update memory LLM
            if "memory_llm" in defaults and isinstance(
                defaults["memory_llm"], MemoryLLMConfig
            ):
                defaults["memory_llm"].model_id = user_model
            # Update evaluation LLM
            if "evaluation_llm" in defaults and isinstance(
                defaults["evaluation_llm"], LLMConfig
            ):
                defaults["evaluation_llm"].model_id = user_model
            # Don't override swarm LLM with user model - keep swarm using v2 for better performance
            # Swarm model can be overridden via CYBER_AGENT_SWARM_MODEL env var if needed
            # For Ollama, also use the same model for embeddings if mxbai-embed-large is not available
            if (
                provider == "ollama"
                and "embedding" in defaults
                and isinstance(defaults["embedding"], EmbeddingConfig)
            ):
                # Check if the default embedding model is available
                try:
                    client = ollama.Client(host=self.get_ollama_host())
                    models_response = client.list()
                    available_models = [
                        m.get("model", m.get("name", ""))
                        for m in models_response["models"]
                    ]
                    if not any(
                        "mxbai-embed-large" in model for model in available_models
                    ):
                        # Use the user's model for embeddings too
                        defaults["embedding"].model_id = user_model
                except Exception:
                    # Fallback to user's model if availability check fails
                    defaults["embedding"].model_id = user_model

        if provider == "litellm":
            self._align_litellm_defaults(defaults)

        # Build memory configuration
        memory_config = MemoryConfig(
            embedder=self._get_memory_embedder_config(provider, defaults),
            llm=self._get_memory_llm_config(provider, defaults),
            vector_store=MemoryVectorStoreConfig(),
        )

        # Build evaluation configuration (with env-aware defaults)
        evaluation_config = EvaluationConfig(
            llm=self._get_evaluation_llm_config(provider, defaults),
            embedding=self._get_evaluation_embedding_config(provider, defaults),
            min_tool_calls=self.getenv_int("EVAL_MIN_TOOL_CALLS", 3),
            min_evidence=self.getenv_int("EVAL_MIN_EVIDENCE", 1),
            max_wait_secs=self.getenv_int(
                "EVALUATION_MAX_WAIT_SECS", self.getenv_int("EVALUATION_WAIT_TIME", 30)
            ),
            poll_interval_secs=self.getenv_int("EVALUATION_POLL_INTERVAL_SECS", 5),
            summary_max_chars=self.getenv_int("EVAL_SUMMARY_MAX_CHARS", 8000),
            rubric_enabled=self.getenv_bool("EVAL_RUBRIC_ENABLED", False),
            judge_temperature=self.getenv_float("EVAL_JUDGE_TEMPERATURE", 0.2),
            judge_max_tokens=self.getenv_int("EVAL_JUDGE_MAX_TOKENS", 800),
            rubric_profile=self.getenv("EVAL_RUBRIC_PROFILE", "default"),
            judge_system_prompt=self.getenv("EVAL_JUDGE_SYSTEM_PROMPT"),
            judge_user_template=self.getenv("EVAL_JUDGE_USER_TEMPLATE"),
            skip_if_insufficient_evidence=self.getenv_bool(
                "EVAL_SKIP_IF_INSUFFICIENT_EVIDENCE", True
            ),
            rationale_persist_mode=self.getenv(
                "EVAL_RATIONALE_PERSIST_MODE", "metadata"
            ),
        )

        # Build swarm configuration
        swarm_config = SwarmConfig(llm=self._get_swarm_llm_config(provider, defaults))

        # Build MCP configuration
        mcp_config = self._get_mcp_config(provider, defaults, overrides)

        # Build output configuration
        output_config = self._get_output_config(provider, defaults, overrides)

        # Resolve host for ollama provider
        host = self.get_ollama_host() if provider == "ollama" else None

        # Build SDK configuration with environment overrides
        sdk_config = SDKConfig(
            enable_hooks=overrides.get("enable_hooks", True),
            enable_streaming=overrides.get("enable_streaming", True),
            conversation_window_size=overrides.get("conversation_window_size", 100),
            enable_telemetry=self.getenv_bool("ENABLE_SDK_TELEMETRY", True),
        )

        config = ServerConfig(
            server_type=provider,
            llm=defaults["llm"],
            embedding=defaults["embedding"],
            memory=memory_config,
            evaluation=evaluation_config,
            swarm=swarm_config,
            mcp=mcp_config,
            output=output_config,
            sdk=sdk_config,
            host=host,
            region=defaults["region"],
        )

        self._config_cache[cache_key] = config
        return config

    def get_llm_config(self, server: str, **overrides) -> LLMConfig:
        """Get LLM configuration for the specified server."""
        server_config = self.get_server_config(server, **overrides)
        return server_config.llm

    def get_embedding_config(self, server: str, **overrides) -> EmbeddingConfig:
        """Get embedding configuration for the specified server."""
        server_config = self.get_server_config(server, **overrides)
        return server_config.embedding

    def get_memory_config(self, server: str, **overrides) -> MemoryConfig:
        """Get memory configuration for the specified server."""
        server_config = self.get_server_config(server, **overrides)
        return server_config.memory

    def get_evaluation_config(self, server: str, **overrides) -> EvaluationConfig:
        """Get evaluation configuration for the specified server."""
        server_config = self.get_server_config(server, **overrides)
        return server_config.evaluation

    def get_swarm_config(self, server: str, **overrides) -> SwarmConfig:
        """Get swarm configuration for the specified server."""
        server_config = self.get_server_config(server, **overrides)
        return server_config.swarm

    def get_mcp_config(self, server: str, **overrides) -> MCPConfig:
        """Get MCP configuration for the specified server."""
        server_config = self.get_server_config(server, **overrides)
        return server_config.mcp

    def get_output_config(self, server: str, **overrides) -> OutputConfig:
        """Get output configuration for the specified server."""
        server_config = self.get_server_config(server, **overrides)
        return server_config.output

    def get_sdk_config(self, server: str, **overrides) -> SDKConfig:
        """Get SDK configuration for the specified server."""
        server_config = self.get_server_config(server, **overrides)
        return server_config.sdk

    # ---------------------------------------------------------------------
    # Swarm helpers (used by specialist sub-agents)
    # ---------------------------------------------------------------------
    def get_swarm_model_id(self, server: Optional[str] = None, **overrides) -> str:
        """Return the configured swarm model_id for the given provider.

        Args:
            server: Provider key (e.g., "bedrock", "ollama", "litellm"). If omitted,
                    will use CYBER_AGENT_PROVIDER (default "bedrock").
            **overrides: Optional overrides forwarded to get_server_config

        Returns:
            The model_id string for the swarm LLM. Falls back to primary llm.model_id
            if swarm_llm is unavailable for the provider.
        """
        try:
            provider = (
                server or self.getenv("CYBER_AGENT_PROVIDER", "bedrock")
            ).lower()
            server_config = self.get_server_config(provider, **overrides)
            # Prefer explicit swarm config when available
            if (
                server_config
                and server_config.swarm
                and server_config.swarm.llm
                and server_config.swarm.llm.model_id
            ):
                return server_config.swarm.llm.model_id
            # Fallback to main llm
            if server_config and server_config.llm and server_config.llm.model_id:
                return server_config.llm.model_id
        except Exception:
            pass
        # Final fallback to safe default aligned with Bedrock memory/evaluation defaults
        return "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

    def get_unified_output_path(
        self,
        server: str,
        target_name: str,
        operation_id: str,
        subdir: str = "",
        **overrides,
    ) -> str:
        """Get unified output path using configuration system.

        Args:
            server: Server type for configuration
            target_name: Target name for organization
            operation_id: Operation ID for uniqueness
            subdir: Optional subdirectory within operation
            **overrides: Configuration overrides

        Returns:
            Full unified output path
        """
        output_config = self.get_output_config(server, **overrides)
        sanitized_target = sanitize_target_name(target_name)

        return get_output_path(
            target_name=sanitized_target,
            operation_id=operation_id,
            subdir=subdir,
            base_dir=output_config.base_dir,
        )

    def ensure_operation_output_dirs(
        self,
        server: str,
        target_name: str,
        operation_id: str,
        module: str = "general",
        **overrides,
    ) -> Dict[str, str]:
        """Ensure operation output directories exist and return absolute paths.

        Creates operation-specific directories using configured base_dir:
        - root: outputs/<target>/<operation_id>/
        - artifacts: outputs/<target>/<operation_id>/artifacts/
        - tools: outputs/<target>/<operation_id>/tools/ (for editor+load_tool meta-tooling)

        Safe to call multiple times. Also copies master execution_prompt.txt for optimization.

        Returns:
            Dict[str, str]: Absolute paths to {'root', 'artifacts', 'tools'}
        """
        # Build operation-specific paths from config
        root = self.get_unified_output_path(
            server, target_name, operation_id, "", **overrides
        )
        artifacts = self.get_unified_output_path(
            server, target_name, operation_id, "artifacts", **overrides
        )
        tools = self.get_unified_output_path(
            server, target_name, operation_id, "tools", **overrides
        )
        try:
            os.makedirs(root, exist_ok=True)
            os.makedirs(artifacts, exist_ok=True)
            os.makedirs(tools, exist_ok=True)

            # Copy master execution prompt to operation folder for optimization
            self._copy_execution_prompt(root, module)

        except Exception as e:
            logger.debug("ensure_operation_output_dirs: could not create dirs: %s", e)
        return {"root": root, "artifacts": artifacts, "tools": tools}

    def _copy_execution_prompt(self, operation_root: str, module: str) -> None:
        """Copy master execution prompt to operation folder if not already present.

        Args:
            operation_root: Root directory of the operation
            module: Module name (e.g., 'general', 'ctf')
        """
        import shutil
        from pathlib import Path

        optimized_path = Path(operation_root) / "execution_prompt_optimized.txt"

        # If optimized prompt already exists and has meaningful content, keep it
        if optimized_path.exists():
            file_size = optimized_path.stat().st_size
            if file_size > 100:  # Anything over 100 bytes is likely real content
                logger.debug(
                    "Execution prompt already exists at %s (size: %d bytes)",
                    optimized_path,
                    file_size,
                )
                return

        # Use the existing ModulePromptLoader to get correct paths
        from modules.prompts import get_module_loader

        module_loader = get_module_loader()

        # Try to find the execution prompt file using the loader's plugins directory
        master_path = None
        candidate = module_loader.plugins_dir / module / "execution_prompt.md"
        if candidate.exists() and candidate.is_file():
            master_path = candidate

        # If module-specific prompt not found and not already trying general, fall back
        if master_path is None and module != "general":
            logger.warning(
                "Module %s execution prompt not found, falling back to general", module
            )
            candidate = module_loader.plugins_dir / "general" / "execution_prompt.md"
            if candidate.exists() and candidate.is_file():
                master_path = candidate

        if master_path is None or not master_path.exists():
            logger.error("No execution prompt found for module %s", module)
            # Create a minimal prompt instead of failing silently
            optimized_path.write_text(
                f"# {module.upper()} Module Execution Prompt\n# No master prompt found - using minimal template\n"
            )
            return

        # Check if master file has meaningful content
        master_size = master_path.stat().st_size
        if master_size < 100:  # Less than 100 bytes is likely a placeholder
            logger.error(
                "Master execution prompt at %s appears to be empty or placeholder (size: %d bytes)",
                master_path,
                master_size,
            )
            # Create a minimal template instead
            optimized_path.write_text(
                f"# {module.upper()} Module Execution Prompt\n"
                f"# Master prompt appears empty - using minimal template\n"
            )
            return

        try:
            # Use shutil.copy() instead of copy2() to avoid preserving timestamps
            # This ensures file modification time reflects when it was actually copied
            shutil.copy(master_path, optimized_path)
            logger.info(
                "Copied master execution prompt from %s to %s",
                master_path,
                optimized_path,
            )
        except Exception as e:
            logger.error("Failed to copy execution prompt: %s", e)

    def get_unified_memory_path(
        self, server: str, target_name: str, **overrides
    ) -> str:
        """Get unified memory path for target.

        Args:
            server: Server type for configuration
            target_name: Target name for organization
            **overrides: Configuration overrides

        Returns:
            Memory path for the target
        """
        output_config = self.get_output_config(server, **overrides)
        sanitized_target = sanitize_target_name(target_name)

        return os.path.join(output_config.base_dir, sanitized_target, "memory")

    def get_mem0_service_config(self, server: str, **overrides) -> Dict[str, Any]:
        """Get complete Mem0 service configuration."""
        server_config = self.get_server_config(server, **overrides)
        memory_config = server_config.memory

        # Build embedder config based on server type
        if server == "ollama":
            embedder_config = {
                "provider": "ollama",
                "config": {
                    "model": memory_config.embedder.model_id,
                    "ollama_base_url": self.get_ollama_host(),
                },
            }
        elif server == "litellm":
            prefix, model_name = self._split_litellm_model_id(
                memory_config.embedder.model_id
            )
            mem0_provider = MEM0_PROVIDER_MAP.get(prefix, "huggingface")
            embedder_config = {
                "provider": mem0_provider,
                "config": {
                    "model": memory_config.embedder.model_id,
                    "embedding_dims": memory_config.embedder.dimensions,
                },
            }
            if mem0_provider == "aws_bedrock":
                embedder_config["config"]["aws_region"] = (
                    memory_config.embedder.aws_region
                )
            elif mem0_provider == "azure_openai":
                embedder_config["config"]["model"] = model_name
                embedder_config["config"]["azure_kwargs"] = {
                    "api_key": self.getenv("AZURE_API_KEY"),
                    "azure_deployment": model_name,
                    "azure_endpoint": self.getenv("AZURE_API_BASE"),
                    "api_version": self.getenv("AZURE_API_VERSION"),
                }
        else:  # bedrock
            embedder_config = {
                "provider": "aws_bedrock",
                "config": {
                    "model": memory_config.embedder.model_id,
                    "aws_region": memory_config.embedder.aws_region,
                },
            }

        # Build LLM config based on server type
        if server == "ollama":
            llm_config = {
                "provider": "ollama",
                "config": {
                    "model": memory_config.llm.model_id,
                    "temperature": memory_config.llm.temperature,
                    "max_tokens": memory_config.llm.max_tokens,
                    "ollama_base_url": self.get_ollama_host(),
                },
            }
        elif server == "litellm":
            # Map LiteLLM model prefix to a Mem0-supported provider (e.g., azure_openai, openai, aws_bedrock)
            prefix, model_name = self._split_litellm_model_id(
                memory_config.llm.model_id
            )
            mem0_llm_provider = MEM0_PROVIDER_MAP.get(prefix, "huggingface")
            llm_config = {
                "provider": mem0_llm_provider,
                "config": {
                    "model": memory_config.llm.model_id,
                    "temperature": memory_config.llm.temperature,
                    "max_tokens": memory_config.llm.max_tokens,
                },
            }
            if mem0_llm_provider == "azure_openai":
                llm_config["config"]["model"] = model_name
                llm_config["config"]["azure_kwargs"] = {
                    "api_key": self.getenv("AZURE_API_KEY"),
                    "azure_deployment": model_name,
                    "azure_endpoint": self.getenv("AZURE_API_BASE"),
                    "api_version": self.getenv("AZURE_API_VERSION"),
                }
        else:  # bedrock
            llm_config = {
                "provider": "aws_bedrock",
                "config": {
                    "model": memory_config.llm.model_id,
                    "temperature": memory_config.llm.temperature,
                    "max_tokens": memory_config.llm.max_tokens,
                },
            }

        # Build vector store config
        opensearch_host = self.getenv("OPENSEARCH_HOST")
        if opensearch_host:
            vector_store_config = {
                "provider": "opensearch",
                "config": memory_config.vector_store.get_config_for_provider(
                    "opensearch", host=opensearch_host
                ),
            }
        else:
            vector_store_config = {
                "provider": "faiss",
                "config": memory_config.vector_store.get_config_for_provider("faiss"),
            }

        vector_store_config["config"]["embedding_model_dims"] = (
            memory_config.embedder.dimensions
        )

        return {
            "embedder": embedder_config,
            "llm": llm_config,
            "vector_store": vector_store_config,
        }

    def validate_requirements(self, provider: str) -> None:
        """Validate that all requirements are met for the specified provider."""
        logger.debug("Validating requirements for provider: %s", provider)
        if provider == "ollama":
            self._validate_ollama_requirements()
        elif provider == "bedrock":
            self._validate_aws_requirements()
        elif provider == "litellm":
            self._validate_litellm_requirements()
        else:
            raise ValueError(f"Unsupported provider type: {provider}")

    def get_context_window_fallbacks(
        self, provider: str
    ) -> Optional[List[Dict[str, List[str]]]]:
        """Optional model fallback mappings for context window resolution.

        Currently returns None by default. Kept as an extension point if a future
        config source wants to provide structured context window fallbacks.
        """
        return None

    def get_ollama_host(self) -> str:
        """Determine appropriate Ollama host based on environment."""
        env_host = self.getenv("OLLAMA_HOST")
        if env_host:
            return env_host

        # Check if running in Docker
        if os.path.exists("/app"):
            candidates = ["http://localhost:11434", "http://host.docker.internal:11434"]
            for host in candidates:
                try:
                    response = requests.get(f"{host}/api/version", timeout=2)
                    if response.status_code == 200:
                        return host
                except (requests.exceptions.RequestException, ConnectionError):
                    pass
            # Fallback to host.docker.internal if no connection works
            return "http://host.docker.internal:11434"
        # Native execution - use localhost
        return "http://localhost:11434"

    def set_environment_variables(self, server: str) -> None:
        """Set environment variables for backward compatibility."""
        server_config = self.get_server_config(server)

        if server == "ollama":
            os.environ["MEM0_LLM_PROVIDER"] = "ollama"
            os.environ["MEM0_LLM_MODEL"] = server_config.memory.llm.model_id
            os.environ["MEM0_EMBEDDING_MODEL"] = server_config.memory.embedder.model_id
        else:
            os.environ["MEM0_LLM_MODEL"] = server_config.memory.llm.model_id
            os.environ["MEM0_EMBEDDING_MODEL"] = server_config.memory.embedder.model_id

    def _apply_environment_overrides(
        self, _server: str, defaults: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply environment variable overrides to default configuration."""
        llm_cfg = (
            defaults.get("llm") if isinstance(defaults.get("llm"), LLMConfig) else None
        )

        llm_model = self.getenv("CYBER_AGENT_LLM_MODEL")
        if llm_model and llm_cfg is not None:
            if llm_model != llm_cfg.model_id:
                logger.info(
                    "ENV override: CYBER_AGENT_LLM_MODEL=%s replaces config model=%s",
                    llm_model,
                    llm_cfg.model_id,
                )
            llm_cfg = LLMConfig(
                provider=llm_cfg.provider,
                model_id=llm_model,
                temperature=llm_cfg.temperature,
                max_tokens=llm_cfg.max_tokens,
                top_p=llm_cfg.top_p,
            )
            defaults["llm"] = llm_cfg

        temperature_override = self.getenv("CYBER_AGENT_TEMPERATURE")
        if temperature_override and llm_cfg is not None:
            temperature = self.getenv_float(
                "CYBER_AGENT_TEMPERATURE", llm_cfg.temperature
            )
            if temperature != llm_cfg.temperature:
                llm_cfg.temperature = temperature
                llm_cfg.parameters["temperature"] = temperature

        top_p_override = self.getenv("CYBER_AGENT_TOP_P")
        if top_p_override and llm_cfg is not None:
            top_p = self.getenv_float(
                "CYBER_AGENT_TOP_P", llm_cfg.top_p if llm_cfg.top_p is not None else 0.0
            )
            if top_p != llm_cfg.top_p:
                llm_cfg.top_p = top_p
                llm_cfg.parameters["top_p"] = top_p

        max_tokens_override = self.getenv("CYBER_AGENT_MAX_TOKENS") or self.getenv(
            "MAX_TOKENS"
        )
        if max_tokens_override and llm_cfg is not None:
            max_tokens = self.getenv_int(
                "CYBER_AGENT_MAX_TOKENS",
                self.getenv_int("MAX_TOKENS", llm_cfg.max_tokens),
            )
            if max_tokens != llm_cfg.max_tokens:
                llm_cfg.max_tokens = max_tokens
                llm_cfg.parameters["max_tokens"] = max_tokens

        embedding_model = self.getenv("CYBER_AGENT_EMBEDDING_MODEL")
        if embedding_model and isinstance(defaults.get("embedding"), EmbeddingConfig):
            embedding_cfg = defaults["embedding"]
            if embedding_model != embedding_cfg.model_id:
                logger.info(
                    "ENV override: CYBER_AGENT_EMBEDDING_MODEL=%s replaces config=%s",
                    embedding_model,
                    embedding_cfg.model_id,
                )
            embedding_cfg.model_id = embedding_model
            embedding_cfg.parameters["dimensions"] = embedding_cfg.dimensions

        eval_model = self.getenv("CYBER_AGENT_EVALUATION_MODEL") or self.getenv(
            "RAGAS_EVALUATOR_MODEL"
        )
        if eval_model and isinstance(defaults.get("evaluation_llm"), LLMConfig):
            evaluation_cfg = defaults["evaluation_llm"]
            evaluation_cfg.model_id = eval_model

        swarm_model = self.getenv("CYBER_AGENT_SWARM_MODEL")
        if swarm_model and isinstance(defaults.get("swarm_llm"), LLMConfig):
            swarm_cfg = defaults["swarm_llm"]
            swarm_cfg.model_id = swarm_model

        memory_llm_model = self.getenv("MEM0_LLM_MODEL")
        if memory_llm_model and isinstance(defaults.get("memory_llm"), MemoryLLMConfig):
            memory_llm_cfg = defaults["memory_llm"]
            memory_llm_cfg.model_id = memory_llm_model

        # Apply AWS_REGION to region and aws_region fields (but not for ollama)
        if _server not in ("ollama",):
            aws_region = self.getenv("AWS_REGION", "us-east-1")
            if defaults.get("region"):
                defaults["region"] = aws_region
            if isinstance(defaults.get("memory_llm"), MemoryLLMConfig):
                defaults["memory_llm"].aws_region = aws_region

        return defaults

    def _split_litellm_model_id(self, model_id: str) -> Tuple[str, str]:
        """Split LiteLLM model id into provider prefix and base id."""
        if not model_id:
            return "", ""
        if "/" in model_id:
            prefix, base = model_id.split("/", 1)
            if prefix.lower() == "models":
                prefix = "gemini"
            return prefix.lower(), base
        return "", model_id

    def _align_litellm_defaults(self, defaults: Dict[str, Any]) -> None:
        """Ensure LiteLLM configuration components stay aligned with the selected model.

        Uses LiteLLM's get_max_tokens() API to dynamically cap max_tokens based on
        model limits from model_prices_and_context_window.json. This ensures we stay
        within model limits without hardcoding values that may change.
        """
        llm_cfg = defaults.get("llm")
        if not isinstance(llm_cfg, LLMConfig):
            return

        provider_prefix, base_model = self._split_litellm_model_id(llm_cfg.model_id)
        if not base_model:
            return

        # Use LiteLLM's model database to get max_output_tokens for this model
        # This handles all providers and updates automatically with LiteLLM
        try:
            import litellm

            # Query LiteLLM's model database for max output tokens
            model_max_tokens = litellm.get_max_tokens(base_model)

            if model_max_tokens and llm_cfg.max_tokens > model_max_tokens:
                logger.info(
                    "Capping max_tokens from %d to %d for model '%s' (model limit from LiteLLM database)",
                    llm_cfg.max_tokens,
                    model_max_tokens,
                    llm_cfg.model_id,
                )
                llm_cfg.max_tokens = model_max_tokens
                llm_cfg.parameters["max_tokens"] = model_max_tokens
            elif model_max_tokens:
                logger.debug(
                    "Model '%s' max_tokens=%d is within limit (model max: %d)",
                    llm_cfg.model_id,
                    llm_cfg.max_tokens,
                    model_max_tokens,
                )
            else:
                logger.debug(
                    "Model '%s' not in LiteLLM database, using configured max_tokens=%d",
                    llm_cfg.model_id,
                    llm_cfg.max_tokens,
                )
        except Exception as e:
            # If LiteLLM doesn't know about this model, log and continue
            # The API call will fail with a clear error if max_tokens is invalid
            logger.debug(
                "Could not query max_tokens for model '%s': %s (will use configured value)",
                llm_cfg.model_id,
                str(e),
            )

        embed_override = self.getenv("CYBER_AGENT_EMBEDDING_MODEL")

        for key in ("memory_llm", "evaluation_llm", "swarm_llm"):
            cfg = defaults.get(key)
            if isinstance(cfg, MemoryLLMConfig):
                cfg.model_id = llm_cfg.model_id
                cfg.provider = ModelProvider.LITELLM
                cfg.parameters["temperature"] = cfg.temperature
                cfg.parameters["max_tokens"] = cfg.max_tokens
            elif isinstance(cfg, LLMConfig):
                cfg.model_id = llm_cfg.model_id
                cfg.provider = ModelProvider.LITELLM
                # Align swarm output cap to primary llm to avoid premature max_tokens stops
                if key == "swarm_llm":
                    cfg.max_tokens = llm_cfg.max_tokens
                cfg.parameters["temperature"] = cfg.temperature
                cfg.parameters["max_tokens"] = cfg.max_tokens

        embed_cfg = defaults.get("embedding")
        if isinstance(embed_cfg, EmbeddingConfig):
            if embed_override:
                embed_model = embed_override
                dims = EMBEDDING_DIMENSIONS.get(embed_model)
                if dims is None:
                    logger.warning(
                        "Unknown embedding model '%s', dimensions not in lookup table. "
                        "Attempting to infer from model name or defaulting to 1536.",
                        embed_model,
                    )
                    if "3-large" in embed_model:
                        dims = 3072
                    elif "ada-002" in embed_model or "3-small" in embed_model:
                        dims = 1536
                    elif "text-embedding-004" in embed_model:
                        dims = 768
                    elif "MiniLM" in embed_model:
                        dims = 384
                    elif "titan" in embed_model and "v2" in embed_model:
                        dims = 1024
                    else:
                        dims = 1536
                        logger.warning(
                            "Could not infer dimensions for '%s', defaulting to 1536. "
                            "If this is incorrect, the FAISS index will fail to load.",
                            embed_model,
                        )
            else:
                embed_model, dims = LITELLM_EMBEDDING_DEFAULTS.get(
                    provider_prefix, DEFAULT_LITELLM_EMBEDDING
                )

            if embed_model == "models/text-embedding-004":
                if importlib.util.find_spec("google.genai") is None:
                    logger.error(
                        "LiteLLM provider '%s' requires optional dependency 'google-genai'. "
                        "Install it or set CYBER_AGENT_EMBEDDING_MODEL to a supported embedding.",
                        provider_prefix,
                    )
                    raise ImportError("google-genai is required for Gemini embeddings")
            elif embed_model == "multi-qa-MiniLM-L6-cos-v1":
                if importlib.util.find_spec("sentence_transformers") is None:
                    logger.error(
                        "LiteLLM provider '%s' requires optional dependency 'sentence-transformers'. "
                        "Install it or set CYBER_AGENT_EMBEDDING_MODEL to a supported embedding.",
                        provider_prefix,
                    )
                    raise ImportError(
                        "sentence-transformers is required for Hugging Face embeddings"
                    )

            embed_cfg.model_id = embed_model
            embed_cfg.dimensions = dims
            embed_cfg.provider = ModelProvider.LITELLM
            embed_cfg.parameters["dimensions"] = dims

    def _get_memory_embedder_config(
        self, _server: str, defaults: Dict[str, Any]
    ) -> MemoryEmbeddingConfig:
        """Get memory embedder configuration."""
        embedding_config = defaults["embedding"]
        return MemoryEmbeddingConfig(
            provider=embedding_config.provider,
            model_id=embedding_config.model_id,
            aws_region=defaults.get("region", self.get_default_region()),
            dimensions=embedding_config.dimensions,
        )

    def _get_memory_llm_config(
        self, _server: str, defaults: Dict[str, Any]
    ) -> MemoryLLMConfig:
        """Get memory LLM configuration."""
        return defaults["memory_llm"]

    def _get_evaluation_llm_config(
        self, _server: str, defaults: Dict[str, Any]
    ) -> ModelConfig:
        """Get evaluation LLM configuration."""
        return defaults["evaluation_llm"]

    def _get_evaluation_embedding_config(
        self, _server: str, defaults: Dict[str, Any]
    ) -> ModelConfig:
        """Get evaluation embedding configuration."""
        return defaults["embedding"]

    def _get_swarm_llm_config(
        self, _server: str, defaults: Dict[str, Any]
    ) -> ModelConfig:
        """Get swarm LLM configuration."""
        return defaults["swarm_llm"]

    def _get_mcp_config(self, _server: str, defaults: Dict[str, Any], overrides: Dict[str, Any]) -> MCPConfig:
        enabled = overrides.get("mcp_enabled") or os.getenv("CYBER_MCP_ENABLED", "true").lower() == "true"

        connections = []

        if enabled:
            conns_json = overrides.get("mcp_conns") or os.getenv("CYBER_MCP_CONNECTIONS")
            if conns_json and conns_json.strip():
                try:
                    conns = json.loads(conns_json)
                    if not isinstance(conns, list):
                        raise ValueError("CYBER_MCP_CONNECTIONS is not an array")
                except json.JSONDecodeError:
                    raise ValueError("CYBER_MCP_CONNECTIONS is not valid JSON")
                for conn in conns:
                    mcp_id = conn.get("id")
                    if mcp_id is None or len(mcp_id) == 0:
                        raise ValueError("CYBER_MCP_CONNECTIONS requires an id property")
                    if mcp_id in map(lambda x: x.id, connections):
                        raise ValueError("CYBER_MCP_CONNECTIONS id property must be unique")

                    mcp_transport = conn.get("transport")
                    if mcp_transport not in ["stdio", "sse", "streamable-http"]:
                        raise ValueError(f"CYBER_MCP_CONNECTIONS {mcp_id} does not have a valid transport: {mcp_transport}")

                    mcp_command = conn.get("command") or None
                    if mcp_transport == "stdio":
                        if not mcp_command:
                            raise ValueError("CYBER_MCP_CONNECTIONS stdio transport requires the command property")
                        if isinstance(mcp_command, str):
                            mcp_command = [str]
                        if not isinstance(mcp_command, list):
                            raise ValueError("CYBER_MCP_CONNECTIONS command property is expected to be a list")
                    else:
                        if mcp_command is not None:
                            raise ValueError("CYBER_MCP_CONNECTIONS network transports do not use the command property")

                    mcp_server_url = conn.get("server_url") or None
                    if mcp_transport == "stdio":
                        if mcp_server_url:
                            raise ValueError("CYBER_MCP_CONNECTIONS stdio transport does not use the server_url property")
                    else:
                        if mcp_server_url is None:
                            raise ValueError("CYBER_MCP_CONNECTIONS network transports require the server_url property")

                    mcp_headers = conn.get("headers")
                    if mcp_headers is not None and not isinstance(mcp_headers, dict):
                        raise ValueError("CYBER_MCP_CONNECTIONS headers property is expected to be a dictionary")

                    mcp_plugins = conn.get("plugins")
                    if mcp_plugins is not None and not isinstance(mcp_plugins, list):
                        raise ValueError("CYBER_MCP_CONNECTIONS plugins property is expected to be a list")
                    if not mcp_plugins or "*" in mcp_plugins:
                        mcp_plugins = ["*"]

                    mcp_timeout = conn.get("timeoutSeconds")
                    if mcp_timeout is not None and not isinstance(mcp_timeout, int):
                        raise ValueError("CYBER_MCP_CONNECTIONS timeoutSeconds is expected to be an integer")
                    if mcp_timeout is not None and mcp_timeout < 0:
                        raise ValueError("CYBER_MCP_CONNECTIONS timeoutSeconds is expected to be a positive integer")

                    mcp_allowed_tools = conn.get("allowedTools")
                    if mcp_allowed_tools is not None and not isinstance(mcp_allowed_tools, list):
                        raise ValueError("CYBER_MCP_CONNECTIONS allowedTools property is expected to be a list")
                    if not mcp_allowed_tools or "*" in mcp_allowed_tools:
                        mcp_allowed_tools = ["*"]

                    mcp_conn = MCPConnection(
                        id=mcp_id,
                        transport=mcp_transport,
                        command=mcp_command,
                        server_url=mcp_server_url,
                        headers=mcp_headers,
                        plugins=mcp_plugins,
                        timeoutSeconds=mcp_timeout,
                        allowed_tools=mcp_allowed_tools,
                    )
                    connections.append(mcp_conn)

        return MCPConfig(enabled=enabled, connections=connections)

    def _get_output_config(
            self, _server: str, _defaults: Dict[str, Any], overrides: Dict[str, Any]
    ) -> OutputConfig:
        """Get output configuration with environment variable and override support."""
        # Get base output directory
        base_dir = (
            overrides.get("output_dir")
            or self.getenv("CYBER_AGENT_OUTPUT_DIR")
            or get_default_base_dir()
        )

        # Get target name
        target_name = overrides.get("target_name")

        # Get operation ID
        operation_id = overrides.get("operation_id")

        # Get feature flags - unified output is now enabled by default
        enable_unified_output = overrides.get(
            "enable_unified_output", True
        ) or self.getenv_bool("CYBER_AGENT_ENABLE_UNIFIED_OUTPUT", True)

        return OutputConfig(
            base_dir=base_dir,
            target_name=target_name,
            enable_unified_output=enable_unified_output,
            operation_id=operation_id,
        )

    def _validate_ollama_requirements(self) -> None:
        """Validate Ollama requirements."""
        ollama_host = self.get_ollama_host()

        # Check if Ollama is running
        try:
            response = requests.get(f"{ollama_host}/api/version", timeout=5)
            if response.status_code != 200:
                raise ConnectionError("Ollama server not responding")
        except Exception as e:
            raise ConnectionError(
                f"Ollama server not accessible at {ollama_host}. "
                "Please ensure Ollama is installed and running."
            ) from e

        # Check if at least one model is available
        try:
            client = ollama.Client(host=ollama_host)
            models_response = client.list()
            available_models = [
                m.get("model", m.get("name", "")) for m in models_response["models"]
            ]

            if not available_models:
                raise ValueError(
                    "No Ollama models found. Please pull at least one model, e.g.: ollama pull qwen3:1.7b"
                )

            # Log available models for debugging
            logger.info(f"Available Ollama models: {available_models}")

            # Enforce presence of default models for predictable local dev unless user overrides
            server_config = self.get_server_config("ollama")
            required_models = [
                server_config.llm.model_id,
                server_config.embedding.model_id,
            ]

            # Require at least one required model to be available
            has_required = any(
                any(req in model for model in available_models)
                for req in required_models
            )

            if not has_required:
                raise ValueError(
                    "Required models not found. Ensure default models are pulled or override with --model."
                )

        except Exception as e:
            if (
                "No Ollama models found" in str(e)
                or "Required models not found" in str(e)
                or "No models available" in str(e)
            ):
                raise e
            raise ConnectionError(f"Could not verify Ollama models: {e}") from e

    def _validate_bedrock_model_access(self) -> None:
        """Validate AWS Bedrock model access and availability.

        Performs basic validation of AWS region configuration.
        Model access validation is handled by the strands-agents framework.

        Raises:
            EnvironmentError: If AWS region is not configured
        """
        region = self.get_default_region()
        if not region:
            raise EnvironmentError(
                "AWS region not configured. Set AWS_REGION environment variable or configure default region."
            )

        # Verify boto3 client can be created with current credentials
        try:
            boto3.client("bedrock-runtime", region_name=region)
        except Exception as e:
            logger.debug("Could not create bedrock-runtime client: %s", e)
            # Model-specific errors will be handled by strands-agents during actual usage

    def _validate_aws_requirements(self) -> None:
        """Validate AWS requirements including Bedrock model access.

        Supports either standard AWS credentials (ACCESS_KEY/SECRET or PROFILE)
        or Bedrock bearer token via AWS_BEARER_TOKEN_BEDROCK without mutating
        credential environment variables.
        """
        bearer_token = self.getenv("AWS_BEARER_TOKEN_BEDROCK")
        access_key = self.getenv("AWS_ACCESS_KEY_ID")
        profile = self.getenv("AWS_PROFILE")

        # Verify AWS credentials are configured (standard creds OR bearer token)
        if not (access_key or profile or bearer_token):
            raise EnvironmentError(
                "AWS credentials not configured for remote mode. "
                "Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, configure AWS_PROFILE, "
                "or set AWS_BEARER_TOKEN_BEDROCK for API key authentication"
            )

        # Prefer standard AWS credentials when present; use bearer token only if no standard credentials
        if bearer_token and not (access_key or profile):
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = bearer_token
        else:
            # Ensure bearer token does not override SigV4 when standard creds are set
            os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)

        # Optionally validate region and client construction; ignore client errors here.
        self._validate_bedrock_model_access()

    def _validate_litellm_requirements(self) -> None:
        """Validate LiteLLM requirements based on model provider prefix.

        LiteLLM handles most validation internally:
        - max_tokens: Auto-capped to model limits via get_modified_max_tokens()
        - temperature: Validated by provider (e.g., reasoning models require 1.0)
        - Model limits: Maintained in model_prices_and_context_window.json

        This validation only checks that required API credentials are configured.
        """
        # Get default LiteLLM model ID
        litellm_config = self._default_configs.get("litellm", {})
        model_id = self.getenv("CYBER_AGENT_LLM_MODEL")
        if not model_id:
            llm_cfg = litellm_config.get("llm")
            model_id = llm_cfg.model_id if hasattr(llm_cfg, "model_id") else ""

        logger.info("Validating LiteLLM configuration for model: %s", model_id)

        # Check provider-specific requirements based on model prefix
        if model_id.startswith("bedrock/"):
            # LiteLLM does NOT support AWS bearer tokens - only standard credentials
            if not (self.getenv("AWS_ACCESS_KEY_ID") or self.getenv("AWS_PROFILE")):
                raise EnvironmentError(
                    "AWS credentials not configured for LiteLLM Bedrock models.\n"
                    "Required: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY OR AWS_PROFILE\n"
                    "Note: LiteLLM does not support AWS_BEARER_TOKEN_BEDROCK"
                )

        elif model_id.startswith("openai/"):
            if not self.getenv("OPENAI_API_KEY"):
                raise EnvironmentError(
                    "OPENAI_API_KEY not configured for LiteLLM OpenAI models. "
                    "Set OPENAI_API_KEY environment variable."
                )
        elif model_id.startswith("anthropic/"):
            if not self.getenv("ANTHROPIC_API_KEY"):
                raise EnvironmentError(
                    "ANTHROPIC_API_KEY not configured for LiteLLM Anthropic models. "
                    "Set ANTHROPIC_API_KEY environment variable."
                )
        elif model_id.startswith("cohere/"):
            if not self.getenv("COHERE_API_KEY"):
                raise EnvironmentError(
                    "COHERE_API_KEY not configured for LiteLLM Cohere models. "
                    "Set COHERE_API_KEY environment variable."
                )
        elif model_id.startswith("azure/"):
            if not self.getenv("AZURE_API_KEY"):
                raise EnvironmentError(
                    "AZURE_API_KEY not configured for LiteLLM Azure models. "
                    "Set AZURE_API_KEY, AZURE_API_BASE, and AZURE_API_VERSION environment variables."
                )
        elif model_id.startswith("gemini/"):
            if not self.getenv("GEMINI_API_KEY"):
                raise EnvironmentError(
                    "GEMINI_API_KEY not configured for LiteLLM Gemini models. "
                    "Set GEMINI_API_KEY environment variable."
                )
        elif model_id.startswith("sagemaker/"):
            has_std_creds = self.getenv("AWS_ACCESS_KEY_ID") and self.getenv(
                "AWS_SECRET_ACCESS_KEY"
            )
            if not (has_std_creds or self.getenv("AWS_PROFILE")):
                raise EnvironmentError(
                    "AWS credentials not configured for LiteLLM SageMaker models.\n"
                    "Required: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY OR AWS_PROFILE"
                )
            if not (self.getenv("AWS_REGION") or self.getenv("AWS_REGION_NAME")):
                raise EnvironmentError(
                    "AWS region not configured for LiteLLM SageMaker models.\n"
                    "Set AWS_REGION or AWS_REGION_NAME environment variable."
                )
        else:
            # No explicit prefix - LiteLLM will auto-detect based on available credentials
            logger.debug(
                "Model '%s' has no explicit prefix. LiteLLM will auto-detect provider based on credentials.",
                model_id,
            )


# Global configuration manager instance
CONFIG_MANAGER_INSTANCE = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global CONFIG_MANAGER_INSTANCE
    if CONFIG_MANAGER_INSTANCE is None:
        CONFIG_MANAGER_INSTANCE = ConfigManager()
    return CONFIG_MANAGER_INSTANCE


def get_model_config(server: str, **overrides) -> ServerConfig:
    """Get model configuration for the specified server.

    Args:
        server: Server type ("local" or "remote")
        **overrides: Configuration overrides

    Returns:
        ServerConfig: Complete server configuration
    """
    return get_config_manager().get_server_config(server, **overrides)


# Backward compatibility functions
def get_default_model_configs(server: str) -> Dict[str, Any]:
    """Get default model configurations (backward compatibility)."""
    config = get_model_config(server)
    return {
        "llm_model": config.llm.model_id,
        "embedding_model": config.embedding.model_id,
        "embedding_dims": config.embedding.dimensions,
    }


def get_ollama_host() -> str:
    """Get Ollama host (backward compatibility)."""
    return get_config_manager().get_ollama_host()
