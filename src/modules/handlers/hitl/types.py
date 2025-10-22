"""Type definitions for HITL system."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class HITLState(Enum):
    """HITL workflow states."""

    ACTIVE = "active"
    PAUSE_REQUESTED = "pause_requested"
    AWAITING_FEEDBACK = "awaiting_feedback"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    REJECTED = "rejected"


class FeedbackType(Enum):
    """Types of user feedback."""

    CORRECTION = "correction"  # Modify tool parameters
    SUGGESTION = "suggestion"  # Propose alternative approach
    APPROVAL = "approval"  # Approve as-is
    REJECTION = "rejection"  # Reject and abort


@dataclass
class ToolInvocation:
    """Tool invocation details for HITL review."""

    tool_name: str
    tool_id: str
    parameters: Dict[str, Any]
    confidence: Optional[float] = None
    reason: Optional[str] = None


@dataclass
class UserFeedback:
    """User feedback on tool invocation."""

    feedback_type: FeedbackType
    content: str
    tool_id: str
    timestamp: float


@dataclass
class AgentInterpretation:
    """Agent's interpretation of user feedback."""

    tool_id: str
    interpretation: str
    modified_parameters: Dict[str, Any]
    awaiting_approval: bool = True
