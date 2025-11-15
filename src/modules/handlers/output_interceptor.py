"""
Unified output interceptor.

Intercepts stdout/stderr lines and emits structured __CYBER_EVENT__ messages.
Supports two modes via environment variable CYBER_UI_MODE:
- react: buffer tool output, emit once, tag metadata to avoid truncation.
- cli: minimal interception (pass-through for performance) unless a structured
  event is detected.
"""

import io
import os
import sys
import threading
from contextlib import contextmanager
from typing import List, TextIO

from .utils import CyberEvent

# Global state for tool execution and output buffering
_in_tool_execution = False
_tool_execution_lock = threading.Lock()
_tool_output_buffer: List[str] = []
_tool_error_buffer: List[str] = []


def set_tool_execution_state(is_executing: bool):
    """Set global tool execution state and manage buffer when tool starts/ends."""
    global _in_tool_execution, _tool_output_buffer, _tool_error_buffer
    with _tool_execution_lock:
        _in_tool_execution = is_executing
        if is_executing:
            # Starting tool execution - clear buffers
            _tool_output_buffer = []
            _tool_error_buffer = []
        # When ending tool execution, buffers are returned by getters


def is_in_tool_execution() -> bool:
    """Check if we're currently executing a tool."""
    with _tool_execution_lock:
        return _in_tool_execution


def get_buffered_output() -> str:
    """Get and clear the buffered tool stdout."""
    global _tool_output_buffer
    with _tool_execution_lock:
        output = "\n".join(_tool_output_buffer)
        _tool_output_buffer = []
        return output


def get_buffered_error_output() -> str:
    """Get and clear the buffered tool stderr."""
    global _tool_error_buffer
    with _tool_execution_lock:
        output = "\n".join(_tool_error_buffer)
        _tool_error_buffer = []
        return output


class OutputInterceptor(io.TextIOBase):
    """Intercept stdout/stderr and convert lines to structured events.

    In React mode, tool output is buffered and emitted once as a single event.
    In CLI mode, this acts as a conservative pass-through.
    """

    def __init__(self, original_stream: TextIO, event_type: str = "output"):
        self.original_stream = original_stream
        self.event_type = event_type
        self.buffer = io.StringIO()
        self.lock = threading.Lock()
        self._in_event_emission = False

    def write(self, data: str) -> int:
        """Intercept write calls and emit as events."""
        if not data:
            return 0

        # Prevent recursion when emitting events
        if self._in_event_emission:
            return self.original_stream.write(data)

        with self.lock:
            # Structured events pass through unchanged
            if "__CYBER_EVENT__" in data:
                # Pass through structured events unchanged and flush immediately
                result = self.original_stream.write(data)
                if hasattr(self.original_stream, "flush"):
                    self.original_stream.flush()
                return result

            # Buffer the data
            self.buffer.write(data)

            # Check if we have complete lines to emit
            content = self.buffer.getvalue()
            if "\n" in content:
                lines = content.split("\n")
                # Keep the last incomplete line in buffer
                self.buffer = io.StringIO()
                if lines[-1]:
                    self.buffer.write(lines[-1])

                # Emit complete lines as events
                for line in lines[:-1]:
                    if line.strip():  # Skip empty lines
                        self._emit_output_event(line)

            return len(data)

    def _emit_output_event(self, content: str):
        """Emit output as a structured event or buffer during tool execution."""
        global _tool_output_buffer

        # During tool execution, buffer the output instead of emitting line by line
        if is_in_tool_execution():
            with _tool_execution_lock:
                if self.event_type == "error":
                    _tool_error_buffer.append(content)
                else:
                    _tool_output_buffer.append(content)
            return  # Don't emit individual lines during tool execution

        try:
            self._in_event_emission = True

            # Detect special output types (best-effort)
            if "MISSION PARAMETERS" in content:
                event_type = "initialization"
            elif "─" * 20 in content:
                event_type = "separator"
            elif any(marker in content for marker in ["✅", "❌", "⚠️", "ℹ️"]):
                event_type = "status"
            else:
                event_type = self.event_type

            # Add metadata to prevent truncation if this is during tool execution
            metadata = {"source": "python_backend"}
            if is_in_tool_execution():
                metadata["fromToolBuffer"] = True
                metadata["tool"] = "shell"  # Most tool outputs are from shell

            event = CyberEvent(type=event_type, content=content, metadata=metadata)

            # Write the structured event to the original stream
            self.original_stream.write(event.to_json() + "\n")
            self.original_stream.flush()

        finally:
            self._in_event_emission = False

    def flush(self):
        """Flush any remaining buffered content."""
        with self.lock:
            content = self.buffer.getvalue()
            if content.strip():
                self._emit_output_event(content)
                self.buffer = io.StringIO()
            self.original_stream.flush()

    def isatty(self):
        """Check if the stream is a TTY."""
        return hasattr(self.original_stream, "isatty") and self.original_stream.isatty()

    # Implement other required methods
    def fileno(self):
        return (
            self.original_stream.fileno()
            if hasattr(self.original_stream, "fileno")
            else -1
        )

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False


@contextmanager
def intercept_output():
    """Context manager to intercept stdout/stderr in React mode."""
    # Save original streams
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Determine UI mode from environment
    ui_mode = os.environ.get("CYBER_UI_MODE", "cli").lower()
    # Only intercept in React UI mode
    if ui_mode != "react":
        # Not in React environment, don't intercept
        yield
        return

    try:
        # Replace with interceptors
        sys.stdout = OutputInterceptor(original_stdout, "output")
        sys.stderr = OutputInterceptor(original_stderr, "error")

        yield

    finally:
        # Flush any remaining content
        if hasattr(sys.stdout, "flush"):
            sys.stdout.flush()
        if hasattr(sys.stderr, "flush"):
            sys.stderr.flush()

        # Restore original streams
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def setup_output_interception():
    """Install interceptors globally when running in React mode."""
    import os

    # Only intercept if running in React environment
    if os.environ.get("CYBER_UI_MODE", "cli").lower() == "react":
        sys.stdout = OutputInterceptor(sys.stdout, "output")
        sys.stderr = OutputInterceptor(sys.stderr, "error")

        # Also redirect print function for extra safety
        import builtins

        # original_print = builtins.print

        def intercepted_print(*args, **kwargs):
            """Intercepted print function."""
            # Convert to string
            output = " ".join(str(arg) for arg in args)

            # Get file parameter
            file = kwargs.get("file", sys.stdout)

            # Write to the file (which might be our interceptor)
            file.write(output)
            if kwargs.get("end", "\n"):
                file.write(kwargs.get("end", "\n"))

            # Handle flush
            if kwargs.get("flush", False) and hasattr(file, "flush"):
                file.flush()

        builtins.print = intercepted_print
