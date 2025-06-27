#!/usr/bin/env python3

import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_ollama_available():
    """Mock Ollama availability"""
    with patch("modules.agent_factory.OLLAMA_AVAILABLE", True):
        yield


@pytest.fixture
def mock_ollama_unavailable():
    """Mock Ollama unavailability"""
    with patch("modules.agent_factory.OLLAMA_AVAILABLE", False):
        yield


@pytest.fixture
def mock_aws_credentials():
    """Mock AWS credentials in environment"""
    with patch.dict(
        os.environ,
        {"AWS_ACCESS_KEY_ID": "test_key", "AWS_SECRET_ACCESS_KEY": "test_secret"},
    ):
        yield


@pytest.fixture
def mock_no_aws_credentials():
    """Mock no AWS credentials in environment"""
    # Clear AWS-related environment variables
    env_vars_to_clear = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE"]
    original_values = {}

    for var in env_vars_to_clear:
        if var in os.environ:
            original_values[var] = os.environ[var]
            del os.environ[var]

    yield

    # Restore original values
    for var, value in original_values.items():
        os.environ[var] = value


@pytest.fixture
def mock_ollama_server_running():
    """Mock Ollama server running successfully"""
    with patch("modules.agent_factory.requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_ollama_server_down():
    """Mock Ollama server not running"""
    with patch("modules.agent_factory.requests.get") as mock_get:
        mock_get.side_effect = Exception("Connection refused")
        yield mock_get


@pytest.fixture
def mock_ollama_models_available():
    """Mock Ollama models being available"""
    with patch("modules.agent_factory.ollama.Client") as mock_client:
        mock_client_instance = mock_client.return_value
        mock_client_instance.list.return_value = {
            "models": [
                {"model": "MFDoom/deepseek-r1-tool-calling:1.5b"},
                {"model": "mxbai-embed-large"},
                {"model": "other-model:latest"},
            ]
        }
        yield mock_client


@pytest.fixture
def mock_ollama_models_missing():
    """Mock Ollama models not available"""
    with patch("modules.agent_factory.ollama.list") as mock_list:
        mock_list.return_value = {"models": [{"name": "some-other-model:latest"}]}
        yield mock_list


@pytest.fixture
def mock_memory_tools():
    """Mock memory tools module"""
    with patch("modules.agent_factory.memory_tools") as mock_tools:
        mock_tools.mem0_instance = None
        mock_tools.operation_id = None
        yield mock_tools


@pytest.fixture
def mock_strands_components():
    """Mock Strands framework components"""
    with (
        patch("modules.agent_factory.Agent") as mock_agent,
        patch("modules.agent_factory.BedrockModel") as mock_bedrock,
        patch("modules.agent_factory.ReasoningHandler") as mock_handler,
        patch("modules.agent_factory.Memory.from_config") as mock_memory,
        patch("modules.agent_factory.get_system_prompt") as mock_prompt,
    ):
        mock_prompt.return_value = "test system prompt"
        yield {
            "agent": mock_agent,
            "bedrock": mock_bedrock,
            "handler": mock_handler,
            "memory": mock_memory,
            "prompt": mock_prompt,
        }


@pytest.fixture
def mock_ollama_model():
    """Mock OllamaModel when available"""
    with patch("modules.agent_factory.OllamaModel") as mock_model:
        yield mock_model


@pytest.fixture
def sample_agent_config():
    """Sample configuration for agent creation"""
    return {
        "target": "test.example.com",
        "objective": "Test security assessment",
        "max_steps": 10,
        "available_tools": ["nmap", "nikto"],
        "model_id": None,
        "region_name": "us-east-1",
        "server": "remote",
    }


@pytest.fixture
def caplog_with_level():
    """Pytest caplog fixture with specific log level"""
    import logging

    def _caplog_with_level(level=logging.INFO):
        import _pytest.logging

        return _pytest.logging.LogCaptureFixture(pytest_config=None)

    return _caplog_with_level
