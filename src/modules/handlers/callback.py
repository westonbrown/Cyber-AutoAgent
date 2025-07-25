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
from typing import Dict, List, Any

from strands.handlers import PrintingCallbackHandler

from .base import HandlerState
from .utils import Colors
from .tools import show_tool_execution, show_tool_result, track_tool_effectiveness
from .reporting import generate_final_report

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

        # Display operation header
        print("\n%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))
        print("🔐 %s%sCyber Security Assessment%s" % (Colors.CYAN, Colors.BOLD, Colors.RESET))
        print("   Operation: %s%s%s" % (Colors.DIM, self.state.operation_id, Colors.RESET))
        print("   Started:   %s%s%s" % (Colors.DIM, timestamp, Colors.RESET))
        print("%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))
        print()

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

                # Detect current swarm agent if in swarm operation
                if self.state.in_swarm_operation:
                    self._detect_current_swarm_agent(kwargs)

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
                            if self._is_valid_tool_use(tool_use.get("name", ""), tool_input):
                                # Step limit checked in show_tool_execution
                                self.state.shown_tools.add(tool_id)
                                self.state.tool_use_map[tool_id] = tool_use
                                show_tool_execution(tool_use, self.state)
                                self.state.last_was_tool = True
                                self.state.last_was_reasoning = False

                # Process tool results
                for block in content:
                    if isinstance(block, dict) and "toolResult" in block:
                        tool_result = block["toolResult"]
                        tool_id = tool_result.get("toolUseId", "")

                        # Store result for later display
                        if tool_id in self.state.tool_use_map:
                            self.state.tool_results[tool_id] = tool_result
                            show_tool_result(tool_id, tool_result, self.state)

                            # Track tool effectiveness
                            track_tool_effectiveness(tool_id, tool_result, self.state)

                            # Track memory operations
                            tool_name = self.state.tool_use_map[tool_id].get("name", "")
                            if tool_name == "mem0_memory":
                                tool_input = self.state.tool_use_map[tool_id].get("input", {})
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
                    show_tool_execution(tool, self.state)
                    self.state.last_was_tool = True
                    self.state.last_was_reasoning = False
            return

        # Handle tool result events
        if "toolResult" in kwargs:
            tool_result = kwargs["toolResult"]
            tool_id = tool_result.get("toolUseId", "")

            if tool_id in self.state.tool_use_map:
                show_tool_result(tool_id, tool_result, self.state)
                track_tool_effectiveness(tool_id, tool_result, self.state)
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

    def _detect_current_swarm_agent(self, event_data: Dict[str, Any]) -> None:
        """Detect which agent is currently executing in a swarm operation.

        This method analyzes callback event data to identify the current agent
        in a swarm execution. It helps provide context in the UI by showing
        which agent is performing each action.

        Args:
            event_data: The callback event data dictionary
        """
        # Method 1: Check for agent context in the event data directly
        # The SDK might provide agent context in various places
        if "agent_name" in event_data:
            agent_name = event_data.get("agent_name", "")
            if agent_name in self.state.swarm_agents:
                self.state.current_swarm_agent = agent_name
                return

        # Check for node_id which might contain agent name
        if "node_id" in event_data:
            node_id = event_data.get("node_id", "")
            for agent_name in self.state.swarm_agents:
                if agent_name in node_id:
                    self.state.current_swarm_agent = agent_name
                    return

        # Method 2: Check message events for agent context
        if "message" in event_data:
            message = event_data["message"]
            if isinstance(message, dict):
                # Check metadata for agent info
                metadata = message.get("metadata", {})
                if isinstance(metadata, dict):
                    # Check for agent name in metadata
                    for key in ["agent", "agent_name", "node", "node_id", "current_agent"]:
                        if key in metadata:
                            agent_value = metadata[key]
                            if agent_value in self.state.swarm_agents:
                                self.state.current_swarm_agent = agent_value
                                return
                            # Check if any agent name is contained in the value
                            for agent_name in self.state.swarm_agents:
                                if agent_name in str(agent_value):
                                    self.state.current_swarm_agent = agent_name
                                    return

                # Check for role-based agent identification
                role = message.get("role", "")
                if role == "assistant":
                    # Look for agent context in the message content
                    content = message.get("content", [])
                    for block in content:
                        if isinstance(block, dict):
                            # Check for agent identification in text blocks
                            if block.get("type") == "text":
                                text = block.get("text", "")
                                # Look for explicit agent declarations
                                if text.strip():
                                    # Check for agent introductions or declarations
                                    for agent_name in self.state.swarm_agents:
                                        # Check various patterns for agent identification
                                        agent_patterns = [
                                            f"I am {agent_name}",
                                            f"As {agent_name}",
                                            f"This is {agent_name}",
                                            f"{agent_name} here",
                                            f"{agent_name} speaking",
                                            # Also check for formatted names
                                            f"I am {agent_name.replace('_', ' ')}",
                                            f"As {agent_name.replace('_', ' ')}",
                                            f"{agent_name.replace('_', ' ')} here",
                                        ]
                                        for pattern in agent_patterns:
                                            if pattern.lower() in text.lower():
                                                self.state.current_swarm_agent = agent_name
                                                return

                            # Check tool use for handoff patterns and complete_swarm_task
                            elif "toolUse" in block:
                                tool_use = block["toolUse"]
                                tool_name = tool_use.get("name", "")

                                if tool_name == "handoff_to_agent":
                                    # Extract the target agent from handoff
                                    tool_input = tool_use.get("input", {})
                                    if isinstance(tool_input, dict):
                                        next_agent = tool_input.get("agent_name", "")
                                        if next_agent in self.state.swarm_agents:
                                            # The next message will be from this agent
                                            self.state.current_swarm_agent = next_agent
                                            return

                                elif tool_name == "complete_swarm_task":
                                    # Swarm is completing, clear the swarm state
                                    self.state.in_swarm_operation = False
                                    self.state.current_swarm_agent = None
                                    return

        # Method 3: Track based on the execution flow
        # If we're in swarm and no agent detected, cycle through agents
        if self.state.in_swarm_operation and not self.state.current_swarm_agent:
            # If this is the first step after swarm starts, use first agent
            if self.state.swarm_step_count == 1 and self.state.swarm_agents:
                self.state.current_swarm_agent = self.state.swarm_agents[0]
            # Otherwise, we might have missed a handoff - use a simple rotation
            # This is a fallback and may not be accurate
            elif self.state.swarm_agents and self.state.swarm_step_count > 1:
                # Rotate through agents based on step count
                agent_index = (self.state.swarm_step_count - 1) % len(self.state.swarm_agents)
                self.state.current_swarm_agent = self.state.swarm_agents[agent_index]

    def _handle_text_block(self, text: str) -> None:
        """Handle text blocks (reasoning/thinking) with proper formatting"""
        if text and not text.isspace():
            # Format output spacing
            if self.state.last_was_tool:
                print()
                self.state.last_was_tool = False

            # Normalize excessive leading spaces in agent output
            lines = text.split('\n')
            normalized_lines = []
            for line in lines:
                # If line has more than 10 leading spaces, it's likely misformatted
                stripped = line.lstrip()
                leading_spaces = len(line) - len(stripped)
                if leading_spaces > 10 and stripped:
                    # Preserve some indentation but not excessive amounts
                    normalized_lines.append('    ' + stripped if leading_spaces > 20 else '  ' + stripped)
                else:
                    normalized_lines.append(line)
            
            normalized_text = '\n'.join(normalized_lines)
            print(normalized_text, end="", flush=True)
            self.state.last_was_reasoning = True

    def generate_report(self, agent: Any, objective: str) -> None:
        """Generate comprehensive final report using LLM analysis.

        Args:
            agent: The agent instance
            objective: The operation objective
        """
        generate_final_report(
            handler_state=self,  # Pass the full handler instead of just state
            agent=agent,
            target=self.target,
            objective=objective,
            memory_config=self.memory_config,
        )

    def generate_final_report(self, agent: Any, target: str, objective: str) -> None:
        """Generate comprehensive final report using LLM analysis (legacy method name).

        Args:
            agent: The agent instance
            target: The target system
            objective: The operation objective
        """
        # Use the stored target if not provided
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
        # This would typically return actual evidence from memory
        # For now, return empty list as placeholder
        return []

    def trigger_evaluation(self, agent_trace_id: str) -> None:
        """Trigger evaluation for the operation if enabled.

        Args:
            agent_trace_id: The trace ID for evaluation
        """
        if self.state.evaluation_triggered:
            return
        self.state.evaluation_triggered = True

        # Import here to avoid circular imports
        from ..evaluation.evaluation import CyberAgentEvaluator

        # Check if evaluation is enabled
        if not os.getenv("ENABLE_AUTO_EVALUATION", "false").lower() == "true":
            logger.info("Evaluation disabled - skipping")
            return

        try:
            # Run evaluation in background thread
            def run_evaluation():
                try:
                    evaluator = CyberAgentEvaluator()
                    import asyncio

                    asyncio.run(evaluator.evaluate_trace(trace_id=agent_trace_id))
                except Exception as e:
                    logger.error("Error running evaluation: %s", e)

            self.state.evaluation_thread = threading.Thread(target=run_evaluation)
            self.state.evaluation_thread.daemon = True
            self.state.evaluation_thread.start()

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
