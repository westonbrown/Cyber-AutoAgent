"""
React Bridge Hook Provider for SDK event integration.

This module provides hooks that integrate with the Strands SDK to emit
lifecycle events for the React UI, complementing the main callback handler.
"""

import time
from typing import Optional, Callable, Dict, Any

from strands.hooks import HookProvider, HookRegistry
from strands.experimental.hooks.events import (
    BeforeToolInvocationEvent,
    AfterToolInvocationEvent,
    BeforeModelInvocationEvent,
    AfterModelInvocationEvent,
)


class ReactBridgeHook(HookProvider):
    """
    SDK Hook provider that bridges SDK events to the React UI.

    This hook provider captures SDK lifecycle events and emits them as
    structured events for the React UI to display. It works alongside
    the main callback handler to provide comprehensive event coverage.
    """

    def __init__(self, emit_func: Optional[Callable] = None, handler=None):
        """
        Initialize the React bridge hook.

        Args:
            emit_func: Optional custom emit function
            handler: Reference to main handler for delegating events
        """
        self.emit_func = emit_func or self._default_emit
        self.start_times: Dict[str, float] = {}
        self.handler = handler  # Reference to main handler to prevent duplication

    def _default_emit(self, event: Dict[str, Any]) -> None:
        """
        Default event emission that delegates to the main handler.

        This prevents duplicate events by routing through the main handler's
        event emission system rather than emitting directly.
        """
        if self.handler and hasattr(self.handler, "_emit_ui_event"):
            self.handler._emit_ui_event(event)
        # If no handler reference, do nothing to prevent duplication

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register lifecycle hooks with the SDK."""
        # Tool invocation lifecycle
        registry.add_callback(BeforeToolInvocationEvent, self.on_before_tool)
        registry.add_callback(AfterToolInvocationEvent, self.on_after_tool)

        # Model invocation lifecycle
        registry.add_callback(BeforeModelInvocationEvent, self.on_before_model)
        registry.add_callback(AfterModelInvocationEvent, self.on_after_model)

    def on_before_tool(self, event: BeforeToolInvocationEvent) -> None:
        """
        Handle pre-tool invocation events.

        Tracks tool start times and emits lifecycle events for monitoring
        tool execution duration and state.
        """
        if event.tool_use:
            # Extract tool ID with fallbacks
            tool_id = (
                getattr(event.tool_use, "toolUseId", None)
                or getattr(event.tool_use, "id", None)
                or str(id(event.tool_use))
            )
            self.start_times[tool_id] = time.time()

            # Extract tool information
            tool_name = getattr(event.tool_use, "name", "unknown")

            # Emit lifecycle event (not content - that's handled by callback)
            lifecycle_event = {
                "type": "tool_lifecycle",
                "event": "before_invocation",
                "tool_name": tool_name,
                "tool_id": tool_id,
                "metadata": {
                    "invocation_state": str(event.invocation_state) if hasattr(event, "invocation_state") else "unknown"
                },
            }
            self.emit_func(lifecycle_event)

    def on_after_tool(self, event: AfterToolInvocationEvent) -> None:
        """
        Handle post-tool invocation events.

        Calculates execution duration and emits completion events with
        success/failure status.
        """
        if event.tool_use:
            # Extract tool ID with fallbacks
            tool_id = (
                getattr(event.tool_use, "toolUseId", None)
                or getattr(event.tool_use, "id", None)
                or str(id(event.tool_use))
            )
            tool_name = getattr(event.tool_use, "name", "unknown")

            # Calculate execution duration
            duration = None
            if tool_id in self.start_times:
                duration = time.time() - self.start_times[tool_id]
                del self.start_times[tool_id]

            # Emit lifecycle completion event
            lifecycle_event = {
                "type": "tool_lifecycle",
                "event": "after_invocation",
                "tool_name": tool_name,
                "tool_id": tool_id,
                "duration": duration,
                "success": event.exception is None if hasattr(event, "exception") else True,
                "metadata": {
                    "has_result": event.result is not None if hasattr(event, "result") else False,
                    "exception": str(event.exception) if hasattr(event, "exception") and event.exception else None,
                },
            }
            self.emit_func(lifecycle_event)

    def on_before_model(self, event: BeforeModelInvocationEvent) -> None:
        """
        Handle pre-model invocation events.

        Tracks when the model starts processing for timing and monitoring.
        """
        lifecycle_event = {
            "type": "model_lifecycle",
            "event": "before_invocation",
            "metadata": {"agent_id": str(id(event.agent)) if hasattr(event, "agent") and event.agent else "unknown"},
        }
        self.emit_func(lifecycle_event)

    def on_after_model(self, event: AfterModelInvocationEvent) -> None:
        """
        Handle post-model invocation events.

        Captures model completion status and any stop reasons.
        """
        lifecycle_event = {
            "type": "model_lifecycle",
            "event": "after_invocation",
            "success": event.exception is None if hasattr(event, "exception") else True,
            "metadata": {
                "stop_reason": (
                    event.stop_response.stop_reason
                    if hasattr(event, "stop_response")
                    and event.stop_response
                    and hasattr(event.stop_response, "stop_reason")
                    else None
                ),
                "exception": str(event.exception) if hasattr(event, "exception") and event.exception else None,
            },
        }
        self.emit_func(lifecycle_event)
