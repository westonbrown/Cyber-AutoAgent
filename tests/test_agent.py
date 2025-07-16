#!/usr/bin/env python3

import pytest
import os
from unittest.mock import Mock, patch

# Add src to path for imports
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.agent import (
    _validate_server_requirements,
    create_agent,
)
from modules.system_prompts import (
    _get_default_model_configs,
    _get_ollama_host,
)


class TestModelConfigs:
    """Test model configuration functions"""

    def test_get_default_model_configs_local(self):
        """Test local model configuration defaults"""
        config = _get_default_model_configs("local")

        assert config["llm_model"] == "llama3.2:3b"
        assert config["embedding_model"] == "mxbai-embed-large"
        assert config["embedding_dims"] == 1024

    def test_get_default_model_configs_remote(self):
        """Test remote model configuration defaults"""
        config = _get_default_model_configs("remote")

        assert "us.anthropic.claude" in config["llm_model"]
        assert config["embedding_model"] == "amazon.titan-embed-text-v2:0"
        assert config["embedding_dims"] == 1024

    def test_get_default_model_configs_invalid(self):
        """Test configuration for invalid server type"""
        # Should now raise an error for invalid server type
        with pytest.raises(ValueError, match="Unsupported server type"):
            _get_default_model_configs("invalid")


class TestOllamaHostDetection:
    """Test Ollama host detection functionality"""

    @patch.dict(os.environ, {"OLLAMA_HOST": "http://custom-host:8080"}, clear=True)
    def test_get_ollama_host_env_override(self):
        """Test OLLAMA_HOST environment variable override"""
        host = _get_ollama_host()
        assert host == "http://custom-host:8080"

    @patch.dict(os.environ, {"OLLAMA_HOST": "http://localhost:9999"}, clear=True)
    def test_get_ollama_host_custom_port(self):
        """Test OLLAMA_HOST with custom port"""
        host = _get_ollama_host()
        assert host == "http://localhost:9999"

    @patch.dict(os.environ, {}, clear=True)
    @patch("os.path.exists")
    def test_get_ollama_host_native_execution(self, mock_exists):
        """Test host detection for native execution (not in Docker)"""
        mock_exists.return_value = False  # /.dockerenv doesn't exist
        
        host = _get_ollama_host()
        # Should use localhost for native execution
        assert host == "http://localhost:11434"

    @patch.dict(os.environ, {}, clear=True)
    @patch("os.path.exists")
    @patch("requests.get")
    def test_get_ollama_host_docker_localhost_works(self, mock_test, mock_exists):
        """Test Docker environment where localhost works (Linux host networking)"""
        mock_exists.return_value = True  # /app exists
        # Mock localhost works, host.docker.internal doesn't
        mock_response = Mock()
        mock_response.status_code = 200
        def side_effect(url, timeout=None):
            if "localhost" in url:
                return mock_response
            else:
                raise Exception("Connection failed")
        mock_test.side_effect = side_effect
        
        host = _get_ollama_host()
        assert host == "http://localhost:11434"
        
        # Verify it tested localhost first and found it working
        assert mock_test.call_count >= 1
        mock_test.assert_any_call("http://localhost:11434/api/version", timeout=2)

    @patch.dict(os.environ, {}, clear=True)
    @patch("os.path.exists")
    @patch("requests.get")
    def test_get_ollama_host_docker_host_internal_works(self, mock_test, mock_exists):
        """Test Docker environment where host.docker.internal works (macOS/Windows)"""
        mock_exists.return_value = True  # /app exists
        # Mock localhost fails, host.docker.internal works
        mock_response = Mock()
        mock_response.status_code = 200
        def side_effect(url, timeout=None):
            if "host.docker.internal" in url:
                return mock_response
            else:
                raise Exception("Connection failed")
        mock_test.side_effect = side_effect
        
        host = _get_ollama_host()
        assert host == "http://host.docker.internal:11434"
        
        # Verify it tested both options
        assert mock_test.call_count >= 2
        mock_test.assert_any_call("http://localhost:11434/api/version", timeout=2)
        mock_test.assert_any_call("http://host.docker.internal:11434/api/version", timeout=2)

    @patch.dict(os.environ, {}, clear=True)
    @patch("os.path.exists")
    @patch("requests.get")
    def test_get_ollama_host_docker_no_connection(self, mock_test, mock_exists):
        """Test Docker environment where neither option works"""
        mock_exists.return_value = True  # /.dockerenv exists
        mock_test.return_value = False  # Neither option works
        
        host = _get_ollama_host()
        # Should fallback to host.docker.internal
        assert host == "http://host.docker.internal:11434"




class TestMemoryConfig:
    """Test memory configuration generation"""

    @patch("modules.agent.initialize_memory_system")
    def test_memory_config_local(self, mock_init_memory):
        """Test local memory configuration is created correctly"""
        # The current implementation builds memory config inline in create_agent
        # We'll test that the right config is passed to initialize_memory_system
        with patch("modules.agent._validate_server_requirements"):
            with patch("modules.agent._create_local_model") as mock_create_local:
                mock_create_local.return_value = Mock()
                with patch("modules.agent.Agent") as mock_agent_class:
                    mock_agent_class.return_value = Mock()
                    with patch("modules.agent.ReasoningHandler") as mock_handler:
                        mock_handler.return_value = Mock()
                        with patch("modules.agent.get_system_prompt"):
                            # Call create_agent with local server
                            create_agent(
                                target="test.com",
                                objective="test",
                                server="local"
                            )
                            
                            # Check that initialize_memory_system was called
                            mock_init_memory.assert_called_once()
                            config = mock_init_memory.call_args[0][0]
                            
                            # Verify local config structure
                            assert config["embedder"]["provider"] == "ollama"
                            assert config["llm"]["provider"] == "ollama"
                            assert "ollama_base_url" in config["embedder"]["config"]

    @patch("modules.agent.initialize_memory_system")
    def test_memory_config_remote(self, mock_init_memory):
        """Test remote memory configuration is created correctly"""
        with patch("modules.agent._validate_server_requirements"):
            with patch("modules.agent._create_remote_model") as mock_create_remote:
                mock_create_remote.return_value = Mock()
                with patch("modules.agent.Agent") as mock_agent_class:
                    mock_agent_class.return_value = Mock()
                    with patch("modules.agent.ReasoningHandler") as mock_handler:
                        mock_handler.return_value = Mock()
                        with patch("modules.agent.get_system_prompt"):
                            # Call create_agent with remote server
                            create_agent(
                                target="test.com",
                                objective="test",
                                server="remote"
                            )
                            
                            # Check that initialize_memory_system was called
                            mock_init_memory.assert_called_once()
                            config = mock_init_memory.call_args[0][0]
                            
                            # Verify remote config structure
                            assert config["embedder"]["provider"] == "aws_bedrock"
                            assert config["llm"]["provider"] == "aws_bedrock"
                            assert "aws_region" in config["embedder"]["config"]


class TestServerValidation:
    """Test server requirements validation"""

    @patch("modules.agent.requests.get")
    @patch("modules.agent.ollama.Client")
    def test_validate_server_requirements_local_success(
        self, mock_ollama_client, mock_requests
    ):
        """Test successful local server validation"""
        # Mock Ollama server responding
        mock_requests.return_value.status_code = 200

        # Mock ollama client and list method
        mock_client_instance = mock_ollama_client.return_value
        mock_client_instance.list.return_value = {
            "models": [{"model": "llama3.2:3b"}, {"model": "mxbai-embed-large"}]
        }

        # Should not raise any exception
        _validate_server_requirements("local")
        
        # Verify client was created (host is now dynamic)
        mock_ollama_client.assert_called_once()

    @patch("modules.agent.requests.get")
    def test_validate_server_requirements_local_server_down(self, mock_requests):
        """Test local server validation when Ollama is down"""
        # Mock Ollama server not responding
        mock_requests.side_effect = Exception("Connection refused")

        with pytest.raises(ConnectionError, match="Ollama server not accessible"):
            _validate_server_requirements("local")

    @patch("modules.agent.requests.get")
    @patch("modules.agent.ollama.Client")
    def test_validate_server_requirements_local_missing_models(
        self, mock_ollama_client, mock_requests
    ):
        """Test local server validation when models are missing"""
        # Mock Ollama server responding
        mock_requests.return_value.status_code = 200

        # Mock ollama client and list method with missing models
        mock_client_instance = mock_ollama_client.return_value
        mock_client_instance.list.return_value = {
            "models": [{"model": "some-other-model:latest"}]
        }

        with pytest.raises(ValueError, match="Required models not found"):
            _validate_server_requirements("local")

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_server_requirements_remote_no_credentials(self):
        """Test remote server validation without AWS credentials"""
        with pytest.raises(EnvironmentError, match="AWS credentials not configured"):
            _validate_server_requirements("remote")

    @patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test_key"}, clear=True)
    def test_validate_server_requirements_remote_success(self):
        """Test successful remote server validation"""
        # Should not raise any exception
        _validate_server_requirements("remote")


class TestCreateAgent:
    """Test agent creation functionality"""

    @patch("modules.agent._validate_server_requirements")
    @patch("modules.agent._create_remote_model")
    @patch("modules.agent.Agent")
    @patch("modules.agent.ReasoningHandler")
    @patch("modules.agent.get_system_prompt")
    @patch("modules.agent.initialize_memory_system")
    def test_create_agent_remote_success(
        self,
        mock_init_memory,
        mock_get_prompt,
        mock_reasoning_handler,
        mock_agent_class,
        mock_create_remote,
        mock_validate,
    ):
        """Test successful remote agent creation"""
        # Setup mocks
        mock_model = Mock()
        mock_create_remote.return_value = mock_model
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        mock_handler = Mock()
        mock_reasoning_handler.return_value = mock_handler
        mock_get_prompt.return_value = "test prompt"

        # Call function
        agent, handler = create_agent(
            target="test.com", objective="test objective", server="remote"
        )

        # Verify calls
        mock_validate.assert_called_once_with("remote")
        mock_create_remote.assert_called_once()
        mock_agent_class.assert_called_once()

        assert agent == mock_agent
        assert handler == mock_handler

    @patch("modules.agent._validate_server_requirements")
    @patch("modules.agent._create_local_model")
    @patch("modules.agent.Agent")
    @patch("modules.agent.ReasoningHandler")
    @patch("modules.agent.get_system_prompt")
    @patch("modules.agent.initialize_memory_system")
    def test_create_agent_local_success(
        self,
        mock_init_memory,
        mock_get_prompt,
        mock_reasoning_handler,
        mock_agent_class,
        mock_create_local,
        mock_validate,
    ):
        """Test successful local agent creation"""
        # Setup mocks
        mock_model = Mock()
        mock_create_local.return_value = mock_model
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        mock_handler = Mock()
        mock_reasoning_handler.return_value = mock_handler
        mock_get_prompt.return_value = "test prompt"

        # Call function
        agent, handler = create_agent(
            target="test.com", objective="test objective", server="local"
        )

        # Verify calls
        mock_validate.assert_called_once_with("local")
        mock_create_local.assert_called_once()
        mock_agent_class.assert_called_once()

        assert agent == mock_agent
        assert handler == mock_handler

    @patch("modules.agent._validate_server_requirements")
    def test_create_agent_validation_failure(self, mock_validate):
        """Test agent creation when validation fails"""
        mock_validate.side_effect = ConnectionError("Test error")

        with pytest.raises(ConnectionError):
            create_agent(target="test.com", objective="test objective", server="local")

    @patch("modules.agent._validate_server_requirements")
    @patch("modules.agent._create_local_model")
    @patch("modules.agent._handle_model_creation_error")
    @patch("modules.agent.initialize_memory_system")
    def test_create_agent_model_creation_failure(
        self,
        mock_init_memory,
        mock_handle_error,
        mock_create_local,
        mock_validate,
    ):
        """Test agent creation when model creation fails"""
        mock_create_local.side_effect = Exception("Model creation failed")

        with pytest.raises(Exception):
            create_agent(target="test.com", objective="test objective", server="local")

        mock_handle_error.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
