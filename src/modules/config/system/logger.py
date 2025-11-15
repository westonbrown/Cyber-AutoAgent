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


def configure_sdk_logging(enable_debug: bool = False) -> None:
    """Configure logging for Strands SDK components.

    Suppresses benign tool registry warnings and optionally enables verbose SDK logging.

    Args:
        enable_debug: If True, enable verbose logging for SDK components
    """
    # Suppress unrecognized tool specification warnings from Strands toolkit registry
    # These are benign warnings from the Strands SDK when built-in tools (stop, http_request, python_repl)
    # are processed during tool registration. The tools work correctly despite the warnings.
    class ToolRegistryWarningFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            # Suppress only the specific "unrecognized tool specification" warning
            if "unrecognized tool specification" in record.getMessage():
                return False
            return True

    # Only enable verbose logging when explicitly requested
    log_level = logging.INFO
    logging.getLogger("strands").setLevel(log_level)
    logging.getLogger("strands.multiagent").setLevel(log_level)
    logging.getLogger("strands.multiagent.swarm").setLevel(log_level)
    logging.getLogger("strands.tools").setLevel(log_level)
    logging.getLogger("strands.tools.registry").setLevel(log_level)
    logging.getLogger("strands.event_loop").setLevel(log_level)
    logging.getLogger("strands_tools").setLevel(log_level)
    logging.getLogger("strands_tools.swarm").setLevel(log_level)

    # Also set our own modules to INFO level
    logging.getLogger("modules.handlers").setLevel(log_level)
    logging.getLogger("modules.handlers.react").setLevel(log_level)

    logger = get_logger("Config.SDK")
    logger.info("SDK verbose logging enabled")


def reset_logger_factory() -> None:
    """Reset factory state for testing."""
    _logger_registry.clear()
