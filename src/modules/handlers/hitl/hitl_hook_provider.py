"""HITL Hook Provider for intercepting tool calls."""

import logging
from typing import Optional

from strands.experimental.hooks.events import BeforeToolInvocationEvent
from strands.hooks import HookProvider, HookRegistry

from .feedback_manager import FeedbackManager

logger = logging.getLogger(__name__)


class HITLHookProvider(HookProvider):
    """Hook provider for HITL tool interception."""

    def __init__(
        self,
        feedback_manager: FeedbackManager,
        auto_pause_on_destructive: bool = True,
        auto_pause_on_low_confidence: bool = True,
        confidence_threshold: float = 70.0,
    ):
        """Initialize HITL hook provider.

        Args:
            feedback_manager: FeedbackManager instance
            auto_pause_on_destructive: Auto-pause before destructive operations
            auto_pause_on_low_confidence: Auto-pause on low confidence
            confidence_threshold: Confidence threshold for auto-pause (0-100)
        """
        self.feedback_manager = feedback_manager
        self.auto_pause_on_destructive = auto_pause_on_destructive
        self.auto_pause_on_low_confidence = auto_pause_on_low_confidence
        self.confidence_threshold = confidence_threshold

        # Track tools that should trigger auto-pause
        self.destructive_patterns = [
            "rm ",
            "delete ",
            "drop ",
            "truncate ",
            "format ",
            "erase ",
        ]

        logger.info(
            "HITLHookProvider initialized (destructive=%s, low_conf=%s, threshold=%.1f)",
            auto_pause_on_destructive,
            auto_pause_on_low_confidence,
            confidence_threshold,
        )

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        """Register hook callbacks.

        Args:
            registry: Hook registry from Strands SDK
            **kwargs: Additional keyword arguments (unused)
        """
        logger.debug("Registering HITL hooks")
        registry.add_callback(BeforeToolInvocationEvent, self._on_before_tool_call)
        logger.info("HITL hooks registered successfully")

    def _on_before_tool_call(self, event: BeforeToolInvocationEvent) -> None:
        """Handle before tool call event.

        Args:
            event: BeforeToolInvocationEvent from Strands SDK
        """
        tool_use = event.tool_use
        tool_name = tool_use.get("name", "unknown")
        tool_id = tool_use.get("toolUseId", tool_use.get("id", "unknown"))
        tool_input = tool_use.get("input", {})

        logger.debug("HITL hook intercepted tool: %s (id=%s)", tool_name, tool_id)

        # Determine if we should pause
        should_pause, reason = self._should_pause_for_tool(tool_name, tool_input)

        if should_pause:
            logger.info(
                "Auto-pause triggered for tool %s (reason=%s)",
                tool_name,
                reason,
            )

            # Request pause through feedback manager
            self.feedback_manager.request_pause(
                tool_name=tool_name,
                tool_id=tool_id,
                parameters=tool_input,
                confidence=None,  # TODO: Extract confidence from event if available
                reason=reason,
            )

            # Block execution until feedback received or timeout
            feedback_received = self.feedback_manager.wait_for_feedback()
            if not feedback_received:
                logger.warning(
                    "Timeout expired waiting for feedback on tool %s - auto-resuming",
                    tool_name
                )

    def _should_pause_for_tool(
        self,
        tool_name: str,
        tool_input: dict,
    ) -> tuple[bool, Optional[str]]:
        """Determine if tool should trigger auto-pause.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters

        Returns:
            Tuple of (should_pause, reason)
        """
        # Check for destructive operations
        if self.auto_pause_on_destructive:
            if self._is_destructive_operation(tool_name, tool_input):
                return True, "destructive_operation"

        # Check for low confidence (if confidence scoring is available)
        if self.auto_pause_on_low_confidence:
            # TODO: Extract confidence from tool invocation metadata
            # For now, we don't have access to model confidence scores
            pass

        return False, None

    def _is_destructive_operation(self, tool_name: str, tool_input: dict) -> bool:
        """Check if operation is potentially destructive.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters

        Returns:
            True if potentially destructive, False otherwise
        """
        # Check shell commands
        if tool_name == "shell":
            command = tool_input.get("command", "")
            if isinstance(command, str):
                command_lower = command.lower()
                for pattern in self.destructive_patterns:
                    if pattern in command_lower:
                        logger.debug(
                            "Destructive pattern '%s' found in command: %s",
                            pattern,
                            command[:50],
                        )
                        return True

        # Check editor operations (file deletions)
        if tool_name == "editor":
            operation = tool_input.get("operation", "")
            if operation in ["delete", "remove"]:
                return True

        return False
