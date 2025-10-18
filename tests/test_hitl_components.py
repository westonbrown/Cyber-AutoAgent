"""Unit tests for HITL (Human-in-the-Loop) feedback system."""

import json
from unittest.mock import Mock, patch

import pytest

from modules.handlers.hitl.feedback_manager import FeedbackManager
from modules.handlers.hitl.hitl_hook_provider import HITLHookProvider
from modules.handlers.hitl.types import FeedbackType, HITLState


@pytest.fixture
def mock_emitter():
    """Mock event emitter."""
    emitter = Mock()
    emitter.emit = Mock()
    return emitter


@pytest.fixture
def mock_memory():
    """Mock memory client."""
    memory = Mock()
    memory.add = Mock()
    return memory


@pytest.fixture
def feedback_manager(mock_memory, mock_emitter):
    """Create FeedbackManager instance."""
    return FeedbackManager(
        memory=mock_memory, operation_id="test_op", emitter=mock_emitter
    )


@pytest.fixture
def hitl_hook(feedback_manager):
    """Create HITLHookProvider instance."""
    return HITLHookProvider(
        feedback_manager=feedback_manager,
        auto_pause_on_destructive=True,
        auto_pause_on_low_confidence=True,
        confidence_threshold=70.0,
    )


class TestFeedbackManager:
    """Tests for FeedbackManager."""

    def test_initialization(self, feedback_manager):
        """Test FeedbackManager initializes with correct state."""
        assert feedback_manager.state == HITLState.ACTIVE
        assert feedback_manager.pending_tool is None
        assert len(feedback_manager.feedback_queue) == 0

    def test_request_pause(self, feedback_manager, mock_emitter):
        """Test pause request changes state and emits event."""
        feedback_manager.request_pause(
            tool_name="shell",
            tool_id="test_123",
            parameters={"command": "rm -rf /"},
            confidence=50.0,
            reason="destructive_operation",
        )

        assert feedback_manager.state == HITLState.AWAITING_FEEDBACK
        assert feedback_manager.pending_tool is not None
        assert feedback_manager.pending_tool.tool_name == "shell"
        assert mock_emitter.emit.called

    def test_submit_feedback(self, feedback_manager, mock_memory):
        """Test feedback submission stores in queue and memory."""
        feedback_manager.request_pause(
            tool_name="shell", tool_id="test_123", parameters={"command": "test"}
        )

        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.CORRECTION,
            content="Use safer command",
            tool_id="test_123",
        )

        assert "test_123" in feedback_manager.feedback_queue
        assert mock_memory.add.called

    def test_confirm_interpretation_approved(self, feedback_manager, mock_emitter):
        """Test interpretation approval resumes execution."""
        feedback_manager.request_pause(
            tool_name="shell", tool_id="test_123", parameters={"command": "test"}
        )
        feedback_manager.submit_feedback(
            FeedbackType.CORRECTION, "Modified command", "test_123"
        )
        feedback_manager.set_agent_interpretation(
            tool_id="test_123",
            interpretation="Will use modified command",
            modified_parameters={"command": "safe_test"},
        )

        feedback_manager.confirm_interpretation(approved=True, tool_id="test_123")

        assert feedback_manager.state == HITLState.ACTIVE
        assert feedback_manager.pending_tool is None

    def test_confirm_interpretation_rejected(self, feedback_manager):
        """Test interpretation rejection sets REJECTED state."""
        feedback_manager.request_pause(
            tool_name="shell", tool_id="test_123", parameters={"command": "test"}
        )
        feedback_manager.submit_feedback(
            FeedbackType.CORRECTION, "Modified command", "test_123"
        )
        feedback_manager.set_agent_interpretation(
            tool_id="test_123",
            interpretation="Will use modified command",
            modified_parameters={"command": "safe_test"},
        )

        feedback_manager.confirm_interpretation(approved=False, tool_id="test_123")

        assert feedback_manager.state == HITLState.REJECTED

    def test_get_pending_feedback(self, feedback_manager):
        """Test retrieving pending feedback."""
        feedback_manager.request_pause(
            tool_name="shell", tool_id="test_123", parameters={"command": "test"}
        )
        feedback_manager.submit_feedback(
            FeedbackType.CORRECTION, "Modified command", "test_123"
        )

        feedback = feedback_manager.get_pending_feedback("test_123")
        assert feedback is not None
        assert feedback.feedback_type == FeedbackType.CORRECTION
        assert feedback.content == "Modified command"


class TestHITLHookProvider:
    """Tests for HITLHookProvider."""

    def test_destructive_operation_detection_rm(self, hitl_hook):
        """Test detection of rm command."""
        is_destructive = hitl_hook._is_destructive_operation(
            "shell", {"command": "rm -rf /data"}
        )
        assert is_destructive is True

    def test_destructive_operation_detection_delete(self, hitl_hook):
        """Test detection of delete command."""
        is_destructive = hitl_hook._is_destructive_operation(
            "shell", {"command": "DELETE FROM users"}
        )
        assert is_destructive is True

    def test_non_destructive_operation(self, hitl_hook):
        """Test non-destructive command not flagged."""
        is_destructive = hitl_hook._is_destructive_operation(
            "shell", {"command": "ls -la"}
        )
        assert is_destructive is False

    def test_destructive_operation_editor_tool(self, hitl_hook):
        """Test destructive patterns in editor tool."""
        is_destructive = hitl_hook._is_destructive_operation(
            "editor", {"operation": "delete", "path": "/etc/passwd"}
        )
        assert is_destructive is True

    def test_should_pause_for_destructive_tool(self, hitl_hook):
        """Test auto-pause triggers for destructive operations."""
        should_pause, reason = hitl_hook._should_pause_for_tool(
            "shell", {"command": "rm -rf /data"}
        )
        assert should_pause is True
        assert reason == "destructive_operation"

    def test_should_not_pause_for_safe_tool(self, hitl_hook):
        """Test auto-pause does not trigger for safe operations."""
        should_pause, reason = hitl_hook._should_pause_for_tool(
            "shell", {"command": "ls -la"}
        )
        assert should_pause is False
        assert reason is None

    def test_auto_pause_disabled(self, feedback_manager):
        """Test auto-pause can be disabled."""
        hook = HITLHookProvider(
            feedback_manager=feedback_manager,
            auto_pause_on_destructive=False,
            auto_pause_on_low_confidence=False,
        )

        should_pause, reason = hook._should_pause_for_tool(
            "shell", {"command": "rm -rf /"}
        )
        assert should_pause is False
        assert reason is None


class TestFeedbackCommandParsing:
    """Tests for feedback command parsing."""

    def test_submit_feedback_command_format(self):
        """Test feedback command JSON format."""
        command = {
            "type": "submit_feedback",
            "feedback_type": "correction",
            "content": "Use safer approach",
            "tool_id": "test_123",
        }

        command_json = json.dumps(command)
        parsed = json.loads(command_json)

        assert parsed["type"] == "submit_feedback"
        assert parsed["feedback_type"] == "correction"
        assert parsed["tool_id"] == "test_123"

    def test_confirm_interpretation_command_format(self):
        """Test interpretation confirmation JSON format."""
        command = {
            "type": "confirm_interpretation",
            "approved": True,
            "tool_id": "test_123",
        }

        command_json = json.dumps(command)
        parsed = json.loads(command_json)

        assert parsed["type"] == "confirm_interpretation"
        assert parsed["approved"] is True


class TestStateTransitions:
    """Tests for HITL state machine transitions."""

    def test_full_approval_workflow(self, feedback_manager):
        """Test complete approval workflow."""
        assert feedback_manager.state == HITLState.ACTIVE

        feedback_manager.request_pause("shell", "test_123", {"command": "test"})
        assert feedback_manager.state == HITLState.AWAITING_FEEDBACK

        feedback_manager.submit_feedback(FeedbackType.APPROVAL, "Approved", "test_123")
        feedback_manager.set_agent_interpretation(
            "test_123", "Proceeding", {"command": "test"}
        )
        assert feedback_manager.state == HITLState.AWAITING_CONFIRMATION

        feedback_manager.confirm_interpretation(True, "test_123")
        assert feedback_manager.state == HITLState.ACTIVE

    def test_rejection_workflow(self, feedback_manager):
        """Test rejection workflow sets REJECTED state."""
        feedback_manager.request_pause("shell", "test_123", {"command": "test"})
        feedback_manager.submit_feedback(FeedbackType.REJECTION, "Rejected", "test_123")
        feedback_manager.set_agent_interpretation("test_123", "Modified", {})

        feedback_manager.confirm_interpretation(False, "test_123")
        assert feedback_manager.state == HITLState.REJECTED
