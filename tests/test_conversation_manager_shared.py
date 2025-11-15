#!/usr/bin/env python3
"""Tests for shared conversation manager functionality.

Verifies that agents without dedicated conversation managers can use
the shared global conversation manager for context reduction.
"""

import types

from modules.handlers.conversation_budget import (
    _ensure_prompt_within_budget,
    register_conversation_manager,
    clear_shared_conversation_manager,
)


class AgentStub:
    def __init__(self, messages, limit=None, telemetry=None):
        self.messages = messages
        self._prompt_token_limit = limit
        # No per-agent CM; force use of shared CM
        self.conversation_manager = None
        # Allow optional telemetry
        if telemetry is not None:
            self.callback_handler = types.SimpleNamespace(sdk_input_tokens=telemetry)


def _make_message(text):
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def test_shared_conversation_manager_is_used_when_agent_has_none():
    calls = []

    class CMStub:
        def reduce_context(self, agent, *args, **kwargs):  # noqa: D401
            calls.append(len(getattr(agent, "messages", [])))

    register_conversation_manager(CMStub())

    # Create an agent near threshold so reduction should trigger
    messages = [_make_message("z" * 4000) for _ in range(2)]
    agent = AgentStub(messages, limit=1000)

    try:
        _ensure_prompt_within_budget(agent)
    finally:
        clear_shared_conversation_manager()

    assert calls, (
        "Expected shared conversation manager to be invoked for agents without a CM"
    )
