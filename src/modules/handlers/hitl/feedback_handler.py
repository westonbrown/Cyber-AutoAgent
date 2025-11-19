"""Handler for receiving feedback from React UI via stdin."""

import json
import logging
import select
import sys
import threading
from typing import Optional

from .feedback_manager import FeedbackManager
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
        if self._running:
            logger.warning("Feedback listener already running")
            return

        self._running = True
        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="HITLFeedbackListener",
        )
        self._listener_thread.start()
        logger.info("Feedback listener started")

    def stop_listening(self) -> None:
        """Stop listening for feedback commands."""
        self._running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=1.0)
        logger.info("Feedback listener stopped")

    def _listen_loop(self) -> None:
        """Main listening loop for stdin commands (runs in background thread)."""
        import time

        logger.info("[HITL-InputHandler] Listener thread STARTED - monitoring stdin")

        iteration = 0
        last_heartbeat = time.time()

        while self._running:
            iteration += 1
            current_time = time.time()

            # Heartbeat every 5 seconds to prove thread is alive
            if current_time - last_heartbeat > 5:
                logger.info(f"[HITL-InputHandler] Heartbeat - iteration {iteration}")
                last_heartbeat = current_time

            try:
                # Check if stdin has data available (non-blocking)
                if select.select([sys.stdin], [], [], 0.5)[0]:
                    logger.info(
                        f"[HITL-InputHandler] Stdin data available at iteration {iteration}"
                    )
                    line = sys.stdin.readline()
                    if line:
                        logger.warning(
                            f"[HITL-InputHandler] Line received: {line[:200]}"
                        )
                        self._process_input_line(line)
            except Exception as e:
                logger.error("Error in feedback listener: %s", e, exc_info=True)

        logger.info("[HITL-InputHandler] Listener thread EXITED")

    def _process_input_line(self, line: str) -> None:
        """Process a line of input from stdin.

        Args:
            line: Input line to process
        """
        # Check for test marker
        if "TEST_STDIN_WORKS" in line:
            logger.warning(
                "[HITL-InputHandler] TEST STDIN WORKS - stdin is functional!"
            )

        # Look for HITL command format: __HITL_COMMAND__<json>__HITL_COMMAND_END__
        if "__HITL_COMMAND__" in line:
            logger.info("[HITL-InputHandler] HITL command detected, parsing...")
            try:
                start = line.index("__HITL_COMMAND__") + len("__HITL_COMMAND__")
                end = line.index("__HITL_COMMAND_END__")
                command_json = line[start:end]
                command = json.loads(command_json)
                logger.info(
                    f"[HITL-InputHandler] Command parsed: type={command.get('type')}"
                )
                self.handle_feedback_command(command)
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning("Failed to parse HITL command: %s", e)

    def handle_feedback_command(self, command: dict) -> None:
        """Process feedback command from UI.

        Args:
            command: Feedback command dictionary with fields:
                - type: Command type ("submit_feedback", "request_pause")
                - Additional fields depending on type
        """
        command_type = command.get("type")

        logger.info("Received HITL command: %s", command_type)

        if command_type == "submit_feedback":
            self._handle_submit_feedback(command)
        elif command_type == "request_pause":
            self._handle_pause_request(command)
        else:
            logger.warning("Unknown feedback command type: %s", command_type)

    def _handle_submit_feedback(self, command: dict) -> None:
        """Handle feedback submission command.

        Args:
            command: Command dict with feedback_type, content, tool_id
        """
        try:
            feedback_type_str = command.get("feedback_type", "correction")
            feedback_type = FeedbackType(feedback_type_str)
            content = command.get("content", "")
            tool_id = command.get("tool_id", "")

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

        except Exception as e:
            logger.error("Failed to submit feedback: %s", e, exc_info=True)

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
