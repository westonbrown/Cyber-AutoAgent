#!/usr/bin/env python3
"""
Environment variable reader with caching and type conversion.

This module provides a centralized interface for reading environment variables
with support for type conversion, defaults, and cache invalidation detection.
"""

import hashlib
import json
import os

from modules.config.system.logger import get_logger

logger = get_logger("Config.EnvReader")


class EnvironmentReader:
    """Centralized environment variable access with caching and validation.

    Provides type-safe environment variable reads with:
    - Automatic type conversion (str, int, float, bool)
    - Default value handling
    - Change detection for cache invalidation
    - Consistent error handling and logging
    """

    def __init__(self):
        """Initialize environment reader with current snapshot."""
        self._env_snapshot = self._capture_env_snapshot()

    def _capture_env_snapshot(self) -> int:
        """Capture hash of current environment state for cache invalidation.

        Returns:
            Hash of current environment variables as integer
        """
        # Create a stable hash of all environment variables
        env_data = json.dumps(dict(sorted(os.environ.items())), sort_keys=True)
        return int(hashlib.md5(env_data.encode()).hexdigest(), 16)

    def has_changed(self) -> bool:
        """Check if environment variables have changed since last snapshot.

        Returns:
            True if environment has changed, False otherwise
        """
        current_snapshot = self._capture_env_snapshot()
        if current_snapshot != self._env_snapshot:
            self._env_snapshot = current_snapshot
            return True
        return False

    def get(self, key: str, default: str = "") -> str:
        """Get environment variable value as string.

        Centralized accessor for all environment variable reads.
        Provides consistent interface and enables cache invalidation.

        Args:
            key: Environment variable name
            default: Default value if variable not set

        Returns:
            Environment variable value or default
        """
        return os.getenv(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get environment variable as boolean.

        Interprets common boolean representations:
        - True: "true", "1", "yes" (case-insensitive)
        - False: anything else or unset

        Args:
            key: Environment variable name
            default: Default value if variable not set

        Returns:
            Boolean value or default
        """
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes")

    def get_int(self, key: str, default: int = 0) -> int:
        """Get environment variable as integer.

        Handles conversion errors gracefully with logging.
        Supports float strings (e.g., "123.45" → 123).

        Args:
            key: Environment variable name
            default: Default value if variable not set or invalid

        Returns:
            Integer value or default if conversion fails
        """
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            logger.warning(
                "Invalid integer value for %s: %s, using default %d",
                key,
                value,
                default,
            )
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get environment variable as float.

        Handles conversion errors gracefully with logging.

        Args:
            key: Environment variable name
            default: Default value if variable not set or invalid

        Returns:
            Float value or default if conversion fails
        """
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(
                "Invalid float value for %s: %s, using default %f", key, value, default
            )
            return default
