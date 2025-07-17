#!/usr/bin/env python3

import asyncio
import io
import logging
import os
import sys
import threading
import time
from datetime import datetime
from typing import Dict, List

from langfuse import Langfuse
from strands.handlers import PrintingCallbackHandler

from .evaluation import CyberAgentEvaluator
from .memory_tools import get_memory_client
from .utils import Colors, get_data_path

logger = logging.getLogger("CyberAutoAgent.handlers")

# Constants for display formatting
CONTENT_PREVIEW_LENGTH = 150
METADATA_PREVIEW_LENGTH = 100
MAX_TOOL_CODE_LINES = 100
EVIDENCE_PREVIEW_LENGTH = 80
FALLBACK_EVIDENCE_PREVIEW_LENGTH = 200


class ReasoningHandler(PrintingCallbackHandler):
    """Callback handler for cyber security assessment operations with step tracking and reporting."""

    def __init__(self, max_steps=100, operation_id=None):
        super().__init__()
        self.steps = 0
        self.max_steps = max_steps
        self.memory_operations = 0
        self.created_tools = []
        self.tools_used = []
        self.tool_effectiveness = {}
        self.last_was_reasoning = False
        self.last_was_tool = False
        self.shown_tools = set()
        self.tool_use_map = {}
        self.tool_results = {}
        self.suppress_parent_output = False
        self.step_limit_reached = False
        self.stop_tool_used = False
        self.report_generated = False
        self.evaluation_triggered = False  # Prevent multiple evaluation triggers
        self.evaluation_thread = None  # Store evaluation thread reference

        # Initialize operation ID
        if operation_id:
            self.operation_id = operation_id
        else:
            self.operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_time = time.time()
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Display operation header
        print("\n%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))
        print(
            "🔐 %s%sCyber Security Assessment%s"
            % (Colors.CYAN, Colors.BOLD, Colors.RESET)
        )
        print("   Operation: %s%s%s" % (Colors.DIM, self.operation_id, Colors.RESET))
        print("   Started:   %s%s%s" % (Colors.DIM, timestamp, Colors.RESET))
        print("%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))
        print()

    def __call__(self, **kwargs):
        """Process callback events with proper step limiting and clean formatting"""

        # Check step limit
        if self.step_limit_reached:
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
                        if tool_id not in self.shown_tools:
                            tool_input = tool_use.get("input", {})
                            if self._is_valid_tool_use(
                                tool_use.get("name", ""), tool_input
                            ):
                                # Step limit checked in _show_tool_execution
                                self.shown_tools.add(tool_id)
                                self.tool_use_map[tool_id] = tool_use
                                self._show_tool_execution(tool_use)
                                self.last_was_tool = True
                                self.last_was_reasoning = False

                # Process tool results
                for block in content:
                    if isinstance(block, dict) and "toolResult" in block:
                        tool_result = block["toolResult"]
                        tool_id = tool_result.get("toolUseId", "")

                        # Store result for later display
                        if tool_id in self.tool_use_map:
                            self.tool_results[tool_id] = tool_result
                            self._show_tool_result(tool_id, tool_result)

                            # Track tool effectiveness
                            self._track_tool_effectiveness(tool_id, tool_result)

                            # Track memory operations
                            tool_name = self.tool_use_map[tool_id].get("name", "")
                            if tool_name == "mem0_memory":
                                tool_input = self.tool_use_map[tool_id].get("input", {})
                                if tool_input.get("action") == "store":
                                    self.memory_operations += 1

                # Suppress parent handler output
                self.suppress_parent_output = True
                return

        # Handle tool usage announcement from streaming
        if "current_tool_use" in kwargs:
            # Check if we've already hit the step limit
            if self.step_limit_reached:
                return

            tool = kwargs["current_tool_use"]
            tool_id = tool.get("toolUseId", "")

            # Validate tool input
            tool_input = tool.get("input", {})
            if self._is_valid_tool_use(tool.get("name", ""), tool_input):
                # Process unshown tools
                if tool_id not in self.shown_tools:
                    self.shown_tools.add(tool_id)
                    self.tool_use_map[tool_id] = tool
                    self._show_tool_execution(tool)
                    self.last_was_tool = True
                    self.last_was_reasoning = False
            return

        # Handle tool result events
        if "toolResult" in kwargs:
            tool_result = kwargs["toolResult"]
            tool_id = tool_result.get("toolUseId", "")

            if tool_id in self.tool_use_map:
                self._show_tool_result(tool_id, tool_result)
                self._track_tool_effectiveness(tool_id, tool_result)
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
            if not self.suppress_parent_output:
                super().__call__(**kwargs)
            return

    def _is_valid_tool_use(self, tool_name, tool_input):
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
            elif action == "retrieve":
                query = tool_input.get("query", "")
                return bool(query.strip() if isinstance(query, str) else query)
            elif action in ["list", "delete", "get", "history"]:
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

    def _handle_text_block(self, text):
        """Handle text blocks (reasoning/thinking) with proper formatting"""
        if text and not text.isspace():
            # Format output spacing
            if self.last_was_tool:
                print()
                self.last_was_tool = False

            print(text, end="", flush=True)
            self.last_was_reasoning = True

    def _show_tool_execution(self, tool_use):
        """Display tool execution with clean formatting based on working implementation"""
        # Enforce step limit
        if self.steps >= self.max_steps and not self.step_limit_reached:
            self.step_limit_reached = True
            print(
                "\n%sStep limit reached (%d). Assessment complete.%s"
                % (Colors.BLUE, self.max_steps, Colors.RESET)
            )
            # Terminate execution
            raise StopIteration("Step limit reached - clean termination")

        self.steps += 1

        tool_name = tool_use.get("name", "unknown")
        tool_input = tool_use.get("input", {})
        if not isinstance(tool_input, dict):
            tool_input = {}

        # Format output
        if self.last_was_reasoning:
            print()

        # Display step header
        print("%s" % ("─" * 80))
        print(
            "Step %d/%d: %s%s%s"
            % (self.steps, self.max_steps, Colors.CYAN, tool_name, Colors.RESET)
        )
        print("%s" % ("─" * 80))

        # Display tool execution details
        if tool_name == "shell":
            command = tool_input.get("command", "")
            parallel = tool_input.get("parallel", False)

            # Process command input
            if isinstance(command, list):
                mode = "parallel" if parallel else "sequential"
                # Remove duplicate commands
                seen = set()
                unique_commands = []
                for cmd in command:
                    cmd_str = (
                        cmd if isinstance(cmd, str) else cmd.get("command", str(cmd))
                    )
                    if cmd_str not in seen:
                        seen.add(cmd_str)
                        unique_commands.append((cmd, cmd_str))

                if len(unique_commands) < len(command):
                    print(
                        "↳ Executing %d unique commands (%s) [%d duplicates removed]:"
                        % (
                            len(unique_commands),
                            mode,
                            len(command) - len(unique_commands),
                        )
                    )
                else:
                    print(
                        "↳ Executing %d commands (%s):" % (len(unique_commands), mode)
                    )

                for i, (cmd, cmd_str) in enumerate(unique_commands):
                    print("  %d. %s%s%s" % (i + 1, Colors.GREEN, cmd_str, Colors.RESET))
                self.tools_used.append(
                    f"shell: {len(unique_commands)} commands ({mode})"
                )
            else:
                print("↳ Running: %s%s%s" % (Colors.GREEN, command, Colors.RESET))
                self.tools_used.append(f"shell: {command}")

        elif tool_name == "file_write":
            path = tool_input.get("path", "")
            content_preview = str(tool_input.get("content", ""))[:50]
            print("↳ Writing: %s%s%s" % (Colors.YELLOW, path, Colors.RESET))
            if content_preview:
                print(
                    "  Content: %s%s...%s" % (Colors.DIM, content_preview, Colors.RESET)
                )

            # Record created tools
            if path and path.startswith("tools/"):
                self.created_tools.append(path.replace("tools/", "").replace(".py", ""))

            self.tools_used.append(f"file_write: {path}")

        elif tool_name == "editor":
            command = tool_input.get("command", "")
            path = tool_input.get("path", "")
            file_text = tool_input.get("file_text", "")

            print("↳ Editor: %s%s%s" % (Colors.CYAN, command, Colors.RESET))
            print("  Path: %s%s%s" % (Colors.YELLOW, path, Colors.RESET))

            # Display file content
            if command == "create" and file_text:
                # Record tool files
                if path and path.startswith("tools/") and path.endswith(".py"):
                    self.created_tools.append(
                        path.replace("tools/", "").replace(".py", "")
                    )
                    print("\n%s" % ("─" * 70))
                    print("📄 %sMETA-TOOL CODE:%s" % (Colors.YELLOW, Colors.RESET))
                else:
                    print("\n%s" % ("─" * 70))
                    print("📄 %sFILE CONTENT:%s" % (Colors.CYAN, Colors.RESET))

                print("%s" % ("─" * 70))

                # Show file content
                lines = file_text.split("\n")
                for i, line in enumerate(lines[:MAX_TOOL_CODE_LINES]):
                    # Apply syntax highlighting
                    if path.endswith(".py"):
                        if line.strip().startswith("@tool"):
                            print("%s%s%s" % (Colors.GREEN, line, Colors.RESET))
                        elif line.strip().startswith("def "):
                            print("%s%s%s" % (Colors.CYAN, line, Colors.RESET))
                        elif line.strip().startswith("#"):
                            print("%s%s%s" % (Colors.DIM, line, Colors.RESET))
                        elif line.strip().startswith(("import ", "from ")):
                            print("%s%s%s" % (Colors.MAGENTA, line, Colors.RESET))
                        else:
                            print(line)
                    else:
                        # Plain text display
                        print(line)

                if len(lines) > MAX_TOOL_CODE_LINES:
                    print(
                        "%s... (%d more lines)%s"
                        % (Colors.DIM, len(lines) - MAX_TOOL_CODE_LINES, Colors.RESET)
                    )
                print("%s" % ("─" * 70))

            self.tools_used.append(f"editor: {command} {path}")

        elif tool_name == "load_tool":
            path = tool_input.get("path", "")
            print("↳ Loading: %s%s%s" % (Colors.GREEN, path, Colors.RESET))
            self.tools_used.append(f"load_tool: {path}")

        elif tool_name == "stop":
            reason = tool_input.get("reason", "No reason provided")
            print("↳ Stopping: %s%s%s" % (Colors.RED, reason, Colors.RESET))
            self.stop_tool_used = True  # Set the flag when stop tool is used
            self.tools_used.append(f"stop: {reason}")

        elif tool_name == "mem0_memory":
            action = tool_input.get("action", "")
            if action == "store":
                content = str(tool_input.get("content", ""))[:CONTENT_PREVIEW_LENGTH]
                metadata = tool_input.get("metadata", {})
                category = (
                    metadata.get("category", "general") if metadata else "general"
                )
                print(
                    "↳ Storing [%s%s%s]: %s%s%s%s"
                    % (
                        Colors.CYAN,
                        category,
                        Colors.RESET,
                        Colors.DIM,
                        content,
                        "..."
                        if len(str(tool_input.get("content", "")))
                        > CONTENT_PREVIEW_LENGTH
                        else "",
                        Colors.RESET,
                    )
                )
                if metadata:
                    print(
                        "  Metadata: %s%s%s%s"
                        % (
                            Colors.DIM,
                            str(metadata)[:METADATA_PREVIEW_LENGTH],
                            "..."
                            if len(str(metadata)) > METADATA_PREVIEW_LENGTH
                            else "",
                            Colors.RESET,
                        )
                    )
            elif action == "retrieve":
                query = tool_input.get("query", "")
                print('↳ Searching: %s"%s"%s' % (Colors.CYAN, query, Colors.RESET))
            elif action == "list":
                print("↳ Listing evidence")
            elif action == "delete":
                memory_id = tool_input.get("memory_id", "unknown")
                print(
                    "↳ Deleting memory: %s%s%s" % (Colors.RED, memory_id, Colors.RESET)
                )
            elif action == "get":
                memory_id = tool_input.get("memory_id", "unknown")
                print(
                    "↳ Getting memory: %s%s%s" % (Colors.CYAN, memory_id, Colors.RESET)
                )
            elif action == "history":
                memory_id = tool_input.get("memory_id", "unknown")
                print(
                    "↳ Getting history for: %s%s%s"
                    % (Colors.CYAN, memory_id, Colors.RESET)
                )

            self.tools_used.append(f"mem0_memory: {action}")

        else:
            # Process custom tools
            if tool_name == "swarm":
                # Display swarm configuration
                task = tool_input.get("task", "")
                swarm_size = tool_input.get("swarm_size", 1)
                pattern = tool_input.get("coordination_pattern", "collaborative")
                tools = tool_input.get("tools", [])
                model_provider = tool_input.get("model_provider", "default")

                print(
                    "↳ %sOrchestrating Swarm Intelligence%s"
                    % (Colors.BOLD, Colors.RESET)
                )

                # Parse task format
                task_parts = task.split(". ")
                if len(task_parts) >= 4 and any(
                    keyword in task
                    for keyword in ["Objective:", "Scope:", "Success:", "Context:"]
                ):
                    # Display structured task
                    for part in task_parts:
                        if part.strip():
                            if "Objective:" in part:
                                print(
                                    "  %sObjective:%s %s"
                                    % (
                                        Colors.CYAN,
                                        Colors.RESET,
                                        part.replace("Objective:", "").strip(),
                                    )
                                )
                            elif "Scope:" in part:
                                print(
                                    "  %sScope:%s %s"
                                    % (
                                        Colors.YELLOW,
                                        Colors.RESET,
                                        part.replace("Scope:", "").strip(),
                                    )
                                )
                            elif "Success:" in part:
                                print(
                                    "  %sSuccess:%s %s"
                                    % (
                                        Colors.GREEN,
                                        Colors.RESET,
                                        part.replace("Success:", "").strip(),
                                    )
                                )
                            elif "Context:" in part:
                                print(
                                    "  %sContext:%s %s"
                                    % (
                                        Colors.DIM,
                                        Colors.RESET,
                                        part.replace("Context:", "").strip(),
                                    )
                                )
                else:
                    # Display task description
                    print(
                        "  Task: %s%s%s"
                        % (
                            Colors.YELLOW,
                            task[:200] + "..." if len(task) > 200 else task,
                            Colors.RESET,
                        )
                    )

                print("  %sConfiguration:%s" % (Colors.BOLD, Colors.RESET))
                print(
                    "    Agents: %s%d%s" % (Colors.CYAN, int(swarm_size), Colors.RESET)
                )
                print("    Pattern: %s%s%s" % (Colors.MAGENTA, pattern, Colors.RESET))
                if tools:
                    print(
                        "    Tools: %s%s%s"
                        % (
                            Colors.GREEN,
                            ", ".join(tools) if isinstance(tools, list) else str(tools),
                            Colors.RESET,
                        )
                    )
                if model_provider and model_provider != "default":
                    print(
                        "    Model: %s%s%s"
                        % (Colors.BLUE, model_provider, Colors.RESET)
                    )

                self.tools_used.append(f"swarm: {int(swarm_size)} agents, {pattern}")
            elif tool_name == "http_request":
                # Display HTTP request details
                method = tool_input.get("method", "GET")
                url = tool_input.get("url", "")
                print(
                    "↳ HTTP Request: %s%s %s%s"
                    % (Colors.MAGENTA, method, url, Colors.RESET)
                )
                self.tools_used.append(f"http_request: {method} {url}")
            elif tool_name == "think":
                # Display thinking process
                thought = tool_input.get("thought", "")
                cycle_count = tool_input.get("cycle_count", 1)
                print(
                    "↳ Thinking (%s%d cycles%s):"
                    % (Colors.CYAN, cycle_count, Colors.RESET)
                )
                print(
                    "  Thought: %s%s%s"
                    % (
                        Colors.DIM,
                        thought[:500] + "..." if len(thought) > 500 else thought,
                        Colors.RESET,
                    )
                )
                self.tools_used.append(f"think: {cycle_count} cycles")
            elif tool_input:
                # Display tool parameters
                key_params = list(tool_input.keys())[:2]
                if key_params:
                    params_str = ", ".join(
                        f"{k}={str(tool_input[k])[:50]}{'...' if len(str(tool_input[k])) > 50 else ''}"
                        for k in key_params
                    )
                    print(
                        "↳ Parameters: %s%s%s" % (Colors.DIM, params_str, Colors.RESET)
                    )
                else:
                    print(
                        "↳ Executing: %s%s%s"
                        % (Colors.MAGENTA, tool_name, Colors.RESET)
                    )
                self.tools_used.append(f"{tool_name}: {list(tool_input.keys())}")
            else:
                print("↳ Executing: %s%s%s" % (Colors.MAGENTA, tool_name, Colors.RESET))
                self.tools_used.append(f"{tool_name}: no params")

        # Format output
        print()
        self.last_was_tool = True
        self.last_was_reasoning = False

    def _show_tool_result(self, tool_id, tool_result):
        """Display tool execution results if they contain meaningful output"""
        tool_use = self.tool_use_map.get(tool_id, {})
        tool_name = tool_use.get("name", "unknown")

        # Parse tool result
        result_content = tool_result.get("content", [])
        status = tool_result.get("status", "unknown")

        # Display tool output
        if tool_name == "shell" and result_content:
            for content_block in result_content:
                if isinstance(content_block, dict) and "text" in content_block:
                    output_text = content_block.get("text", "")
                    if output_text.strip():
                        # Remove summary lines
                        lines = output_text.strip().split("\n")
                        filtered_lines = []
                        skip_summary = False
                        for line in lines:
                            if "Execution Summary:" in line:
                                skip_summary = True
                                continue
                            if skip_summary and (
                                "Total commands:" in line
                                or "Successful:" in line
                                or "Failed:" in line
                            ):
                                continue
                            if skip_summary and line.strip() == "":
                                skip_summary = False
                                continue
                            if not skip_summary:
                                filtered_lines.append(line)

                        # Display filtered output
                        if filtered_lines and any(
                            line.strip() for line in filtered_lines
                        ):
                            for line in filtered_lines:
                                print(line)
                    break
        elif status == "error":
            # Display error messages
            for content_block in result_content:
                if isinstance(content_block, dict) and "text" in content_block:
                    error_text = content_block.get("text", "").strip()
                    if error_text and error_text != "Error:":
                        print("%sError: %s%s" % (Colors.RED, error_text, Colors.RESET))
        else:
            # Display tool results
            if result_content and tool_name not in ["shell"]:
                for content_block in result_content:
                    if isinstance(content_block, dict) and "text" in content_block:
                        output_text = content_block.get("text", "")
                        if output_text.strip():
                            # Display full swarm output
                            if tool_name == "swarm":
                                print(
                                    "%s[Swarm Output]%s" % (Colors.CYAN, Colors.RESET)
                                )
                                print(output_text)
                            # Display truncated output
                            else:
                                # Truncate long outputs
                                max_lines = 50
                                lines = output_text.strip().split("\n")
                                if len(lines) > max_lines:
                                    for line in lines[:max_lines]:
                                        print(line)
                                    print(
                                        "%s... (%d more lines)%s"
                                        % (
                                            Colors.DIM,
                                            len(lines) - max_lines,
                                            Colors.RESET,
                                        )
                                    )
                                else:
                                    print(output_text)
                            break

        # Display separator
        print("%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))

    def _track_tool_effectiveness(self, tool_id, tool_result):
        """Track tool effectiveness for analysis"""
        tool_use = self.tool_use_map.get(tool_id, {})
        tool_name = tool_use.get("name", "unknown")
        status = tool_result.get("status", "unknown")

        if tool_name not in self.tool_effectiveness:
            self.tool_effectiveness[tool_name] = {"success": 0, "error": 0}

        if status == "success":
            self.tool_effectiveness[tool_name]["success"] += 1
        else:
            self.tool_effectiveness[tool_name]["error"] += 1

    def has_reached_limit(self):
        """Check if step limit reached"""
        return self.steps >= self.max_steps

    def should_stop(self):
        """Check if agent should stop (step limit or stop tool used)"""
        return self.has_reached_limit() or self.stop_tool_used

    def get_remaining_steps(self):
        """Get remaining steps for budget management"""
        return max(0, self.max_steps - self.steps)

    def get_budget_urgency_level(self):
        """Get current budget urgency level for decision making"""
        remaining = self.get_remaining_steps()
        if remaining > 20:
            return "ABUNDANT"
        elif remaining > 10:
            return "CONSTRAINED"
        elif remaining > 5:
            return "CRITICAL"
        else:
            return "EMERGENCY"

    def get_summary(self):
        """Generate operation summary"""
        return {
            "total_steps": self.steps,
            "tools_created": len(self.created_tools),
            "evidence_collected": self.memory_operations,
            "capability_expansion": self.created_tools,
            "memory_operations": self.memory_operations,
            "operation_id": self.operation_id,
        }

    def get_evidence_summary(self):
        """Get evidence summary from mem0_memory tool"""
        # Legacy method - evidence retrieved via mem0_memory tool
        return []

    def generate_final_report(self, agent, target: str, objective: str) -> None:
        """
        Generate comprehensive final assessment report using LLM analysis.

        Args:
            agent: The agent instance for generating the report
            target: Target system being assessed
            objective: Assessment objective/goals
        """
        # Ensure single report generation
        if self.report_generated:
            return
        self.report_generated = True

        # Send operation metadata to Langfuse
        self._send_operation_metadata()

        # Collect evidence from memory first
        evidence = self._retrieve_evidence()

        # Only generate report if evidence was collected
        if not evidence:
            print("\n%s%s%s" % (Colors.DIM, "═" * 80, Colors.RESET))
            print(
                "%s%sNo evidence collected - skipping final report generation%s"
                % (Colors.YELLOW, Colors.BOLD, Colors.RESET)
            )
            print("%s%s%s" % (Colors.DIM, "═" * 80, Colors.RESET))
            return

        print("\n%s%s%s" % (Colors.DIM, "═" * 80, Colors.RESET))
        print(
            "%s%sGenerating Final Assessment Report%s"
            % (Colors.CYAN, Colors.BOLD, Colors.RESET)
        )
        print("%s%s%s" % (Colors.DIM, "═" * 80, Colors.RESET))

        # Generate AI assessment report
        try:
            report_content = self._generate_llm_report(
                agent, target, objective, evidence
            )
            self._display_final_report(report_content)
            # Save report
            self._save_report_to_file(report_content, target, objective)
        except Exception as e:
            print(
                "%sError generating final report: %s%s"
                % (Colors.RED, str(e), Colors.RESET)
            )
            # If LLM report generation fails, don't save any report

        # Note: Evaluation is triggered from cyberautoagent.py, not here to avoid duplicates

    def _retrieve_evidence(self) -> List[Dict]:
        """Retrieve all collected evidence from memory system."""
        evidence = []

        # Initialize memory client
        memory_client = get_memory_client()
        if memory_client is None:
            logger.error("Memory client is not initialized!")
            print(
                "%sError: Memory client not initialized. Cannot retrieve evidence.%s"
                % (Colors.RED, Colors.RESET)
            )
            return evidence

        # Set agent user ID
        agent_user_id = "cyber_agent"

        try:
            # Retrieve memories
            logger.info(
                "Attempting to retrieve memories for user_id: %s", agent_user_id
            )

            # Fetch memory list
            memories_response = memory_client.list_memories(user_id=agent_user_id)

            # Process response
            logger.debug("Memory response type: %s", type(memories_response))
            logger.debug("Memory response: %s", memories_response)

            # Parse memory response format
            if isinstance(memories_response, dict):
                # Extract from dictionary response
                raw_memories = memories_response.get(
                    "memories", memories_response.get("results", [])
                )
                logger.debug(
                    "Extracted %d memories from dict response", len(raw_memories)
                )
            elif isinstance(memories_response, list):
                # Process list response
                raw_memories = memories_response
                logger.debug("Got %d memories as list", len(raw_memories))
            else:
                # Handle unexpected format
                raw_memories = []
                logger.warning(
                    "Unexpected memory response format: %s", type(memories_response)
                )

            logger.info("Found %d total memories", len(raw_memories))

            # Process findings
            for mem in raw_memories:
                # Extract metadata
                metadata = mem.get("metadata", {})

                # Process memory entry
                logger.debug("Processing memory: %s", mem)

                if metadata and metadata.get("category") == "finding":
                    evidence.append(
                        {
                            "category": metadata.get("category"),
                            "content": mem.get("memory", "N/A"),
                            "id": mem.get("id", "N/A"),
                        }
                    )
                    logger.info(
                        "Added finding to evidence: %s...",
                        mem.get("memory", "N/A")[:50],
                    )
                # Include uncategorized memories
                elif "memory" in mem and "category" not in metadata:
                    # Include concise memories
                    if len(mem.get("memory", "").split()) < 50:
                        evidence.append(
                            {
                                "category": "general",
                                "content": mem.get("memory", "N/A"),
                                "id": mem.get("id", "N/A"),
                            }
                        )
                        logger.info(
                            "Added general memory to evidence: %s...",
                            mem.get("memory", "N/A")[:50],
                        )

            # Only show retrieval message if evidence was found
            if evidence:
                print(
                    "%sRetrieved %d items from memory for final report.%s"
                    % (Colors.DIM, len(evidence), Colors.RESET)
                )

        except Exception as e:
            logger.error(
                "Error retrieving evidence from mem0_memory: %s", str(e), exc_info=True
            )
            print(
                "%sWarning: Failed to retrieve evidence from memory (user_id: %s). Report may be incomplete.%s"
                % (Colors.YELLOW, agent_user_id, Colors.RESET)
            )
            print("%sError details: %s%s" % (Colors.DIM, str(e), Colors.RESET))
            evidence = []

        return evidence

    def _generate_llm_report(
        self, agent, target: str, objective: str, evidence: List[Dict]
    ) -> str:
        """Generate assessment report using LLM analysis."""
        # Prepare evidence for analysis
        evidence_text = [
            f"[{item['category'].upper()}] {item['content']}" for item in evidence
        ]

        report_prompt = f"""Based on the evidence collected during this cyber security assessment, generate a comprehensive final report.

TARGET: {target}
OBJECTIVE: {objective}
EVIDENCE COLLECTED ({len(evidence)} items):

{chr(10).join(evidence_text)}

Please provide:
1. Executive Summary of findings
2. Critical vulnerabilities discovered
3. Attack vectors identified
4. Risk assessment
5. Recommendations for remediation
6. Overall security posture evaluation

Format this as a professional penetration testing report."""

        print(
            "%sAnalyzing collected evidence and generating insights...%s"
            % (Colors.DIM, Colors.RESET)
        )

        if not (agent and callable(agent)):
            raise ValueError("Agent not available for report generation")

        # Suppress output during generation
        original_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            # Generate report
            raw_report = agent(report_prompt)
            return self._clean_duplicate_content(str(raw_report))
        finally:
            # Restore output
            sys.stdout = original_stdout

    def _clean_duplicate_content(self, report_content: str) -> str:
        """Remove duplicate sections from LLM-generated content."""
        report_lines = report_content.split("\n")
        clean_lines = []
        seen_section_markers = set()

        i = 0
        while i < len(report_lines):
            line = report_lines[i]

            # Detect duplicate sections
            if (
                line.strip().startswith("# Penetration Testing Report")
                or line.strip().startswith("**Target:")
                or (line.strip().startswith("# ") and "Report" in line)
            ):
                # Skip duplicate markers
                if line.strip() in seen_section_markers:
                    break

                # Check for existing content
                if (
                    line.strip().startswith("# Penetration Testing Report")
                    and len(clean_lines) > 10
                ):
                    break

                seen_section_markers.add(line.strip())

            # Detect duplicate summaries
            elif line.strip().startswith("## 1. Executive Summary") and any(
                "## 1. Executive Summary" in existing_line
                for existing_line in clean_lines
            ):
                # Skip duplicate content
                break

            clean_lines.append(line)
            i += 1

        return "\n".join(clean_lines)

    def _display_final_report(self, report_content: str) -> None:
        """Display the final assessment report."""
        print("\n%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))
        print(
            "📋 %s%sFINAL ASSESSMENT REPORT%s"
            % (Colors.GREEN, Colors.BOLD, Colors.RESET)
        )
        print("%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))
        print("\n%s" % report_content)
        print("\n%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))

    def _save_report_to_file(
        self, report_content: str, target: str, objective: str
    ) -> None:
        """Save report to file in evidence directory."""
        try:
            # Create evidence directory
            evidence_dir = os.path.join(
                get_data_path("evidence"), f"evidence_{self.operation_id}"
            )
            os.makedirs(evidence_dir, exist_ok=True)

            # Write report file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"final_report_{timestamp}.md"
            report_path = os.path.join(evidence_dir, report_filename)

            with open(report_path, "w", encoding="utf-8") as f:
                f.write("# Cybersecurity Assessment Report\n\n")
                f.write(f"**Operation ID:** {self.operation_id}\n")
                f.write(f"**Target:** {target}\n")
                f.write(f"**Objective:** {objective}\n")
                f.write(
                    f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                )
                f.write("---\n\n")
                f.write(report_content)

            print(
                "\n%sReport saved to: %s%s" % (Colors.GREEN, report_path, Colors.RESET)
            )

        except Exception as e:
            print(
                "%sWarning: Could not save report to file: %s%s"
                % (Colors.YELLOW, str(e), Colors.RESET)
            )

    def _trigger_evaluation_if_enabled(self):
        """Trigger automatic evaluation if enabled via environment variable."""
        # Prevent multiple evaluation triggers
        if self.evaluation_triggered:
            logger.debug("Evaluation already triggered, skipping duplicate trigger")
            return

        eval_enabled = os.getenv("ENABLE_AUTO_EVALUATION", "false").lower()
        logger.debug(f"Evaluation check: ENABLE_AUTO_EVALUATION='{eval_enabled}'")
        if eval_enabled == "true":
            self.evaluation_triggered = True  # Mark as triggered
            try:
                # Configure Langfuse connection
                langfuse = Langfuse(
                    public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "cyber-public"),
                    secret_key=os.getenv("LANGFUSE_SECRET_KEY", "cyber-secret"),
                    host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
                )

                # Execute batch evaluation
                def run_batch_evaluation():
                    try:
                        # Create evaluator instance
                        evaluator = CyberAgentEvaluator()

                        # Allow trace propagation delay
                        logger.info(
                            f"Starting batch evaluation for operation {self.operation_id}"
                        )
                        print(
                            f"\n{Colors.DIM}Waiting 30 seconds for trace propagation...{Colors.RESET}"
                        )
                        time.sleep(30)

                        # Retrieve operation traces
                        logger.info(
                            f"Fetching traces for operation {self.operation_id}"
                        )
                        print(
                            f"\n{Colors.CYAN}Fetching traces for evaluation...{Colors.RESET}"
                        )

                        # Fetch traces from Langfuse API
                        logger.info("Attempting to fetch traces from Langfuse API")

                        try:
                            # First, try to get all recent traces without filtering
                            all_traces = langfuse.api.trace.list(limit=20)
                            logger.info(
                                f"API returned {len(all_traces.data) if hasattr(all_traces, 'data') else 0} traces"
                            )

                            # Log trace structure for debugging
                            if hasattr(all_traces, "data") and all_traces.data:
                                first_trace = all_traces.data[0]
                                logger.debug(
                                    f"First trace attributes: {dir(first_trace)}"
                                )
                                if hasattr(first_trace, "session_id"):
                                    logger.debug(
                                        f"First trace session_id: {first_trace.session_id}"
                                    )
                                if hasattr(first_trace, "metadata"):
                                    logger.debug(
                                        f"First trace metadata: {first_trace.metadata}"
                                    )
                                if hasattr(first_trace, "tags"):
                                    logger.debug(
                                        f"First trace tags: {first_trace.tags}"
                                    )

                            # Try to filter by session_id if available
                            filtered_traces = []
                            for t in all_traces.data:
                                # Check various possible locations for session_id
                                if (
                                    hasattr(t, "session_id")
                                    and t.session_id == self.operation_id
                                ):
                                    filtered_traces.append(t)
                                elif hasattr(t, "metadata") and isinstance(
                                    t.metadata, dict
                                ):
                                    # Check in metadata
                                    if (
                                        t.metadata.get("session_id")
                                        == self.operation_id
                                    ):
                                        filtered_traces.append(t)
                                    elif (
                                        t.metadata.get("attributes", {}).get(
                                            "session.id"
                                        )
                                        == self.operation_id
                                    ):
                                        filtered_traces.append(t)

                            if filtered_traces:
                                logger.info(
                                    f"Found {len(filtered_traces)} traces matching operation {self.operation_id}"
                                )
                                traces = type(
                                    "obj", (object,), {"data": filtered_traces}
                                )
                            else:
                                logger.info(
                                    f"No traces found with session_id {self.operation_id}, using all recent traces"
                                )
                                traces = all_traces

                        except Exception as api_error:
                            logger.error(
                                f"Failed to fetch traces from Langfuse API: {str(api_error)}",
                                exc_info=True,
                            )
                            print(
                                f"\n{Colors.RED}❌ Failed to fetch traces: {str(api_error)}{Colors.RESET}"
                            )
                            return

                        if not traces.data:
                            logger.warning(
                                f"No traces found for operation {self.operation_id}"
                            )
                            print(
                                f"\n{Colors.YELLOW}⚠️ No traces found for operation {self.operation_id} - evaluation skipped{Colors.RESET}"
                            )
                            return

                        logger.info(f"Found {len(traces.data)} traces to evaluate")
                        print(
                            f"\n{Colors.GREEN}✓ Found {len(traces.data)} trace(s) to evaluate{Colors.RESET}"
                        )

                        successful_evals = 0
                        failed_evals = 0

                        # Process traces
                        for i, trace in enumerate(traces.data, 1):
                            trace_id = trace.id
                            logger.info(
                                f"Evaluating trace {i}/{len(traces.data)}: {trace_id}"
                            )
                            print(
                                f"\n{Colors.CYAN}Evaluating trace {i}/{len(traces.data)}: {trace_id[:8]}...{Colors.RESET}"
                            )

                            try:
                                # Execute evaluation - handle asyncio properly in thread
                                try:
                                    # Try to get existing event loop
                                    loop = asyncio.get_event_loop()
                                    if loop.is_running():
                                        # If loop is already running, create a new task
                                        future = asyncio.ensure_future(
                                            evaluator.evaluate_trace(trace_id)
                                        )
                                        scores = loop.run_until_complete(future)
                                    else:
                                        # If no loop is running, use asyncio.run
                                        scores = asyncio.run(
                                            evaluator.evaluate_trace(trace_id)
                                        )
                                except RuntimeError as e:
                                    logger.debug(f"RuntimeError in asyncio: {str(e)}")
                                    # No event loop in thread, create a new one
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    try:
                                        scores = loop.run_until_complete(
                                            evaluator.evaluate_trace(trace_id)
                                        )
                                    finally:
                                        loop.close()
                                except Exception as async_error:
                                    logger.error(
                                        f"Asyncio execution failed: {str(async_error)}",
                                        exc_info=True,
                                    )
                                    raise

                                if scores:
                                    successful_evals += 1
                                    logger.info(
                                        f"Successfully evaluated trace {trace_id}: {scores}"
                                    )
                                    print(
                                        f"{Colors.GREEN}✅ Evaluation completed: {scores}{Colors.RESET}"
                                    )
                                else:
                                    failed_evals += 1
                                    logger.warning(
                                        f"No scores returned for trace {trace_id}"
                                    )
                                    print(
                                        f"{Colors.YELLOW}⚠️ No scores returned{Colors.RESET}"
                                    )

                            except Exception as eval_error:
                                failed_evals += 1
                                logger.error(
                                    f"Failed to evaluate trace {trace_id}: {str(eval_error)}",
                                    exc_info=True,
                                )
                                print(
                                    f"{Colors.RED}❌ Evaluation failed: {str(eval_error)}{Colors.RESET}"
                                )

                        # Summary
                        logger.info(
                            f"Batch evaluation complete: {successful_evals} successful, {failed_evals} failed"
                        )
                        print(f"\n{Colors.CYAN}{'=' * 60}{Colors.RESET}")
                        print(
                            f"{Colors.BOLD}Evaluation Summary for {self.operation_id}:{Colors.RESET}"
                        )
                        print(f"   ✅ Successful evaluations: {successful_evals}")
                        print(f"   ❌ Failed evaluations: {failed_evals}")
                        print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")

                    except Exception as batch_error:
                        logger.error(
                            f"Batch evaluation crashed: {str(batch_error)}",
                            exc_info=True,
                        )
                        print(
                            f"\n{Colors.RED}❌ Batch evaluation crashed: {str(batch_error)}{Colors.RESET}"
                        )
                    finally:
                        logger.info(
                            f"Batch evaluation thread completed for operation {self.operation_id}"
                        )

                # Launch background evaluation
                eval_thread = threading.Thread(
                    target=run_batch_evaluation,
                    daemon=False,
                    name=f"eval-{self.operation_id}",
                )
                eval_thread.start()

                print(
                    f"\n{Colors.CYAN}Batch evaluation scheduled for operation {self.operation_id} (will run in 30 seconds){Colors.RESET}"
                )
                logger.debug(
                    f"Background evaluation thread started: {eval_thread.name}"
                )

                # Store thread reference for later joining
                self.evaluation_thread = eval_thread

            except Exception as e:
                logger.warning(f"Failed to trigger automatic evaluation: {str(e)}")
        else:
            logger.debug(
                "Automatic evaluation disabled (set ENABLE_AUTO_EVALUATION=true to enable)"
            )

    def _send_operation_metadata(self):
        """Send operation completion metadata to Langfuse."""
        try:
            # Initialize Langfuse client
            langfuse = Langfuse(
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "cyber-public"),
                secret_key=os.getenv("LANGFUSE_SECRET_KEY", "cyber-secret"),
                host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
            )

            # Calculate operation metrics
            operation_duration = time.time() - self.start_time

            # Tool usage summary
            tool_usage_summary = {}
            for tool_entry in self.tools_used:
                tool_name = tool_entry.split(":")[0]
                tool_usage_summary[tool_name] = tool_usage_summary.get(tool_name, 0) + 1

            # Log operation metadata
            operation_metadata = {
                "operation_id": self.operation_id,
                "duration_seconds": round(operation_duration, 2),
                "total_steps": self.steps,
                "max_steps": self.max_steps,
                "step_utilization": round((self.steps / self.max_steps) * 100, 1),
                "completion_reason": "step_limit"
                if self.step_limit_reached
                else "objective_achieved"
                if self.stop_tool_used
                else "completed",
                "tools_created": len(self.created_tools),
                "created_tools_list": self.created_tools,
                "memory_operations": self.memory_operations,
                "tool_usage_summary": tool_usage_summary,
                "tool_usage_count": sum(tool_usage_summary.values()),
                "unique_tools_used": len(tool_usage_summary),
                "tool_effectiveness": self.tool_effectiveness,
                "avg_seconds_per_step": round(operation_duration / self.steps, 2)
                if self.steps > 0
                else 0,
            }
            logger.debug(f"Operation metadata: {operation_metadata}")

            logger.debug(f"Operation {self.operation_id} metadata logged successfully")

        except Exception as e:
            logger.warning(f"Failed to send operation metadata to Langfuse: {str(e)}")

    def trigger_evaluation_on_completion(self):
        """Trigger evaluation when agent completes (success or failure)."""
        logger.debug("trigger_evaluation_on_completion called")
        self._trigger_evaluation_if_enabled()

    def wait_for_evaluation_completion(self, timeout=300):
        """Wait for evaluation thread to complete if it exists."""
        if (
            hasattr(self, "evaluation_thread")
            and self.evaluation_thread
            and self.evaluation_thread.is_alive()
        ):
            logger.info(f"Waiting for evaluation to complete (timeout: {timeout}s)...")
            self.evaluation_thread.join(timeout=timeout)
            if self.evaluation_thread.is_alive():
                logger.warning("Evaluation thread did not complete within timeout")
            else:
                logger.info("Evaluation completed successfully")
