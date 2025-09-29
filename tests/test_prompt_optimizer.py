import json
from pathlib import Path

import pytest

from modules.tools.prompt_optimizer import PromptOptimizerError, prompt_optimizer


def _setup_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "outputs" / "target" / "OP_TEST"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CYBER_OPERATION_ROOT", str(root))
    monkeypatch.setenv("CYBER_OPERATION_ID", "OP_TEST")
    monkeypatch.setenv("CYBER_TARGET_NAME", "target")
    # Clear cooldown tracking to avoid cross-test interference
    monkeypatch.delenv("CYBER_PROMPT_OVERLAY_LAST_STEP", raising=False)
    return root


def test_prompt_optimizer_apply_and_reset(tmp_path, monkeypatch):
    root = _setup_env(tmp_path, monkeypatch)

    result = prompt_optimizer(
        action="apply",
        overlay={"directives": ["Focus on consolidation"], "trajectory": {"mode": "consolidate"}},
        trigger="agent_reflection",
        current_step=12,
        expires_after_steps=10,
    )

    assert result["status"] == "success"
    assert result["action"] == "apply"

    overlay_path = root / "adaptive_prompt.json"
    assert overlay_path.exists()
    data = json.loads(overlay_path.read_text(encoding="utf-8"))
    assert data["payload"]["directives"] == ["Focus on consolidation"]
    assert data["origin"] == "agent_reflection"
    assert data["expires_after_steps"] == 10

    reset_result = prompt_optimizer(action="reset")
    assert reset_result["status"] == "success"
    assert reset_result["overlay"] is None
    assert not overlay_path.exists()


def test_prompt_optimizer_cooldown_enforced(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)

    prompt_optimizer(action="apply", overlay={"directives": ["initial"]}, current_step=5)

    with pytest.raises(PromptOptimizerError):
        prompt_optimizer(action="apply", overlay={"directives": ["too_soon"]}, current_step=10)

    # After reset, cooldown clears
    prompt_optimizer(action="reset")
    prompt_optimizer(action="apply", overlay={"directives": ["after_reset"]}, current_step=25)


def test_prompt_optimizer_view_and_update(tmp_path, monkeypatch):
    root = _setup_env(tmp_path, monkeypatch)

    view_result = prompt_optimizer(action="view")
    assert view_result["status"] == "success"
    assert view_result["overlay"] is None
    assert view_result.get("overlayActive") is False

    update_result = prompt_optimizer(
        action="update",
        prompt="Directive alpha\nDirective beta",
        current_step=9,
        trigger="reflection",
        note="initial rewrite",
    )
    assert update_result["action"] == "update"
    overlay_path = root / "adaptive_prompt.json"
    data = json.loads(overlay_path.read_text(encoding="utf-8"))
    assert data["payload"]["directives"] == ["Directive alpha", "Directive beta"]
    assert data["origin"] == "reflection"
    assert data["note"] == "initial rewrite"


def test_prompt_optimizer_add_context(tmp_path, monkeypatch):
    overlay_dir = _setup_env(tmp_path, monkeypatch)
    prompt_optimizer(action="apply", overlay={"directives": ["seed"]}, current_step=1)
    prompt_optimizer(
        action="add_context",
        context="expand attack surface focus",
        current_step=20,
        reviewer="operator",
    )

    overlay_path = overlay_dir / "adaptive_prompt.json"
    data = json.loads(overlay_path.read_text(encoding="utf-8"))
    assert data["payload"]["directives"] == ["seed", "expand attack surface focus"]
    assert data["reviewer"] == "operator"
    assert "history" in data


def test_prompt_optimizer_update_requires_prompt(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)
    with pytest.raises(PromptOptimizerError):
        prompt_optimizer(action="update", current_step=3)


def test_prompt_optimizer_optimize_execution_creates_optimized_file(tmp_path, monkeypatch):
    """Test that optimize_execution creates execution_prompt_optimized.txt"""
    root = _setup_env(tmp_path, monkeypatch)

    # Create a master execution prompt in the expected location
    module_dir = Path("src/modules/operation_plugins/general")
    module_dir.mkdir(parents=True, exist_ok=True)
    master_prompt = module_dir / "execution_prompt.txt"
    master_prompt.write_text("Original execution prompt\nTactic: SQLi\nTactic: XSS")

    # Create execution_prompt_optimized.txt in operation root
    optimized_path = root / "execution_prompt_optimized.txt"
    optimized_path.write_text("Original execution prompt\nTactic: SQLi\nTactic: XSS")

    # Call optimize_execution
    from unittest.mock import patch
    with patch("modules.tools.prompt_optimizer._llm_rewrite_execution_prompt") as mock_rewrite:
        mock_rewrite.return_value = "Optimized prompt\nFocus: File Upload\nAvoid: SQLi (blocked by WAF)"

        result = prompt_optimizer(
            action="optimize_execution",
            learned_patterns="SQLi blocked by WAF. File upload works at /admin/upload",
            remove_dead_ends=["sql_injection"],
            focus_areas=["file_upload"]
        )

    assert result["status"] == "success"
    assert result["action"] == "optimize_execution"
    assert optimized_path.exists()

    # Verify optimized content
    optimized_content = optimized_path.read_text()
    assert "Optimized prompt" in optimized_content
    assert "File Upload" in optimized_content


def test_prompt_optimizer_optimize_execution_uses_llm(tmp_path, monkeypatch):
    """Test that optimize_execution uses LLM to rewrite prompt"""
    root = _setup_env(tmp_path, monkeypatch)

    # Create optimized prompt file
    optimized_path = root / "execution_prompt_optimized.txt"
    optimized_path.write_text("Current execution prompt with SQLi and XSS tactics")

    from unittest.mock import patch, MagicMock

    # Mock the LLM rewriter
    with patch("modules.tools.prompt_optimizer._llm_rewrite_execution_prompt") as mock_rewrite:
        mock_rewrite.return_value = "Rewritten prompt focusing on file upload"

        result = prompt_optimizer(
            action="optimize_execution",
            learned_patterns="File upload vulnerability found",
            remove_dead_ends=["sql_injection", "xss"],
            focus_areas=["file_upload"]
        )

        # Verify LLM was called with correct arguments
        mock_rewrite.assert_called_once()
        call_kwargs = mock_rewrite.call_args.kwargs
        assert "Current execution prompt" in call_kwargs["current_prompt"]
        assert "File upload vulnerability" in call_kwargs["learned_patterns"]
        assert "sql_injection" in call_kwargs["remove_tactics"]
        assert "file_upload" in call_kwargs["focus_tactics"]


def test_prompt_optimizer_optimize_execution_preserves_master(tmp_path, monkeypatch):
    """Test that optimize_execution doesn't modify master prompt"""
    root = _setup_env(tmp_path, monkeypatch)

    # Create master prompt
    module_dir = Path("src/modules/operation_plugins/general")
    module_dir.mkdir(parents=True, exist_ok=True)
    master_prompt = module_dir / "execution_prompt.txt"
    original_master_content = "Master execution prompt\nUnmodified content"
    master_prompt.write_text(original_master_content)

    # Create operation-specific optimized prompt
    optimized_path = root / "execution_prompt_optimized.txt"
    optimized_path.write_text("Operation-specific prompt")

    from unittest.mock import patch
    with patch("modules.tools.prompt_optimizer._llm_rewrite_execution_prompt") as mock_rewrite:
        mock_rewrite.return_value = "Optimized operation-specific prompt"

        prompt_optimizer(
            action="optimize_execution",
            learned_patterns="Target-specific learning",
            remove_dead_ends=["tactic_a"],
            focus_areas=["tactic_b"]
        )

    # Verify master is unchanged
    assert master_prompt.read_text() == original_master_content
    # Verify operation prompt was optimized
    assert optimized_path.read_text() == "Optimized operation-specific prompt"


def test_prompt_optimizer_optimize_execution_handles_missing_file(tmp_path, monkeypatch):
    """Test optimize_execution handles missing execution_prompt_optimized.txt"""
    root = _setup_env(tmp_path, monkeypatch)

    # Don't create execution_prompt_optimized.txt

    result = prompt_optimizer(
        action="optimize_execution",
        learned_patterns="Some patterns",
        remove_dead_ends=["tactic_a"],
        focus_areas=["tactic_b"]
    )

    assert result["status"] == "error"
    assert "content" in result
    error_text = result["content"][0]["text"].lower()
    assert "not found" in error_text


def test_prompt_optimizer_optimize_execution_with_empty_lists(tmp_path, monkeypatch):
    """Test optimize_execution with empty remove_dead_ends and focus_areas"""
    root = _setup_env(tmp_path, monkeypatch)

    optimized_path = root / "execution_prompt_optimized.txt"
    optimized_path.write_text("Current prompt")

    from unittest.mock import patch
    with patch("modules.tools.prompt_optimizer._llm_rewrite_execution_prompt") as mock_rewrite:
        mock_rewrite.return_value = "Optimized prompt"

        result = prompt_optimizer(
            action="optimize_execution",
            learned_patterns="General learning without specific tactics",
            remove_dead_ends=[],
            focus_areas=[]
        )

    assert result["status"] == "success"
    mock_rewrite.assert_called_once()
    call_kwargs = mock_rewrite.call_args[1]
    assert call_kwargs["remove_tactics"] == []
    assert call_kwargs["focus_tactics"] == []
