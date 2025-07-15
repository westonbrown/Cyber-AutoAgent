#!/usr/bin/env python3

import sys
import io
import os
import logging
from datetime import datetime
from typing import List, Dict
from strands.handlers import PrintingCallbackHandler
from strands import Agent
from .utils import Colors, get_data_path
from .memory_tools import get_memory_client, mem0_memory

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
        self.shown_tools = set()  # Track shown tools to avoid duplicates
        self.tool_use_map = {}  # Map tool IDs to tool info
        self.tool_results = {}  # Store tool results for output display
        self.suppress_parent_output = False  # Flag to control parent handler
        self.step_limit_reached = False  # Flag to track if we've hit the limit
        self.stop_tool_used = False  # Flag to track if stop tool was used
        self.report_generated = False  # Flag to prevent duplicate reports

        # Use provided operation ID or generate one
        if operation_id:
            self.operation_id = operation_id
        else:
            self.operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Clean header with full-width break lines
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
        
        # Immediately return if step limit has been reached
        if self.step_limit_reached:
            return

        # Handle streaming text data (reasoning/thinking)
        if "data" in kwargs:
            text = kwargs.get("data", "")
            self._handle_text_block(text)
            return

        # Handle message events (tool uses and results)
        if "message" in kwargs:
            message = kwargs["message"]
            if isinstance(message, dict):
                content = message.get("content", [])

                # First, handle any text blocks (reasoning)
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        self._handle_text_block(text)

                # Process tool uses
                for block in content:
                    if isinstance(block, dict) and "toolUse" in block:
                        tool_use = block["toolUse"]
                        tool_id = tool_use.get("toolUseId", "")

                        # Only process if not already shown and has valid input
                        if tool_id not in self.shown_tools:
                            tool_input = tool_use.get("input", {})
                            if self._is_valid_tool_use(
                                tool_use.get("name", ""), tool_input
                            ):
                                # Step limit is now checked in _show_tool_execution - no need for pre-check
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

                # Prevent duplicate output from parent handler
                self.suppress_parent_output = True
                return

        # Handle tool usage announcement from streaming
        if "current_tool_use" in kwargs:
            # Check if we've already hit the step limit
            if self.step_limit_reached:
                return
                
            tool = kwargs["current_tool_use"]
            tool_id = tool.get("toolUseId", "")

            # Check if this tool has valid input
            tool_input = tool.get("input", {})
            if self._is_valid_tool_use(tool.get("name", ""), tool_input):
                # Only show if not already shown
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

        # For lifecycle events, pass to parent but respect suppression flag
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
            # Handle case where command might be a list
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
                return True  # These have other validations
            return False
        elif tool_name == "file_write":
            return bool(tool_input.get("path") and tool_input.get("content"))
        elif tool_name == "editor":
            return bool(tool_input.get("command") and tool_input.get("path"))
        elif tool_name == "load_tool":
            path = tool_input.get("path", "")
            return bool(path.strip() if isinstance(path, str) else path)
        else:
            # For other tools, assume valid if there's any input
            return bool(tool_input)

    def _handle_text_block(self, text):
        """Handle text blocks (reasoning/thinking) with proper formatting"""
        if text and not text.isspace():
            # Add spacing before reasoning if last was a tool
            if self.last_was_tool:
                print()  # Add spacing
                self.last_was_tool = False

            print(text, end="", flush=True)
            self.last_was_reasoning = True

    def _show_tool_execution(self, tool_use):
        """Display tool execution with clean formatting based on working implementation"""
        # Check step limit BEFORE incrementing to prevent execution beyond limit
        if self.steps >= self.max_steps and not self.step_limit_reached:
            self.step_limit_reached = True
            print(
                "\n%sStep limit reached (%d). Assessment complete.%s"
                % (Colors.BLUE, self.max_steps, Colors.RESET)
            )
            # Stop all further processing by raising StopIteration
            raise StopIteration("Step limit reached - clean termination")
            
        self.steps += 1

        tool_name = tool_use.get("name", "unknown")
        tool_input = tool_use.get("input", {})
        if not isinstance(tool_input, dict):
            tool_input = {}

        # Add reasoning separator if needed
        if self.last_was_reasoning:
            print()  # Add line after reasoning

        # Print step header with exact format from working version
        print("%s" % ("─" * 80))
        print(
            "Step %d/%d: %s%s%s"
            % (self.steps, self.max_steps, Colors.CYAN, tool_name, Colors.RESET)
        )
        print("%s" % ("─" * 80))

        # Show detailed tool information
        if tool_name == "shell":
            command = tool_input.get("command", "")
            parallel = tool_input.get("parallel", False)
            
            # Handle different command formats
            if isinstance(command, list):
                mode = "parallel" if parallel else "sequential"
                # Deduplicate commands while preserving order
                seen = set()
                unique_commands = []
                for cmd in command:
                    cmd_str = cmd if isinstance(cmd, str) else cmd.get("command", str(cmd))
                    if cmd_str not in seen:
                        seen.add(cmd_str)
                        unique_commands.append((cmd, cmd_str))
                
                if len(unique_commands) < len(command):
                    print("↳ Executing %d unique commands (%s) [%d duplicates removed]:" % 
                          (len(unique_commands), mode, len(command) - len(unique_commands)))
                else:
                    print("↳ Executing %d commands (%s):" % (len(unique_commands), mode))
                
                for i, (cmd, cmd_str) in enumerate(unique_commands):
                    print("  %d. %s%s%s" % (i+1, Colors.GREEN, cmd_str, Colors.RESET))
                self.tools_used.append(f"shell: {len(unique_commands)} commands ({mode})")
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

            # Track tool creation
            if path and path.startswith("tools/"):
                self.created_tools.append(path.replace("tools/", "").replace(".py", ""))

            self.tools_used.append(f"file_write: {path}")

        elif tool_name == "editor":
            command = tool_input.get("command", "")
            path = tool_input.get("path", "")
            file_text = tool_input.get("file_text", "")

            print("↳ Editor: %s%s%s" % (Colors.CYAN, command, Colors.RESET))
            print("  Path: %s%s%s" % (Colors.YELLOW, path, Colors.RESET))

            # Show content for any file creation
            if command == "create" and file_text:
                # Track tools specifically
                if path and path.startswith("tools/") and path.endswith(".py"):
                    self.created_tools.append(path.replace("tools/", "").replace(".py", ""))
                    print("\n%s" % ("─" * 70))
                    print("📄 %sMETA-TOOL CODE:%s" % (Colors.YELLOW, Colors.RESET))
                else:
                    print("\n%s" % ("─" * 70))
                    print("📄 %sFILE CONTENT:%s" % (Colors.CYAN, Colors.RESET))
                
                print("%s" % ("─" * 70))
                
                # Display the file content with syntax highlighting
                lines = file_text.split("\n")
                for i, line in enumerate(lines[:MAX_TOOL_CODE_LINES]):
                    # Python syntax highlighting
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
                        # No highlighting for non-Python files
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
                category = metadata.get("category", "general") if metadata else "general"
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
                print("↳ Deleting memory: %s%s%s" % (Colors.RED, memory_id, Colors.RESET))
            elif action == "get":
                memory_id = tool_input.get("memory_id", "unknown")
                print("↳ Getting memory: %s%s%s" % (Colors.CYAN, memory_id, Colors.RESET))
            elif action == "history":
                memory_id = tool_input.get("memory_id", "unknown")
                print("↳ Getting history for: %s%s%s" % (Colors.CYAN, memory_id, Colors.RESET))

            self.tools_used.append(f"mem0_memory: {action}")

        else:
            # Custom tool
            if tool_name == "swarm":
                # Special handling for swarm tool - show full parameters
                task = tool_input.get("task", "")
                swarm_size = tool_input.get("swarm_size", 1)
                pattern = tool_input.get("coordination_pattern", "collaborative")
                tools = tool_input.get("tools", [])
                model_provider = tool_input.get("model_provider", "default")
                
                print("↳ %sOrchestrating Swarm Intelligence%s" % (Colors.BOLD, Colors.RESET))
                
                # Parse task structure if possible
                task_parts = task.split(". ")
                if len(task_parts) >= 4 and any(keyword in task for keyword in ["Objective:", "Scope:", "Success:", "Context:"]):
                    # Structured task format
                    for part in task_parts:
                        if part.strip():
                            if "Objective:" in part:
                                print("  %sObjective:%s %s" % (Colors.CYAN, Colors.RESET, part.replace("Objective:", "").strip()))
                            elif "Scope:" in part:
                                print("  %sScope:%s %s" % (Colors.YELLOW, Colors.RESET, part.replace("Scope:", "").strip()))
                            elif "Success:" in part:
                                print("  %sSuccess:%s %s" % (Colors.GREEN, Colors.RESET, part.replace("Success:", "").strip()))
                            elif "Context:" in part:
                                print("  %sContext:%s %s" % (Colors.DIM, Colors.RESET, part.replace("Context:", "").strip()))
                else:
                    # Unstructured task - show as is
                    print("  Task: %s%s%s" % (Colors.YELLOW, task[:200] + "..." if len(task) > 200 else task, Colors.RESET))
                
                print("  %sConfiguration:%s" % (Colors.BOLD, Colors.RESET))
                print("    Agents: %s%d%s" % (Colors.CYAN, int(swarm_size), Colors.RESET))
                print("    Pattern: %s%s%s" % (Colors.MAGENTA, pattern, Colors.RESET))
                if tools:
                    print("    Tools: %s%s%s" % (Colors.GREEN, ", ".join(tools) if isinstance(tools, list) else str(tools), Colors.RESET))
                if model_provider and model_provider != "default":
                    print("    Model: %s%s%s" % (Colors.BLUE, model_provider, Colors.RESET))
                
                self.tools_used.append(f"swarm: {int(swarm_size)} agents, {pattern}")
            elif tool_name == "http_request":
                # Special handling for http_request - show full URL
                method = tool_input.get("method", "GET")
                url = tool_input.get("url", "")
                print("↳ HTTP Request: %s%s %s%s" % (Colors.MAGENTA, method, url, Colors.RESET))
                self.tools_used.append(f"http_request: {method} {url}")
            elif tool_name == "think":
                # Special handling for think tool - show full thought
                thought = tool_input.get("thought", "")
                cycle_count = tool_input.get("cycle_count", 1)
                print("↳ Thinking (%s%d cycles%s):" % (Colors.CYAN, cycle_count, Colors.RESET))
                print("  Thought: %s%s%s" % (Colors.DIM, thought[:500] + "..." if len(thought) > 500 else thought, Colors.RESET))
                self.tools_used.append(f"think: {cycle_count} cycles")
            elif tool_input:
                # Show first 2 most relevant parameters for other tools
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

        # Add blank line for readability
        print()
        self.last_was_tool = True
        self.last_was_reasoning = False

    def _show_tool_result(self, tool_id, tool_result):
        """Display tool execution results if they contain meaningful output"""
        tool_use = self.tool_use_map.get(tool_id, {})
        tool_name = tool_use.get("name", "unknown")

        # Extract result content
        result_content = tool_result.get("content", [])
        status = tool_result.get("status", "unknown")

        # Process tool output based on tool type
        if tool_name == "shell" and result_content:
            for content_block in result_content:
                if isinstance(content_block, dict) and "text" in content_block:
                    output_text = content_block.get("text", "")
                    if output_text.strip():
                        # Filter out execution summary lines
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

                        # Only show output if there's content after filtering
                        if filtered_lines and any(
                            line.strip() for line in filtered_lines
                        ):
                            for line in filtered_lines:
                                print(line)
                    break
        elif status == "error":
            # Show errors for any tool, but filter out empty error messages
            for content_block in result_content:
                if isinstance(content_block, dict) and "text" in content_block:
                    error_text = content_block.get("text", "").strip()
                    if error_text and error_text != "Error:":
                        print("%sError: %s%s" % (Colors.RED, error_text, Colors.RESET))
        else:
            # Show output for other tools (like swarm, mem0_memory, etc.)
            if result_content and tool_name not in ["shell"]:  # Shell already handled above
                for content_block in result_content:
                    if isinstance(content_block, dict) and "text" in content_block:
                        output_text = content_block.get("text", "")
                        if output_text.strip():
                            # For swarm tool, show the full output without truncation
                            if tool_name == "swarm":
                                print("%s[Swarm Output]%s" % (Colors.CYAN, Colors.RESET))
                                print(output_text)
                            # For other tools, show reasonable output
                            else:
                                # Limit output to reasonable length for non-swarm tools
                                max_lines = 50
                                lines = output_text.strip().split("\n")
                                if len(lines) > max_lines:
                                    for line in lines[:max_lines]:
                                        print(line)
                                    print(
                                        "%s... (%d more lines)%s"
                                        % (Colors.DIM, len(lines) - max_lines, Colors.RESET)
                                    )
                                else:
                                    print(output_text)
                            break  # Only show first text block

        # Add separator line after tool result
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
        # Since we're using mem0_memory tool now, we can't directly access memories here
        # The agent should use mem0_memory(action="list") to get evidence
        # For now, return empty list to maintain compatibility
        return []

    def generate_final_report(self, agent, target: str, objective: str) -> None:
        """
        Generate comprehensive final assessment report using LLM analysis.

        Args:
            agent: The agent instance for generating the report
            target: Target system being assessed
            objective: Assessment objective/goals
        """
        # Prevent duplicate report generation
        if self.report_generated:
            return
        self.report_generated = True

        print("\n%s%s%s" % (Colors.DIM, "═" * 80, Colors.RESET))
        print(
            "%s%sGenerating Final Assessment Report%s"
            % (Colors.CYAN, Colors.BOLD, Colors.RESET)
        )
        print("%s%s%s" % (Colors.DIM, "═" * 80, Colors.RESET))

        # Retrieve evidence from memory system
        evidence = self._retrieve_evidence()

        # Always generate some form of report, even if no evidence or LLM fails
        report_content = ""

        if not evidence:
            self._display_no_evidence_message()
            report_content = self._generate_no_evidence_report(target, objective)
        else:
            # Generate LLM-based assessment report
            try:
                report_content = self._generate_llm_report(
                    agent, target, objective, evidence
                )
                self._display_final_report(report_content)

            except Exception as e:
                print(
                    "%sError generating final report: %s%s"
                    % (Colors.RED, str(e), Colors.RESET)
                )
                self._display_fallback_evidence(evidence)
                report_content = self._generate_fallback_report(
                    target, objective, evidence
                )

        # Always save report to file, regardless of content type
        self._save_report_to_file(report_content, target, objective)

    def _retrieve_evidence(self) -> List[Dict]:
        """Retrieve all collected evidence from memory system."""
        evidence = []
        
        # Get memory client using the helper function
        memory_client = get_memory_client()
        if memory_client is None:
            logger.error("Memory client is not initialized!")
            print(
                "%sError: Memory client not initialized. Cannot retrieve evidence.%s"
                % (Colors.RED, Colors.RESET)
            )
            return evidence
        
        # Use simple user_id for consistency
        agent_user_id = "cyber_agent"
        
        try:
            # Debug logging
            logger.info("Attempting to retrieve memories for user_id: %s", agent_user_id)
            
            # Call list_memories on the memory client
            memories_response = memory_client.list_memories(user_id=agent_user_id)
            
            # Debug the response type
            logger.debug("Memory response type: %s", type(memories_response))
            logger.debug("Memory response: %s", memories_response)
            
            # Handle different response formats from mem0 API
            if isinstance(memories_response, dict):
                # Extract memories from standard response formats
                raw_memories = memories_response.get("memories", memories_response.get("results", []))
                logger.debug("Extracted %d memories from dict response", len(raw_memories))
            elif isinstance(memories_response, list):
                # Direct list return
                raw_memories = memories_response
                logger.debug("Got %d memories as list", len(raw_memories))
            else:
                # Fallback for unexpected format
                raw_memories = []
                logger.warning("Unexpected memory response format: %s", type(memories_response))

            logger.info("Found %d total memories", len(raw_memories))
            
            # Filter for 'finding' category and format for the report
            for mem in raw_memories:
                # Ensure 'metadata' is a dict and 'category' exists
                metadata = mem.get('metadata', {})
                
                # Debug each memory
                logger.debug("Processing memory: %s", mem)
                
                if metadata and metadata.get('category') == 'finding':
                    evidence.append({
                        'category': metadata.get('category'),
                        'content': mem.get('memory', 'N/A'),
                        'id': mem.get('id', 'N/A')
                    })
                    logger.info("Added finding to evidence: %s...", mem.get('memory', 'N/A')[:50])
                # Also include any memories that don't have a category but are relevant
                elif 'memory' in mem and 'category' not in metadata:
                    # Heuristic: if it's a concise memory, include it
                    if len(mem.get('memory', '').split()) < 50: # Arbitrary length for "concise"
                        evidence.append({
                            'category': 'general',
                            'content': mem.get('memory', 'N/A'),
                            'id': mem.get('id', 'N/A')
                        })
                        logger.info("Added general memory to evidence: %s...", mem.get('memory', 'N/A')[:50])

            print(
                "%sRetrieved %d items from memory for final report.%s"
                % (Colors.DIM, len(evidence), Colors.RESET)
            )
            
        except Exception as e:
            logger.error("Error retrieving evidence from mem0_memory: %s", str(e), exc_info=True)
            print(
                "%sWarning: Failed to retrieve evidence from memory (user_id: %s). Report may be incomplete.%s"
                % (Colors.YELLOW, agent_user_id, Colors.RESET)
            )
            print(
                "%sError details: %s%s" % (Colors.DIM, str(e), Colors.RESET)
            )
            evidence = [] # Ensure empty list on error

        return evidence

    def _display_no_evidence_message(self) -> None:
        """Display message when no evidence is available."""
        print(
            "%sNo evidence collected during operation%s" % (Colors.YELLOW, Colors.RESET)
        )
        print(
            "%sSteps completed: %d/%d%s"
            % (Colors.DIM, self.steps, self.max_steps, Colors.RESET)
        )
        print(
            "%sMemory operations: %d%s"
            % (Colors.DIM, self.memory_operations, Colors.RESET)
        )

    def _generate_llm_report(
        self, agent, target: str, objective: str, evidence: List[Dict]
    ) -> str:
        """Generate assessment report using LLM analysis."""
        # Format evidence for LLM analysis
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

        # Capture stdout to prevent duplicate display
        original_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            # Generate report with suppressed output
            # Create a new agent with mem0_memory tool for evidence verification
            # Use the same model as the original agent
            report_agent = Agent(
                model=agent.model if hasattr(agent, 'model') else None,
                tools=[mem0_memory],  # Include mem0_memory for evidence verification
                system_prompt="You are a cybersecurity assessment report generator. Follow the exact structure and requirements provided in the prompt. Generate a professional penetration testing report that includes all six requested sections: Executive Summary, Critical Vulnerabilities, Attack Vectors, Risk Assessment, Recommendations, and Security Posture Evaluation. Use mem0_memory if needed to ensure all findings are included."
            )
            
            raw_report = report_agent(report_prompt)
            report_text = str(raw_report)
            return self._clean_duplicate_content(report_text)
        finally:
            # Restore stdout
            sys.stdout = original_stdout

    def _clean_duplicate_content(self, report_content: str) -> str:
        """Remove duplicate sections from LLM-generated content."""
        report_lines = report_content.split("\n")
        clean_lines = []
        seen_section_markers = set()

        i = 0
        while i < len(report_lines):
            line = report_lines[i]

            # Check for report start markers that indicate duplication
            if (
                line.strip().startswith("# Penetration Testing Report")
                or line.strip().startswith("**Target:")
                or (line.strip().startswith("# ") and "Report" in line)
            ):
                # If we've seen this exact marker before, stop processing
                if line.strip() in seen_section_markers:
                    break

                # For the main report header, also check if we already have content
                if (
                    line.strip().startswith("# Penetration Testing Report")
                    and len(clean_lines) > 10
                ):  # Already have substantial content
                    break

                seen_section_markers.add(line.strip())

            # Check for duplicate executive summary sections
            elif line.strip().startswith("## 1. Executive Summary") and any(
                "## 1. Executive Summary" in existing_line
                for existing_line in clean_lines
            ):
                # Found duplicate executive summary, stop here
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
            # Create evidence directory if it doesn't exist
            evidence_dir = os.path.join(
                get_data_path("evidence"), f"evidence_{self.operation_id}"
            )
            os.makedirs(evidence_dir, exist_ok=True)

            # Save report with timestamp
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
                "\n%sReport saved to: %s%s"
                % (Colors.GREEN, report_path, Colors.RESET)
            )

        except Exception as e:
            print(
                "%sWarning: Could not save report to file: %s%s"
                % (Colors.YELLOW, str(e), Colors.RESET)
            )

    def _generate_no_evidence_report(self, target: str, objective: str) -> str:  # pylint: disable=unused-argument
        """Generate a report when no evidence was collected."""
        summary = self.get_summary()
        return f"""## Assessment Summary

**Status:** No evidence collected during assessment

### Operation Details
- Steps completed: {summary["total_steps"]}/{self.max_steps}
- Tools created: {summary["tools_created"]}
- Memory operations: {summary["memory_operations"]}

### Possible Reasons
- Target may not be reachable
- No vulnerabilities found within step limit
- Authentication or permission issues
- Network connectivity problems

### Recommendations
- Verify target accessibility
- Increase iteration limit if needed
- Check network connectivity and permissions
- Review target configuration and scope
"""

    def _generate_fallback_report(
        self, target: str, objective: str, evidence: List[Dict]  # pylint: disable=unused-argument
    ) -> str:
        """Generate a fallback report when LLM generation fails."""
        summary = self.get_summary()
        evidence_summary = ""

        # Group evidence by category
        categories = {}
        for item in evidence:
            cat = item.get("category", "unknown")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item.get("content", ""))

        # Format evidence by category
        for category, items in categories.items():
            evidence_summary += f"\n### {category.title()} Findings\n"
            for i, item in enumerate(items[:5], 1):  # Limit to 5 items per category
                evidence_summary += (
                    f"{i}. {item[:200]}{'...' if len(item) > 200 else ''}\n"
                )
            if len(items) > 5:
                evidence_summary += f"... and {len(items) - 5} more items\n"

        return f"""## Assessment Summary

**Status:** Evidence collected but LLM report generation failed

### Operation Details
- Steps completed: {summary["total_steps"]}/{self.max_steps}
- Tools created: {summary["tools_created"]}
- Evidence items: {len(evidence)}
- Memory operations: {summary["memory_operations"]}

### Evidence Collected
{evidence_summary}

### Note
This is a fallback report generated when AI analysis was unavailable. 
Review the evidence items above for detailed findings.
"""

    def _display_fallback_evidence(self, evidence: List[Dict]) -> None:
        """Display evidence summary as fallback when LLM generation fails."""
        print(
            "\n%sDisplaying collected evidence instead:%s"
            % (Colors.YELLOW, Colors.RESET)
        )
        for i, item in enumerate(evidence, 1):
            print("\n%d. %s[%s]%s" % (i, Colors.GREEN, item["category"], Colors.RESET))
            content_preview = item["content"][:FALLBACK_EVIDENCE_PREVIEW_LENGTH]
            print(
                "   %s%s"
                % (
                    content_preview,
                    "..."
                    if len(item["content"]) > FALLBACK_EVIDENCE_PREVIEW_LENGTH
                    else "",
                )
            )
            if len(item["content"]) > FALLBACK_EVIDENCE_PREVIEW_LENGTH:
                print("   %s(truncated)%s" % (Colors.DIM, Colors.RESET))
