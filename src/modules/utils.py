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
    print("%s%s%s" % (Colors.CYAN, full_banner, Colors.RESET))

def print_section(title, content, color=Colors.BLUE, emoji=""):
    """Print formatted section with optional emoji"""
    print("\n%s" % ('─'*60))
    print("%s %s%s%s%s" % (emoji, color, Colors.BOLD, title, Colors.RESET))
    print("%s" % ('─'*60))
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
    print("%s[%s]%s %s %s[%s]%s %s" % (Colors.DIM, timestamp, Colors.RESET, emoji, color, status, Colors.RESET, message))

def analyze_objective_completion(messages: List[Dict], objective: str = None) -> Tuple[bool, float, str]:
    """Check if agent has achieved objective based on their own evaluation
    
    Returns:
        (is_complete, confidence_score, completion_summary)
    """
    if not messages:
        return False, 0.0, ""
    
    # Look for explicit completion declaration by the agent
    for msg in reversed(messages[-5:]):  # Check last 5 messages
        if msg.get("role") == "assistant":
            content = str(msg.get("content", ""))
            
            # Agent's explicit declaration takes precedence
            if "objective achieved:" in content.lower():
                # Extract the agent's reasoning
                match = re.search(r"objective achieved:(.+?)(?:\n|$)", content, re.IGNORECASE | re.DOTALL)
                if match:
                    summary = match.group(1).strip()
                    return True, 1.0, summary
                return True, 1.0, "Agent declared objective complete"
    
    # If objective provided, check for relevant evidence (as guidance only)
    if objective:
        from .objective_evaluator import ObjectiveEvaluator
        evaluator = ObjectiveEvaluator(objective)
        
        # Gather evidence from recent messages
        evidence = []
        for msg in messages[-10:]:  # Last 10 messages
            if msg.get("role") == "assistant":
                content = str(msg.get("content", "")).lower()
                if any(keyword in content for keyword in ['found', 'discovered', 'extracted', 'gained', 'compromised']):
                    evidence.append({'content': content, 'category': 'finding'})
        
        relevance, matches = evaluator.evaluate_evidence(evidence)
        
        # High relevance might indicate completion (but agent decides)
        if relevance > 0.7 and matches:
            return False, relevance, f"High relevance ({relevance:.0%}) but agent hasn't declared completion"
    
    return False, 0.0, ""
