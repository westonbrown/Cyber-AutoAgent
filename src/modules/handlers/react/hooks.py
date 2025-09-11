"""
SDK Hook Integration for React UI Event Emission.

This module provides a clean integration with the Strands SDK hooks system,
capturing tool lifecycle events and emitting them as structured events for
the React UI and logging infrastructure.
"""

import time
import json
import logging
from typing import Optional, Dict, Any

from strands.hooks import HookProvider, HookRegistry
from strands.experimental.hooks.events import (
    BeforeToolInvocationEvent,
    AfterToolInvocationEvent,
)

from ..events import EventEmitter, get_emitter

logger = logging.getLogger(__name__)


class ReactHooks(HookProvider):
    """
    Hook provider that bridges SDK tool events to the React UI.

    This class captures tool invocation events from the Strands SDK and emits
    them as structured __CYBER_EVENT__ entries that can be displayed in the
    React terminal UI and logged to files.
    """

    def __init__(self, emitter: Optional[EventEmitter] = None, operation_id: Optional[str] = None):
        """
        Initialize the React hooks provider.

        Args:
            emitter: Event emitter for outputting structured events.
                    Defaults to stdout emitter if not provided.
            operation_id: Operation identifier for event correlation.
        """
        self.emitter = emitter or get_emitter(operation_id=operation_id)
        self.tool_start_times: Dict[str, float] = {}

    def register_hooks(self, registry: HookRegistry) -> None:
        """
        Register callbacks for SDK lifecycle events.

        Args:
            registry: The SDK's hook registry for event subscriptions.
        """
        logger.debug("ReactHooks.register_hooks called - registering tool callbacks")
        registry.add_callback(BeforeToolInvocationEvent, self._on_before_tool)
        registry.add_callback(AfterToolInvocationEvent, self._on_after_tool)
        logger.debug("ReactHooks callbacks registered successfully")

    def _on_before_tool(self, event: BeforeToolInvocationEvent) -> None:
        """
        Handle tool invocation start events.

        Emits tool_start and tool_invocation_start events with parsed
        tool arguments for display in the UI.

        Args:
            event: The before tool invocation event from the SDK.
        """
        logger.debug("ReactHooks._on_before_tool called with event: %s", type(event))

        try:
            tool_use = event.tool_use
            tool_name = tool_use.get("name", "unknown")
            tool_id = tool_use.get("toolUseId", tool_use.get("id"))

            # Enhanced logging for swarm debugging
            if tool_name == "swarm":
                logger.debug("=== SWARM TOOL INVOCATION START ===")
                logger.debug(f"Tool use structure: {tool_use}")
            elif tool_name == "handoff_to_agent":
                logger.debug("=== HANDOFF TOOL INVOCATION ===")
                logger.debug(f"Handoff tool use: {tool_use}")

            # Track timing for duration calculation
            if tool_id:
                self.tool_start_times[tool_id] = time.time()

            # Parse tool input safely
            tool_input = self._parse_tool_input(tool_use.get("input", {}))

            # Parse command arrays for shell tool BEFORE emitting tool_start
            # This fixes the [object Object] display issue
            if tool_name == "shell" and "command" in tool_input:
                command = tool_input["command"]
                if isinstance(command, str) and command.strip().startswith("["):
                    try:
                        import json

                        parsed_commands = json.loads(command)
                        if isinstance(parsed_commands, list):
                            tool_input["command"] = parsed_commands
                    except json.JSONDecodeError:
                        pass  # Keep original if parsing fails

            # Emit structured events with already-parsed input
            event_dict = {"type": "tool_start", "tool_name": tool_name, "tool_id": tool_id, "tool_input": tool_input}

            # Log the tool invocation at INFO level for visibility
            logger.info("Tool invocation: %s (id=%s)", tool_name, tool_id)
            logger.debug("Tool input: %s", tool_input)

            # Emit the tool_start event with complete information
            self.emitter.emit(event_dict)

            # Emit tool_invocation_start for backward compatibility
            # This simpler event is used by some UI components
            self.emitter.emit({"type": "tool_invocation_start", "tool_name": tool_name})

            # Still emit tool_input_corrected for compatibility with existing code
            # that might rely on this event
            if tool_name == "shell" and isinstance(tool_input.get("command"), list):
                self.emitter.emit(
                    {
                        "type": "tool_input_corrected",
                        "tool_name": tool_name,
                        "tool_id": tool_id,
                        "tool_input": tool_input,
                    }
                )

        except Exception as e:
            logger.error("Error processing before tool event: %s", e, exc_info=True)

    def _on_after_tool(self, event: AfterToolInvocationEvent) -> None:
        """
        Handle tool invocation completion events.

        Emits tool_end and tool_invocation_end events with results
        and execution metrics.

        Args:
            event: The after tool invocation event from the SDK.
        """
        try:
            tool_use = event.tool_use
            tool_name = tool_use.get("name", "unknown")
            tool_id = tool_use.get("toolUseId", tool_use.get("id"))

            # Enhanced logging for swarm completion
            if tool_name == "swarm":
                logger.debug("=== SWARM TOOL COMPLETION ===")
                logger.debug(f"Tool result type: {type(event.result)}")
                if hasattr(event, "result"):
                    logger.debug(
                        f"Result content: {str(event.result)[:500]}..."
                        if len(str(event.result)) > 500
                        else str(event.result)
                    )
            elif tool_name == "handoff_to_agent":
                logger.debug("=== HANDOFF COMPLETION ===")
                logger.debug(f"Handoff result: {event.result}")

            # Calculate execution duration
            duration = self._calculate_duration(tool_id)

            # Extract and process result
            result = event.result
            success, output = self._process_tool_result(result)

            # Log completion at INFO level
            logger.info("Tool completed: %s (id=%s) in %.2fs", tool_name, tool_id, duration)

            # Extra debug for swarm tool
            if tool_name == "swarm":
                logger.debug(f"Swarm execution took {duration:.2f}s")
                logger.debug(f"Success: {success}, Output length: {len(output)}")
                if output:
                    logger.debug(f"Swarm output preview: {output[:200]}..." if len(output) > 200 else output)

            # Emit thinking_end to stop animations
            self.emitter.emit({"type": "thinking_end", "tool_name": tool_name, "tool_id": tool_id})

            # Emit completion events
            self.emitter.emit(
                {
                    "type": "tool_end",
                    "tool_name": tool_name,
                    "tool_id": tool_id,
                    "success": success,
                    "duration": f"{duration:.2f}s",
                }
            )

            # Don't emit tool_invocation_end here - ReactBridgeHandler handles this
            # This prevents duplicate tool_invocation_end events in the logs
            # ReactHooks focuses on tool lifecycle (tool_start/tool_end with timing)
            # ReactBridgeHandler handles invocation flow (tool_invocation_start/end)

            # Don't emit output here - ReactBridgeHandler will handle tool output
            # This prevents duplicate output events for the same tool result
            # The ReactBridgeHandler processes tool results and emits appropriate output

        except Exception as e:
            logger.error("Error processing after tool event: %s", e, exc_info=True)

    def _parse_tool_input(self, input_data: Any) -> Dict[str, Any]:
        """
        Parse tool input into a structured dictionary.

        Args:
            input_data: Raw input data from tool invocation.

        Returns:
            Parsed tool input as a dictionary.
        """
        if isinstance(input_data, dict):
            return input_data

        if isinstance(input_data, str):
            try:
                return json.loads(input_data)
            except json.JSONDecodeError:
                return {"raw": input_data}

        return {"raw": str(input_data)}

    def _calculate_duration(self, tool_id: Optional[str]) -> float:
        """
        Calculate tool execution duration.

        Args:
            tool_id: Unique identifier for the tool invocation.

        Returns:
            Duration in seconds, or 0 if start time not found.
        """
        if tool_id and tool_id in self.tool_start_times:
            duration = time.time() - self.tool_start_times[tool_id]
            del self.tool_start_times[tool_id]
            return duration
        return 0.0

    def _process_tool_result(self, result: Any) -> tuple[bool, str]:
        """
        Process tool result to extract success status and output text.

        Args:
            result: Raw tool result from SDK.

        Returns:
            Tuple of (success status, output text).
        """
        if not result:
            return True, ""

        if isinstance(result, dict):
            success = result.get("status", "success") == "success"

            # Extract text from content array
            output_parts = []
            content = result.get("content", [])

            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        output_parts.append(item["text"])
            elif isinstance(content, str):
                output_parts.append(content)

            return success, "\n".join(output_parts).strip()

        # Fallback for non-dict results
        return True, str(result).strip()
