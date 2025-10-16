#!/usr/bin/env python3
import types

from modules.agents import cyber_autoagent as ca


def test_tool_router_maps_unknown_tool_to_shell():
    # Prepare hook with a sentinel shell tool
    sentinel_shell = object()
    hook = ca._ToolRouterHook(shell_tool=sentinel_shell)  # type: ignore[attr-defined]

    # Minimal event carrying an unknown tool name
    event = types.SimpleNamespace()
    event.selected_tool = None
    event.tool_use = {
        "name": "nmap",
        "input": {"options": "-sC -sV", "target": "http://example.com:8080"},
    }

    # Invoke hook
    hook._on_before_tool(event)  # type: ignore[attr-defined]

    # Verify that shell was selected and command composed
    assert event.selected_tool is sentinel_shell
    cmd = event.tool_use.get("input", {}).get("command", "")
    assert isinstance(cmd, str) and cmd.startswith("nmap")
    assert "-sC" in cmd and "-sV" in cmd and "http://example.com:8080" in cmd


def test_tool_router_keeps_registered_tools_unchanged():
    sentinel_shell = object()
    hook = ca._ToolRouterHook(shell_tool=sentinel_shell)  # type: ignore[attr-defined]

    event = types.SimpleNamespace()
    event.selected_tool = object()  # Simulate already-resolved tool
    event.tool_use = {"name": "shell", "input": {"command": "echo hi"}}

    hook._on_before_tool(event)  # should no-op

    # selected_tool remains unchanged (not replaced with sentinel)
    assert event.selected_tool is not sentinel_shell
    # input remains as-is
    assert event.tool_use["input"]["command"] == "echo hi"