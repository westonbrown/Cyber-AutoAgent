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

logger = logging.getLogger(__name__)


class ReactBridgeHandler(PrintingCallbackHandler):
    """
    Handler that bridges SDK callbacks to React UI events.

    This handler processes SDK callbacks and emits structured events that
    the React UI can display. It handles tool execution, reasoning text,
    metrics tracking, and operation state management.
    """

    def __init__(self, max_steps: int = 100, operation_id: str = None):
        """
        Initialize the React bridge handler.

        Args:
            max_steps: Maximum allowed execution steps
            operation_id: Unique operation identifier
        """
        super().__init__()

        # Operation configuration
        self.current_step = 0
        self.max_steps = max_steps
        self.operation_id = operation_id or f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_time = time.time()

        # Metrics tracking
        self.memory_ops = 0
        self.evidence_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.last_metrics_emit_time = time.time()
        self.last_metrics = None

        # Tool tracking
        self.last_tool_name = None
        self.last_tool_id = None
        self.announced_tools = set()
        self.tool_input_buffer = {}
        self.tools_used = set()

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

        # Initialize tool emitter
        self.tool_emitter = ToolEventEmitter(self._emit_ui_event)

        # Emit initial metrics
        self._emit_initial_metrics()

    def __call__(self, **kwargs):
        """
        Process SDK callbacks and emit appropriate UI events.

        This is the main entry point for all SDK callbacks. It routes
        different callback types to appropriate handlers.
        """
        # SDK event adapter - transform SDK events to UI events
        self._transform_sdk_event(kwargs)

    def _emit_ui_event(self, event: Dict[str, Any]) -> None:
        """
        Emit structured event for the React UI.

        All events are emitted with a specific format that the React UI
        can parse and display appropriately.
        """
        event["timestamp"] = datetime.now().isoformat()
        print(f"__CYBER_EVENT__{json.dumps(event)}__CYBER_EVENT_END__", flush=True)

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

        # Process each type of SDK event

        # 1. Message events (for step tracking)
        if message and isinstance(message, dict):
            self._process_message(message)

        # 2. Reasoning text events
        if reasoning_text:
            self._accumulate_reasoning_text(reasoning_text)
            # Estimate tokens for metrics
            self.total_output_tokens += len(reasoning_text) // 4

        # 3. Streaming data events
        elif data and not complete:
            self.total_output_tokens += len(data) // 4

        # 4. Tool announcement events
        if current_tool_use:
            self._process_tool_announcement(current_tool_use)

        # 5. Tool result events
        if tool_result:
            self._process_tool_result_from_message(tool_result)

        # Check alternative result keys
        for alt_key in ["result", "tool_result", "execution_result", "response", "output"]:
            if alt_key in kwargs and kwargs[alt_key] is not None:
                result_data = kwargs[alt_key]
                if isinstance(result_data, str):
                    result_data = {"content": [{"text": result_data}], "status": "success"}
                self._process_tool_result_from_message(result_data)

        # 6. Completion events
        if complete or kwargs.get("is_final"):
            self._handle_completion()

        # 7. SDK metrics events
        if event_loop_metrics:
            self._process_metrics(event_loop_metrics)

        # 8. Periodic metrics emission
        if time.time() - self.last_metrics_emit_time > 5:
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
                self.current_step += 1
                self.pending_step_header = True
            else:
                self.current_step += 1
                self._emit_step_header()

            # Check if step limit reached and raise exception
            if self.current_step >= self.max_steps:
                from modules.handlers.base import StepLimitReached

                raise StepLimitReached(f"Step limit reached: {self.current_step}/{self.max_steps}")

            # Count output tokens
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    self.total_output_tokens += len(str(item.get("text", ""))) // 4

        elif message.get("role") == "user":
            # Count input tokens
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    self.total_input_tokens += len(str(item.get("text", ""))) // 4

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
        tool_input = tool_use.get("input", {})

        # Only process new tools
        if tool_id and tool_id not in self.announced_tools:
            # Emit accumulated reasoning first
            self._emit_accumulated_reasoning()

            # Emit step header if pending
            if self.pending_step_header or (self.current_step == 0 and tool_id):
                if self.current_step == 0:
                    self.current_step = 1
                self._emit_step_header()
                self.pending_step_header = False

            # Track tool
            self.announced_tools.add(tool_id)
            self.last_tool_name = tool_name
            self.last_tool_id = tool_id
            self.tools_used.add(tool_name)
            self.tool_input_buffer[tool_id] = tool_input

            # Emit tool start event
            self._emit_ui_event({"type": "tool_start", "tool_name": tool_name, "tool_input": tool_input})

            # Emit tool-specific events
            if tool_input and self._is_valid_input(tool_input):
                self.tool_emitter.emit_tool_specific_events(tool_name, tool_input)

                # Handle swarm tracking
                if tool_name == "swarm":
                    self._track_swarm_start(tool_input)
                elif tool_name == "handoff_to_agent":
                    self._track_agent_handoff(tool_input)
                elif tool_name == "complete_swarm_task":
                    self._track_swarm_complete()
                elif tool_name == "stop":
                    self._stop_tool_used = True

        # Handle streaming updates
        elif tool_id in self.announced_tools and tool_input:
            self.tool_input_buffer[tool_id] = tool_input
            if isinstance(tool_input, str):
                try:
                    parsed_input = json.loads(tool_input)
                    if isinstance(parsed_input, dict):
                        self.tool_emitter.emit_tool_specific_events(tool_name, parsed_input)
                except json.JSONDecodeError:
                    pass
            elif isinstance(tool_input, dict):
                self.tool_emitter.emit_tool_specific_events(tool_name, tool_input)

    def _process_tool_result_from_message(self, tool_result: Any) -> None:
        """Process tool execution results."""
        # Stop thinking animation
        self._emit_ui_event({"type": "thinking_end"})

        # Convert result to dict format
        if hasattr(tool_result, "__dict__"):
            tool_result_dict = tool_result.__dict__
        elif isinstance(tool_result, dict):
            tool_result_dict = tool_result
        else:
            tool_result_dict = {"content": [{"text": str(tool_result)}], "status": "success"}

        # Extract result details
        content_items = tool_result_dict.get("content", [])
        status = tool_result_dict.get("status", "success")
        tool_use_id = tool_result_dict.get("toolUseId")

        # Get original tool input
        tool_input = self.tool_input_buffer.get(tool_use_id, {})

        # Handle errors
        if status == "error":
            error_text = ""
            for item in content_items:
                if isinstance(item, dict) and "text" in item:
                    error_text += item["text"] + "\n"
            if error_text.strip():
                self._emit_ui_event({"type": "error", "content": error_text.strip()})
            return

        # Extract output text
        output_text = self._extract_output_text(content_items)

        # Emit output or status
        if output_text.strip():
            self._emit_ui_event({"type": "output", "content": output_text.strip()})
        elif self.last_tool_name in ["handoff_to_user", "handoff_to_agent", "stop", "mem0_memory", "shell"]:
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

        # Update metrics
        if self.last_tool_name == "mem0_memory":
            self.memory_ops += 1
            action = tool_input.get("action", "unknown") if isinstance(tool_input, dict) else "unknown"
            if action == "store":
                self.evidence_count += 1

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
        self._emit_ui_event(
            {
                "type": "step_header",
                "step": self.current_step,
                "maxSteps": self.max_steps,
                "operation": self.operation_id,
                "duration": self._format_duration(time.time() - self.start_time),
            }
        )

    def _emit_initial_metrics(self) -> None:
        """Emit initial metrics on startup."""
        self._emit_ui_event(
            {
                "type": "metrics_update",
                "metrics": {"tokens": 0, "cost": 0.0, "duration": "0s", "memoryOps": 0, "evidence": 0},
            }
        )

    def _emit_estimated_metrics(self) -> None:
        """Emit estimated metrics based on token counting."""
        # Claude 3.5 Sonnet pricing: $3/1M input, $15/1M output
        input_cost = (self.total_input_tokens / 1_000_000) * 3.0
        output_cost = (self.total_output_tokens / 1_000_000) * 15.0
        total_cost = input_cost + output_cost

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

    def _process_metrics(self, event_loop_metrics: Dict[str, Any]) -> None:
        """Process SDK metrics and emit updates."""
        self.last_metrics = event_loop_metrics
        usage = event_loop_metrics.accumulated_usage

        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)

        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0
        total_cost = input_cost + output_cost

        self._emit_ui_event(
            {
                "type": "metrics_update",
                "metrics": {
                    "tokens": input_tokens + output_tokens,
                    "cost": total_cost,
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
            self._emit_ui_event({"type": "output", "content": "Command completed successfully"})

    def _track_swarm_start(self, tool_input: Dict[str, Any]) -> None:
        """Track swarm operation start."""
        agents = tool_input.get("agents", [])
        agent_names = []

        if isinstance(agents, list):
            for agent in agents:
                if isinstance(agent, dict):
                    name = agent.get("name") or agent.get("role") or "agent"
                    agent_names.append(name)
                elif isinstance(agent, str):
                    agent_names.append(agent)
                else:
                    agent_names.append("agent")

        self.in_swarm_operation = True
        self.swarm_agents = agent_names
        self.current_swarm_agent = agent_names[0] if agent_names else None
        self.swarm_handoff_count = 0

    def _track_agent_handoff(self, tool_input: Dict[str, Any]) -> None:
        """Track agent handoffs in swarm."""
        if self.in_swarm_operation:
            agent_name = tool_input.get("agent_name", "")
            message = tool_input.get("message", "")
            message_preview = message[:100] + "..." if len(message) > 100 else message

            from_agent = self.current_swarm_agent or "unknown"
            self.current_swarm_agent = agent_name
            self.swarm_handoff_count += 1

            self._emit_ui_event(
                {
                    "type": "swarm_handoff",
                    "from_agent": from_agent,
                    "to_agent": agent_name,
                    "message": message_preview,
                }
            )

    def _track_swarm_complete(self) -> None:
        """Track swarm completion."""
        if self.in_swarm_operation:
            final_agent = self.current_swarm_agent or "unknown"

            self._emit_ui_event(
                {
                    "type": "swarm_complete",
                    "final_agent": final_agent,
                    "execution_count": self.swarm_handoff_count + 1,
                }
            )

            # Reset swarm state
            self.in_swarm_operation = False
            self.swarm_agents = []
            self.current_swarm_agent = None
            self.swarm_handoff_count = 0

    def _is_valid_input(self, tool_input: Any) -> bool:
        """Check if tool input is valid."""
        return bool(tool_input) and (isinstance(tool_input, dict) or isinstance(tool_input, str))

    def _extract_output_text(self, content_items: List[Any]) -> str:
        """Extract text from content items."""
        output_text = ""
        for item in content_items:
            if isinstance(item, dict):
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
            from modules.tools.report_generator import generate_security_report

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

            report_content = generate_security_report(
                target=target,
                objective=objective,
                operation_id=self.operation_id,
                steps_executed=self.current_step,
                tools_used=list(self.tools_used),
                provider=provider,
                module=module,
            )

            if report_content and not report_content.startswith("Error:"):
                self._emit_ui_event({"type": "output", "content": "\n" + report_content})
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

        if os.getenv("ENABLE_AUTO_EVALUATION", "true").lower() != "true":
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

    def wait_for_evaluation_completion(self, timeout: int = 300) -> None:
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
