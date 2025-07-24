#!/usr/bin/env python3

import pytest
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.prompts.system import (
    get_system_prompt,
    _get_memory_context_guidance,
)


class TestMemoryContextGuidance:
    """Test memory context guidance generation"""

    def test_fresh_start_guidance(self):
        """Test memory context guidance for fresh start"""
        result = _get_memory_context_guidance(
            has_memory_path=False, has_existing_memories=False, memory_overview=None
        )

        assert "## MEMORY CONTEXT" in result
        assert "Starting fresh assessment with no previous context" in result
        assert "Do NOT check memory on fresh operations" in result
        assert "Begin with reconnaissance and target information gathering" in result
        assert "Store all findings immediately with category=\"finding\"" in result

    def test_memory_path_guidance(self):
        """Test memory context guidance with explicit memory path"""
        result = _get_memory_context_guidance(
            has_memory_path=True, has_existing_memories=False, memory_overview=None
        )

        assert "## MEMORY CONTEXT" in result
        assert "Continuing assessment with 0 existing memories" in result
        assert "**CRITICAL FIRST ACTION**: Load all memories with mem0_memory(action=\"list\", user_id=\"cyber_agent\")" in result
        assert "Analyze retrieved memories before taking any actions" in result
        assert "Avoid repeating work already completed" in result

    def test_existing_memories_guidance(self):
        """Test memory context guidance with existing memories"""
        result = _get_memory_context_guidance(
            has_memory_path=False, has_existing_memories=True, memory_overview=None
        )

        assert "## MEMORY CONTEXT" in result
        assert "Continuing assessment with 0 existing memories" in result
        assert "**CRITICAL FIRST ACTION**: Load all memories with mem0_memory(action=\"list\", user_id=\"cyber_agent\")" in result
        assert "Analyze retrieved memories before taking any actions" in result
        assert "Avoid repeating work already completed" in result

    def test_detailed_memory_overview_guidance(self):
        """Test memory context guidance with detailed memory overview"""
        memory_overview = {
            "has_memories": True,
            "total_count": 5,
            "categories": {"finding": 3, "general": 2},
            "recent_findings": [
                {
                    "content": "SQL injection found in login form",
                    "created_at": "2024-01-01",
                },
                {
                    "content": "XSS vulnerability in search parameter",
                    "created_at": "2024-01-02",
                },
            ],
        }

        result = _get_memory_context_guidance(
            has_memory_path=False,
            has_existing_memories=True,
            memory_overview=memory_overview,
        )

        assert "## MEMORY CONTEXT" in result
        assert "Continuing assessment with 5 existing memories" in result
        assert "**CRITICAL FIRST ACTION**: Load all memories with mem0_memory(action=\"list\", user_id=\"cyber_agent\")" in result
        assert "Analyze retrieved memories before taking any actions" in result
        assert "Avoid repeating work already completed" in result
        assert "Build upon previous discoveries" in result

    def test_empty_memory_overview(self):
        """Test memory context guidance with empty memory overview"""
        memory_overview = {
            "has_memories": False,
            "total_count": 0,
            "categories": {},
            "recent_findings": [],
        }

        result = _get_memory_context_guidance(
            has_memory_path=False,
            has_existing_memories=True,
            memory_overview=memory_overview,
        )

        assert "## MEMORY CONTEXT" in result
        assert "Continuing assessment with 0 existing memories" in result
        assert "**CRITICAL FIRST ACTION**: Load all memories with mem0_memory(action=\"list\", user_id=\"cyber_agent\")" in result


class TestMemoryAwareSystemPrompts:
    """Test memory-aware system prompt generation"""

    def test_system_prompt_fresh_start(self):
        """Test system prompt generation for fresh start"""
        result = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=50,
            operation_id="OP_20240101_120000",
            tools_context="",
            provider="bedrock",
            has_memory_path=False,
            has_existing_memories=False,
            memory_overview=None,
        )

        assert "## MEMORY CONTEXT" in result
        assert "Starting fresh assessment with no previous context" in result
        assert "Begin with reconnaissance and target information gathering" in result
        assert "Target: test.com" in result
        assert "Operation ID: OP_20240101_120000" in result
        assert "Budget: 50 steps" in result

    def test_system_prompt_with_memory_path(self):
        """Test system prompt generation with memory path"""
        result = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=50,
            operation_id="OP_20240101_120000",
            tools_context="",
            provider="bedrock",
            has_memory_path=True,
            has_existing_memories=False,
            memory_overview=None,
        )

        assert "## MEMORY CONTEXT" in result
        assert "Continuing assessment with 0 existing memories" in result
        assert "**CRITICAL FIRST ACTION**: Load all memories with mem0_memory(action=\"list\", user_id=\"cyber_agent\")" in result

    def test_system_prompt_with_existing_memories(self):
        """Test system prompt generation with existing memories"""
        result = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=50,
            operation_id="OP_20240101_120000",
            tools_context="",
            provider="bedrock",
            has_memory_path=False,
            has_existing_memories=True,
            memory_overview=None,
        )

        assert "## MEMORY CONTEXT" in result
        assert "Continuing assessment with 0 existing memories" in result
        assert "**CRITICAL FIRST ACTION**: Load all memories with mem0_memory(action=\"list\", user_id=\"cyber_agent\")" in result

    def test_system_prompt_with_detailed_memory_overview(self):
        """Test system prompt generation with detailed memory overview"""
        memory_overview = {
            "has_memories": True,
            "total_count": 8,
            "categories": {"finding": 5, "general": 3},
            "recent_findings": [
                {
                    "content": "Critical SQL injection vulnerability found in /admin/login endpoint",
                    "created_at": "2024-01-01",
                },
                {
                    "content": "RCE vulnerability discovered in file upload functionality",
                    "created_at": "2024-01-02",
                },
            ],
        }

        result = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=50,
            operation_id="OP_20240101_120000",
            tools_context="",
            provider="bedrock",
            has_memory_path=False,
            has_existing_memories=True,
            memory_overview=memory_overview,
        )

        assert "## MEMORY CONTEXT" in result
        assert "Continuing assessment with 8 existing memories" in result
        assert "**CRITICAL FIRST ACTION**: Load all memories with mem0_memory(action=\"list\", user_id=\"cyber_agent\")" in result
        assert "Analyze retrieved memories before taking any actions" in result

    def test_system_prompt_with_tools_context(self):
        """Test system prompt generation with tools context"""
        tools_context = """
## ENVIRONMENTAL CONTEXT

Professional tools discovered in your environment:
nmap, nikto, sqlmap, metasploit

Leverage these tools directly via shell. 
"""

        result = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=50,
            operation_id="OP_20240101_120000",
            tools_context=tools_context,
            provider="bedrock",
            has_memory_path=False,
            has_existing_memories=False,
            memory_overview=None,
        )

        assert "Professional tools discovered" in result
        assert "nmap, nikto, sqlmap, metasploit" in result
        assert "## MEMORY CONTEXT" in result

    def test_system_prompt_with_output_config(self):
        """Test system prompt generation with output configuration"""
        output_config = {
            "base_dir": "./outputs",
            "target_name": "test.com",
            "enable_unified_output": True,
        }

        result = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=50,
            operation_id="OP_20240101_120000",
            tools_context="",
            provider="bedrock",
            has_memory_path=False,
            has_existing_memories=False,
            output_config=output_config,
            memory_overview=None,
        )

        assert "## OUTPUT DIRECTORY STRUCTURE" in result
        assert "Base directory: ./outputs" in result
        assert "Target organization: ./outputs/test.com/" in result
        assert "## MEMORY CONTEXT" in result

    def test_system_prompt_server_variations(self):
        """Test system prompt generation with different server configurations"""
        # Test remote server
        result_remote = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=50,
            operation_id="OP_20240101_120000",
            provider="bedrock",
        )

        assert 'model_provider: "bedrock"' in result_remote

        # Test local server
        result_local = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=50,
            operation_id="OP_20240101_120000",
            provider="ollama",
        )

        assert 'model_provider: "ollama"' in result_local

    def test_system_prompt_urgency_levels(self):
        """Test system prompt generation with different urgency levels"""
        # High urgency (< 30 steps)
        result_high = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=20,
            operation_id="OP_20240101_120000",
        )

        assert "Budget: 20 steps" in result_high
        assert "Urgency: HIGH" in result_high

        # Medium urgency (>= 30 steps)
        result_medium = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=50,
            operation_id="OP_20240101_120000",
        )

        assert "Budget: 50 steps" in result_medium
        assert "Urgency: MEDIUM" in result_medium

    def test_system_prompt_memory_instructions_consistency(self):
        """Test consistency between memory context and dynamic instructions"""
        # With existing memories - should have consistent instructions
        result_with_memories = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=50,
            operation_id="OP_20240101_120000",
            has_existing_memories=True,
        )

        # Should have both memory context and dynamic instruction
        assert "**CRITICAL FIRST ACTION**: Load all memories with mem0_memory(action=\"list\", user_id=\"cyber_agent\")" in result_with_memories

        # Without existing memories - should have fresh start instructions
        result_fresh = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=50,
            operation_id="OP_20240101_120000",
            has_existing_memories=False,
        )

        assert "Starting fresh assessment with no previous context" in result_fresh
        assert "Begin with reconnaissance and target information gathering" in result_fresh


class TestMemoryAwarePromptIntegration:
    """Test integration of memory-aware prompts with system components"""

    def test_memory_overview_integration(self):
        """Test that memory overview data is properly integrated into prompts"""
        memory_overview = {
            "has_memories": True,
            "total_count": 3,
            "categories": {"finding": 2, "general": 1},
            "recent_findings": [
                {
                    "content": "Port 22 SSH open with weak credentials",
                    "created_at": "2024-01-01",
                },
            ],
        }

        result = get_system_prompt(
            target="vulnerable.com",
            objective="comprehensive penetration test",
            max_steps=100,
            operation_id="OP_20240101_120000",
            has_existing_memories=True,
            memory_overview=memory_overview,
        )

        # Verify all components are present
        assert "Target: vulnerable.com" in result
        assert "comprehensive penetration test" in result
        assert "OP_20240101_120000" in result
        assert "Continuing assessment with 3 existing memories" in result
        assert "**CRITICAL FIRST ACTION**: Load all memories with mem0_memory(action=\"list\", user_id=\"cyber_agent\")" in result

        # Verify memory-aware instructions are included
        assert "Analyze retrieved memories before taking any actions" in result
        assert "Avoid repeating work already completed" in result
        assert "Build upon previous discoveries" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
