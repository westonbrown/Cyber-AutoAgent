#!/usr/bin/env python3

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


def _minimal_server_config():
    # Create a minimal server_config with required nested attributes
    return SimpleNamespace(
        llm=SimpleNamespace(model_id="gpt-4o"),
        output=SimpleNamespace(base_dir="./outputs"),
        swarm=SimpleNamespace(llm=SimpleNamespace(model_id="gpt-4o")),
        sdk=SimpleNamespace(conversation_window_size=64),
    )


@patch("modules.agents.cyber_autoagent.get_config_manager")
@patch("modules.agents.cyber_autoagent.create_litellm_model")
@patch("modules.handlers.react.hooks.ReactHooks")
@patch("modules.handlers.react.react_bridge_handler.ReactBridgeHandler")
@patch("modules.agents.cyber_autoagent.initialize_memory_system")
@patch("modules.agents.cyber_autoagent.get_memory_client", return_value=None)
def test_agent_creation_litellm(
    mock_get_memory_client,
    mock_init_memory,
    mock_rbh,
    mock_hooks,
    mock_create_litellm,
    mock_get_cfg,
):
    # Stub out the UI handler to have an emitter attribute
    mock_rbh.return_value = SimpleNamespace(emitter=None)

    # Mock config manager
    mock_cfg = Mock()
    mock_cfg.validate_requirements.return_value = None
    mock_cfg.get_server_config.return_value = _minimal_server_config()
    mock_cfg.get_default_region.return_value = "us-east-1"
    mock_cfg.get_mem0_service_config.return_value = {
        "vector_store": {"provider": "faiss", "config": {"path": "test"}},
        "embedder": {"provider": "aws_bedrock", "config": {"model": "test"}},
        "llm": {"provider": "aws_bedrock", "config": {"model": "test"}},
    }
    mock_get_cfg.return_value = mock_cfg

    mock_model = Mock()
    mock_create_litellm.return_value = mock_model

    from modules.agents.cyber_autoagent import create_agent, AgentConfig

    config = AgentConfig(target="t", objective="o", provider="litellm", op_id="OP_TEST")
    agent, handler = create_agent(target="t", objective="o", config=config)

    assert agent is not None
    assert handler is not None
    mock_create_litellm.assert_called_once()


@patch("modules.agents.cyber_autoagent.get_config_manager")
@patch("modules.agents.cyber_autoagent._handle_model_creation_error")
@patch("modules.handlers.react.hooks.ReactHooks")
@patch("modules.handlers.react.react_bridge_handler.ReactBridgeHandler")
@patch("modules.agents.cyber_autoagent.initialize_memory_system")
@patch("modules.agents.cyber_autoagent.get_memory_client", return_value=None)
def test_agent_creation_unsupported_provider_raises(
    mock_get_memory_client,
    mock_init_memory,
    mock_rbh,
    mock_hooks,
    mock_handle_error,
    mock_get_cfg,
):
    mock_rbh.return_value = SimpleNamespace(emitter=None)
    mock_cfg = Mock()
    mock_cfg.validate_requirements.return_value = None
    mock_cfg.get_server_config.return_value = _minimal_server_config()
    mock_cfg.get_default_region.return_value = "us-east-1"
    mock_cfg.get_mem0_service_config.return_value = {
        "vector_store": {"provider": "faiss", "config": {"path": "test"}},
        "embedder": {"provider": "aws_bedrock", "config": {"model": "test"}},
        "llm": {"provider": "aws_bedrock", "config": {"model": "test"}},
    }
    mock_get_cfg.return_value = mock_cfg

    from modules.agents.cyber_autoagent import create_agent, AgentConfig

    with pytest.raises(ValueError):
        config = AgentConfig(
            target="t", objective="o", provider="unsupported", op_id="OP_TEST"
        )
        create_agent(target="t", objective="o", config=config)

    assert mock_handle_error.called
