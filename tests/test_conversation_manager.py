from typing import Any

from strands.types.exceptions import ContextWindowOverflowException

from modules.handlers.conversation_budget import (
    MappingConversationManager,
    LargeToolResultMapper,
)


class _AgentStub:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = messages
        self.system_prompt = "stub"
        self.tool_registry = None


def _make_message(text: str) -> dict[str, Any]:
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def test_pruning_conversation_manager_sliding_trims_messages():
    manager = MappingConversationManager(
        window_size=3, summary_ratio=0.5, preserve_recent_messages=1
    )
    agent = _AgentStub([_make_message(str(i)) for i in range(5)])

    manager.apply_management(agent)

    assert len(agent.messages) == 3
    # Ensure newest messages are preserved
    assert [block["content"][0]["text"] for block in agent.messages] == ["2", "3", "4"]


def test_pruning_conversation_manager_falls_back_to_summary(monkeypatch):
    manager = MappingConversationManager(
        window_size=1, summary_ratio=0.5, preserve_recent_messages=1
    )
    agent = _AgentStub([_make_message("old"), _make_message("recent")])

    # Force sliding reduction to raise overflow so summarization path executes
    def _raise_overflow(*_args, **_kwargs):
        raise ContextWindowOverflowException("forced")

    monkeypatch.setattr(manager._sliding, "reduce_context", _raise_overflow)

    summary_message = _make_message("summary")

    def _fake_generate_summary(messages, _agent):
        assert len(messages) == 1
        return summary_message

    monkeypatch.setattr(manager, "_generate_summary", _fake_generate_summary)

    manager.reduce_context(agent)

    assert agent.messages[0] is summary_message
    # Ensure recent message preserved after summary insertion
    assert agent.messages[1]["content"][0]["text"] == "recent"


def test_tool_result_compressor_truncates_large_content():
    mapper = LargeToolResultMapper(max_tool_chars=100, truncate_at=10)
    message = {
        "role": "assistant",
        "content": [
            {
                "toolResult": {
                    "status": "success",
                    "toolUseId": "abc",
                    "content": [
                        {"text": "x" * 120},
                    ],
                }
            }
        ],
    }
    result = mapper(message, 1, [message])
    assert result is not None
    tool_content = result["content"][0]["toolResult"]["content"]
    assert "compressed" in tool_content[0]["text"]
    assert "[truncated" in tool_content[1]["text"]


def test_tool_result_compressor_summarizes_json():
    mapper = LargeToolResultMapper(max_tool_chars=50, truncate_at=10)
    message = {
        "role": "assistant",
        "content": [
            {
                "toolResult": {
                    "status": "success",
                    "toolUseId": "json",
                    "content": [
                        {"json": {"a": "x" * 50, "b": "y" * 60, "c": "z" * 70}},
                    ],
                }
            }
        ],
    }
    result = mapper(message, 1, [message])
    assert result is not None

    # New format: [note, text_indicator, json_indicator]
    tool_content = result["content"][0]["toolResult"]["content"]
    assert len(tool_content) >= 2

    # Check text indicator (human-readable)
    text_block = tool_content[1]["text"]
    assert "Compressed:" in text_block
    assert "keys" in text_block

    # Check structured JSON indicator (for LLM comprehension)
    json_block = tool_content[2]["json"]
    assert json_block["_compressed"] is True
    assert "_n_original_keys" in json_block
    assert json_block["_type"] == "json"


def test_reduce_context_records_event(monkeypatch):
    manager = MappingConversationManager(
        window_size=2, summary_ratio=0.5, preserve_recent_messages=1
    )
    agent = _AgentStub(
        [_make_message("one"), _make_message("two"), _make_message("three")]
    )
    setattr(agent, "_pending_reduction_reason", "telemetry tokens 900")

    manager.reduce_context(agent)

    history = getattr(agent, "_context_reduction_events", [])
    assert history, "Expected reduction history to be recorded"
    event = history[-1]
    assert event["reason"] == "telemetry tokens 900"
    assert event["removed_messages"] > 0
