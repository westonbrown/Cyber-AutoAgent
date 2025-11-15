#!/usr/bin/env python3
"""
Type definitions for configuration system.

Contains all dataclass definitions, enums, and constants used across
the configuration modules to avoid circular imports.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Literal

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


@dataclass
class MCPConnection:
    """Configuration for a single MCP server connection."""

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
    """Configuration for Model Context Protocol servers."""

    enabled: bool = field(default_factory=lambda: False)
    connections: List[MCPConnection] = field(default_factory=list)


@dataclass
class AgentConfig:
    """Configuration object for agent creation."""

    target: str
    objective: str
    max_steps: int = 100
    available_tools: Optional[List[str]] = None
    op_id: Optional[str] = None
    model_id: Optional[str] = None
    region_name: Optional[str] = None
    provider: str = "bedrock"
    memory_path: Optional[str] = None
    memory_mode: str = "auto"
    module: str = "general"
    mcp_connections: List[MCPConnection] = field(default_factory=list)


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

