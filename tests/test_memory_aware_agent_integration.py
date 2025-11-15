#!/usr/bin/env python3

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add src to path for imports


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.agents.cyber_autoagent import create_agent


class TestMemoryAwareAgentIntegration:
    """Test memory-aware system prompt integration with agent creation"""

    @patch("modules.agents.cyber_autoagent.initialize_memory_system")
    @patch("modules.agents.cyber_autoagent.get_memory_client")
    @patch("modules.agents.cyber_autoagent.check_existing_memories")
    @patch("modules.agents.cyber_autoagent.create_bedrock_model")
    @patch("modules.agents.cyber_autoagent.get_config_manager")
    def test_agent_creation_with_memory_overview(
        self,
        mock_config_manager,
        mock_create_model,
        mock_check_memories,
        mock_get_client,
        mock_initialize_memory,
    ):
        """Test agent creation with memory overview integration"""
        # Mock config manager
        mock_config = Mock()
        mock_config.validate_requirements.return_value = None
        mock_config.get_server_config.return_value = Mock(
            llm=Mock(model_id="claude-3-sonnet"),
            output=Mock(base_dir="./outputs"),
        )
        mock_config.get_default_region.return_value = "us-east-1"
        mock_config.get_mem0_service_config.return_value = {
            "vector_store": {"provider": "faiss", "config": {"path": "test"}},
            "embedder": {"provider": "aws_bedrock", "config": {"model": "test"}},
            "llm": {"provider": "aws_bedrock", "config": {"model": "test"}},
        }
        mock_config_manager.return_value = mock_config

        # Mock memory system
        mock_check_memories.return_value = True
        mock_memory_client = Mock()
        mock_memory_client.get_memory_overview.return_value = {
            "has_memories": True,
            "total_count": 5,
            "categories": {"finding": 3, "general": 2},
            "recent_findings": [
                {"content": "SQL injection found in login", "created_at": "2024-01-01"},
                {"content": "XSS vulnerability in search", "created_at": "2024-01-02"},
            ],
        }
        mock_memory_client.get_active_plan.return_value = None  # No active plan
        mock_get_client.return_value = mock_memory_client

        # Mock model creation
        mock_model = Mock()
        mock_create_model.return_value = mock_model

        # Create agent
        from modules.agents.cyber_autoagent import AgentConfig
        config = AgentConfig(
            target="test.com",
            objective="test objective",
            max_steps=50,
            op_id="OP_20240101_120000",
            provider="bedrock",
        )
        agent, handler = create_agent(target="test.com", objective="test objective", config=config)

        # Verify memory system was initialized
        mock_initialize_memory.assert_called_once()
        mock_check_memories.assert_called_once_with("test.com", "bedrock")
        assert mock_get_client.call_count == 2  # Called for overview and active plan
        mock_memory_client.get_memory_overview.assert_called_once_with(user_id="cyber_agent")

        # Verify agent was created with memory-aware system prompt
        assert agent is not None
        assert handler is not None

        # Check that the system prompt contains memory context
        system_prompt = agent.system_prompt
        assert "## MEMORY CONTEXT" in system_prompt
        assert "Continuing assessment with 5 existing memories" in system_prompt
        assert "Load all memories with mem0_memory" in system_prompt
        assert "**CRITICAL FIRST ACTION**" in system_prompt

    @patch("modules.agents.cyber_autoagent.initialize_memory_system")
    @patch("modules.agents.cyber_autoagent.get_memory_client")
    @patch("modules.agents.cyber_autoagent.check_existing_memories")
    @patch("modules.agents.cyber_autoagent.create_bedrock_model")
    @patch("modules.agents.cyber_autoagent.get_config_manager")
    def test_agent_creation_fresh_start(
        self,
        mock_config_manager,
        mock_create_model,
        mock_check_memories,
        mock_get_client,
        mock_initialize_memory,
    ):
        """Test agent creation for fresh start (no existing memories)"""
        # Mock config manager
        mock_config = Mock()
        mock_config.validate_requirements.return_value = None
        mock_config.get_server_config.return_value = Mock(
            llm=Mock(model_id="claude-3-sonnet"),
            output=Mock(base_dir="./outputs"),
        )
        mock_config.get_default_region.return_value = "us-east-1"
        mock_config.get_mem0_service_config.return_value = {
            "vector_store": {"provider": "faiss", "config": {"path": "test"}},
            "embedder": {"provider": "aws_bedrock", "config": {"model": "test"}},
            "llm": {"provider": "aws_bedrock", "config": {"model": "test"}},
        }
        mock_config_manager.return_value = mock_config

        # Mock memory system - no existing memories
        mock_check_memories.return_value = False
        mock_get_client.return_value = None  # No client needed for fresh start

        # Mock model creation
        mock_model = Mock()
        mock_create_model.return_value = mock_model

        # Create agent
        from modules.agents.cyber_autoagent import AgentConfig
        config = AgentConfig(
            target="test.com",
            objective="test objective",
            max_steps=50,
            op_id="OP_20240101_120000",
            provider="bedrock",
        )
        agent, handler = create_agent(target="test.com", objective="test objective", config=config)

        # Verify memory system was initialized
        mock_initialize_memory.assert_called_once()
        mock_check_memories.assert_called_once_with("test.com", "bedrock")

        # Verify agent was created with fresh start system prompt
        assert agent is not None
        assert handler is not None

        # Check that the system prompt contains fresh start context
        system_prompt = agent.system_prompt
        assert "## MEMORY CONTEXT" in system_prompt
        assert "Starting fresh assessment" in system_prompt
        assert "reconnaissance and target information gathering" in system_prompt
        assert "Store all findings immediately" in system_prompt

    @patch("modules.agents.cyber_autoagent.initialize_memory_system")
    @patch("modules.agents.cyber_autoagent.get_memory_client")
    @patch("modules.agents.cyber_autoagent.check_existing_memories")
    @patch("modules.agents.cyber_autoagent.create_bedrock_model")
    @patch("modules.agents.cyber_autoagent.get_config_manager")
    def test_agent_creation_with_memory_path(
        self,
        mock_config_manager,
        mock_create_model,
        mock_check_memories,
        mock_get_client,
        mock_initialize_memory,
    ):
        """Test agent creation with explicit memory path"""
        # Mock config manager
        mock_config = Mock()
        mock_config.validate_requirements.return_value = None
        mock_config.get_server_config.return_value = Mock(
            llm=Mock(model_id="claude-3-sonnet"),
            output=Mock(base_dir="./outputs"),
        )
        mock_config.get_default_region.return_value = "us-east-1"
        mock_config.get_mem0_service_config.return_value = {
            "vector_store": {"provider": "faiss", "config": {"path": "test"}},
            "embedder": {"provider": "aws_bedrock", "config": {"model": "test"}},
            "llm": {"provider": "aws_bedrock", "config": {"model": "test"}},
        }
        mock_config_manager.return_value = mock_config

        # Mock memory system
        mock_check_memories.return_value = True
        mock_memory_client = Mock()
        mock_memory_client.get_memory_overview.return_value = {
            "has_memories": True,
            "total_count": 2,
            "categories": {"finding": 1, "general": 1},
            "recent_findings": [
                {"content": "Port scan completed", "created_at": "2024-01-01"},
            ],
        }
        mock_get_client.return_value = mock_memory_client

        # Mock model creation
        mock_model = Mock()
        mock_create_model.return_value = mock_model

        # Mock path validation
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=True),
        ):
            # Create agent with memory path
            from modules.agents.cyber_autoagent import AgentConfig
            config = AgentConfig(
                target="test.com",
                objective="test objective",
                max_steps=50,
                op_id="OP_20240101_120000",
                provider="bedrock",
                memory_path="/test/memory/path",
            )
            agent, handler = create_agent(target="test.com", objective="test objective", config=config)

        # Verify memory system was initialized with path
        mock_initialize_memory.assert_called_once()

        # Verify agent was created with memory path context
        assert agent is not None
        assert handler is not None

        # Check that the system prompt contains memory path context
        system_prompt = agent.system_prompt
        assert "## MEMORY CONTEXT" in system_prompt
        assert "Continuing assessment with 2 existing memories" in system_prompt
        assert "Load all memories with mem0_memory" in system_prompt

    @patch("modules.agents.cyber_autoagent.initialize_memory_system")
    @patch("modules.agents.cyber_autoagent.get_memory_client")
    @patch("modules.agents.cyber_autoagent.check_existing_memories")
    @patch("modules.agents.cyber_autoagent.create_bedrock_model")
    @patch("modules.agents.cyber_autoagent.get_config_manager")
    def test_agent_creation_memory_overview_error_handling(
        self,
        mock_config_manager,
        mock_create_model,
        mock_check_memories,
        mock_get_client,
        mock_initialize_memory,
    ):
        """Test agent creation handles memory overview errors gracefully"""
        # Mock config manager
        mock_config = Mock()
        mock_config.validate_requirements.return_value = None
        mock_config.get_server_config.return_value = Mock(
            llm=Mock(model_id="claude-3-sonnet"),
            output=Mock(base_dir="./outputs"),
        )
        mock_config.get_default_region.return_value = "us-east-1"
        mock_config.get_mem0_service_config.return_value = {
            "vector_store": {"provider": "faiss", "config": {"path": "test"}},
            "embedder": {"provider": "aws_bedrock", "config": {"model": "test"}},
            "llm": {"provider": "aws_bedrock", "config": {"model": "test"}},
        }
        mock_config_manager.return_value = mock_config

        # Mock memory system with error
        mock_check_memories.return_value = True
        mock_memory_client = Mock()
        mock_memory_client.get_memory_overview.side_effect = Exception("Memory overview error")
        mock_get_client.return_value = mock_memory_client

        # Mock model creation
        mock_model = Mock()
        mock_create_model.return_value = mock_model

        # Create agent - should handle error gracefully
        from modules.agents.cyber_autoagent import AgentConfig
        config = AgentConfig(
            target="test.com",
            objective="test objective",
            max_steps=50,
            op_id="OP_20240101_120000",
            provider="bedrock",
        )
        agent, handler = create_agent(target="test.com", objective="test objective", config=config)

        # Verify agent was still created successfully
        assert agent is not None
        assert handler is not None

        # Check that the system prompt contains fallback memory context
        system_prompt = agent.system_prompt
        assert "## MEMORY CONTEXT" in system_prompt
        assert "Continuing assessment with 0 existing memories" in system_prompt

    @patch("modules.agents.cyber_autoagent.initialize_memory_system")
    @patch("modules.agents.cyber_autoagent.get_memory_client")
    @patch("modules.agents.cyber_autoagent.check_existing_memories")
    @patch("modules.config.models.factory.create_ollama_model")
    @patch("modules.agents.cyber_autoagent.get_config_manager")
    def test_agent_creation_local_server_with_memory(
        self,
        mock_config_manager,
        mock_create_model,
        mock_check_memories,
        mock_get_client,
        mock_initialize_memory,
    ):
        """Test agent creation with local server and memory overview"""
        # Mock config manager for local server
        mock_config = Mock()
        mock_config.validate_requirements.return_value = None
        mock_config.get_server_config.return_value = Mock(
            llm=Mock(model_id="llama3.2:3b"),
            output=Mock(base_dir="./outputs"),
        )
        mock_config.get_default_region.return_value = "us-east-1"
        mock_config.get_mem0_service_config.return_value = {
            "vector_store": {"provider": "faiss", "config": {"path": "test"}},
            "embedder": {"provider": "ollama", "config": {"model": "test"}},
            "llm": {"provider": "ollama", "config": {"model": "test"}},
        }
        mock_config_manager.return_value = mock_config

        # Mock memory system
        mock_check_memories.return_value = True
        mock_memory_client = Mock()
        mock_memory_client.get_memory_overview.return_value = {
            "has_memories": True,
            "total_count": 1,
            "categories": {"finding": 1},
            "recent_findings": [
                {"content": "Local scan completed", "created_at": "2024-01-01"},
            ],
        }
        mock_get_client.return_value = mock_memory_client

        # Mock model creation
        mock_model = Mock()
        mock_create_model.return_value = mock_model

        # Create agent with local server
        from modules.agents.cyber_autoagent import AgentConfig
        config = AgentConfig(
            target="test.com",
            objective="test objective",
            max_steps=50,
            op_id="OP_20240101_120000",
            provider="ollama",
        )
        agent, handler = create_agent(target="test.com", objective="test objective", config=config)

        # Verify agent was created successfully
        assert agent is not None
        assert handler is not None

        # Check that the system prompt contains both memory context and local server config
        system_prompt = agent.system_prompt
        assert "## MEMORY CONTEXT" in system_prompt
        assert "Continuing assessment with 1 existing memories" in system_prompt
        assert "Load all memories with mem0_memory" in system_prompt
        assert 'model_provider: "ollama"' in system_prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
