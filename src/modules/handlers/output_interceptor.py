"""
Output interceptor to capture all Python print statements and convert them to structured events.

This module ensures that only React Ink renders to the terminal by intercepting all
stdout/stderr writes and converting them to structured events.
"""

import sys
import io
import os
import threading
from typing import TextIO
from contextlib import contextmanager

from .utils import CyberEvent


class OutputInterceptor(io.TextIOBase):
    """Intercepts stdout/stderr and converts to structured events."""

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
            # Check if this is already a structured event
            if "__CYBER_EVENT__" in data:
                # Pass through structured events unchanged
                return self.original_stream.write(data)

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
        """Emit output as a structured event."""
        try:
            self._in_event_emission = True

            # Detect special output types
            if "MISSION PARAMETERS" in content:
                event_type = "initialization"
            elif "─" * 20 in content:
                event_type = "separator"
            elif any(marker in content for marker in ["✅", "❌", "⚠️", "ℹ️"]):
                event_type = "status"
            else:
                event_type = self.event_type

            event = CyberEvent(type=event_type, content=content, metadata={"source": "python_backend"})

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
        return self.original_stream.fileno() if hasattr(self.original_stream, "fileno") else -1

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False


@contextmanager
def intercept_output():
    """Context manager to intercept all Python output."""
    # Save original streams
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Check if we're in a React environment (has __REACT_INK__ env var)
    if not sys.stdout.isatty() or not os.environ.get("__REACT_INK__"):
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
    """Set up output interception for the entire application."""
    import os

    # Only intercept if running in React environment
    if os.environ.get("__REACT_INK__"):
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
