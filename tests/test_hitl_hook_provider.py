"""Comprehensive unit tests for HITLHookProvider hook registration and invocation.

This test suite verifies that the HITLHookProvider correctly:
1. Registers hook callbacks with the HookRegistry
2. Intercepts tool invocation events
3. Intercepts model invocation events for manual pause detection
4. Triggers auto-pause for destructive operations
5. Integrates with FeedbackManager for pause/resume workflow
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from strands.hooks import (
    BeforeToolCallEvent,
    BeforeModelCallEvent,
    HookRegistry,
)

from modules.handlers.hitl.feedback_manager import FeedbackManager
from modules.handlers.hitl.hitl_hook_provider import HITLHookProvider
from modules.handlers.hitl.types import HITLState


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
        memory=mock_memory,
        operation_id="test_hook_op",
        emitter=mock_emitter,
    )


@pytest.fixture
def hitl_hook_provider(feedback_manager):
    """Create HITLHookProvider instance with default settings."""
    return HITLHookProvider(
        feedback_manager=feedback_manager,
        auto_pause_on_destructive=True,
        auto_pause_on_low_confidence=True,
        confidence_threshold=70.0,
    )


@pytest.fixture
def mock_hook_registry():
    """Create mock HookRegistry."""
    registry = Mock(spec=HookRegistry)
    registry.add_callback = Mock()
    return registry


@pytest.fixture
def mock_tool_event():
    """Create mock BeforeToolCallEvent."""
    event = Mock(spec=BeforeToolCallEvent)
    event.tool_use = {
        "name": "test_tool",
        "toolUseId": "tool_123",
        "input": {"test_param": "value"},
    }
    return event


@pytest.fixture
def mock_model_event():
    """Create mock BeforeModelCallEvent."""
    event = Mock(spec=BeforeModelCallEvent)
    return event


class TestHookRegistration:
    """Tests for hook registration with HookRegistry."""

    def test_register_hooks_calls_add_callback(
        self, hitl_hook_provider, mock_hook_registry
    ):
        """Test that register_hooks calls add_callback for both event types."""
        hitl_hook_provider.register_hooks(mock_hook_registry)

        # Verify add_callback was called twice (tool and model events)
        assert mock_hook_registry.add_callback.call_count == 2

    def test_register_hooks_for_tool_invocation(
        self, hitl_hook_provider, mock_hook_registry
    ):
        """Test that BeforeToolCallEvent callback is registered."""
        hitl_hook_provider.register_hooks(mock_hook_registry)

        # Check for BeforeToolCallEvent registration
        calls = mock_hook_registry.add_callback.call_args_list
        tool_event_registered = any(
            BeforeToolCallEvent in call[0] for call in calls
        )
        assert tool_event_registered

    def test_register_hooks_for_model_invocation(
        self, hitl_hook_provider, mock_hook_registry
    ):
        """Test that BeforeModelCallEvent callback is registered."""
        hitl_hook_provider.register_hooks(mock_hook_registry)

        # Check for BeforeModelCallEvent registration
        calls = mock_hook_registry.add_callback.call_args_list
        model_event_registered = any(
            BeforeModelCallEvent in call[0] for call in calls
        )
        assert model_event_registered

    def test_register_hooks_correct_callbacks(
        self, hitl_hook_provider, mock_hook_registry
    ):
        """Test that correct callback methods are registered."""
        hitl_hook_provider.register_hooks(mock_hook_registry)

        # Verify the correct methods are registered
        calls = mock_hook_registry.add_callback.call_args_list

        # Find tool invocation callback
        tool_callback = None
        model_callback = None
        for call_args in calls:
            if call_args[0][0] == BeforeToolCallEvent:
                tool_callback = call_args[0][1]
            elif call_args[0][0] == BeforeModelCallEvent:
                model_callback = call_args[0][1]

        assert tool_callback == hitl_hook_provider._on_before_tool_call
        assert model_callback == hitl_hook_provider._check_manual_pause


class TestToolInvocationInterception:
    """Tests for _on_before_tool_call event handling."""

    def test_on_before_tool_call_extracts_tool_info(
        self, hitl_hook_provider, mock_tool_event, feedback_manager
    ):
        """Test that tool information is correctly extracted from event."""
        # Mock wait_for_feedback to avoid blocking
        feedback_manager.wait_for_feedback = Mock(return_value=True)

        # Trigger hook
        hitl_hook_provider._on_before_tool_call(mock_tool_event)

        # Verify tool info was processed (would cause pause if destructive)
        # For non-destructive tool, should not trigger pause
        assert feedback_manager.state == HITLState.ACTIVE

    def test_on_before_tool_call_triggers_pause_for_destructive(
        self, hitl_hook_provider, feedback_manager
    ):
        """Test that destructive operations trigger auto-pause."""
        # Create event with destructive command
        event = Mock(spec=BeforeToolCallEvent)
        event.tool_use = {
            "name": "shell",
            "toolUseId": "shell_123",
            "input": {"command": "rm -rf /data"},
        }

        # Mock wait_for_feedback to avoid blocking
        feedback_manager.wait_for_feedback = Mock(return_value=True)

        # Trigger hook
        hitl_hook_provider._on_before_tool_call(event)

        # Verify pause was requested
        assert feedback_manager.state == HITLState.PAUSED
        assert feedback_manager.pending_tool is not None
        assert feedback_manager.pending_tool.tool_name == "shell"
        assert feedback_manager.pending_tool.reason == "destructive_operation"

    def test_on_before_tool_call_does_not_pause_safe_operation(
        self, hitl_hook_provider, feedback_manager
    ):
        """Test that safe operations do not trigger pause."""
        # Create event with safe command
        event = Mock(spec=BeforeToolCallEvent)
        event.tool_use = {
            "name": "shell",
            "toolUseId": "shell_456",
            "input": {"command": "ls -la"},
        }

        # Trigger hook
        hitl_hook_provider._on_before_tool_call(event)

        # Verify no pause was requested
        assert feedback_manager.state == HITLState.ACTIVE
        assert feedback_manager.pending_tool is None

    def test_on_before_tool_call_waits_for_feedback(
        self, hitl_hook_provider, feedback_manager
    ):
        """Test that hook blocks and waits for feedback when pause triggered."""
        # Create destructive event
        event = Mock(spec=BeforeToolCallEvent)
        event.tool_use = {
            "name": "shell",
            "toolUseId": "shell_789",
            "input": {"command": "delete important_file.txt"},
        }

        # Mock wait_for_feedback
        feedback_manager.wait_for_feedback = Mock(return_value=True)

        # Trigger hook
        hitl_hook_provider._on_before_tool_call(event)

        # Verify wait_for_feedback was called
        feedback_manager.wait_for_feedback.assert_called_once()

    def test_on_before_tool_call_handles_timeout(
        self, hitl_hook_provider, feedback_manager
    ):
        """Test that hook handles timeout when feedback not received."""
        # Create destructive event
        event = Mock(spec=BeforeToolCallEvent)
        event.tool_use = {
            "name": "editor",
            "toolUseId": "editor_001",
            "input": {"operation": "delete", "path": "/etc/config"},
        }

        # Mock wait_for_feedback to simulate timeout
        feedback_manager.wait_for_feedback = Mock(return_value=False)

        # Trigger hook (should not raise exception)
        hitl_hook_provider._on_before_tool_call(event)

        # Verify wait_for_feedback was called
        feedback_manager.wait_for_feedback.assert_called_once()


class TestModelInvocationInterception:
    """Tests for _check_manual_pause event handling."""

    def test_check_manual_pause_no_pause(
        self, hitl_hook_provider, mock_model_event, feedback_manager
    ):
        """Test that hook does nothing when not paused."""
        # Ensure not paused
        feedback_manager.state = HITLState.ACTIVE

        # Trigger hook (should return immediately)
        hitl_hook_provider._check_manual_pause(mock_model_event)

        # No action should be taken
        assert feedback_manager.state == HITLState.ACTIVE

    def test_check_manual_pause_detects_pause(
        self, hitl_hook_provider, mock_model_event, feedback_manager
    ):
        """Test that hook detects manual pause and blocks."""
        # Set paused state
        feedback_manager.request_pause(is_manual=True)

        # Mock wait_for_feedback to avoid actual blocking
        feedback_manager.wait_for_feedback = Mock(return_value=True)

        # Trigger hook
        hitl_hook_provider._check_manual_pause(mock_model_event)

        # Verify wait_for_feedback was called
        feedback_manager.wait_for_feedback.assert_called_once()

    def test_check_manual_pause_resumes_after_feedback(
        self, hitl_hook_provider, mock_model_event, feedback_manager
    ):
        """Test that execution resumes after feedback received."""
        # Set paused state
        feedback_manager.request_pause(is_manual=True)

        # Mock wait_for_feedback to simulate feedback received
        feedback_manager.wait_for_feedback = Mock(return_value=True)

        # Trigger hook
        hitl_hook_provider._check_manual_pause(mock_model_event)

        # State should be updated by wait_for_feedback
        feedback_manager.wait_for_feedback.assert_called_once()

    def test_check_manual_pause_handles_timeout(
        self, hitl_hook_provider, mock_model_event, feedback_manager
    ):
        """Test that hook handles timeout during manual pause."""
        # Set paused state
        feedback_manager.request_pause(is_manual=True)

        # Mock wait_for_feedback to simulate timeout
        feedback_manager.wait_for_feedback = Mock(return_value=False)

        # Trigger hook (should not raise exception)
        hitl_hook_provider._check_manual_pause(mock_model_event)

        # Verify wait_for_feedback was called
        feedback_manager.wait_for_feedback.assert_called_once()


class TestDestructiveOperationDetection:
    """Tests for _is_destructive_operation method."""

    def test_detects_rm_command(self, hitl_hook_provider):
        """Test detection of rm command."""
        is_destructive = hitl_hook_provider._is_destructive_operation(
            "shell", {"command": "rm -rf /tmp/data"}
        )
        assert is_destructive is True

    def test_detects_delete_command(self, hitl_hook_provider):
        """Test detection of delete command."""
        is_destructive = hitl_hook_provider._is_destructive_operation(
            "shell", {"command": "DELETE FROM users WHERE id=1"}
        )
        assert is_destructive is True

    def test_detects_drop_command(self, hitl_hook_provider):
        """Test detection of drop command."""
        is_destructive = hitl_hook_provider._is_destructive_operation(
            "shell", {"command": "DROP TABLE sensitive_data"}
        )
        assert is_destructive is True

    def test_detects_truncate_command(self, hitl_hook_provider):
        """Test detection of truncate command."""
        is_destructive = hitl_hook_provider._is_destructive_operation(
            "shell", {"command": "TRUNCATE TABLE logs"}
        )
        assert is_destructive is True

    def test_detects_format_command(self, hitl_hook_provider):
        """Test detection of format command."""
        is_destructive = hitl_hook_provider._is_destructive_operation(
            "shell", {"command": "format /dev/sda1"}
        )
        assert is_destructive is True

    def test_detects_erase_command(self, hitl_hook_provider):
        """Test detection of erase command."""
        is_destructive = hitl_hook_provider._is_destructive_operation(
            "shell", {"command": "erase disk"}
        )
        assert is_destructive is True

    def test_detects_editor_delete_operation(self, hitl_hook_provider):
        """Test detection of delete operation in editor tool."""
        is_destructive = hitl_hook_provider._is_destructive_operation(
            "editor", {"operation": "delete", "path": "/etc/passwd"}
        )
        assert is_destructive is True

    def test_detects_editor_remove_operation(self, hitl_hook_provider):
        """Test detection of remove operation in editor tool."""
        is_destructive = hitl_hook_provider._is_destructive_operation(
            "editor", {"operation": "remove", "path": "/important/file"}
        )
        assert is_destructive is True

    def test_safe_command_not_detected(self, hitl_hook_provider):
        """Test that safe commands are not flagged as destructive."""
        is_destructive = hitl_hook_provider._is_destructive_operation(
            "shell", {"command": "ls -la"}
        )
        assert is_destructive is False

    def test_case_insensitive_detection(self, hitl_hook_provider):
        """Test that detection is case insensitive."""
        is_destructive = hitl_hook_provider._is_destructive_operation(
            "shell", {"command": "RM -rf /data"}
        )
        assert is_destructive is True

    def test_empty_command(self, hitl_hook_provider):
        """Test handling of empty command."""
        is_destructive = hitl_hook_provider._is_destructive_operation(
            "shell", {"command": ""}
        )
        assert is_destructive is False

    def test_missing_command_parameter(self, hitl_hook_provider):
        """Test handling of missing command parameter."""
        is_destructive = hitl_hook_provider._is_destructive_operation("shell", {})
        assert is_destructive is False


class TestPauseDecisionLogic:
    """Tests for _should_pause_for_tool method."""

    def test_should_pause_for_destructive_when_enabled(self, hitl_hook_provider):
        """Test pause triggered for destructive op when auto-pause enabled."""
        should_pause, reason = hitl_hook_provider._should_pause_for_tool(
            "shell", {"command": "rm -rf /"}
        )
        assert should_pause is True
        assert reason == "destructive_operation"

    def test_should_not_pause_for_destructive_when_disabled(self, feedback_manager):
        """Test no pause for destructive op when auto-pause disabled."""
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

    def test_should_not_pause_for_safe_operation(self, hitl_hook_provider):
        """Test no pause for safe operations."""
        should_pause, reason = hitl_hook_provider._should_pause_for_tool(
            "shell", {"command": "echo 'Hello, World!'"}
        )
        assert should_pause is False
        assert reason is None

    def test_should_pause_for_editor_delete(self, hitl_hook_provider):
        """Test pause triggered for editor delete operation."""
        should_pause, reason = hitl_hook_provider._should_pause_for_tool(
            "editor", {"operation": "delete", "path": "/critical/file"}
        )
        assert should_pause is True
        assert reason == "destructive_operation"


class TestHookProviderConfiguration:
    """Tests for HITLHookProvider configuration options."""

    def test_default_configuration(self, feedback_manager):
        """Test hook provider initializes with default settings."""
        hook = HITLHookProvider(feedback_manager=feedback_manager)

        assert hook.auto_pause_on_destructive is True
        assert hook.auto_pause_on_low_confidence is True
        assert hook.confidence_threshold == 70.0

    def test_custom_configuration(self, feedback_manager):
        """Test hook provider accepts custom settings."""
        hook = HITLHookProvider(
            feedback_manager=feedback_manager,
            auto_pause_on_destructive=False,
            auto_pause_on_low_confidence=False,
            confidence_threshold=80.0,
        )

        assert hook.auto_pause_on_destructive is False
        assert hook.auto_pause_on_low_confidence is False
        assert hook.confidence_threshold == 80.0

    def test_destructive_patterns_configured(self, hitl_hook_provider):
        """Test that destructive patterns are configured."""
        patterns = hitl_hook_provider.destructive_patterns

        assert "rm " in patterns
        assert "delete " in patterns
        assert "drop " in patterns
        assert "truncate " in patterns
        assert "format " in patterns
        assert "erase " in patterns


class TestIntegrationWithFeedbackManager:
    """Tests for integration between HITLHookProvider and FeedbackManager."""

    def test_hook_requests_pause_through_manager(
        self, hitl_hook_provider, feedback_manager
    ):
        """Test that hook uses FeedbackManager to request pause."""
        # Create destructive event
        event = Mock(spec=BeforeToolCallEvent)
        event.tool_use = {
            "name": "shell",
            "toolUseId": "integration_001",
            "input": {"command": "rm -rf /critical"},
        }

        # Mock wait_for_feedback
        feedback_manager.wait_for_feedback = Mock(return_value=True)

        # Trigger hook
        hitl_hook_provider._on_before_tool_call(event)

        # Verify FeedbackManager state changed
        assert feedback_manager.state == HITLState.PAUSED
        assert feedback_manager.pending_tool is not None

    def test_hook_waits_using_manager(
        self, hitl_hook_provider, feedback_manager
    ):
        """Test that hook uses FeedbackManager.wait_for_feedback()."""
        # Create destructive event
        event = Mock(spec=BeforeToolCallEvent)
        event.tool_use = {
            "name": "shell",
            "toolUseId": "integration_002",
            "input": {"command": "delete /etc/config"},
        }

        # Spy on wait_for_feedback
        original_wait = feedback_manager.wait_for_feedback
        feedback_manager.wait_for_feedback = Mock(side_effect=original_wait)

        # Trigger hook
        hitl_hook_provider._on_before_tool_call(event)

        # Verify wait_for_feedback was called
        feedback_manager.wait_for_feedback.assert_called()

    def test_manual_pause_uses_manager(
        self, hitl_hook_provider, feedback_manager, mock_model_event
    ):
        """Test that manual pause check uses FeedbackManager."""
        # Request manual pause
        feedback_manager.request_pause(is_manual=True)

        # Mock wait_for_feedback
        feedback_manager.wait_for_feedback = Mock(return_value=True)

        # Trigger hook
        hitl_hook_provider._check_manual_pause(mock_model_event)

        # Verify integration
        feedback_manager.wait_for_feedback.assert_called_once()
