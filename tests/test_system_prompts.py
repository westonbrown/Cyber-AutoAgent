#!/usr/bin/env python3

import os
import sys

import pytest

# Add src to path for imports


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.prompts import get_system_prompt


class TestGetSystemPrompt:
    """Test the get_system_prompt function"""

    def test_get_system_prompt_basic(self):
        """Test basic system prompt generation"""
        prompt = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
        )

        assert "test.com" in prompt
        assert "test objective" in prompt
        assert "100" in prompt
        assert "OP_20240101_120000" in prompt
        assert "Begin with reconnaissance" in prompt

    def test_get_system_prompt_with_memory_path(self):
        """Test system prompt with explicit memory path"""
        prompt = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
            has_memory_path=True,
        )

        assert "CRITICAL FIRST ACTION**: Load all memories" in prompt
        assert 'mem0_memory(action="list"' in prompt
        assert "Build upon previous discoveries" in prompt

    def test_get_system_prompt_with_existing_memories(self):
        """Test system prompt with existing memories detected"""
        prompt = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
            has_existing_memories=True,
        )

        assert "CRITICAL FIRST ACTION**: Load all memories" in prompt
        assert 'mem0_memory(action="list"' in prompt
        assert "Build upon previous discoveries" in prompt

    def test_get_system_prompt_with_both_memory_flags(self):
        """Test system prompt with both memory path and existing memories"""
        prompt = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
            has_memory_path=True,
            has_existing_memories=True,
        )

        assert "CRITICAL FIRST ACTION**: Load all memories" in prompt
        assert 'mem0_memory(action="list"' in prompt
        assert "Build upon previous discoveries" in prompt

    def test_get_system_prompt_no_memory_flags(self):
        """Test system prompt without memory flags"""
        prompt = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
            has_memory_path=False,
            has_existing_memories=False,
        )

        assert "Begin with reconnaissance" in prompt
        assert "Starting fresh assessment with no previous context" in prompt
        assert "Do NOT check memory on fresh operations" in prompt

    def test_get_system_prompt_with_tools_context(self):
        """Test system prompt with tools context"""
        tools_context = "## ENVIRONMENTAL CONTEXT\n\nTools: nmap, curl"

        prompt = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
            tools_context=tools_context,
        )

        assert "ENVIRONMENTAL CONTEXT" in prompt
        assert "nmap, curl" in prompt

    def test_get_system_prompt_with_output_config(self):
        """Test system prompt with output configuration"""
        output_config = {
            "base_dir": "/custom/output",
            "target_name": "test_target",
            "enable_unified_output": True,
        }

        prompt = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
            output_config=output_config,
        )

        assert "OUTPUT DIRECTORY STRUCTURE" in prompt
        assert "/custom/output" in prompt

    def test_get_system_prompt_different_servers(self):
        """Test system prompt generation for different server types"""
        # Test local server
        prompt_local = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
            provider="ollama",
        )

        # Test remote server
        prompt_remote = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
            provider="bedrock",
        )

        # Both should contain the basic elements
        assert "test.com" in prompt_local
        assert "test.com" in prompt_remote
        assert "test objective" in prompt_local
        assert "test objective" in prompt_remote


class TestMemoryInstructions:
    """Test memory instruction logic in system prompts"""

    def test_memory_instruction_priority(self):
        """Test that memory path takes priority over existing memories"""
        prompt = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
            has_memory_path=True,
            has_existing_memories=False,  # Should be ignored
        )

        assert "CRITICAL FIRST ACTION**: Load all memories" in prompt

    def test_memory_instruction_existing_only(self):
        """Test memory instruction when only existing memories are detected"""
        prompt = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
            has_memory_path=False,
            has_existing_memories=True,
        )

        assert "CRITICAL FIRST ACTION**: Load all memories" in prompt

    def test_memory_instruction_fresh_operation(self):
        """Test memory instruction for fresh operations"""
        prompt = get_system_prompt(
            target="test.com",
            objective="test objective",
            max_steps=100,
            operation_id="OP_20240101_120000",
            has_memory_path=False,
            has_existing_memories=False,
        )

        assert "Begin with reconnaissance" in prompt
        assert "Starting fresh assessment with no previous context" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
