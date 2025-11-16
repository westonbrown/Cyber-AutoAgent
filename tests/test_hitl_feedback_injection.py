"""Unit tests for HITL feedback injection hook with mocked agent behavior.

This test suite verifies that HITL feedback injection works correctly
without requiring a live LLM. It mocks the Strands SDK components to test:
1. Feedback injection into system prompt
2. Different feedback message formats
3. System prompt modification verification
4. Feedback clearing after injection
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from strands.hooks import BeforeModelCallEvent, HookRegistry

from modules.handlers.hitl.feedback_manager import FeedbackManager
from modules.handlers.hitl.feedback_injection_hook import HITLFeedbackInjectionHook
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
        operation_id="test_injection_op",
        emitter=mock_emitter,
    )


@pytest.fixture
def feedback_injection_hook(feedback_manager):
    """Create HITLFeedbackInjectionHook instance."""
    return HITLFeedbackInjectionHook(feedback_manager=feedback_manager)


@pytest.fixture
def mock_agent():
    """Create mock agent with system_prompt attribute."""
    agent = Mock()
    agent.system_prompt = "You are a helpful assistant. Follow user instructions carefully."
    return agent


@pytest.fixture
def mock_event(mock_agent):
    """Create mock BeforeModelCallEvent."""
    event = Mock(spec=BeforeModelCallEvent)
    event.agent = mock_agent
    return event


class TestFeedbackInjectionHook:
    """Tests for HITLFeedbackInjectionHook."""

    def test_hook_initialization(self, feedback_injection_hook, feedback_manager):
        """Test hook initializes with correct feedback manager."""
        assert feedback_injection_hook.feedback_manager == feedback_manager

    def test_hook_registration(self, feedback_injection_hook):
        """Test hook registers BeforeModelCallEvent callback."""
        registry = Mock(spec=HookRegistry)
        registry.add_callback = Mock()

        feedback_injection_hook.register_hooks(registry)

        # Verify callback was registered for BeforeModelCallEvent
        registry.add_callback.assert_called_once_with(
            BeforeModelCallEvent,
            feedback_injection_hook.inject_feedback,
        )

    def test_inject_feedback_no_pending(self, feedback_injection_hook, mock_event, mock_agent):
        """Test inject_feedback does nothing when no feedback pending."""
        original_prompt = mock_agent.system_prompt
        original_length = len(original_prompt)

        # Call inject_feedback with no pending feedback
        feedback_injection_hook.inject_feedback(mock_event)

        # System prompt should be unchanged
        assert mock_event.agent.system_prompt == original_prompt
        assert len(mock_event.agent.system_prompt) == original_length

    def test_inject_feedback_with_pending(
        self, feedback_injection_hook, feedback_manager, mock_event, mock_agent
    ):
        """Test inject_feedback appends feedback to system prompt when pending."""
        original_prompt = mock_agent.system_prompt
        original_length = len(original_prompt)

        # Submit feedback to manager
        feedback_manager.request_pause(
            tool_name="test_tool",
            tool_id="test_001",
            parameters={"param": "value"},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.CORRECTION,
            content="Please use a safer approach",
            tool_id="test_001",
        )

        # Verify feedback is pending
        assert feedback_manager.pending_feedback is not None

        # Call inject_feedback
        feedback_injection_hook.inject_feedback(mock_event)

        # Verify system prompt was modified
        new_prompt = mock_event.agent.system_prompt
        assert len(new_prompt) > original_length
        assert "HUMAN FEEDBACK RECEIVED" in new_prompt
        assert "Please use a safer approach" in new_prompt
        assert original_prompt in new_prompt  # Original prompt preserved

    def test_feedback_cleared_after_injection(
        self, feedback_injection_hook, feedback_manager, mock_event
    ):
        """Test feedback is cleared after injection to prevent duplicate injection."""
        # Submit feedback
        feedback_manager.request_pause(
            tool_name="test_tool",
            tool_id="test_002",
            parameters={},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.SUGGESTION,
            content="Consider alternative approach",
            tool_id="test_002",
        )

        # Verify feedback is pending before injection
        assert feedback_manager.pending_feedback is not None

        # Inject feedback
        feedback_injection_hook.inject_feedback(mock_event)

        # Verify feedback was cleared
        assert feedback_manager.pending_feedback is None

    def test_multiple_injections_no_duplicate(
        self, feedback_injection_hook, feedback_manager, mock_event, mock_agent
    ):
        """Test multiple inject_feedback calls don't duplicate feedback."""
        # Submit feedback
        feedback_manager.request_pause(
            tool_name="test_tool",
            tool_id="test_003",
            parameters={},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.CORRECTION,
            content="Use this specific command instead",
            tool_id="test_003",
        )

        # First injection
        feedback_injection_hook.inject_feedback(mock_event)
        first_prompt = mock_event.agent.system_prompt
        first_length = len(first_prompt)

        # Second injection (should be no-op since feedback cleared)
        feedback_injection_hook.inject_feedback(mock_event)
        second_prompt = mock_event.agent.system_prompt
        second_length = len(second_prompt)

        # Prompts should be identical (no duplicate injection)
        assert first_prompt == second_prompt
        assert first_length == second_length


class TestFeedbackMessageFormats:
    """Tests for different feedback message formats."""

    def test_correction_feedback_format(
        self, feedback_injection_hook, feedback_manager, mock_event
    ):
        """Test CORRECTION feedback is properly formatted."""
        feedback_manager.request_pause(
            tool_name="shell",
            tool_id="test_004",
            parameters={"command": "rm -rf /"},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.CORRECTION,
            content="Use 'rm -i' for interactive deletion",
            tool_id="test_004",
        )

        feedback_injection_hook.inject_feedback(mock_event)

        prompt = mock_event.agent.system_prompt
        assert "HUMAN FEEDBACK RECEIVED" in prompt
        assert "Type: correction" in prompt
        assert "Use 'rm -i' for interactive deletion" in prompt
        assert "incorporate this feedback" in prompt.lower()

    def test_suggestion_feedback_format(
        self, feedback_injection_hook, feedback_manager, mock_event
    ):
        """Test SUGGESTION feedback is properly formatted."""
        feedback_manager.request_pause(
            tool_name="scan",
            tool_id="test_005",
            parameters={"target": "192.168.1.1"},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.SUGGESTION,
            content="Consider scanning ports 80, 443, 8080 first",
            tool_id="test_005",
        )

        feedback_injection_hook.inject_feedback(mock_event)

        prompt = mock_event.agent.system_prompt
        assert "HUMAN FEEDBACK RECEIVED" in prompt
        assert "Type: suggestion" in prompt
        assert "Consider scanning ports 80, 443, 8080 first" in prompt

    def test_approval_feedback_format(
        self, feedback_injection_hook, feedback_manager, mock_event
    ):
        """Test APPROVAL feedback is properly formatted."""
        feedback_manager.request_pause(
            tool_name="exploit",
            tool_id="test_006",
            parameters={"vulnerability": "CVE-2024-1234"},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.APPROVAL,
            content="Approved - proceed with exploit",
            tool_id="test_006",
        )

        feedback_injection_hook.inject_feedback(mock_event)

        prompt = mock_event.agent.system_prompt
        assert "HUMAN FEEDBACK RECEIVED" in prompt
        assert "Type: approval" in prompt
        assert "Approved - proceed with exploit" in prompt

    def test_rejection_feedback_format(
        self, feedback_injection_hook, feedback_manager, mock_event
    ):
        """Test REJECTION feedback is properly formatted."""
        feedback_manager.request_pause(
            tool_name="delete_file",
            tool_id="test_007",
            parameters={"path": "/etc/passwd"},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.REJECTION,
            content="REJECTED - Do not proceed with this action",
            tool_id="test_007",
        )

        feedback_injection_hook.inject_feedback(mock_event)

        prompt = mock_event.agent.system_prompt
        assert "HUMAN FEEDBACK RECEIVED" in prompt
        assert "Type: rejection" in prompt
        assert "REJECTED - Do not proceed with this action" in prompt

    def test_long_feedback_content(
        self, feedback_injection_hook, feedback_manager, mock_event
    ):
        """Test long feedback content is fully injected."""
        long_feedback = """This is a very detailed piece of feedback.

        Step 1: First, analyze the vulnerability more carefully
        Step 2: Then, check for alternative exploitation methods
        Step 3: Consider the impact on system stability
        Step 4: Document all findings before proceeding
        Step 5: Only then should you attempt the exploit

        Remember to be cautious and thorough in your approach.
        """

        feedback_manager.request_pause(
            tool_name="exploit",
            tool_id="test_008",
            parameters={},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.CORRECTION,
            content=long_feedback,
            tool_id="test_008",
        )

        feedback_injection_hook.inject_feedback(mock_event)

        prompt = mock_event.agent.system_prompt
        assert long_feedback in prompt
        assert "Step 1:" in prompt
        assert "Step 5:" in prompt

    def test_special_characters_in_feedback(
        self, feedback_injection_hook, feedback_manager, mock_event
    ):
        """Test feedback with special characters is properly injected."""
        special_feedback = "Use command: curl -X POST 'http://test.com?q=1&r=2' -H 'Content-Type: application/json'"

        feedback_manager.request_pause(
            tool_name="http_request",
            tool_id="test_009",
            parameters={},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.CORRECTION,
            content=special_feedback,
            tool_id="test_009",
        )

        feedback_injection_hook.inject_feedback(mock_event)

        prompt = mock_event.agent.system_prompt
        assert special_feedback in prompt


class TestSystemPromptModification:
    """Tests for system prompt modification verification."""

    def test_system_prompt_preserves_original(
        self, feedback_injection_hook, feedback_manager, mock_event, mock_agent
    ):
        """Test that feedback injection preserves original system prompt."""
        original_prompt = "You are a security testing assistant."
        mock_agent.system_prompt = original_prompt

        feedback_manager.request_pause(
            tool_name="test",
            tool_id="test_010",
            parameters={},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.SUGGESTION,
            content="Test feedback",
            tool_id="test_010",
        )

        feedback_injection_hook.inject_feedback(mock_event)

        # Original prompt should still be present
        assert original_prompt in mock_event.agent.system_prompt

    def test_system_prompt_appends_with_newlines(
        self, feedback_injection_hook, feedback_manager, mock_event, mock_agent
    ):
        """Test that feedback is appended with proper newline separation."""
        original_prompt = "Original prompt"
        mock_agent.system_prompt = original_prompt

        feedback_manager.request_pause(
            tool_name="test",
            tool_id="test_011",
            parameters={},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.CORRECTION,
            content="Feedback content",
            tool_id="test_011",
        )

        feedback_injection_hook.inject_feedback(mock_event)

        new_prompt = mock_event.agent.system_prompt
        # Should have newlines between original and feedback
        assert "\n\n" in new_prompt

    def test_empty_system_prompt_handling(
        self, feedback_injection_hook, feedback_manager, mock_event, mock_agent
    ):
        """Test feedback injection works even with empty initial system prompt."""
        mock_agent.system_prompt = ""

        feedback_manager.request_pause(
            tool_name="test",
            tool_id="test_012",
            parameters={},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.SUGGESTION,
            content="Feedback for empty prompt",
            tool_id="test_012",
        )

        feedback_injection_hook.inject_feedback(mock_event)

        # Feedback should still be injected
        prompt = mock_event.agent.system_prompt
        assert "HUMAN FEEDBACK RECEIVED" in prompt
        assert "Feedback for empty prompt" in prompt

    def test_system_prompt_length_increases(
        self, feedback_injection_hook, feedback_manager, mock_event, mock_agent
    ):
        """Test that system prompt length increases after injection."""
        original_length = len(mock_agent.system_prompt)

        feedback_manager.request_pause(
            tool_name="test",
            tool_id="test_013",
            parameters={},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.CORRECTION,
            content="This feedback should increase prompt length",
            tool_id="test_013",
        )

        feedback_injection_hook.inject_feedback(mock_event)

        new_length = len(mock_event.agent.system_prompt)
        assert new_length > original_length

    def test_system_prompt_verification_logged(
        self, feedback_injection_hook, feedback_manager, mock_event, mock_agent, caplog
    ):
        """Test that system prompt verification is logged."""
        import logging

        caplog.set_level(logging.DEBUG)

        feedback_manager.request_pause(
            tool_name="test",
            tool_id="test_014",
            parameters={},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.SUGGESTION,
            content="Verify this gets logged",
            tool_id="test_014",
        )

        feedback_injection_hook.inject_feedback(mock_event)

        # Check that verification logging occurred
        # The hook includes verification logging with prompt length
        assert any("chars" in record.message.lower() for record in caplog.records)


class TestFeedbackInjectionIntegration:
    """Integration tests for feedback injection workflow."""

    def test_full_feedback_workflow_with_injection(
        self, feedback_injection_hook, feedback_manager, mock_event
    ):
        """Test complete workflow: pause -> feedback -> injection -> clear."""
        # Step 1: Request pause
        feedback_manager.request_pause(
            tool_name="shell",
            tool_id="workflow_001",
            parameters={"command": "test"},
            reason="testing_workflow",
        )
        assert feedback_manager.pending_tool is not None

        # Step 2: Submit feedback
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.CORRECTION,
            content="Workflow test feedback",
            tool_id="workflow_001",
        )
        assert feedback_manager.pending_feedback is not None

        # Step 3: Inject feedback (simulates BeforeModelCallEvent)
        feedback_injection_hook.inject_feedback(mock_event)

        # Step 4: Verify injection
        assert "Workflow test feedback" in mock_event.agent.system_prompt

        # Step 5: Verify feedback cleared
        assert feedback_manager.pending_feedback is None

    def test_sequential_feedback_injections(
        self, feedback_injection_hook, feedback_manager, mock_agent
    ):
        """Test multiple sequential feedback submissions and injections."""
        # First feedback cycle
        mock_event1 = Mock(spec=BeforeModelCallEvent)
        mock_event1.agent = mock_agent

        feedback_manager.request_pause(
            tool_name="tool1",
            tool_id="seq_001",
            parameters={},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.SUGGESTION,
            content="First feedback",
            tool_id="seq_001",
        )
        feedback_injection_hook.inject_feedback(mock_event1)

        first_prompt = mock_event1.agent.system_prompt
        assert "First feedback" in first_prompt

        # Second feedback cycle (new agent state for next invocation)
        mock_agent.system_prompt = first_prompt  # Carry over modified prompt
        mock_event2 = Mock(spec=BeforeModelCallEvent)
        mock_event2.agent = mock_agent

        feedback_manager.request_pause(
            tool_name="tool2",
            tool_id="seq_002",
            parameters={},
        )
        feedback_manager.submit_feedback(
            feedback_type=FeedbackType.CORRECTION,
            content="Second feedback",
            tool_id="seq_002",
        )
        feedback_injection_hook.inject_feedback(mock_event2)

        second_prompt = mock_event2.agent.system_prompt
        assert "First feedback" in second_prompt  # Previous feedback preserved
        assert "Second feedback" in second_prompt  # New feedback added

    def test_no_injection_without_pause(
        self, feedback_injection_hook, feedback_manager, mock_event, mock_agent
    ):
        """Test that direct feedback submission without pause doesn't inject."""
        original_prompt = mock_agent.system_prompt

        # Try to submit feedback without pause (should fail or be ignored)
        # The actual behavior depends on implementation, but injection shouldn't happen
        feedback_injection_hook.inject_feedback(mock_event)

        # Prompt should be unchanged
        assert mock_event.agent.system_prompt == original_prompt
