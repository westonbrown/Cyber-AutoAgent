"""Integration tests for HITL system end-to-end workflows.

This test suite verifies complete HITL workflows:
1. Stdin → FeedbackInputHandler → FeedbackManager → Hook → Model
2. Auto-pause workflow (destructive tool detection)
3. Manual pause workflow (user-initiated)
4. Feedback injection into model system prompt
5. Timeout handling for both pause types
"""

import json
import threading
import time
from unittest.mock import Mock, MagicMock, patch, call

import pytest
from strands.experimental.hooks.events import (
    BeforeToolInvocationEvent,
    BeforeModelInvocationEvent,
)
from strands.hooks import HookRegistry

from modules.handlers.hitl.feedback_handler import FeedbackInputHandler
from modules.handlers.hitl.feedback_manager import FeedbackManager
from modules.handlers.hitl.hitl_hook_provider import HITLHookProvider
from modules.handlers.hitl.feedback_injection_hook import HITLFeedbackInjectionHook
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
        memory=mock_memory,
        operation_id="test_integration_op",
        emitter=mock_emitter,
    )


@pytest.fixture
def feedback_handler(feedback_manager):
    """Create FeedbackInputHandler instance."""
    return FeedbackInputHandler(feedback_manager=feedback_manager)


@pytest.fixture
def hitl_hook_provider(feedback_manager):
    """Create HITLHookProvider instance."""
    return HITLHookProvider(
        feedback_manager=feedback_manager,
        auto_pause_on_destructive=True,
        auto_pause_on_low_confidence=True,
        confidence_threshold=70.0,
    )


@pytest.fixture
def feedback_injection_hook(feedback_manager):
    """Create HITLFeedbackInjectionHook instance."""
    return HITLFeedbackInjectionHook(feedback_manager=feedback_manager)


@pytest.fixture
def mock_agent():
    """Create mock agent with system_prompt attribute."""
    agent = Mock()
    agent.system_prompt = "You are a test assistant."
    return agent


class TestAutoPauseWorkflow:
    """Integration tests for auto-pause workflow."""

    def test_auto_pause_full_workflow(
        self,
        feedback_manager,
        hitl_hook_provider,
        feedback_injection_hook,
        mock_agent,
    ):
        """Test complete auto-pause workflow from tool detection to feedback injection.

        Flow:
        1. Hook intercepts destructive tool call
        2. FeedbackManager pauses execution
        3. User submits feedback via stdin handler
        4. Feedback is stored and execution resumes
        5. Injection hook adds feedback to system prompt
        6. Feedback is cleared after injection
        """
        # Step 1: Hook intercepts destructive tool
        tool_event = Mock(spec=BeforeToolInvocationEvent)
        tool_event.tool_use = {
            "name": "shell",
            "toolUseId": "auto_001",
            "input": {"command": "rm -rf /data"},
        }

        # Mock wait_for_feedback to simulate async feedback submission
        feedback_received_event = threading.Event()

        def wait_side_effect():
            # Wait for feedback to be submitted
            return feedback_received_event.wait(timeout=5)

        feedback_manager.wait_for_feedback = Mock(side_effect=wait_side_effect)

        # Start hook in background thread
        hook_thread = threading.Thread(
            target=hitl_hook_provider._on_before_tool_call,
            args=(tool_event,),
        )
        hook_thread.start()

        # Wait for pause to be requested
        time.sleep(0.1)

        # Step 2: Verify pause was triggered
        assert feedback_manager.state == HITLState.PAUSED
        assert feedback_manager.pending_tool is not None
        assert feedback_manager.pending_tool.tool_name == "shell"

        # Step 3: Submit feedback (simulating stdin input)
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.CORRECTION,
            content="Use 'rm -i' for interactive deletion",
            tool_id="auto_001",
        )

        # Signal feedback received
        feedback_received_event.set()

        # Wait for hook to complete
        hook_thread.join(timeout=2)

        # Step 4: Verify feedback stored
        assert feedback_manager.pending_feedback is not None
        assert feedback_manager.state == HITLState.ACTIVE

        # Step 5: Simulate model invocation with injection hook
        model_event = Mock(spec=BeforeModelInvocationEvent)
        model_event.agent = mock_agent

        original_prompt = mock_agent.system_prompt
        feedback_injection_hook.inject_feedback(model_event)

        # Step 6: Verify feedback was injected
        new_prompt = mock_agent.system_prompt
        assert len(new_prompt) > len(original_prompt)
        assert "HUMAN FEEDBACK RECEIVED" in new_prompt
        assert "Use 'rm -i' for interactive deletion" in new_prompt

        # Step 7: Verify feedback was cleared after injection
        assert feedback_manager.pending_feedback is None

    def test_auto_pause_with_timeout(
        self, feedback_manager, hitl_hook_provider
    ):
        """Test auto-pause workflow when timeout expires without feedback."""
        # Configure short timeout for testing
        feedback_manager.auto_pause_timeout = 1

        # Create destructive tool event
        tool_event = Mock(spec=BeforeToolInvocationEvent)
        tool_event.tool_use = {
            "name": "shell",
            "toolUseId": "timeout_001",
            "input": {"command": "delete /critical/data"},
        }

        # Don't mock wait_for_feedback - let it timeout naturally
        start_time = time.time()
        hitl_hook_provider._on_before_tool_call(tool_event)
        elapsed = time.time() - start_time

        # Verify timeout occurred (should be ~1 second)
        assert elapsed >= 1.0
        assert elapsed < 2.0

        # Verify execution auto-resumed
        assert feedback_manager.state == HITLState.ACTIVE

    def test_auto_pause_skipped_for_safe_operation(
        self, feedback_manager, hitl_hook_provider
    ):
        """Test that safe operations bypass auto-pause."""
        # Create safe tool event
        tool_event = Mock(spec=BeforeToolInvocationEvent)
        tool_event.tool_use = {
            "name": "shell",
            "toolUseId": "safe_001",
            "input": {"command": "ls -la"},
        }

        # Execute hook
        hitl_hook_provider._on_before_tool_call(tool_event)

        # Verify no pause occurred
        assert feedback_manager.state == HITLState.ACTIVE
        assert feedback_manager.pending_tool is None


class TestManualPauseWorkflow:
    """Integration tests for manual pause workflow."""

    def test_manual_pause_full_workflow(
        self,
        feedback_manager,
        hitl_hook_provider,
        feedback_injection_hook,
        mock_agent,
    ):
        """Test complete manual pause workflow.

        Flow:
        1. User requests manual pause
        2. Hook detects pause before model invocation
        3. User submits feedback
        4. Execution resumes
        5. Feedback injected into system prompt
        """
        # Step 1: User requests manual pause
        feedback_manager.request_pause(is_manual=True)

        assert feedback_manager.state == HITLState.PAUSED
        assert feedback_manager.pending_tool is not None
        assert feedback_manager.pending_tool.tool_name == "manual_intervention"

        # Step 2: Mock model invocation in background thread
        model_event = Mock(spec=BeforeModelInvocationEvent)

        feedback_received_event = threading.Event()

        def wait_side_effect():
            return feedback_received_event.wait(timeout=5)

        feedback_manager.wait_for_feedback = Mock(side_effect=wait_side_effect)

        hook_thread = threading.Thread(
            target=hitl_hook_provider._check_manual_pause,
            args=(model_event,),
        )
        hook_thread.start()

        # Wait for hook to start waiting
        time.sleep(0.1)

        # Step 3: Submit feedback
        tool_id = feedback_manager.pending_tool.tool_id
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.SUGGESTION,
            content="Check system logs before proceeding",
            tool_id=tool_id,
        )

        # Signal feedback received
        feedback_received_event.set()

        # Wait for hook to complete
        hook_thread.join(timeout=2)

        # Step 4: Verify execution resumed
        assert feedback_manager.state == HITLState.ACTIVE

        # Step 5: Inject feedback
        model_event.agent = mock_agent
        feedback_injection_hook.inject_feedback(model_event)

        # Verify injection
        prompt = mock_agent.system_prompt
        assert "Check system logs before proceeding" in prompt

    def test_manual_pause_with_timeout(
        self, feedback_manager, hitl_hook_provider
    ):
        """Test manual pause with timeout expiration."""
        # Configure short timeout
        feedback_manager.manual_pause_timeout = 1

        # Request manual pause
        feedback_manager.request_pause(is_manual=True)

        # Create model event
        model_event = Mock(spec=BeforeModelInvocationEvent)

        # Check manual pause (will timeout)
        start_time = time.time()
        hitl_hook_provider._check_manual_pause(model_event)
        elapsed = time.time() - start_time

        # Verify timeout occurred
        assert elapsed >= 1.0
        assert elapsed < 2.0

        # Verify auto-resume
        assert feedback_manager.state == HITLState.ACTIVE


class TestStdinToFeedbackFlow:
    """Integration tests for stdin → feedback manager flow."""

    def test_stdin_submit_feedback_integration(
        self, feedback_handler, feedback_manager
    ):
        """Test stdin command flows to feedback manager.

        Flow:
        1. Stdin receives submit_feedback command
        2. FeedbackInputHandler parses command
        3. FeedbackManager stores feedback
        4. Feedback available for injection
        """
        # Step 1: Setup initial pause
        feedback_manager.request_pause(
            tool_name="test_tool",
            tool_id="stdin_001",
            parameters={"test": "value"},
        )

        # Step 2: Simulate stdin command
        command = {
            "type": "submit_feedback",
            "feedback_type": "correction",
            "content": "Feedback from stdin",
            "tool_id": "stdin_001",
        }
        line = f"__HITL_COMMAND__{json.dumps(command)}__HITL_COMMAND_END__\n"

        # Step 3: Process stdin line
        feedback_handler._process_input_line(line)

        # Step 4: Verify feedback stored
        feedback = feedback_manager.get_pending_feedback("stdin_001")
        assert feedback is not None
        assert feedback.feedback_type == FeedbackType.CORRECTION
        assert feedback.content == "Feedback from stdin"
        assert feedback_manager.state == HITLState.ACTIVE

    def test_stdin_request_pause_integration(
        self, feedback_handler, feedback_manager
    ):
        """Test stdin pause request flows to feedback manager."""
        # Mock wait_for_feedback to avoid blocking
        feedback_manager.wait_for_feedback = Mock(return_value=True)

        # Simulate stdin command
        command = {
            "type": "request_pause",
            "is_manual": True,
        }
        line = f"__HITL_COMMAND__{json.dumps(command)}__HITL_COMMAND_END__\n"

        # Process command
        feedback_handler._process_input_line(line)

        # Verify pause was requested
        feedback_manager.wait_for_feedback.assert_called_once()


class TestCompleteEndToEnd:
    """Complete end-to-end integration tests."""

    def test_complete_auto_pause_cycle(
        self,
        feedback_handler,
        feedback_manager,
        hitl_hook_provider,
        feedback_injection_hook,
        mock_agent,
    ):
        """Test complete cycle: tool call → pause → stdin feedback → injection.

        This is the most realistic integration test simulating actual usage.
        """
        # Step 1: Hook intercepts destructive tool
        tool_event = Mock(spec=BeforeToolInvocationEvent)
        tool_event.tool_use = {
            "name": "shell",
            "toolUseId": "e2e_001",
            "input": {"command": "DROP TABLE users"},
        }

        # Setup async coordination
        feedback_received_event = threading.Event()

        def wait_side_effect():
            return feedback_received_event.wait(timeout=5)

        feedback_manager.wait_for_feedback = Mock(side_effect=wait_side_effect)

        # Start hook in background
        hook_thread = threading.Thread(
            target=hitl_hook_provider._on_before_tool_call,
            args=(tool_event,),
        )
        hook_thread.start()

        # Wait for pause
        time.sleep(0.1)

        # Step 2: Verify pause
        assert feedback_manager.state == HITLState.PAUSED

        # Step 3: Submit feedback via stdin
        command = {
            "type": "submit_feedback",
            "feedback_type": "rejection",
            "content": "REJECTED - use UPDATE instead",
            "tool_id": "e2e_001",
        }
        line = f"__HITL_COMMAND__{json.dumps(command)}__HITL_COMMAND_END__\n"
        feedback_handler._process_input_line(line)

        # Signal feedback received
        feedback_received_event.set()

        # Wait for hook to complete
        hook_thread.join(timeout=2)

        # Step 4: Verify feedback stored
        assert feedback_manager.pending_feedback is not None

        # Step 5: Simulate model invocation with injection
        model_event = Mock(spec=BeforeModelInvocationEvent)
        model_event.agent = mock_agent

        feedback_injection_hook.inject_feedback(model_event)

        # Step 6: Verify complete flow
        prompt = mock_agent.system_prompt
        assert "HUMAN FEEDBACK RECEIVED" in prompt
        assert "REJECTED - use UPDATE instead" in prompt
        assert feedback_manager.pending_feedback is None  # Cleared after injection

    def test_complete_manual_pause_cycle(
        self,
        feedback_handler,
        feedback_manager,
        hitl_hook_provider,
        feedback_injection_hook,
        mock_agent,
    ):
        """Test complete manual pause cycle with stdin interaction."""
        # Step 1: User requests pause via stdin
        pause_command = {
            "type": "request_pause",
            "is_manual": True,
        }

        # Setup async coordination
        feedback_received_event = threading.Event()

        def wait_side_effect():
            return feedback_received_event.wait(timeout=5)

        feedback_manager.wait_for_feedback = Mock(side_effect=wait_side_effect)

        # Process pause request in background
        pause_thread = threading.Thread(
            target=feedback_handler._process_input_line,
            args=(f"__HITL_COMMAND__{json.dumps(pause_command)}__HITL_COMMAND_END__\n",),
        )
        pause_thread.start()

        # Wait for pause to be established
        time.sleep(0.1)

        # Step 2: Verify pause state
        assert feedback_manager.state == HITLState.PAUSED

        # Step 3: Get tool_id for feedback submission
        tool_id = feedback_manager.pending_tool.tool_id

        # Step 4: Submit feedback via stdin
        feedback_command = {
            "type": "submit_feedback",
            "feedback_type": "suggestion",
            "content": "Review security implications first",
            "tool_id": tool_id,
        }
        feedback_line = f"__HITL_COMMAND__{json.dumps(feedback_command)}__HITL_COMMAND_END__\n"
        feedback_handler._process_input_line(feedback_line)

        # Signal feedback received
        feedback_received_event.set()

        # Wait for pause thread to complete
        pause_thread.join(timeout=2)

        # Step 5: Verify feedback stored
        assert feedback_manager.pending_feedback is not None

        # Step 6: Inject feedback
        model_event = Mock(spec=BeforeModelInvocationEvent)
        model_event.agent = mock_agent

        feedback_injection_hook.inject_feedback(model_event)

        # Step 7: Verify complete flow
        prompt = mock_agent.system_prompt
        assert "Review security implications first" in prompt

    def test_multiple_pause_resume_cycles(
        self,
        feedback_handler,
        feedback_manager,
        hitl_hook_provider,
        feedback_injection_hook,
        mock_agent,
    ):
        """Test multiple pause/resume cycles in sequence."""
        feedback_manager.auto_pause_timeout = 10  # Longer timeout

        for i in range(3):
            # Create destructive tool event
            tool_event = Mock(spec=BeforeToolInvocationEvent)
            tool_event.tool_use = {
                "name": "shell",
                "toolUseId": f"cycle_{i}",
                "input": {"command": f"rm file_{i}"},
            }

            # Setup async
            feedback_received_event = threading.Event()

            def wait_side_effect():
                return feedback_received_event.wait(timeout=5)

            feedback_manager.wait_for_feedback = Mock(side_effect=wait_side_effect)

            # Start hook
            hook_thread = threading.Thread(
                target=hitl_hook_provider._on_before_tool_call,
                args=(tool_event,),
            )
            hook_thread.start()

            # Wait for pause
            time.sleep(0.1)
            assert feedback_manager.state == HITLState.PAUSED

            # Submit feedback
            command = {
                "type": "submit_feedback",
                "feedback_type": "correction",
                "content": f"Feedback for cycle {i}",
                "tool_id": f"cycle_{i}",
            }
            line = f"__HITL_COMMAND__{json.dumps(command)}__HITL_COMMAND_END__\n"
            feedback_handler._process_input_line(line)

            feedback_received_event.set()
            hook_thread.join(timeout=2)

            # Inject feedback
            model_event = Mock(spec=BeforeModelInvocationEvent)
            model_event.agent = mock_agent

            feedback_injection_hook.inject_feedback(model_event)

            # Verify feedback was injected
            assert f"Feedback for cycle {i}" in mock_agent.system_prompt

            # Verify state reset for next cycle
            assert feedback_manager.state == HITLState.ACTIVE
            assert feedback_manager.pending_feedback is None


class TestErrorRecovery:
    """Tests for error recovery in integrated workflows."""

    def test_recovery_from_invalid_stdin_during_pause(
        self, feedback_handler, feedback_manager, hitl_hook_provider
    ):
        """Test that invalid stdin during pause doesn't break workflow."""
        # Setup pause
        tool_event = Mock(spec=BeforeToolInvocationEvent)
        tool_event.tool_use = {
            "name": "shell",
            "toolUseId": "error_001",
            "input": {"command": "rm file"},
        }

        feedback_received_event = threading.Event()
        feedback_manager.wait_for_feedback = Mock(
            side_effect=lambda: feedback_received_event.wait(timeout=2)
        )

        # Start hook
        hook_thread = threading.Thread(
            target=hitl_hook_provider._on_before_tool_call,
            args=(tool_event,),
        )
        hook_thread.start()

        time.sleep(0.1)

        # Send invalid stdin commands
        invalid_lines = [
            "invalid json\n",
            "__HITL_COMMAND__{not valid}__HITL_COMMAND_END__\n",
            "TEST_STDIN_WORKS\n",
        ]

        for line in invalid_lines:
            feedback_handler._process_input_line(line)

        # Send valid feedback
        valid_command = {
            "type": "submit_feedback",
            "feedback_type": "correction",
            "content": "Valid feedback",
            "tool_id": "error_001",
        }
        valid_line = f"__HITL_COMMAND__{json.dumps(valid_command)}__HITL_COMMAND_END__\n"
        feedback_handler._process_input_line(valid_line)

        feedback_received_event.set()
        hook_thread.join(timeout=3)

        # Verify workflow completed successfully
        assert feedback_manager.state == HITLState.ACTIVE
        feedback = feedback_manager.get_pending_feedback("error_001")
        assert feedback.content == "Valid feedback"

    def test_concurrent_pause_requests(
        self, feedback_manager, hitl_hook_provider
    ):
        """Test handling of concurrent pause requests."""
        # Configure short timeout
        feedback_manager.auto_pause_timeout = 1

        # Create two destructive events
        event1 = Mock(spec=BeforeToolInvocationEvent)
        event1.tool_use = {
            "name": "shell",
            "toolUseId": "concurrent_001",
            "input": {"command": "rm file1"},
        }

        event2 = Mock(spec=BeforeToolInvocationEvent)
        event2.tool_use = {
            "name": "shell",
            "toolUseId": "concurrent_002",
            "input": {"command": "rm file2"},
        }

        # Start both hooks (second should wait for first to complete)
        thread1 = threading.Thread(
            target=hitl_hook_provider._on_before_tool_call,
            args=(event1,),
        )
        thread2 = threading.Thread(
            target=hitl_hook_provider._on_before_tool_call,
            args=(event2,),
        )

        thread1.start()
        time.sleep(0.05)  # Ensure first starts before second
        thread2.start()

        # Wait for both to complete (via timeout)
        thread1.join(timeout=3)
        thread2.join(timeout=3)

        # Both should have completed (via timeout auto-resume)
        assert feedback_manager.state == HITLState.ACTIVE
