#!/usr/bin/env python3
"""
Provider-specific configuration modules.

Each provider module contains helpers specific to that provider's configuration,
connectivity, and model management.
"""

from modules.config.providers.bedrock_config import get_default_region
from modules.config.providers.ollama_config import get_ollama_host
from modules.config.providers.litellm_config import (
    align_litellm_defaults,
    get_context_window_fallbacks,
    split_litellm_model_id,
)

__all__ = [
    "get_default_region",
    "get_ollama_host",
    "split_litellm_model_id",
    "align_litellm_defaults",
    "get_context_window_fallbacks",
]
