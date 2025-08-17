#!/usr/bin/env python3
"""
Utility functions for the handlers module.

This module contains general utility functions for file operations,
output formatting, and message analysis.
"""

import json
import os
import re
import shutil
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Tuple, Optional, Any, Union
from datetime import datetime


def get_terminal_width(default=80):
    """Get terminal width with fallback to default."""
    try:
        # Try to get actual terminal size
        size = shutil.get_terminal_size((default, 24))
        # Return a slightly smaller width to account for edge cases
        return max(40, min(size.columns - 2, default))
    except (OSError, ValueError):
        return default


def print_separator(char="─", color_start="", color_end=""):
    """Print a separator line that fits the terminal width."""
    width = get_terminal_width()
    if color_start and color_end:
        print(f"{color_start}{char * width}{color_end}")
    else:
        print(char * width)


def get_output_path(
    target_name: str,
    operation_id: str,
    subdir: str = "",
    base_dir: Optional[str] = None,
) -> str:
    """Get path for unified output directory structure.

    Args:
        target_name: Sanitized target name for organization
        operation_id: Unique operation identifier (should include OP_ prefix)
        subdir: Optional subdirectory within the operation directory
        base_dir: Optional base directory override (defaults to ./outputs)

    Returns:
        Full path in format: {base_dir}/{target_name}/{operation_id}/{subdir}
    """
    if base_dir is None:
        base_dir = os.path.join(os.getcwd(), "outputs")

    operation_dir = os.path.join(base_dir, target_name, operation_id)
    return os.path.join(operation_dir, subdir) if subdir else operation_dir


def sanitize_target_name(target: str) -> str:
    """Sanitize target string for safe filesystem usage.

    Args:
        target: Raw target string (URL, IP, domain, etc.)

    Returns:
        Sanitized string safe for filesystem usage
    """
    # Remove protocol prefixes
    sanitized = re.sub(r"^https?://", "", target)
    sanitized = re.sub(r"^ftp://", "", sanitized)

    # Remove path components (keep only domain/host part)
    sanitized = sanitized.split("/")[0]

    # Remove query parameters
    sanitized = sanitized.split("?")[0]

    # Remove port numbers
    sanitized = re.sub(r":\d+$", "", sanitized)

    # Replace unsafe characters with underscores
    sanitized = re.sub(r"[^\w\-.]", "_", sanitized)

    # Remove consecutive underscores
    sanitized = re.sub(r"_+", "_", sanitized)

    # Remove leading/trailing underscores and dots
    sanitized = sanitized.strip("_.")

    # Ensure non-empty result
    if not sanitized:
        sanitized = "unknown_target"

    return sanitized


def validate_output_path(path: str, base_dir: str) -> bool:
    """Validate that a path is within the allowed output directory.

    Args:
        path: Path to validate
        base_dir: Base directory that should contain the path

    Returns:
        True if path is safe and within base_dir, False otherwise
    """
    try:
        # Resolve both paths to absolute paths
        abs_path = os.path.abspath(path)
        abs_base = os.path.abspath(base_dir)

        # Check if path is within base directory
        common_path = os.path.commonpath([abs_path, abs_base])
        return common_path == abs_base
    except (ValueError, OSError):
        return False


def create_output_directory(path: str) -> bool:
    """Create output directory if it doesn't exist.

    Args:
        path: Directory path to create

    Returns:
        True if directory was created or already exists, False on error
    """
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError:
        return False


# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output formatting."""

    # Check if output is to a terminal (not redirected), Docker pseudo-TTY, or if colors are forced
    # Docker allocates a pseudo-TTY when -t flag is used, which makes isatty() return True
    # We also respect FORCE_COLOR env var which is set in docker-compose.yml
    _force_color = os.environ.get("FORCE_COLOR", "").lower() in ("1", "true", "yes")
    _is_tty = hasattr(os.sys.stdout, "isatty") and os.sys.stdout.isatty()
    _is_terminal = _is_tty or _force_color

    # Define colors only if outputting to terminal or colors are forced
    BLUE = "\033[94m" if _is_terminal else ""
    GREEN = "\033[92m" if _is_terminal else ""
    YELLOW = "\033[93m" if _is_terminal else ""
    RED = "\033[91m" if _is_terminal else ""
    CYAN = "\033[96m" if _is_terminal else ""
    MAGENTA = "\033[95m" if _is_terminal else ""
    BOLD = "\033[1m" if _is_terminal else ""
    DIM = "\033[2m" if _is_terminal else ""
    RESET = "\033[0m" if _is_terminal else ""


def print_banner():
    """Display operation banner with clean, centered ASCII art."""
    # Check if banner is disabled by environment variables
    import os

    if os.getenv("CYBERAGENT_NO_BANNER", "").lower() in ("1", "true", "yes") or os.getenv("__REACT_INK__") == "true":
        # Banner disabled - return early
        return

    banner_lines = [
        r" ██████╗██╗   ██╗██████╗ ███████╗██████╗ ",
        r"██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗",
        r"██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝",
        r"██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗",
        r"╚██████╗   ██║   ██████╔╝███████╗██║  ██║",
        r" ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝",
        r"",
        r"█████╗ ██╗   ██╗████████╗ ██████╗  █████╗  ██████╗ ███████╗███╗   ██╗████████╗",
        r"██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝",
        r"███████║██║   ██║   ██║   ██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ",
        r"██╔══██║██║   ██║   ██║   ██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ",
        r"██║  ██║╚██████╔╝   ██║   ╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ",
        r"╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ",
    ]

    subtitle = "-- Autonomous Cyber Agent --"

    banner_art_width = 0
    if banner_lines:
        banner_art_width = max(len(line.rstrip()) for line in banner_lines)

    padding_length = (banner_art_width - len(subtitle)) // 2
    centered_subtitle = (" " * max(0, padding_length)) + subtitle

    # Construct the full banner string
    full_banner = "\n".join(banner_lines) + "\n" + centered_subtitle

    # Print banner for CLI mode
    print("%s%s%s" % (Colors.CYAN, full_banner, Colors.RESET))


def print_section(title, content, color=Colors.BLUE, emoji=""):
    """Print formatted section with optional emoji."""
    # Check if output is disabled by environment variables
    import os

    if os.getenv("CYBERAGENT_NO_BANNER", "").lower() in ("1", "true", "yes") or os.getenv("__REACT_INK__") == "true":
        # Output disabled - return early
        return

    # Print section for CLI mode
    print("\n%s" % ("─" * 60))
    print("%s %s%s%s%s" % (emoji, color, Colors.BOLD, title, Colors.RESET))
    print("%s" % ("─" * 60))
    print(content)


def print_status(message, status="INFO"):
    """Print status message with color coding and emojis."""
    # Check if output is disabled by environment variables
    import os

    if os.getenv("CYBERAGENT_NO_BANNER", "").lower() in ("1", "true", "yes") or os.getenv("__REACT_INK__") == "true":
        # Output disabled - return early
        return

    # Print status for CLI mode
    status_config = {
        "INFO": (Colors.BLUE, "ℹ️"),
        "SUCCESS": (Colors.GREEN, "✅"),
        "WARNING": (Colors.YELLOW, "⚠️"),
        "ERROR": (Colors.RED, "❌"),
        "THINKING": (Colors.MAGENTA, "🤔"),
        "EXECUTING": (Colors.CYAN, "⚡"),
        "FOUND": (Colors.GREEN, "[SCAN]"),
    }
    color, prefix = status_config.get(status, (Colors.BLUE, "[INFO]"))
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(
        "%s[%s]%s %s %s%s %s"
        % (
            Colors.DIM,
            timestamp,
            Colors.RESET,
            prefix,
            color,
            Colors.RESET,
            message,
        )
    )


def analyze_objective_completion(messages: List[Dict]) -> Tuple[bool, str, Dict]:
    """Check if agent has declared objective completion through self-assessment.

    Returns:
        (is_complete, summary, metadata)
    """
    if not messages:
        return False, "", {}

    # Look for explicit completion declaration - trust the agent's judgment
    for msg in reversed(messages[-5:]):  # Check last 5 messages
        if msg.get("role") == "assistant":
            content_raw = msg.get("content", "")
            if isinstance(content_raw, list) and len(content_raw) > 0:
                content = ""
                for block in content_raw:
                    if isinstance(block, dict) and "text" in block:
                        content += block["text"] + " "
                content = content.strip()
            else:
                content = str(content_raw)

            # Check for explicit objective declaration
            if "objective achieved:" in content.lower():
                match = re.search(
                    r"objective achieved:(.+?)(?:\n|$)",
                    content,
                    re.IGNORECASE | re.DOTALL,
                )
                if match:
                    summary = match.group(1).strip()

                    # Extract any confidence or completion percentage mentioned
                    confidence_match = re.search(r"(\d+)%", content)
                    confidence = int(confidence_match.group(1)) if confidence_match else 100

                    return (
                        True,
                        summary,
                        {"confidence": confidence, "agent_determined": True},
                    )
                return (
                    True,
                    "Agent declared objective complete",
                    {"confidence": 100, "agent_determined": True},
                )

            # Check for flag pattern (CTF-style flags)
            flag_match = re.search(r"FLAG\{[^}]+\}", content)
            if flag_match:
                flag = flag_match.group(0)
                # Also check for success indicators near the flag
                if any(
                    indicator in content.lower()
                    for indicator in [
                        "congratulations",
                        "success",
                        "correct",
                        "flag obtained",
                        "flag found",
                    ]
                ):
                    return (
                        True,
                        f"Flag obtained: {flag}",
                        {"confidence": 100, "flag_detected": True},
                    )

            # Check for other success indicators that might indicate completion
            success_indicators = [
                "successfully obtained flag",
                "flag obtained",
                "challenge complete",
                "challenge solved",
                "objective complete",
            ]

            for indicator in success_indicators:
                if indicator in content.lower():
                    return (
                        True,
                        f"Success indicator detected: {indicator}",
                        {"confidence": 95, "success_indicator": True},
                    )

    return False, "", {}



@dataclass
class CyberEvent:
    """Structured event for terminal output."""

    type: str  # 'step_start', 'command', 'command_array', 'output', 'error', 'status', 'complete'
    content: Union[str, List[str]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_json(self) -> str:
        """Convert event to JSON with special markers for parsing."""
        return f"__CYBER_EVENT__{json.dumps(asdict(self), separators=(',', ':'))}__CYBER_EVENT_END__"


def emit_event(event_type: str, content: Union[str, List[str]], **metadata) -> None:
    """Emit a structured event to stdout for React parsing.

    This replaces direct print() calls to prevent garbled output.
    Events are wrapped in special markers for reliable parsing.

    Args:
        event_type: Type of event (step_start, command, output, etc.)
        content: Event content (string or list of strings)
        **metadata: Additional metadata (step number, tool name, etc.)
    """
    event = CyberEvent(type=event_type, content=content, metadata=metadata)
    # Use print with flush to ensure immediate output
    print(event.to_json(), flush=True)


def emit_step_start(step: int, total_steps: int, tool_name: str) -> None:
    """Emit a step start event."""
    emit_event("step_start", tool_name, step=step, total_steps=total_steps)


def emit_command(command: Union[str, List[str]]) -> None:
    """Emit a command execution event."""
    if isinstance(command, list):
        emit_event("command_array", command)
    else:
        emit_event("command", command)


def emit_output(output: str) -> None:
    """Emit tool output event."""
    # Emit the entire output as a single event
    # The UI will handle formatting and display
    if output.strip():
        emit_event("output", output.strip())


def emit_error(error: str) -> None:
    """Emit an error event."""
    emit_event("error", error, level="error")


def emit_status(message: str, level: str = "info") -> None:
    """Emit a status message event."""
    emit_event("status", message, level=level)
