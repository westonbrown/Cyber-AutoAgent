"""
Core handler functionality.

This module contains the base handler classes, utilities, and the main
reasoning handler for agent callback processing.
"""

from .base import HandlerError, HandlerState, StepLimitReached
from .callback import ReasoningHandler
from .utils import (
    Colors,
    CyberEvent,
    create_output_directory,
    emit_event,
    emit_status,
    get_output_path,
    print_banner,
    print_section,
    print_status,
    sanitize_target_name,
    validate_output_path,
)

__all__ = [
    # Base classes
    "HandlerState",
    "HandlerError",
    "StepLimitReached",
    # Main handler
    "ReasoningHandler",
    # Utilities
    "Colors",
    "get_output_path",
    "sanitize_target_name",
    "validate_output_path",
    "create_output_directory",
    "print_banner",
    "print_section",
    "print_status",
    "emit_event",
    "emit_status",
    "CyberEvent",
]
