"""Unified model capabilities and limits.

This module centralizes:
- Capability detection (reasoning, tool support, param allowance)
- Static INPUT token limits and provider defaults for prompt budgeting

Precedence order for all parameters:
1. models.dev (authoritative, 500+ models)
2. Static patterns (known models, version-controlled)
3. LiteLLM detection (dynamic, for unknown models)
4. Environment overrides (CYBER_REASONING_ALLOW/DENY)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Models.dev client for authoritative model metadata
try:
    from modules.config.models.dev_client import get_models_client
except ImportError:
    get_models_client = None  # type: ignore

# --- LiteLLM imports (guarded) -------------------------------------------------
try:
    import litellm  # type: ignore
    from litellm.utils import (  # type: ignore
        LlmProviders,
        ProviderConfigManager,
        supports_reasoning as llm_supports_reasoning,
    )
except Exception:  # pragma: no cover
    litellm = None  # type: ignore
    ProviderConfigManager = None  # type: ignore
    LlmProviders = None  # type: ignore

    def llm_supports_reasoning(
        model: str, custom_llm_provider: Optional[str] = None
    ) -> bool:  # type: ignore
        return False


# --- Helpers -------------------------------------------------------------------


def _split_prefix(model_id: str) -> Tuple[str, str]:
    if not isinstance(model_id, str):
        return "", ""
    if "/" in model_id:
        p, rest = model_id.split("/", 1)
        return p.lower(), rest
    return "", model_id


def supports_reasoning_model(model_id: Optional[str]) -> bool:
    """Return True if the model is known to support extended reasoning blocks.

    This is a fast explicit check for models with native reasoning support.
    For more comprehensive capability detection, use ModelCapabilitiesResolver.

    Scope (explicit):
    - OpenAI/Azure: GPT-5 family and O-series (o3/o4 and mini variants)
    - Anthropic/Bedrock: Claude Sonnet 4 / 4.5 and Opus
    - Moonshot (LiteLLM): Kimi 'thinking' preview variants only

    NOTE: Do not include older Claude 3.7 and below.
    """
    mid = (model_id or "").lower()

    # Fast path: OpenAI/Azure families already supported
    openai_reasoning_markers = (
        "gpt-5",
        "/o4",
        "/o3",
        "o4-mini",
        "o3-mini",
    )
    if any(marker in mid for marker in openai_reasoning_markers):
        return True

    # Moonshot Kimi 'thinking' variants via LiteLLM (tools unsupported on these models)
    moonshot_thinking_markers = (
        "moonshot/kimi-thinking",
        "kimi-thinking",
        "kimi_k2_thinking",
        "k2-thinking",
    )
    if any(marker in mid for marker in moonshot_thinking_markers):
        return True

    # Anthropic/Bedrock explicit allow-list (Sonnet 4/4.5 and Opus only)
    anthropic_allow_markers = (
        # Common Anthropic naming forms across providers
        "claude-sonnet-4-5",
        "sonnet-4-5",
        "claude-sonnet-4",
        "sonnet-4",
        "claude-opus",
        "/opus",  # e.g., claude-4-opus or claude-3-opus style ids
        "-opus",  # covers bedrock/other provider dash-separated ids
    )
    return any(marker in mid for marker in anthropic_allow_markers)


# --- Capabilities ---------------------------------------------------------------


@dataclass(frozen=True)
class Capabilities:
    supports_reasoning: bool
    pass_reasoning_effort: bool
    supports_tools: bool
    supports_tool_choice: bool


class ModelCapabilitiesResolver:
    """Model capability detection with authoritative models.dev source.

    Precedence: models.dev → static patterns → LiteLLM → env overrides
    Cached per (provider, model_id).
    """

    @staticmethod
    @lru_cache(maxsize=512)
    def capabilities(provider: str, model_id: str) -> Capabilities:
        provider = (provider or "").lower()
        model = model_id or ""
        base_provider = provider

        if provider == "litellm":
            pfx, _ = _split_prefix(model)
            if pfx:
                base_provider = pfx

        supports_reason = False
        pass_reasoning_effort = False
        supports_tools = True
        supports_tool_choice = True

        # Priority 1: models.dev (authoritative source for 500+ models)
        if get_models_client is not None:
            try:
                client = get_models_client()
                info = client.get_model_info(model)
                if info and info.capabilities:
                    caps = info.capabilities
                    supports_reason = bool(caps.reasoning)
                    supports_tools = bool(caps.tool_call)
                    supports_tool_choice = supports_tools
                    logger.debug(
                        "Using models.dev: model=%s reasoning=%s tools=%s",
                        model,
                        supports_reason,
                        supports_tools,
                    )
            except Exception as e:
                logger.debug("models.dev lookup failed for %s: %s", model, e)

        # Priority 2: Static patterns (known models, when models.dev unavailable)
        if not supports_reason:
            supports_reason = supports_reasoning_model(model)
            if supports_reason:
                logger.debug("Using static pattern: model=%s reasoning=%s", model, True)

        # Priority 3: LiteLLM detection (fallback for unknown models)
        if not supports_reason:
            try:
                custom = (
                    base_provider
                    if base_provider and base_provider != "litellm"
                    else None
                )
                supports_reason = bool(
                    llm_supports_reasoning(model=model, custom_llm_provider=custom)  # type: ignore[arg-type]
                )
                if supports_reason:
                    logger.debug(
                        "Using LiteLLM detection: model=%s reasoning=%s", model, True
                    )
            except Exception:
                supports_reason = False

        # Check provider params for reasoning_effort support
        allowed_params: list[str] = []
        try:
            if (
                ProviderConfigManager is not None
                and LlmProviders is not None
                and base_provider
            ):
                prov_enum = LlmProviders(base_provider)  # type: ignore[call-arg]
                cfg = ProviderConfigManager.get_provider_chat_config(
                    model=model, provider=prov_enum
                )
                if cfg is not None and hasattr(cfg, "get_supported_openai_params"):
                    allowed_params = list(
                        cfg.get_supported_openai_params(model=model) or []
                    )
        except Exception as e:
            logger.debug(
                "Provider config lookup failed for %s/%s: %s",
                base_provider,
                model,
                e,
            )

        lowered = {p.lower() for p in allowed_params}
        if ("thinking" in lowered) or ("reasoning_effort" in lowered):
            supports_reason = True
        pass_reasoning_effort = "reasoning_effort" in lowered

        # Update tool support from provider params if available
        if lowered:
            supports_tools = "tools" in lowered
            supports_tool_choice = "tool_choice" in lowered

        # Priority 4: Environment overrides (highest precedence)
        model_l = model.lower()
        allow = os.getenv("CYBER_REASONING_ALLOW", "").lower().split(",")
        deny = os.getenv("CYBER_REASONING_DENY", "").lower().split(",")
        allow = [a.strip() for a in allow if a and a.strip()]
        deny = [d.strip() for d in deny if d and d.strip()]

        if any(tok in model_l for tok in allow):
            supports_reason = True
            logger.info("ENV override: forcing reasoning=True for %s", model)
        if any(tok in model_l for tok in deny):
            supports_reason = False
            logger.info("ENV override: forcing reasoning=False for %s", model)

        return Capabilities(
            supports_reasoning=supports_reason,
            pass_reasoning_effort=pass_reasoning_effort,
            supports_tools=supports_tools,
            supports_tool_choice=supports_tool_choice,
        )


# Public helper
_resolver = ModelCapabilitiesResolver()


def get_capabilities(provider: str, model_id: str) -> Capabilities:
    return _resolver.capabilities(provider, model_id)


# --- Input limits (static registry) --------------------------------------------
# Accurate INPUT token limits (context window capacity) for known models
# These are NOT output limits.

MODEL_INPUT_LIMITS = {
    # Azure OpenAI GPT-5 Family (400K total, 272K input, 128K output)
    "azure/gpt-5": 272000,
    "azure/gpt-5-mini": 272000,
    "azure/gpt-5-nano": 272000,
    "azure/gpt-5-pro": 272000,
    "azure/gpt-5-codex": 272000,
    "azure/responses/gpt-5-pro": 272000,
    # Azure OpenAI GPT-5-Chat (128K total)
    "azure/gpt-5-chat": 128000,
    # Azure OpenAI GPT-OSS Family (131K context)
    "azure/gpt-oss-120b": 131072,
    "azure/gpt-oss-20b": 131072,
    # Azure OpenAI GPT-4 Family
    "azure/gpt-4o": 128000,
    "azure/gpt-4o-mini": 128000,
    "azure/gpt-4": 128000,
    "azure/gpt-4-turbo": 128000,
    # OpenAI Direct (same as Azure variants)
    "gpt-5": 272000,
    "gpt-5-mini": 272000,
    "gpt-5-nano": 272000,
    "gpt-5-pro": 272000,
    "gpt-5-codex": 272000,
    "gpt-5-chat": 128000,
    "gpt-oss-120b": 131072,
    "gpt-oss-20b": 131072,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 128000,
    # AWS Bedrock - Claude 3.5 Family (200K input)
    "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0": 200000,
    "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0": 200000,
    "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0": 200000,
    # AWS Bedrock - Claude Sonnet 4.5 (1M input)
    "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0": 1000000,
    "bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0": 1000000,
    # AWS Bedrock - Claude 3 Opus/Sonnet (200K)
    "bedrock/anthropic.claude-3-opus-20240229-v1:0": 200000,
    "bedrock/anthropic.claude-3-sonnet-20240229-v1:0": 200000,
    # Anthropic Direct API (same as Bedrock)
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-5-haiku-20241022": 200000,
    "claude-sonnet-4-5-20250929": 1000000,
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": 1000000,
    # OpenRouter - Various providers
    "openrouter/openrouter/polaris-alpha": 256000,
    "openrouter/anthropic/claude-3.5-sonnet": 200000,
    "openrouter/anthropic/claude-3.5-haiku": 200000,
    "openrouter/google/gemini-2.5-flash": 1000000,
    "openrouter/google/gemini-2.0-flash-exp": 1000000,
    # Moonshot Kimi
    "moonshot/kimi-k2-thinking": 256000,
    # Google Gemini (1M input for flash models)
    "gemini/gemini-2.5-flash": 1000000,
    "gemini/gemini-2.0-flash-exp": 1000000,
    "gemini/gemini-1.5-pro": 1000000,
    "gemini/gemini-1.5-flash": 1000000,
    "vertex_ai/gemini-2.5-flash": 1000000,
    "vertex_ai/gemini-2.0-flash-exp": 1000000,
    # Deepseek
    "deepseek/deepseek-chat": 64000,
    "deepseek/deepseek-reasoner": 64000,
    # Common Ollama models (approximate)
    "ollama/llama3.1:70b": 128000,
    "ollama/llama3.1:8b": 128000,
    "ollama/mistral:latest": 32000,
    "ollama/codellama:latest": 16000,
}

MODEL_FAMILY_PATTERNS = [
    # Azure/OpenAI GPT-5-Chat variants (128K)
    (r"azure.*gpt-5-chat", 128000),
    (r"^gpt-5-chat", 128000),
    # Azure/OpenAI GPT-5 variants (272K)
    (r"azure.*gpt-5", 272000),
    (r"^gpt-5", 272000),
    # Azure/OpenAI GPT-OSS variants (131K)
    (r"azure.*gpt-oss", 131072),
    (r"^gpt-oss", 131072),
    # Azure/OpenAI GPT-4 variants
    (r"azure.*gpt-4", 128000),
    (r"^gpt-4", 128000),
    # Bedrock Claude Sonnet 4.x = 1M context
    (r"bedrock/.*claude.*sonnet.*4[-.]5", 1000000),
    (r"claude.*sonnet.*4[-.]5", 1000000),
    # Bedrock Claude 3.5 variants = 200K
    (r"bedrock/.*claude.*3-5", 200000),
    (r"claude.*3-5", 200000),
    # Bedrock Claude 3 variants = 200K
    (r"bedrock/.*claude.*3-opus", 200000),
    (r"bedrock/.*claude.*3-sonnet", 200000),
    # OpenRouter with claude
    (r"openrouter/.*claude", 200000),
    # Gemini variants = 1M
    (r"gemini.*2\.[05].*flash", 1000000),
    (r"gemini.*1\.5", 1000000),
    (r"vertex_ai/.*gemini", 1000000),
    # Ollama llama3.1 variants = 128K
    (r"ollama/.*llama3\.1", 128000),
]


def get_model_input_limit(model_id: str) -> Optional[int]:
    """Get INPUT token limit for a model (context window capacity).

    Precedence:
    1. models.dev (authoritative)
    2. Static registry (exact match)
    3. Pattern matching (family match)
    4. None (caller should use provider defaults)
    """
    if not model_id:
        return None

    # Priority 1: models.dev
    if get_models_client is not None:
        try:
            client = get_models_client()
            info = client.get_model_info(model_id)
            if info and info.limits and info.limits.context:
                return info.limits.context
        except Exception:
            pass

    # Priority 2: Static registry (exact match)
    if model_id in MODEL_INPUT_LIMITS:
        return MODEL_INPUT_LIMITS[model_id]

    # Priority 3: Pattern matching (family match)
    for pattern, limit in MODEL_FAMILY_PATTERNS:
        if re.search(pattern, model_id, re.IGNORECASE):
            return limit

    return None


def get_provider_default_limit(provider: str) -> Optional[int]:
    """Conservative default INPUT limit for a provider (last resort)."""
    defaults = {
        "bedrock": 200000,  # Conservative for Claude 3.5
        "ollama": 32000,  # Varies widely locally
        "litellm": 128000,  # Unknown LiteLLM models
    }
    return defaults.get((provider or "").lower())


def get_model_output_limit(model_id: str) -> Optional[int]:
    """Get OUTPUT token limit for a model (max completion length).

    Precedence:
    1. MAX_COMPLETION_TOKENS env var (UI reasoning models)
    2. MAX_TOKENS env var (UI general setting)
    3. models.dev (authoritative)
    4. None (caller should use safe defaults)
    """
    if not model_id:
        return None

    # Priority 1: MAX_COMPLETION_TOKENS (UI reasoning models)
    override = os.getenv("MAX_COMPLETION_TOKENS")
    if override:
        try:
            return int(override)
        except ValueError:
            logger.warning("Invalid MAX_COMPLETION_TOKENS: %s", override)

    # Priority 2: MAX_TOKENS (UI general setting)
    override = os.getenv("MAX_TOKENS")
    if override:
        try:
            return int(override)
        except ValueError:
            logger.warning("Invalid MAX_TOKENS: %s", override)

    # Priority 3: models.dev
    if get_models_client is not None:
        try:
            client = get_models_client()
            info = client.get_model_info(model_id)
            if info and info.limits and info.limits.output:
                return info.limits.output
        except Exception:
            pass

    return None


def get_model_pricing(model_id: str) -> Optional[tuple[float, float]]:
    """Get pricing for a model (cost per million tokens).

    Returns:
        Tuple of (input_cost, output_cost) in USD per million tokens
        None if pricing unavailable
    """
    if not model_id:
        return None

    if get_models_client is not None:
        try:
            client = get_models_client()
            info = client.get_model_info(model_id)
            if info and info.pricing:
                return (info.pricing.input, info.pricing.output)
        except Exception:
            pass

    return None


__all__ = [
    # Capabilities
    "Capabilities",
    "ModelCapabilitiesResolver",
    "get_capabilities",
    "supports_reasoning_model",
    # Limits
    "get_model_input_limit",
    "get_model_output_limit",
    "get_provider_default_limit",
    "MODEL_INPUT_LIMITS",
    "MODEL_FAMILY_PATTERNS",
    # Pricing
    "get_model_pricing",
]
