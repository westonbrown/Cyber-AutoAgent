#!/usr/bin/env python3
"""
SDK-Native Handler - Properly uses Strands SDK callbacks
Clean SDK integration that emits structured events for React UI
"""

import json
import time
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from strands.handlers import PrintingCallbackHandler
from strands.hooks import HookProvider, HookRegistry
from strands.experimental.hooks.events import (
    BeforeToolInvocationEvent,
    AfterToolInvocationEvent,
    BeforeModelInvocationEvent,
    AfterModelInvocationEvent,
)

logger = logging.getLogger(__name__)


class SDKNativeHandler(PrintingCallbackHandler):
    """Handler that extends SDK's PrintingCallbackHandler for React UI integration

    This handler follows SDK patterns while emitting structured events for the React UI.
    It handles:
    - Tool execution with proper argument display
    - Output formatting for various tool types
    - Reasoning text buffering to prevent fragmentation
    - Metrics tracking and reporting
    """

    def __init__(self, max_steps=100, operation_id=None):
        super().__init__()
        self.current_step = 0
        self.max_steps = max_steps
        self.operation_id = operation_id or f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_time = time.time()

        # Track metrics
        self.memory_ops = 0
        self.evidence_count = 0
        self.last_metrics = None

        # Track token usage manually since SDK doesn't emit real-time metrics
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.last_metrics_emit_time = time.time()

        # Tool tracking
        self.last_tool_name = None
        self.last_tool_id = None
        self.announced_tools = set()
        self.tool_input_buffer = {}  # Store tool inputs for result processing
        self.tools_used = set()  # Track all tools used during the assessment

        # Reasoning buffer to accumulate fragments
        self.reasoning_buffer = []
        self.reasoning_timer = None
        self.last_reasoning_time = 0

        # Step header tracking for proper ordering
        self.pending_step_header = False

        # State tracking for proper termination
        self._stop_tool_used = False
        self._report_generated = False

        # Emit initial metrics
        self._emit_initial_metrics()

    def __call__(self, **kwargs):
        """Process SDK callbacks following PrintingCallbackHandler pattern

        Args:
            **kwargs: SDK callback parameters including:
                - reasoningText: Reasoning/thinking text from the model
                - data: Streaming text data
                - complete: Whether streaming is complete
                - current_tool_use: Tool being invoked
                - toolResult: Result from tool execution
                - message: Message objects
                - event_loop_metrics: SDK metrics
        """

        # SDK provides these key parameters (matching PrintingCallbackHandler)
        reasoning_text = kwargs.get("reasoningText")
        data = kwargs.get("data", "")
        complete = kwargs.get("complete", False)
        current_tool_use = kwargs.get("current_tool_use")
        tool_result = kwargs.get("toolResult")
        message = kwargs.get("message")
        event_loop_metrics = kwargs.get("event_loop_metrics")

        # Check if this is a reasoning delta (fragment)
        reasoning_delta = kwargs.get("reasoning", False) and reasoning_text

        # Process messages for tool results and step progression
        if message and isinstance(message, dict):
            content = message.get("content", [])

            # Check if this assistant message will contain tool usage (for proper step header timing)
            has_tool_use = False
            if message.get("role") == "assistant":
                for block in content:
                    if isinstance(block, dict) and (block.get("type") == "tool_use" or "toolUse" in block):
                        has_tool_use = True
                        break

            # For assistant messages with tool use, mark that we need to emit step header later
            # (Step header will be emitted AFTER reasoning is flushed but BEFORE tool starts)
            if message.get("role") == "assistant" and has_tool_use:
                self.current_step += 1
                self.pending_step_header = True

            # Process tool results from message content (SDK native pattern)
            for i, block in enumerate(content):
                if isinstance(block, dict):
                    # Check for various tool result formats
                    if "toolResult" in block:
                        tool_result = block["toolResult"]
                        self._process_tool_result_from_message(tool_result)
                    elif "toolResponse" in block:
                        tool_result = block["toolResponse"]
                        self._process_tool_result_from_message(tool_result)
                    elif block.get("type") == "tool_result":
                        self._process_tool_result_from_message(block)

            # For assistant messages WITHOUT tool use, emit step header normally
            if message.get("role") == "assistant" and not has_tool_use:
                self.current_step += 1

                # Estimate input tokens from message content
                for item in content:
                    if isinstance(item, dict):
                        if "text" in item:
                            self.total_output_tokens += len(str(item.get("text", ""))) // 4

                self._emit_ui_event(
                    {
                        "type": "step_header",
                        "step": self.current_step,
                        "maxSteps": self.max_steps,
                        "operation": self.operation_id,
                        "duration": self._format_duration(time.time() - self.start_time),
                    }
                )
            elif message.get("role") == "user":
                # Count input tokens from user messages
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        self.total_input_tokens += len(str(item.get("text", ""))) // 4

        # Handle reasoning text (SDK native!) - Accumulate silently until tool starts
        if reasoning_text:
            self._accumulate_reasoning_text(reasoning_text)
            # Estimate tokens for reasoning (rough estimate: 4 chars per token)
            self.total_output_tokens += len(reasoning_text) // 4

        # Handle streaming data - for non-reasoning content, emit directly
        elif data and not complete:
            # Don't buffer regular streaming data - only reasoning text needs buffering
            # Just estimate tokens for data
            self.total_output_tokens += len(data) // 4

        # Handle tool announcements (SDK native!)
        if current_tool_use:
            tool_name = current_tool_use.get("name", "")
            tool_id = current_tool_use.get("toolUseId", "")
            tool_input = current_tool_use.get("input", {})

            # Debug: Log full current_tool_use structure
            # Full current_tool_use: {current_tool_use}", file=sys.stderr, flush=True)

            # Only emit events for new tools
            if tool_id and tool_id not in self.announced_tools:
                # Emit any accumulated reasoning text before tool starts
                self._emit_accumulated_reasoning()

                # Emit pending step header AFTER reasoning but BEFORE tool
                # OR if this is the first tool and no step header has been emitted yet
                if self.pending_step_header or (self.current_step == 0 and tool_id):
                    if self.current_step == 0:
                        self.current_step = 1  # First tool is step 1
                        # First tool detected, emitting step header for step 1", file=sys.stderr, flush=True)
                    else:
                        # Emitting step header AFTER reasoning flush for step {self.current_step}", file=sys.stderr, flush=True)
                        pass  # Add pass statement to satisfy Python's syntax requirement

                    self._emit_ui_event(
                        {
                            "type": "step_header",
                            "step": self.current_step,
                            "maxSteps": self.max_steps,
                            "operation": self.operation_id,
                            "duration": self._format_duration(time.time() - self.start_time),
                        }
                    )
                    self.pending_step_header = False

                # NO divider after reasoning - step header provides the visual break

                self.announced_tools.add(tool_id)
                self.last_tool_name = tool_name
                self.last_tool_id = tool_id
                self.tools_used.add(tool_name)  # Track tools for report generation

                # Store tool input for later use in results
                self.tool_input_buffer[tool_id] = tool_input

                # Emit tool start event
                self._emit_ui_event({"type": "tool_start", "tool_name": tool_name, "tool_input": tool_input})

                # Emit tool-specific events based on tool type - but only if we have complete input
                if tool_input and (
                    isinstance(tool_input, dict) or (isinstance(tool_input, str) and len(tool_input) > 0)
                ):
                    self._emit_tool_specific_events(tool_name, tool_input)

            # Handle streaming tool input updates for already announced tools
            elif tool_id and tool_id in self.announced_tools and tool_input:
                # Update stored tool input
                self.tool_input_buffer[tool_id] = tool_input

                # Check if this looks like a complete input (applies to ALL tools)
                if isinstance(tool_input, str):
                    try:
                        # Try to parse as JSON to see if it's complete
                        import json

                        parsed_input = json.loads(tool_input)
                        if isinstance(parsed_input, dict):
                            # This looks like complete input, emit tool-specific events
                            self._emit_tool_specific_events(tool_name, parsed_input)
                    except json.JSONDecodeError:
                        # Not complete JSON yet, ignore
                        pass
                elif isinstance(tool_input, dict):
                    # If it's already a dict, emit immediately
                    self._emit_tool_specific_events(tool_name, tool_input)

        # Handle tool results from direct parameter
        if tool_result:
            # Debug: Log tool result processing
            # Processing tool result from variable: {tool_result}", file=sys.stderr, flush=True)
            self._process_tool_result_from_message(tool_result)

        # Handle tool results from kwargs (alternative parameter names)
        if kwargs.get("toolResult") is not None:
            # Got toolResult in kwargs: {kwargs.get('toolResult')}", file=sys.stderr, flush=True)
            self._process_tool_result_from_message(kwargs.get("toolResult"))

        # Check for other possible tool result parameter names
        for alt_key in ["result", "tool_result", "execution_result", "response", "output"]:
            if alt_key in kwargs and kwargs[alt_key] is not None:
                # Found alternative tool result key '{alt_key}': {kwargs[alt_key]}", file=sys.stderr, flush=True)
                # Convert to standard format if needed
                result_data = kwargs[alt_key]
                if isinstance(result_data, str):
                    # Convert string to standard format
                    result_data = {"content": [{"text": result_data}], "status": "success"}
                self._process_tool_result_from_message(result_data)

        # Also check if we have a complete flag without results - might indicate tool completion
        if complete and not tool_result and not any(k in kwargs for k in ["toolResult", "result", "tool_result"]):
            if self.last_tool_name:
                # Complete flag set but no tool result for {self.last_tool_name}", file=sys.stderr, flush=True)
                pass  # Add pass statement to satisfy Python's syntax requirement

        # Track metrics from SDK (not custom!)
        if event_loop_metrics:
            self.last_metrics = event_loop_metrics
            # Emit footer update with SDK metrics
            usage = event_loop_metrics.accumulated_usage
            tokens_used = usage.get("totalTokens", 0)

            # Debug: log what we're getting
            # Metrics: usage={usage}", file=sys.stderr, flush=True)

            # Calculate cost based on model
            # Default to Sonnet pricing if not specified
            input_tokens = usage.get("inputTokens", 0)
            output_tokens = usage.get("outputTokens", 0)

            # Sonnet pricing: $3/1M input, $15/1M output
            input_cost = (input_tokens / 1_000_000) * 3.0
            output_cost = (output_tokens / 1_000_000) * 15.0
            total_cost = input_cost + output_cost

            self._emit_ui_event(
                {
                    "type": "metrics_update",
                    "metrics": {
                        "tokens": tokens_used,
                        "cost": total_cost,
                        "duration": self._format_duration(time.time() - self.start_time),
                        "memoryOps": self.memory_ops,
                        "evidence": self.evidence_count,
                    },
                }
            )

        # Handle completion events
        if complete or kwargs.get("is_final"):
            self._emit_accumulated_reasoning()

            # Check if this is a tool completion without explicit result
            if self.last_tool_name and not tool_result and not kwargs.get("toolResult"):
                # Emit a completion status for tools that might not have explicit results
                self._emit_ui_event({"type": "thinking_end"})
                self._emit_ui_event({"type": "output", "content": f"Command completed successfully"})

        # Emit metrics periodically (every 5 seconds)
        current_time = time.time()
        if current_time - self.last_metrics_emit_time > 5:
            self._emit_estimated_metrics()
            self.last_metrics_emit_time = current_time

        # DON'T call parent class - it prints to stdout causing duplicate output
        # We handle all output through structured events
        # super().__call__(**kwargs)

    def _emit_ui_event(self, event):
        """Emit event for UI - single place for event emission"""
        # Use the existing marker format for compatibility
        # But this is the ONLY place we emit custom events
        event["timestamp"] = datetime.now().isoformat()
        print(f"__CYBER_EVENT__{json.dumps(event)}__CYBER_EVENT_END__", flush=True)

    def _emit_initial_metrics(self):
        """Emit initial metrics on handler creation"""
        self._emit_ui_event(
            {
                "type": "metrics_update",
                "metrics": {"tokens": 0, "cost": 0.0, "duration": "0s", "memoryOps": 0, "evidence": 0},
            }
        )

    def _emit_estimated_metrics(self):
        """Emit estimated metrics based on token counting"""
        # Calculate estimated cost
        # Using Claude 3.5 Sonnet pricing: $3/1M input, $15/1M output
        input_cost = (self.total_input_tokens / 1_000_000) * 3.0
        output_cost = (self.total_output_tokens / 1_000_000) * 15.0
        total_cost = input_cost + output_cost

        # Emit metrics update
        self._emit_ui_event(
            {
                "type": "metrics_update",
                "metrics": {
                    "tokens": self.total_input_tokens + self.total_output_tokens,
                    "cost": total_cost,
                    "duration": self._format_duration(time.time() - self.start_time),
                    "memoryOps": self.memory_ops,
                    "evidence": self.evidence_count,
                },
            }
        )

    def _emit_tool_specific_events(self, tool_name: str, tool_input: Any) -> None:
        """Emit tool-specific events for proper UI display"""
        if tool_name == "shell":
            self._emit_shell_commands(tool_input)
        elif tool_name == "mem0_memory":
            self._emit_memory_operation(tool_input)
        elif tool_name == "http_request":
            self._emit_http_request(tool_input)
        elif tool_name == "file_write":
            self._emit_file_write(tool_input)
        elif tool_name == "editor":
            self._emit_editor_operation(tool_input)
        elif tool_name == "handoff_to_user":
            self._emit_user_handoff(tool_input)
        elif tool_name == "swarm":
            self._emit_swarm_operation(tool_input)
        elif tool_name == "python_repl":
            self._emit_python_repl(tool_input)
        elif tool_name == "load_tool":
            self._emit_load_tool(tool_input)
        elif tool_name == "stop":
            self._emit_stop_tool(tool_input)
        elif tool_name == "generate_security_report":
            self._emit_report_generator(tool_input)
        elif tool_name == "handoff_to_agent":
            self._emit_agent_handoff(tool_input)
        else:
            # For other tools, show the input parameters
            self._emit_generic_tool_params(tool_name, tool_input)

    def _emit_shell_commands(self, tool_input: Any) -> None:
        """Extract and emit shell commands"""
        commands = []

        if isinstance(tool_input, str):
            commands = [tool_input]
        elif isinstance(tool_input, dict):
            # Try various field names that tools might use
            for field in ["command", "commands", "cmd", "script", "bash_command", "shell_command"]:
                if field in tool_input:
                    value = tool_input[field]
                    if isinstance(value, list):
                        commands = value
                    elif isinstance(value, str):
                        # Handle JSON string format like '["cmd1", "cmd2"]'
                        try:
                            import json

                            parsed_value = json.loads(value)
                            if isinstance(parsed_value, list):
                                commands = parsed_value
                            else:
                                commands = [str(value)]
                        except (json.JSONDecodeError, TypeError):
                            commands = [str(value)]
                    else:
                        commands = [str(value)]
                    break

        # Emit each command with the correct prefix format
        for cmd in commands:
            if cmd:
                self._emit_ui_event({"type": "command", "content": str(cmd)})

        # After all commands are emitted, signal that commands are complete
        # This allows the UI to start thinking animation after ALL commands are shown
        if commands:
            self._emit_ui_event({"type": "tool_commands_complete"})

    def _emit_memory_operation(self, tool_input: Any) -> None:
        """Emit memory operation details"""
        if isinstance(tool_input, dict):
            action = tool_input.get("action", "unknown")
            if action == "store":
                content = tool_input.get("content", "")
                preview = content[:100] + "..." if len(content) > 100 else content
                self._emit_ui_event({"type": "metadata", "content": {"action": "storing memory", "preview": preview}})
            elif action == "retrieve":
                query = tool_input.get("query", "")
                self._emit_ui_event({"type": "metadata", "content": {"action": "retrieving memory", "query": query}})

    def _emit_http_request(self, tool_input: Any) -> None:
        """Emit HTTP request details"""
        if isinstance(tool_input, dict):
            method = tool_input.get("method", "GET")
            url = tool_input.get("url", "")
            self._emit_ui_event({"type": "metadata", "content": {"method": method, "url": url}})

    def _emit_file_write(self, tool_input: Any) -> None:
        """Emit file write details"""
        if isinstance(tool_input, dict):
            path = tool_input.get("path", "")
            content = str(tool_input.get("content", ""))
            preview = content[:50] + "..." if len(content) > 50 else content
            self._emit_ui_event({"type": "metadata", "content": {"path": path, "preview": preview}})

    def _emit_editor_operation(self, tool_input: Any) -> None:
        """Emit editor operation details"""
        if isinstance(tool_input, dict):
            command = tool_input.get("command", "")
            path = tool_input.get("path", "")
            self._emit_ui_event({"type": "metadata", "content": {"command": command, "path": path}})

    def _emit_user_handoff(self, tool_input: Any) -> None:
        """Emit user handoff event"""
        if isinstance(tool_input, dict):
            message = tool_input.get("message", "")
            breakout = tool_input.get("breakout_of_loop", False)
        else:
            message = str(tool_input) if tool_input else ""
            breakout = False

        self._emit_ui_event({"type": "user_handoff", "message": message, "breakout": breakout})

    def _emit_generic_tool_params(self, tool_name: str, tool_input: Any) -> None:
        """Emit generic tool parameters"""
        if isinstance(tool_input, dict) and tool_input:
            metadata = {}
            for i, (key, value) in enumerate(tool_input.items()):
                if i >= 3:  # Limit to first 3 parameters
                    metadata["..."] = f"and {len(tool_input) - 3} more"
                    break
                value_str = str(value)[:50]
                if len(str(value)) > 50:
                    value_str += "..."
                metadata[key] = value_str

            if metadata:
                self._emit_ui_event({"type": "metadata", "content": metadata})

    def _emit_swarm_operation(self, tool_input: Any) -> None:
        """Emit swarm orchestration details"""
        if isinstance(tool_input, dict):
            agents = tool_input.get("agents", [])
            task = tool_input.get("task", "")
            agent_count = len(agents) if isinstance(agents, list) else 0
            task_preview = task[:100] + "..." if len(task) > 100 else task

            self._emit_ui_event(
                {"type": "metadata", "content": {"agents": f"{agent_count} agents", "task": task_preview}}
            )

    def _emit_python_repl(self, tool_input: Any) -> None:
        """Emit Python REPL execution details"""
        if isinstance(tool_input, dict):
            code = tool_input.get("code", "")
            # Show first few lines of code
            code_lines = code.split("\n")
            if len(code_lines) > 3:
                preview = "\n".join(code_lines[:3]) + "\n..."
            else:
                preview = code

            self._emit_ui_event({"type": "metadata", "content": {"code": preview}})

    def _emit_load_tool(self, tool_input: Any) -> None:
        """Emit dynamic tool loading details"""
        if isinstance(tool_input, dict):
            tool_name = tool_input.get("tool_name", "")
            path = tool_input.get("path", "")

            self._emit_ui_event({"type": "metadata", "content": {"loading": tool_name, "path": path}})

    def _emit_stop_tool(self, tool_input: Any) -> None:
        """Emit stop execution details"""
        # Mark that stop tool was used
        self._stop_tool_used = True

        if isinstance(tool_input, dict):
            reason = tool_input.get("reason", "No reason provided")
        else:
            reason = str(tool_input) if tool_input else "No reason provided"

        self._emit_ui_event({"type": "metadata", "content": {"stopping": reason}})

    def _emit_report_generator(self, tool_input: Any) -> None:
        """Emit report generation details"""
        if isinstance(tool_input, dict):
            target = tool_input.get("target", "")
            report_type = tool_input.get("report_type", "security_assessment")

            self._emit_ui_event({"type": "metadata", "content": {"target": target, "type": report_type}})

    def _emit_agent_handoff(self, tool_input: Any) -> None:
        """Emit agent handoff details"""
        if isinstance(tool_input, dict):
            agent_name = tool_input.get("agent_name", "")
            message = tool_input.get("message", "")
            message_preview = message[:100] + "..." if len(message) > 100 else message

            self._emit_ui_event({"type": "metadata", "content": {"handoff_to": agent_name, "message": message_preview}})

    def _accumulate_reasoning_text(self, text):
        """Silently accumulate reasoning text without emitting anything"""
        if not text:
            return

        # Filter out standalone "reasoning" labels completely
        if text.strip().lower() == "reasoning":
            return

        # Clean and accumulate text with proper spacing
        cleaned_text = text.strip()
        if cleaned_text:
            # If we have existing content, we need to handle spacing
            if self.reasoning_buffer:
                last_char = self.reasoning_buffer[-1][-1] if self.reasoning_buffer else ""
                first_char = cleaned_text[0]

                # Add space if both are alphanumeric or if transitioning between word and punctuation
                if (
                    last_char.isalnum()
                    and first_char.isalnum()
                    or last_char.isalnum()
                    and first_char in ".!?:;,"
                    or last_char in ".!?:;,"
                    and first_char.isalnum()
                ):
                    self.reasoning_buffer.append(" ")

            # Add the cleaned text
            self.reasoning_buffer.append(cleaned_text)

        self.last_reasoning_time = time.time()

    def _emit_accumulated_reasoning(self):
        """Emit accumulated reasoning text as a single complete block"""
        if self.reasoning_buffer:
            # Combine all buffered reasoning text into a single clean block
            combined_reasoning = "".join(self.reasoning_buffer).strip()

            if combined_reasoning:
                self._emit_ui_event({"type": "reasoning", "content": combined_reasoning})

            # Clear the buffer after emitting
            self.reasoning_buffer = []

    def _process_tool_result_from_message(self, tool_result: Any) -> None:
        """Process tool results from message content (SDK native pattern)"""
        # Emit tool completion event to stop thinking animation
        self._emit_ui_event({"type": "thinking_end"})

        # Handle different tool result types
        if hasattr(tool_result, "__dict__"):
            # AgentResult object - convert to dict
            tool_result_dict = tool_result.__dict__ if hasattr(tool_result, "__dict__") else {}
        elif isinstance(tool_result, dict):
            tool_result_dict = tool_result
        else:
            # Fallback for other types
            tool_result_dict = {"content": [{"text": str(tool_result)}], "status": "success"}

        # Extract SDK-structured content
        content_items = tool_result_dict.get("content", [])
        status = tool_result_dict.get("status", "success")
        tool_use_id = tool_result_dict.get("toolUseId")

        # Get the original tool input if available
        tool_input = self.tool_input_buffer.get(tool_use_id, {})

        # Handle error status
        if status == "error":
            error_text = ""
            for item in content_items:
                if isinstance(item, dict) and "text" in item:
                    error_text += item["text"] + "\n"

            if error_text.strip():
                self._emit_ui_event({"type": "error", "content": error_text.strip()})
            return

        # Process successful results - extract all content with enhanced parsing
        output_text = ""
        for item in content_items:
            if isinstance(item, dict):
                # Standard text content
                if "text" in item:
                    output_text += item["text"]
                # JSON content
                elif "json" in item:
                    import json

                    output_text += json.dumps(item["json"], indent=2)
                # Alternative field names that tools might use
                elif "content" in item:
                    output_text += str(item["content"])
                elif "output" in item:
                    output_text += str(item["output"])
                elif "result" in item:
                    output_text += str(item["result"])
            elif isinstance(item, str):
                # Handle direct string content
                output_text += item
            else:
                # Handle other types by converting to string
                output_text += str(item)

        # Emit output if we have content
        if output_text.strip():
            self._emit_ui_event({"type": "output", "content": output_text.strip()})
        else:
            # For tools that might not have output, provide completion status
            # Include shell tool in the fallback list since it often has empty results
            if self.last_tool_name in ["handoff_to_user", "handoff_to_agent", "stop", "mem0_memory", "shell"]:
                status_messages = {
                    "handoff_to_user": "Awaiting user response",
                    "handoff_to_agent": "Handed off to agent",
                    "stop": "Execution stopped",
                    "mem0_memory": "Memory operation completed",
                    "shell": "Command completed successfully",
                }
                self._emit_ui_event(
                    {"type": "output", "content": status_messages.get(self.last_tool_name, "Operation completed")}
                )
            else:
                pass  # Tool without output fallback

        # Update metrics for specific tools
        if self.last_tool_name == "mem0_memory":
            self.memory_ops += 1
            action = tool_input.get("action", "unknown") if isinstance(tool_input, dict) else "unknown"
            if action == "store":
                self.evidence_count += 1

    def _process_memory_result(self, content_items: List[Any], tool_input: Dict[str, Any]) -> None:
        """Process memory operation results"""
        action = tool_input.get("action", "unknown") if isinstance(tool_input, dict) else "unknown"

        # Check if we got any content back
        has_content = any(isinstance(item, dict) and item.get("text") for item in content_items)

        if action == "retrieve" and has_content:
            # Show retrieved memories
            memories = []
            for item in content_items:
                if isinstance(item, dict) and "text" in item:
                    memories.append(item["text"])

            if memories:
                self._emit_ui_event({"type": "output", "content": "\n".join(memories)})
        else:
            # Just emit completion status
            self._emit_ui_event({"type": "output", "content": f"Memory {action} completed"})

        # Track metrics
        self.memory_ops += 1
        if action == "store":
            self.evidence_count += 1

    def _process_shell_result(self, content_items: List[Any], metadata: Dict[str, Any]) -> None:
        """Process shell command results"""
        output_lines = []

        for item in content_items:
            if isinstance(item, dict) and "text" in item:
                output_lines.append(item["text"])

        if output_lines:
            # Emit the shell output
            self._emit_ui_event(
                {
                    "type": "output",
                    "content": "\n".join(output_lines),
                    "exitCode": metadata.get("exit_code"),
                    "duration": metadata.get("duration_seconds"),
                }
            )

    def _process_generic_result(self, content_items: List[Any], metadata: Dict[str, Any]) -> None:
        """Process generic tool results"""
        output_lines = []

        for item in content_items:
            if isinstance(item, dict) and "text" in item:
                output_lines.append(item["text"])

        if output_lines:
            self._emit_ui_event(
                {"type": "output", "content": "\n".join(output_lines), "duration": metadata.get("duration_seconds")}
            )
        elif self.last_tool_name in ["handoff_to_user", "handoff_to_agent", "stop"]:
            # These tools might have empty output
            status_messages = {
                "handoff_to_user": "Awaiting user response",
                "handoff_to_agent": "Handed off to agent",
                "stop": "Execution stopped",
            }
            self._emit_ui_event(
                {"type": "output", "content": status_messages.get(self.last_tool_name, "Operation completed")}
            )

    def _count_memory_ops(self, metrics):
        """Count memory operations from SDK metrics"""
        # Use our tracked count
        return self.memory_ops

    def _count_evidence(self, metrics):
        """Count evidence from memory storage operations"""
        # Use our tracked count
        return self.evidence_count

    def _format_duration(self, seconds):
        """Format duration for display"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m {int(seconds%60)}s"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}h {mins}m"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}d {hours}h"

    def ensure_report_generated(self, agent, target, objective, module=None):
        """Ensure report is generated only once - single trigger point"""
        if not getattr(self, "_report_generated", False):
            self.generate_final_report(agent, target, objective, module)

    def generate_final_report(self, agent, target, objective, module=None):
        """Generate final report using the report agent after main agent completes"""
        # Prevent duplicate report generation
        if getattr(self, "_report_generated", False):
            return

        try:
            # Mark report as generated
            self._report_generated = True

            # Import the report tool
            from modules.tools.report_generator import generate_security_report

            # Collect information for the report
            tools_used = list(self.tools_used) if hasattr(self, "tools_used") else []
            steps_executed = self.current_step

            # Generate the report using the tool
            self._emit_ui_event(
                {"type": "output", "content": "\n◆ Generating comprehensive security assessment report..."}
            )

            # Call the report generator tool
            # Determine the provider from the agent's model
            provider = "bedrock"  # Default
            if hasattr(agent, "model"):
                model_class = agent.model.__class__.__name__
                if "Bedrock" in model_class:
                    provider = "bedrock"
                elif "Ollama" in model_class:
                    provider = "ollama"
                elif "LiteLLM" in model_class:
                    provider = "litellm"

            report_content = generate_security_report(
                target=target,
                objective=objective,
                operation_id=self.operation_id,
                steps_executed=steps_executed,
                tools_used=tools_used,
                provider=provider,
                module=module,
            )

            # Emit the report content
            if report_content and not report_content.startswith("Error:"):
                self._emit_ui_event({"type": "output", "content": "\n" + report_content})
            else:
                self._emit_ui_event({"type": "error", "content": f"Failed to generate report: {report_content}"})

        except Exception as e:
            logger.error(f"Error generating final report: {e}")
            self._emit_ui_event({"type": "error", "content": f"Error generating report: {str(e)}"})

    @property
    def state(self):
        """Mock state for compatibility"""

        class MockState:
            report_generated = getattr(self, "_report_generated", False)
            stop_tool_used = getattr(self, "_stop_tool_used", False)
            step_limit_reached = self.current_step >= self.max_steps if hasattr(self, "current_step") else False

        return MockState()

    def should_stop(self) -> bool:
        """Check if the handler should stop execution."""
        # Check if stop tool was used or step limit reached
        return getattr(self, "_stop_tool_used", False) or (self.current_step >= self.max_steps)

    def has_reached_limit(self) -> bool:
        """Check if step limit has been reached."""
        return self.current_step >= self.max_steps

    @property
    def stop_tool_used(self) -> bool:
        """Check if stop tool was used."""
        return getattr(self, "_stop_tool_used", False)

    @property
    def report_generated(self) -> bool:
        """Check if report was generated."""
        return getattr(self, "_report_generated", False)

    def get_summary(self):
        """Get operation summary compatible with main application"""
        return {
            # Main app expects these keys
            "total_steps": self.current_step,
            "tools_created": len(self.tools_used),
            "evidence_collected": self.evidence_count,
            "memory_operations": self.memory_ops,
            "capability_expansion": bool(self.tools_used),
            "evidence_count": self.evidence_count,
            "duration": self._format_duration(time.time() - self.start_time),
            "metrics": self.last_metrics,
        }

    def trigger_evaluation_on_completion(self):
        """Trigger evaluation after agent completion"""
        # Import here to avoid circular imports
        import os
        from modules.evaluation.manager import EvaluationManager, TraceType

        # Check if evaluation is enabled
        if os.getenv("ENABLE_AUTO_EVALUATION", "true").lower() != "true":
            logger.debug("Auto-evaluation is disabled, skipping")
            return

        try:
            # Create evaluation manager for this operation
            eval_manager = EvaluationManager(operation_id=self.operation_id)

            # Register the main agent trace
            eval_manager.register_trace(
                trace_id=self.operation_id,
                trace_type=TraceType.MAIN_AGENT,
                name=f"Security Assessment - {self.operation_id}",
                session_id=self.operation_id,  # Langfuse uses session_id for lookup
            )

            # Run evaluation asynchronously
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            logger.info("Starting evaluation for operation %s", self.operation_id)
            results = loop.run_until_complete(eval_manager.evaluate_all_traces())

            if results:
                logger.info("Evaluation completed successfully: %d traces evaluated", len(results))
                # Emit evaluation complete event
                self._emit_ui_event(
                    {"type": "evaluation_complete", "operation_id": self.operation_id, "traces_evaluated": len(results)}
                )
            else:
                logger.warning("No evaluation results returned")

        except Exception as e:
            logger.error("Error during evaluation: %s", str(e), exc_info=True)
            # Don't fail the operation due to evaluation errors

    def wait_for_evaluation_completion(self, timeout=300):
        """Wait for evaluation to complete (compatibility method)"""
        # Since we run evaluation synchronously in trigger_evaluation_on_completion,
        # this is a no-op for compatibility
        logger.debug("Evaluation already completed or not running")


class ReactBridgeHook(HookProvider):
    """SDK Hook provider that emits events for React UI"""

    def __init__(self, emit_func=None, handler=None):
        self.emit_func = emit_func or self._default_emit
        self.start_times = {}
        self.handler = handler  # Reference to the main handler for tool result processing

    def _default_emit(self, event):
        """Delegate to main handler instead of duplicating events"""
        # Don't emit events directly - let the main SDKNativeHandler handle all emissions
        # This prevents duplicate events from hooks and callback handler
        if self.handler and hasattr(self.handler, "_emit_ui_event"):
            self.handler._emit_ui_event(event)
        # If no handler reference, do nothing to prevent duplication

    def register_hooks(self, registry: HookRegistry):
        """Register hooks for SDK events"""
        # Tool invocation hooks
        registry.add_callback(BeforeToolInvocationEvent, self.on_before_tool)
        registry.add_callback(AfterToolInvocationEvent, self.on_after_tool)

        # Model invocation hooks for streaming
        registry.add_callback(BeforeModelInvocationEvent, self.on_before_model)
        registry.add_callback(AfterModelInvocationEvent, self.on_after_model)

    def on_before_tool(self, event: BeforeToolInvocationEvent):
        """Handle before tool invocation - lifecycle event only"""
        if event.tool_use:
            tool_id = (
                getattr(event.tool_use, "toolUseId", None)
                or getattr(event.tool_use, "id", None)
                or str(id(event.tool_use))
            )
            self.start_times[tool_id] = time.time()

            # Only emit lifecycle events - let callback handler handle streaming
            tool_name = getattr(event.tool_use, "name", "unknown")
            tool_input = getattr(event.tool_use, "input", {})

            # Emit tool lifecycle event (not duplicate of callback handler)
            lifecycle_event = {
                "type": "tool_lifecycle",
                "event": "before_invocation",
                "tool_name": tool_name,
                "tool_id": tool_id,
                "metadata": {
                    "invocation_state": str(event.invocation_state) if hasattr(event, "invocation_state") else "unknown"
                },
            }
            self.emit_func(lifecycle_event)

    def on_after_tool(self, event: AfterToolInvocationEvent):
        """Handle after tool invocation - lifecycle event only"""
        if event.tool_use:
            tool_id = (
                getattr(event.tool_use, "toolUseId", None)
                or getattr(event.tool_use, "id", None)
                or str(id(event.tool_use))
            )
            tool_name = getattr(event.tool_use, "name", "unknown")

            # Calculate duration if we tracked start time
            duration = None
            if tool_id in self.start_times:
                duration = time.time() - self.start_times[tool_id]
                del self.start_times[tool_id]

            # Emit tool lifecycle completion event (not duplicate of callback handler)
            lifecycle_event = {
                "type": "tool_lifecycle",
                "event": "after_invocation",
                "tool_name": tool_name,
                "tool_id": tool_id,
                "duration": duration,
                "success": event.exception is None if hasattr(event, "exception") else True,
                "metadata": {
                    "has_result": event.result is not None if hasattr(event, "result") else False,
                    "exception": str(event.exception) if hasattr(event, "exception") and event.exception else None,
                },
            }
            self.emit_func(lifecycle_event)

    def on_before_model(self, event: BeforeModelInvocationEvent):
        """Handle before model invocation - lifecycle event only"""
        # Emit model lifecycle event (not streaming content)
        lifecycle_event = {
            "type": "model_lifecycle",
            "event": "before_invocation",
            "metadata": {"agent_id": str(id(event.agent)) if hasattr(event, "agent") and event.agent else "unknown"},
        }
        self.emit_func(lifecycle_event)

    def on_after_model(self, event: AfterModelInvocationEvent):
        """Handle after model invocation - lifecycle event only"""
        # Emit model lifecycle completion event
        lifecycle_event = {
            "type": "model_lifecycle",
            "event": "after_invocation",
            "success": event.exception is None if hasattr(event, "exception") else True,
            "metadata": {
                "stop_reason": (
                    event.stop_response.stop_reason
                    if hasattr(event, "stop_response")
                    and event.stop_response
                    and hasattr(event.stop_response, "stop_reason")
                    else None
                ),
                "exception": str(event.exception) if hasattr(event, "exception") and event.exception else None,
            },
        }
        self.emit_func(lifecycle_event)
