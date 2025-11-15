#!/usr/bin/env python3
import os
from unittest.mock import MagicMock

from modules.config.manager import align_mem0_config
from modules.config.models.factory import (
    _parse_context_window_fallbacks,
    _split_model_prefix,
)


def test_parse_context_window_fallbacks_valid():
    os.environ["CYBER_CONTEXT_WINDOW_FALLBACKS"] = "gpt-4o:gpt-4o-mini,gpt-3.5;model-b:model-c"
    fallbacks = _parse_context_window_fallbacks()
    assert fallbacks == [
        {"gpt-4o": ["gpt-4o-mini", "gpt-3.5"]},
        {"model-b": ["model-c"]},
    ]


def test_parse_context_window_fallbacks_invalid_entries():
    os.environ["CYBER_CONTEXT_WINDOW_FALLBACKS"] = "gpt-4o:;:foo;model-x:model-y"
    fallbacks = _parse_context_window_fallbacks()
    assert fallbacks == [{"model-x": ["model-y"]}]


def test_parse_context_window_fallbacks_uses_config_defaults(monkeypatch):
    os.environ.pop("CYBER_CONTEXT_WINDOW_FALLBACKS", None)
    mock_config = MagicMock()
    mock_config.get_context_window_fallbacks.return_value = [{"model-a": ["model-b"]}]
    monkeypatch.setattr("modules.config.models.factory._get_config_manager", lambda: mock_config)
    fallbacks = _parse_context_window_fallbacks()
    assert fallbacks == [{"model-a": ["model-b"]}]


def testalign_mem0_config_sets_expected_provider():
    cfg = {"llm": {"provider": "aws_bedrock", "config": {"model": "claude"}}}
    align_mem0_config("azure/gpt-5", cfg)
    assert cfg["llm"]["provider"] == "azure_openai"
    assert cfg["llm"]["config"]["model"] == "gpt-5"


def test_split_model_prefix_handles_no_prefix():
    prefix, remainder = _split_model_prefix("claude-3")
    assert prefix == ""
    assert remainder == "claude-3"
