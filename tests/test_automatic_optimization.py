#!/usr/bin/env python3
"""Unit tests for automatic prompt optimization in PromptRebuildHook."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from modules.handlers.prompt_rebuild_hook import PromptRebuildHook


@pytest.fixture
def mock_callback_handler():
    """Create a mock callback handler."""
    handler = MagicMock()
    handler.current_step = 20  # Set to trigger optimization
    handler.emitter = MagicMock()
    return handler


@pytest.fixture
def mock_memory():
    """Create a mock memory client with test data."""
    memory = MagicMock()

    # Mock successful findings for pattern extraction
    memory.search.return_value = [
        {
            "memory": "[VULNERABILITY] SQL Injection [WHERE] /login endpoint [IMPACT] Authentication bypass",
            "metadata": {"severity": "critical", "validation_status": "confirmed"}
        },
        {
            "memory": "[VULNERABILITY] SSTI [WHERE] Template rendering [IMPACT] Remote code execution",
            "metadata": {"severity": "high", "validation_status": "confirmed"}
        },
        {
            "memory": "[BLOCKED] xss at /search",
            "metadata": {"category": "adaptation"}
        },
        {
            "memory": "[BLOCKED] xss at /comment",
            "metadata": {"category": "adaptation"}
        },
        {
            "memory": "[BLOCKED] xss at /profile",
            "metadata": {"category": "adaptation"}
        }
    ]

    return memory


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config object."""
    config = MagicMock()
    config.output_dir = str(tmp_path / "outputs")
    config.provider = "ollama"
    config.target = "test-target"
    config.module = "general"
    return config


@pytest.fixture
def setup_operation_folder(tmp_path, mock_config):
    """Set up operation folder structure with execution prompt."""
    from modules.handlers.utils import sanitize_target_name

    output_dir = Path(mock_config.output_dir)
    target_name = sanitize_target_name("test-target")
    operation_folder = output_dir / target_name / "OP_TEST123"
    operation_folder.mkdir(parents=True, exist_ok=True)

    # Create execution prompt file with test content
    exec_prompt_path = operation_folder / "execution_prompt_optimized.txt"
    exec_prompt_path.write_text("""
# Test Execution Prompt

## Attack Vectors
- Try SQL injection on all input fields
- Test for XSS in search and comment forms
- Look for SSTI in template rendering
- Attempt path traversal on file parameters
""")

    return operation_folder


def test_auto_optimization_triggers_at_step_20(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test that auto-optimization triggers at step 20."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
        module="general",
        rebuild_interval=20,
    )

    # Set current step to 20
    mock_callback_handler.current_step = 20

    # Create mock event
    mock_event = MagicMock()
    mock_agent = MagicMock()
    mock_agent.system_prompt = "original prompt"
    mock_event.agent = mock_agent

    # Mock the optimization methods
    with patch.object(hook, '_auto_optimize_execution_prompt') as mock_optimize:
        with patch('modules.prompts.get_system_prompt') as mock_get_prompt:
            mock_get_prompt.return_value = "rebuilt prompt"

            # Call check_if_rebuild_needed
            hook.check_if_rebuild_needed(mock_event)

            # Verify auto-optimization was called
            mock_optimize.assert_called_once()


def test_auto_optimization_extracts_patterns(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test that auto-optimization correctly extracts patterns from memory."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
    )

    # Test pattern extraction
    patterns = hook._extract_learned_patterns()
    assert "SQL Injection" in patterns

    # Test dead end identification
    mock_memory.search.return_value = [
        {"memory": "[BLOCKED] xss attempt 1", "metadata": {"category": "adaptation"}},
        {"memory": "[BLOCKED] xss attempt 2", "metadata": {"category": "adaptation"}},
        {"memory": "[BLOCKED] xss attempt 3", "metadata": {"category": "adaptation"}},
    ]
    dead_ends = hook._identify_dead_ends()
    assert "xss" in dead_ends

    # Test working tactics identification
    mock_memory.search.return_value = [
        {
            "memory": "Found SSTI vulnerability allowing code execution",
            "metadata": {"severity": "critical", "validation_status": "confirmed"}
        },
        {
            "memory": "SQL injection successful with UNION SELECT",
            "metadata": {"severity": "high", "validation_status": "confirmed"}
        }
    ]
    tactics = hook._identify_working_tactics()
    assert "ssti" in tactics or "sql_injection" in tactics


def test_auto_optimization_rewrites_prompt(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test that auto-optimization actually rewrites the execution prompt."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
    )

    # Mock the LLM rewrite function to return optimized content
    with patch('modules.tools.prompt_optimizer._llm_rewrite_execution_prompt') as mock_rewrite:
        mock_rewrite.return_value = """
# Optimized Execution Prompt

## Focus Areas (Working)
- SSTI in template rendering - confirmed RCE capability
- SQL injection on login - authentication bypass confirmed

## Avoid (Dead Ends)
- XSS attempts blocked by WAF (failed 3+ times)
"""

        # Set up memory responses
        mock_memory.search.side_effect = [
            # For pattern extraction
            [{"memory": "[VULNERABILITY] SSTI confirmed", "metadata": {"severity": "critical"}}],
            # For dead ends
            [
                {"memory": "[BLOCKED] xss test 1"},
                {"memory": "[BLOCKED] xss test 2"},
                {"memory": "[BLOCKED] xss test 3"}
            ],
            # For working tactics
            [{"memory": "ssti works", "metadata": {"validation_status": "confirmed"}}]
        ]

        # Call auto-optimization
        hook._auto_optimize_execution_prompt()

        # Verify the prompt was rewritten
        mock_rewrite.assert_called_once()

        # Check that the optimized prompt was saved
        optimized_content = hook.exec_prompt_path.read_text()
        assert "Focus Areas (Working)" in optimized_content
        assert "Avoid (Dead Ends)" in optimized_content


def test_auto_optimization_handles_no_patterns_gracefully(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test that auto-optimization handles cases with no clear patterns."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
    )

    # Mock empty memory responses
    mock_memory.search.return_value = []

    # Should not crash and should log appropriately
    hook._auto_optimize_execution_prompt()

    # Verify prompt wasn't changed
    original_content = hook.exec_prompt_path.read_text()
    assert "Test Execution Prompt" in original_content


def test_auto_optimization_at_multiple_intervals(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test that auto-optimization triggers at steps 20, 40, 60, etc."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
        rebuild_interval=20,
    )

    mock_event = MagicMock()
    mock_agent = MagicMock()
    mock_agent.system_prompt = "original prompt"
    mock_event.agent = mock_agent

    with patch.object(hook, '_auto_optimize_execution_prompt') as mock_optimize:
        with patch('modules.prompts.get_system_prompt') as mock_get_prompt:
            mock_get_prompt.return_value = "rebuilt prompt"

            # Test at step 20
            mock_callback_handler.current_step = 20
            hook.check_if_rebuild_needed(mock_event)
            assert mock_optimize.call_count == 1
            hook.last_rebuild_step = 20

            # Test at step 40
            mock_callback_handler.current_step = 40
            hook.check_if_rebuild_needed(mock_event)
            assert mock_optimize.call_count == 2
            hook.last_rebuild_step = 40

            # Test at step 60
            mock_callback_handler.current_step = 60
            hook.check_if_rebuild_needed(mock_event)
            assert mock_optimize.call_count == 3


def test_auto_optimization_error_handling(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test that auto-optimization handles errors gracefully."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
    )

    # Mock LLM rewrite to raise an error
    with patch('modules.tools.prompt_optimizer._llm_rewrite_execution_prompt') as mock_rewrite:
        mock_rewrite.side_effect = Exception("LLM service unavailable")

        # Should not crash the operation
        hook._auto_optimize_execution_prompt()

        # Verify original prompt is unchanged
        original_content = hook.exec_prompt_path.read_text()
        assert "Test Execution Prompt" in original_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])