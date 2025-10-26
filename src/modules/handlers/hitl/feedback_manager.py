"""Feedback manager for HITL workflows."""

import logging
import time
from typing import Any, Dict, Optional

from .hitl_logger import log_hitl
from .types import (
    FeedbackType,
    HITLState,
    ToolInvocation,
    UserFeedback,
)

logger = logging.getLogger(__name__)


class FeedbackManager:
    """Manages HITL feedback state and workflow."""

    def __init__(
        self,
        memory=None,
        operation_id: Optional[str] = None,
        emitter=None,
    ):
        """Initialize feedback manager.

        Args:
            memory: Memory client for storing interventions
            operation_id: Operation identifier
            emitter: Event emitter for UI communication
        """
        self.memory = memory
        self.operation_id = operation_id
        self.emitter = emitter

        # State tracking
        self.state = HITLState.ACTIVE
        self.pending_tool: Optional[ToolInvocation] = None
        self.pending_feedback: Optional[UserFeedback] = None

        # Feedback queue for tools awaiting approval
        self.feedback_queue: Dict[str, UserFeedback] = {}

        logger.info("FeedbackManager initialized for operation %s", operation_id)

    def request_pause(
        self,
        tool_name: str,
        tool_id: str,
        parameters: Dict[str, Any],
        confidence: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Request pause for tool review.

        Args:
            tool_name: Name of the tool to review
            tool_id: Unique tool invocation ID
            parameters: Tool parameters
            confidence: Confidence score (0-100)
            reason: Reason for pause (e.g., "destructive_operation")
        """
        logger.info(
            "Pause requested for tool %s (id=%s, reason=%s)",
            tool_name,
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

        # Emit pause event to UI
        if self.emitter:
            self.emitter.emit(
                {
                    "type": "hitl_pause_requested",
                    "tool_name": tool_name,
                    "tool_id": tool_id,
                    "parameters": parameters,
                    "confidence": confidence,
                    "reason": reason,
                }
            )

    def request_manual_pause(self) -> None:
        """Request manual intervention pause initiated by user.

        Creates a synthetic tool invocation for user-requested intervention.
        """
        timestamp = int(time.time() * 1000)
        tool_id = f"manual_{timestamp}"

        logger.info("Manual intervention requested by user (id=%s)", tool_id)

        self.state = HITLState.PAUSED
        self.pending_tool = ToolInvocation(
            tool_name="manual_intervention",
            tool_id=tool_id,
            parameters={},
            confidence=None,
            reason="User requested manual intervention",
        )

        # Emit pause event to UI
        if self.emitter:
            self.emitter.emit(
                {
                    "type": "hitl_pause_requested",
                    "tool_name": "manual_intervention",
                    "tool_id": tool_id,
                    "parameters": {},
                    "confidence": None,
                    "reason": "User requested manual intervention",
                }
            )

    def submit_feedback(
        self,
        feedback_type: FeedbackType,
        content: str,
        tool_id: str,
    ) -> None:
        """Submit user feedback for pending tool.

        Args:
            feedback_type: Type of feedback
            content: Feedback content
            tool_id: Tool invocation ID
        """
        log_hitl(
            "FeedbackMgr",
            "submit_feedback() called",
            "INFO",
            feedback_type=feedback_type.value,
            content_length=len(content),
            tool_id=tool_id,
        )

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

        log_hitl(
            "FeedbackMgr",
            f"Created UserFeedback object at timestamp={feedback.timestamp}",
            "DEBUG",
        )

        old_state = self.state
        self.pending_feedback = feedback
        self.feedback_queue[tool_id] = feedback

        log_hitl(
            "FeedbackMgr",
            f"✓ Feedback stored in state - pending_feedback={'SET' if self.pending_feedback else 'None'}",
            "INFO",
            queue_size=len(self.feedback_queue),
        )

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

        # State remains PAUSED until explicitly resumed
        log_hitl(
            "FeedbackMgr",
            f"Feedback stored - state remains: {self.state.name}",
            "INFO",
        )

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
        log_hitl("FeedbackMgr", "Resuming execution", "INFO")
        logger.info("[HITL-FM] Resuming execution from paused state")
        self.state = HITLState.ACTIVE
        self.pending_tool = None
        self.pending_feedback = None

    def get_pending_feedback_message(self) -> Optional[str]:
        """Get pending feedback formatted as agent message.

        Returns:
            Formatted message if feedback pending, None otherwise
        """
        log_hitl("FeedbackMgr", "get_pending_feedback_message() called", "INFO")

        if not self.pending_feedback:
            logger.debug("[HITL-FM] No pending feedback to retrieve")
            log_hitl(
                "FeedbackMgr", "No pending feedback found - returning None", "INFO"
            )
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

        log_hitl(
            "FeedbackMgr",
            f"✓ Formatted feedback message: {len(message)} chars",
            "INFO",
            feedback_type=feedback.feedback_type.value,
            message_preview=message[:100],
        )

        return message

    def clear_pending_feedback(self) -> None:
        """Clear pending feedback after it has been injected into agent context."""
        log_hitl("FeedbackMgr", "clear_pending_feedback() called", "INFO")

        if self.pending_feedback:
            feedback_info = f"type={self.pending_feedback.feedback_type.value}, tool_id={self.pending_feedback.tool_id}"
            logger.info(
                "[HITL-FM] Clearing pending feedback after injection (type=%s, tool_id=%s)",
                self.pending_feedback.feedback_type.value,
                self.pending_feedback.tool_id,
            )
            self.pending_feedback = None
            log_hitl(
                "FeedbackMgr",
                f"✓ Cleared pending feedback: {feedback_info}",
                "INFO",
            )
        else:
            logger.warning(
                "[HITL-FM] clear_pending_feedback called but no feedback was pending"
            )
            log_hitl("FeedbackMgr", "WARNING: No feedback to clear", "WARNING")

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
