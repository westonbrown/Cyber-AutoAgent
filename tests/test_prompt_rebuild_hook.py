#!/usr/bin/env python3
"""
Unit tests for the PromptRebuildHook trigger-based prompt rebuilding system.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.handlers.prompt_rebuild_hook import PromptRebuildHook


@pytest.fixture
def mock_callback_handler():
    """Create a mock callback handler."""
    handler = MagicMock()
    handler.current_step = 0
    handler.emitter = MagicMock()
    return handler


@pytest.fixture
def mock_memory():
    """Create a mock memory client."""
    memory = MagicMock()
    memory.search = MagicMock(return_value=[])
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
    """Set up operation folder structure."""
    from modules.handlers.utils import sanitize_target_name

    output_dir = Path(mock_config.output_dir)
    target_name = sanitize_target_name("test-target")
    operation_folder = output_dir / target_name / "OP_TEST123"
    operation_folder.mkdir(parents=True, exist_ok=True)

    # Create execution prompt file
    exec_prompt_path = operation_folder / "execution_prompt_optimized.txt"
    exec_prompt_path.write_text("Original execution prompt content")

    return operation_folder


def test_prompt_rebuild_hook_initialization(
    mock_callback_handler, mock_memory, mock_config
):
    """Test PromptRebuildHook initialization."""
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

    assert hook.target == "test-target"
    assert hook.objective == "test objective"
    assert hook.operation_id == "OP_TEST123"
    assert hook.max_steps == 100
    assert hook.module == "general"
    assert hook.rebuild_interval == 20
    assert hook.last_rebuild_step == 0
    assert hook.force_rebuild is False
    assert hook.last_phase is None


def test_prompt_rebuild_hook_register_hooks(
    mock_callback_handler, mock_memory, mock_config
):
    """Test hook registration."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
    )

    mock_registry = MagicMock()
    hook.register_hooks(mock_registry)

    # Verify callback was registered
    mock_registry.add_callback.assert_called_once()
    call_args = mock_registry.add_callback.call_args
    assert call_args[0][1] == hook.check_if_rebuild_needed


def test_prompt_rebuild_not_triggered_before_interval(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test that rebuild is not triggered before interval is reached."""
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

    # Set current step to 10 (before interval)
    mock_callback_handler.current_step = 10

    # Create mock event
    mock_event = MagicMock()
    mock_agent = MagicMock()
    mock_agent.system_prompt = "original prompt"
    mock_event.agent = mock_agent

    # Call check_if_rebuild_needed
    hook.check_if_rebuild_needed(mock_event)

    # Verify prompt was not changed
    assert mock_event.agent.system_prompt == "original prompt"


def test_prompt_rebuild_triggered_at_interval(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test that rebuild is triggered when interval is reached."""
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

    # Set current step to 20 (at interval)
    mock_callback_handler.current_step = 20

    # Create mock event
    mock_event = MagicMock()
    mock_agent = MagicMock()
    mock_agent.system_prompt = "original prompt"
    mock_event.agent = mock_agent

    # Mock get_system_prompt to return new prompt
    with patch("modules.prompts.get_system_prompt") as mock_get_prompt:
        mock_get_prompt.return_value = "rebuilt prompt"

        # Call check_if_rebuild_needed
        hook.check_if_rebuild_needed(mock_event)

    # Verify prompt was rebuilt with execution prompt appended
    expected_prompt = "rebuilt prompt\n\n## MODULE EXECUTION GUIDANCE\nOriginal execution prompt content"
    assert mock_event.agent.system_prompt == expected_prompt
    assert hook.last_rebuild_step == 20


def test_prompt_rebuild_triggered_by_force_flag(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test that rebuild is triggered when force_rebuild flag is set."""
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

    # Set current step to 5 (before interval)
    mock_callback_handler.current_step = 5

    # Set force_rebuild flag
    hook.set_force_rebuild()
    assert hook.force_rebuild is True

    # Create mock event
    mock_event = MagicMock()
    mock_agent = MagicMock()
    mock_agent.system_prompt = "original prompt"
    mock_event.agent = mock_agent

    # Mock get_system_prompt to return new prompt
    with patch("modules.prompts.get_system_prompt") as mock_get_prompt:
        mock_get_prompt.return_value = "rebuilt prompt"

        # Call check_if_rebuild_needed
        hook.check_if_rebuild_needed(mock_event)

    # Verify prompt was rebuilt and force flag cleared
    expected_prompt = "rebuilt prompt\n\n## MODULE EXECUTION GUIDANCE\nOriginal execution prompt content"
    assert mock_event.agent.system_prompt == expected_prompt
    assert hook.force_rebuild is False


def test_phase_change_detection(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test phase change detection."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
    )

    # First call - set initial phase to 1
    mock_memory.get_active_plan.return_value = None  # No active plan
    plan_data = {"memory": "Phase 1: Recon (active, 50% complete)"}
    mock_memory.search_memories.return_value = [plan_data]
    # This sets last_phase to 1 internally
    assert hook._phase_changed() is False

    # Second call - same phase (1)
    plan_data = {"memory": "Phase 1: Recon (active, 80% complete)"}
    mock_memory.search_memories.return_value = [plan_data]
    # Should not detect change since still phase 1
    assert hook._phase_changed() is False

    # Third call - phase changed to 2
    plan_data = {"memory": "Phase 2: Exploitation (active, 0% complete)"}
    mock_memory.search_memories.return_value = [plan_data]
    # Should detect change from 1 to 2
    assert hook._phase_changed() is True


def test_execution_prompt_modification_detection(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test execution prompt modification detection."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
    )

    exec_prompt_path = hook.exec_prompt_path
    assert exec_prompt_path.exists()

    # Initial check should prime the modification time
    assert hook._execution_prompt_modified() is False
    assert hook._execution_prompt_modified() is False

    # Modify the file and update mtime to be in the future
    # Make content long enough to pass validation (>100 chars)
    modified_content = "Modified execution prompt content" + " " * 100
    exec_prompt_path.write_text(modified_content)
    import os

    current_mtime = exec_prompt_path.stat().st_mtime
    os.utime(exec_prompt_path, (current_mtime + 10, current_mtime + 10))

    # Don't call _execution_prompt_modified() here as it will update last_mtime
    # Let check_if_rebuild_needed detect it instead

    # Ensure rebuild triggers via check_if_rebuild_needed even below interval
    mock_callback_handler.current_step = 3
    mock_event = MagicMock()
    mock_agent = MagicMock()
    mock_agent.system_prompt = "original"
    mock_event.agent = mock_agent

    with patch("modules.prompts.get_system_prompt") as mock_get_prompt:
        mock_get_prompt.return_value = "rebuilt due to prompt change"
        hook.check_if_rebuild_needed(mock_event)

    expected_prompt = f"rebuilt due to prompt change\n\n## MODULE EXECUTION GUIDANCE\n{modified_content.strip()}"
    assert mock_event.agent.system_prompt == expected_prompt
    assert hook.last_rebuild_step == 3


def test_query_memory_overview(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test memory overview query."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
    )

    # Mock memory list_memories results (preferred method)
    mock_memory.list_memories.return_value = [
        {"memory": "Critical finding", "metadata": {"severity": "critical"}},
        {"memory": "High finding 1", "metadata": {"severity": "high"}},
        {"memory": "High finding 2", "metadata": {"severity": "high"}},
        {"memory": "Medium finding", "metadata": {"severity": "medium"}},
        {"memory": "Low finding", "metadata": {"severity": "low"}},
    ]

    overview = hook._query_memory_overview()

    assert overview is not None
    assert overview["total_count"] == 5
    assert len(overview["sample"]) == 3  # First 3 findings
    assert overview["recent_summary"] is not None
    # Simplified version no longer counts severity levels


def test_query_plan_snapshot(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test plan snapshot query."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
    )

    # Mock memory - first check if get_active_plan exists
    # If it does, use that; otherwise fall back to search_memories
    mock_memory.get_active_plan.return_value = {
        "memory": "Phase 2: Exploitation (active, 45% complete)"
    }

    snapshot = hook._query_plan_snapshot()

    assert snapshot is not None
    assert "Phase 2" in snapshot
    assert "Exploitation" in snapshot
    assert "active" in snapshot
    assert "45%" in snapshot


def test_extract_current_phase(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test phase extraction from snapshot."""
    hook = PromptRebuildHook(
        callback_handler=mock_callback_handler,
        memory_instance=mock_memory,
        config=mock_config,
        target="test-target",
        objective="test objective",
        operation_id="OP_TEST123",
        max_steps=100,
    )

    # Test with valid snapshot
    snapshot = "Phase 2: Exploitation (active, 45% complete)"
    phase = hook._extract_current_phase(snapshot)
    assert phase == 2

    # Test with None
    phase = hook._extract_current_phase(None)
    assert phase is None

    # Test with invalid snapshot
    snapshot = "Invalid snapshot format"
    phase = hook._extract_current_phase(snapshot)
    assert phase is None


def test_rebuild_with_memory_and_plan_context(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test that rebuilt prompt includes fresh memory and plan context."""
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

    # Set up memory and plan data
    # Mock list_memories for memory overview
    mock_memory.list_memories.return_value = [
        {"memory": "Critical finding", "metadata": {"severity": "critical"}},
        {"memory": "High finding", "metadata": {"severity": "high"}},
    ]
    # Mock search_memories for plan snapshot
    mock_memory.search_memories.return_value = [
        {"memory": "Phase 2: Exploitation (active, 30% complete)"}
    ]

    # Set current step to trigger rebuild
    mock_callback_handler.current_step = 20

    # Create mock event
    mock_event = MagicMock()
    mock_agent = MagicMock()
    mock_agent.system_prompt = "original prompt"
    mock_event.agent = mock_agent

    # Mock get_system_prompt
    with patch("modules.prompts.get_system_prompt") as mock_get_prompt:
        mock_get_prompt.return_value = "rebuilt prompt with context"

        # Call check_if_rebuild_needed
        hook.check_if_rebuild_needed(mock_event)

        # Verify get_system_prompt was called with context
        mock_get_prompt.assert_called_once()
        call_kwargs = mock_get_prompt.call_args[1]
        assert call_kwargs["target"] == "test-target"
        assert call_kwargs["objective"] == "test objective"
        assert call_kwargs["operation_id"] == "OP_TEST123"
        assert call_kwargs["current_step"] == 20
        assert call_kwargs["max_steps"] == 100
        assert call_kwargs["memory_overview"] is not None
        assert call_kwargs["plan_snapshot"] is not None


def test_rebuild_handles_errors_gracefully(
    mock_callback_handler, mock_memory, mock_config, setup_operation_folder
):
    """Test that rebuild errors don't crash the operation."""
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

    # Set current step to trigger rebuild
    mock_callback_handler.current_step = 20

    # Create mock event
    mock_event = MagicMock()
    mock_agent = MagicMock()
    mock_agent.system_prompt = "original prompt"
    mock_event.agent = mock_agent

    # Mock get_system_prompt to raise an error
    with patch("modules.prompts.get_system_prompt") as mock_get_prompt:
        mock_get_prompt.side_effect = Exception("Rebuild failed")

        # Call check_if_rebuild_needed - should not raise
        hook.check_if_rebuild_needed(mock_event)

    # Verify prompt was not changed
    assert mock_event.agent.system_prompt == "original prompt"
