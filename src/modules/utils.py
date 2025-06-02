#!/usr/bin/env python3

from typing import List, Dict
from datetime import datetime

# ANSI color codes for terminal output
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

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
        r"╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   "
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
    print(f"{Colors.CYAN}{full_banner}{Colors.RESET}")

def print_section(title, content, color=Colors.BLUE, emoji=""):
    """Print formatted section with optional emoji"""
    print(f"\n{'─'*60}")
    print(f"{emoji} {color}{Colors.BOLD}{title}{Colors.RESET}")
    print(f"{'─'*60}")
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
        "CREATING": (Colors.YELLOW, "🛠️")
    }
    color, emoji = status_config.get(status, (Colors.BLUE, "•"))
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{Colors.DIM}[{timestamp}]{Colors.RESET} {emoji} {color}[{status}]{Colors.RESET} {message}")

#TODO improve objective completion logic. We should decompose sub goals from the plan and critic each sub step
def analyze_objective_completion(messages: List[Dict]) -> bool:
    """Check if agent explicitly declared objective achievement or demonstrated security impact"""
    if not messages:
        return False
    
    # Look for explicit completion declaration
    for msg in reversed(messages[-3:]):
        if msg.get("role") == "assistant":
            content = str(msg.get("content", "")).lower()
            if "objective achieved:" in content:
                return True
    
    # Check for security impact indicators in recent messages
    security_impact_indicators = [
        "user credentials extracted",
        "database compromised",
        "command execution",
        "shell access",
        "data exfiltration",
        "privilege escalation",
        "administrative access",
        "passwords dumped",
        "database dump",
        "credentials found"
    ]
    
    # Look in last 2 messages for security impact
    for msg in reversed(messages[-2:]):
        if msg.get("role") == "assistant":
            content = str(msg.get("content", "")).lower()
            for indicator in security_impact_indicators:
                if indicator in content:
                    return True
    
    return False