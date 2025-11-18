#!/usr/bin/env python3
"""
Default configuration builders for all providers.

This module provides default configurations for LLM models, embeddings,
and provider-specific settings across Bedrock, Ollama, and LiteLLM.
"""

from typing import Any, Dict

from modules.config.types import (
    EmbeddingConfig,
    LLMConfig,
    MemoryLLMConfig,
    ModelProvider,
)


def build_default_configs() -> Dict[str, Dict[str, Any]]:
    """Initialize default configurations for all provider types.

    Returns:
        Dictionary mapping provider names to their default configurations.
        Each provider config includes:
        - llm: Main LLM configuration
        - embedding: Embedding model configuration
        - memory_llm: Memory service LLM configuration
        - evaluation_llm: Evaluation LLM configuration
        - swarm_llm: Swarm/specialist LLM configuration
        - host: Provider host (if applicable)
        - region: AWS region (if applicable)
    """
    return {
        "ollama": build_ollama_defaults(),
        "bedrock": build_bedrock_defaults(),
        "litellm": build_litellm_defaults(),
    }


def build_ollama_defaults() -> Dict[str, Any]:
    """Build default configuration for Ollama provider.

    Returns:
        Ollama default configuration with local models
    """
    return {
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
    }


def build_bedrock_defaults() -> Dict[str, Any]:
    """Build default configuration for AWS Bedrock provider.

    Returns:
        Bedrock default configuration with Claude models
    """
    return {
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
    }


def build_litellm_defaults() -> Dict[str, Any]:
    """Build default configuration for LiteLLM provider.

    LiteLLM acts as a universal gateway supporting 100+ providers.
    Defaults use Bedrock models through LiteLLM.

    Returns:
        LiteLLM default configuration with Bedrock models via LiteLLM
    """
    return {
        "llm": LLMConfig(
            provider=ModelProvider.LITELLM,
            model_id="bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",  # Default to Bedrock via LiteLLM
            temperature=0.95,
            max_tokens=32000,
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
    }
