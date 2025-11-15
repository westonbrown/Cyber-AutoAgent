#!/usr/bin/env python3
"""
Test to reproduce Issue #63 - strands_tools.shell has no attribute 'stream'

This test demonstrates the bug caused by incorrect import style.
"""

import pytest


def test_incorrect_import_causes_attributeerror():
    """Reproduce the bug: importing 'from strands_tools import shell' returns module"""
    # This is the WRONG way (current bug in cyber_autoagent.py line 18)
    from strands_tools import shell as shell_wrong

    # shell_wrong is a MODULE, not a tool function
    assert str(type(shell_wrong)) == "<class 'module'>", (
        "shell should be a module with wrong import"
    )
    assert not callable(shell_wrong), "Module is not callable"
    assert not hasattr(shell_wrong, "stream"), "Module doesn't have .stream attribute"

    # This would cause: AttributeError: module 'strands_tools.shell' has no attribute 'stream'
    with pytest.raises(AttributeError, match="has no attribute 'stream'"):
        shell_wrong.stream()


def test_correct_import_provides_stream():
    """Show the fix: importing 'from strands_tools.shell import shell' returns tool"""
    # This is the CORRECT way (the fix)
    from strands_tools.shell import shell as shell_correct

    # shell_correct is a DecoratedFunctionTool, not a module
    assert "DecoratedFunctionTool" in str(type(shell_correct)), (
        "shell should be a DecoratedFunctionTool"
    )
    assert callable(shell_correct), "Tool should be callable"
    assert hasattr(shell_correct, "stream"), "Tool should have .stream attribute"

    # This works correctly
    assert callable(shell_correct.stream), ".stream should be callable"


def test_all_tools_affected_by_wrong_import():
    """Show that ALL tools in line 18 are affected by this bug"""
    # Current WRONG imports (line 18 of cyber_autoagent.py)
    from strands_tools import (
        editor,
        http_request,
        load_tool,
        python_repl,
        shell,
        stop,
        swarm,
    )

    wrong_tools = {
        "editor": editor,
        "http_request": http_request,
        "load_tool": load_tool,
        "python_repl": python_repl,
        "shell": shell,
        "stop": stop,
        "swarm": swarm,
    }

    # ALL are modules (WRONG)
    for name, tool in wrong_tools.items():
        assert str(type(tool)) == "<class 'module'>", (
            f"{name} should be module with wrong import"
        )
        assert not callable(tool), f"{name} module should not be callable"


def test_all_tools_work_with_correct_import():
    """Show that ALL tools work correctly with proper import"""
    # CORRECT imports (the fix)
    from strands_tools.editor import editor
    from strands_tools.http_request import http_request
    from strands_tools.load_tool import load_tool
    from strands_tools.python_repl import python_repl
    from strands_tools.shell import shell
    from strands_tools.stop import stop
    from strands_tools.swarm import swarm

    correct_tools = {
        "editor": editor,
        "http_request": http_request,
        "load_tool": load_tool,
        "python_repl": python_repl,
        "shell": shell,
        "stop": stop,
        "swarm": swarm,
    }

    # ALL are DecoratedFunctionTools (CORRECT)
    for name, tool in correct_tools.items():
        if name in {"http_request", "python_repl", "stop"}:
            # These are plain functions in current strands_tools release
            assert callable(tool), f"{name} should be callable"
        else:
            assert "DecoratedFunctionTool" in str(type(tool)), (
                f"{name} should be DecoratedFunctionTool"
            )
            assert callable(tool), f"{name} tool should be callable"


def test_tools_with_stream_attribute():
    """Identify which tools have .stream() method"""
    from strands_tools.editor import editor
    from strands_tools.load_tool import load_tool
    from strands_tools.shell import shell
    from strands_tools.swarm import swarm

    # Tools that HAVE .stream attribute
    tools_with_stream = {
        "editor": editor,
        "load_tool": load_tool,
        "shell": shell,
        "swarm": swarm,
    }

    for name, tool in tools_with_stream.items():
        assert hasattr(tool, "stream"), f"{name} should have .stream attribute"
        assert callable(tool.stream), f"{name}.stream should be callable"


if __name__ == "__main__":
    print("Running bug reproduction tests...")
    print("\n1. Testing incorrect import (reproduces bug)...")
    test_incorrect_import_causes_attributeerror()
    print("   ✓ Confirmed: Wrong import causes AttributeError")

    print("\n2. Testing correct import (shows fix)...")
    test_correct_import_provides_stream()
    print("   ✓ Confirmed: Correct import provides .stream attribute")

    print("\n3. Testing all affected tools...")
    test_all_tools_affected_by_wrong_import()
    print("   ✓ Confirmed: ALL tools affected by wrong import")

    print("\n4. Testing all tools with correct import...")
    test_all_tools_work_with_correct_import()
    print("   ✓ Confirmed: ALL tools work with correct import")

    print("\n5. Identifying tools with .stream()...")
    test_tools_with_stream_attribute()
    print("   ✓ Confirmed: editor, load_tool, shell, swarm have .stream()")

    print("\n✅ All tests passed! Bug reproduced and fix validated.")
