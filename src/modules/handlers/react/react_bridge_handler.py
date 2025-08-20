"""
React Bridge Handler - Integrates Strands SDK callbacks with React UI.

This handler extends the SDK's PrintingCallbackHandler to emit structured
events for the React terminal UI, providing real-time operation visibility.
"""

import json
import time
import logging
import os
from datetime import datetime
from typing import Dict, Any, List

from strands.handlers import PrintingCallbackHandler

from .tool_emitters import ToolEventEmitter
from ..output_interceptor import set_tool_execution_state, get_buffered_output
from ..events import EventEmitter, get_emitter

logger = logging.getLogger(__name__)


class ReactBridgeHandler(PrintingCallbackHandler):
    """
    Handler that bridges SDK callbacks to React UI events.

    This handler processes SDK callbacks and emits structured events that
    the React UI can display. It handles tool execution, reasoning text,
    metrics tracking, and operation state management.
    """

    def __init__(self, max_steps: int = 100, operation_id: str = None, model_id: str = None, swarm_model_id: str = None, emitter: EventEmitter = None, init_context: Dict[str, Any] = None):
        """
        Initialize the React bridge handler.

        Args:
            max_steps: Maximum allowed execution steps
            operation_id: Unique operation identifier
            model_id: Model ID for accurate pricing calculations
            swarm_model_id: Model ID to use for swarm agents
            emitter: Event emitter to use (defaults to stdout)
            init_context: Optional initialization context with rich operation details
        """
        super().__init__()
        
        # Operation configuration
        self.current_step = 0
        self.max_steps = max_steps
        self.operation_id = operation_id or f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize emitter with operation context
        self.emitter = emitter or get_emitter(operation_id=self.operation_id)
        self.start_time = time.time()
        self.model_id = model_id
        self.swarm_model_id = swarm_model_id or "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        self.init_context = init_context or {}
        
        # Metrics tracking
        self.memory_ops = 0
        self.evidence_count = 0
        # Track SDK metrics as authoritative source
        self.sdk_input_tokens = 0
        self.sdk_output_tokens = 0
        self.last_metrics_emit_time = time.time()
        self.last_metrics = None

        # Tool tracking
        self.last_tool_name = None
        self.last_tool_id = None
        self.announced_tools = set()
        self.tool_input_buffer = {}
        self.tools_used = set()
        # Track whether a tool invocation already emitted meaningful output to suppress redundant generic completions
        self.tool_use_output_emitted = {}

        # Reasoning buffer to prevent fragmentation
        self.reasoning_buffer = []
        self.last_reasoning_time = 0

        # Step header tracking
        self.pending_step_header = False

        # Operation state
        self._stop_tool_used = False
        self._report_generated = False

        # Swarm operation tracking
        self.in_swarm_operation = False
        self.swarm_agents = []
        self.current_swarm_agent = None
        self.swarm_handoff_count = 0
        # Track last emitted swarm signature to prevent duplicates
        self._last_swarm_signature = None
        # Track sub-agent steps separately
        self.swarm_agent_steps = {}  # {agent_name: current_step}
        self.swarm_max_iterations = 30  # Default max iterations for entire swarm
        self.swarm_iteration_count = 0  # Track total iterations across all agents

        # Initialize tool emitter
        self.tool_emitter = ToolEventEmitter(self._emit_ui_event)

        # Emit initial metrics
        self._emit_initial_metrics()

        # Emit operation initialization details if provided
        try:
            op_event = {
                "type": "operation_init",
                "operation_id": self.operation_id,
                "max_steps": self.max_steps,
                "model_id": self.model_id,
            }

            # Merge provided context
            if isinstance(self.init_context, dict):
                op_event.update(self.init_context)

            # Best-effort defaults for memory backend if not supplied
            memory_info = op_event.get("memory", {}) or {}
            if "backend" not in memory_info:
                if os.getenv("MEM0_API_KEY"):
                    memory_info["backend"] = "mem0_cloud"
                elif os.getenv("OPENSEARCH_HOST"):
                    memory_info["backend"] = "opensearch"
                else:
                    memory_info["backend"] = "faiss"
            op_event["memory"] = memory_info

            # UI mode hint
            if "ui_mode" not in op_event:
                op_event["ui_mode"] = "react" if os.getenv("__REACT_INK__") else "cli"

            self._emit_ui_event(op_event)
        except Exception as e:
            logger.debug("Failed to emit operation_init event: %s", e)

    def __call__(self, **kwargs):
        """
        Process SDK callbacks and emit appropriate UI events.

        This is the main entry point for all SDK callbacks. It routes
        different callback types to appropriate handlers.
        """
        # Debug log to verify handler is being called
        if kwargs:
            logger.debug("ReactBridgeHandler.__call__ invoked with keys: %s", list(kwargs.keys()))
        
        # Transform SDK events to UI events
        self._transform_sdk_event(kwargs)

    def _emit_ui_event(self, event: Dict[str, Any]) -> None:
        """
        Emit structured event for the React UI.

        All events are emitted with a specific format that the React UI
        can parse and display appropriately.
        """
        # Use the pluggable emitter - maintains backward compatibility
        # The emitter handles timestamp addition and protocol formatting
        self.emitter.emit(event)

    def _transform_sdk_event(self, kwargs: Dict[str, Any]) -> None:
        """
        Transform SDK events to UI events in a clean, maintainable way.

        This method acts as an adapter between the SDK callback format
        and our UI event format, preserving all existing UI functionality.
        """
        # Extract callback parameters
        reasoning_text = kwargs.get("reasoningText")
        data = kwargs.get("data", "")
        complete = kwargs.get("complete", False)
        current_tool_use = kwargs.get("current_tool_use")
        tool_result = kwargs.get("toolResult")
        message = kwargs.get("message")
        event_loop_metrics = kwargs.get("event_loop_metrics")

        # Handle AgentResult from SDK - this contains the actual metrics
        agent_result = kwargs.get("result")
        if agent_result and hasattr(agent_result, "metrics"):
            event_loop_metrics = agent_result.metrics

        # Process each type of SDK event

        # 1. Message events (for step tracking)
        if message and isinstance(message, dict):
            self._process_message(message)

        # 2. Reasoning text events
        if reasoning_text:
            self._accumulate_reasoning_text(reasoning_text)
            # Estimate tokens for metrics
            pass  # Token counting via SDK metrics

        # 3. Streaming data events
        elif data and not complete:
            pass  # Token counting via SDK metrics

        # 4. Tool announcement events
        if current_tool_use:
            self._process_tool_announcement(current_tool_use)

        # 5. Tool result events
        tool_result_processed = False
        if tool_result:
            self._process_tool_result_from_message(tool_result)
            tool_result_processed = True

        # Check alternative result keys (skip 'result' if it's an AgentResult with metrics)
        for alt_key in ["result", "tool_result", "execution_result", "response", "output"]:
            if alt_key in kwargs and kwargs[alt_key] is not None:
                result_data = kwargs[alt_key]

                # Skip if this is an AgentResult (already processed for metrics above)
                if alt_key == "result" and hasattr(result_data, "metrics"):
                    continue
                
                # Skip tool_result if we already processed it above
                if alt_key == "tool_result" and tool_result_processed:
                    continue

                if isinstance(result_data, str):
                    result_data = {"content": [{"text": result_data}], "status": "success"}
                self._process_tool_result_from_message(result_data)

        # 6. Completion events
        if complete or kwargs.get("is_final"):
            self._handle_completion()

        # 7. SDK metrics events
        if event_loop_metrics:
            self._process_metrics(event_loop_metrics)

        # 8. Try to get metrics from agent if available
        agent = kwargs.get("agent")
        if agent and hasattr(agent, "event_loop_metrics"):
            # Get metrics directly from the agent during operation
            usage = agent.event_loop_metrics.accumulated_usage
            if usage:
                self.sdk_input_tokens = usage.get("inputTokens", 0)
                self.sdk_output_tokens = usage.get("outputTokens", 0)

        # 9. Periodic metrics emission (every 2 seconds for more responsive updates)
        if time.time() - self.last_metrics_emit_time > 2:
            self._emit_estimated_metrics()
            self.last_metrics_emit_time = time.time()

    def _process_message(self, message: Dict[str, Any]) -> None:
        """Process message objects to track steps and extract content."""
        content = message.get("content", [])

        # Check if message contains tool usage
        has_tool_use = any(
            isinstance(block, dict) and (block.get("type") == "tool_use" or "toolUse" in block) for block in content
        )

        # Handle step progression
        if message.get("role") == "assistant":
            if has_tool_use:
                # Don't increment here - let tool announcement handle it
                self.pending_step_header = True
            else:
                # Pure reasoning step without tools
                self.current_step += 1

                # Check if step limit exceeded BEFORE emitting confusing header
                if self.current_step > self.max_steps:
                    from modules.handlers.base import StepLimitReached

                    raise StepLimitReached(f"Step limit exceeded: {self.current_step}/{self.max_steps}")

                # Only emit header if within step limits
                self._emit_step_header()

            # Count output tokens
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    pass  # Token counting via SDK metrics

        elif message.get("role") == "user":
            # Count input tokens
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    pass  # Token counting via SDK metrics

        # Process tool results in message content
        for block in content:
            if isinstance(block, dict):
                if "toolResult" in block:
                    self._process_tool_result_from_message(block["toolResult"])
                elif "toolResponse" in block:
                    self._process_tool_result_from_message(block["toolResponse"])
                elif block.get("type") == "tool_result":
                    self._process_tool_result_from_message(block)

    def _process_tool_announcement(self, tool_use: Dict[str, Any]) -> None:
        """Process tool usage announcements."""
        tool_name = tool_use.get("name", "")
        tool_id = tool_use.get("toolUseId", "")
        raw_input = tool_use.get("input", {})
        tool_input = self._parse_tool_input_from_stream(raw_input)

        # Emit reasoning for swarm agents regardless of tool announcement status
        if self.in_swarm_operation and self.reasoning_buffer:
            self._emit_accumulated_reasoning()
        
        # Only process new tools
        if tool_id and tool_id not in self.announced_tools:
            # Emit accumulated reasoning first (for non-swarm or if not already emitted)
            if not self.in_swarm_operation:
                self._emit_accumulated_reasoning()

            # Emit step header if pending or first tool
            if self.pending_step_header or (self.current_step == 0 and tool_id):
                if self.current_step == 0 or self.pending_step_header:
                    self.current_step += 1

                # Check if step limit exceeded BEFORE emitting confusing header
                if self.current_step > self.max_steps:
                    from modules.handlers.base import StepLimitReached

                    raise StepLimitReached(f"Step limit exceeded: {self.current_step}/{self.max_steps}")

                # Only emit header if within step limits
                self._emit_step_header()
                self.pending_step_header = False

            # Track tool
            self.announced_tools.add(tool_id)
            self.last_tool_name = tool_name
            self.last_tool_id = tool_id
            self.tools_used.add(tool_name)
            self.tool_input_buffer[tool_id] = tool_input

            # Emit tool_start ONLY if we have meaningful input; otherwise wait for streaming update
            has_meaningful_input = bool(tool_input) and tool_input != {} and self._is_valid_input(tool_input)
            if has_meaningful_input:
                # Suppress OutputInterceptor during tool execution
                set_tool_execution_state(True)
                
                # Add swarm context to tool_start events
                tool_event = {
                    "type": "tool_start", 
                    "tool_name": tool_name, 
                    "tool_input": tool_input
                }
                if self.in_swarm_operation and self.current_swarm_agent:
                    tool_event["swarm_agent"] = self.current_swarm_agent
                    tool_event["swarm_step"] = self.swarm_agent_steps.get(self.current_swarm_agent, 1)
                
                self._emit_ui_event(tool_event)

            # Emit tool-specific events (skip 'swarm' to avoid duplicate swarm_start emissions)
            if tool_input and self._is_valid_input(tool_input) and tool_name != "swarm":
                self.tool_emitter.emit_tool_specific_events(tool_name, tool_input)

            # Emit thinking animation for tool execution with start time for elapsed tracking
            current_time_ms = int(time.time() * 1000)
            self._emit_ui_event({"type": "thinking", "context": "tool_execution", "startTime": current_time_ms})

            # Handle swarm tracking (only here; ToolEventEmitter is skipped for 'swarm')
            if tool_name == "swarm":
                try:
                    self._track_swarm_start(tool_input)
                except Exception as e:
                    logger.warning("SWARM_START parsing failed: %s; input=%s", e, raw_input)
            elif tool_name == "handoff_to_agent":
                try:
                    # Only track handoff if we have a valid agent_name
                    if tool_input and tool_input.get("agent_name"):
                        self._track_agent_handoff(tool_input)
                    else:
                        logger.debug("Skipping handoff tracking - no agent_name in tool_input: %s", tool_input)
                except Exception as e:
                    logger.warning("AGENT_HANDOFF parsing failed: %s; input=%s", e, raw_input)
            elif tool_name == "complete_swarm_task":
                self._track_swarm_complete()
            elif tool_name == "stop":
                self._stop_tool_used = True

        # Handle streaming updates - buffer and emit ONLY when complete
        elif tool_id in self.announced_tools and raw_input:
            old_input = self.tool_input_buffer.get(tool_id, {})
            new_input = self._parse_tool_input_from_stream(raw_input)

            # Update buffer with latest input
            self.tool_input_buffer[tool_id] = new_input

            # Check if we have complete, usable input (not partial JSON)
            is_partial_json = (
                isinstance(new_input, dict)
                and len(new_input) == 1
                and "value" in new_input
                and isinstance(new_input.get("value"), str)
            )

            # Don't emit anything if we have partial JSON
            if is_partial_json:
                return

            # Check if this is a meaningful update from empty/partial to complete
            was_empty_or_partial = (
                not old_input
                or old_input == {}
                or (isinstance(old_input, dict) and len(old_input) == 1 and "value" in old_input)
            )

            has_complete_content = new_input and new_input != {} and not is_partial_json

            # Only emit when we transition to complete content
            if was_empty_or_partial and has_complete_content:
                # Suppress OutputInterceptor during tool execution
                set_tool_execution_state(True)
                
                # Re-emit tool_start with the complete input
                self._emit_ui_event({"type": "tool_start", "tool_name": self.last_tool_name, "tool_input": new_input})

                # Emit tool-specific events now that we have the real input (skip 'swarm')
                if self._is_valid_input(new_input) and self.last_tool_name != "swarm":
                    self.tool_emitter.emit_tool_specific_events(self.last_tool_name, new_input)

                # Handle swarm tracking with real input (single source of truth)
                if self.last_tool_name == "swarm":
                    try:
                        self._track_swarm_start(new_input)
                    except Exception as e:
                        logger.warning("SWARM_START streaming update parsing failed: %s; input=%s", e, raw_input)

    def _process_tool_result_from_message(self, tool_result: Any) -> None:
        """Process tool execution results."""
        # Clear tool execution flag and get buffered output
        set_tool_execution_state(False)
        buffered_output = get_buffered_output()
        
        # Stop thinking animation
        self._emit_ui_event({"type": "thinking_end"})

        # Convert result to dict format
        if hasattr(tool_result, "__dict__"):
            tool_result_dict = tool_result.__dict__
        elif isinstance(tool_result, dict):
            tool_result_dict = tool_result
        else:
            tool_result_dict = {"content": [{"text": str(tool_result)}], "status": "success"}
        
        # Debug logging for shell tool results
        if self.last_tool_name == "shell":
            logger.debug("Shell tool result structure: %s", tool_result_dict.keys() if isinstance(tool_result_dict, dict) else type(tool_result_dict))
            if "content" in tool_result_dict:
                logger.debug("Shell content items: %d", len(tool_result_dict.get("content", [])))
                for i, item in enumerate(tool_result_dict.get("content", [])[:3]):  # Log first 3 items
                    logger.debug("Content item %d: %s", i, item if isinstance(item, dict) else str(item)[:100])

        # Extract result details
        content_items = tool_result_dict.get("content", [])
        status = tool_result_dict.get("status", "success")
        tool_use_id = tool_result_dict.get("toolUseId") or self.last_tool_id

        # Get original tool input
        tool_input = self.tool_input_buffer.get(tool_use_id, {})

        # Emit tool completion event
        success = status != "error"
        self._emit_ui_event({"type": "tool_invocation_end", "success": success, "tool_name": self.last_tool_name})
        
        # Exit swarm mode when swarm tool completes
        # This handles cases where swarm hits max_iterations without calling complete_swarm_task
        if self.last_tool_name == "swarm" and self.in_swarm_operation:
            logger.info("Swarm tool completed, exiting swarm mode (iterations: %d)", self.swarm_iteration_count)
            self.in_swarm_operation = False
            self.swarm_agents = []
            self.current_swarm_agent = None

        # Handle errors with tool-specific processing
        if status == "error":
            error_text = ""
            for item in content_items:
                if isinstance(item, dict) and "text" in item:
                    error_text += item["text"] + "\n"
            
            if error_text.strip():
                # Combine buffered output with error text for single emission
                combined_output = ""
                if buffered_output:
                    combined_output = buffered_output + "\n"
                
                # Process errors through tool-specific handlers for cleaner display
                if self.last_tool_name == "shell":
                    clean_error = self._parse_shell_tool_output(error_text.strip())
                    combined_output += clean_error
                elif self.last_tool_name == "http_request":
                    clean_error = self._parse_http_tool_output(error_text.strip())
                    combined_output += clean_error
                else:
                    combined_output += error_text.strip()
                
                # Emit single consolidated output event
                self._emit_ui_event({
                    "type": "output", 
                    "content": combined_output.strip(),
                    "metadata": {"fromToolBuffer": True, "tool": self.last_tool_name}
                })
                
                # Mark that we've emitted output for this tool invocation
                if tool_use_id:
                    self.tool_use_output_emitted[tool_use_id] = True
            return

        # Extract output text
        output_text = self._extract_output_text(content_items)
        
        # Check for buffered output from tool execution
        if buffered_output:
            # Emit buffered output to avoid duplicates
            # Add metadata for proper UI handling
            self._emit_ui_event({
                "type": "output", 
                "content": buffered_output,
                "metadata": {"fromToolBuffer": True, "tool": self.last_tool_name}
            })
            
            # Mark that we've emitted output for this tool invocation
            if tool_use_id:
                self.tool_use_output_emitted[tool_use_id] = True
            
            # Return to prevent duplicate output
            return

        # If we reach here, there was no buffered output, so process normally
        # But first check if output was already emitted to prevent duplicates
        if tool_use_id and self.tool_use_output_emitted.get(tool_use_id, False):
            return  # Skip - output already emitted from error handling or buffered output
        
        # Special handling for shell tool results
        if self.last_tool_name == "shell":
            self._process_shell_output(output_text, content_items, status, tool_use_id)
        elif self.last_tool_name == "http_request":
            self._process_http_output(output_text, content_items, status, tool_use_id)
        else:
            # Emit output or status
            if output_text.strip():
                # Check if we already processed this exact output
                output_key = f"{tool_use_id or self.last_tool_id}:{hash(output_text.strip())}"
                if hasattr(self, '_processed_outputs') and output_key in self._processed_outputs:
                    return  # Skip duplicate output
                
                # Initialize tracking if not exists
                if not hasattr(self, '_processed_outputs'):
                    self._processed_outputs = set()
                
                # Agent tracking is handled through explicit handoff events only
                # No text parsing needed - it's unreliable and causes false positives

                # Mark this output as processed
                self._processed_outputs.add(output_key)
                # Mark meaningful output for this tool invocation
                if tool_use_id:
                    self.tool_use_output_emitted[tool_use_id] = True
                # Mark all tool outputs with metadata to prevent truncation
                self._emit_ui_event({
                    "type": "output", 
                    "content": output_text.strip(),
                    "metadata": {"fromToolBuffer": True, "tool": self.last_tool_name}
                })

        # Update metrics
        if self.last_tool_name == "mem0_memory":
            self.memory_ops += 1
            action = tool_input.get("action", "unknown") if isinstance(tool_input, dict) else "unknown"
            if action == "store":
                self.evidence_count += 1

    def _parse_shell_tool_output(self, output_text: str) -> str:
        """Parse and clean shell tool output for display - show all content."""
        if not output_text:
            return ""
        
        # Check if this output contains individual command echoes that duplicate
        # what we already show in the tool invocation display
        # The pattern is lines that start with the tree character ⎿ followed by a command
        lines = output_text.split('\n')
        filtered_lines = []
        for line in lines:
            # Skip lines that are just command echoes (they start with ⎿)
            if line.strip().startswith('⎿'):
                continue
            filtered_lines.append(line)
        
        # Rejoin the filtered output
        output_text = '\n'.join(filtered_lines)
        
        # Filter SDK execution wrapper to prevent duplicate display
        if "Execution Summary:" in output_text and "Total commands:" in output_text:
            # Extract command info and actual output/error content
            lines = output_text.split('\n')
            command = ""
            actual_output = []
            in_output_section = False
            capture_error = False
            status = ""
            exit_code = ""
            
            for line in lines:
                if line.startswith("Command:"):
                    command = line[8:].strip()
                elif line.startswith("Status:"):
                    status = line[7:].strip()
                    in_output_section = False
                    capture_error = False
                elif line.startswith("Exit Code:"):
                    exit_code = line[10:].strip()
                elif line.startswith("Output:"):
                    in_output_section = True
                    # Check for inline content
                    content_after = line[7:].strip()
                    if content_after:
                        actual_output.append(content_after)
                    continue
                elif line.startswith("Error:"):
                    in_output_section = False
                    capture_error = True
                    # Check for inline error message
                    error_msg = line[6:].strip()
                    if error_msg:
                        actual_output.append(f"Error: {error_msg}")
                    continue
                elif line.startswith("Execution Summary:") or line.startswith("Total commands:"):
                    continue  # Skip wrapper headers
                elif in_output_section:
                    actual_output.append(line)
                elif capture_error and line.strip():
                    actual_output.append(line)
            
            # If we have extracted content, return it
            if actual_output:
                return '\n'.join(actual_output).strip()
            
            # If no output/error captured but we have command info, provide context
            # Also extract any other information from the full text that might be useful
            if command:
                # Try to extract any additional info from the original text
                additional_info = []
                for line in lines:
                    # Skip already processed lines and wrapper lines
                    if (not line.startswith("Execution Summary:") and 
                        not line.startswith("Total commands:") and
                        not line.startswith("Command:") and
                        not line.startswith("Status:") and
                        not line.startswith("Exit Code:") and
                        not line.startswith("Output:") and
                        not line.startswith("Error:") and
                        not line.startswith("Successful:") and
                        not line.startswith("Failed:") and
                        line.strip()):
                        additional_info.append(line)
                
                if additional_info:
                    return "\n".join(additional_info)
                elif status == "error" and exit_code:
                    return f"Command failed: {command}\nExit code: {exit_code}\n(No output captured)"
                elif status == "success":
                    return f"Command succeeded: {command}\n(No output)"
                else:
                    return f"Command: {command}\nStatus: {status or 'unknown'}"
        
        # Return full output as fallback
        return output_text.strip()
    
    def _parse_http_tool_output(self, output_text: str) -> str:
        """Parse and clean HTTP tool output for display - show all content."""
        if not output_text:
            return ""
        
        # Return full HTTP output without truncation
        return output_text.strip()

    def _process_shell_output(self, output_text: str, _content_items: List, _status: str, tool_use_id: str = None) -> None:
        """Process shell command output with intelligent parsing and clean display."""
        # Skip if output was already emitted
        if tool_use_id and self.tool_use_output_emitted.get(tool_use_id, False):
            return
            
        if not output_text.strip():
            # Only emit generic completion if no prior meaningful output for this invocation
            self._emit_ui_event({
                "type": "output", 
                "content": "Command completed",
                "metadata": {"fromToolBuffer": True, "tool": self.last_tool_name}
            })
            if tool_use_id:
                self.tool_use_output_emitted[tool_use_id] = True
            return

        # Check if we already processed this exact output
        output_key = f"{tool_use_id or self.last_tool_id}:{hash(output_text.strip())}"
        if hasattr(self, '_processed_outputs') and output_key in self._processed_outputs:
            return  # Skip duplicate output
        
        # Initialize tracking if not exists
        if not hasattr(self, '_processed_outputs'):
            self._processed_outputs = set()
        
        # Parse and clean shell tool output
        clean_output = self._parse_shell_tool_output(output_text.strip())
        
        # Agent tracking handled through explicit events, not text parsing
        
        # Mark this output as processed
        self._processed_outputs.add(output_key)
        if tool_use_id:
            self.tool_use_output_emitted[tool_use_id] = True
        # Always mark shell output with metadata to prevent truncation
        self._emit_ui_event({
            "type": "output", 
            "content": clean_output,
            "metadata": {"fromToolBuffer": True, "tool": "shell"}
        })

    def _process_http_output(self, output_text: str, _content_items: List, _status: str, tool_use_id: str = None) -> None:
        """Process HTTP request output with intelligent parsing and clean display."""
        # Skip if output was already emitted
        if tool_use_id and self.tool_use_output_emitted.get(tool_use_id, False):
            return
            
        if not output_text.strip():
            # Only emit generic completion if no prior meaningful output for this invocation
            self._emit_ui_event({
                "type": "output", 
                "content": "Request completed",
                "metadata": {"fromToolBuffer": True, "tool": self.last_tool_name}
            })
            if tool_use_id:
                self.tool_use_output_emitted[tool_use_id] = True
            return

        # Check if we already processed this exact output
        output_key = f"{tool_use_id or self.last_tool_id}:{hash(output_text.strip())}"
        if hasattr(self, '_processed_outputs') and output_key in self._processed_outputs:
            return  # Skip duplicate output
        
        # Initialize tracking if not exists
        if not hasattr(self, '_processed_outputs'):
            self._processed_outputs = set()

        # Parse and clean HTTP tool output
        clean_output = self._parse_http_tool_output(output_text.strip())
        
        # Agent tracking handled through explicit events, not text parsing
        
        # Mark this output as processed
        self._processed_outputs.add(output_key)
        if tool_use_id:
            self.tool_use_output_emitted[tool_use_id] = True
        # Always mark HTTP output with metadata to prevent truncation
        self._emit_ui_event({
            "type": "output",
            "content": clean_output,
            "metadata": {"fromToolBuffer": True, "tool": "http_request"}
        })

    def _accumulate_reasoning_text(self, text: str) -> None:
        """Accumulate reasoning text to prevent fragmentation."""
        if not text or text.strip().lower() == "reasoning":
            return

        cleaned_text = text.strip()
        if cleaned_text:
            # Handle spacing between fragments
            if self.reasoning_buffer:
                last_char = self.reasoning_buffer[-1][-1] if self.reasoning_buffer else ""
                first_char = cleaned_text[0]

                # Add space if needed
                if (
                    last_char.isalnum()
                    and first_char.isalnum()
                    or last_char.isalnum()
                    and first_char in ".!?:;,"
                    or last_char in ".!?:;,"
                    and first_char.isalnum()
                ):
                    self.reasoning_buffer.append(" ")

            self.reasoning_buffer.append(cleaned_text)
        self.last_reasoning_time = time.time()

    def _emit_accumulated_reasoning(self) -> None:
        """Emit accumulated reasoning text as a complete block."""
        if self.reasoning_buffer:
            combined_reasoning = "".join(self.reasoning_buffer).strip()

            if combined_reasoning:
                # Add agent prefix if in swarm
                if self.in_swarm_operation and self.current_swarm_agent:
                    agent_prefix = f"[{self.current_swarm_agent.upper()}] "
                    combined_reasoning = agent_prefix + combined_reasoning

                self._emit_ui_event({"type": "reasoning", "content": combined_reasoning})

            self.reasoning_buffer = []

    def _emit_step_header(self) -> None:
        """Emit step header with current progress."""
        event = {
            "type": "step_header",
            "step": self.current_step,
            "maxSteps": self.max_steps,
            "operation": self.operation_id,
            "duration": self._format_duration(time.time() - self.start_time),
        }

        # Add swarm agent information if in swarm operation
        if self.in_swarm_operation:
            event["is_swarm_operation"] = True
            if self.current_swarm_agent:
                event["swarm_agent"] = self.current_swarm_agent
                # Track and increment sub-agent steps
                if self.current_swarm_agent not in self.swarm_agent_steps:
                    self.swarm_agent_steps[self.current_swarm_agent] = 1
                else:
                    self.swarm_agent_steps[self.current_swarm_agent] += 1
                
                # Increment total iteration count
                self.swarm_iteration_count += 1
                
                event["swarm_sub_step"] = self.swarm_agent_steps[self.current_swarm_agent]
                event["swarm_total_iterations"] = self.swarm_iteration_count
                event["swarm_max_iterations"] = self.swarm_max_iterations
            else:
                event["swarm_context"] = "Multi-Agent Operation"

        self._emit_ui_event(event)

    def _emit_initial_metrics(self) -> None:
        """Emit initial metrics on startup."""
        self._emit_ui_event(
            {
                "type": "metrics_update",
                "metrics": {"tokens": 0, "cost": 0.0, "duration": "0s", "memoryOps": 0, "evidence": 0},
            }
        )

    def _emit_estimated_metrics(self) -> None:
        """Emit metrics based on SDK token counts."""
        total_tokens = self.sdk_input_tokens + self.sdk_output_tokens

        # Report both individual and total token counts for compatibility
        # Cost calculation is handled by the React app using config values
        self._emit_ui_event(
            {
                "type": "metrics_update",
                "metrics": {
                    "tokens": total_tokens,  # For Footer compatibility
                    "inputTokens": self.sdk_input_tokens,
                    "outputTokens": self.sdk_output_tokens,
                    "totalTokens": total_tokens,
                    "duration": self._format_duration(time.time() - self.start_time),
                    "memoryOps": self.memory_ops,
                    "evidence": self.evidence_count,
                },
            }
        )

    def _process_metrics(self, event_loop_metrics: Dict[str, Any]) -> None:
        """Process SDK metrics and emit updates."""
        self.last_metrics = event_loop_metrics
        usage = event_loop_metrics.accumulated_usage

        # Update SDK token counts as authoritative source
        self.sdk_input_tokens = usage.get("inputTokens", 0)
        self.sdk_output_tokens = usage.get("outputTokens", 0)
        total_tokens = self.sdk_input_tokens + self.sdk_output_tokens

        # Report both individual and total token counts for compatibility
        # Cost calculation is handled by the React app using config values
        self._emit_ui_event(
            {
                "type": "metrics_update",
                "metrics": {
                    "tokens": total_tokens,  # For Footer compatibility
                    "inputTokens": self.sdk_input_tokens,
                    "outputTokens": self.sdk_output_tokens,
                    "totalTokens": total_tokens,
                    "duration": self._format_duration(time.time() - self.start_time),
                    "memoryOps": self.memory_ops,
                    "evidence": self.evidence_count,
                },
            }
        )

    def _handle_completion(self) -> None:
        """Handle completion events."""
        self._emit_accumulated_reasoning()

        if self.last_tool_name and not hasattr(self, "_last_tool_had_result"):
            self._emit_ui_event({"type": "thinking_end"})
            self._emit_ui_event({
                "type": "output", 
                "content": "Command completed successfully",
                "metadata": {"fromToolBuffer": True, "tool": self.last_tool_name}
            })

    def _track_swarm_start(self, tool_input: Dict[str, Any]) -> None:
        """Track swarm operation start. Emit a single, well-formed swarm_start.
        
        Agent Tracking Flow:
        1. Initial agent is set from the agents list (first agent)
        2. Agent changes are tracked ONLY through explicit handoff_to_agent events
        3. No text parsing is used - it's unreliable and causes false positives
        4. The current_swarm_agent is displayed in step headers and events
        """
        if not isinstance(tool_input, dict):
            tool_input = {}
        agents = tool_input.get("agents", [])
        task = tool_input.get("task", "")
        

        # Build agent names and details lists
        agent_names: List[str] = []
        agent_details: List[Dict[str, Any]] = []
        
        if isinstance(agents, list):
            for i, agent in enumerate(agents):
                if isinstance(agent, dict):
                    name = agent.get("name") or agent.get("role") or f"agent_{i+1}"
                    system_prompt = agent.get("system_prompt", "")
                    tools = agent.get("tools", [])
                    
                    agent_names.append(name)
                    # Extract model info from model_settings or use parent config
                    model_settings = agent.get("model_settings", {})
                    model_provider = agent.get("model_provider", "bedrock")
                    
                    # Always use our configured swarm model, override any agent-specific model
                    # This ensures all swarm agents use the model configured in the UI
                    model_id = self.swarm_model_id
                    
                    agent_details.append({
                        "name": name,
                        "role": system_prompt,  # Full system prompt as role
                        "system_prompt": system_prompt,  # Keep for compatibility
                        "tools": tools if isinstance(tools, list) else [],
                        "model_provider": model_provider,
                        "model_id": model_id,
                        "temperature": model_settings.get("params", {}).get("temperature", 0.7)
                    })
                elif isinstance(agent, str):
                    agent_names.append(agent)
                    agent_details.append({
                        "name": agent,
                        "system_prompt": "",
                        "tools": [],
                        "model_provider": "default",
                        "model_id": "default"
                    })

        # Skip emitting if we have no meaningful content yet (pre-stream empty input)
        if not agent_names and not task:
            return
            
        # Skip emitting if agents list is empty but task exists (partial/empty agent data)
        if task and not agent_names:
            logger.debug("Skipping swarm_start emission - task exists but no agents yet")
            return

        # Compute signature to dedupe repeated emissions
        signature = json.dumps({"agents": agent_names, "task": task}, sort_keys=True)
        if self._last_swarm_signature == signature:
            return

        # Update state
        self.in_swarm_operation = True
        self.swarm_agents = agent_names
        self.current_swarm_agent = agent_names[0] if agent_names else None
        self.swarm_handoff_count = 0
        # Reset sub-agent step tracking for new swarm
        self.swarm_agent_steps = {}
        
        # Initialize step counter for first agent and iteration tracking
        if self.current_swarm_agent:
            self.swarm_agent_steps[self.current_swarm_agent] = 0
        
        # Set max iterations from tool input
        self.swarm_max_iterations = tool_input.get("max_iterations", 30)
        self.swarm_iteration_count = 0

        # Emit a single swarm_start UI event with full agent details
        try:
            event = {
                "type": "swarm_start",
                "agent_names": agent_names,
                "agent_count": len(agent_names),
                "agent_details": agent_details,
                "task": task,
                "max_handoffs": tool_input.get("max_handoffs", 25),
                "max_iterations": tool_input.get("max_iterations", 30),
                "timeout": tool_input.get("execution_timeout", 1200),
            }
            self._emit_ui_event(event)
        except Exception as e:
            logger.warning("Failed to emit swarm_start: %s", e)

    def _track_agent_handoff(self, tool_input: Dict[str, Any]) -> None:
        """Track agent handoffs in swarm."""
        if self.in_swarm_operation:
            if not isinstance(tool_input, dict):
                tool_input = self._parse_tool_input_from_stream(tool_input)
                if not isinstance(tool_input, dict):
                    tool_input = {}
            agent_name = tool_input.get("agent_name", "")
            message = tool_input.get("message", "")
            message_preview = message[:100] + "..." if len(message) > 100 else message

            from_agent = self.current_swarm_agent or "unknown"
            # Only update current_swarm_agent if we have a valid agent_name
            if agent_name:
                self.current_swarm_agent = agent_name
                self.swarm_handoff_count += 1
                # Initialize step count for new agent if not exists
                if agent_name not in self.swarm_agent_steps:
                    self.swarm_agent_steps[agent_name] = 0
            else:
                # Log warning but don't break the flow
                logger.warning("Handoff with empty agent_name from %s", from_agent)

            self._emit_ui_event(
                {
                    "type": "swarm_handoff",
                    "from_agent": from_agent,
                    "to_agent": agent_name,
                    "message": message_preview,
                }
            )

            # Mark subsequent steps clearly by emitting a new step header on handoff
            try:
                self.current_step += 1
                # Guard against step limit overflow similar to initial header emission
                if self.current_step <= self.max_steps:
                    self._emit_step_header()
                else:
                    from modules.handlers.base import StepLimitReached

                    raise StepLimitReached(f"Step limit exceeded: {self.current_step}/{self.max_steps}")
            except Exception as _:
                # Do not break stream on header failure
                pass

    def _track_swarm_complete(self) -> None:
        """Track swarm completion with enhanced metrics."""
        if self.in_swarm_operation:
            final_agent = self.current_swarm_agent or "unknown"
            duration = time.time() - self.start_time
            
            # Calculate agent completion stats
            completed_agents = [agent for agent in self.swarm_agents if agent in self.swarm_agent_steps]
            
            self._emit_ui_event(
                {
                    "type": "swarm_complete",
                    "final_agent": final_agent,
                    "execution_count": self.swarm_handoff_count + 1,
                    "duration": f"{duration:.1f}s",
                    "total_tokens": self.sdk_input_tokens + self.sdk_output_tokens,
                    "completed_agents": completed_agents,
                    "total_agents": len(self.swarm_agents),
                }
            )

            # Reset swarm state
            self.in_swarm_operation = False
            self.swarm_agents = []
            self.current_swarm_agent = None
            self.swarm_handoff_count = 0


    def _is_valid_input(self, tool_input: Any) -> bool:
        """Check if tool input is valid."""
        # Allow empty dicts as valid - tools may have no required parameters
        return isinstance(tool_input, (dict, str))

    def _parse_tool_input_from_stream(self, tool_input: Any) -> Dict[str, Any]:
        """Parse tool input from SDK streaming format into usable dictionary.

        The Strands SDK sends tool inputs through multiple streaming updates:
        1. Initial: Empty dict {}
        2. Streaming: Wrapped partial JSON {"value": "{\"task\": \"..."}
        3. Complete: Full JSON that can be unwrapped and parsed

        This function handles all these cases elegantly:
        - Unwraps nested JSON strings from streaming updates
        - Preserves partial JSON for buffering
        - Returns clean dict for tool consumption

        Args:
            tool_input: Raw input from SDK (dict, str, or other)

        Returns:
            Dict with parsed tool parameters or wrapped value
        """
        # Handle None or empty input
        if not tool_input:
            return {}

        # Handle dictionary input (most common case)
        if isinstance(tool_input, dict):
            # Check for SDK streaming pattern: {"value": "json_string"}
            if len(tool_input) == 1 and "value" in tool_input:
                value = tool_input["value"]

                # If value is a JSON string, try to parse it
                if isinstance(value, str):
                    stripped = value.strip()

                    # Check if it looks like JSON
                    if stripped and (stripped[0] in "{[" and stripped[-1] in "}]"):
                        try:
                            # Attempt to parse complete JSON
                            parsed = json.loads(stripped)
                            # Return parsed dict directly, or wrap non-dict values
                            return parsed if isinstance(parsed, dict) else {"value": parsed}
                        except json.JSONDecodeError:
                            # Partial JSON - keep wrapped for buffering
                            return tool_input

                    # Non-JSON string value
                    return tool_input

            # Regular dict - return as-is
            return tool_input

        # Handle string input (less common)
        if isinstance(tool_input, str):
            stripped = tool_input.strip()
            if not stripped:
                return {}

            # Try to parse as JSON
            try:
                parsed = json.loads(stripped)
                return parsed if isinstance(parsed, dict) else {"value": parsed}
            except json.JSONDecodeError:
                # Plain string - wrap in value key
                return {"value": stripped}

        # Fallback for unexpected types
        return {"value": str(tool_input)} if tool_input else {}

    def _extract_output_text(self, content_items: List[Any]) -> str:
        """Extract text from content items, handling all possible formats."""
        output_text = ""
        for item in content_items:
            if isinstance(item, dict):
                # Extract text from various possible keys
                if "text" in item:
                    output_text += item["text"]
                elif "json" in item:
                    output_text += json.dumps(item["json"], indent=2)
                elif "content" in item:
                    output_text += str(item["content"])
                elif "output" in item:
                    output_text += str(item["output"])
                elif "result" in item:
                    output_text += str(item["result"])
                elif "message" in item:
                    output_text += str(item["message"])
                elif "data" in item:
                    output_text += str(item["data"])
                else:
                    # If dict has no recognized keys, convert entire dict to string
                    output_text += json.dumps(item, indent=2)
            elif isinstance(item, str):
                output_text += item
            else:
                output_text += str(item)
        return output_text

    def _format_duration(self, seconds: float) -> str:
        """Format duration for human-readable display."""
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

    # Report generation methods
    def ensure_report_generated(self, agent, target: str, objective: str, module: str = None) -> None:
        """Ensure report is generated only once."""
        if not self._report_generated:
            self.generate_final_report(agent, target, objective, module)

    def generate_final_report(self, agent, target: str, objective: str, module: str = None) -> None:
        """Generate final security assessment report."""
        if self._report_generated:
            return

        try:
            self._report_generated = True
            # Import report generator function (not a tool, called directly by handler)
            from modules.handlers.report_generator import generate_security_report

            # Emit completion header before generating report
            self._emit_ui_event(
                {
                    "type": "step_header",
                    "step": "FINAL REPORT",
                    "maxSteps": self.max_steps,
                    "operation": self.operation_id,
                    "duration": self._format_duration(time.time() - self.start_time),
                }
            )

            # Determine provider from agent model
            provider = "bedrock"
            if hasattr(agent, "model"):
                model_class = agent.model.__class__.__name__
                if "Bedrock" in model_class:
                    provider = "bedrock"
                elif "Ollama" in model_class:
                    provider = "ollama"
                elif "LiteLLM" in model_class:
                    provider = "litellm"

            self._emit_ui_event(
                {"type": "output", "content": "\n◆ Generating comprehensive security assessment report..."}
            )

            # Prepare config data for report generation
            config_data = json.dumps({
                "steps_executed": self.current_step,
                "tools_used": list(self.tools_used),
                "provider": provider,
                "module": module
            })
            
            report_content = generate_security_report(
                target=target,
                objective=objective,
                operation_id=self.operation_id,
                config_data=config_data
            )

            if report_content and not report_content.startswith("Error:"):
                # Save report to file first
                try:
                    from modules.handlers.utils import sanitize_target_name, get_output_path
                    from pathlib import Path

                    target_name = sanitize_target_name(target)
                    output_dir = get_output_path(target_name, self.operation_id, "", "./outputs")

                    # Create output directory if it doesn't exist
                    Path(output_dir).mkdir(parents=True, exist_ok=True)

                    # Save report as markdown file
                    report_path = os.path.join(output_dir, "security_assessment_report.md")
                    with open(report_path, "w", encoding="utf-8") as f:
                        f.write(report_content)

                    # Emit the full report content to the UI
                    self._emit_ui_event(
                        {
                            "type": "report_content",
                            "content": report_content
                        }
                    )

                    # Also emit file path information for reference
                    self._emit_ui_event(
                        {
                            "type": "output",
                            "content": f"\n{'━'*80}\n\nASSESSMENT COMPLETE\n\nREPORT ALSO SAVED TO:\n  • {report_path}\n\nMEMORY STORED IN:\n  • {output_dir}/memory/\n\nOPERATION LOGS:\n  • {os.path.join(output_dir, 'cyber_operations.log')}\n\n{'━'*80}\n",
                        }
                    )

                    # Emit a completion event for clean UI transition
                    self._emit_ui_event(
                        {"type": "assessment_complete", "operation_id": self.operation_id, "report_path": report_path}
                    )

                    logger.info("Report saved to %s", report_path)

                except Exception as save_error:
                    logger.warning("Could not save report to file: %s", save_error)
                    self._emit_ui_event(
                        {"type": "output", "content": f"\n⚠️ Note: Report could not be saved to file: {save_error}"}
                    )
            else:
                self._emit_ui_event({"type": "error", "content": f"Failed to generate report: {report_content}"})

        except Exception as e:
            logger.error("Error generating final report: %s", e)
            self._emit_ui_event({"type": "error", "content": f"Error generating report: {str(e)}"})

    # Evaluation methods
    def trigger_evaluation_on_completion(self) -> None:
        """Trigger evaluation after operation completion."""
        from modules.evaluation.manager import EvaluationManager, TraceType

        verbose_eval = os.getenv("VERBOSE", "false").lower() == "true"

        if verbose_eval:
            logger.info("EVAL_DEBUG: trigger_evaluation_on_completion called for operation %s", self.operation_id)

        # Check if observability is enabled first - evaluation requires Langfuse infrastructure
        if os.getenv("ENABLE_OBSERVABILITY", "false").lower() != "true":
            logger.debug("Observability is disabled - skipping evaluation (requires Langfuse)")
            if verbose_eval:
                logger.info("EVAL_DEBUG: Skipping evaluation - observability disabled")
            return

        # Default evaluation to same setting as observability
        default_evaluation = os.getenv("ENABLE_OBSERVABILITY", "false")
        if os.getenv("ENABLE_AUTO_EVALUATION", default_evaluation).lower() != "true":
            logger.debug("Auto-evaluation is disabled, skipping")
            if verbose_eval:
                logger.info("EVAL_DEBUG: Auto-evaluation disabled via ENABLE_AUTO_EVALUATION=false")
            return

        try:
            if verbose_eval:
                logger.info("EVAL_DEBUG: Starting evaluation process for operation %s", self.operation_id)

            eval_manager = EvaluationManager(operation_id=self.operation_id)

            eval_manager.register_trace(
                trace_id=self.operation_id,
                trace_type=TraceType.MAIN_AGENT,
                name=f"Security Assessment - {self.operation_id}",
                session_id=self.operation_id,
            )

            if verbose_eval:
                logger.info("EVAL_DEBUG: Registered trace for evaluation")

            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            logger.info("Starting evaluation for operation %s", self.operation_id)
            if verbose_eval:
                logger.info("EVAL_DEBUG: Starting async evaluation loop")

            results = loop.run_until_complete(eval_manager.evaluate_all_traces())

            if results:
                logger.info("Evaluation completed successfully: %d traces evaluated", len(results))
                if verbose_eval:
                    logger.info("EVAL_DEBUG: Evaluation results: %s", results)
                self._emit_ui_event(
                    {"type": "evaluation_complete", "operation_id": self.operation_id, "traces_evaluated": len(results)}
                )
            else:
                logger.warning("No evaluation results returned")
                if verbose_eval:
                    logger.info("EVAL_DEBUG: No evaluation results - check trace finding and metric evaluation")

        except Exception as e:
            logger.warning("Evaluation failed but continuing operation: %s", str(e))
            if verbose_eval:
                logger.error("EVAL_DEBUG: Full evaluation exception details", exc_info=True)
            # Don't re-raise the exception - just log and continue

    def wait_for_evaluation_completion(self, _timeout: int = 300) -> None:
        """Wait for evaluation to complete (no-op for compatibility)."""
        logger.debug("Evaluation already completed or not running")

    def get_evidence_summary(self) -> List[str]:
        """Get a summary of key evidence collected.

        Returns:
            List of evidence summary strings
        """
        # For React bridge handler, return empty list as placeholder
        # Real evidence would come from memory/findings analysis
        return []

    # Property methods for compatibility
    @property
    def state(self):
        """Mock state object for compatibility."""

        class MockState:
            report_generated = self._report_generated
            stop_tool_used = self._stop_tool_used
            step_limit_reached = self.current_step >= self.max_steps

        return MockState()

    def should_stop(self) -> bool:
        """Check if execution should stop."""
        return self._stop_tool_used or (self.current_step >= self.max_steps)

    def has_reached_limit(self) -> bool:
        """Check if step limit reached."""
        return self.current_step >= self.max_steps

    @property
    def stop_tool_used(self) -> bool:
        """Check if stop tool was used."""
        return self._stop_tool_used

    @property
    def report_generated(self) -> bool:
        """Check if report was generated."""
        return self._report_generated

    def get_summary(self) -> Dict[str, Any]:
        """Get operation summary for reporting."""
        return {
            "total_steps": self.current_step,
            "tools_created": len(self.tools_used),
            "evidence_collected": self.evidence_count,
            "memory_operations": self.memory_ops,
            "capability_expansion": list(self.tools_used),
            "memory_ops": self.memory_ops,
            "evidence_count": self.evidence_count,
            "duration": self._format_duration(time.time() - self.start_time),
            "metrics": self.last_metrics,
        }
