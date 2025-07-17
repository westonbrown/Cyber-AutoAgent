#!/usr/bin/env python3

import os
import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime


def get_data_path(subdir: str = "", base_dir: Optional[str] = None) -> str:
    """Get the appropriate data path with optional base directory override.

    Args:
        subdir: Subdirectory to append to base path
        base_dir: Optional base directory override (defaults to current working directory)

    Returns:
        Full path combining base directory and subdirectory
    """
    base = base_dir if base_dir is not None else os.getcwd()
    return os.path.join(base, subdir) if subdir else base


def get_output_path(
    target_name: str,
    operation_id: str,
    subdir: str = "",
    base_dir: Optional[str] = None,
) -> str:
    """Get path for unified output directory structure.

    Args:
        target_name: Sanitized target name for organization
        operation_id: Unique operation identifier
        subdir: Optional subdirectory within the operation directory
        base_dir: Optional base directory override (defaults to ./outputs)

    Returns:
        Full path in format: {base_dir}/{target_name}/OP_{operation_id}/{subdir}
    """
    if base_dir is None:
        base_dir = os.path.join(os.getcwd(), "outputs")

    operation_dir = os.path.join(base_dir, target_name, f"OP_{operation_id}")
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
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner():
    """Display operation banner with clean, centered ASCII art."""
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

    # Print the banner with color
    print("%s%s%s" % (Colors.CYAN, full_banner, Colors.RESET))


def print_section(title, content, color=Colors.BLUE, emoji=""):
    """Print formatted section with optional emoji"""
    print("\n%s" % ("─" * 60))
    print("%s %s%s%s%s" % (emoji, color, Colors.BOLD, title, Colors.RESET))
    print("%s" % ("─" * 60))
    print(content)


def print_status(message, status="INFO"):
    """Print status message with color coding and emojis"""
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
                    confidence = (
                        int(confidence_match.group(1)) if confidence_match else 100
                    )

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
