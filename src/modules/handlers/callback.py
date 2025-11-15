#!/usr/bin/env python3
"""
Main callback handler for cyber security assessment operations.

This module contains the ReasoningHandler class which orchestrates all
callback operations, step tracking, and report generation.
"""

import logging
import os
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List

from strands.handlers import PrintingCallbackHandler

from ..handlers.events import get_emitter
from .base import HandlerState, StepLimitReached
from .utils import emit_event

logger = logging.getLogger("CyberAutoAgent.handlers")


class ReasoningHandler(PrintingCallbackHandler):
    """Callback handler for cyber security assessment operations with step tracking and reporting."""

    def __init__(
        self,
        max_steps=100,
        operation_id=None,
        target=None,
        output_base_dir=None,
        memory_config=None,
    ):  # pylint: disable=too-many-positional-arguments
        super().__init__()

        # Initialize emitter for event emission
        self.emitter = get_emitter(operation_id=operation_id)

        # Initialize handler state
        self.state = HandlerState(max_steps=max_steps)

        # Store configuration
        self.target = target
        self.output_base_dir = output_base_dir
        self.memory_config = memory_config

        # Initialize operation ID
        if operation_id:
            self.state.operation_id = operation_id
        else:
            self.state.operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.state.start_time = time.time()
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Emit structured banner event instead of direct print
        emit_event(
            "banner",
            {
                "title": "Cyber Security Assessment",
                "operation_id": self.state.operation_id,
                "timestamp": timestamp,
                "icon": "🔐",
            },
        )

    def __call__(self, **kwargs):
        """Process callback events with proper step limiting and clean formatting"""

        # Check for interrupt
        if "cyberautoagent" in sys.modules:
            cyberautoagent = sys.modules["cyberautoagent"]
            if hasattr(cyberautoagent, "interrupted") and cyberautoagent.interrupted:
                raise KeyboardInterrupt("User interrupted operation")

        # Check step limit
        if self.state.step_limit_reached:
            return

        # Process reasoning text (SDK native pattern)
        if "reasoningText" in kwargs:
            text = kwargs.get("reasoningText", "")
            self._handle_text_block(text)
            return

        # Process streaming text data
        if "data" in kwargs:
            text = kwargs.get("data", "")
            self._handle_text_block(text)
            return

        # Process message events
        if "message" in kwargs:
            message = kwargs["message"]
            if isinstance(message, dict):
                content = message.get("content", [])

                # Agent tracking handled through explicit handoff events only
                # Text-based detection removed - it's unreliable

                # Process text blocks
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        self._handle_text_block(text)

                # Process tool uses
                for block in content:
                    if isinstance(block, dict) and "toolUse" in block:
                        tool_use = block["toolUse"]
                        tool_id = tool_use.get("toolUseId", "")

                        # Process new tool uses with valid input
                        if tool_id not in self.state.shown_tools:
                            tool_input = tool_use.get("input", {})
                            if self._is_valid_tool_use(
                                tool_use.get("name", ""), tool_input
                            ):
                                # Step limit checked in show_tool_execution
                                self.state.shown_tools.add(tool_id)
                                self.state.tool_use_map[tool_id] = tool_use
                                try:
                                    # Emit tool start event
                                    tool_name = tool_use.get("name", "unknown")
                                    emit_event(
                                        "tool_start",
                                        tool_name,
                                        tool_name=tool_name,
                                        tool_id=tool_id,
                                        tool_input=tool_input,
                                        operation_id=self.state.operation_id,
                                    )

                                    emit_event(
                                        "tool_invocation_start",
                                        tool_name,
                                        tool_name=tool_name,
                                        operation_id=self.state.operation_id,
                                    )

                                    self.state.last_was_tool = True
                                    self.state.last_was_reasoning = False
                                except StepLimitReached:
                                    # Re-raise to stop execution
                                    raise

                # Process tool results
                for block in content:
                    if isinstance(block, dict) and "toolResult" in block:
                        tool_result = block["toolResult"]
                        tool_id = tool_result.get("toolUseId", "")

                        # Store result for later display
                        if tool_id in self.state.tool_use_map:
                            self.state.tool_results[tool_id] = tool_result

                            # Emit tool end event
                            tool_name = self.state.tool_use_map[tool_id].get("name", "")
                            success = tool_result.get("status", "success") == "success"

                            emit_event(
                                "tool_end",
                                tool_name,
                                tool_name=tool_name,
                                tool_id=tool_id,
                                success=success,
                                operation_id=self.state.operation_id,
                            )

                            emit_event(
                                "tool_invocation_end",
                                tool_name,
                                tool_name=tool_name,
                                success=success,
                                operation_id=self.state.operation_id,
                            )

                            # Track memory operations
                            if tool_name == "mem0_memory":
                                tool_input = self.state.tool_use_map[tool_id].get(
                                    "input", {}
                                )
                                if tool_input.get("action") == "store":
                                    self.state.memory_operations += 1

                # Suppress parent handler output
                self.state.suppress_parent_output = True
                return

        # Handle tool usage announcement from streaming
        if "current_tool_use" in kwargs:
            # Check if we've already hit the step limit
            if self.state.step_limit_reached:
                return

            tool = kwargs["current_tool_use"]
            tool_id = tool.get("toolUseId", "")

            # Validate tool input
            tool_input = tool.get("input", {})
            if self._is_valid_tool_use(tool.get("name", ""), tool_input):
                # Process unshown tools
                if tool_id not in self.state.shown_tools:
                    self.state.shown_tools.add(tool_id)
                    self.state.tool_use_map[tool_id] = tool
                    try:
                        # Emit tool start event
                        tool_name = tool.get("name", "unknown")
                        emit_event(
                            "tool_start",
                            tool_name,
                            tool_name=tool_name,
                            tool_id=tool_id,
                            tool_input=tool_input,
                            operation_id=self.state.operation_id,
                        )

                        emit_event(
                            "tool_invocation_start",
                            tool_name,
                            tool_name=tool_name,
                            operation_id=self.state.operation_id,
                        )

                        self.state.last_was_tool = True
                        self.state.last_was_reasoning = False
                    except StepLimitReached:
                        # Re-raise to stop execution
                        raise
            return

        # Handle tool result events
        if "toolResult" in kwargs:
            tool_result = kwargs["toolResult"]
            tool_id = tool_result.get("toolUseId", "")

            if tool_id in self.state.tool_use_map:
                # Emit tool end event
                tool_name = self.state.tool_use_map[tool_id].get("name", "")
                success = tool_result.get("status", "success") == "success"

                emit_event(
                    "tool_end",
                    tool_name,
                    tool_name=tool_name,
                    tool_id=tool_id,
                    success=success,
                    operation_id=self.state.operation_id,
                )

                emit_event(
                    "tool_invocation_end",
                    tool_name,
                    tool_name=tool_name,
                    success=success,
                    operation_id=self.state.operation_id,
                )
            return

        # Handle lifecycle events
        if any(
            k in kwargs
            for k in [
                "init_event_loop",
                "start_event_loop",
                "start",
                "complete",
                "force_stop",
            ]
        ):
            if not self.state.suppress_parent_output:
                super().__call__(**kwargs)
            return

    def _is_valid_tool_use(self, tool_name: str, tool_input: Any) -> bool:
        """Check if this tool use has valid input (not empty)"""
        if not tool_input:
            return False

        # Ensure tool_input is a dictionary
        if not isinstance(tool_input, dict):
            return False

        if tool_name == "shell":
            command = tool_input.get("command", "")
            # Process command format
            if isinstance(command, list):
                command = " ".join(command) if command else ""
            return bool(command.strip() if isinstance(command, str) else command)
        elif tool_name == "mem0_memory":
            action = tool_input.get("action", "")
            if action == "store":
                content = tool_input.get("content", "")
                return bool(content.strip() if isinstance(content, str) else content)
            elif action == "search":
                query = tool_input.get("query", "")
                return bool(query.strip() if isinstance(query, str) else query)
            elif action in ["list", "delete", "get", "update", "history"]:
                return True
            return False
        elif tool_name == "file_write":
            return bool(tool_input.get("path") and tool_input.get("content"))
        elif tool_name == "editor":
            return bool(tool_input.get("command") and tool_input.get("path"))
        elif tool_name == "load_tool":
            path = tool_input.get("path", "")
            return bool(path.strip() if isinstance(path, str) else path)
        else:
            # Default validation
            return bool(tool_input)

    def _handle_text_block(self, text: str) -> None:
        """Handle text blocks (reasoning/thinking) with proper formatting"""
        if text and not text.isspace():
            # Format output spacing
            if self.state.last_was_tool:
                self.state.last_was_tool = False

            # Normalize excessive leading spaces in agent output
            lines = text.split("\n")
            normalized_lines = []
            for line in lines:
                # If line has more than 10 leading spaces, it's likely misformatted
                stripped = line.lstrip()
                leading_spaces = len(line) - len(stripped)
                if leading_spaces > 10 and stripped:
                    # Preserve some indentation but not excessive amounts
                    normalized_lines.append(
                        "    " + stripped if leading_spaces > 20 else "  " + stripped
                    )
                else:
                    normalized_lines.append(line)

            normalized_text = "\n".join(normalized_lines)

            # Emit reasoning event instead of direct print
            emit_event(
                "reasoning",
                normalized_text,
                operation_id=self.state.operation_id,
                step=self.state.steps,
            )
            self.state.last_was_reasoning = True

    def generate_report(self, agent: Any, objective: str) -> None:
        """Generate comprehensive final report using LLM analysis.

        Args:
            agent: The agent instance
            objective: The operation objective
        """
        pass

    def generate_final_report(self, agent: Any, target: str, objective: str) -> None:
        """Generate comprehensive final report using LLM analysis.

        Args:
            agent: The agent instance
            target: The target system
            objective: The operation objective
        """
        if not target and self.target:
            target = self.target
        self.generate_report(agent, objective)

    def should_stop(self) -> bool:
        """Check if the handler should stop execution.

        Returns:
            True if step limit reached or stop tool was used
        """
        return self.state.step_limit_reached or self.state.stop_tool_used

    def has_reached_limit(self) -> bool:
        """Check if step limit has been reached.

        Returns:
            True if step limit has been reached
        """
        return self.state.step_limit_reached

    def get_summary(self) -> Dict[str, Any]:
        """Generate operation summary.

        Returns:
            Dictionary with operation summary statistics
        """
        return {
            "total_steps": self.state.steps,
            "tools_created": len(self.state.created_tools),
            "evidence_collected": self.state.memory_operations,
            "capability_expansion": self.state.created_tools,
            "memory_operations": self.state.memory_operations,
            "operation_id": self.state.operation_id,
        }

    def get_evidence_summary(self) -> List[str]:
        """Get a summary of key evidence collected.

        Returns:
            List of evidence summary strings
        """
        # Evidence retrieval not yet implemented
        return []

    def trigger_evaluation(self, agent_trace_id: str) -> None:
        """Trigger evaluation for the operation if enabled.

        Args:
            agent_trace_id: The trace ID for evaluation (usually the operation_id)
        """
        if self.state.evaluation_triggered:
            return
        self.state.evaluation_triggered = True

        # Import here to avoid circular imports
        from modules.evaluation.evaluation import CyberAgentEvaluator

        # Check if evaluation is enabled (application is source of truth when explicit)
        ui_mode = os.getenv("CYBER_UI_MODE", "").lower()
        if "ENABLE_AUTO_EVALUATION" in os.environ:
            enabled = os.environ["ENABLE_AUTO_EVALUATION"].lower() == "true"
        else:
            # In React UI, default to false unless explicitly enabled by the app
            enabled = (
                os.getenv(
                    "ENABLE_AUTO_EVALUATION", "false" if ui_mode == "react" else "true"
                ).lower()
                == "true"
            )
        if not enabled:
            logger.info("Evaluation disabled - skipping")
            return

        try:
            # Run evaluation in background thread
            def run_evaluation():
                try:
                    logger.info(
                        "Starting evaluation thread for operation: %s", agent_trace_id
                    )
                    evaluator = CyberAgentEvaluator()
                    import asyncio

                    # Evaluate all traces for this operation
                    logger.info("Running evaluation for trace ID: %s", agent_trace_id)
                    result = asyncio.run(
                        evaluator.evaluate_trace(trace_id=agent_trace_id)
                    )
                    logger.info("Evaluation completed. Results: %s", result)
                except Exception as e:
                    logger.error("Error running evaluation: %s", e, exc_info=True)

            self.state.evaluation_thread = threading.Thread(target=run_evaluation)
            # Don't use daemon thread - allow evaluation to complete
            self.state.evaluation_thread.daemon = False
            self.state.evaluation_thread.start()

            # Wait a moment to ensure evaluation starts
            # time module already imported at module level

            time.sleep(1)
            logger.info("Evaluation thread started successfully (non-daemon mode)")

        except Exception as e:
            logger.error("Error triggering evaluation: %s", e)

    def trigger_evaluation_on_completion(self) -> None:
        """Trigger evaluation on operation completion."""
        self.trigger_evaluation(self.state.operation_id)

    @property
    def operation_id(self) -> str:
        """Get the operation ID."""
        return self.state.operation_id

    @property
    def steps(self) -> int:
        """Get the current step count."""
        return self.state.steps

    @property
    def max_steps(self) -> int:
        """Get the maximum allowed steps."""
        return self.state.max_steps

    @property
    def memory_operations(self) -> int:
        """Get the memory operation count."""
        return self.state.memory_operations

    @property
    def tools_used(self) -> List[str]:
        """Get the list of tools used."""
        return self.state.tools_used

    @property
    def tool_effectiveness(self) -> Dict[str, Dict[str, int]]:
        """Get tool effectiveness metrics."""
        return self.state.tool_effectiveness

    @property
    def created_tools(self) -> List[str]:
        """Get the list of created tools."""
        return self.state.created_tools

    @property
    def stop_tool_used(self) -> bool:
        """Check if stop tool was used."""
        return self.state.stop_tool_used

    @property
    def report_generated(self) -> bool:
        """Check if report was generated."""
        return self.state.report_generated

    def wait_for_evaluation_completion(self, timeout: int = 300) -> bool:
        """
        Wait for evaluation to complete.

        Args:
            timeout: Maximum time to wait in seconds (default: 300)

        Returns:
            True if evaluation completed, False if timeout reached
        """
        if not self.state.evaluation_triggered:
            logger.debug("No evaluation was triggered, nothing to wait for")
            return True

        if not self.state.evaluation_thread:
            logger.debug("No evaluation thread found")
            return True

        logger.info("Waiting for evaluation to complete (timeout: %ds)...", timeout)
        self.state.evaluation_thread.join(timeout=timeout)

        if self.state.evaluation_thread.is_alive():
            logger.warning("Evaluation did not complete within %ds timeout", timeout)
            return False

        logger.info("Evaluation completed successfully")
        return True
