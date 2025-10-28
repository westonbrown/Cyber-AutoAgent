"""Comprehensive unit tests for FeedbackInputHandler stdin processing.

This test suite verifies that the FeedbackInputHandler correctly:
1. Parses stdin commands in correct format
2. Handles malformed/invalid commands gracefully
3. Manages listener thread lifecycle
4. Routes commands to appropriate handlers
5. Processes test markers
6. Handles edge cases (empty lines, partial data)
"""

import json
import sys
import threading
import time
from io import StringIO
from unittest.mock import Mock, MagicMock, patch, call

import pytest

from modules.handlers.hitl.feedback_handler import FeedbackInputHandler
from modules.handlers.hitl.feedback_manager import FeedbackManager
from modules.handlers.hitl.types import FeedbackType


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
        operation_id="test_stdin_op",
        emitter=mock_emitter,
    )


@pytest.fixture
def feedback_handler(feedback_manager):
    """Create FeedbackInputHandler instance."""
    return FeedbackInputHandler(feedback_manager=feedback_manager)


class TestHandlerInitialization:
    """Tests for FeedbackInputHandler initialization."""

    def test_handler_initialization(self, feedback_manager):
        """Test handler initializes with FeedbackManager."""
        handler = FeedbackInputHandler(feedback_manager=feedback_manager)

        assert handler.feedback_manager == feedback_manager
        assert handler._running is False
        assert handler._listener_thread is None

    def test_handler_not_running_initially(self, feedback_handler):
        """Test handler is not running initially."""
        assert feedback_handler._running is False


class TestThreadLifecycle:
    """Tests for listener thread lifecycle management."""

    def test_start_listening_starts_thread(self, feedback_handler):
        """Test that start_listening creates and starts thread."""
        feedback_handler.start_listening()

        assert feedback_handler._running is True
        assert feedback_handler._listener_thread is not None
        assert feedback_handler._listener_thread.is_alive()

        # Clean up
        feedback_handler.stop_listening()

    def test_start_listening_sets_daemon_thread(self, feedback_handler):
        """Test that listener thread is daemon thread."""
        feedback_handler.start_listening()

        assert feedback_handler._listener_thread.daemon is True

        # Clean up
        feedback_handler.stop_listening()

    def test_start_listening_thread_name(self, feedback_handler):
        """Test that thread has correct name."""
        feedback_handler.start_listening()

        assert feedback_handler._listener_thread.name == "HITLFeedbackListener"

        # Clean up
        feedback_handler.stop_listening()

    def test_start_listening_idempotent(self, feedback_handler):
        """Test that calling start_listening multiple times is safe."""
        feedback_handler.start_listening()
        thread1 = feedback_handler._listener_thread

        # Call again
        feedback_handler.start_listening()
        thread2 = feedback_handler._listener_thread

        # Should be same thread
        assert thread1 == thread2

        # Clean up
        feedback_handler.stop_listening()

    def test_stop_listening_stops_thread(self, feedback_handler):
        """Test that stop_listening stops the thread."""
        feedback_handler.start_listening()
        assert feedback_handler._running is True

        feedback_handler.stop_listening()

        assert feedback_handler._running is False

    def test_stop_listening_when_not_running(self, feedback_handler):
        """Test that stop_listening is safe when not running."""
        # Should not raise exception
        feedback_handler.stop_listening()
        assert feedback_handler._running is False


class TestCommandParsing:
    """Tests for stdin command parsing."""

    def test_process_input_line_valid_submit_feedback(self, feedback_handler):
        """Test parsing valid submit_feedback command."""
        command = {
            "type": "submit_feedback",
            "feedback_type": "correction",
            "content": "Use safer approach",
            "tool_id": "test_123",
        }
        line = f"__HITL_COMMAND__{json.dumps(command)}__HITL_COMMAND_END__\n"

        # Mock handle_feedback_command to verify it's called
        feedback_handler.handle_feedback_command = Mock()

        feedback_handler._process_input_line(line)

        # Verify command was parsed and handled
        feedback_handler.handle_feedback_command.assert_called_once_with(command)

    def test_process_input_line_valid_request_pause(self, feedback_handler):
        """Test parsing valid request_pause command."""
        command = {
            "type": "request_pause",
            "is_manual": True,
        }
        line = f"__HITL_COMMAND__{json.dumps(command)}__HITL_COMMAND_END__\n"

        # Mock handle_feedback_command
        feedback_handler.handle_feedback_command = Mock()

        feedback_handler._process_input_line(line)

        # Verify command was parsed and handled
        feedback_handler.handle_feedback_command.assert_called_once_with(command)

    def test_process_input_line_invalid_json(self, feedback_handler):
        """Test handling of invalid JSON."""
        line = "__HITL_COMMAND__{invalid json}__HITL_COMMAND_END__\n"

        # Should not raise exception
        feedback_handler._process_input_line(line)

    def test_process_input_line_missing_end_marker(self, feedback_handler):
        """Test handling of missing end marker."""
        command = {"type": "submit_feedback"}
        line = f"__HITL_COMMAND__{json.dumps(command)}\n"

        # Should not raise exception
        feedback_handler._process_input_line(line)

    def test_process_input_line_missing_start_marker(self, feedback_handler):
        """Test handling of missing start marker."""
        command = {"type": "submit_feedback"}
        line = f"{json.dumps(command)}__HITL_COMMAND_END__\n"

        # Mock handle_feedback_command (should not be called)
        feedback_handler.handle_feedback_command = Mock()

        feedback_handler._process_input_line(line)

        # Verify command was not processed
        feedback_handler.handle_feedback_command.assert_not_called()

    def test_process_input_line_no_markers(self, feedback_handler):
        """Test handling of line without HITL markers."""
        line = "This is a regular line without markers\n"

        # Mock handle_feedback_command (should not be called)
        feedback_handler.handle_feedback_command = Mock()

        feedback_handler._process_input_line(line)

        # Verify command was not processed
        feedback_handler.handle_feedback_command.assert_not_called()

    def test_process_input_line_empty_line(self, feedback_handler):
        """Test handling of empty line."""
        line = ""

        # Should not raise exception
        feedback_handler._process_input_line(line)

    def test_process_input_line_test_marker(self, feedback_handler):
        """Test detection of TEST_STDIN_WORKS marker."""
        line = "TEST_STDIN_WORKS\n"

        # Should not raise exception (logs test success)
        feedback_handler._process_input_line(line)

    def test_process_input_line_complex_content(self, feedback_handler):
        """Test parsing command with complex content."""
        command = {
            "type": "submit_feedback",
            "feedback_type": "correction",
            "content": "Use this command:\ncurl -X POST 'http://test.com?q=1&r=2'\n-H 'Content-Type: application/json'",
            "tool_id": "test_456",
        }
        line = f"__HITL_COMMAND__{json.dumps(command)}__HITL_COMMAND_END__\n"

        # Mock handle_feedback_command
        feedback_handler.handle_feedback_command = Mock()

        feedback_handler._process_input_line(line)

        # Verify command was parsed correctly
        feedback_handler.handle_feedback_command.assert_called_once()
        parsed_command = feedback_handler.handle_feedback_command.call_args[0][0]
        assert parsed_command["content"] == command["content"]


class TestCommandRouting:
    """Tests for routing commands to appropriate handlers."""

    def test_handle_feedback_command_submit_feedback(self, feedback_handler):
        """Test routing to _handle_submit_feedback."""
        command = {
            "type": "submit_feedback",
            "feedback_type": "correction",
            "content": "Test feedback",
            "tool_id": "test_789",
        }

        # Mock the handler
        feedback_handler._handle_submit_feedback = Mock()

        feedback_handler.handle_feedback_command(command)

        # Verify correct handler was called
        feedback_handler._handle_submit_feedback.assert_called_once_with(command)

    def test_handle_feedback_command_request_pause(self, feedback_handler):
        """Test routing to _handle_pause_request."""
        command = {
            "type": "request_pause",
            "is_manual": True,
        }

        # Mock the handler
        feedback_handler._handle_pause_request = Mock()

        feedback_handler.handle_feedback_command(command)

        # Verify correct handler was called
        feedback_handler._handle_pause_request.assert_called_once_with(command)

    def test_handle_feedback_command_unknown_type(self, feedback_handler):
        """Test handling of unknown command type."""
        command = {
            "type": "unknown_command",
        }

        # Should not raise exception
        feedback_handler.handle_feedback_command(command)

    def test_handle_feedback_command_missing_type(self, feedback_handler):
        """Test handling of command without type field."""
        command = {
            "content": "Some content",
        }

        # Should not raise exception
        feedback_handler.handle_feedback_command(command)


class TestSubmitFeedbackHandler:
    """Tests for _handle_submit_feedback method."""

    def test_handle_submit_feedback_correction(
        self, feedback_handler, feedback_manager
    ):
        """Test handling correction feedback."""
        command = {
            "feedback_type": "correction",
            "content": "Use safer command",
            "tool_id": "test_001",
        }

        # Setup pause (required before feedback submission)
        feedback_manager.request_pause(
            tool_name="test_tool",
            tool_id="test_001",
            parameters={},
        )

        feedback_handler._handle_submit_feedback(command)

        # Verify feedback was submitted
        feedback = feedback_manager.get_pending_feedback("test_001")
        assert feedback is not None
        assert feedback.feedback_type == FeedbackType.CORRECTION
        assert feedback.content == "Use safer command"

    def test_handle_submit_feedback_suggestion(
        self, feedback_handler, feedback_manager
    ):
        """Test handling suggestion feedback."""
        command = {
            "feedback_type": "suggestion",
            "content": "Consider alternative approach",
            "tool_id": "test_002",
        }

        # Setup pause
        feedback_manager.request_pause(
            tool_name="test_tool",
            tool_id="test_002",
            parameters={},
        )

        feedback_handler._handle_submit_feedback(command)

        # Verify feedback
        feedback = feedback_manager.get_pending_feedback("test_002")
        assert feedback.feedback_type == FeedbackType.SUGGESTION

    def test_handle_submit_feedback_approval(
        self, feedback_handler, feedback_manager
    ):
        """Test handling approval feedback."""
        command = {
            "feedback_type": "approval",
            "content": "Approved - proceed",
            "tool_id": "test_003",
        }

        # Setup pause
        feedback_manager.request_pause(
            tool_name="test_tool",
            tool_id="test_003",
            parameters={},
        )

        feedback_handler._handle_submit_feedback(command)

        # Verify feedback
        feedback = feedback_manager.get_pending_feedback("test_003")
        assert feedback.feedback_type == FeedbackType.APPROVAL

    def test_handle_submit_feedback_rejection(
        self, feedback_handler, feedback_manager
    ):
        """Test handling rejection feedback."""
        command = {
            "feedback_type": "rejection",
            "content": "REJECTED - do not proceed",
            "tool_id": "test_004",
        }

        # Setup pause
        feedback_manager.request_pause(
            tool_name="test_tool",
            tool_id="test_004",
            parameters={},
        )

        feedback_handler._handle_submit_feedback(command)

        # Verify feedback
        feedback = feedback_manager.get_pending_feedback("test_004")
        assert feedback.feedback_type == FeedbackType.REJECTION

    def test_handle_submit_feedback_defaults_to_correction(
        self, feedback_handler, feedback_manager
    ):
        """Test feedback defaults to correction when type missing."""
        command = {
            "content": "Some feedback",
            "tool_id": "test_005",
        }

        # Setup pause
        feedback_manager.request_pause(
            tool_name="test_tool",
            tool_id="test_005",
            parameters={},
        )

        feedback_handler._handle_submit_feedback(command)

        # Verify default type
        feedback = feedback_manager.get_pending_feedback("test_005")
        assert feedback.feedback_type == FeedbackType.CORRECTION

    def test_handle_submit_feedback_invalid_type(
        self, feedback_handler, feedback_manager
    ):
        """Test handling of invalid feedback type."""
        command = {
            "feedback_type": "invalid_type",
            "content": "Some feedback",
            "tool_id": "test_006",
        }

        # Setup pause
        feedback_manager.request_pause(
            tool_name="test_tool",
            tool_id="test_006",
            parameters={},
        )

        # Should handle error gracefully (logged but not raised)
        feedback_handler._handle_submit_feedback(command)

        # Verify feedback was not submitted due to invalid type
        feedback = feedback_manager.get_pending_feedback("test_006")
        assert feedback is None

    def test_handle_submit_feedback_empty_content(
        self, feedback_handler, feedback_manager
    ):
        """Test handling of empty content."""
        command = {
            "feedback_type": "correction",
            "content": "",
            "tool_id": "test_007",
        }

        # Setup pause
        feedback_manager.request_pause(
            tool_name="test_tool",
            tool_id="test_007",
            parameters={},
        )

        # Should not raise exception
        feedback_handler._handle_submit_feedback(command)

        # Verify feedback was submitted
        feedback = feedback_manager.get_pending_feedback("test_007")
        assert feedback.content == ""


class TestPauseRequestHandler:
    """Tests for _handle_pause_request method."""

    def test_handle_pause_request_manual(
        self, feedback_handler, feedback_manager
    ):
        """Test handling manual pause request."""
        command = {
            "is_manual": True,
        }

        # Mock wait_for_feedback to avoid blocking test
        feedback_manager.wait_for_feedback = Mock(return_value=True)

        feedback_handler._handle_pause_request(command)

        # Verify pause was requested
        feedback_manager.wait_for_feedback.assert_called_once()

    def test_handle_pause_request_auto(
        self, feedback_handler, feedback_manager
    ):
        """Test handling auto pause request."""
        command = {
            "is_manual": False,
        }

        # Mock wait_for_feedback
        feedback_manager.wait_for_feedback = Mock(return_value=True)

        feedback_handler._handle_pause_request(command)

        # Verify pause was requested
        feedback_manager.wait_for_feedback.assert_called_once()

    def test_handle_pause_request_defaults_to_manual(
        self, feedback_handler, feedback_manager
    ):
        """Test pause request defaults to manual when field missing."""
        command = {}

        # Mock wait_for_feedback
        feedback_manager.wait_for_feedback = Mock(return_value=True)

        feedback_handler._handle_pause_request(command)

        # Verify pause was requested (default is manual)
        feedback_manager.wait_for_feedback.assert_called_once()

    def test_handle_pause_request_timeout(
        self, feedback_handler, feedback_manager
    ):
        """Test handling timeout during pause."""
        command = {
            "is_manual": True,
        }

        # Mock wait_for_feedback to simulate timeout
        feedback_manager.wait_for_feedback = Mock(return_value=False)

        # Should not raise exception
        feedback_handler._handle_pause_request(command)

        feedback_manager.wait_for_feedback.assert_called_once()


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_malformed_json_no_crash(self, feedback_handler):
        """Test that malformed JSON doesn't crash handler."""
        lines = [
            "__HITL_COMMAND__{not valid json__HITL_COMMAND_END__\n",
            "__HITL_COMMAND__{\"type\": }__HITL_COMMAND_END__\n",
            "__HITL_COMMAND__{{}}__HITL_COMMAND_END__\n",
        ]

        for line in lines:
            # Should not raise exception
            feedback_handler._process_input_line(line)

    def test_partial_command_no_crash(self, feedback_handler):
        """Test that partial commands don't crash handler."""
        lines = [
            "__HITL_COMMAND__\n",
            "__HITL_COMMAND_END__\n",
            "__HITL_COMMAND__{\"type\": \"submit\n",
        ]

        for line in lines:
            # Should not raise exception
            feedback_handler._process_input_line(line)

    def test_multiple_commands_in_line(self, feedback_handler):
        """Test handling of multiple commands in single line."""
        command1 = {"type": "request_pause", "is_manual": True}
        command2 = {"type": "submit_feedback", "content": "test", "tool_id": "001"}

        # Multiple commands in one line (only first should be parsed)
        line = f"__HITL_COMMAND__{json.dumps(command1)}__HITL_COMMAND_END____HITL_COMMAND__{json.dumps(command2)}__HITL_COMMAND_END__\n"

        # Mock handler
        feedback_handler.handle_feedback_command = Mock()

        feedback_handler._process_input_line(line)

        # Should parse first command
        feedback_handler.handle_feedback_command.assert_called_once_with(command1)

    def test_unicode_in_content(self, feedback_handler, feedback_manager):
        """Test handling of unicode characters in content."""
        command = {
            "type": "submit_feedback",
            "feedback_type": "correction",
            "content": "Use emoji: 🔒 for security",
            "tool_id": "test_unicode",
        }
        line = f"__HITL_COMMAND__{json.dumps(command)}__HITL_COMMAND_END__\n"

        # Setup pause
        feedback_manager.request_pause(
            tool_name="test", tool_id="test_unicode", parameters={}
        )

        # Mock handler to verify content
        original_handler = feedback_handler._handle_submit_feedback
        feedback_handler._handle_submit_feedback = Mock(side_effect=original_handler)

        feedback_handler._process_input_line(line)

        # Verify unicode was preserved
        feedback_handler._handle_submit_feedback.assert_called_once()
        parsed_command = feedback_handler._handle_submit_feedback.call_args[0][0]
        assert "🔒" in parsed_command["content"]

    def test_very_long_content(self, feedback_handler, feedback_manager):
        """Test handling of very long content."""
        long_content = "A" * 10000
        command = {
            "type": "submit_feedback",
            "feedback_type": "correction",
            "content": long_content,
            "tool_id": "test_long",
        }
        line = f"__HITL_COMMAND__{json.dumps(command)}__HITL_COMMAND_END__\n"

        # Setup pause
        feedback_manager.request_pause(
            tool_name="test", tool_id="test_long", parameters={}
        )

        # Should not raise exception
        feedback_handler._process_input_line(line)

        # Verify feedback was submitted
        feedback = feedback_manager.get_pending_feedback("test_long")
        assert len(feedback.content) == 10000


class TestStdinMocking:
    """Tests using mocked stdin for realistic scenarios."""

    @patch("sys.stdin")
    @patch("select.select")
    def test_listen_loop_reads_from_stdin(
        self, mock_select, mock_stdin, feedback_handler
    ):
        """Test that listen loop reads from stdin when data available."""
        # Setup mock stdin
        command = {"type": "submit_feedback", "content": "test", "tool_id": "001"}
        line = f"__HITL_COMMAND__{json.dumps(command)}__HITL_COMMAND_END__\n"
        mock_stdin.readline.return_value = line
        mock_stdin.isatty.return_value = False
        mock_stdin.fileno.return_value = 0
        mock_stdin.closed = False

        # Mock select to return stdin has data once, then stop
        call_count = 0

        def select_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ([mock_stdin], [], [])  # Data available
            else:
                # Stop the loop
                feedback_handler._running = False
                return ([], [], [])

        mock_select.side_effect = select_side_effect

        # Mock command handler
        feedback_handler.handle_feedback_command = Mock()

        # Start listen loop in thread
        feedback_handler._running = True
        thread = threading.Thread(target=feedback_handler._listen_loop)
        thread.start()
        thread.join(timeout=2)

        # Verify command was processed
        feedback_handler.handle_feedback_command.assert_called_once_with(command)

    @patch("sys.stdin")
    @patch("select.select")
    def test_listen_loop_handles_stdin_timeout(
        self, mock_select, mock_stdin, feedback_handler
    ):
        """Test that listen loop handles select timeout gracefully."""
        mock_stdin.isatty.return_value = False
        mock_stdin.fileno.return_value = 0
        mock_stdin.closed = False

        # Mock select to timeout (return empty list)
        call_count = 0

        def select_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                feedback_handler._running = False
            return ([], [], [])  # Timeout

        mock_select.side_effect = select_side_effect

        # Start listen loop
        feedback_handler._running = True
        thread = threading.Thread(target=feedback_handler._listen_loop)
        thread.start()
        thread.join(timeout=2)

        # Loop should exit cleanly
        assert not feedback_handler._running
