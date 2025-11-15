#!/usr/bin/env python3
"""
Provider validation logic for configuration management.

This module validates requirements for different providers (Bedrock, Ollama, LiteLLM)
including credentials, connectivity, and model availability.
"""

import os

import boto3
import ollama
import requests

from modules.config.system.env_reader import EnvironmentReader
from modules.config.system.logger import get_logger

logger = get_logger("Config.Validation")


def validate_provider(
    provider: str,
    env_reader: EnvironmentReader,
    ollama_host: str = None,
    region: str = None,
    server_config=None,
) -> None:
    """Validate that all requirements are met for the specified provider.

    Args:
        provider: Provider name ("bedrock", "ollama", or "litellm")
        env_reader: Environment variable reader
        ollama_host: Ollama server host (for Ollama validation)
        region: AWS region (for Bedrock validation)
        server_config: Server configuration (for Ollama model checks)

    Raises:
        ValueError: If provider is unsupported
        ConnectionError: If provider services are not accessible
        EnvironmentError: If required credentials or configuration missing
    """
    logger.debug("Validating requirements for provider: %s", provider)
    if provider == "ollama":
        validate_ollama_requirements(env_reader, ollama_host, server_config)
    elif provider == "bedrock":
        validate_aws_requirements(env_reader, region)
    elif provider == "litellm":
        validate_litellm_requirements(env_reader)
    else:
        raise ValueError(f"Unsupported provider type: {provider}")


def validate_ollama_requirements(
    env_reader: EnvironmentReader, ollama_host: str = None, server_config=None
) -> None:
    """Validate Ollama requirements.

    Checks:
    - Ollama server is accessible
    - At least one model is available
    - Required models (if server_config provided) are available

    Args:
        env_reader: Environment variable reader
        ollama_host: Ollama server host URL
        server_config: Optional server configuration with required models

    Raises:
        ConnectionError: If Ollama server is not accessible
        ValueError: If no models are available or required models missing
    """
    if not ollama_host:
        raise ValueError("ollama_host is required for Ollama validation")

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

        # If server_config provided, check required models
        if server_config:
            required_models = [
                server_config.llm.model_id,
                server_config.embedding.model_id,
            ]

            # Require at least one required model to be available
            has_required = any(
                any(req in model for model in available_models) for req in required_models
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


def validate_bedrock_model_access(region: str) -> None:
    """Validate AWS Bedrock model access and availability.

    Performs basic validation of AWS region configuration.
    Model access validation is handled by the strands-agents framework.

    Args:
        region: AWS region

    Raises:
        EnvironmentError: If AWS region is not configured
    """
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


def validate_aws_requirements(env_reader: EnvironmentReader, region: str = None) -> None:
    """Validate AWS requirements including Bedrock model access.

    Supports either standard AWS credentials (ACCESS_KEY/SECRET or PROFILE)
    or Bedrock bearer token via AWS_BEARER_TOKEN_BEDROCK without mutating
    credential environment variables.

    Args:
        env_reader: Environment variable reader
        region: AWS region for validation

    Raises:
        EnvironmentError: If required credentials are not configured or region not set
    """
    # Check region first
    if not region:
        raise EnvironmentError(
            "AWS region not configured. Set AWS_REGION environment variable or configure default region."
        )

    bearer_token = env_reader.get("AWS_BEARER_TOKEN_BEDROCK")
    access_key = env_reader.get("AWS_ACCESS_KEY_ID")
    profile = env_reader.get("AWS_PROFILE")

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
    if region:
        validate_bedrock_model_access(region)


def validate_litellm_requirements(env_reader: EnvironmentReader, model_id: str = "") -> None:
    """Validate LiteLLM requirements based on model provider prefix.

    LiteLLM handles most validation internally:
    - max_tokens: Auto-capped to model limits via get_modified_max_tokens()
    - temperature: Validated by provider (e.g., reasoning models require 1.0)
    - Model limits: Maintained in model_prices_and_context_window.json

    This validation only checks that required API credentials are configured.

    Args:
        env_reader: Environment variable reader
        model_id: LiteLLM model ID (e.g., "bedrock/...", "openai/...")

    Raises:
        EnvironmentError: If required credentials for the model's provider are missing
    """
    if not model_id:
        logger.debug("No model_id provided to LiteLLM validation, skipping")
        return

    logger.info("Validating LiteLLM configuration for model: %s", model_id)

    # Check provider-specific requirements based on model prefix
    if model_id.startswith("bedrock/"):
        # LiteLLM does NOT support AWS bearer tokens - only standard credentials
        if not (env_reader.get("AWS_ACCESS_KEY_ID") or env_reader.get("AWS_PROFILE")):
            raise EnvironmentError(
                "AWS credentials not configured for LiteLLM Bedrock models.\n"
                "Required: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY OR AWS_PROFILE\n"
                "Note: LiteLLM does not support AWS_BEARER_TOKEN_BEDROCK"
            )

    elif model_id.startswith("openai/"):
        if not env_reader.get("OPENAI_API_KEY"):
            raise EnvironmentError(
                "OPENAI_API_KEY not configured for LiteLLM OpenAI models. "
                "Set OPENAI_API_KEY environment variable."
            )
    elif model_id.startswith("anthropic/"):
        if not env_reader.get("ANTHROPIC_API_KEY"):
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not configured for LiteLLM Anthropic models. "
                "Set ANTHROPIC_API_KEY environment variable."
            )
    elif model_id.startswith("cohere/"):
        if not env_reader.get("COHERE_API_KEY"):
            raise EnvironmentError(
                "COHERE_API_KEY not configured for LiteLLM Cohere models. "
                "Set COHERE_API_KEY environment variable."
            )
    elif model_id.startswith("azure/"):
        if not env_reader.get("AZURE_API_KEY"):
            raise EnvironmentError(
                "AZURE_API_KEY not configured for LiteLLM Azure models. "
                "Set AZURE_API_KEY, AZURE_API_BASE, and AZURE_API_VERSION environment variables."
            )
    elif model_id.startswith("gemini/"):
        if not env_reader.get("GEMINI_API_KEY"):
            raise EnvironmentError(
                "GEMINI_API_KEY not configured for LiteLLM Gemini models. "
                "Set GEMINI_API_KEY environment variable."
            )
    elif model_id.startswith("sagemaker/"):
        has_std_creds = env_reader.get("AWS_ACCESS_KEY_ID") and env_reader.get(
            "AWS_SECRET_ACCESS_KEY"
        )
        if not (has_std_creds or env_reader.get("AWS_PROFILE")):
            raise EnvironmentError(
                "AWS credentials not configured for LiteLLM SageMaker models.\n"
                "Required: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY OR AWS_PROFILE"
            )
        if not (env_reader.get("AWS_REGION") or env_reader.get("AWS_REGION_NAME")):
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
