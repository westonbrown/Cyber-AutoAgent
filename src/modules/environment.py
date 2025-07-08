#!/usr/bin/env python3

import logging
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List

from .utils import Colors, get_data_path


def clean_operation_memory(operation_id: str):
    """Clean up memory data for a specific operation."""
    mem0_path = f"/tmp/mem0_{operation_id}"
    if os.path.exists(mem0_path):
        try:
            shutil.rmtree(mem0_path)
            print("%s[*] Cleaned up operation memory: %s%s" % (Colors.GREEN, mem0_path, Colors.RESET))
        except Exception as e:
            print("%s[!] Failed to clean %s: %s%s" % (Colors.RED, mem0_path, str(e), Colors.RESET))


def auto_setup(skip_mem0_cleanup: bool = False) -> List[str]:
    """Setup directories and discover available cyber tools"""
    # Create necessary directories in proper locations
    Path("tools").mkdir(exist_ok=True)  # Local tools directory for custom tools
    Path(get_data_path("logs")).mkdir(exist_ok=True)  # Logs directory

    # Note: Memory cleanup is handled per-operation to avoid conflicts
    # Each operation uses its own isolated memory path: /tmp/mem0_{operation_id}
    if skip_mem0_cleanup:
        print("%s[*] Using existing memory store%s" % (Colors.CYAN, Colors.RESET))

    print("%s[*] Discovering cyber security tools...%s" % (Colors.CYAN, Colors.RESET))

    # Just check which tools are available
    cyber_tools = {
        'nmap': 'Network discovery and security auditing',
        'nikto': 'Web server scanner',
        'sqlmap': 'SQL injection detection and exploitation',
        'gobuster': 'Directory/file brute-forcer',
        'netcat': 'Network utility for reading/writing data',
        'curl': 'HTTP client for web requests',
        'metasploit': 'Penetration testing framework',
        'iproute2': 'Provides modern networking tools (ip, ss, tc, etc.)',
        'net-tools': 'Provides classic networking utilities (netstat, ifconfig, route, etc.)',
    }

    available_tools = []

    # Check existing tools using subprocess for security
    for tool_name, description in cyber_tools.items():
        check_cmd = (
            ["which", tool_name]
            if tool_name != "metasploit"
            else ["which", "msfconsole"]
        )
        try:
            subprocess.run(check_cmd, capture_output=True, check=True, timeout=5)
            available_tools.append(tool_name)
            print(
                "  %s✓%s %-12s - %s"
                % (Colors.GREEN, Colors.RESET, tool_name, description)
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            print(
                "  %s○%s %-12s - %s %s(not available)%s"
                % (
                    Colors.YELLOW,
                    Colors.RESET,
                    tool_name,
                    description,
                    Colors.DIM,
                    Colors.RESET,
                )
            )

    print(
        "\n%s[+] Environment ready. %d cyber tools available.%s\n"
        % (Colors.GREEN, len(available_tools), Colors.RESET)
    )

    return available_tools


class TeeOutput:
    """Thread-safe output duplicator to both terminal and log file"""
    def __init__(self, stream, log_file):
        self.terminal = stream
        self.log = open(log_file, 'a', encoding='utf-8', buffering=1)  # Line buffering
        self.lock = threading.Lock()
        
    def write(self, message):
        with self.lock:
            self.terminal.write(message)
            self.terminal.flush()
            try:
                self.log.write(message)
                self.log.flush()
            except (ValueError, OSError):
                # Handle closed file gracefully
                pass
        
    def flush(self):
        with self.lock:
            self.terminal.flush()
            try:
                self.log.flush()
            except (ValueError, OSError):
                pass
        
    def close(self):
        with self.lock:
            try:
                self.log.close()
            except:
                pass
    
    # Additional methods to fully mimic file objects
    def fileno(self):
        return self.terminal.fileno()
    
    def isatty(self):
        return self.terminal.isatty()


def setup_logging(log_file: str = "cyber_operations.log", verbose: bool = False):
    """Configure unified logging for all operations with complete terminal capture"""
    # Ensure the directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Create header in log file
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write("\n" + "="*80 + "\n")
        f.write(f"CYBER-AUTOAGENT SESSION STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
    
    # Set up stdout and stderr redirection to capture ALL terminal output
    sys.stdout = TeeOutput(sys.stdout, log_file)
    sys.stderr = TeeOutput(sys.stderr, log_file)
    
    # Traditional logger setup for structured logging
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler - log everything to file
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler - only show warnings and above unless verbose
    # Note: This won't duplicate because we're using TeeOutput for stdout/stderr
    console_handler = logging.StreamHandler(sys.__stdout__)  # Use original stdout
    console_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console_handler.setFormatter(formatter)

    # Configure the logger specifically
    cyber_logger = logging.getLogger("CyberAutoAgent")
    cyber_logger.setLevel(logging.DEBUG)
    cyber_logger.addHandler(file_handler)
    if verbose:
        cyber_logger.addHandler(console_handler)
    cyber_logger.propagate = False  # Don't propagate to root logger

    # Suppress Strands framework error logging for expected step limit termination
    strands_event_loop_logger = logging.getLogger("strands.event_loop.event_loop")
    strands_event_loop_logger.setLevel(
        logging.CRITICAL
    )  # Only show critical errors, not our expected StopIteration
    
    # Capture all other loggers at INFO level to file
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_file_handler = logging.FileHandler(log_file, mode="a")
    root_file_handler.setLevel(logging.INFO)
    root_file_handler.setFormatter(formatter)
    root_logger.addHandler(root_file_handler)

    return cyber_logger
