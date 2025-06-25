#!/usr/bin/env python3

import logging
import subprocess
import sys
from pathlib import Path
from typing import List

from .utils import Colors, get_data_path

def auto_setup() -> List[str]:
    """Setup directories and discover available cyber tools"""
    # Create necessary directories in proper locations
    Path('tools').mkdir(exist_ok=True)  # Local tools directory for custom tools
    Path(get_data_path('logs')).mkdir(exist_ok=True)  # Logs directory
    
    print("%s[*] Discovering cyber security tools...%s" % (Colors.CYAN, Colors.RESET))
    
    # Just check which tools are available
    cyber_tools = {
        'nmap': 'Network discovery and security auditing',
        'nikto': 'Web server scanner',
        'sqlmap': 'SQL injection detection and exploitation',
        'gobuster': 'Directory/file brute-forcer',
        'netcat': 'Network utility for reading/writing data',
        'curl': 'HTTP client for web requests',
        'metasploit': 'Penetration testing framework'
    }
    
    available_tools = []
    
    # Check existing tools using subprocess for security
    for tool_name, description in cyber_tools.items():
        check_cmd = ["which", tool_name] if tool_name != 'metasploit' else ["which", "msfconsole"]
        try:
            subprocess.run(check_cmd, capture_output=True, check=True, timeout=5)
            available_tools.append(tool_name)
            print("  %s✓%s %-12s - %s" % (Colors.GREEN, Colors.RESET, tool_name, description))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            print("  %s○%s %-12s - %s %s(not available)%s" % (Colors.YELLOW, Colors.RESET, tool_name, description, Colors.DIM, Colors.RESET))
    
    print("\n%s[+] Environment ready. %d cyber tools available.%s\n" % (Colors.GREEN, len(available_tools), Colors.RESET))
    
    return available_tools

def setup_logging(log_file: str = 'cyber_operations.log', verbose: bool = False):
    """Configure unified logging for all operations"""
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler - log everything to file
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Console handler - only show warnings and above unless verbose
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console_handler.setFormatter(formatter)
    
    # Configure the logger specifically
    cyber_logger = logging.getLogger('CyberAutoAgent')
    cyber_logger.setLevel(logging.DEBUG)
    cyber_logger.addHandler(file_handler)
    cyber_logger.addHandler(console_handler)
    cyber_logger.propagate = False  # Don't propagate to root logger
    
    # Suppress Strands framework error logging for expected step limit termination
    strands_event_loop_logger = logging.getLogger('strands.event_loop.event_loop')
    strands_event_loop_logger.setLevel(logging.CRITICAL)  # Only show critical errors, not our expected StopIteration
    
    return cyber_logger
