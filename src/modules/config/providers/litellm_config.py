#!/usr/bin/env python3
"""
LiteLLM provider configuration helpers.

This module provides configuration utilities specific to LiteLLM universal gateway,
including model ID parsing, embedding defaults, and configuration alignment.
"""

import importlib.util
from typing import Any, Dict, List, Optional, Tuple

import litellm

from modules.config.system.env_reader import EnvironmentReader
from modules.config.system.logger import get_logger
from modules.config.types import (
    LITELLM_EMBEDDING_DEFAULTS,
    DEFAULT_LITELLM_EMBEDDING,
    EMBEDDING_DIMENSIONS,
    ModelProvider,
    LLMConfig,
    EmbeddingConfig,
    MemoryLLMConfig,
)

logger = get_logger("Config.LiteLLMProvider")


def split_litellm_model_id(model_id: str) -> Tuple[str, str]:
    """Split LiteLLM model id into provider prefix and base id.

    Args:
        model_id: Full LiteLLM model ID (e.g., "bedrock/claude-3", "openai/gpt-4")

    Returns:
        Tuple of (provider_prefix, base_model_id)
        Returns ("", model_id) if no prefix found
    """
    if not model_id:
        return "", ""
    if "/" in model_id:
        prefix, base = model_id.split("/", 1)
        # Special handling for Gemini "models/" prefix
        if prefix.lower() == "models":
            prefix = "gemini"
        return prefix.lower(), base
    return "", model_id


def get_context_window_fallbacks(provider: str) -> Optional[List[Dict[str, List[str]]]]:
    """Optional model fallback mappings for context window resolution.

    Currently returns None by default. Kept as an extension point if a future
    config source wants to provide structured context window fallbacks.

    Args:
        provider: Provider name

    Returns:
        None (no fallbacks configured by default)
    """
    return None


def align_litellm_defaults(
    defaults: Dict[str, Any], env_reader: EnvironmentReader
) -> None:
    """Ensure LiteLLM configuration components stay aligned with the selected model.

    Uses LiteLLM's get_max_tokens() API to dynamically cap max_tokens based on
    model limits from model_prices_and_context_window.json. This ensures we stay
    within model limits without hardcoding values that may change.

    Aligns:
    - Main LLM max_tokens to model limits
    - memory_llm, evaluation_llm, swarm_llm configs to main LLM model
    - Embedding model and dimensions based on provider

    Args:
        defaults: Default configuration dictionary (modified in-place)
        env_reader: Environment variable reader for overrides

    Raises:
        ImportError: If required dependencies for embeddings are missing
    """
    llm_cfg = defaults.get("llm")
    if not isinstance(llm_cfg, LLMConfig):
        return

    provider_prefix, base_model = split_litellm_model_id(llm_cfg.model_id)
    if not base_model:
        return

    # Use LiteLLM's model database to get max_output_tokens for this model
    # This handles all providers and updates automatically with LiteLLM
    try:
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

    embed_override = env_reader.get("CYBER_AGENT_EMBEDDING_MODEL")

    # Align all LLM configs to the main LLM model
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

    # Configure embedding model
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
                # Infer dimensions from model name
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
            # Use provider-specific embedding defaults
            embed_model, dims = LITELLM_EMBEDDING_DEFAULTS.get(
                provider_prefix, DEFAULT_LITELLM_EMBEDDING
            )

        # Check required dependencies for specific embedding models
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

        # Update embedding configuration
        embed_cfg.model_id = embed_model
        embed_cfg.dimensions = dims
        embed_cfg.provider = ModelProvider.LITELLM
        embed_cfg.parameters["dimensions"] = dims
