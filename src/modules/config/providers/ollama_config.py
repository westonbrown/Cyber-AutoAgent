#!/usr/bin/env python3
"""
Ollama provider configuration helpers.

This module provides configuration utilities specific to Ollama local models,
including host detection and connectivity checks.
"""

import os

import requests

from modules.config.system.env_reader import EnvironmentReader
from modules.config.system.logger import get_logger

logger = get_logger("Config.OllamaProvider")


def get_ollama_host(env_reader: EnvironmentReader) -> str:
    """Determine appropriate Ollama host based on environment.

    Tries the following in order:
    1. OLLAMA_HOST environment variable
    2. If in Docker (/app exists), try localhost and host.docker.internal
    3. Default to localhost for native execution

    Args:
        env_reader: Environment variable reader

    Returns:
        Ollama host URL (e.g., "http://localhost:11434")
    """
    env_host = env_reader.get("OLLAMA_HOST")
    if env_host:
        return env_host

    # Check if running in Docker
    if os.path.exists("/app"):
        candidates = ["http://localhost:11434", "http://host.docker.internal:11434"]
        for host in candidates:
            try:
                response = requests.get(f"{host}/api/version", timeout=2)
                if response.status_code == 200:
                    logger.debug("Found Ollama at %s", host)
                    return host
            except (requests.exceptions.RequestException, ConnectionError):
                pass
        # Fallback to host.docker.internal if no connection works
        logger.debug(
            "No Ollama connection found, falling back to host.docker.internal"
        )
        return "http://host.docker.internal:11434"
    # Native execution - use localhost
    return "http://localhost:11434"
