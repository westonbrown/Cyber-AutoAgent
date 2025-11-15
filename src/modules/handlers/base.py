"""
Base classes and constants for the handlers module.

This module contains shared constants, type definitions, and base functionality
used across different handler components.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Environment configuration
# Helper function to detect if running in Docker
def is_docker():
    """Check if running inside a Docker container."""
    return os.path.exists("/.dockerenv") or os.path.exists("/app")


# Use langfuse-web:3000 when in Docker, localhost:3000 otherwise
DEFAULT_LANGFUSE_HOST = (
    "http://langfuse-web:3000" if is_docker() else "http://localhost:3000"
)
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", DEFAULT_LANGFUSE_HOST)
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-placeholder")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-placeholder")

# Display configuration
CONTENT_PREVIEW_LENGTH = 200
MAX_CONTENT_DISPLAY_LENGTH = 500


@dataclass
class HandlerState:
    """State management for handler operations."""

    # Step tracking
    steps: int = 0
    max_steps: int = 100
    step_limit_reached: bool = False

    # Tool tracking
    shown_tools: set = field(default_factory=set)
    tool_use_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    tool_results: Dict[str, Any] = field(default_factory=dict)
    tools_used: List[str] = field(default_factory=list)

    # Display state
    last_was_tool: bool = False
    last_was_reasoning: bool = False
    suppress_parent_handler: bool = False
    suppress_parent_output: bool = False

    # Operation tracking
    operation_id: Optional[str] = None
    report_generated: bool = False
    memory_operations: int = 0
    stop_tool_used: bool = False
    created_tools: List[str] = field(default_factory=list)
    start_time: float = 0.0
    evaluation_triggered: bool = False
    evaluation_thread: Optional[Any] = None

    # Swarm operation tracking
    in_swarm_operation: bool = False
    swarm_agents: List[str] = field(default_factory=list)
    swarm_step_count: int = 0
    current_swarm_agent: Optional[str] = None

    # Tool effectiveness tracking
    tool_effectiveness: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class HandlerError(Exception):
    """Base exception for handler-related errors."""


class StepLimitReached(HandlerError):
    """Raised when the step limit is reached."""
