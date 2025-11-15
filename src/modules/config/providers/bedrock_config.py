#!/usr/bin/env python3
"""
AWS Bedrock provider configuration helpers.

This module provides configuration utilities specific to AWS Bedrock models,
including region resolution and credential handling.
"""

from modules.config.system.env_reader import EnvironmentReader
from modules.config.system.logger import get_logger

logger = get_logger("Config.BedrockProvider")


def get_default_region(env_reader: EnvironmentReader) -> str:
    """Get the default AWS region with environment override support.

    Args:
        env_reader: Environment variable reader

    Returns:
        AWS region string (defaults to "us-east-1")
    """
    return env_reader.get("AWS_REGION", "us-east-1")
