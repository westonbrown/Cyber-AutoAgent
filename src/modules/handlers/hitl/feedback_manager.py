"""Feedback manager for HITL workflows."""

import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from .types import (
    FeedbackType,
    HITLState,
    ToolInvocation,
    UserFeedback,
)

if TYPE_CHECKING:
    # Import only during type checking to avoid circular dependencies at runtime
    # This pattern allows type hints without creating import cycles
    from modules.config.manager import HITLConfig

logger = logging.getLogger(__name__)


class FeedbackManager:
    """Manages HITL feedback state and workflow."""

    def __init__(
        self,
        memory=None,
        operation_id: Optional[str] = None,
        emitter=None,
        hitl_config: Optional["HITLConfig"] = None,
    ):
        """Initialize feedback manager.

        Args:
            memory: Memory client for storing interventions
            operation_id: Operation identifier
            emitter: Event emitter for UI communication
            hitl_config: HITL configuration with timeout settings
        """
        self.memory = memory
        self.operation_id = operation_id
        self.emitter = emitter

        # Store timeout configuration for pause mechanism
        if hitl_config:
            self.manual_pause_timeout = hitl_config.manual_pause_timeout
            self.auto_pause_timeout = hitl_config.auto_pause_timeout
        else:
            # Default timeouts if no config provided
            self.manual_pause_timeout = 120
            self.auto_pause_timeout = 30

        # State tracking
        self.state = HITLState.ACTIVE
        self.pending_tool: Optional[ToolInvocation] = None
        self.pending_feedback: Optional[UserFeedback] = None

        # Pause mechanism using threading.Event for blocking coordination
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start in non-paused state (event is set)
        self._is_manual_pause = False  # Track if current pause is manual vs auto

        # Feedback queue for tools awaiting approval
        self.feedback_queue: Dict[str, UserFeedback] = {}

        logger.info("FeedbackManager initialized for operation %s", operation_id)

    def request_pause(
        self,
        tool_name: Optional[str] = None,
        tool_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
        reason: Optional[str] = None,
        is_manual: bool = False,
    ) -> None:
        """Request execution pause (auto or manual).

        Args:
            tool_name: Name of tool to review (auto-generated for manual pause)
            tool_id: Unique tool invocation ID (auto-generated for manual pause)
            parameters: Tool parameters (empty dict for manual pause)
            confidence: Confidence score 0-100 (None for manual pause)
            reason: Reason for pause
            is_manual: True for user-triggered pause, False for auto-pause
        """
        # Generate synthetic data for manual pauses
        if is_manual:
            tool_name = tool_name or "manual_intervention"
            tool_id = tool_id or f"manual_{int(time.time() * 1000)}"
            parameters = parameters or {}
            reason = reason or "User requested manual intervention"

        log_msg = "manual pause" if is_manual else f"auto-pause for {tool_name}"
        logger.info(
            "Pause requested: %s (id=%s, reason=%s)",
            log_msg,
            tool_id,
            reason,
        )

        self.state = HITLState.PAUSED
        self.pending_tool = ToolInvocation(
            tool_name=tool_name,
            tool_id=tool_id,
            parameters=parameters,
            confidence=confidence,
            reason=reason,
        )

        # Block execution by clearing the event
        self._is_manual_pause = is_manual
        self._pause_event.clear()

        # Emit pause event to UI
        if self.emitter:
            # Include timeout for UI display
            timeout_seconds = (
                self.manual_pause_timeout if is_manual else self.auto_pause_timeout
            )

            self.emitter.emit(
                {
                    "type": "hitl_pause_requested",
                    "tool_name": tool_name,
                    "tool_id": tool_id,
                    "parameters": parameters,
                    "confidence": confidence,
                    "reason": reason,
                    "is_manual": is_manual,
                    "timeout_seconds": timeout_seconds,
                }
            )

    def wait_for_feedback(self) -> bool:
        """Block execution until feedback is received or timeout expires.

        Uses appropriate timeout based on pause type (manual vs auto).
        Returns True if feedback received, False if timeout.
        """
        if self.state != HITLState.PAUSED:
            # Not paused, no need to wait
            return True

        # Use appropriate timeout based on pause type
        timeout = (
            self.manual_pause_timeout
            if self._is_manual_pause
            else self.auto_pause_timeout
        )
        pause_type = "manual" if self._is_manual_pause else "auto"

        logger.info(
            "[HITL-FM] Blocking execution - waiting for feedback (%s pause, timeout=%ds)",
            pause_type,
            timeout,
        )

        # Block until event is set (feedback received) or timeout expires
        feedback_received = self._pause_event.wait(timeout=timeout)

        if feedback_received:
            logger.info("[HITL-FM] Feedback received, execution resuming")
            return True
        else:
            logger.warning(
                "[HITL-FM] Timeout expired after %ds, auto-resuming execution", timeout
            )
            # Auto-resume on timeout
            self.resume()
            return False

    def submit_feedback(
        self,
        feedback_type: FeedbackType,
        content: str,
        tool_id: str,
    ) -> None:
        """Submit user feedback and auto-resume execution.

        Feedback submission indicates user intent to continue.
        Execution resumes immediately after storing feedback.

        Args:
            feedback_type: Type of feedback
            content: Feedback content
            tool_id: Tool invocation ID
        """
        logger.info(
            "[HITL-FM] Feedback submitted for tool %s: type=%s, operation=%s",
            tool_id,
            feedback_type.value,
            self.operation_id,
        )
        logger.info(
            "[HITL-FM] Feedback content (length=%d):\n%s",
            len(content),
            content[:200] + "..." if len(content) > 200 else content,
        )

        feedback = UserFeedback(
            feedback_type=feedback_type,
            content=content,
            tool_id=tool_id,
            timestamp=time.time(),
        )
        self.pending_feedback = feedback
        self.feedback_queue[tool_id] = feedback

        logger.debug(
            "[HITL-FM] Feedback stored - pending_feedback=%s, queue_size=%d",
            self.pending_feedback is not None,
            len(self.feedback_queue),
        )

        # Emit feedback event to backend
        if self.emitter:
            self.emitter.emit(
                {
                    "type": "hitl_feedback_submitted",
                    "feedback_type": feedback_type.value,
                    "content": content,
                    "tool_id": tool_id,
                    "timestamp": feedback.timestamp,
                }
            )

        # Store intervention in memory
        if self.memory:
            self._store_intervention(feedback)

        # Auto-resume execution (user intent to continue)
        # Note: Don't clear pending_feedback yet - injection hook needs it
        self._pause_event.set()
        self.state = HITLState.ACTIVE
        self._is_manual_pause = False
        logger.info("[HITL-FM] Execution auto-resumed after feedback submission")

    def get_pending_feedback(self, tool_id: str) -> Optional[UserFeedback]:
        """Get pending feedback for tool.

        Args:
            tool_id: Tool invocation ID

        Returns:
            UserFeedback if exists, None otherwise
        """
        return self.feedback_queue.get(tool_id)

    def is_paused(self) -> bool:
        """Check if currently paused."""
        return self.state == HITLState.PAUSED

    def resume(self) -> None:
        """Resume execution from paused state."""
        logger.info("[HITL-FM] Resuming execution from paused state")
        self.state = HITLState.ACTIVE
        self.pending_tool = None
        self.pending_feedback = None

        # Signal the pause event to unblock wait_for_feedback()
        self._pause_event.set()
        self._is_manual_pause = False

    def get_pending_feedback_message(self) -> Optional[str]:
        """Get pending feedback formatted as agent message.

        Returns:
            Formatted message if feedback pending, None otherwise
        """
        if not self.pending_feedback:
            logger.debug("[HITL-FM] No pending feedback to retrieve")
            return None

        feedback = self.pending_feedback

        message = f"""HUMAN FEEDBACK RECEIVED:

Type: {feedback.feedback_type.value}
Content: {feedback.content}

Please incorporate this feedback and adjust your approach accordingly. Continue the security assessment with this guidance in mind."""

        logger.info(
            "[HITL-FM] Formatted pending feedback into message (type=%s, length=%d)",
            feedback.feedback_type.value,
            len(message),
        )
        logger.debug("[HITL-FM] Formatted message preview:\n%s", message[:300])

        return message

    def clear_pending_feedback(self) -> None:
        """Clear pending feedback after it has been injected into agent context."""
        if self.pending_feedback:
            logger.info(
                "[HITL-FM] Clearing pending feedback after injection (type=%s, tool_id=%s)",
                self.pending_feedback.feedback_type.value,
                self.pending_feedback.tool_id,
            )
            self.pending_feedback = None
        else:
            logger.warning(
                "[HITL-FM] clear_pending_feedback called but no feedback was pending"
            )

    def _store_intervention(self, feedback: UserFeedback) -> None:
        """Store intervention in memory and logs.

        Args:
            feedback: User feedback to store
        """
        try:
            if self.memory and self.pending_tool:
                intervention_data = {
                    "category": "hitl_intervention",
                    "tool_name": self.pending_tool.tool_name,
                    "tool_id": feedback.tool_id,
                    "feedback_type": feedback.feedback_type.value,
                    "feedback_content": feedback.content,
                    "original_parameters": self.pending_tool.parameters,
                    "timestamp": feedback.timestamp,
                }

                # Store in Mem0
                if hasattr(self.memory, "add"):
                    self.memory.add(
                        str(intervention_data),
                        user_id="cyber_agent",
                        metadata=intervention_data,
                    )

                logger.info(
                    "Intervention stored in memory for tool %s", feedback.tool_id
                )

        except Exception as e:
            logger.warning("Failed to store intervention in memory: %s", e)
