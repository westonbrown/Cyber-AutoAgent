#!/usr/bin/env python3
import types

from modules.handlers.conversation_budget import (
    _ensure_prompt_within_budget,
    _estimate_prompt_tokens,
    _strip_reasoning_content,
)


class AgentStub:
    def __init__(self, messages, limit=None, telemetry=None):
        self.messages = messages
        self._prompt_token_limit = limit
        self.conversation_manager = types.SimpleNamespace(
            calls=[],
            reduce_context=lambda agent: self.conversation_manager.calls.append(len(agent.messages)),
        )
        if telemetry is not None:
            self.callback_handler = types.SimpleNamespace(sdk_input_tokens=telemetry)


def _make_message(text):
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def _make_reasoning_message(text="thinking"):
    return {
        "role": "assistant",
        "content": [{"reasoningContent": {"reasoningText": {"text": text}}}],
    }


def test_estimate_prompt_tokens_counts_text_blocks():
    agent = AgentStub([_make_message("a" * 40), _make_message("b" * 80)])
    estimated = _estimate_prompt_tokens(agent)
    assert estimated == (120 // 4)


def test_ensure_prompt_reduces_context_when_near_limit():
    messages = [_make_message("x" * 4000) for _ in range(10)]
    agent = AgentStub(messages, limit=1000)
    _ensure_prompt_within_budget(agent)
    assert agent.conversation_manager.calls, "Expected reduce_context to be invoked"


def test_ensure_prompt_skips_when_under_budget():
    agent = AgentStub([_make_message("short text")], limit=10000)
    _ensure_prompt_within_budget(agent)
    assert not agent.conversation_manager.calls


def test_ensure_prompt_telemetry_trigger():
    messages = [_make_message("short text")] * 2
    agent = AgentStub(messages, limit=1000, telemetry=900)
    _ensure_prompt_within_budget(agent)
    assert agent.conversation_manager.calls, "Telemetry tokens above threshold should trigger reduction"


def test_strip_reasoning_content_removes_when_disallowed():
    message = _make_reasoning_message()
    agent = AgentStub([message])
    setattr(agent, "_allow_reasoning_content", False)
    _strip_reasoning_content(agent)
    assert agent.messages[0]["content"] == []


def test_strip_reasoning_content_keeps_when_allowed():
    message = _make_reasoning_message()
    agent = AgentStub([message])
    setattr(agent, "_allow_reasoning_content", True)
    _strip_reasoning_content(agent)
    assert agent.messages[0]["content"] == message["content"]
