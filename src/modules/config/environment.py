#!/usr/bin/env python3

import logging
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List

from ..handlers.utils import Colors


def clean_operation_memory(operation_id: str, target_name: str = None):
    """Clean up memory data for a specific operation.

    Args:
        operation_id: The operation identifier
        target_name: The sanitized target name (optional, for unified output structure)
    """
    logger = logging.getLogger(__name__)
    logger.debug(
        "clean_operation_memory called with operation_id=%s, target_name=%s",
        operation_id,
        target_name,
    )

    if not target_name:
        logger.warning("No target_name provided, skipping memory cleanup")
        return

    # Unified output structure - per-target memory
    memory_path = os.path.join("outputs", target_name, "memory", f"mem0_faiss_{target_name}")
    logger.debug("Checking memory path: %s", memory_path)

    if os.path.exists(memory_path):
        try:
            # Safety check - ensure we're only removing memory directories
            if "mem0_faiss_" not in memory_path:
                logger.error(
                    "SAFETY CHECK FAILED: Path does not contain expected memory patterns: %s",
                    memory_path,
                )
                return

            logger.debug("About to remove memory path: %s", memory_path)
            if os.path.isdir(memory_path):
                shutil.rmtree(memory_path)
            else:
                os.remove(memory_path)

            logger.info("Cleaned up operation memory: %s", memory_path)
            print(f"{Colors.GREEN}[*] Cleaned up operation memory: {memory_path}{Colors.RESET}")

        except Exception as e:
            logger.error("Failed to clean %s: %s", memory_path, e)
            print(f"{Colors.RED}[!] Failed to clean {memory_path}: {e}{Colors.RESET}")
    else:
        logger.debug("Memory path does not exist: %s", memory_path)


def auto_setup(skip_mem0_cleanup: bool = False) -> List[str]:
    """Setup directories and discover available cyber tools"""
    # Create necessary directories in proper locations
    Path("tools").mkdir(exist_ok=True)  # Local tools directory for custom tools

    # Each operation uses its own isolated memory path: /tmp/mem0_{operation_id}
    if skip_mem0_cleanup:
        print("%s[*] Using existing memory store%s" % (Colors.CYAN, Colors.RESET))

    print("%s[*] Discovering cyber security tools...%s" % (Colors.CYAN, Colors.RESET))

    # Just check which tools are available
    cyber_tools = {
        "nmap": "Network discovery and security auditing",
        "nikto": "Web server scanner",
        "sqlmap": "SQL injection detection and exploitation",
        "gobuster": "Directory/file brute-forcer",
        "netcat": "Network utility for reading/writing data",
        "curl": "HTTP client for web requests",
        "metasploit": "Penetration testing framework",
        "tcpdump": "Network packet capture",
        "iproute2": "Provides modern networking tools (ip, ss, tc, etc.)",
        "net-tools": "Provides classic networking utilities (netstat, ifconfig, route, etc.)",
    }

    available_tools = []

    # Check existing tools using subprocess for security
    for tool_name, description in cyber_tools.items():
        tool_commands = {
            "metasploit": "msfconsole",
            "iproute2": "ip",
            "net-tools": "netstat",
        }
        check_cmd = ["which", tool_commands.get(tool_name, tool_name)]
        try:
            subprocess.run(check_cmd, capture_output=True, check=True, timeout=5)
            available_tools.append(tool_name)
            print("  %s✓%s %-12s - %s" % (Colors.GREEN, Colors.RESET, tool_name, description))
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
        "\n%s[+] Environment ready. %d cyber tools available.%s\n" % (Colors.GREEN, len(available_tools), Colors.RESET)
    )
    return available_tools


class TeeOutput:
    """Thread-safe output duplicator to both terminal and log file"""

    def __init__(self, stream, log_file):
        self.terminal = stream
        self.log = open(log_file, "a", encoding="utf-8", buffering=1)
        self.lock = threading.Lock()
        self.line_buffer = ""  # Buffer for incomplete lines

    def write(self, message):
        with self.lock:
            # Write to terminal as-is
            self.terminal.write(message)
            self.terminal.flush()

            # Clean message for log file
            try:
                # Remove ANSI escape sequences for log file
                ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
                clean_message = ansi_escape.sub("", message)

                # Handle carriage returns properly
                # If message contains \r without \n, it's likely overwriting the same line
                if "\r" in clean_message and "\r\n" not in clean_message:
                    # Split by \r and take the last part (what would be visible on screen)
                    parts = clean_message.split("\r")
                    # Keep only the last part after all overwrites
                    clean_message = parts[-1]
                    # If we had buffered content, clear it as it's being overwritten
                    self.line_buffer = ""

                # Add to line buffer
                self.line_buffer += clean_message

                # Write complete lines to log
                if "\n" in self.line_buffer:
                    lines = self.line_buffer.split("\n")
                    # Write all complete lines
                    for line in lines[:-1]:
                        # Strip any leading spaces that might cause indentation issues
                        # but preserve intentional indentation (2+ spaces)
                        if line and len(line) - len(line.lstrip()) > 30:
                            # This line has excessive leading spaces, likely from positioning
                            line = line.lstrip()
                        self.log.write(line + "\n")
                    # Keep the incomplete line in buffer
                    self.line_buffer = lines[-1]
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
                # Flush any remaining buffered content
                if self.line_buffer:
                    # Strip excessive leading spaces from final buffer
                    if len(self.line_buffer) - len(self.line_buffer.lstrip()) > 30:
                        self.line_buffer = self.line_buffer.lstrip()
                    self.log.write(self.line_buffer)
                    self.log.flush()
                self.log.close()
            except (OSError, AttributeError):
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
    with open(log_file, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"CYBER-AUTOAGENT SESSION STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

    # Set up stdout and stderr redirection to capture ALL terminal output
    sys.stdout = TeeOutput(sys.stdout, log_file)
    sys.stderr = TeeOutput(sys.stderr, log_file)

    # Traditional logger setup for structured logging
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # File handler - log everything to file
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler - only show warnings and above unless verbose
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
    strands_event_loop_logger.setLevel(logging.CRITICAL)  # Only show critical errors, not our expected StopIteration

    # Capture all other loggers at INFO level to file
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_file_handler = logging.FileHandler(log_file, mode="a")
    root_file_handler.setLevel(logging.INFO)
    root_file_handler.setFormatter(formatter)
    root_logger.addHandler(root_file_handler)

    return cyber_logger
