#!/usr/bin/env python3
"""Centralized logger factory for component-based logging.

Provides component-based naming for better log readability.

Component Naming Convention:
- Agents.* - Agent implementations
- Tools.* - Tool implementations
- Handlers.* - Event handlers
- Evaluation.* - Evaluation components
- Config.* - Configuration
- Prompts.* - Prompt management

Usage:
    from modules.config.logger_factory import get_logger

    logger = get_logger("Agents.CyberAutoAgent")
    logger.info("Agent started")
"""

import logging
from typing import Dict

_logger_registry: Dict[str, logging.Logger] = {}


def get_logger(component_name: str) -> logging.Logger:
    """Get or create a logger with component-based name.

    Args:
        component_name: Component identifier (e.g., "Agents.CyberAutoAgent")

    Returns:
        Logger instance for the component
    """
    if component_name not in _logger_registry:
        _logger_registry[component_name] = logging.getLogger(component_name)

    return _logger_registry[component_name]


def initialize_logger_factory(
    log_file: str | None = None, verbose: bool = False
) -> None:
    """Initialize logger factory.

    Called by environment.setup_logging() during startup.
    Currently a no-op placeholder that accepts keyword
    arguments for backward compatibility with setup_logging.
    """
    # Reserved for future configuration (e.g., attach handlers).
    # Accept log_file/verbose to avoid TypeError when older call
    # sites pass them through.
    _ = (log_file, verbose)


def reset_logger_factory() -> None:
    """Reset factory state for testing."""
    _logger_registry.clear()
