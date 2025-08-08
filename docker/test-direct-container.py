#!/usr/bin/env python3
"""
Test script to run directly in the container to understand what's happening.
"""

import json
import sys
import time

# Mock tool announcement to see what happens
def test_tool_announcement():
    """Test what happens when we announce a tool."""
    
    # Test cases for different tools
    test_cases = [
        {
            "name": "quick_recon",
            "toolUseId": "test-1",
            "input": {"target": "testphp.vulnweb.com"}
        },
        {
            "name": "shell",
            "toolUseId": "test-2",
            "input": {"commands": ["nmap -sT testphp.vulnweb.com"]}
        },
        {
            "name": "mem0_memory",
            "toolUseId": "test-3",
            "input": {"action": "store", "content": "Test finding"}
        },
        {
            "name": "unknown_tool",
            "toolUseId": "test-4",
            "input": {"param1": "value1", "param2": "value2"}
        }
    ]
    
    for tool_use in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing tool: {tool_use['name']}")
        print(f"{'='*60}")
        
        # Simulate what the handler does
        tool_name = tool_use.get("name", "")
        tool_id = tool_use.get("toolUseId", "")
        tool_input = tool_use.get("input", {})
        
        print(f"Tool name: {tool_name}")
        print(f"Tool ID: {tool_id}")
        print(f"Tool input: {tool_input}")
        print(f"Tool input type: {type(tool_input)}")
        
        # Test serialization
        event = {
            "type": "tool_start",
            "tool_name": tool_name,
            "tool_input": tool_input
        }
        
        try:
            json_str = json.dumps(event)
            print(f"✓ Serialization successful")
            print(f"  Event: {json_str[:100]}...")
        except Exception as e:
            print(f"✗ Serialization failed: {e}")
            
            # Try with default=str
            try:
                json_str = json.dumps(event, default=str)
                print(f"✓ Serialization with default=str successful")
                print(f"  Event: {json_str[:100]}...")
            except Exception as e2:
                print(f"✗ Still failed: {e2}")

if __name__ == "__main__":
    print("Direct Container Tool Event Test")
    print("="*60)
    test_tool_announcement()