#!/usr/bin/env python3
"""
Model creation factory for all providers.

This module contains all model instantiation logic for Bedrock, Ollama, and LiteLLM.
Model creation is a configuration concern because it involves reading configuration,
applying provider-specific settings, and managing credentials.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

from strands.models import BedrockModel
from strands.models.litellm import LiteLLMModel
from strands.models.ollama import OllamaModel

from modules.config.system.logger import get_logger
from modules.config.models.capabilities import (
    get_model_input_limit,
    get_provider_default_limit,
)
from modules.handlers.conversation_budget import PROMPT_TOKEN_FALLBACK_LIMIT
from modules.handlers.utils import print_status

logger = get_logger("Config.ModelFactory")


def _get_config_manager():
    """Lazy import to avoid circular dependency."""
    from modules.config.manager import get_config_manager
    return get_config_manager()


# === Helper Functions ===


def _split_model_prefix(model_id: str) -> Tuple[str, str]:
    """Split model ID into provider prefix and remainder.

    Args:
        model_id: Full model ID (e.g., "bedrock/claude-3", "openai/gpt-4")

    Returns:
        Tuple of (prefix, remainder). Returns ("", model_id) if no prefix found.
    """
    if not isinstance(model_id, str):
        return "", ""
    if "/" in model_id:
        prefix, remainder = model_id.split("/", 1)
        return prefix.lower(), remainder
    return "", model_id


def _get_prompt_limit_from_model(model_id: Optional[str]) -> Optional[int]:
    """Get INPUT token limit (context window) from LiteLLM registry.

    Tries multiple forms of the model ID to find the limit in LiteLLM's database.

    Args:
        model_id: Model identifier

    Returns:
        INPUT token limit or None if not found
    """
    if not model_id:
        return None
    try:
        import litellm

        prefix, remainder = _split_model_prefix(model_id)
        candidates: List[str] = []
        # Common forms to try with LiteLLM's registry
        if remainder:
            candidates.append(remainder)  # e.g. openrouter/polaris-alpha
            # Also try last segment, e.g. polaris-alpha
            if "/" in remainder:
                candidates.append(remainder.split("/", 1)[-1])
        # Always include the full id as a last resort (e.g. openrouter/openrouter/polaris-alpha)
        candidates.append(model_id)

        for cand in candidates:
            limit: Optional[int] = None
            try:
                # Try get_context_window first (most accurate if available)
                get_cw = getattr(litellm, "get_context_window", None)
                if callable(get_cw):
                    cw = get_cw(cand)
                    if isinstance(cw, (int, float)) and int(cw) > 0:
                        limit = int(cw)
                # Check model_cost registry for max_input_tokens (INPUT limit, not output)
                # This must come BEFORE get_max_tokens because get_max_tokens returns OUTPUT limits
                if not limit:
                    model_cost = getattr(litellm, "model_cost", None)
                    if isinstance(model_cost, dict) and cand in model_cost:
                        info = model_cost.get(cand) or {}
                        # Prioritize max_input_tokens (correct input limit)
                        input_limit = info.get("max_input_tokens")
                        if (
                            isinstance(input_limit, (int, float))
                            and int(input_limit) > 0
                        ):
                            limit = int(input_limit)
                            logger.debug(
                                "Using max_input_tokens=%d for '%s' (not max_tokens which is output limit)",
                                limit,
                                cand,
                            )
                        # Fallback to context_window or max_tokens if max_input_tokens unavailable
                        elif not limit:
                            for key in ("context_window", "max_tokens"):
                                v = info.get(key)
                                if isinstance(v, (int, float)) and int(v) > 0:
                                    limit = int(v)
                                    break
                # Last resort: get_max_tokens (often returns OUTPUT limit, less reliable)
                if not limit:
                    get_mt = getattr(litellm, "get_max_tokens", None)
                    if callable(get_mt):
                        mt = get_mt(cand)
                        if isinstance(mt, (int, float)) and int(mt) > 0:
                            limit = int(mt)
                            logger.debug(
                                "Using get_max_tokens=%d for '%s' (may be output limit, verify with CYBER_PROMPT_FALLBACK_TOKENS)",
                                limit,
                                cand,
                            )
                if isinstance(limit, int) and limit > 0:
                    logger.info(
                        "Resolved prompt limit %d via LiteLLM for model '%s' (candidate '%s')",
                        limit,
                        model_id,
                        cand,
                    )
                    return limit
            except Exception:
                # Try next candidate
                continue
    except Exception:
        logger.debug(
            "Unable to resolve prompt token limit for %s", model_id, exc_info=True
        )
    return None


def _resolve_prompt_token_limit(
    provider: str, server_config: Any, model_id: Optional[str]
) -> Optional[int]:
    """
    Resolve INPUT token limit (context window capacity) for the model.

    Priority order:
    1. CYBER_PROMPT_LIMIT_FORCE - Explicit override
    2. Static model registry - Known models with verified limits
    3. LiteLLM max_input_tokens - Auto-detection from registry
    4. CYBER_PROMPT_FALLBACK_TOKENS - Explicit fallback
    5. Provider defaults - Conservative last resort

    Args:
        provider: Provider name ("bedrock", "ollama", "litellm")
        server_config: Server configuration object
        model_id: Model identifier

    Returns:
        INPUT limit (for conversation history), NOT output limit (for generation)
    """
    # Priority 1: Explicit override
    try:
        forced = os.getenv("CYBER_PROMPT_LIMIT_FORCE")
        if forced is not None:
            fv = int(forced)
            if fv > 0:
                logger.info(
                    "Using CYBER_PROMPT_LIMIT_FORCE=%d for model %s", fv, model_id
                )
                return fv
    except Exception:
        pass

    # Priority 2: Static model registry (known models with verified limits)
    limit = get_model_input_limit(model_id) if model_id else None
    if limit:
        logger.info(
            "Using static registry input limit=%d for model %s", limit, model_id
        )
        return limit

    # Priority 3: LiteLLM automatic detection (check max_input_tokens)
    if provider == "litellm" and model_id:
        limit = _get_prompt_limit_from_model(model_id)
        if limit:
            logger.info(
                "Using LiteLLM detected input limit=%d for model %s", limit, model_id
            )
            return limit

    # Priority 4: CYBER_PROMPT_FALLBACK_TOKENS (explicit fallback config)
    if PROMPT_TOKEN_FALLBACK_LIMIT > 0:
        logger.info(
            "Using CYBER_PROMPT_FALLBACK_TOKENS=%d as fallback for model %s",
            PROMPT_TOKEN_FALLBACK_LIMIT,
            model_id,
        )
        return PROMPT_TOKEN_FALLBACK_LIMIT

    # Priority 5: Provider-specific conservative defaults
    provider_default = get_provider_default_limit(provider)
    if provider_default:
        logger.warning(
            "Using conservative provider default limit=%d for %s (model %s). "
            "Consider setting CYBER_PROMPT_FALLBACK_TOKENS for accurate limit.",
            provider_default,
            provider,
            model_id,
        )
        return provider_default

    # No limit could be determined - warn and return None
    logger.warning(
        "Could not resolve input token limit for provider=%s model=%s. "
        "Set CYBER_PROMPT_FALLBACK_TOKENS or CYBER_PROMPT_LIMIT_FORCE to specify limit.",
        provider,
        model_id,
    )
    return None


def _parse_context_window_fallbacks() -> Optional[List[Dict[str, List[str]]]]:
    """Parse context window fallbacks from environment or configuration.

    Returns:
        List of fallback mappings or None if not configured
    """

    def _parse_spec(spec: str) -> Optional[List[Dict[str, List[str]]]]:
        fallbacks: List[Dict[str, List[str]]] = []
        for clause in spec.split(";"):
            clause = clause.strip()
            if not clause or ":" not in clause:
                continue
            model, targets = clause.split(":", 1)
            target_list = [
                target.strip() for target in targets.split(",") if target.strip()
            ]
            model_name = model.strip()
            if not model_name or not target_list:
                continue
            fallbacks.append({model_name: target_list})
        return fallbacks or None

    env_spec = os.getenv("CYBER_CONTEXT_WINDOW_FALLBACKS", "").strip()
    if env_spec:
        parsed = _parse_spec(env_spec)
        if parsed:
            return parsed
    try:
        config_manager = _get_config_manager()
        config_fallbacks = (
            config_manager.get_context_window_fallbacks("litellm") or []
        )
        if config_fallbacks:
            copied: List[Dict[str, List[str]]] = []
            for mapping in config_fallbacks:
                for model_name, targets in mapping.items():
                    copied.append({model_name: list(targets)})
            return copied or None
    except Exception:
        logger.debug("No configured context_window_fallbacks available", exc_info=True)
    return None


def _apply_context_window_fallbacks(client_args: Dict[str, Any]) -> None:
    """Attach context window fallbacks to LiteLLM if configured.

    Args:
        client_args: Client arguments dictionary (modified in-place)
    """
    fallbacks = _parse_context_window_fallbacks()
    if not fallbacks:
        return
    client_args.setdefault("context_window_fallbacks", fallbacks)
    try:
        import litellm

        litellm.context_window_fallbacks = fallbacks
    except Exception:
        logger.debug(
            "Unable to apply context_window_fallbacks to LiteLLM", exc_info=True
        )


def _handle_model_creation_error(provider: str, error: Exception) -> None:
    """Provide helpful error messages based on provider type.

    Args:
        provider: Provider name ("bedrock", "ollama", "litellm")
        error: Exception that occurred
    """
    error_messages = {
        "ollama": [
            "Ensure Ollama is installed: https://ollama.ai",
            "Start Ollama: ollama serve",
            "Pull required models (see config.py file)",
        ],
        "bedrock": [
            "Check AWS credentials and region settings",
            "Verify AWS_ACCESS_KEY_ID or AWS_BEARER_TOKEN_BEDROCK",
            "Ensure Bedrock access is enabled in your AWS account",
        ],
        "litellm": [
            "Check environment variables for your model provider",
            "For Bedrock: AWS_ACCESS_KEY_ID (bearer tokens not supported)",
            "For OpenAI: OPENAI_API_KEY",
            "For Anthropic: ANTHROPIC_API_KEY",
        ],
    }

    print_status(f"{provider.title()} model creation failed: {error}", "ERROR")
    if provider in error_messages:
        print_status("Troubleshooting steps:", "WARNING")
        for i, step in enumerate(error_messages[provider], 1):
            print_status(f"    {i}. {step}", "INFO")


# === Model Creation Functions ===


def create_bedrock_model(
    model_id: str,
    region_name: str,
    provider: str = "bedrock",
) -> BedrockModel:
    """Create AWS Bedrock model instance using centralized configuration.

    Args:
        model_id: Bedrock model identifier
        region_name: AWS region
        provider: Provider name (default: "bedrock")

    Returns:
        Configured BedrockModel instance

    Raises:
        Exception: If model creation fails
    """
    from botocore.config import Config as BotocoreConfig

    # Get centralized configuration
    config_manager = _get_config_manager()

    # Configure boto3 client with robust retry and timeout settings
    # This prevents ReadTimeoutError during long-running operations
    boto_config = BotocoreConfig(
        region_name=region_name,
        retries={"max_attempts": 10, "mode": "adaptive"},
        read_timeout=1200,  # 20 minutes
        connect_timeout=1200,  # 20 minutes
        max_pool_connections=100,
    )

    if config_manager.is_thinking_model(model_id):
        # Use thinking model configuration
        config = config_manager.get_thinking_model_config(model_id, region_name)
        return BedrockModel(
            model_id=config["model_id"],
            region_name=config["region_name"],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
            additional_request_fields=config["additional_request_fields"],
            boto_client_config=boto_config,
        )
    # Standard model configuration
    config = config_manager.get_standard_model_config(model_id, region_name, provider)

    # Select parameter source by model role (primary vs swarm)
    try:
        server_config = config_manager.get_server_config(provider)
        llm_temp = server_config.llm.temperature
        llm_max = server_config.llm.max_tokens
        role = "primary"
        swarm_env = config_manager.getenv("CYBER_AGENT_SWARM_MODEL")
        is_swarm = False
        if swarm_env and model_id and swarm_env == model_id:
            is_swarm = True
        elif (
            server_config.swarm
            and server_config.swarm.llm
            and server_config.swarm.llm.model_id == model_id
            and server_config.swarm.llm.model_id != server_config.llm.model_id
        ):
            is_swarm = True
        if is_swarm:
            llm_temp = server_config.swarm.llm.temperature
            # Use swarm model's max_tokens (calculated by ConfigManager from models.dev)
            # This respects per-model limits - different models have different constraints
            llm_max = server_config.swarm.llm.max_tokens

            # Defensive: Ensure valid max_tokens
            if not isinstance(llm_max, int) or llm_max <= 0:
                logger.warning(
                    "Invalid swarm max_tokens=%s for model %s, falling back to 4096",
                    llm_max,
                    config.get("model_id"),
                )
                llm_max = 4096

            role = "swarm"
    except Exception:
        # Fallback to standard config if any issue arises
        llm_temp = config.get("temperature", 0.95)
        llm_max = config.get("max_tokens", 4096)
        role = "unknown"

    # Observability: one-liner
    try:
        logger.info(
            "Model build: role=%s provider=bedrock model=%s max_tokens=%s",
            role,
            config.get("model_id"),
            llm_max,
        )
    except Exception:
        pass

    # Build BedrockModel kwargs
    model_kwargs = {
        "model_id": config["model_id"],
        "region_name": config["region_name"],
        "temperature": llm_temp,
        "max_tokens": llm_max,
        "boto_client_config": boto_config,
    }

    # Only include top_p if present in config (some providers reject both temperature and top_p)
    if config.get("top_p") is not None:
        model_kwargs["top_p"] = config["top_p"]

    # Add additional request fields if present (e.g., anthropic_beta for extended context)
    if config.get("additional_request_fields"):
        model_kwargs["additional_request_fields"] = config[
            "additional_request_fields"
        ]

    return BedrockModel(**model_kwargs)


def create_ollama_model(
    model_id: str,
    provider: str = "ollama",
) -> OllamaModel:
    """Create Ollama model instance using centralized configuration.

    Args:
        model_id: Ollama model identifier
        provider: Provider name (default: "ollama")

    Returns:
        Configured OllamaModel instance

    Raises:
        Exception: If model creation fails
    """
    # Get centralized configuration
    config_manager = _get_config_manager()
    config = config_manager.get_local_model_config(model_id, provider)

    # Select parameter source by model role (primary vs swarm)
    try:
        server_config = config_manager.get_server_config(provider)
        llm_temp = server_config.llm.temperature
        llm_max = server_config.llm.max_tokens
        role = "primary"
        swarm_env = config_manager.getenv("CYBER_AGENT_SWARM_MODEL")
        is_swarm = False
        if swarm_env and model_id and swarm_env == model_id:
            is_swarm = True
        elif (
            server_config.swarm
            and server_config.swarm.llm
            and server_config.swarm.llm.model_id == model_id
            and server_config.swarm.llm.model_id != server_config.llm.model_id
        ):
            is_swarm = True
        if is_swarm:
            llm_temp = server_config.swarm.llm.temperature
            # Use swarm model's max_tokens (calculated by ConfigManager from models.dev)
            # This respects per-model limits - different models have different constraints
            llm_max = server_config.swarm.llm.max_tokens

            # Defensive: Ensure valid max_tokens
            if not isinstance(llm_max, int) or llm_max <= 0:
                logger.warning(
                    "Invalid swarm max_tokens=%s for model %s, falling back to 4096",
                    llm_max,
                    config.get("model_id"),
                )
                llm_max = 4096

            role = "swarm"
    except Exception:
        llm_temp = config.get("temperature", 0.95)
        llm_max = config.get("max_tokens", 4096)
        role = "unknown"

    # Observability: one-liner
    try:
        logger.info(
            "Model build: role=%s provider=ollama model=%s max_tokens=%s",
            role,
            config.get("model_id"),
            llm_max,
        )
    except Exception:
        pass

    return OllamaModel(
        host=config["host"],
        model_id=config["model_id"],
        temperature=llm_temp,
        max_tokens=llm_max,
    )


def create_litellm_model(
    model_id: str,
    region_name: str,
    provider: str = "litellm",
) -> LiteLLMModel:
    """Create LiteLLM model instance for universal provider access.

    Args:
        model_id: LiteLLM model identifier (e.g., "bedrock/...", "openai/...")
        region_name: AWS region (for Bedrock/SageMaker models)
        provider: Provider name (default: "litellm")

    Returns:
        Configured LiteLLMModel instance

    Raises:
        Exception: If model creation fails
    """
    # Get centralized configuration
    config_manager = _get_config_manager()

    # Get standard configuration (LiteLLM doesn't have special thinking mode handling)
    config = config_manager.get_standard_model_config(model_id, region_name, provider)

    # Prepare client args based on model prefix
    client_args: Dict[str, Any] = {}

    # Configure AWS Bedrock models via LiteLLM
    if model_id.startswith(("bedrock/", "sagemaker/")):
        client_args["aws_region_name"] = region_name
        aws_profile = config_manager.getenv("AWS_PROFILE") or config_manager.getenv(
            "AWS_DEFAULT_PROFILE"
        )
        if aws_profile:
            client_args["aws_profile_name"] = aws_profile
        role_arn = config_manager.getenv("AWS_ROLE_ARN")
        if role_arn:
            client_args["aws_role_name"] = role_arn
        session_name = config_manager.getenv("AWS_ROLE_SESSION_NAME")
        if session_name:
            client_args["aws_session_name"] = session_name
        sts_endpoint = config_manager.getenv("AWS_STS_ENDPOINT")
        if sts_endpoint:
            client_args["aws_sts_endpoint"] = sts_endpoint
        external_id = config_manager.getenv("AWS_EXTERNAL_ID")
        if external_id:
            client_args["aws_external_id"] = external_id

    if model_id.startswith("sagemaker/"):
        sagemaker_base_url = config_manager.getenv("SAGEMAKER_BASE_URL")
        if sagemaker_base_url:
            client_args["sagemaker_base_url"] = sagemaker_base_url

    # Build params dict with optional reasoning parameters
    # Select parameter source by model role (primary vs swarm)
    try:
        server_config = config_manager.get_server_config(provider)
        llm_temp = server_config.llm.temperature
        llm_max = server_config.llm.max_tokens
        role = "primary"
        swarm_env = config_manager.getenv("CYBER_AGENT_SWARM_MODEL")
        is_swarm = False
        if swarm_env and model_id and swarm_env == model_id:
            is_swarm = True
        elif (
            server_config.swarm
            and server_config.swarm.llm
            and server_config.swarm.llm.model_id == model_id
            and server_config.swarm.llm.model_id != server_config.llm.model_id
        ):
            is_swarm = True
        if is_swarm:
            llm_temp = server_config.swarm.llm.temperature
            # Use swarm model's max_tokens (calculated by ConfigManager from models.dev)
            # This respects per-model limits - different models have different constraints
            llm_max = server_config.swarm.llm.max_tokens

            # Defensive: Ensure valid max_tokens
            if not isinstance(llm_max, int) or llm_max <= 0:
                logger.warning(
                    "Invalid swarm max_tokens=%s for model %s, falling back to 4096",
                    llm_max,
                    config.get("model_id"),
                )
                llm_max = 4096

            role = "swarm"
    except Exception:
        llm_temp = config.get("temperature", 0.95)
        llm_max = config.get("max_tokens", 4096)
        role = "unknown"

    # LiteLLM best-effort output clamp (no new envs, best-effort only)
    try:
        import litellm  # type: ignore

        base = config.get("model_id") or model_id
        if isinstance(base, str) and "/" in base:
            base = base.split("/", 1)[1]
        model_cap = litellm.get_max_tokens(base)  # may return None for unknown models
        if (
            isinstance(model_cap, (int, float))
            and int(model_cap) > 0
            and llm_max > int(model_cap)
        ):
            logger.info(
                "LiteLLM cap: reducing max_tokens from %s to %s for model=%s",
                llm_max,
                int(model_cap),
                config.get("model_id"),
            )
            llm_max = int(model_cap)
    except Exception:
        pass

    # Observability: one-liner
    try:
        logger.info(
            "Model build: role=%s provider=litellm model=%s max_tokens=%s",
            role,
            config.get("model_id"),
            llm_max,
        )
    except Exception:
        pass

    params: Dict[str, Any] = {
        "temperature": llm_temp,
        "max_tokens": llm_max,
    }

    # Only include top_p if present in config (avoid provider conflicts)
    if "top_p" in config:
        params["top_p"] = config["top_p"]

    # Add request timeout and retries for robustness (env-overridable)
    timeout_secs = config_manager.getenv_int("LITELLM_TIMEOUT", 180)
    num_retries = config_manager.getenv_int("LITELLM_NUM_RETRIES", 3)
    if timeout_secs > 0:
        client_args["timeout"] = timeout_secs
    if num_retries >= 0:
        client_args["num_retries"] = num_retries

    # Reasoning parameters for reasoning-capable models (o1, o3, o4, gpt-5)
    reasoning_effort = config_manager.getenv("REASONING_EFFORT")
    try:
        from modules.config.models.capabilities import get_capabilities

        caps = get_capabilities(provider, config.get("model_id", ""))
        if reasoning_effort and caps.pass_reasoning_effort:
            params["reasoning_effort"] = reasoning_effort
    except Exception:
        # If capability resolution fails, do not attach the param
        pass

    # Reasoning text verbosity for Azure Responses API models (default: medium)
    reasoning_verbosity = config_manager.getenv("REASONING_VERBOSITY", "medium")
    if reasoning_verbosity and "azure/responses/" in config["model_id"]:
        params["text"] = {
            "format": {"type": "text"},
            "verbosity": reasoning_verbosity,
        }
        logger.info(
            "Set reasoning text verbosity=%s for model %s",
            reasoning_verbosity,
            config["model_id"],
        )

    max_completion_tokens = config_manager.getenv_int("MAX_COMPLETION_TOKENS", 0)
    if max_completion_tokens > 0:
        params["max_completion_tokens"] = max_completion_tokens

    _apply_context_window_fallbacks(client_args)

    return LiteLLMModel(
        client_args=client_args,
        model_id=config["model_id"],
        params=params,
    )


def create_anthropic_oauth_model(
    model_id: str,
    provider: str = "anthropic_oauth",
):
    """Create Anthropic OAuth model instance.

    Uses Claude Max unlimited quota via OAuth authentication.
    Bills against Claude Max subscription instead of per-token API usage.

    Args:
        model_id: Anthropic model identifier (e.g., "claude-sonnet-4-20250514")
        provider: Provider name (default: "anthropic_oauth")

    Returns:
        Configured AnthropicOAuthModel instance

    Raises:
        Exception: If model creation fails or OAuth token not found
    """
    from modules.models.anthropic_oauth_model import AnthropicOAuthModel

    # Get centralized configuration
    config_manager = _get_config_manager()

    # Get server config for this provider
    try:
        server_config = config_manager.get_server_config(provider)
        temperature = server_config.llm.temperature
        max_tokens = server_config.llm.max_tokens
    except Exception as e:
        logger.warning(
            "Could not get server config for %s, using defaults: %s",
            provider,
            e
        )
        temperature = 0.95
        max_tokens = 8192

    print_status(f"Using {model_id} with OAuth authentication", Colors.CYAN)

    # Create and return OAuth model
    return AnthropicOAuthModel(
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
    )
