#!/usr/bin/env python3
"""
Tests for StdoutEventEmitter behavior:
- Ensures newline is printed with every event
- Verifies deduplication logic avoids duplicate emissions for identical events
"""

import io
import json
from contextlib import redirect_stdout

from modules.handlers.events.emitters import StdoutEventEmitter


def test_emitter_appends_newline_and_serializes_output():
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
