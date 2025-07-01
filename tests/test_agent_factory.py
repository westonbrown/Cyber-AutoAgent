#!/usr/bin/env python3

import pytest
import os
import tempfile
from unittest.mock import Mock, patch

# Add src to path for imports
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.agent_factory import (
    _get_default_model_configs,
    _create_memory_config,
    _validate_server_requirements,
    _get_ollama_host,
    _test_ollama_connection,
    create_agent,
)


class TestModelConfigs:
    """Test model configuration functions"""

    def test_get_default_model_configs_local(self):
        """Test local model configuration defaults"""
        config = _get_default_model_configs("local")

        assert config["llm_model"] == "MFDoom/qwen3:4b"
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
        config = _get_default_model_configs("invalid")
        # Should default to remote
        assert "us.anthropic.claude" in config["llm_model"]


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
    @patch("modules.agent_factory._test_ollama_connection")
    def test_get_ollama_host_docker_localhost_works(self, mock_test, mock_exists):
        """Test Docker environment where localhost works (Linux host networking)"""
        mock_exists.return_value = True  # /.dockerenv exists
        # Mock localhost works, host.docker.internal doesn't
        mock_test.side_effect = lambda host: host == "http://localhost:11434"
        
        host = _get_ollama_host()
        assert host == "http://localhost:11434"
        
        # Verify it tested localhost first and found it working
        assert mock_test.call_count >= 1
        mock_test.assert_any_call("http://localhost:11434")

    @patch.dict(os.environ, {}, clear=True)
    @patch("os.path.exists")
    @patch("modules.agent_factory._test_ollama_connection")
    def test_get_ollama_host_docker_host_internal_works(self, mock_test, mock_exists):
        """Test Docker environment where host.docker.internal works (macOS/Windows)"""
        mock_exists.return_value = True  # /.dockerenv exists
        # Mock localhost fails, host.docker.internal works
        mock_test.side_effect = lambda host: host == "http://host.docker.internal:11434"
        
        host = _get_ollama_host()
        assert host == "http://host.docker.internal:11434"
        
        # Verify it tested both options
        assert mock_test.call_count >= 2
        mock_test.assert_any_call("http://localhost:11434")
        mock_test.assert_any_call("http://host.docker.internal:11434")

    @patch.dict(os.environ, {}, clear=True)
    @patch("os.path.exists")
    @patch("modules.agent_factory._test_ollama_connection")
    def test_get_ollama_host_docker_no_connection(self, mock_test, mock_exists):
        """Test Docker environment where neither option works"""
        mock_exists.return_value = True  # /.dockerenv exists
        mock_test.return_value = False  # Neither option works
        
        host = _get_ollama_host()
        # Should fallback to host.docker.internal
        assert host == "http://host.docker.internal:11434"

    @patch("modules.agent_factory.requests.get")
    def test_test_ollama_connection_success(self, mock_get):
        """Test successful Ollama connection test"""
        mock_get.return_value.status_code = 200
        
        result = _test_ollama_connection("http://localhost:11434")
        assert result is True

    @patch("modules.agent_factory.requests.get")
    def test_test_ollama_connection_failure(self, mock_get):
        """Test failed Ollama connection test"""
        mock_get.side_effect = Exception("Connection failed")
        
        result = _test_ollama_connection("http://localhost:11434")
        assert result is False



class TestMemoryConfig:
    """Test memory configuration generation"""

    def test_create_memory_config_local(self):
        """Test local memory configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("modules.agent_factory.get_data_path", return_value=tmpdir):
                defaults = {
                    "llm_model": "MFDoom/qwen3:4b",
                    "embedding_model": "mxbai-embed-large",
                    "embedding_dims": 1024,
                }
                config = _create_memory_config("local", "test_op", defaults)

                assert config["llm"]["provider"] == "ollama"
                assert config["embedder"]["provider"] == "ollama"
                assert config["llm"]["config"]["model"] == "MFDoom/qwen3:4b"
                assert config["embedder"]["config"]["model"] == "mxbai-embed-large"
                assert config["vector_store"]["provider"] == "faiss"
                assert config["vector_store"]["config"]["embedding_model_dims"] == 1024

    def test_create_memory_config_remote(self):
        """Test remote memory configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("modules.agent_factory.get_data_path", return_value=tmpdir):
                defaults = {
                    "llm_model": "claude",
                    "embedding_model": "amazon.titan-embed-text-v2:0",
                    "embedding_dims": 1024,
                }
                config = _create_memory_config("remote", "test_op", defaults)

                assert config["llm"]["provider"] == "aws_bedrock"
                assert config["embedder"]["provider"] == "aws_bedrock"
                assert (
                    config["embedder"]["config"]["model"]
                    == "amazon.titan-embed-text-v2:0"
                )
                assert config["vector_store"]["provider"] == "faiss"


class TestServerValidation:
    """Test server requirements validation"""

    @patch("modules.agent_factory.OLLAMA_AVAILABLE", True)
    @patch("modules.agent_factory.requests.get")
    @patch("modules.agent_factory.ollama.Client")
    def test_validate_server_requirements_local_success(
        self, mock_ollama_client, mock_requests
    ):
        """Test successful local server validation"""
        # Mock Ollama server responding
        mock_requests.return_value.status_code = 200

        # Mock ollama client and list method
        mock_client_instance = mock_ollama_client.return_value
        mock_client_instance.list.return_value = {
            "models": [{"model": "MFDoom/qwen3:4b"}, {"model": "mxbai-embed-large"}]
        }

        # Should not raise any exception
        _validate_server_requirements("local")
        
        # Verify client was created (host is now dynamic)
        mock_ollama_client.assert_called_once()

    @patch("modules.agent_factory.OLLAMA_AVAILABLE", True)
    @patch("modules.agent_factory.requests.get")
    def test_validate_server_requirements_local_server_down(self, mock_requests):
        """Test local server validation when Ollama is down"""
        # Mock Ollama server not responding
        mock_requests.side_effect = Exception("Connection refused")

        with pytest.raises(ConnectionError, match="Ollama server not accessible"):
            _validate_server_requirements("local")

    @patch("modules.agent_factory.OLLAMA_AVAILABLE", True)
    @patch("modules.agent_factory.requests.get")
    @patch("modules.agent_factory.ollama.Client")
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

    @patch("modules.agent_factory._validate_server_requirements")
    @patch("modules.agent_factory.Memory.from_config")
    @patch("modules.agent_factory._create_remote_model")
    @patch("modules.agent_factory.Agent")
    @patch("modules.agent_factory.ReasoningHandler")
    @patch("modules.agent_factory.get_system_prompt")
    @patch("modules.agent_factory.memory_tools")
    def test_create_agent_remote_success(
        self,
        mock_memory_tools,
        mock_get_prompt,
        mock_reasoning_handler,
        mock_agent_class,
        mock_create_remote,
        mock_memory_from_config,
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

    @patch("modules.agent_factory._validate_server_requirements")
    @patch("modules.agent_factory.Memory.from_config")
    @patch("modules.agent_factory._create_local_model")
    @patch("modules.agent_factory.Agent")
    @patch("modules.agent_factory.ReasoningHandler")
    @patch("modules.agent_factory.get_system_prompt")
    @patch("modules.agent_factory.memory_tools")
    def test_create_agent_local_success(
        self,
        mock_memory_tools,
        mock_get_prompt,
        mock_reasoning_handler,
        mock_agent_class,
        mock_create_local,
        mock_memory_from_config,
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

    @patch("modules.agent_factory._validate_server_requirements")
    def test_create_agent_validation_failure(self, mock_validate):
        """Test agent creation when validation fails"""
        mock_validate.side_effect = ConnectionError("Test error")

        with pytest.raises(ConnectionError):
            create_agent(target="test.com", objective="test objective", server="local")

    @patch("modules.agent_factory._validate_server_requirements")
    @patch("modules.agent_factory.Memory.from_config")
    @patch("modules.agent_factory._create_local_model")
    @patch("modules.agent_factory._handle_model_creation_error")
    @patch("modules.agent_factory.memory_tools")
    def test_create_agent_model_creation_failure(
        self,
        mock_memory_tools,
        mock_handle_error,
        mock_create_local,
        mock_memory_from_config,
        mock_validate,
    ):
        """Test agent creation when model creation fails"""
        mock_create_local.side_effect = Exception("Model creation failed")

        with pytest.raises(Exception):
            create_agent(target="test.com", objective="test objective", server="local")

        mock_handle_error.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
