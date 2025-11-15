#!/usr/bin/env python3

from pathlib import Path
from unittest.mock import patch

from modules.prompts.factory import ModulePromptLoader


def test_module_prompt_loader_discovers_tools(tmp_path, monkeypatch):
    # Create fake operation_plugins structure with a tool
    plugins_dir = tmp_path / "operation_plugins" / "general" / "tools"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "__init__.py").write_text("\n")
    (plugins_dir / "quick_recon.py").write_text("# tool\n")

    loader = ModulePromptLoader()
    # Point the loader at our temp plugins dir
    monkeypatch.setattr(loader, "plugins_dir", tmp_path / "operation_plugins")

    tools = loader.discover_module_tools("general")
    names = [Path(p).name for p in tools]
    assert "quick_recon.py" in names
    assert "__init__.py" not in names


def test_module_prompt_loader_load_module_report_prompt(tmp_path, monkeypatch):
    # Create a report_prompt.md for module
    module_dir = tmp_path / "operation_plugins" / "general"
    module_dir.mkdir(parents=True)
    (module_dir / "report_prompt.md").write_text("Report Guidance\n")

    loader = ModulePromptLoader()
    monkeypatch.setattr(loader, "plugins_dir", tmp_path / "operation_plugins")

    content = loader.load_module_report_prompt("general")
    assert "Report Guidance" in content


@patch("modules.prompts.factory.load_prompt_template")
@patch("pathlib.Path.exists")
def test_module_prompt_loader_execution_prompt_candidates(mock_exists, mock_loader):
    # Mock that the file doesn't exist in operation_plugins so it falls back to templates
    mock_exists.return_value = False

    # Simulate template availability only for the second candidate
    def fake_load(name: str) -> str:
        if name == "general_execution_prompt.md":
            return ""  # first candidate missing
        if name == "module_general_execution_prompt.md":
            return "EXEC2"  # second candidate present
        if name == "general.md":
            return ""  # third candidate missing
        return ""

    mock_loader.side_effect = fake_load

    loader = ModulePromptLoader()
    content = loader.load_module_execution_prompt("general")
    assert content == "EXEC2"


def test_module_prompt_loader_prioritizes_operation_optimized_prompt(
    tmp_path, monkeypatch
):
    """Test that operation-specific optimized prompt takes priority."""
    # Create operation folder with optimized prompt
    operation_root = tmp_path / "outputs" / "target" / "OP_TEST"
    operation_root.mkdir(parents=True)
    optimized_path = operation_root / "execution_prompt_optimized.txt"
    optimized_path.write_text("Optimized execution prompt for this operation")

    # Create master prompt
    plugins_dir = tmp_path / "operation_plugins" / "general"
    plugins_dir.mkdir(parents=True)
    master_path = plugins_dir / "execution_prompt.txt"
    master_path.write_text("Master execution prompt")

    loader = ModulePromptLoader()
    monkeypatch.setattr(loader, "plugins_dir", tmp_path / "operation_plugins")

    # Load with operation_root - should get optimized version
    content = loader.load_module_execution_prompt(
        "general", operation_root=str(operation_root)
    )
    assert content == "Optimized execution prompt for this operation"
    assert loader.last_loaded_execution_prompt_source == f"optimized:{optimized_path}"


def test_module_prompt_loader_falls_back_to_master_when_no_optimized(
    tmp_path, monkeypatch
):
    """Test fallback to master when optimized prompt doesn't exist."""
    # Create operation folder WITHOUT optimized prompt
    operation_root = tmp_path / "outputs" / "target" / "OP_TEST"
    operation_root.mkdir(parents=True)

    # Create master prompt
    plugins_dir = tmp_path / "operation_plugins" / "general"
    plugins_dir.mkdir(parents=True)
    master_path = plugins_dir / "execution_prompt.md"
    master_path.write_text("Master execution prompt")

    loader = ModulePromptLoader()
    monkeypatch.setattr(loader, "plugins_dir", tmp_path / "operation_plugins")

    # Load with operation_root - should fall back to master
    content = loader.load_module_execution_prompt(
        "general", operation_root=str(operation_root)
    )
    assert content == "Master execution prompt"
    assert loader.last_loaded_execution_prompt_source == str(master_path)


def test_module_prompt_loader_handles_invalid_operation_root(tmp_path, monkeypatch):
    """Test handling of invalid operation_root path."""
    # Create master prompt
    plugins_dir = tmp_path / "operation_plugins" / "general"
    plugins_dir.mkdir(parents=True)
    master_path = plugins_dir / "execution_prompt.md"
    master_path.write_text("Master execution prompt")

    loader = ModulePromptLoader()
    monkeypatch.setattr(loader, "plugins_dir", tmp_path / "operation_plugins")

    # Load with non-existent operation_root - should fall back to master
    content = loader.load_module_execution_prompt(
        "general", operation_root="/nonexistent/path"
    )
    assert content == "Master execution prompt"


def test_module_prompt_loader_handles_empty_optimized_file(tmp_path, monkeypatch):
    """Test handling of empty optimized prompt file."""
    # Create operation folder with EMPTY optimized prompt
    operation_root = tmp_path / "outputs" / "target" / "OP_TEST"
    operation_root.mkdir(parents=True)
    optimized_path = operation_root / "execution_prompt_optimized.txt"
    optimized_path.write_text("")  # Empty file

    # Create master prompt
    plugins_dir = tmp_path / "operation_plugins" / "general"
    plugins_dir.mkdir(parents=True)
    master_path = plugins_dir / "execution_prompt.md"
    master_path.write_text("Master execution prompt")

    loader = ModulePromptLoader()
    monkeypatch.setattr(loader, "plugins_dir", tmp_path / "operation_plugins")

    # Load with operation_root - should fall back to master since optimized is empty
    content = loader.load_module_execution_prompt(
        "general", operation_root=str(operation_root)
    )
    assert content == "Master execution prompt"


def test_module_prompt_loader_operation_root_none(tmp_path, monkeypatch):
    """Test that operation_root=None works correctly."""
    # Create master prompt
    plugins_dir = tmp_path / "operation_plugins" / "general"
    plugins_dir.mkdir(parents=True)
    master_path = plugins_dir / "execution_prompt.md"
    master_path.write_text("Master execution prompt")

    loader = ModulePromptLoader()
    monkeypatch.setattr(loader, "plugins_dir", tmp_path / "operation_plugins")

    # Load with operation_root=None - should use master
    content = loader.load_module_execution_prompt("general", operation_root=None)
    assert content == "Master execution prompt"
