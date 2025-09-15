#!/usr/bin/env python3

import pathlib
from types import SimpleNamespace
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
    # Create a report_prompt.txt for module
    module_dir = tmp_path / "operation_plugins" / "general"
    module_dir.mkdir(parents=True)
    (module_dir / "report_prompt.txt").write_text("Report Guidance\n")

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
