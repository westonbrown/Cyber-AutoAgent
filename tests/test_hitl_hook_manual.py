#!/usr/bin/env python3

## COMMAND: uv run python tests/test_hitl_hook_manual.py 2>&1 | grep -A 2 "Full response"

"""Manual test for HITL feedback injection hook.

This test verifies that the feedback injection hook mechanism works correctly
by creating a minimal agent setup and testing feedback injection in isolation.

Run with: uv run python tests/test_hitl_hook_manual.py
"""

import sys
from unittest.mock import Mock

from strands import Agent
from strands.models.ollama import OllamaModel

# Import our HITL components
from modules.handlers.hitl.feedback_manager import FeedbackManager, FeedbackType
from modules.handlers.hitl.feedback_injection_hook import HITLFeedbackInjectionHook


def direct_print(msg: str):
    """Print directly to stdout, bypassing all logging."""
    sys.stdout.write(f"[TEST] {msg}\n")
    sys.stdout.flush()


def test_feedback_injection_hook():
    """Test that feedback injection hook modifies system prompt."""
    direct_print("=" * 80)
    direct_print("HITL Feedback Injection Hook - Isolation Test")
    direct_print("=" * 80)

    # Step 1: Create mock memory and emitter
    direct_print("\n1. Setting up mock components...")
    mock_memory = Mock()
    mock_emitter = Mock()

    # Step 2: Create feedback manager
    direct_print("2. Creating FeedbackManager...")
    feedback_manager = FeedbackManager(
        memory=mock_memory,
        operation_id="test_op_001",
        emitter=mock_emitter,
    )
    direct_print(
        f"   FeedbackManager created for operation: {feedback_manager.operation_id}"
    )

    # Step 3: Create feedback injection hook
    direct_print("3. Creating HITLFeedbackInjectionHook...")
    feedback_hook = HITLFeedbackInjectionHook(feedback_manager=feedback_manager)
    direct_print(f"   Hook initialized for operation: {feedback_manager.operation_id}")

    # Step 4: Create simple Ollama model
    direct_print("4. Creating Ollama model...")
    try:
        model = OllamaModel(
            model_id="llama3.2:3b",
            host="http://localhost:11434",
            temperature=0.7,
        )
        direct_print("   Ollama model created successfully")
    except Exception as e:
        direct_print(f"   ERROR: Failed to create Ollama model: {e}")
        direct_print("   Make sure Ollama is running and llama3.2:3b is available")
        return False

    # Step 5: Create agent with feedback hook
    direct_print("5. Creating Agent with feedback injection hook...")
    system_prompt = """You are a test assistant.
Your job is to respond to user messages briefly.
If you receive feedback, acknowledge it in your response."""

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[],  # No tools needed for this test
        hooks=[feedback_hook],  # Register our hook
    )
    direct_print("   Agent created with hook registered")

    # Step 6: First invocation - no feedback
    direct_print("\n6. Testing agent WITHOUT feedback...")
    direct_print("   Calling agent with: 'Hello, please introduce yourself'")

    result1 = agent("Hello, please introduce yourself")
    # Extract text from message content
    content1 = ""
    if hasattr(result1, "message") and result1.message:
        msg_content = result1.message.get("content", [])
        if msg_content and isinstance(msg_content, list):
            content1 = "".join(
                [block.get("text", "") for block in msg_content if "text" in block]
            )

    direct_print(f"   Agent response length: {len(content1)} chars")
    direct_print(f"   Response preview: {content1[:100] if content1 else '(empty)'}...")

    # Step 7: Submit feedback
    direct_print("\n7. Submitting HITL feedback...")
    feedback_content = "IMPORTANT: When you respond, start with 'FEEDBACK RECEIVED:' to confirm you saw this message."

    # Request pause (simulating HITL pause)
    feedback_manager.request_pause(
        tool_name="test_tool",
        tool_id="test_001",
        parameters={"test": "value"},
        reason="testing_feedback_injection",
    )
    direct_print("   Pause requested")

    # Submit feedback
    feedback_manager.submit_feedback(
        feedback_type=FeedbackType.SUGGESTION,
        content=feedback_content,
        tool_id="test_001",
    )
    direct_print(f"   Feedback submitted: {feedback_content[:50]}...")

    # Verify feedback is pending
    pending = feedback_manager.get_pending_feedback_message()
    if pending:
        direct_print(f"   ✓ Pending feedback detected ({len(pending)} chars)")
    else:
        direct_print("   ✗ ERROR: No pending feedback found!")
        return False

    # Step 8: Second invocation - WITH feedback
    direct_print("\n8. Testing agent WITH feedback...")
    direct_print("   Hook should inject feedback into system prompt before this call")
    direct_print("   Calling agent with: 'What is 2+2?'")

    result2 = agent("What is 2+2?")
    # Extract text from message content
    content2 = ""
    if hasattr(result2, "message") and result2.message:
        msg_content = result2.message.get("content", [])
        if msg_content and isinstance(msg_content, list):
            content2 = "".join(
                [block.get("text", "") for block in msg_content if "text" in block]
            )

    direct_print(f"   Agent response length: {len(content2)} chars")
    direct_print(f"   Full response:\n{content2}")

    # Step 9: Verify feedback was processed
    direct_print("\n9. Verifying feedback injection...")

    # Check if agent response contains our marker
    if "FEEDBACK RECEIVED" in content2.upper():
        direct_print("   ✓ SUCCESS: Agent acknowledged feedback!")
        direct_print("   This proves the hook injected feedback into system prompt")
        return True
    else:
        direct_print("   ✗ FAILURE: Agent did not acknowledge feedback")
        direct_print("   Hook may not have fired or feedback not injected correctly")

        # Debug: Check if feedback was cleared
        still_pending = feedback_manager.get_pending_feedback_message()
        if still_pending:
            direct_print("   ✗ Feedback still pending (hook didn't clear it)")
        else:
            direct_print(
                "   ! Feedback was cleared (hook may have fired but agent didn't see it)"
            )

        return False


if __name__ == "__main__":
    direct_print("\nStarting HITL feedback injection hook test...\n")

    try:
        success = test_feedback_injection_hook()

        direct_print("\n" + "=" * 80)
        if success:
            direct_print("TEST RESULT: PASSED ✓")
            direct_print("The feedback injection hook mechanism works correctly!")
            sys.exit(0)
        else:
            direct_print("TEST RESULT: FAILED ✗")
            direct_print("The feedback injection hook is NOT working as expected")
            sys.exit(1)

    except KeyboardInterrupt:
        direct_print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        direct_print(f"\n\nTEST ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
