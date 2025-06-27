#!/usr/bin/env python3

import os
import re
from typing import List, Dict, Tuple
from datetime import datetime


def get_data_path(subdir=""):
    """Get the appropriate data path for current environment (Docker or local)"""
    base = "/app" if os.path.exists("/app") else os.getcwd()
    return os.path.join(base, subdir) if subdir else base


def sanitize_for_model(content: str) -> str:
    """Remove emojis and other non-ASCII characters that may cause model issues.
    
    This function sanitizes content before it's passed to the model while preserving
    the semantic meaning of the text.
    
    Args:
        content: Text content that may contain emojis
        
    Returns:
        Sanitized text with emojis removed/replaced
    """
    if not isinstance(content, str):
        return str(content)
    
    # Replace emojis with text equivalents for common ones used in the system
    replacements = {
        "🟢": "ABUNDANT BUDGET",
        "🟡": "CONSTRAINED BUDGET", 
        "🟠": "CRITICAL BUDGET",
        "🔴": "EMERGENCY BUDGET",
        "🚨": "CRITICAL",
        "✅": "SUCCESS",
        "❌": "ERROR",
        "⚠️": "WARNING",
        "🎯": "FOUND",
        "🔄": "EVOLVING",
        "🛠️": "CREATING",
        "🤔": "THINKING",
        "⚡": "EXECUTING",
        "ℹ️": "INFO",
        "→": "->",
        "←": "<-",
        "↑": "UP",
        "↓": "DOWN",
    }
    
    # Apply specific replacements first
    sanitized = content
    for emoji, replacement in replacements.items():
        sanitized = sanitized.replace(emoji, replacement)
    
    # More aggressive approach - keep only ASCII printable characters
    # This will remove ALL non-ASCII characters that could cause issues
    sanitized = re.sub(r'[^\x20-\x7E\n\r\t]', '', sanitized)
    
    # Clean up any double spaces created by character removal
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    return sanitized


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
        "FOUND": (Colors.GREEN, "🎯"),
        "EVOLVING": (Colors.CYAN, "🔄"),
        "CREATING": (Colors.YELLOW, "🛠️"),
    }
    color, emoji = status_config.get(status, (Colors.BLUE, "•"))
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(
        "%s[%s]%s %s %s[%s]%s %s"
        % (
            Colors.DIM,
            timestamp,
            Colors.RESET,
            emoji,
            color,
            status,
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

    import re

    # Look for explicit completion declaration - trust the agent's judgment
    for msg in reversed(messages[-5:]):  # Check last 5 messages
        if msg.get("role") == "assistant":
            # Handle both old string format and new structured format
            content_raw = msg.get("content", "")
            if isinstance(content_raw, list) and len(content_raw) > 0:
                # New format: content is a list of content blocks
                content = ""
                for block in content_raw:
                    if isinstance(block, dict) and "text" in block:
                        content += block["text"] + " "
                content = content.strip()
            else:
                # Old format: content is a string
                content = str(content_raw)

            # Check for explicit objective declaration
            if "objective achieved:" in content.lower():
                # Extract the agent's reasoning
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

    # No explicit completion - let agent continue
    return False, "", {}
