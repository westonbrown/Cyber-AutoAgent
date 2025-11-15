#!/usr/bin/env python3
"""
Tests for StdoutEventEmitter behavior:
- Ensures newline is printed with every event
- Verifies deduplication logic avoids duplicate emissions for identical events
- All events now emit JSON format (React terminal is the default UI)
"""

import io
import json
from contextlib import redirect_stdout

from modules.handlers.events.emitters import StdoutEventEmitter


def test_emitter_appends_newline_and_serializes_output():
    """Test emitter always outputs JSON with newline."""
    emitter = StdoutEventEmitter(operation_id="TEST_OP")
    buf = io.StringIO()

    event = {"type": "output", "content": "hello"}

    with redirect_stdout(buf):
        emitter.emit(event)

    out = buf.getvalue()
    assert out.endswith("\n"), "Emitter must end each event with a newline"
    assert "__CYBER_EVENT__" in out and "__CYBER_EVENT_END__" in out
    # Validate JSON payload parses
    payload_str = out.split("__CYBER_EVENT__", 1)[1].split("__CYBER_EVENT_END__", 1)[0]
    payload = json.loads(payload_str)
    assert payload["type"] == "output"
    assert payload["content"] == "hello"


def test_emitter_deduplicates_non_tool_events():
    """Test deduplication works for non-tool events."""
    emitter = StdoutEventEmitter(operation_id="TEST_OP")
    buf = io.StringIO()

    event = {"type": "reasoning", "content": "thinking"}

    with redirect_stdout(buf):
        emitter.emit(event)
        emitter.emit(event)  # duplicate

    out = buf.getvalue()
    # Only one event should be present for duplicate
    occurrences = out.count("__CYBER_EVENT__")
    assert occurrences == 1, f"Expected 1 event, got {occurrences}"


def test_emitter_always_json_format():
    """Test that all events always emit JSON format (no CLI mode)."""
    emitter = StdoutEventEmitter(operation_id="TEST_OP")
    buf = io.StringIO()

    events = [
        {"type": "operation_init", "operation_id": "test-123", "target": "example.com"},
        {"type": "step_header", "step": 2, "maxSteps": 5},
        {"type": "reasoning", "content": "Analyzing"},
        {"type": "tool_start", "tool_name": "nmap"},
        {"type": "output", "content": "Test output"},
        {"type": "error", "content": "Error message"},
    ]

    with redirect_stdout(buf):
        for event in events:
            emitter.emit(event)

    out = buf.getvalue()

    # All events should be JSON formatted with markers
    event_count = out.count("__CYBER_EVENT__")
    assert event_count == len(events), (
        f"Expected {len(events)} events, got {event_count}"
    )

    # No human-readable formatting (CLI mode removed)
    assert "Operation initialization complete" not in out
    assert "[Step" not in out
    assert "💭" not in out
    assert "⚡ Executing:" not in out
    assert "❌ Error:" not in out

    # All output should be valid JSON
    event_matches = out.split("__CYBER_EVENT__")[1:]
    for match in event_matches:
        json_str = match.split("__CYBER_EVENT_END__")[0]
        parsed = json.loads(json_str)  # Should not raise
        assert "type" in parsed
        assert "id" in parsed
        assert "timestamp" in parsed
