"""Handler for receiving feedback from React UI via stdin."""

import json
import logging
import select
import sys
import threading
from typing import Optional

from .feedback_manager import FeedbackManager
from .hitl_logger import log_hitl
from .types import FeedbackType

logger = logging.getLogger(__name__)


class FeedbackInputHandler:
    """Handles incoming feedback from React UI via stdin commands."""

    def __init__(self, feedback_manager: FeedbackManager):
        """Initialize feedback input handler.

        Args:
            feedback_manager: FeedbackManager instance
        """
        self.feedback_manager = feedback_manager
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None

        logger.info("FeedbackInputHandler initialized")

    def start_listening(self) -> None:
        """Start listening for feedback commands in background thread."""
        log_hitl("InputHandler", "start_listening() called", "INFO")

        if self._running:
            logger.warning("Feedback listener already running")
            log_hitl("InputHandler", "Listener already running - skipping", "WARNING")
            return

        self._running = True
        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="HITLFeedbackListener",
        )
        self._listener_thread.start()
        logger.info("Feedback listener started")
        log_hitl(
            "InputHandler",
            f"✓ Feedback listener thread started: {self._listener_thread.name}",
            "INFO",
            thread_id=self._listener_thread.ident,
        )

    def stop_listening(self) -> None:
        """Stop listening for feedback commands."""
        self._running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=1.0)
        logger.info("Feedback listener stopped")

    def _listen_loop(self) -> None:
        """Main listening loop for stdin commands (runs in background thread)."""
        import time

        log_hitl("InputHandler", "=== LISTEN LOOP STARTED ===", "INFO")
        logger.info("[HITL-InputHandler] Listener thread STARTED - monitoring stdin")

        # Log stdin status
        try:
            log_hitl(
                "InputHandler",
                f"stdin status: isatty={sys.stdin.isatty()}, fileno={sys.stdin.fileno()}, closed={sys.stdin.closed}",
                "INFO",
            )
        except Exception as e:
            log_hitl("InputHandler", f"Failed to get stdin status: {e}", "ERROR")

        iteration = 0
        last_heartbeat = time.time()

        while self._running:
            iteration += 1
            current_time = time.time()

            # Heartbeat every 5 seconds to prove thread is alive
            if current_time - last_heartbeat > 5:
                log_hitl(
                    "InputHandler",
                    f"❤️ Thread alive - iteration {iteration}",
                    "INFO",
                )
                logger.info(f"[HITL-InputHandler] Heartbeat - iteration {iteration}")
                last_heartbeat = current_time

            try:
                # Check if stdin has data available (non-blocking)
                if select.select([sys.stdin], [], [], 0.5)[0]:
                    log_hitl(
                        "InputHandler",
                        f"✓ STDIN HAS DATA [iter {iteration}]",
                        "INFO",
                    )
                    logger.info(
                        f"[HITL-InputHandler] Stdin data available at iteration {iteration}"
                    )
                    line = sys.stdin.readline()
                    if line:
                        log_hitl(
                            "InputHandler",
                            f"★ LINE RECEIVED ({len(line)} chars): {line[:100]}",
                            "WARNING",  # Use WARNING so it's always visible
                        )
                        logger.warning(
                            f"[HITL-InputHandler] Line received: {line[:200]}"
                        )
                        self._process_input_line(line)
                    else:
                        log_hitl("InputHandler", "Empty line received", "DEBUG")
            except Exception as e:
                logger.error("Error in feedback listener: %s", e, exc_info=True)
                log_hitl("InputHandler", f"ERROR in listen loop: {e}", "ERROR")

        log_hitl("InputHandler", "=== LISTEN LOOP EXITED ===", "INFO")
        logger.info("[HITL-InputHandler] Listener thread EXITED")

    def _process_input_line(self, line: str) -> None:
        """Process a line of input from stdin.

        Args:
            line: Input line to process
        """
        # Log ALL input lines for debugging
        log_hitl(
            "InputHandler",
            f"Processing line: length={len(line)}, preview={line[:150]}",
            "INFO",
        )

        # Check for test marker
        if "TEST_STDIN_WORKS" in line:
            log_hitl("InputHandler", "✓✓✓ TEST STDIN SUCCESS ✓✓✓", "WARNING")
            logger.warning(
                "[HITL-InputHandler] TEST STDIN WORKS - stdin is functional!"
            )

        # Look for HITL command format: __HITL_COMMAND__<json>__HITL_COMMAND_END__
        if "__HITL_COMMAND__" in line:
            log_hitl("InputHandler", "✓ HITL command markers found in line", "INFO")
            logger.info("[HITL-InputHandler] HITL command detected, parsing...")
            try:
                start = line.index("__HITL_COMMAND__") + len("__HITL_COMMAND__")
                end = line.index("__HITL_COMMAND_END__")
                command_json = line[start:end]
                log_hitl(
                    "InputHandler",
                    f"Extracted JSON ({len(command_json)} chars)",
                    "DEBUG",
                    json_preview=command_json[:100],
                )
                command = json.loads(command_json)
                log_hitl(
                    "InputHandler",
                    f"✓ Parsed command successfully: type={command.get('type')}",
                    "INFO",
                )
                logger.info(
                    f"[HITL-InputHandler] Command parsed: type={command.get('type')}"
                )
                self.handle_feedback_command(command)
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning("Failed to parse HITL command: %s", e)
                log_hitl(
                    "InputHandler", f"ERROR: Failed to parse command: {e}", "ERROR"
                )
        else:
            log_hitl(
                "InputHandler",
                "No HITL markers in line - treating as regular input",
                "DEBUG",
            )

    def handle_feedback_command(self, command: dict) -> None:
        """Process feedback command from UI.

        Args:
            command: Feedback command dictionary with fields:
                - type: Command type ("submit_feedback", "request_pause")
                - Additional fields depending on type
        """
        command_type = command.get("type")

        logger.info("Received HITL command: %s", command_type)
        log_hitl("InputHandler", f"Routing command type: {command_type}", "INFO")

        if command_type == "submit_feedback":
            log_hitl("InputHandler", "→ Calling _handle_submit_feedback()", "INFO")
            self._handle_submit_feedback(command)
        elif command_type == "request_pause":
            log_hitl("InputHandler", "→ Calling _handle_pause_request()", "INFO")
            self._handle_pause_request(command)
        else:
            logger.warning("Unknown feedback command type: %s", command_type)
            log_hitl(
                "InputHandler", f"ERROR: Unknown command type: {command_type}", "ERROR"
            )

    def _handle_submit_feedback(self, command: dict) -> None:
        """Handle feedback submission command.

        Args:
            command: Command dict with feedback_type, content, tool_id
        """
        log_hitl("InputHandler", "_handle_submit_feedback() entered", "INFO")
        try:
            feedback_type_str = command.get("feedback_type", "correction")
            feedback_type = FeedbackType(feedback_type_str)
            content = command.get("content", "")
            tool_id = command.get("tool_id", "")

            log_hitl(
                "InputHandler",
                "Calling feedback_manager.submit_feedback()",
                "INFO",
                feedback_type=feedback_type.value,
                content_length=len(content),
                tool_id=tool_id,
            )

            self.feedback_manager.submit_feedback(
                feedback_type=feedback_type,
                content=content,
                tool_id=tool_id,
            )

            logger.info(
                "Feedback submitted: type=%s, tool_id=%s",
                feedback_type.value,
                tool_id,
            )
            log_hitl("InputHandler", "✓ Feedback submitted successfully", "INFO")

        except Exception as e:
            logger.error("Failed to submit feedback: %s", e, exc_info=True)
            log_hitl("InputHandler", f"ERROR: Failed to submit feedback: {e}", "ERROR")

    def _handle_pause_request(self, command: dict) -> None:
        """Handle pause request from user.

        Blocks listener thread until feedback received or timeout.

        Args:
            command: Command dict with optional 'is_manual' field
        """
        try:
            is_manual = command.get("is_manual", True)
            self.feedback_manager.request_pause(is_manual=is_manual)

            # Block until feedback or timeout
            # This runs on listener thread, so it doesn't block agent
            feedback_received = self.feedback_manager.wait_for_feedback()

            if feedback_received:
                logger.info("Pause resumed after feedback")
            else:
                logger.warning("Pause timed out - auto-resumed")

        except Exception as e:
            logger.error("Failed to handle pause request: %s", e, exc_info=True)
