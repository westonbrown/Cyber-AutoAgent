#!/usr/bin/env python3
"""
Centralized model configuration management for Cyber-AutoAgent.

This module provides a unified configuration system for all model-related
settings, including LLM models, embedding models, and provider configurations.
It supports multiple providers (AWS Bedrock, Ollama) and allows for easy
environment variable overrides.

Key Components:
- ModelProvider: Enum for supported providers
- Configuration dataclasses: Type-safe configuration objects
- ConfigManager: Central configuration management
- Environment variable support with fallbacks
- Validation and error handling
"""

import os
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
import requests
import ollama
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from .handlers.utils import get_output_path, sanitize_target_name

logger = logging.getLogger(__name__)


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
    top_p: float = 0.95

    def __post_init__(self):
        super().__post_init__()
        # Add LLM-specific parameters to the parameters dict
        self.parameters.update(
            {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
            }
        )


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
    aws_region: str = field(
        default_factory=lambda: os.getenv("AWS_REGION", "us-east-1")
    )

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

    aws_region: str = field(
        default_factory=lambda: os.getenv("AWS_REGION", "us-east-1")
    )
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
class OutputConfig:
    """Configuration for output directory management."""

    base_dir: str = field(default_factory=get_default_base_dir)
    target_name: Optional[str] = None
    enable_unified_output: bool = True  # Default to enabled for new unified structure
    operation_id: Optional[str] = None  # Current operation ID for path generation


@dataclass
class ServerConfig:
    """Complete server configuration."""

    server_type: str  # "bedrock", "ollama", or "litellm"
    llm: LLMConfig
    embedding: EmbeddingConfig
    memory: MemoryConfig
    evaluation: EvaluationConfig
    swarm: SwarmConfig
    output: OutputConfig = field(default_factory=OutputConfig)
    host: Optional[str] = None
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))


class ConfigManager:
    """Central configuration manager for all model configurations."""

    def __init__(self):
        """Initialize configuration manager."""
        self._config_cache = {}
        self._default_configs = self._initialize_default_configs()

    def get_default_region(self) -> str:
        """Get the default AWS region with environment override support."""
        return os.getenv("AWS_REGION", "us-east-1")

    def get_thinking_models(self) -> List[str]:
        """Get list of models that support thinking capabilities."""
        return [
            "us.anthropic.claude-opus-4-20250514-v1:0",
            "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "us.anthropic.claude-sonnet-4-20250514-v1:0",
        ]

    def is_thinking_model(self, model_id: str) -> bool:
        """Check if a model supports thinking capabilities."""
        return model_id in self.get_thinking_models()

    def get_thinking_model_config(
        self, model_id: str, region_name: str
    ) -> Dict[str, Any]:
        """Get configuration for thinking-enabled models."""
        return {
            "model_id": model_id,
            "region_name": region_name,
            "temperature": 1.0,
            "max_tokens": 4096,
            "additional_request_fields": {
                "anthropic_beta": ["interleaved-thinking-2025-05-14"],
                "thinking": {"type": "enabled", "budget_tokens": 8000},
            },
        }

    def get_standard_model_config(
        self, model_id: str, region_name: str, provider: str
    ) -> Dict[str, Any]:
        """Get configuration for standard (non-thinking) models."""
        provider_config = self.get_server_config(provider)
        llm_config = provider_config.llm

        return {
            "model_id": model_id,
            "region_name": region_name,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
            "top_p": llm_config.top_p,
        }

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
                    max_tokens=4096,
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
                    max_tokens=500,
                ),
                "host": None,  # Will be resolved dynamically
                "region": "ollama",
            },
            "bedrock": {
                "llm": LLMConfig(
                    provider=ModelProvider.AWS_BEDROCK,
                    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                    temperature=0.95,
                    max_tokens=4096,
                    top_p=0.95,
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
                    aws_region=os.getenv("AWS_REGION", "us-east-1"),
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
                    max_tokens=500,
                ),
                "host": None,
                "region": os.getenv("AWS_REGION", "us-east-1"),
            },
            "litellm": {
                "llm": LLMConfig(
                    provider=ModelProvider.LITELLM,
                    model_id="bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0",  # Default to Bedrock via LiteLLM
                    temperature=0.95,
                    max_tokens=4096,
                    top_p=0.95,
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
                    aws_region=os.getenv("AWS_REGION", "us-east-1"),
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
                    max_tokens=500,
                ),
                "host": None,
                "region": os.getenv("AWS_REGION", "us-east-1"),
            },
        }

    def get_server_config(self, provider: str, **overrides) -> ServerConfig:
        """Get complete provider configuration with optional overrides."""
        logger.debug("Getting server config for provider: %s", provider)
        cache_key = f"provider_{provider}_{hash(frozenset(overrides.items()))}"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        if provider not in self._default_configs:
            logger.error("Provider %s not in available configs: %s", provider, list(self._default_configs.keys()))
            raise ValueError(f"Unsupported provider type: {provider}")

        defaults = self._default_configs[provider].copy()

        # Apply environment variable overrides
        defaults = self._apply_environment_overrides(provider, defaults)

        # Apply function parameter overrides
        defaults.update(overrides)

        # Build memory configuration
        memory_config = MemoryConfig(
            embedder=self._get_memory_embedder_config(provider, defaults),
            llm=self._get_memory_llm_config(provider, defaults),
            vector_store=MemoryVectorStoreConfig(),
        )

        # Build evaluation configuration
        evaluation_config = EvaluationConfig(
            llm=self._get_evaluation_llm_config(provider, defaults),
            embedding=self._get_evaluation_embedding_config(provider, defaults),
        )

        # Build swarm configuration
        swarm_config = SwarmConfig(llm=self._get_swarm_llm_config(provider, defaults))

        # Build output configuration
        output_config = self._get_output_config(provider, defaults, overrides)

        # Resolve host for ollama provider
        host = self.get_ollama_host() if provider == "ollama" else None

        config = ServerConfig(
            server_type=provider,
            llm=defaults["llm"],
            embedding=defaults["embedding"],
            memory=memory_config,
            evaluation=evaluation_config,
            swarm=swarm_config,
            output=output_config,
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

    def get_output_config(self, server: str, **overrides) -> OutputConfig:
        """Get output configuration for the specified server."""
        server_config = self.get_server_config(server, **overrides)
        return server_config.output

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
            # For LiteLLM, we need to map to the actual provider that Mem0 supports
            # Extract provider from model ID (e.g., "bedrock/model" -> "aws_bedrock")
            model_id = memory_config.embedder.model_id
            if model_id.startswith("bedrock/"):
                embedder_config = {
                    "provider": "aws_bedrock",
                    "config": {
                        "model": model_id.replace("bedrock/", ""),  # Remove prefix for Mem0
                        "aws_region": memory_config.embedder.aws_region,
                    },
                }
            else:
                # Default to AWS Bedrock for unsupported providers
                embedder_config = {
                    "provider": "aws_bedrock",
                    "config": {
                        "model": "amazon.titan-embed-text-v2:0",
                        "aws_region": memory_config.embedder.aws_region,
                    },
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
            # For LiteLLM, we need to map to the actual provider that Mem0 supports
            model_id = memory_config.llm.model_id
            if model_id.startswith("bedrock/"):
                llm_config = {
                    "provider": "aws_bedrock",
                    "config": {
                        "model": model_id.replace("bedrock/", ""),  # Remove prefix for Mem0
                        "temperature": memory_config.llm.temperature,
                        "max_tokens": memory_config.llm.max_tokens,
                        "aws_region": memory_config.llm.aws_region,
                    },
                }
            else:
                # Default to AWS Bedrock for unsupported providers
                llm_config = {
                    "provider": "aws_bedrock",
                    "config": {
                        "model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                        "temperature": memory_config.llm.temperature,
                        "max_tokens": memory_config.llm.max_tokens,
                        "aws_region": memory_config.llm.aws_region,
                    },
                }
        else:  # bedrock
            llm_config = {
                "provider": "aws_bedrock",
                "config": {
                    "model": memory_config.llm.model_id,
                    "temperature": memory_config.llm.temperature,
                    "max_tokens": memory_config.llm.max_tokens,
                    "aws_region": memory_config.llm.aws_region,
                },
            }

        # Build vector store config
        if os.environ.get("OPENSEARCH_HOST"):
            vector_store_config = {
                "provider": "opensearch",
                "config": memory_config.vector_store.get_config_for_provider(
                    "opensearch", host=os.environ.get("OPENSEARCH_HOST")
                ),
            }
        else:
            vector_store_config = {
                "provider": "faiss",
                "config": memory_config.vector_store.get_config_for_provider("faiss"),
            }

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

    def get_ollama_host(self) -> str:
        """Determine appropriate Ollama host based on environment."""
        env_host = os.getenv("OLLAMA_HOST")
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
        # Main LLM model override
        llm_model = os.getenv("CYBER_AGENT_LLM_MODEL")
        if llm_model:
            defaults["llm"] = LLMConfig(
                provider=defaults["llm"].provider,
                model_id=llm_model,
                temperature=defaults["llm"].temperature,
                max_tokens=defaults["llm"].max_tokens,
            )

        # Embedding model override
        embedding_model = os.getenv("CYBER_AGENT_EMBEDDING_MODEL")
        if embedding_model:
            defaults["embedding"] = EmbeddingConfig(
                provider=defaults["embedding"].provider,
                model_id=embedding_model,
                dimensions=defaults["embedding"].dimensions,
            )

        # Evaluation model override
        eval_model = os.getenv("CYBER_AGENT_EVALUATION_MODEL") or os.getenv(
            "RAGAS_EVALUATOR_MODEL"
        )
        if eval_model:
            defaults["evaluation_llm"] = LLMConfig(
                provider=defaults["evaluation_llm"].provider,
                model_id=eval_model,
                temperature=defaults["evaluation_llm"].temperature,
                max_tokens=defaults["evaluation_llm"].max_tokens,
            )

        # Swarm model override
        swarm_model = os.getenv("CYBER_AGENT_SWARM_MODEL")
        if swarm_model:
            defaults["swarm_llm"] = LLMConfig(
                provider=defaults["swarm_llm"].provider,
                model_id=swarm_model,
                temperature=defaults["swarm_llm"].temperature,
                max_tokens=defaults["swarm_llm"].max_tokens,
            )

        # Memory LLM override
        memory_llm_model = os.getenv("MEM0_LLM_MODEL")
        if memory_llm_model:
            defaults["memory_llm"] = MemoryLLMConfig(
                provider=defaults["memory_llm"].provider,
                model_id=memory_llm_model,
                temperature=defaults["memory_llm"].temperature,
                max_tokens=defaults["memory_llm"].max_tokens,
                aws_region=defaults["memory_llm"].aws_region,
            )

        # Memory embedding override (only if not already overridden)
        mem0_embedding_model = os.getenv("MEM0_EMBEDDING_MODEL")
        if (
            mem0_embedding_model and not embedding_model
        ):  # Only if not already overridden
            defaults["embedding"] = EmbeddingConfig(
                provider=defaults["embedding"].provider,
                model_id=mem0_embedding_model,
                dimensions=defaults["embedding"].dimensions,
            )

        # Region override
        aws_region = os.getenv("AWS_REGION")
        if aws_region:
            defaults["region"] = aws_region

        return defaults

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

    def _get_output_config(
        self, _server: str, _defaults: Dict[str, Any], overrides: Dict[str, Any]
    ) -> OutputConfig:
        """Get output configuration with environment variable and override support."""
        # Get base output directory
        base_dir = (
            overrides.get("output_dir")
            or os.getenv("CYBER_AGENT_OUTPUT_DIR")
            or get_default_base_dir()
        )

        # Get target name
        target_name = overrides.get("target_name")

        # Get operation ID
        operation_id = overrides.get("operation_id")

        # Get feature flags - unified output is now enabled by default
        enable_unified_output = (
            overrides.get("enable_unified_output", True)
            or os.getenv("CYBER_AGENT_ENABLE_UNIFIED_OUTPUT", "true").lower() == "true"
        )

        # cleanup_memory removed as part of memory management simplification

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

        # Check if required models are available
        try:
            client = ollama.Client(host=ollama_host)
            models_response = client.list()
            available_models = [
                m.get("model", m.get("name", "")) for m in models_response["models"]
            ]

            server_config = self.get_server_config("ollama")
            required_models = [
                server_config.llm.model_id,
                server_config.embedding.model_id,
            ]

            missing = [
                m
                for m in required_models
                if not any(m in model for model in available_models)
            ]

            if missing:
                raise ValueError(
                    f"Required models not found: {missing}. "
                    f"Pull them with: ollama pull {' && ollama pull '.join(missing)}"
                )
        except Exception as e:
            if "Required models not found" in str(e):
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

    def _convert_bearer_token_if_needed(self) -> None:
        """Convert AWS Bedrock API key to session credentials if provided."""
        bearer_token = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        if bearer_token and not os.getenv("AWS_ACCESS_KEY_ID"):
            os.environ["AWS_ACCESS_KEY_ID"] = "ASIABEARERTOKEN"
            os.environ["AWS_SECRET_ACCESS_KEY"] = "bearer+token+placeholder"
            os.environ["AWS_SESSION_TOKEN"] = bearer_token

    def _validate_aws_requirements(self) -> None:
        """Validate AWS requirements including Bedrock model access."""
        # Convert bearer token if needed
        self._convert_bearer_token_if_needed()
        
        # Verify AWS credentials are configured
        if not (os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE")):
            raise EnvironmentError(
                "AWS credentials not configured for remote mode. "
                "Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, configure AWS_PROFILE, "
                "or set AWS_BEARER_TOKEN_BEDROCK for API key authentication"
            )
        self._validate_bedrock_model_access()

    def _validate_litellm_requirements(self) -> None:
        """Validate LiteLLM requirements based on model provider prefix.
        
        LiteLLM handles authentication internally based on model prefixes,
        so we validate that required environment variables are set for the
        default model configuration.
        """
        # Get default LiteLLM model ID
        litellm_config = self._default_configs.get("litellm", {})
        model_id = litellm_config.get("llm", {}).model_id if hasattr(litellm_config.get("llm", {}), "model_id") else ""
        
        # Check provider-specific requirements based on model prefix
        if model_id.startswith("bedrock/"):
            # LiteLLM does NOT support AWS bearer tokens - only standard credentials
            if not (os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE")):
                raise EnvironmentError(
                    "AWS credentials not configured for LiteLLM Bedrock models. "
                    "Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or configure AWS_PROFILE. "
                    "Note: LiteLLM does not support AWS_BEARER_TOKEN_BEDROCK - use standard AWS credentials instead."
                )
                
        elif model_id.startswith("openai/"):
            if not os.getenv("OPENAI_API_KEY"):
                raise EnvironmentError(
                    "OPENAI_API_KEY not configured for LiteLLM OpenAI models. "
                    "Set OPENAI_API_KEY environment variable."
                )
        elif model_id.startswith("anthropic/"):
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise EnvironmentError(
                    "ANTHROPIC_API_KEY not configured for LiteLLM Anthropic models. "
                    "Set ANTHROPIC_API_KEY environment variable."
                )
        elif model_id.startswith("cohere/"):
            if not os.getenv("COHERE_API_KEY"):
                raise EnvironmentError(
                    "COHERE_API_KEY not configured for LiteLLM Cohere models. "
                    "Set COHERE_API_KEY environment variable."
                )
        # LiteLLM will handle other provider validations internally


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
