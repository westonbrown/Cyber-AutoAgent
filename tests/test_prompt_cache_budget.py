#!/usr/bin/env python3
"""Tests for prompt cache budget optimization.

Verifies that prompt caching detection allows relaxed token thresholds,
reducing unnecessary context reductions when cache hits occur.
"""

import types

from modules.handlers.conversation_budget import (
    _ensure_prompt_within_budget,
    register_conversation_manager,
    clear_shared_conversation_manager,
)


class AgentStub:
    def __init__(self, messages, limit=None, telemetry=None, cache_hint=False):
        self.messages = messages
        self._prompt_token_limit = limit
        # Provide a stub CM when needed
        self.conversation_manager = None
        # Test/legacy telemetry injection point
        self.callback_handler = (
            types.SimpleNamespace(sdk_input_tokens=telemetry)
            if telemetry is not None
            else None
        )
        # Optional prompt cache hint
        if cache_hint:
            setattr(self, "_prompt_cache_hit", True)


def _make_message(text):
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def test_prompt_cache_hint_relaxes_threshold(monkeypatch):
    # Ensure a predictable relax amount
    monkeypatch.setenv("CYBER_PROMPT_CACHE_RELAX", "0.1")

    # Shared CM stub which records calls
    calls = []

    class CMStub:
        def reduce_context(self, agent, *args, **kwargs):  # noqa: D401
            calls.append(len(getattr(agent, "messages", [])))

    register_conversation_manager(CMStub())

    # Telemetry close to 80% threshold (e.g., 850/1000)
    messages = [_make_message("x" * 10)]
    agent = AgentStub(messages, limit=1000, telemetry=850, cache_hint=True)

    try:
        _ensure_prompt_within_budget(agent)
    finally:
        clear_shared_conversation_manager()

    # With cache hint and +0.1 relax, threshold becomes 900 -> no reduction
    assert not calls, "Expected no reduction when cache hint relaxes threshold"


def test_no_cache_hint_triggers_reduction(monkeypatch):
    monkeypatch.delenv("CYBER_PROMPT_CACHE_RELAX", raising=False)

    calls = []

    class CMStub:
        def reduce_context(self, agent, *args, **kwargs):
            calls.append(len(getattr(agent, "messages", [])))

    register_conversation_manager(CMStub())

    # Telemetry over 80% -> triggers reduction without cache hint
    # Need enough content to trigger: ~800 tokens * 3.7 ratio = ~2960 chars
    messages = [_make_message("x" * 1500)] * 2  # 3000 chars total
    agent = AgentStub(messages, limit=1000, telemetry=900, cache_hint=False)

    try:
        _ensure_prompt_within_budget(agent)
    finally:
        clear_shared_conversation_manager()

    assert calls, "Expected reduction to be invoked without cache hint"
