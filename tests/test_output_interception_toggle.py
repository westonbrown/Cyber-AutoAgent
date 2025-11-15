#!/usr/bin/env python3

from types import SimpleNamespace
from unittest.mock import Mock, patch


def _minimal_server_config():
    return SimpleNamespace(
        llm=SimpleNamespace(model_id="claude-3-sonnet"),
        output=SimpleNamespace(base_dir="./outputs"),
        swarm=SimpleNamespace(llm=SimpleNamespace(model_id="claude-3-sonnet")),
        sdk=SimpleNamespace(conversation_window_size=64),
    )


@patch("modules.handlers.output_interceptor.setup_output_interception")
@patch("modules.agents.cyber_autoagent.get_config_manager")
@patch("modules.agents.cyber_autoagent.create_bedrock_model")
@patch("modules.handlers.react.hooks.ReactHooks")
@patch("modules.handlers.react.react_bridge_handler.ReactBridgeHandler")
@patch("modules.agents.cyber_autoagent.initialize_memory_system")
@patch("modules.agents.cyber_autoagent.get_memory_client", return_value=None)
def test_output_interception_react_only(
    mock_get_memory_client,
    mock_init_memory,
    mock_rbh,
    mock_hooks,
    mock_create_model,
    mock_get_cfg,
    mock_setup_intercept,
    monkeypatch,
):
    mock_rbh.return_value = SimpleNamespace(emitter=None)
    mock_model = Mock()
    mock_create_model.return_value = mock_model

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

    # CLI mode: should NOT setup interception
    monkeypatch.setenv("CYBER_UI_MODE", "cli")
    config = AgentConfig(target="t", objective="o", provider="bedrock", op_id="OP_TEST")
    create_agent(target="t", objective="o", config=config)
    assert mock_setup_intercept.call_count == 0

    # React mode: should setup interception
    monkeypatch.setenv("CYBER_UI_MODE", "react")
    config = AgentConfig(
        target="t2", objective="o2", provider="bedrock", op_id="OP_TEST2"
    )
    create_agent(target="t2", objective="o2", config=config)
    assert mock_setup_intercept.call_count == 1
