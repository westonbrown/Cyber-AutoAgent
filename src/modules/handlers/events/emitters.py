"""Event emitters for different transport mechanisms."""

import json
import os
from typing import Dict, Any, Protocol, Set, Optional
from datetime import datetime
from collections import deque


class EventEmitter(Protocol):
    """Protocol for event emitters - minimal interface."""
    
    def emit(self, event: Dict[str, Any]) -> None:
        """Emit an event to the configured transport."""
        ...


class StdoutEventEmitter:
    """Emits events to stdout using the existing __CYBER_EVENT__ protocol.
    
    This maintains 100% backward compatibility with the React UI while
    adding deduplication at the source to prevent duplicate events.
    """
    
    def __init__(self, operation_id: Optional[str] = None):
        """Initialize emitter with deduplication tracking.
        
        Args:
            operation_id: Operation ID for event ID generation
        """
        self.operation_id = operation_id or "default"
        self._event_counter = 0
        self._emitted_ids: Set[str] = set()
        # Keep last 100 event signatures for deduplication
        self._recent_signatures = deque(maxlen=100)
        
    def emit(self, event: Dict[str, Any]) -> None:
        """Emit event with deduplication and ID tracking.
        
        Args:
            event: Event dictionary to emit
        """
        # Generate event ID if not present
        if "id" not in event:
            event["id"] = f"{self.operation_id}_{self._event_counter}"
            self._event_counter += 1
        
        # Create signature for deduplication (excluding timestamp and ID)
        signature = self._create_signature(event)
        
        # Skip duplicate events
        if signature in self._recent_signatures:
            return  # Silent skip - prevents duplicate emission
            
        # Add timestamp if not present
        if "timestamp" not in event:
            event["timestamp"] = datetime.now().isoformat()
        
        # Emit the event
        print(f"__CYBER_EVENT__{json.dumps(event)}__CYBER_EVENT_END__", flush=True)
        
        # Track for deduplication
        self._recent_signatures.append(signature)
        
    def _create_signature(self, event: Dict[str, Any]) -> str:
        """Create a signature for event deduplication.
        
        Excludes timestamp, id, and other volatile fields.
        
        Args:
            event: Event to create signature for
            
        Returns:
            Signature string for comparison
        """
        event_type = event.get("type", "")
        if event_type in ("tool_start", "tool_end", "tool_invocation_start", "tool_invocation_end", "metrics_update"):
            return f"{event_type}_{event.get('tool_name', '')}_{datetime.now().isoformat()}_{self._event_counter}"
        
        # Create a copy without volatile fields
        sig_dict = {k: v for k, v in event.items() 
                   if k not in ("timestamp", "id", "duration", "metrics")}
        
        # Special handling for output events - include content for dedup
        if event.get("type") == "output":
            # Normalize output content for comparison
            content = sig_dict.get("content", "")
            if isinstance(content, str):
                # Strip whitespace variations
                content = content.strip()
            sig_dict["content"] = content
            
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