"""Feedback manager for HITL workflows."""

import logging
import time
from typing import Any, Dict, Optional

from .types import (
    AgentInterpretation,
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
        self.pending_interpretation: Optional[AgentInterpretation] = None

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

        self.state = HITLState.PAUSE_REQUESTED
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

        self.state = HITLState.AWAITING_FEEDBACK

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
        logger.info(
            "Feedback submitted for tool %s: type=%s",
            tool_id,
            feedback_type.value,
        )

        feedback = UserFeedback(
            feedback_type=feedback_type,
            content=content,
            tool_id=tool_id,
            timestamp=time.time(),
        )

        self.pending_feedback = feedback
        self.feedback_queue[tool_id] = feedback

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

        self.state = HITLState.AWAITING_CONFIRMATION

    def set_agent_interpretation(
        self,
        tool_id: str,
        interpretation: str,
        modified_parameters: Dict[str, Any],
    ) -> None:
        """Set agent's interpretation of feedback.

        Args:
            tool_id: Tool invocation ID
            interpretation: Agent's interpretation text
            modified_parameters: Modified tool parameters
        """
        logger.info("Agent interpretation set for tool %s", tool_id)

        self.pending_interpretation = AgentInterpretation(
            tool_id=tool_id,
            interpretation=interpretation,
            modified_parameters=modified_parameters,
            awaiting_approval=True,
        )

        # Emit interpretation event to UI
        if self.emitter:
            self.emitter.emit(
                {
                    "type": "hitl_agent_interpretation",
                    "tool_id": tool_id,
                    "interpretation": interpretation,
                    "modified_parameters": modified_parameters,
                    "awaiting_approval": True,
                }
            )

    def confirm_interpretation(self, approved: bool, tool_id: str) -> None:
        """Confirm or reject agent interpretation.

        Args:
            approved: Whether interpretation is approved
            tool_id: Tool invocation ID
        """
        logger.info(
            "Interpretation %s for tool %s",
            "approved" if approved else "rejected",
            tool_id,
        )

        if approved:
            self.state = HITLState.ACTIVE
        else:
            self.state = HITLState.REJECTED

        # Emit resume or rejection event
        if self.emitter:
            if approved and self.pending_interpretation:
                self.emitter.emit(
                    {
                        "type": "hitl_resume",
                        "tool_id": tool_id,
                        "modified_parameters": self.pending_interpretation.modified_parameters,
                        "approved": True,
                    }
                )
            else:
                self.emitter.emit(
                    {
                        "type": "hitl_resume",
                        "tool_id": tool_id,
                        "approved": False,
                    }
                )

        # Clear pending state
        if approved:
            self.pending_tool = None
            self.pending_feedback = None
            self.pending_interpretation = None

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
        return self.state in (
            HITLState.PAUSE_REQUESTED,
            HITLState.AWAITING_FEEDBACK,
            HITLState.AWAITING_CONFIRMATION,
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
