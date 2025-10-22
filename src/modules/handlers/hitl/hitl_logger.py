"""Dedicated logger for HITL debugging with detailed trace output."""

import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

# Global HITL logger instance
_hitl_logger: Optional[logging.Logger] = None
_log_file_path: Optional[str] = None


def get_hitl_logger() -> logging.Logger:
    """Get or create the HITL debug logger.

    Returns:
        Logger instance configured for HITL debugging
    """
    global _hitl_logger
    if _hitl_logger is None:
        _hitl_logger = logging.getLogger("HITL")
        _hitl_logger.setLevel(logging.DEBUG)
    return _hitl_logger


def setup_hitl_logging(log_dir: str) -> str:
    """Configure HITL logging to write to dedicated debug file.

    Args:
        log_dir: Directory to create hitl_debug.log in

    Returns:
        Path to created log file
    """
    global _log_file_path

    # Create log directory if needed
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # HITL-specific log file
    _log_file_path = os.path.join(log_dir, "hitl_debug.log")

    logger = get_hitl_logger()

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create file handler with detailed formatting
    file_handler = logging.FileHandler(_log_file_path, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # Include microseconds and thread name for precise timing
    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(threadName)-20s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    # Write header
    with open(_log_file_path, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 100 + "\n")
        f.write(
            f"HITL DEBUG SESSION STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        f.write(f"Main Thread: {threading.current_thread().name}\n")
        f.write("=" * 100 + "\n\n")

    logger.info("HITL logging initialized at %s", _log_file_path)

    return _log_file_path


def log_hitl(component: str, message: str, level: str = "INFO", **kwargs):
    """Convenience function for HITL logging with component tagging.

    Args:
        component: Component name (UI, ExecService, InputHandler, etc.)
        message: Log message
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        **kwargs: Additional context to log
    """
    logger = get_hitl_logger()

    # Format message with component tag
    formatted_msg = f"[{component}] {message}"

    # Add kwargs as key=value pairs if provided
    if kwargs:
        context = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        formatted_msg = f"{formatted_msg} | {context}"

    # Log at appropriate level
    level_upper = level.upper()
    if level_upper == "DEBUG":
        logger.debug(formatted_msg)
    elif level_upper == "WARNING":
        logger.warning(formatted_msg)
    elif level_upper == "ERROR":
        logger.error(formatted_msg)
    else:
        logger.info(formatted_msg)


def get_log_file_path() -> Optional[str]:
    """Get path to current HITL log file.

    Returns:
        Path to log file if configured, None otherwise
    """
    return _log_file_path
