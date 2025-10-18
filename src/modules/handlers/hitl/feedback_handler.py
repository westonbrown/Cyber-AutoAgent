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
        while self._running:
            try:
                # Check if stdin has data available (non-blocking)
                if select.select([sys.stdin], [], [], 0.5)[0]:
                    line = sys.stdin.readline()
                    if line:
                        self._process_input_line(line)
            except Exception as e:
                logger.error("Error in feedback listener: %s", e, exc_info=True)

    def _process_input_line(self, line: str) -> None:
        """Process a line of input from stdin.

        Args:
            line: Input line to process
        """
        # Look for HITL command format: __HITL_COMMAND__<json>__HITL_COMMAND_END__
        if "__HITL_COMMAND__" in line:
            try:
                start = line.index("__HITL_COMMAND__") + len("__HITL_COMMAND__")
                end = line.index("__HITL_COMMAND_END__")
                command_json = line[start:end]
                command = json.loads(command_json)
                self.handle_feedback_command(command)
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning("Failed to parse HITL command: %s", e)

    def handle_feedback_command(self, command: dict) -> None:
        """Process feedback command from UI.

        Args:
            command: Feedback command dictionary with fields:
                - type: Command type ("submit_feedback", "confirm_interpretation")
                - Additional fields depending on type
        """
        command_type = command.get("type")

        logger.info("Received HITL command: %s", command_type)

        if command_type == "submit_feedback":
            self._handle_submit_feedback(command)
        elif command_type == "confirm_interpretation":
            self._handle_confirm_interpretation(command)
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

            self.feedback_manager.submit_feedback(
                feedback_type=feedback_type,
                content=command.get("content", ""),
                tool_id=command.get("tool_id", ""),
            )

            logger.info(
                "Feedback submitted: type=%s, tool_id=%s",
                feedback_type.value,
                command.get("tool_id"),
            )

        except Exception as e:
            logger.error("Failed to submit feedback: %s", e, exc_info=True)

    def _handle_confirm_interpretation(self, command: dict) -> None:
        """Handle interpretation confirmation command.

        Args:
            command: Command dict with approved (bool), tool_id
        """
        try:
            self.feedback_manager.confirm_interpretation(
                approved=command.get("approved", False),
                tool_id=command.get("tool_id", ""),
            )

            logger.info(
                "Interpretation confirmed: approved=%s, tool_id=%s",
                command.get("approved"),
                command.get("tool_id"),
            )

        except Exception as e:
            logger.error("Failed to confirm interpretation: %s", e, exc_info=True)
