"""Event emitters for different transport mechanisms."""

import hashlib
import json
import os
from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional, Protocol


class EventEmitter(Protocol):
    """Protocol for event emitters - minimal interface."""

    def emit(self, event: Dict[str, Any]) -> None:
        """Emit an event to the configured transport."""
        ...


class StdoutEventEmitter:
    """Emits events to stdout using the existing __CYBER_EVENT__ protocol.

    This maintains 100% backward compatibility with the React UI while
    adding intelligent deduplication to prevent duplicate events.
    """

    def __init__(self, operation_id: Optional[str] = None):
        """Initialize emitter with deduplication tracking.

        Args:
            operation_id: Operation ID for event ID generation
        """
        self.operation_id = operation_id or "default"
        self._event_counter = 0
        # Keep last 100 event signatures for deduplication
        self._recent_signatures = deque(maxlen=100)
        # Track the last output content to prevent exact duplicates
        self._last_output_content = None
        self._last_output_time = None
        # Cache UI mode to avoid repeated os.getenv calls
        self._ui_mode = os.getenv("CYBER_UI_MODE", "react").lower()

    def emit(self, event: Dict[str, Any]) -> None:
        """Emit event with deduplication and ID tracking.

        Args:
            event: Event dictionary to emit
        """
        # Generate event ID if not present (React mode only needs this)
        if self._ui_mode == "react" and "id" not in event:
            event["id"] = f"{self.operation_id}_{self._event_counter}"
            self._event_counter += 1

        # Add timestamp if not present (React mode only needs this)
        if self._ui_mode == "react" and "timestamp" not in event:
            event["timestamp"] = datetime.now().isoformat()

        # Special handling for output events - prevent exact duplicates within 100ms window
        if event.get("type") == "output":
            content = event.get("content", "")
            current_time = datetime.now()

            # Check if this is an exact duplicate within a short time window
            if (
                self._last_output_content == content
                and self._last_output_time
                and (current_time - self._last_output_time).total_seconds() < 0.1
            ):
                return  # Skip duplicate output within 100ms

            self._last_output_content = content
            self._last_output_time = current_time

        # Skip duplicate events based on signature
        # Tool events and metrics updates should not be deduplicated
        event_type = event.get("type", "")
        if event_type not in (
            "tool_start",
            "tool_end",
            "tool_invocation_start",
            "tool_invocation_end",
            "metrics_update",
        ):
            # Create signature for deduplication (only when needed)
            signature = self._create_signature(event)
            if signature in self._recent_signatures:
                return  # Skip duplicate emission
        else:
            signature = None

        # Emit the event in the appropriate format
        if self._ui_mode == "react":
            # React mode: emit structured JSON events
            try:
                # Ensure output content is stringified to avoid "[object Object]" in UI
                if event.get("type") == "output":
                    content = event.get("content")
                    if not isinstance(content, str):
                        try:
                            if isinstance(content, (dict, list)):
                                event["content"] = json.dumps(content, ensure_ascii=False)
                            else:
                                event["content"] = str(content)
                        except Exception:
                            event["content"] = str(content)

                # Use ensure_ascii=True to properly escape control characters
                # This ensures that newlines in shell commands are properly escaped
                json_str = json.dumps(event, ensure_ascii=True)
            except (TypeError, ValueError) as e:
                # If JSON serialization fails, try to clean up the event data
                try:
                    cleaned_event = self._clean_event_for_json(event)
                    json_str = json.dumps(cleaned_event, ensure_ascii=True)
                except Exception:
                    # Last resort: emit a simple error event
                    error_event = {
                        "type": "error",
                        "error": f"Failed to serialize event: {str(e)}",
                        "event_type": event.get("type", "unknown"),
                        "id": event.get("id", "unknown"),
                        "timestamp": event.get("timestamp", datetime.now().isoformat()),
                    }
                    json_str = json.dumps(error_event, ensure_ascii=True)

            print(f"__CYBER_EVENT__{json_str}__CYBER_EVENT_END__\n", end="", flush=True)
        else:
            # CLI mode: emit human-readable formatted output
            self._emit_cli_format(event)

        # Track for deduplication (except tool events and metrics updates)
        if signature is not None:
            self._recent_signatures.append(signature)

    def _clean_event_for_json(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Clean event data to ensure JSON serialization succeeds.

        Recursively processes the event dictionary to handle problematic
        data types that json.dumps cannot serialize.

        Args:
            event: Event dictionary that may contain problematic data

        Returns:
            Cleaned event dictionary safe for JSON serialization
        """

        def clean_value(value):
            """Recursively clean values for JSON serialization."""
            if value is None:
                return None
            elif isinstance(value, (str, int, float, bool)):
                return value
            elif isinstance(value, dict):
                return {k: clean_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [clean_value(item) for item in value]
            elif isinstance(value, tuple):
                return list(value)  # Convert tuples to lists
            elif hasattr(value, "__dict__"):
                # Try to convert objects to dict
                return clean_value(value.__dict__)
            else:
                # Last resort: convert to string
                return str(value)

        # Create a deep copy to avoid modifying the original
        return clean_value(event)

    def _emit_cli_format(self, event: Dict[str, Any]) -> None:
        """Emit event in human-readable CLI format.

        Args:
            event: Event dictionary to format and print
        """
        event_type = event.get("type", "")
        content = event.get("content", "")

        # Skip internal/state management events that don't need CLI display
        # These are either handled elsewhere or are pure state transitions
        if event_type in ("metrics_update", "tool_input_update", "thinking_end",
                          "tool_invocation_start", "tool_invocation_end"):
            return

        # Operation initialization - show key details
        if event_type == "operation_init":
            print("\n" + "─" * 80, flush=True)
            print("◆ Operation initialization complete", flush=True)
            if event.get("operation_id"):
                print(f"  Operation ID: {event['operation_id']}", flush=True)
            if event.get("target"):
                print(f"  Target: {event['target']}", flush=True)
            if event.get("objective"):
                # Truncate long objectives
                obj = str(event['objective'])
                if len(obj) > 100:
                    obj = obj[:97] + "..."
                print(f"  Objective: {obj}", flush=True)
            print("─" * 80 + "\n", flush=True)

        # Step headers - show progress
        elif event_type == "step_header":
            step = event.get("step", "?")
            max_steps = event.get("maxSteps", "?")
            duration = event.get("duration", "")
            duration_str = f" ({duration})" if duration else ""
            print(f"\n[Step {step}/{max_steps}]{duration_str}", flush=True)

        # Print reasoning/thinking content
        elif event_type == "reasoning":
            if content:
                print(f"\n💭 {content}\n", flush=True)

        # Print tool execution info
        elif event_type == "tool_start":
            tool_name = event.get("tool_name", "unknown")
            print(f"\n⚡ Executing: {tool_name}", flush=True)

        elif event_type == "tool_end":
            tool_name = event.get("tool_name", "unknown")
            success = event.get("success", True)
            status = "✅" if success else "❌"
            print(f"{status} Completed: {tool_name}\n", flush=True)

        # Print output content
        elif event_type == "output":
            if content:
                print(content, flush=True)

        # Print errors
        elif event_type == "error":
            print(f"❌ Error: {content}", flush=True)

    def _create_signature(self, event: Dict[str, Any]) -> str:
        """Create a signature for event deduplication.

        Excludes timestamp, id, and other volatile fields.

        Args:
            event: Event to create signature for

        Returns:
            Signature string for comparison
        """
        event_type = event.get("type", "")

        # Tool events and metrics updates should have unique signatures to avoid deduplication
        if event_type in ("tool_start", "tool_end", "tool_invocation_start", "tool_invocation_end", "metrics_update"):
            # Include timestamp to make each event unique
            return f"{event_type}_{event.get('tool_name', '')}_{event.get('timestamp', datetime.now().isoformat())}"

        # Create a copy without volatile fields for other events
        sig_dict = {k: v for k, v in event.items() if k not in ("timestamp", "id", "duration", "metrics")}

        # Special handling for output events - include content for dedup
        if event_type == "output":
            # Normalize output content for comparison
            content = sig_dict.get("content", "")
            if isinstance(content, str):
                # Strip whitespace variations but preserve content
                content = content.strip()
            sig_dict["content"] = content

            # Use a hash of the content for more efficient comparison
            if content:
                content_hash = hashlib.md5(content.encode()).hexdigest()
                return f"output_{content_hash}"

        # Create stable signature
        return json.dumps(sig_dict, sort_keys=True)


def get_emitter(transport: str = None, operation_id: Optional[str] = None) -> EventEmitter:
    """Factory function to get the appropriate emitter.

    Args:
        transport: Type of transport ('stdout', 'websocket', etc.)
                  Defaults to environment variable EVENT_TRANSPORT or 'stdout'
        operation_id: Operation ID for event tracking

    Returns:
        EventEmitter instance
    """
    if transport is None:
        transport = os.environ.get("EVENT_TRANSPORT", "stdout")

    if transport == "stdout":
        return StdoutEventEmitter(operation_id=operation_id)
    # Future: elif transport == "websocket": return WebSocketEventEmitter(operation_id)
    else:
        # Default to stdout for unknown transports
        return StdoutEventEmitter(operation_id=operation_id)
