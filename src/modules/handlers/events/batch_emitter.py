"""Event batching for performance optimization."""

import threading
import time
from typing import Any, Dict, List, Optional

from .emitters import EventEmitter


class BatchingEmitter:
    """Batches events to reduce UI re-renders and improve performance.

    Groups events within a time window and emits them as a single batch,
    reducing the number of React re-renders from hundreds to just a few.
    """

    def __init__(
        self,
        base_emitter: EventEmitter,
        batch_ms: int = 50,
        operation_id: Optional[str] = None,
    ):
        """Initialize batching emitter.

        Args:
            base_emitter: Underlying emitter to send batches through
            batch_ms: Milliseconds to batch events (default 50ms)
            operation_id: Operation ID for tracking
        """
        self.base = base_emitter
        self.batch: List[Dict[str, Any]] = []
        self.batch_ms = batch_ms / 1000.0  # Convert to seconds
        self.timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()
        self.operation_id = operation_id or "batch"

    def emit(self, event: Dict[str, Any]) -> None:
        """Add event to batch and schedule flush.

        Args:
            event: Event to batch
        """
        with self.lock:
            # Critical events bypass batching
            if self._is_critical(event):
                self._flush()
                self.base.emit(event)
                return

            self.batch.append(event)

            # Start timer if not running
            if not self.timer or not self.timer.is_alive():
                self.timer = threading.Timer(self.batch_ms, self._flush)
                self.timer.start()

    def _is_critical(self, event: Dict[str, Any]) -> bool:
        """Check if event should bypass batching.

        Critical events like errors or user handoffs should be immediate.

        Args:
            event: Event to check

        Returns:
            True if event should bypass batching
        """
        critical_types = {
            "error",
            "user_handoff",
            "assessment_complete",
            "step_header",
            "report_content",
        }
        return event.get("type") in critical_types

    def _flush(self) -> None:
        """Flush batched events."""
        with self.lock:
            if not self.batch:
                return

            # Single event - emit directly
            if len(self.batch) == 1:
                self.base.emit(self.batch[0])
            else:
                # Multiple events - emit as batch
                self.base.emit(
                    {
                        "type": "batch",
                        "id": f"{self.operation_id}_batch_{int(time.time() * 1000)}",
                        "events": self.batch,
                    }
                )

            self.batch = []
            if self.timer:
                self.timer.cancel()
            self.timer = None

    def flush_immediate(self) -> None:
        """Force immediate flush of pending events."""
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        self._flush()
