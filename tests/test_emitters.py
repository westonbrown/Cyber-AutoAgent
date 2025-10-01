#!/usr/bin/env python3
"""
Tests for StdoutEventEmitter behavior:
- Ensures newline is printed with every event
- Verifies deduplication logic avoids duplicate emissions for identical events
"""

import io
import json
import os
from contextlib import redirect_stdout
from unittest.mock import patch

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


def test_cli_mode_operation_init():
    """Test CLI mode formats operation_init event correctly."""
    with patch.dict(os.environ, {"CYBER_UI_MODE": "cli"}):
        emitter = StdoutEventEmitter(operation_id="TEST_OP")
        buf = io.StringIO()

        event = {
            "type": "operation_init",
            "operation_id": "test-123",
            "target": "example.com",
            "objective": "Test objective",
        }

        with redirect_stdout(buf):
            emitter.emit(event)

        out = buf.getvalue()
        assert "Operation initialization complete" in out
        assert "test-123" in out
        assert "example.com" in out
        assert "Test objective" in out


def test_cli_mode_step_header():
    """Test CLI mode formats step_header event correctly."""
    with patch.dict(os.environ, {"CYBER_UI_MODE": "cli"}):
        emitter = StdoutEventEmitter(operation_id="TEST_OP")
        buf = io.StringIO()

        event = {"type": "step_header", "step": 2, "maxSteps": 5, "duration": "1.5s"}

        with redirect_stdout(buf):
            emitter.emit(event)

        out = buf.getvalue()
        assert "[Step 2/5]" in out
        assert "(1.5s)" in out


def test_cli_mode_reasoning():
    """Test CLI mode formats reasoning event correctly."""
    with patch.dict(os.environ, {"CYBER_UI_MODE": "cli"}):
        emitter = StdoutEventEmitter(operation_id="TEST_OP")
        buf = io.StringIO()

        event = {"type": "reasoning", "content": "Analyzing target"}

        with redirect_stdout(buf):
            emitter.emit(event)

        out = buf.getvalue()
        assert "💭" in out
        assert "Analyzing target" in out


def test_cli_mode_tool_execution():
    """Test CLI mode formats tool_start and tool_end events correctly."""
    with patch.dict(os.environ, {"CYBER_UI_MODE": "cli"}):
        emitter = StdoutEventEmitter(operation_id="TEST_OP")
        buf = io.StringIO()

        with redirect_stdout(buf):
            emitter.emit({"type": "tool_start", "tool_name": "nmap"})
            emitter.emit({"type": "tool_end", "tool_name": "nmap", "success": True})

        out = buf.getvalue()
        assert "⚡ Executing: nmap" in out
        assert "✅ Completed: nmap" in out


def test_cli_mode_output():
    """Test CLI mode formats output event correctly."""
    with patch.dict(os.environ, {"CYBER_UI_MODE": "cli"}):
        emitter = StdoutEventEmitter(operation_id="TEST_OP")
        buf = io.StringIO()

        event = {"type": "output", "content": "Test output content"}

        with redirect_stdout(buf):
            emitter.emit(event)

        out = buf.getvalue()
        assert "Test output content" in out
        assert "__CYBER_EVENT__" not in out  # CLI mode should not use event markers


def test_cli_mode_error():
    """Test CLI mode formats error event correctly."""
    with patch.dict(os.environ, {"CYBER_UI_MODE": "cli"}):
        emitter = StdoutEventEmitter(operation_id="TEST_OP")
        buf = io.StringIO()

        event = {"type": "error", "content": "Something went wrong"}

        with redirect_stdout(buf):
            emitter.emit(event)

        out = buf.getvalue()
        assert "❌ Error:" in out
        assert "Something went wrong" in out


def test_cli_mode_skips_internal_events():
    """Test CLI mode skips internal events that don't need display."""
    with patch.dict(os.environ, {"CYBER_UI_MODE": "cli"}):
        emitter = StdoutEventEmitter(operation_id="TEST_OP")
        buf = io.StringIO()

        internal_events = [
            {"type": "metrics_update", "content": "test"},
            {"type": "tool_input_update", "content": "test"},
            {"type": "thinking_end", "content": "test"},
            {"type": "tool_invocation_start", "content": "test"},
            {"type": "tool_invocation_end", "content": "test"},
        ]

        with redirect_stdout(buf):
            for event in internal_events:
                emitter.emit(event)

        out = buf.getvalue()
        assert out == "", "Internal events should produce no output in CLI mode"
