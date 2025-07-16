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
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    """Supported model providers."""
    AWS_BEDROCK = "aws_bedrock"
    OLLAMA = "ollama"
    OPENAI = "openai"  # Future extension possible in a simple way


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
            raise ValueError(f"provider must be a ModelProvider enum, got {type(self.provider)}")


@dataclass
class LLMConfig(ModelConfig):
    """Configuration for LLM models."""
    temperature: float = 0.95
    max_tokens: int = 4096
    top_p: float = 0.95
    
    def __post_init__(self):
        super().__post_init__()
        # Add LLM-specific parameters to the parameters dict
        self.parameters.update({
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p
        })


@dataclass
class EmbeddingConfig(ModelConfig):
    """Configuration for embedding models."""
    dimensions: int = 1024
    
    def __post_init__(self):
        super().__post_init__()
        # Add embedding-specific parameters
        self.parameters.update({
            "dimensions": self.dimensions
        })


@dataclass
class VectorStoreConfig:
    """Configuration for vector storage."""
    provider: str = "faiss"
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryConfig:
    """Configuration for memory system."""
    embedder: ModelConfig
    llm: ModelConfig
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)


@dataclass
class EvaluationConfig:
    """Configuration for evaluation system."""
    llm: ModelConfig
    embedding: ModelConfig


@dataclass
class SwarmConfig:
    """Configuration for swarm system."""
    llm: ModelConfig


@dataclass
class ServerConfig:
    """Complete server configuration."""
    server_type: str  # "local" or "remote"
    llm: LLMConfig
    embedding: EmbeddingConfig
    memory: MemoryConfig
    evaluation: EvaluationConfig
    swarm: SwarmConfig
    host: Optional[str] = None
    region: str = "us-east-1"


class ConfigManager:
    """Central configuration manager for all model configurations."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self._config_cache = {}
        self._default_configs = self._initialize_default_configs()
    
    def _initialize_default_configs(self) -> Dict[str, Dict[str, Any]]:
        """Initialize default configurations for all server types."""
        return {
            "local": {
                "llm": LLMConfig(
                    provider=ModelProvider.OLLAMA,
                    model_id="llama3.2:3b",
                    temperature=0.95,
                    max_tokens=4096
                ),
                "embedding": EmbeddingConfig(
                    provider=ModelProvider.OLLAMA,
                    model_id="mxbai-embed-large",
                    dimensions=1024
                ),
                "memory_llm": LLMConfig(
                    provider=ModelProvider.OLLAMA,
                    model_id="llama3.2:3b",
                    temperature=0.1,
                    max_tokens=2000
                ),
                "evaluation_llm": LLMConfig(
                    provider=ModelProvider.OLLAMA,
                    model_id="llama3.2:3b",
                    temperature=0.1,
                    max_tokens=2000
                ),
                "swarm_llm": LLMConfig(
                    provider=ModelProvider.OLLAMA,
                    model_id="llama3.2:3b",
                    temperature=0.7,
                    max_tokens=500
                ),
                "host": None,  # Will be resolved dynamically
                "region": "local"
            },
            "remote": {
                "llm": LLMConfig(
                    provider=ModelProvider.AWS_BEDROCK,
                    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                    temperature=0.95,
                    max_tokens=4096,
                    top_p=0.95
                ),
                "embedding": EmbeddingConfig(
                    provider=ModelProvider.AWS_BEDROCK,
                    model_id="amazon.titan-embed-text-v2:0",
                    dimensions=1024
                ),
                "memory_llm": LLMConfig(
                    provider=ModelProvider.AWS_BEDROCK,
                    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    temperature=0.1,
                    max_tokens=2000
                ),
                "evaluation_llm": LLMConfig(
                    provider=ModelProvider.AWS_BEDROCK,
                    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    temperature=0.1,
                    max_tokens=2000
                ),
                "swarm_llm": LLMConfig(
                    provider=ModelProvider.AWS_BEDROCK,
                    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    temperature=0.7,
                    max_tokens=500
                ),
                "host": None,
                "region": "us-east-1"
            }
        }
    
    def get_server_config(self, server: str, **overrides) -> ServerConfig:
        """Get complete server configuration with optional overrides."""
        cache_key = f"server_{server}_{hash(frozenset(overrides.items()))}"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        if server not in self._default_configs:
            raise ValueError(f"Unsupported server type: {server}")
        
        defaults = self._default_configs[server].copy()
        
        # Apply environment variable overrides
        defaults = self._apply_environment_overrides(server, defaults)
        
        # Apply function parameter overrides
        defaults.update(overrides)
        
        # Build memory configuration
        memory_config = MemoryConfig(
            embedder=self._get_memory_embedder_config(server, defaults),
            llm=self._get_memory_llm_config(server, defaults),
            vector_store=VectorStoreConfig()
        )
        
        # Build evaluation configuration
        evaluation_config = EvaluationConfig(
            llm=self._get_evaluation_llm_config(server, defaults),
            embedding=self._get_evaluation_embedding_config(server, defaults)
        )
        
        # Build swarm configuration
        swarm_config = SwarmConfig(
            llm=self._get_swarm_llm_config(server, defaults)
        )
        
        # Resolve host for local server
        host = self.get_ollama_host() if server == "local" else None
        
        config = ServerConfig(
            server_type=server,
            llm=defaults["llm"],
            embedding=defaults["embedding"],
            memory=memory_config,
            evaluation=evaluation_config,
            swarm=swarm_config,
            host=host,
            region=defaults["region"]
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
    
    def validate_requirements(self, server: str) -> None:
        """Validate that all requirements are met for the specified server."""
        if server == "local":
            self._validate_ollama_requirements()
        elif server == "remote":
            self._validate_aws_requirements()
        else:
            raise ValueError(f"Unsupported server type: {server}")
    
    def get_ollama_host(self) -> str:
        """Determine appropriate Ollama host based on environment."""
        env_host = os.getenv("OLLAMA_HOST")
        if env_host:
            return env_host
        
        # Check if running in Docker
        if os.path.exists('/app'): 
            candidates = ["http://localhost:11434", "http://host.docker.internal:11434"]
            for host in candidates:
                try:
                    response = requests.get(f"{host}/api/version", timeout=2)
                    if response.status_code == 200:
                        return host
                except Exception:
                    pass
            # Fallback to host.docker.internal if no connection works
            return "http://host.docker.internal:11434"
        else:
            # Native execution - use localhost
            return "http://localhost:11434"
    
    def set_environment_variables(self, server: str) -> None:
        """Set environment variables for backward compatibility."""
        server_config = self.get_server_config(server)
        
        if server == "local":
            os.environ["MEM0_LLM_PROVIDER"] = "ollama"
            os.environ["MEM0_LLM_MODEL"] = server_config.memory.llm.model_id
            os.environ["MEM0_EMBEDDING_MODEL"] = server_config.memory.embedder.model_id
        else:
            os.environ["MEM0_LLM_MODEL"] = server_config.memory.llm.model_id
            os.environ["MEM0_EMBEDDING_MODEL"] = server_config.memory.embedder.model_id
    
    def _apply_environment_overrides(self, server: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to default configuration."""
        # Main LLM model override
        llm_model = os.getenv("CYBER_AGENT_LLM_MODEL")
        if llm_model:
            defaults["llm"] = LLMConfig(
                provider=defaults["llm"].provider,
                model_id=llm_model,
                temperature=defaults["llm"].temperature,
                max_tokens=defaults["llm"].max_tokens
            )
        
        # Embedding model override
        embedding_model = os.getenv("CYBER_AGENT_EMBEDDING_MODEL")
        if embedding_model:
            defaults["embedding"] = EmbeddingConfig(
                provider=defaults["embedding"].provider,
                model_id=embedding_model,
                dimensions=defaults["embedding"].dimensions
            )
        
        # Evaluation model override
        eval_model = os.getenv("CYBER_AGENT_EVALUATION_MODEL") or os.getenv("RAGAS_EVALUATOR_MODEL")
        if eval_model:
            defaults["evaluation_llm"] = LLMConfig(
                provider=defaults["evaluation_llm"].provider,
                model_id=eval_model,
                temperature=defaults["evaluation_llm"].temperature,
                max_tokens=defaults["evaluation_llm"].max_tokens
            )
        
        # Swarm model override
        swarm_model = os.getenv("CYBER_AGENT_SWARM_MODEL")
        if swarm_model:
            defaults["swarm_llm"] = LLMConfig(
                provider=defaults["swarm_llm"].provider,
                model_id=swarm_model,
                temperature=defaults["swarm_llm"].temperature,
                max_tokens=defaults["swarm_llm"].max_tokens
            )
        
        # Memory LLM override
        memory_llm_model = os.getenv("MEM0_LLM_MODEL")
        if memory_llm_model:
            defaults["memory_llm"] = LLMConfig(
                provider=defaults["memory_llm"].provider,
                model_id=memory_llm_model,
                temperature=defaults["memory_llm"].temperature,
                max_tokens=defaults["memory_llm"].max_tokens
            )
        
        # Memory embedding override (only if not already overridden)
        mem0_embedding_model = os.getenv("MEM0_EMBEDDING_MODEL")
        if mem0_embedding_model and not embedding_model:  # Only if not already overridden
            defaults["embedding"] = EmbeddingConfig(
                provider=defaults["embedding"].provider,
                model_id=mem0_embedding_model,
                dimensions=defaults["embedding"].dimensions
            )
        
        # Region override
        aws_region = os.getenv("AWS_REGION")
        if aws_region:
            defaults["region"] = aws_region
        
        return defaults
    
    def _get_memory_embedder_config(self, server: str, defaults: Dict[str, Any]) -> ModelConfig:
        """Get memory embedder configuration."""
        return defaults["embedding"]
    
    def _get_memory_llm_config(self, server: str, defaults: Dict[str, Any]) -> ModelConfig:
        """Get memory LLM configuration."""
        return defaults["memory_llm"]
    
    def _get_evaluation_llm_config(self, server: str, defaults: Dict[str, Any]) -> ModelConfig:
        """Get evaluation LLM configuration."""
        return defaults["evaluation_llm"]
    
    def _get_evaluation_embedding_config(self, server: str, defaults: Dict[str, Any]) -> ModelConfig:
        """Get evaluation embedding configuration."""
        return defaults["embedding"]
    
    def _get_swarm_llm_config(self, server: str, defaults: Dict[str, Any]) -> ModelConfig:
        """Get swarm LLM configuration."""
        return defaults["swarm_llm"]
    
    def _validate_ollama_requirements(self) -> None:
        """Validate Ollama requirements."""
        ollama_host = self.get_ollama_host()
        
        # Check if Ollama is running
        try:
            response = requests.get(f"{ollama_host}/api/version", timeout=5)
            if response.status_code != 200:
                raise ConnectionError("Ollama server not responding")
        except Exception:
            raise ConnectionError(
                f"Ollama server not accessible at {ollama_host}. "
                "Please ensure Ollama is installed and running."
            )
        
        # Check if required models are available
        try:
            import ollama
            client = ollama.Client(host=ollama_host)
            models_response = client.list()
            available_models = [m.get("model", m.get("name", "")) for m in models_response["models"]]
            
            server_config = self.get_server_config("local")
            required_models = [
                server_config.llm.model_id,
                server_config.embedding.model_id
            ]
            
            missing = [
                m for m in required_models
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
            raise ConnectionError(f"Could not verify Ollama models: {e}")
    
    def _validate_aws_requirements(self) -> None:
        """Validate AWS requirements."""
        if not (os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE")):
            raise EnvironmentError(
                "AWS credentials not configured for remote mode. "
                "Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or configure AWS_PROFILE"
            )


# Global configuration manager instance
_config_manager = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


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