"""
React UI integration handlers.

This module contains handlers and utilities for integrating with the React
terminal UI, including event emission, tool handling, and SDK hooks.
"""

from .hooks import ReactHooks

# Output interception is provided by unified handler in modules.handlers.output_interceptor
from modules.handlers.output_interceptor import (
    OutputInterceptor,
    intercept_output,
    setup_output_interception,
)
from .react_bridge_handler import ReactBridgeHandler
from .tool_emitters import ToolEventEmitter

__all__ = [
    "ReactBridgeHandler",
    "ReactHooks",
    "ToolEventEmitter",
    "OutputInterceptor",
    "intercept_output",
    "setup_output_interception",
]
