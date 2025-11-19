"""Unit tests for HITL (Human-in-the-Loop) feedback system."""

import json
from unittest.mock import Mock

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

        assert feedback_manager.state == HITLState.PAUSED
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

    def test_resume_from_paused(self, feedback_manager):
        """Test resuming execution from paused state."""
        feedback_manager.request_pause(
            tool_name="shell", tool_id="test_123", parameters={"command": "test"}
        )
        assert feedback_manager.state == HITLState.PAUSED

        feedback_manager.resume()

        assert feedback_manager.state == HITLState.ACTIVE
        assert feedback_manager.pending_tool is None
        assert feedback_manager.pending_feedback is None

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

    def test_manual_intervention_command_format(self):
        """Test manual intervention command JSON format."""
        command = {
            "type": "request_pause",
            "is_manual": True,
        }

        command_json = json.dumps(command)
        parsed = json.loads(command_json)

        assert parsed["type"] == "request_pause"
        assert parsed["is_manual"] is True


class TestStateTransitions:
    """Tests for HITL state machine transitions."""

    def test_pause_and_resume_workflow(self, feedback_manager):
        """Test complete pause and resume workflow."""
        assert feedback_manager.state == HITLState.ACTIVE

        # Pause for review
        feedback_manager.request_pause("shell", "test_123", {"command": "test"})
        assert feedback_manager.state == HITLState.PAUSED
        assert feedback_manager.is_paused()

        # Submit feedback (auto-resumes)
        feedback_manager.submit_feedback(
            FeedbackType.CORRECTION, "Use safer command", "test_123"
        )
        assert feedback_manager.state == HITLState.ACTIVE
        assert not feedback_manager.is_paused()

    def test_manual_intervention_workflow(self, feedback_manager):
        """Test user-requested manual intervention."""
        assert feedback_manager.state == HITLState.ACTIVE

        # User requests manual pause
        feedback_manager.request_pause(is_manual=True)
        assert feedback_manager.state == HITLState.PAUSED
        assert feedback_manager.pending_tool is not None
        assert feedback_manager.pending_tool.tool_name == "manual_intervention"

        # User provides guidance (auto-resumes)
        tool_id = feedback_manager.pending_tool.tool_id
        feedback_manager.submit_feedback(
            FeedbackType.SUGGESTION, "Check XYZ before continuing", tool_id
        )
        assert feedback_manager.state == HITLState.ACTIVE
        assert not feedback_manager.is_paused()
