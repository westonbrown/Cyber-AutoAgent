#!/usr/bin/env python3
"""
Test the actual handler flow in the container.
"""

import sys
import os
sys.path.insert(0, '/app/src')

from modules.handlers.react.react_bridge_handler import ReactBridgeHandler
from modules.handlers.react.tool_emitters import ToolEventEmitter
import json

# Create a test handler
handler = ReactBridgeHandler(max_steps=50)

print(f"Handler initialized with max_steps={handler.max_steps}")
print(f"Current step: {handler.current_step}")
print("")

# Test 1: Process a tool announcement
print("="*60)
print("TEST 1: Tool announcement for quick_recon")
print("="*60)

tool_use = {
    "name": "quick_recon",
    "toolUseId": "test-quick-recon",
    "input": {"target": "testphp.vulnweb.com"}
}

print(f"Before: current_step={handler.current_step}, announced_tools={handler.announced_tools}")
handler._process_tool_announcement(tool_use)
print(f"After: current_step={handler.current_step}, announced_tools={handler.announced_tools}")

# Test 2: Check if tool-specific events are emitted
print("\n" + "="*60)
print("TEST 2: Tool-specific event emission")
print("="*60)

# Create a mock emitter to capture events
captured_events = []

def mock_emit(event):
    captured_events.append(event)
    print(f"  Emitted: {event}")

emitter = ToolEventEmitter(mock_emit)

# Test different tools
test_tools = [
    ("quick_recon", {"target": "testphp.vulnweb.com"}),
    ("shell", {"commands": ["nmap -sT testphp.vulnweb.com"]}),
    ("mem0_memory", {"action": "store", "content": "Test finding"}),
    ("unknown_tool", {"param1": "value1", "param2": "value2"}),
    ("shell", {}),  # Empty input
    ("shell", None),  # None input
]

for tool_name, tool_input in test_tools:
    captured_events.clear()
    print(f"\nTesting {tool_name} with input: {tool_input}")
    emitter.emit_tool_specific_events(tool_name, tool_input or {})
    print(f"  Events captured: {len(captured_events)}")

# Test 3: Check step progression
print("\n" + "="*60)
print("TEST 3: Step progression")
print("="*60)

# Simulate processing messages with tool usage
message_with_tool = {
    "role": "assistant",
    "content": [
        {
            "type": "tool_use",
            "toolUse": {
                "name": "shell",
                "toolUseId": "test-shell-1",
                "input": {"commands": ["ls -la"]}
            }
        }
    ]
}

print(f"Before message: current_step={handler.current_step}")
handler._process_message(message_with_tool)
print(f"After message: current_step={handler.current_step}")

# Check if we hit step limit
print(f"\nShould stop? {handler.should_stop()}")
print(f"Has reached limit? {handler.has_reached_limit()}")

# Test 4: Check validation
print("\n" + "="*60)
print("TEST 4: Input validation")
print("="*60)

test_inputs = [
    {},
    {"key": "value"},
    None,
    "",
    "string",
]

for inp in test_inputs:
    result = handler._is_valid_input(inp)
    print(f"  _is_valid_input({inp}) = {result}")