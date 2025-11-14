"""
React Bridge Handler - Integrates Strands SDK callbacks with React UI.

This handler extends the SDK's PrintingCallbackHandler to emit structured
events for the React terminal UI, providing real-time operation visibility.
"""

import json
import os
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from strands.handlers import PrintingCallbackHandler

from ..events import EventEmitter, get_emitter
from ..output_interceptor import (
    get_buffered_output,
    get_buffered_error_output,
    set_tool_execution_state,
)
from .tool_emitters import ToolEventEmitter
from modules.config.logger_factory import get_logger

logger = get_logger("Handlers.ReactBridge")


class ReactBridgeHandler(PrintingCallbackHandler):
    """
    Handler that bridges SDK callbacks to React UI events.

    This handler processes SDK callbacks and emits structured events that
    the React UI can display. It handles tool execution, reasoning text,
    metrics tracking, and operation state management.
    """

    def __init__(
        self,
        max_steps: int = 100,
        operation_id: str = None,
        model_id: str = None,
        swarm_model_id: str = None,
        emitter: EventEmitter = None,
        init_context: Dict[str, Any] = None,
    ):
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
        self.operation_id = (
            operation_id or f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # Initialize emitter with operation context
        self.emitter = emitter or get_emitter(operation_id=self.operation_id)
        self.start_time = time.time()
        self.model_id = model_id
        self.swarm_model_id = (
            swarm_model_id or "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
        self.init_context = init_context or {}

        # Metrics tracking
        self.memory_ops = 0
        self.evidence_count = 0
        # Track SDK metrics as authoritative source
        self.sdk_input_tokens = 0
        self.sdk_output_tokens = 0
        # Metrics emission handled by background thread

        # Tool tracking
        self.last_tool_name = None
        self.last_tool_id = None
        self.tool_start_times = {}  # Track start times for duration calculation
        self.announced_tools = set()
        self.tool_input_buffer = {}
        self.tool_name_buffer = {}  # Map tool_id -> tool_name for correct attribution
        self.tools_used = set()
        # Track per-tool usage counts for accurate reporting
        self.tool_counts = {}
        # Track whether a tool invocation already emitted meaningful output to suppress redundant generic completions
        self.tool_use_output_emitted = {}
        # Track tool IDs that have complete input to avoid duplicate updates
        self.tools_with_complete_input = set()

        # Reasoning buffer to prevent fragmentation
        self.reasoning_buffer = []
        # Track times for reasoning streaming control (append vs. flush)
        self.last_reasoning_time = 0
        self._last_reasoning_flush = 0
        # Track whether any reasoning has ever been emitted (for CLI orchestration heuristics)
        self._emitted_any_reasoning = False

        # Recent reasoning dedupe per agent (TTL-based to prevent repeated summaries)
        self._recent_reasoning_by_agent = {}
        try:
            self._recent_reasoning_ttl = float(
                os.getenv("REASONING_DEDUPE_TTL_S", "20")
            )
        except Exception:
            self._recent_reasoning_ttl = 20.0

        # Ensure each numeric step has exactly one reasoning block (after initial pre-step reasoning)
        self._reasoning_required_for_current_step = (
            False  # Set True at each step header; cleared on reasoning emit
        )

        # Step header tracking
        self.pending_step_header = False
        # Track whether we already emitted a header for the current reasoning-only cycle
        self._reasoning_step_header_emitted = False
        # Reasoning gating to avoid duplicate reasoning per step
        self._any_step_header_emitted = False
        self._reasoning_emitted_since_last_step_header = False

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

        # Termination tracking (stop tool or step limit)
        self._termination_emitted = False
        # Track sub-agent steps separately
        self.swarm_agent_steps = {}  # {agent_name: current_step}
        # Track python_repl preview emission per tool id to suppress generic completion
        self._python_preview_emitted = set()
        self.swarm_max_iterations = (
            None  # Max iterations for entire swarm (provided by tool input)
        )
        self.swarm_max_handoffs = (
            None  # Max handoffs across the swarm (provided by tool input)
        )
        self.swarm_iteration_count = 0  # Track total iterations across all agents
        self.swarm_tool_id = None  # Track the swarm tool's specific ID

        # Swarm agent tool mapping for intelligent agent detection
        self.swarm_agent_tools = {}  # {agent_name: [tool_list]}
        self.swarm_agent_details = []  # Store full agent details
        # Track in-flight tool execution per agent to control reasoning flush timing
        self._tool_running_by_agent: Dict[str, bool] = {}
        # Emit swarm iteration limit notice only once
        self._swarm_limit_announced = False
        self._swarm_handoff_limit_announced = False

        # Initialize tool emitter
        self.tool_emitter = ToolEventEmitter(self._emit_ui_event)

        # Metrics update thread
        self._metrics_thread = None
        self._stop_metrics = False
        self._last_agent = None  # Store agent reference for metrics

        # Emit initial metrics
        self._emit_initial_metrics()

        # Start periodic metrics updates
        self._start_metrics_thread()

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
                op_event["ui_mode"] = os.getenv("CYBER_UI_MODE", "cli").lower()

            self._emit_ui_event(op_event)

            # Emit startup spinner immediately after initialization
            # This provides visual feedback during model loading and first reasoning
            self._emit_ui_event(
                {"type": "thinking", "context": "startup", "urgent": True}
            )
        except Exception as e:
            logger.warning("Failed to emit operation_init event: %s", e)

    def __call__(self, **kwargs):
        """
        Process SDK callbacks and emit appropriate UI events.

        This is the main entry point for all SDK callbacks. It routes
        different callback types to appropriate handlers.

        When in swarm operation context, callbacks are attributed to the
        currently active swarm agent for proper visibility in the UI.
        """
        # Minimal logging for production

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
        try:
            self.emitter.emit(event)
        except BrokenPipeError:
            # Frontend terminal closed (user interrupted) - suppress noisy traceback
            logger.debug(f"Frontend disconnected, skipping event {event.get('type')}")
        except Exception as e:
            logger.error(
                f"Failed to emit event {event.get('type')}: {e}", exc_info=True
            )

    def _emit_termination(self, reason: str, message: str) -> None:
        """Emit a single termination_reason event (idempotent) with a clear final step.

        Ensures the UI sees a clean end-of-operation sequence:
        - Flush any pending reasoning
        - End any active thinking indicator
        - Emit a final step header (TERMINATED)
        - Emit the termination_reason payload
        """
        try:
            if self._termination_emitted:
                return
            self._termination_emitted = True

            # Flush any accumulated reasoning so it doesn't appear after termination
            try:
                self._emit_accumulated_reasoning(force=True)
            except Exception:
                pass

            # End any active thinking indicator in the UI
            try:
                self._emit_ui_event({"type": "thinking_end"})
            except Exception:
                pass

            # Emit a final step header for clear visual separation in the stream
            try:
                self._emit_ui_event(
                    {
                        "type": "step_header",
                        "step": "TERMINATED",
                        "operation": self.operation_id,
                        "duration": self._format_duration(
                            time.time() - self.start_time
                        ),
                        "maxSteps": self.max_steps,
                    }
                )
            except Exception:
                pass

            # Emit termination details
            self._emit_ui_event(
                {
                    "type": "termination_reason",
                    "reason": reason,
                    "message": message,
                    "current_step": self.current_step,
                    "max_steps": self.max_steps,
                }
            )
        except Exception as e:
            logger.debug("Failed to emit termination event: %s", e)

    def _transform_sdk_event(self, kwargs: Dict[str, Any]) -> None:
        """Adapt SDK callbacks to UI events.

        Delegates to small helpers to keep this method readable and testable.
        """
        # Swarm agent detection from callback context
        self._maybe_switch_swarm_agent(kwargs)

        # Extract common fields
        message = kwargs.get("message")
        reasoning_text = kwargs.get("reasoningText")
        data = kwargs.get("data", "")
        complete = kwargs.get("complete", False)
        current_tool_use = kwargs.get("current_tool_use")
        tool_result = kwargs.get("toolResult")

        # Track whether we saw explicit reasoning in this callback to avoid duplicate extraction
        self._recent_reasoning_seen = False

        # Metrics from AgentResult
        agent_result = kwargs.get("result")
        event_loop_metrics = kwargs.get("event_loop_metrics")
        if agent_result and hasattr(agent_result, "metrics"):
            event_loop_metrics = agent_result.metrics

        # 1) Reasoning first (prefer explicit reasoningText over message extraction to avoid duplicates)
        skip_message_reasoning = False
        if reasoning_text:
            self._handle_reasoning(reasoning_text)
            self._recent_reasoning_seen = True
            skip_message_reasoning = True
        elif data and not complete:
            self._handle_streaming_reasoning(data)
            self._recent_reasoning_seen = True

        # 2) Message (tool blocks, result blocks, and optional swarm reasoning extraction)
        if message and isinstance(message, dict):
            self._process_message(
                message, skip_reasoning_extraction=skip_message_reasoning
            )

        # 3) Tool lifecycle
        if current_tool_use:
            self._handle_tool_announcement(current_tool_use)

        if tool_result:
            self._handle_tool_result(tool_result)

        # 3b) Alternate result keys
        self._handle_alternate_results(kwargs, tool_result_already=bool(tool_result))

        # 4) Completion and errors
        if complete or kwargs.get("is_final"):
            self._handle_completion()

        if kwargs.get("error") and "MaxTokensReached" in str(kwargs.get("error")):
            self._emit_ui_event(
                {
                    "type": "error",
                    "content": "⚠️ Token limit reached - agent cannot continue due to context size.",
                    "metadata": {"error_type": "max_tokens"},
                }
            )

        # 5) Metrics
        if event_loop_metrics:
            self._process_metrics(event_loop_metrics)

        # Reset duplicate guard at end of processing for this callback
        self._recent_reasoning_seen = False

        agent = kwargs.get("agent")
        if agent and hasattr(agent, "event_loop_metrics"):
            usage = agent.event_loop_metrics.accumulated_usage
            if usage:
                self.sdk_input_tokens = usage.get("inputTokens", 0)
                self.sdk_output_tokens = usage.get("outputTokens", 0)

    # -- Helper methods ----------------------------------------------------

    def _maybe_switch_swarm_agent(self, kwargs: Dict[str, Any]) -> None:
        if not self.in_swarm_operation:
            return
        detected = self._detect_swarm_agent_from_callback(kwargs)
        if detected and detected != self.current_swarm_agent:
            # In swarm mode, do NOT flush reasoning on agent switches; keep rationale
            # buffered and let it flush after the next tool_end to preserve ordering.
            if (not self.in_swarm_operation) and self.reasoning_buffer:
                self._emit_accumulated_reasoning()
            self.current_swarm_agent = detected
            if detected not in self.swarm_agent_steps:
                self.swarm_agent_steps[detected] = 0

    def _handle_reasoning(self, text: str) -> None:
        """Handle reasoning text with per-agent TTL dedupe, then accumulate.

        We avoid emitting identical reasoning fragments repeatedly within a short
        window per agent, which commonly happens in swarm mode.
        """
        if not text:
            return
        try:
            agent_key = self.current_swarm_agent or "main"
            # Normalize whitespace to compare fragments robustly
            norm = re.sub(r"\s+", " ", str(text)).strip()
            if not norm:
                return
            now = time.time()
            recent = self._recent_reasoning_by_agent.get(agent_key, {})
            # Prune expired entries
            if recent:
                for k, ts in list(recent.items()):
                    if now - ts > getattr(self, "_recent_reasoning_ttl", 20.0):
                        del recent[k]
            # Skip if we've seen this fragment very recently for this agent
            if norm in recent:
                return
            recent[norm] = now
            self._recent_reasoning_by_agent[agent_key] = recent
        except Exception:
            # Never break reasoning on dedupe errors
            pass
        # Accumulate for later flush
        # Do not advance or pre-emit step headers for reasoning-only turns; steps are driven by tool usage
        self._accumulate_reasoning_text(text)

    def _handle_streaming_reasoning(self, data: str) -> None:
        # Do not advance or pre-emit step headers for reasoning streaming; steps are driven by tools
        # Accumulate only; avoid emitting incremental deltas to prevent duplicate fragments
        if data and not data.startswith("[") and not data.startswith("{"):
            self._accumulate_reasoning_text(data)

    def _handle_tool_announcement(self, tool_use: Dict[str, Any]) -> None:
        # Swarm context agent inference
        if self.in_swarm_operation:
            tool_name = tool_use.get("name", "")
            # Do not flush reasoning here; step header will pre-flush once to avoid duplicates
            if tool_name not in ["swarm", "complete_swarm_task", "handoff_to_agent"]:
                active_agent = self._infer_active_swarm_agent(tool_name)
                if active_agent and active_agent != self.current_swarm_agent:
                    if self.reasoning_buffer:
                        # Avoid duplicate emissions: agent switch flush is allowed; header pre-flush will see empty buffer
                        self._emit_accumulated_reasoning()
                    prev = self.current_swarm_agent
                    self.current_swarm_agent = active_agent
                    if active_agent not in self.swarm_agent_steps:
                        self.swarm_agent_steps[active_agent] = 0
                    self._emit_ui_event(
                        {
                            "type": "swarm_agent_transition",
                            "from_agent": prev,
                            "to_agent": active_agent,
                            "via_tool": tool_name,
                        }
                    )
        self._process_tool_announcement(tool_use)

    def _handle_tool_result(self, tool_result: Any) -> None:
        # In swarm mode, do not flush reasoning here; defer until after tool_end
        self._process_tool_result_from_message(tool_result)

    def _handle_alternate_results(
        self, kwargs: Dict[str, Any], tool_result_already: bool
    ) -> None:
        for alt_key in [
            "result",
            "tool_result",
            "execution_result",
            "response",
            "output",
        ]:
            result_data = kwargs.get(alt_key)
            if result_data is None:
                continue
            if alt_key == "result" and hasattr(result_data, "metrics"):
                continue
            if alt_key == "tool_result" and tool_result_already:
                continue
            if isinstance(result_data, str):
                result_data = {"content": [{"text": result_data}], "status": "success"}
            self._process_tool_result_from_message(result_data)

    def _process_message(
        self, message: Dict[str, Any], skip_reasoning_extraction: bool = False
    ) -> None:
        """Process message objects to track steps and extract content.

        Args:
            message: The SDK message dict
            skip_reasoning_extraction: When True, do not extract reasoning text from message content
                                      (used to avoid duplication when reasoningText is provided)
        """
        content = message.get("content", [])

        # Check if message contains tool usage
        has_tool_use = any(
            isinstance(block, dict)
            and (block.get("type") == "tool_use" or "toolUse" in block)
            for block in content
        )

        # Handle step progression
        if message.get("role") == "assistant":
            # Identify the very first assistant turn (before any steps are counted)
            initial_assistant = not self.in_swarm_operation and self.current_step == 0

            if has_tool_use:
                # Reset batch tracking for new assistant response with tools
                # This allows multiple tools in the same response to share one step header
                if hasattr(self, "_step_header_emitted_for_batch"):
                    delattr(self, "_step_header_emitted_for_batch")
                if hasattr(self, "_tools_in_current_step"):
                    # Clear the list but keep the attribute to signal we're in a step
                    self._tools_in_current_step = []

                if initial_assistant:
                    # Do not emit header yet; let the first tool announcement emit Step 1
                    # Ensure a header will be emitted on tool announcement
                    self.pending_step_header = True
                else:
                    # Defer step header to tool announcement to keep a single emission path
                    # Ensure a header will be emitted on tool announcement
                    self.pending_step_header = True
            else:
                # Pure reasoning turn without tools: do not advance steps or emit headers
                if initial_assistant:
                    # Keep initial reasoning above the first step header
                    pass
                elif self._reasoning_step_header_emitted:
                    # Reset any prior flag
                    self._reasoning_step_header_emitted = False
                else:
                    # No-op: keep reasoning adjacent to upcoming tool step
                    pass

            # Count output tokens
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    pass  # Token counting via SDK metrics

        elif message.get("role") == "user":
            # Count input tokens
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    pass  # Token counting via SDK metrics

        # Emit swarm agent reasoning from assistant message text prior to tool_use blocks
        # This captures agent rationale that may not arrive via reasoningText callbacks.
        # Avoid duplicate emission if explicit reasoningText/streaming already seen for this callback.
        if (
            self.in_swarm_operation
            and message.get("role") == "assistant"
            and not getattr(self, "_recent_reasoning_seen", False)
            and not skip_reasoning_extraction
        ):
            try:
                for block in content:
                    # Stop at first tool_use/toolUse block to avoid pulling post-tool text
                    if isinstance(block, dict) and (
                        block.get("type") == "tool_use" or "toolUse" in block
                    ):
                        break
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        text_val = block.get("text", "").strip()
                        if text_val:
                            # Reuse existing reasoning pipeline (adds swarm_agent metadata and flushes appropriately)
                            self._handle_reasoning(text_val)
                            # Mark so we don't double-extract within same callback
                            self._recent_reasoning_seen = True
            except Exception:
                # Never allow parsing issues to break streaming
                pass

        # Additionally, in swarm, capture one trailing text block that appears AFTER a tool_use
        # in the same assistant message (common pattern for short rationale)
        if (
            self.in_swarm_operation
            and message.get("role") == "assistant"
            and has_tool_use
            and not getattr(self, "_recent_reasoning_seen", False)
            and not skip_reasoning_extraction
        ):
            try:
                seen_tool = False
                for block in content:
                    if isinstance(block, dict) and (
                        block.get("type") == "tool_use" or "toolUse" in block
                    ):
                        seen_tool = True
                        continue
                    if (
                        seen_tool
                        and isinstance(block, dict)
                        and isinstance(block.get("text"), str)
                    ):
                        txt = block.get("text", "").strip()
                        # Skip JSON-like blocks and empty
                        if txt and not txt.startswith("{") and not txt.startswith("["):
                            self._handle_reasoning(txt)
                            self._recent_reasoning_seen = True
                            break
            except Exception:
                pass

        # Process tool uses in message content
        for block in content:
            if isinstance(block, dict):
                # Handle tool use blocks
                if "toolUse" in block:
                    tool_use = block["toolUse"]
                    # Always process tool announcements - handler will determine if events needed
                    self._process_tool_announcement(tool_use)
                elif block.get("type") == "tool_use":
                    # Alternative format
                    self._process_tool_announcement(block)

        # Process tool results in message content
        for block in content:
            if isinstance(block, dict):
                if "toolResult" in block:
                    self._process_tool_result_from_message(block["toolResult"])
                elif "toolResponse" in block:
                    self._process_tool_result_from_message(block["toolResponse"])
                elif block.get("type") == "tool_result":
                    self._process_tool_result_from_message(block)

    def _handoff_input_complete(self, tool_input: Any) -> bool:
        try:
            return (
                isinstance(tool_input, dict)
                and bool(tool_input.get("handoff_to"))
                and bool(tool_input.get("message"))
            )
        except Exception:
            return False

    def _process_tool_announcement(self, tool_use: Dict[str, Any]) -> None:
        """Process tool usage announcements.

        For main agent: ReactHooks handles tool events via SDK hooks.
        For swarm agents: We handle events here since they lack hooks.
        """
        tool_name = tool_use.get("name", "")
        tool_id = tool_use.get("toolUseId", "")
        raw_input = tool_use.get("input", {})
        tool_input = self._parse_tool_input_from_stream(raw_input)

        # Special handling for stop tool: flush reasoning, mark stop, but proceed with normal tool display
        if tool_name == "stop":
            # Flush any pending reasoning before termination
            if self.reasoning_buffer:
                self._emit_accumulated_reasoning()
            # Mark stop; SDK loop will end; we still show step header and tool header for clarity
            self._stop_tool_used = True
            # Do not emit termination here to preserve natural ordering (after tool header)
            # Do not prevent deferred step header; allow standard header and tool events

        # Check if this is a swarm agent tool (needs immediate emission)
        is_swarm_agent_tool = (
            self.in_swarm_operation
            and self.current_swarm_agent
            and tool_name not in ["swarm", "complete_swarm_task", "handoff_to_agent"]
        )

        # Only process new tools
        if tool_id and tool_id not in self.announced_tools:
            # Ensure a step header will be emitted for each new tool (non-swarm)
            # IMPORTANT: Only emit header for the FIRST tool in a multi-tool response
            # Claude 4.5 can invoke multiple tools in parallel within the same response
            if not self.in_swarm_operation:
                # Check if this is the first tool announcement since the last step header
                if self.current_step == 0 or not hasattr(
                    self, "_tools_in_current_step"
                ):
                    self._tools_in_current_step = []
                    self.pending_step_header = True
                    # Emit accumulated reasoning first (for non-swarm or if not already emitted)
                    self._emit_accumulated_reasoning()

                # Track this tool as part of current step
                self._tools_in_current_step.append(tool_id)

            # Emit step header ONLY if pending (i.e., this is the first tool in the response)
            if self.pending_step_header and (
                self.current_step == 0 or self.pending_step_header
            ):
                if self.current_step == 0:
                    # First tool ever - increment step
                    if not self.in_swarm_operation:
                        self.current_step += 1
                elif self.pending_step_header and not hasattr(
                    self, "_step_header_emitted_for_batch"
                ):
                    # First tool in this batch - increment step
                    if not self.in_swarm_operation:
                        self.current_step += 1
                    self._step_header_emitted_for_batch = True

                # Check if step limit exceeded BEFORE emitting confusing header
                # Don't enforce step limit for swarm agents - they have their own limits
                if not self.in_swarm_operation and self.current_step > self.max_steps:
                    # Emit notification about step limit before raising exception
                    self._emit_termination(
                        "step_limit",
                        f"Completed maximum allowed steps ({self.max_steps}/{self.max_steps}). Operation will now generate final report.",
                    )
                    from modules.handlers.base import StepLimitReached

                    raise StepLimitReached(
                        f"Step limit reached: {self.current_step}/{self.max_steps}"
                    )

                # Only emit header if within step limits
                self._emit_step_header()
                self.pending_step_header = False

            # Track tool
            self.announced_tools.add(tool_id)
            self.last_tool_name = tool_name
            self.last_tool_id = tool_id
            self.tools_used.add(tool_name)
            # Increment per-tool usage count once per announced tool id
            try:
                self.tool_counts[tool_name] = self.tool_counts.get(tool_name, 0) + 1
            except Exception:
                # Defensive: never allow metrics to break streaming
                pass
            self.tool_input_buffer[tool_id] = tool_input
            self.tool_name_buffer[tool_id] = (
                tool_name  # Track tool name for correct attribution
            )

            # Intelligently detect which swarm agent is active based on tool usage
            if self.in_swarm_operation and tool_name != "swarm":
                inferred_agent = self._infer_active_swarm_agent(tool_name)
                if inferred_agent and inferred_agent != self.current_swarm_agent:
                    # Agent has changed! Update tracking
                    self.current_swarm_agent = inferred_agent
                    # Initialize step count if needed
                    if inferred_agent not in self.swarm_agent_steps:
                        self.swarm_agent_steps[inferred_agent] = 0

            # Emit tool_start for meaningful input OR swarm agents (which need immediate emission)
            has_meaningful_input = (
                bool(tool_input)
                and tool_input != {}
                and self._is_valid_input(tool_input)
            )

            # For handoff_to_agent, require complete input (handoff_to and message) to avoid duplicate args
            if tool_name == "handoff_to_agent" and not self._handoff_input_complete(
                tool_input
            ):
                has_meaningful_input = False

            # For swarm agents, delay emission until we have input
            if is_swarm_agent_tool and not has_meaningful_input:
                # Don't emit yet for swarm agents without input
                # The tool_input_update will handle it
                return

            # Only the swarm path emits tool headers from the bridge; main agent headers come from ReactHooks
            should_emit = self.in_swarm_operation and (
                has_meaningful_input or is_swarm_agent_tool
            )

            if should_emit:
                # Suppress OutputInterceptor during tool execution
                set_tool_execution_state(True)
                # Mark tool running for this agent to prevent mid-tool reasoning flushes
                try:
                    agent_key = self.current_swarm_agent or "main"
                    self._tool_running_by_agent[agent_key] = True
                except Exception:
                    pass

                # Record start time for duration calculation
                if tool_id:
                    self.tool_start_times[tool_id] = time.time()

                # Build tool_start event with all necessary information
                tool_event = {
                    "type": "tool_start",
                    "tool_name": tool_name,
                    "tool_id": tool_id,
                    "tool_input": tool_input,
                }

                # Mark as having complete input if it's meaningful
                if has_meaningful_input or (is_swarm_agent_tool and tool_input):
                    self.tools_with_complete_input.add(tool_id)

                # Add swarm context if applicable
                if self.in_swarm_operation and self.current_swarm_agent:
                    tool_event["swarm_agent"] = self.current_swarm_agent
                    tool_event["swarm_step"] = self.swarm_agent_steps.get(
                        self.current_swarm_agent, 1
                    )

                self._emit_ui_event(tool_event)

                # Also emit tool_invocation_start for compatibility
                invocation_event = {
                    "type": "tool_invocation_start",
                    "tool_name": tool_name,
                }
                if self.in_swarm_operation and self.current_swarm_agent:
                    invocation_event["swarm_agent"] = self.current_swarm_agent
                self._emit_ui_event(invocation_event)

            # Emit tool-specific events (skip 'swarm' to avoid duplicate swarm_start emissions)
            if tool_input and self._is_valid_input(tool_input) and tool_name != "swarm":
                self.tool_emitter.emit_tool_specific_events(tool_name, tool_input)

            # Emit thinking animation ONLY after a tool_start has been emitted
            # This prevents the UI from showing an 'Executing' spinner without a corresponding tool header
            if should_emit:
                current_time_ms = int(time.time() * 1000)
                self._emit_ui_event(
                    {
                        "type": "thinking",
                        "context": "tool_execution",
                        "startTime": current_time_ms,
                    }
                )

            # Handle swarm tracking (only here; ToolEventEmitter is skipped for 'swarm')
            if tool_name == "swarm":
                try:
                    self._track_swarm_start(tool_input, tool_id)
                    # Emit a status update about swarm execution
                    self._emit_ui_event(
                        {
                            "type": "info",
                            "content": "Swarm agents executing in parallel - this may take a few minutes...",
                            "metadata": {"swarm_status": "executing"},
                        }
                    )
                except Exception as e:
                    logger.warning(
                        "SWARM_START parsing failed: %s; input=%s", e, raw_input
                    )
            elif tool_name == "handoff_to_agent":
                try:
                    # Track handoff and ensure we have valid agent tracking
                    if tool_input:
                        # Normalize agent field: prefer explicit agent_name, fall back to handoff_to alias
                        agent_name = (
                            tool_input.get("agent_name")
                            or tool_input.get("handoff_to")
                            or ""
                        )
                        if agent_name:
                            tool_input["agent_name"] = (
                                agent_name  # ensure consistent key for downstream
                            )
                            # Emit accumulated reasoning before handoff
                            if self.reasoning_buffer:
                                self._emit_accumulated_reasoning()
                            self._track_agent_handoff(tool_input)
                        else:
                            # Try to extract agent from message or other fields
                            message = tool_input.get("message", "")
                            if message:
                                # Look for agent name in message
                                for known_agent in self.swarm_agents:
                                    if known_agent.lower() in message.lower():
                                        tool_input["agent_name"] = known_agent
                                        self._track_agent_handoff(tool_input)
                                        break
                            else:
                                pass  # No known agent found in input
                except Exception as e:
                    logger.warning(
                        "AGENT_HANDOFF parsing failed: %s; input=%s", e, raw_input
                    )
            elif tool_name == "complete_swarm_task":
                self._track_swarm_complete()
            elif tool_name == "stop":
                # Mark stop; termination will be emitted on tool result to appear below tool args
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
                or (
                    isinstance(old_input, dict)
                    and len(old_input) == 1
                    and "value" in old_input
                )
            )

            has_complete_content = new_input and new_input != {} and not is_partial_json

            # Only emit when we transition to complete content
            if was_empty_or_partial and has_complete_content:
                # Suppress OutputInterceptor during tool execution
                set_tool_execution_state(True)

                # For swarm agents, emit proper tool_start if not already done
                if (
                    self.in_swarm_operation
                    and self.current_swarm_agent
                    and tool_id in self.announced_tools
                    and tool_id not in self.tools_with_complete_input
                ):
                    # Emit complete tool_start event now that we have the input
                    self._emit_ui_event(
                        {
                            "type": "tool_start",
                            "tool_name": self.last_tool_name,
                            "tool_id": tool_id,
                            "tool_input": new_input,
                            "swarm_agent": self.current_swarm_agent,
                            "swarm_step": self.swarm_agent_steps.get(
                                self.current_swarm_agent, 1
                            ),
                        }
                    )
                    # Also emit tool_invocation_start for compatibility
                    self._emit_ui_event(
                        {
                            "type": "tool_invocation_start",
                            "tool_name": self.last_tool_name,
                            "swarm_agent": self.current_swarm_agent,
                        }
                    )
                    # Mark as having complete input now
                    self.tools_with_complete_input.add(tool_id)

                # For non-swarm handoff_to_agent, emit tool_start now that input is complete and skip tool_input_update
                elif (
                    not self.in_swarm_operation
                    and self.last_tool_name == "handoff_to_agent"
                    and tool_id in self.announced_tools
                    and tool_id not in self.tools_with_complete_input
                    and self._handoff_input_complete(new_input)
                ):
                    self._emit_ui_event(
                        {
                            "type": "tool_start",
                            "tool_name": self.last_tool_name,
                            "tool_id": tool_id,
                            "tool_input": new_input,
                        }
                    )
                    self._emit_ui_event(
                        {
                            "type": "tool_invocation_start",
                            "tool_name": self.last_tool_name,
                        }
                    )
                    self.tools_with_complete_input.add(tool_id)
                    # Skip tool_input_update for handoff_to_agent to avoid duplicate args listing
                    return

                # Emit a tool_input_update to let the UI refresh placeholders
                try:
                    if tool_id:
                        # Skip tool_input_update for handoff_to_agent to avoid duplicated fields when UI merges events
                        if self.last_tool_name != "handoff_to_agent":
                            self._emit_ui_event(
                                {
                                    "type": "tool_input_update",
                                    "tool_id": tool_id,
                                    "tool_input": new_input,
                                }
                            )
                except Exception:
                    pass

                # Emit tool-specific events now that we have the real input (skip 'swarm')
                if self._is_valid_input(new_input) and self.last_tool_name != "swarm":
                    self.tool_emitter.emit_tool_specific_events(
                        self.last_tool_name, new_input
                    )

                # Handle swarm tracking with real input (single source of truth)
                if self.last_tool_name == "swarm":
                    try:
                        self._track_swarm_start(new_input, self.last_tool_id)
                    except Exception as e:
                        logger.warning(
                            "SWARM_START streaming update parsing failed: %s; input=%s",
                            e,
                            raw_input,
                        )
                        self._track_swarm_start(new_input, self.last_tool_id)
                    except Exception as e:
                        logger.warning(
                            "SWARM_START streaming update parsing failed: %s; input=%s",
                            e,
                            raw_input,
                        )

    def _synthesize_swarm_tool_start(
        self, tool_name: str, buffered_output: str = None
    ) -> None:
        """Synthesize a tool_start event for swarm agents when missing.

        This elegant workaround addresses SDK limitations where swarm agent
        tool invocations don't emit proper start events.
        """
        if not self.in_swarm_operation or tool_name in [
            "swarm",
            "handoff_to_agent",
            "complete_swarm_task",
        ]:
            return

        # Infer which agent is using this tool
        inferred_agent = self._infer_active_swarm_agent(tool_name)
        if inferred_agent and inferred_agent != self.current_swarm_agent:
            # Agent has changed - emit transition event
            prev_agent = self.current_swarm_agent
            self.current_swarm_agent = inferred_agent
            if inferred_agent not in self.swarm_agent_steps:
                self.swarm_agent_steps[inferred_agent] = 0

            # Emit agent transition for UI visibility
            self._emit_ui_event(
                {
                    "type": "swarm_agent_transition",
                    "from_agent": prev_agent,
                    "to_agent": inferred_agent,
                    "via_tool": tool_name,
                }
            )

        # Extract tool input from buffered output if available
        tool_input = {}
        if buffered_output and tool_name in [
            "specialized_recon_orchestrator",
            "auth_chain_analyzer",
            "sql_injection_tester",
            "advanced_payload_coordinator",
        ]:
            # Parse target from output for these tools
            if "testphp.vulnweb.com" in buffered_output:
                tool_input = {"target": "testphp.vulnweb.com"}

        # Emit synthetic tool_start
        self._emit_ui_event(
            {
                "type": "tool_start",
                "tool_name": tool_name,
                "tool_input": tool_input,
                "swarm_agent": self.current_swarm_agent,
                "synthetic": True,  # Mark as synthetic for transparency
            }
        )

    def _process_tool_result_from_message(self, tool_result: Any) -> None:
        """Process tool execution results."""
        # Clear tool execution flag and get buffered output
        set_tool_execution_state(False)
        buffered_output = get_buffered_output()

        # Convert result to dict format early to extract tool_use_id
        if hasattr(tool_result, "__dict__"):
            tool_result_dict = tool_result.__dict__
        elif isinstance(tool_result, dict):
            tool_result_dict = tool_result
        else:
            tool_result_dict = {
                "content": [{"text": str(tool_result)}],
                "status": "success",
            }

        # Extract tool_use_id and get correct tool name early for proper attribution
        tool_use_id = tool_result_dict.get("toolUseId") or self.last_tool_id
        tool_name = self.tool_name_buffer.get(tool_use_id, self.last_tool_name)

        # Do not flush reasoning here; for swarm we want reasoning to follow tool output

        # Ensure we have proper tracking for swarm agents
        if (
            self.in_swarm_operation
            and not self.current_swarm_agent
            and self.swarm_agents
        ):
            # If no current agent set but we're in swarm, use first agent
            self.current_swarm_agent = self.swarm_agents[0]
            logger.info(
                f"Swarm operation started with agent: {self.current_swarm_agent}"
            )

        # Parse swarm output for agent events if this is the swarm tool completing
        if tool_name == "swarm" and buffered_output:
            self._parse_swarm_output_for_events(buffered_output)

        # Also check for swarm timeout or failure patterns
        if self.in_swarm_operation and buffered_output:
            # Look for timeout indicators
            if "300001ms" in buffered_output or "timeout" in buffered_output.lower():
                self._emit_ui_event(
                    {
                        "type": "warning",
                        "content": "⚠️ Swarm execution timeout - agents may have encountered issues with tool permissions or connectivity",
                        "metadata": {"swarm_timeout": True},
                    }
                )

        # Stop thinking animation
        self._emit_ui_event({"type": "thinking_end"})

        # Debug logging for shell tool results
        if tool_name == "shell":
            logger.debug(
                "Shell tool result structure: %s",
                tool_result_dict.keys()
                if isinstance(tool_result_dict, dict)
                else type(tool_result_dict),
            )
            if "content" in tool_result_dict:
                logger.debug(
                    "Shell content items: %d", len(tool_result_dict.get("content", []))
                )
                for i, item in enumerate(
                    tool_result_dict.get("content", [])[:3]
                ):  # Log first 3 items
                    logger.debug(
                        "Content item %d: %s",
                        i,
                        item if isinstance(item, dict) else str(item)[:100],
                    )

        # Extract result details
        content_items = tool_result_dict.get("content", [])
        status = tool_result_dict.get("status", "success")

        # If python_repl produced stdout/stderr, emit a brief preview so it's not lost
        try:
            if tool_name == "python_repl":
                # Stdout preview
                if buffered_output and str(buffered_output).strip():
                    lines = str(buffered_output).splitlines()
                    max_lines = 8
                    preview_lines = lines[:max_lines]
                    remainder = len(lines) - max_lines
                    if remainder > 0:
                        preview_lines.append(f"... ({remainder} more lines)")
                    preview = "\n".join(preview_lines).strip()
                    # Safety cap to avoid giant bursts
                    if len(preview) > 1200:
                        preview = preview[:1200] + "\n... (truncated)"
                    if preview:
                        self._emit_ui_event(
                            {
                                "type": "output",
                                "content": preview,
                                "metadata": {
                                    "fromToolBuffer": True,
                                    "tool": "python_repl",
                                    "preview": True,
                                    "stderr": False,
                                },
                            }
                        )
                        if tool_use_id:
                            self._python_preview_emitted.add(tool_use_id)
                # Stderr preview (very short)
                try:
                    buffered_err = get_buffered_error_output()
                except Exception:
                    buffered_err = ""
                if buffered_err and str(buffered_err).strip():
                    err_lines = str(buffered_err).splitlines()
                    err_max_lines = 4
                    err_preview_lines = err_lines[:err_max_lines]
                    err_remainder = len(err_lines) - err_max_lines
                    if err_remainder > 0:
                        err_preview_lines.append(f"... ({err_remainder} more lines)")
                    err_preview = "\n".join(err_preview_lines).strip()
                    if len(err_preview) > 800:
                        err_preview = err_preview[:800] + "\n... (truncated)"
                    if err_preview:
                        self._emit_ui_event(
                            {
                                "type": "output",
                                "content": err_preview,
                                "metadata": {
                                    "fromToolBuffer": True,
                                    "tool": "python_repl",
                                    "preview": True,
                                    "stderr": True,
                                },
                            }
                        )
                        if tool_use_id:
                            self._python_preview_emitted.add(tool_use_id)
        except Exception:
            pass

        # Get original tool input
        tool_input = self.tool_input_buffer.get(tool_use_id, {})

        # For swarm agents, ensure we have proper tool visibility
        # The tool_start should have been emitted when processing toolUse blocks
        # This is the tool_end event

        # Emit tool completion event with swarm context
        success = status != "error"

        # For stop tool, emit termination after tool header (below where output would go)
        try:
            if tool_name == "stop" and not self._termination_emitted:
                # Use tool input reason if available
                reason_msg = "Stop tool used - terminating"
                try:
                    if isinstance(tool_input, dict):
                        reason_msg = (
                            tool_input.get("reason")
                            or tool_input.get("message")
                            or reason_msg
                        )
                except Exception:
                    pass
                self._emit_termination("stop_tool", reason_msg)
        except Exception:
            pass

        # Update live metrics for memory operations and evidence collection
        try:
            if tool_name == "mem0_memory" and success:
                # Increment memory operation count on successful store actions
                if isinstance(tool_input, dict):
                    action = tool_input.get("action") or tool_input.get("Action")
                    if action == "store":
                        self.memory_ops += 1
                        metadata = (
                            tool_input.get("metadata", {})
                            if isinstance(tool_input.get("metadata"), dict)
                            else {}
                        )
                        category = str(metadata.get("category", "")).lower()
                        if category in ("finding", "evidence"):
                            self.evidence_count += 1
        except Exception:
            # Never allow metrics update errors to disrupt output
            pass

        # Calculate duration if we have start time
        duration = None
        if tool_use_id and tool_use_id in self.tool_start_times:
            duration = time.time() - self.tool_start_times[tool_use_id]
            del self.tool_start_times[tool_use_id]  # Clean up

        # Defer tool_end emission until after output so reasoning can appear below output
        _deferred_tool_end = {
            "tool_name": tool_name,
            "tool_id": tool_use_id or self.last_tool_id,
            "success": success,
        }
        if duration is not None:
            _deferred_tool_end["duration"] = f"{duration:.2f}s"
        if self.in_swarm_operation and self.current_swarm_agent:
            _deferred_tool_end["swarm_agent"] = self.current_swarm_agent

        # Exit swarm mode when swarm tool completes
        # Check if we're exiting THE swarm tool specifically (not just any tool during swarm operation)
        # Compare tool IDs to ensure we're detecting the swarm tool itself ending
        is_swarm_tool_ending = (
            (tool_use_id == self.swarm_tool_id)
            if self.swarm_tool_id
            else (tool_name == "swarm")
        )

        if is_swarm_tool_ending and self.in_swarm_operation:
            logger.info(
                "Swarm tool completed, emitting swarm_complete and exiting swarm mode (iterations: %d)",
                self.swarm_iteration_count,
            )
            try:
                # Emit proper completion summary and reset swarm state
                self._track_swarm_complete()
            except Exception as e:
                logger.warning("Failed to emit swarm_complete on swarm tool end: %s", e)
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
                if tool_name == "shell":
                    clean_error = self._parse_shell_tool_output_detailed(
                        error_text.strip()
                    )
                elif tool_name == "http_request":
                    clean_error = self._parse_http_tool_output(error_text.strip())
                else:
                    clean_error = error_text.strip()
                combined_output += clean_error

                # Detect timeout specifics for clearer UI messaging
                timeout_seconds = None
                try:
                    # Common patterns: "timed out after 30 seconds", TimeoutExpired, etc.
                    import re

                    m = re.search(
                        r"timed out after\s+(\d+)\s*seconds?",
                        clean_error,
                        re.IGNORECASE,
                    )
                    if m:
                        timeout_seconds = int(m.group(1))
                except Exception:
                    pass
                requested_timeout = None
                try:
                    requested_timeout = (
                        tool_input.get("timeout")
                        if isinstance(tool_input, dict)
                        else None
                    )
                except Exception:
                    requested_timeout = None

                # Emit a structured error event with guidance if this looks like a timeout
                looks_like_timeout = (
                    ("timed out" in clean_error.lower())
                    or ("timeout" in clean_error.lower())
                    or ("TimeoutExpired" in clean_error)
                )
                if looks_like_timeout:
                    friendly_msg_lines = [
                        "Shell command timed out"
                        + (
                            f" after {timeout_seconds}s"
                            if timeout_seconds
                            else (
                                f" after {requested_timeout}s"
                                if requested_timeout
                                else ""
                            )
                        )
                        + ".",
                        "Tip: Re-run with a higher timeout (e.g., add 'timeout': 300 to the shell tool input) or set SHELL_DEFAULT_TIMEOUT in your environment.",
                    ]
                    self._emit_ui_event(
                        {
                            "type": "error",
                            "content": "\n".join(friendly_msg_lines),
                            "metadata": {
                                "type": "timeout",
                                "tool": tool_name,
                                "timeout": timeout_seconds or requested_timeout,
                            },
                        }
                    )

                # Emit single consolidated output event (raw/cleaned details)
                self._emit_ui_event(
                    {
                        "type": "output",
                        "content": combined_output.strip(),
                        "metadata": {"fromToolBuffer": True, "tool": tool_name},
                    }
                )

                # Now emit tool completion after consolidated output is sent
                self._emit_ui_event(
                    {
                        "type": "tool_invocation_end",
                        "success": success,
                        "tool_name": tool_name,
                    }
                )
                # Emit tool_end after output and invocation_end
                self._emit_ui_event({"type": "tool_end", **_deferred_tool_end})
                # Flush reasoning after tool end for swarm
                if self.in_swarm_operation and self.reasoning_buffer:
                    self._emit_accumulated_reasoning(force=True)

                # Mark that we've emitted output for this tool invocation
                if tool_use_id:
                    self.tool_use_output_emitted[tool_use_id] = True
            return

        # If we reach here, there was no buffered output, so process normally
        # But first check if output was already emitted
        if tool_use_id and self.tool_use_output_emitted.get(tool_use_id, False):
            return

        # Build output_text from content items (ensure defined before use)
        output_text = ""
        try:
            parts = []
            for item in content_items:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                elif isinstance(item, str):
                    parts.append(item)
            output_text = "\n".join(parts).strip()
        except Exception:
            # Fallback to stringified tool_result_dict if unexpected structure
            output_text = str(tool_result_dict)

        # Clean/parse known tool outputs
        if tool_name == "shell":
            output_text = self._parse_shell_tool_output_detailed(output_text)
        elif tool_name == "editor":
            output_text = self._parse_editor_tool_output(output_text)
        elif tool_name == "swarm" and "Status.FAILED" in output_text:
            # Override SDK's incorrect timeout metrics with cached actual metrics
            if hasattr(self, "last_swarm_metrics"):
                metrics = self.last_swarm_metrics
                output_text = f"""🎯 **Swarm Execution Timed Out**
📊 **Status:** Partial Success (Timeout after {metrics["duration"]})
🤖 **Agents Run:** {len(metrics["completed_agents"])}/{metrics["total_agents"]} agents
🔄 **Iterations Completed:** {metrics["total_iterations"]}
📈 **Tokens Used:** {metrics["total_tokens"]:,}

**Agent Activity:**"""
                for agent, activity in metrics.get("agent_activity", {}).items():
                    if activity["active"]:
                        output_text += f"\n• {agent}: {activity['steps']} steps ✓"
                    else:
                        output_text += f"\n• {agent}: Not started"

        if not output_text.strip():
            # For python_repl with no textual output, emit executed code and suppress generic message if a preview was shown
            try:
                if tool_name == "python_repl":
                    preview_emitted = bool(
                        tool_use_id
                        and tool_use_id
                        in getattr(self, "_python_preview_emitted", set())
                    )
                    code_input = self.tool_input_buffer.get(
                        tool_use_id or self.last_tool_id, {}
                    )
                    code_text = self._extract_code_from_input(code_input)
                    if code_text and code_text.strip():
                        code_event = {
                            "type": "tool_output",
                            "tool": "python_repl",
                            "status": "success",
                            "output": {"text": code_text},
                        }
                        if self.in_swarm_operation and self.current_swarm_agent:
                            code_event["swarm_agent"] = self.current_swarm_agent
                        self._emit_ui_event(code_event)
                    if preview_emitted:
                        if tool_use_id:
                            self.tool_use_output_emitted[tool_use_id] = True
                        # Emit tool completion without generic placeholder
                        self._emit_ui_event(
                            {
                                "type": "tool_invocation_end",
                                "success": success,
                                "tool_name": tool_name,
                            }
                        )
                        return
            except Exception:
                pass

            # Emit generic completion after code emission (if any)
            self._emit_ui_event(
                {
                    "type": "output",
                    "content": "Command completed",
                    "metadata": {"fromToolBuffer": True, "tool": tool_name},
                }
            )
            if tool_use_id:
                self.tool_use_output_emitted[tool_use_id] = True
            # Emit tool completion
            self._emit_ui_event(
                {
                    "type": "tool_invocation_end",
                    "success": success,
                    "tool_name": tool_name,
                }
            )
            # Emit tool_end after output and invocation_end
            self._emit_ui_event({"type": "tool_end", **_deferred_tool_end})
            if self.in_swarm_operation and self.reasoning_buffer:
                self._emit_accumulated_reasoning(force=True)
            return

        # Check if we already processed this exact output
        output_key = f"{tool_use_id or self.last_tool_id}:{hash(output_text.strip())}"
        if (
            hasattr(self, "_processed_outputs")
            and output_key in self._processed_outputs
        ):
            return  # Skip duplicate output

        # Initialize tracking if not exists
        if not hasattr(self, "_processed_outputs"):
            self._processed_outputs = set()

        # Agent tracking is handled through explicit handoff events only
        # No text parsing needed - it's unreliable and causes false positives

        # Mark this output as processed
        self._processed_outputs.add(output_key)
        # Mark meaningful output for this tool invocation
        if tool_use_id:
            self.tool_use_output_emitted[tool_use_id] = True
        # Mark all tool outputs with metadata to prevent truncation
        self._emit_ui_event(
            {
                "type": "output",
                "content": output_text.strip(),
                "metadata": {"fromToolBuffer": True, "tool": tool_name},
            }
        )

        # Emit tool completion with swarm context
        tool_inv_end_event = {
            "type": "tool_invocation_end",
            "success": success,
            "tool_name": tool_name,
        }
        if self.in_swarm_operation and self.current_swarm_agent:
            tool_inv_end_event["swarm_agent"] = self.current_swarm_agent
        self._emit_ui_event(tool_inv_end_event)
        # Emit tool_end after output and invocation_end
        self._emit_ui_event({"type": "tool_end", **_deferred_tool_end})
        # Mark tool no longer running and flush any pending reasoning now
        try:
            agent_key = self.current_swarm_agent or "main"
            if agent_key in self._tool_running_by_agent:
                self._tool_running_by_agent[agent_key] = False
        except Exception:
            pass
        if self.in_swarm_operation and self.reasoning_buffer:
            self._emit_accumulated_reasoning(force=True)

        # Ensure exactly one reasoning per step: if none occurred in this step, emit a brief rationale now
        try:
            if (not self.in_swarm_operation) and bool(
                getattr(self, "_reasoning_required_for_current_step", False)
            ):
                fallback = f"Reviewed {self.last_tool_name or 'tool'} results and determined next action."
                self._emit_ui_event({"type": "reasoning", "content": fallback})
                self._emitted_any_reasoning = True
                self._reasoning_emitted_since_last_step_header = True
                self._reasoning_required_for_current_step = False
        except Exception:
            pass

    def _parse_editor_tool_output(self, output_text: str) -> str:
        """Parse editor tool output - keep raw output to show what was changed."""
        if not output_text:
            return ""

        # Just return the raw output - user wants to see full details including Old/New strings
        # This shows exactly what was replaced which is important for understanding changes
        return output_text.strip()

    def _parse_shell_tool_output(self, output_text: str) -> str:
        """Minimal parsing of shell tool output - show raw output as requested."""
        if not output_text:
            return ""

        # Only remove duplicate command echoes that start with ⎿
        # since those are already shown in the tool invocation
        lines = output_text.split("\n")
        filtered_lines = []
        for line in lines:
            # Skip lines that are just command echoes (they start with ⎿)
            if line.strip().startswith("⎿"):
                continue
            filtered_lines.append(line)

        # Return the output with minimal filtering - user wants raw output
        return "\n".join(filtered_lines).strip()

    def _parse_shell_tool_output_detailed(self, output_text: str) -> str:
        """Detailed shell parsing - not currently used but kept for reference."""
        if not output_text:
            return ""

        # Extract command info and actual output/error content
        lines = output_text.split("\n")
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
            elif line.startswith("Execution Summary:") or line.startswith(
                "Total commands:"
            ):
                continue  # Skip wrapper headers
            elif in_output_section:
                actual_output.append(line)
            elif capture_error and line.strip():
                actual_output.append(line)

        # If we have extracted content, return it
        if actual_output:
            return "\n".join(actual_output).strip()

        # If no output/error captured but we have command info, provide context
        # Also extract any other information from the full text that might be useful
        if command:
            # Try to extract any additional info from the original text
            additional_info = []
            for line in lines:
                # Skip already processed lines and wrapper lines
                if (
                    not line.startswith("Execution Summary:")
                    and not line.startswith("Total commands:")
                    and not line.startswith("Command:")
                    and not line.startswith("Status:")
                    and not line.startswith("Exit Code:")
                    and not line.startswith("Output:")
                    and not line.startswith("Error:")
                    and not line.startswith("Successful:")
                    and not line.startswith("Failed:")
                    and line.strip()
                ):
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

    def _process_shell_output(
        self,
        output_text: str,
        _content_items: List,
        _status: str,
        tool_use_id: str = None,
    ) -> None:
        """Process shell command output with intelligent parsing and clean display."""
        # Skip if output was already emitted
        if tool_use_id and self.tool_use_output_emitted.get(tool_use_id, False):
            return

        if not output_text.strip():
            # Only emit generic completion if no prior meaningful output for this invocation
            self._emit_ui_event(
                {
                    "type": "output",
                    "content": "Command completed",
                    "metadata": {"fromToolBuffer": True, "tool": self.last_tool_name},
                }
            )
            if tool_use_id:
                self.tool_use_output_emitted[tool_use_id] = True
            return

        # Check if we already processed this exact output
        output_key = f"{tool_use_id or self.last_tool_id}:{hash(output_text.strip())}"
        if (
            hasattr(self, "_processed_outputs")
            and output_key in self._processed_outputs
        ):
            return  # Skip duplicate output

        # Initialize tracking if not exists
        if not hasattr(self, "_processed_outputs"):
            self._processed_outputs = set()

        # Parse and clean shell tool output
        clean_output = self._parse_shell_tool_output_detailed(output_text.strip())

        # Agent tracking handled through explicit events, not text parsing

        # Mark this output as processed
        self._processed_outputs.add(output_key)
        if tool_use_id:
            self.tool_use_output_emitted[tool_use_id] = True
        # Always mark shell output with metadata to prevent truncation
        self._emit_ui_event(
            {
                "type": "output",
                "content": clean_output,
                "metadata": {"fromToolBuffer": True, "tool": "shell"},
            }
        )

    def _process_http_output(
        self,
        output_text: str,
        _content_items: List,
        _status: str,
        tool_use_id: str = None,
    ) -> None:
        """Process HTTP request output with intelligent parsing and clean display."""
        # Skip if output was already emitted
        if tool_use_id and self.tool_use_output_emitted.get(tool_use_id, False):
            return

        if not output_text.strip():
            # Only emit generic completion if no prior meaningful output for this invocation
            self._emit_ui_event(
                {
                    "type": "output",
                    "content": "Request completed",
                    "metadata": {"fromToolBuffer": True, "tool": self.last_tool_name},
                }
            )
            if tool_use_id:
                self.tool_use_output_emitted[tool_use_id] = True
            return

        # Check if we already processed this exact output
        output_key = f"{tool_use_id or self.last_tool_id}:{hash(output_text.strip())}"
        if (
            hasattr(self, "_processed_outputs")
            and output_key in self._processed_outputs
        ):
            return  # Skip duplicate output

        # Initialize tracking if not exists
        if not hasattr(self, "_processed_outputs"):
            self._processed_outputs = set()

        # Parse and clean HTTP tool output
        clean_output = self._parse_http_tool_output(output_text.strip())

        # Agent tracking handled through explicit events, not text parsing

        # Mark this output as processed
        self._processed_outputs.add(output_key)
        if tool_use_id:
            self.tool_use_output_emitted[tool_use_id] = True
        # Always mark HTTP output with metadata to prevent truncation
        self._emit_ui_event(
            {
                "type": "output",
                "content": clean_output,
                "metadata": {"fromToolBuffer": True, "tool": "http_request"},
            }
        )

    def _collapse_repeated_sentences(self, text: str) -> str:
        """Collapse immediate duplicate sentences within a single chunk without reformatting whitespace.

        We keep the original spacing and newlines by extracting sentence-like segments
        including their trailing separator/whitespace and only dropping adjacent duplicates
        (compared with a normalized form).
        """
        try:
            s = str(
                text
            )  # DO NOT strip; leading/trailing spaces are meaningful for streaming joins
            if not s:
                return s
            # Grab segments ending with . ! ? : (plus following whitespace) or the tail
            parts = re.findall(r".*?(?:[\.!\?:](?=\s)|$)\s*", s, flags=re.S)
            out = []
            prev_norm = None
            for p in parts:
                if not p:
                    continue
                # Normalized form for comparison only
                n = re.sub(r"\s+", " ", p).strip().lower()
                if prev_norm is not None and n == prev_norm:
                    # skip immediate duplicate segment
                    continue
                out.append(p)  # preserve original spacing/newlines
                prev_norm = n
            return "".join(out)
        except Exception:
            return text

    def _accumulate_reasoning_text(self, text: str) -> None:
        """Accumulate reasoning text to prevent fragmentation."""
        if not text:
            return

        if text.strip().lower() == "reasoning":
            return

        # Collapse immediate repeated sentences within the same chunk
        try:
            text = self._collapse_repeated_sentences(text)
        except Exception:
            pass

        # Merge with previous fragment to avoid duplicate prefixes (e.g., "Great" then "Great! I can...")
        try:
            if self.reasoning_buffer:
                last_chunk = self.reasoning_buffer[-1]
                last_norm = str(last_chunk).strip()
                cur_norm = str(text).strip()
                if last_norm and cur_norm:
                    if cur_norm.startswith(last_norm) and len(cur_norm) > len(
                        last_norm
                    ):
                        # Replace last short fragment with the longer current one
                        self.reasoning_buffer[-1] = text
                    elif last_norm.startswith(cur_norm) and len(last_norm) > len(
                        cur_norm
                    ):
                        # Current is a shorter prefix of last; drop it
                        pass
                    else:
                        self.reasoning_buffer.append(text)
                else:
                    self.reasoning_buffer.append(text)
            else:
                self.reasoning_buffer.append(text)
        except Exception:
            # Fallback to simple append on any error
            self.reasoning_buffer.append(text)

        now = time.time()
        self.last_reasoning_time = now

        # In swarm mode, never flush based on timers/size; defer until tool_end or explicit completion
        if self.in_swarm_operation and self.current_swarm_agent:
            try:
                self._last_reasoning_flush = (
                    self._last_reasoning_flush
                )  # no-op keep attribute stable
            except Exception:
                self._last_reasoning_flush = 0
            return

    def _parse_swarm_output_for_events(self, output_text: str) -> None:
        """Parse swarm execution output to extract and emit missing agent events.

        Since SDK doesn't emit events for swarm agents due to callback limitations,
        we parse the structured output to identify agent transitions. We avoid
        hardcoded patterns and instead focus on the structured format that the
        swarm tool provides in its output.
        """
        if not output_text or not self.in_swarm_operation:
            return

        lines = output_text.split("\n")
        current_agent = None
        agent_content_buffer = []
        error_messages = []

        for line in lines:
            # Check for common error patterns
            if "requires root privileges" in line:
                error_messages.append(
                    "⚠️ Some tools require root privileges - agents may use alternative approaches"
                )
            elif "QUITTING!" in line:
                continue  # Skip redundant quit messages

            # Look for agent section headers in the structured output (e.g., "**RECON_SPECIALIST:**")
            # This is a reliable format from the swarm tool's structured output
            agent_match = re.match(r"\*\*([A-Z_]+):\*\*", line)
            if agent_match:
                # If we had a previous agent with content, emit it
                if current_agent and agent_content_buffer:
                    agent_output = "\n".join(agent_content_buffer)
                    if agent_output.strip():
                        # Emit the complete agent contribution as output
                        self._emit_ui_event(
                            {
                                "type": "output",
                                "content": f"[{current_agent.upper().replace('_', ' ')}]\n{agent_output}",
                                "metadata": {
                                    "swarm_agent": current_agent,
                                    "fromSwarmAgent": True,
                                },
                            }
                        )
                    agent_content_buffer = []

                # Start tracking new agent
                agent_name = agent_match.group(1).lower()
                if agent_name != current_agent:
                    current_agent = agent_name
                    # Update current swarm agent
                    if agent_name in self.swarm_agents:
                        self.current_swarm_agent = agent_name
                        if agent_name not in self.swarm_agent_steps:
                            self.swarm_agent_steps[agent_name] = 0
                        # Increment step count for this agent's contribution
                        self.swarm_agent_steps[agent_name] += 1

                        # Emit a structured event for agent transition
                        self._emit_ui_event(
                            {
                                "type": "swarm_agent_active",
                                "agent": agent_name,
                                "step": self.swarm_agent_steps[agent_name],
                                "metadata": {"fromSwarmOutput": True},
                            }
                        )
                        logger.debug(
                            f"Swarm agent transition detected: {agent_name} (step {self.swarm_agent_steps[agent_name]})"
                        )
                continue

            # Collect content for current agent (everything after their header)
            if current_agent and line.strip() and not line.startswith("**"):
                # Filter out repetitive error messages
                if "QUITTING!" not in line:
                    agent_content_buffer.append(line)

        # Handle any remaining buffered content
        if current_agent and agent_content_buffer:
            agent_output = "\n".join(agent_content_buffer)
            if agent_output.strip():
                self._emit_ui_event(
                    {
                        "type": "output",
                        "content": f"[{current_agent.upper().replace('_', ' ')}]\n{agent_output}",
                        "metadata": {
                            "swarm_agent": current_agent,
                            "fromSwarmAgent": True,
                        },
                    }
                )

        # Emit unique error messages if any
        if error_messages:
            for msg in set(error_messages):  # Use set to deduplicate
                self._emit_ui_event(
                    {
                        "type": "info",
                        "content": msg,
                        "metadata": {"swarm_error_context": True},
                    }
                )

    def _extract_swarm_reasoning_from_output(self, output_text: str) -> Optional[str]:
        """Extract reasoning patterns from swarm agent output.

        Swarm agents often embed their reasoning in their output.
        This method extracts it for better visibility.
        """
        if not output_text or not self.in_swarm_operation:
            return None

        # Common reasoning patterns in swarm agent outputs
        reasoning_indicators = [
            "need to",
            "should",
            "will",
            "found",
            "identified",
            "discovered",
            "detected",
            "analyzing",
            "checking",
            "scanning",
            "testing",
        ]

        lines = output_text.split("\n")
        reasoning_lines = []

        for line in lines[:10]:  # Check first 10 lines
            line_lower = line.lower().strip()
            if any(indicator in line_lower for indicator in reasoning_indicators):
                reasoning_lines.append(line.strip())
                if len(reasoning_lines) >= 2:  # Limit extraction
                    break

        if reasoning_lines:
            return " ".join(reasoning_lines)
        return None

    def _begin_reasoning_step_if_needed(self) -> None:
        """Pre-emit step header for reasoning-only cycles (non-swarm) once per cycle.

        Special case: Do NOT pre-emit for the initial reasoning (before any step starts).
        The initial reasoning should appear above [STEP 1], matching prior behavior.
        """
        try:
            if self.in_swarm_operation or self._reasoning_step_header_emitted:
                return
            # If no steps yet, do not emit a header here; the first tool will establish Step 1
            if self.current_step == 0:
                return
            # Increment global step and enforce step limit
            self.current_step += 1
            if self.current_step > self.max_steps:
                # Emit termination before raising
                self._emit_termination(
                    "step_limit",
                    f"Completed maximum allowed steps ({self.max_steps}/{self.max_steps}). Operation will now finalize.",
                )
                from modules.handlers.base import StepLimitReached

                raise StepLimitReached(
                    f"Step limit reached: {self.current_step}/{self.max_steps}"
                )
            # Emit the step header now so reasoning falls under the right step
            self._emit_step_header()
            self._reasoning_step_header_emitted = True
        except Exception:
            # Never break streaming on header pre-emit issues
            pass

    def _emit_accumulated_reasoning(self, force: bool = False) -> None:
        """Emit accumulated reasoning text as a complete block.

        In swarm mode, never emit reasoning while a tool is actively running
        for the current agent. This guarantees reasoning is rendered after
        the tool output (post tool_end), not between tool args and output.

        Args:
            force: If True, bypass per-step gating (used at step transitions and completion)
        """
        # Guard: if a tool is running for this agent in swarm, defer emission
        try:
            if self.in_swarm_operation:
                agent_key = self.current_swarm_agent or "main"
                if bool(self._tool_running_by_agent.get(agent_key, False)):
                    return
        except Exception:
            pass

        if not self.reasoning_buffer:
            return

        combined_reasoning = "".join(self.reasoning_buffer).strip()
        if not combined_reasoning:
            # Nothing meaningful; clear and return
            self.reasoning_buffer = []
            return

        # Per-step gating: at most one reasoning emission between step headers
        if (
            (not force)
            and self._any_step_header_emitted
            and self._reasoning_emitted_since_last_step_header
        ):
            # Keep buffer for next step header flush
            return

        # Include swarm agent metadata in reasoning event
        reasoning_event = {"type": "reasoning", "content": combined_reasoning}
        if self.in_swarm_operation and self.current_swarm_agent:
            # Add agent name to the event metadata only; avoid prefixing content to prevent duplication in UI
            reasoning_event["swarm_agent"] = self.current_swarm_agent

        self._emit_ui_event(reasoning_event)
        # Mark that we have emitted reasoning at least once in this operation
        self._emitted_any_reasoning = True
        self._reasoning_emitted_since_last_step_header = True
        # This step now has its reasoning
        try:
            self._reasoning_required_for_current_step = False
        except Exception:
            pass
        # Update last flush time for streaming control
        try:
            self._last_reasoning_flush = time.time()
        except Exception:
            self._last_reasoning_flush = 0

        # Clear after successful emission
        self.reasoning_buffer = []

        # Emit tool_preparation spinner after reasoning
        # This indicates the agent is selecting tools based on the reasoning
        self._emit_ui_event(
            {"type": "thinking", "context": "tool_preparation", "urgent": True}
        )

    def _emit_step_header(self) -> None:
        """Emit step header with current progress."""
        # Do not emit a step header before the first actionable step is established
        if not self.in_swarm_operation and self.current_step == 0:
            return
        # Reset per-step reasoning gate for the new step and flush buffered reasoning before header
        try:
            flushed_here = False
            # In swarm mode, do NOT pre-flush at headers; flush occurs after tool_end for proper ordering
            if (not self.in_swarm_operation) and self.reasoning_buffer:
                # Flush accumulated reasoning for the upcoming step (appears above header)
                self._emit_accumulated_reasoning(force=True)
                flushed_here = True
            if self._any_step_header_emitted:
                # Starting a new step interval: allow one reasoning emission again
                # BUT if we just flushed here, keep the emission gate set (True) to avoid a second
                # reasoning block within the same step interval.
                if not flushed_here:
                    self._reasoning_emitted_since_last_step_header = False
        except Exception:
            pass
        event = {
            "type": "step_header",
            "operation": self.operation_id,
            "duration": self._format_duration(time.time() - self.start_time),
        }

        # Don't show parent step number during swarm operations
        if not self.in_swarm_operation:
            event["step"] = self.current_step
            event["maxSteps"] = self.max_steps
            # Include total tool invocations for budget transparency (Sonnet 4.5 does parallel tools)
            event["totalTools"] = (
                sum(self.tool_counts.values()) if self.tool_counts else 0
            )

        # Add swarm agent information if in swarm operation
        if self.in_swarm_operation:
            event["is_swarm_operation"] = True
            if self.current_swarm_agent:
                event["swarm_agent"] = self.current_swarm_agent

                # Determine current total iterations across all agents BEFORE incrementing this agent's sub-step
                total_prev = (
                    sum(self.swarm_agent_steps.values())
                    if self.swarm_agent_steps
                    else 0
                )

                # Do not enforce iteration limits at the UI layer; the SDK controls completion.
                # Always emit the step header to reflect actual execution progress.

                # Track and increment sub-agent steps (now safe to increment)
                if self.current_swarm_agent not in self.swarm_agent_steps:
                    self.swarm_agent_steps[self.current_swarm_agent] = 1
                else:
                    self.swarm_agent_steps[self.current_swarm_agent] += 1

                # Compose event fields using SDK-aligned totals: total is computed as sum of agent sub-steps
                total_now = total_prev + 1
                current_agent_steps = self.swarm_agent_steps.get(
                    self.current_swarm_agent, 1
                )
                event["swarm_sub_step"] = current_agent_steps
                event["swarm_total_iterations"] = total_now
                event["agent_count"] = (
                    len(self.swarm_agents) if self.swarm_agents else 1
                )
            else:
                event["swarm_context"] = "Multi-Agent Operation"

        self._emit_ui_event(event)
        # This new step requires a reasoning emission (unless a pre-header flush already sufficed)
        try:
            if not flushed_here:
                self._reasoning_required_for_current_step = True
            else:
                # If we flushed reasoning just before the header, consider this step satisfied
                self._reasoning_required_for_current_step = False
        except Exception:
            pass
        # Mark that we have emitted at least one header
        self._any_step_header_emitted = True

        # Emit tool_preparation spinner after step header
        # Provides visual feedback while agent selects tools for this step
        self._emit_ui_event(
            {"type": "thinking", "context": "tool_preparation", "urgent": True}
        )

    def _emit_initial_metrics(self) -> None:
        """Emit initial metrics on startup."""
        self._emit_ui_event(
            {
                "type": "metrics_update",
                "metrics": {
                    "tokens": 0,
                    "cost": 0.0,
                    "duration": "0s",
                    "memoryOps": 0,
                    "evidence": 0,
                },
            }
        )

    def _start_metrics_thread(self) -> None:
        """Start a background thread for periodic metrics updates."""

        def update_metrics_loop():
            """Background loop to emit metrics every 5 seconds."""
            logger.debug("Metrics update thread started")
            update_count = 0
            while not self._stop_metrics:
                try:
                    # Wait 5 seconds between updates - balanced for UI responsiveness without log spam
                    time.sleep(5)

                    # Only emit if we're not stopped
                    if not self._stop_metrics and not self.should_stop():
                        update_count += 1
                        # Force emission every 6 updates (30 seconds) for duration updates
                        force_update = update_count % 6 == 0
                        self._emit_estimated_metrics(force=force_update)

                except Exception as e:
                    logger.error(f"Error in metrics update thread: {e}", exc_info=True)

        # Start the background thread
        self._metrics_thread = threading.Thread(target=update_metrics_loop, daemon=True)
        self._metrics_thread.start()
        logger.debug("Started periodic metrics update thread")

    def _stop_metrics_thread(self) -> None:
        """Stop the metrics update thread."""
        self._stop_metrics = True
        if self._metrics_thread and self._metrics_thread.is_alive():
            self._metrics_thread.join(timeout=1)

    def _extract_code_from_input(self, tool_input: Any) -> str:
        """Best-effort extraction of code from tool input for python_repl.

        Looks for common keys and returns a string.
        """
        try:
            if not tool_input:
                return ""
            if isinstance(tool_input, str):
                return tool_input
            if isinstance(tool_input, dict):
                val = (
                    tool_input.get("code")
                    or tool_input.get("source")
                    or tool_input.get("input")
                )
                if isinstance(val, str):
                    return val
                if val is not None:
                    try:
                        return json.dumps(val, indent=2)
                    except Exception:
                        return str(val)
                # As a fallback, return JSON of tool_input if it looks like code
                pretty = json.dumps(tool_input, indent=2)
                return pretty
            # Fallback stringification
            return str(tool_input)
        except Exception:
            return ""

    def _emit_estimated_metrics(self, force=False) -> None:
        """Emit metrics based on SDK token counts.

        Args:
            force: If True, emit even if metrics have not changed (for periodic duration updates)
        """
        # Try to get fresh metrics from stored agent reference if available
        if hasattr(self, "_last_agent") and self._last_agent:
            try:
                if hasattr(self._last_agent, "event_loop_metrics"):
                    usage = self._last_agent.event_loop_metrics.accumulated_usage
                    if usage:
                        self.sdk_input_tokens = usage.get(
                            "inputTokens", self.sdk_input_tokens
                        )
                        self.sdk_output_tokens = usage.get(
                            "outputTokens", self.sdk_output_tokens
                        )
            except Exception as e:
                logger.debug(f"Could not get metrics from agent: {e}")

        total_tokens = self.sdk_input_tokens + self.sdk_output_tokens

        # Build current metrics
        current_metrics = {
            "tokens": total_tokens,  # For Footer compatibility
            "inputTokens": self.sdk_input_tokens,
            "outputTokens": self.sdk_output_tokens,
            "totalTokens": total_tokens,
            "duration": self._format_duration(time.time() - self.start_time),
            "memoryOps": self.memory_ops,
            "evidence": self.evidence_count,
        }

        # Compare only meaningful fields (not duration which always changes)
        meaningful_fields = {
            "tokens": total_tokens,
            "memoryOps": self.memory_ops,
            "evidence": self.evidence_count,
        }

        # Only emit if meaningful metrics have changed, it's the first emission, or forced
        if (
            force
            or not hasattr(self, "_last_meaningful_metrics")
            or self._last_meaningful_metrics != meaningful_fields
        ):
            logger.debug(
                f"Emitting metrics: input={self.sdk_input_tokens}, output={self.sdk_output_tokens}, total={total_tokens}"
            )

            # Report both individual and total token counts for compatibility
            # Cost calculation is handled by the React app using config values
            self._emit_ui_event(
                {
                    "type": "metrics_update",
                    "metrics": current_metrics,
                }
            )

            # Store meaningful fields for comparison
            self._last_meaningful_metrics = meaningful_fields.copy()

    def _process_metrics(self, event_loop_metrics: Dict[str, Any]) -> None:
        """Process SDK metrics - only updates internal counters."""
        usage = event_loop_metrics.accumulated_usage

        # Update SDK token counts as authoritative source
        self.sdk_input_tokens = usage.get("inputTokens", 0)
        self.sdk_output_tokens = usage.get("outputTokens", 0)

        # Metrics emission is handled by the background thread
        # This method only updates the internal counters

    def _handle_completion(self) -> None:
        """Handle completion events."""
        self._emit_accumulated_reasoning(force=True)

        # End any active thinking indicator
        self._emit_ui_event({"type": "thinking_end"})

        # Emit explicit completion summary for UI/logs
        try:
            total_tokens = self.sdk_input_tokens + self.sdk_output_tokens
            self._emit_ui_event(
                {
                    "type": "operation_complete",
                    "operation": self.operation_id,
                    "duration": self._format_duration(time.time() - self.start_time),
                    "metrics": {
                        "inputTokens": self.sdk_input_tokens,
                        "outputTokens": self.sdk_output_tokens,
                        "totalTokens": total_tokens,
                        "memoryOps": self.memory_ops,
                        "evidence": self.evidence_count,
                    },
                }
            )
        except Exception:
            pass

        # Stop metrics thread on completion
        self._stop_metrics_thread()

    def _track_swarm_start(
        self, tool_input: Dict[str, Any], tool_id: str = None
    ) -> None:
        """Track swarm operation start. Emit a single, well-formed swarm_start.

        Agent Tracking Flow:
        1. Initial agent is set from the agents list (first agent)
        2. Agent changes are tracked ONLY through explicit handoff_to_agent events
        3. No text parsing is used - it's unreliable and causes false positives
        4. The current_swarm_agent is displayed in step headers and events
        """
        logger.debug("=== SWARM START TRACKING ===")
        logger.debug(f"Tool ID: {tool_id}")

        if not isinstance(tool_input, dict):
            tool_input = {}
        agents = tool_input.get("agents", [])
        task = tool_input.get("task", "")

        logger.debug(f"Tool input keys: {list(tool_input.keys())}")
        logger.debug(f"Task: {task or 'No task'}")
        logger.debug(
            f"Number of agents: {len(agents) if isinstance(agents, list) else 0}"
        )
        logger.debug(f"Max handoffs: {tool_input.get('max_handoffs')}")
        logger.debug(f"Max iterations: {tool_input.get('max_iterations')}")
        logger.debug(f"Execution timeout: {tool_input.get('execution_timeout')}")

        # Store the swarm tool's ID for proper completion detection
        if tool_id:
            self.swarm_tool_id = tool_id

        # Mark swarm start time and token baseline for accurate metrics
        try:
            self._swarm_start_time = time.time()
            self._swarm_tokens_start = int(self.sdk_input_tokens) + int(
                self.sdk_output_tokens
            )
        except Exception:
            # Fallbacks if metrics not yet available
            self._swarm_start_time = time.time()
            self._swarm_tokens_start = 0

        # Build agent names and details lists
        agent_names: List[str] = []
        agent_details: List[Dict[str, Any]] = []

        if isinstance(agents, list):
            for i, agent in enumerate(agents):
                if isinstance(agent, dict):
                    name = agent.get("name") or agent.get("role") or f"agent_{i + 1}"
                    system_prompt = agent.get("system_prompt", "")
                    tools = agent.get("tools", [])

                    agent_names.append(name)
                    # Extract model info from model_settings or use parent config
                    model_settings = agent.get("model_settings", {})
                    model_provider = agent.get("model_provider", "bedrock")

                    # Prefer per-agent model_id when provided; fall back to configured swarm model for display
                    agent_model_id = None
                    try:
                        # Common locations for per-agent model identifiers
                        agent_model_id = model_settings.get(
                            "model_id"
                        ) or model_settings.get("model")
                    except Exception:
                        agent_model_id = None
                    model_id = agent_model_id or self.swarm_model_id

                    agent_details.append(
                        {
                            "name": name,
                            "role": system_prompt,  # Full system prompt as role
                            "system_prompt": system_prompt,  # Keep for compatibility
                            "tools": tools if isinstance(tools, list) else [],
                            "model_provider": model_provider,
                            "model_id": model_id,
                            "temperature": model_settings.get("params", {}).get(
                                "temperature", 0.7
                            ),
                        }
                    )
                elif isinstance(agent, str):
                    agent_names.append(agent)
                    agent_details.append(
                        {
                            "name": agent,
                            "system_prompt": "",
                            "tools": [],
                            "model_provider": "default",
                            "model_id": "default",
                        }
                    )

        # Skip emitting if we have no meaningful content yet (pre-stream empty input)
        if not agent_names and not task:
            logger.debug("Skipping swarm_start - no agents and no task")
            return

        # Skip emitting if agents list is empty but task exists (partial/empty agent data)
        if task and not agent_names:
            logger.debug(
                "Skipping swarm_start emission - task exists but no agents yet"
            )
            return

        logger.debug(f"Found {len(agent_names)} agents: {agent_names}")
        for i, detail in enumerate(agent_details):
            logger.debug(
                f"Agent {i + 1} '{detail['name']}': tools={detail.get('tools', [])}"
            )

        # Compute signature to dedupe repeated emissions
        signature = json.dumps({"agents": agent_names, "task": task}, sort_keys=True)
        if self._last_swarm_signature == signature:
            return

        # Check if this is a NEW swarm operation or an update to existing
        is_new_swarm = not self.in_swarm_operation
        logger.debug(
            f"Is new swarm: {is_new_swarm}, Currently in swarm: {self.in_swarm_operation}"
        )

        # Update state
        self.in_swarm_operation = True
        self.swarm_agents = agent_names
        self.current_swarm_agent = agent_names[0] if agent_names else None
        logger.debug(f"Set current swarm agent to: {self.current_swarm_agent}")

        # Only reset counters for NEW swarm operations
        if is_new_swarm:
            logger.debug("Resetting swarm counters for NEW swarm operation")
            self.swarm_handoff_count = 0
            # Reset sub-agent step tracking for new swarm
            self.swarm_agent_steps = {}
            # Only reset iteration count for NEW swarm
            self.swarm_iteration_count = 0
        else:
            logger.debug(
                f"Continuing existing swarm - handoffs: {self.swarm_handoff_count}, iterations: {self.swarm_iteration_count}"
            )

        # Build tool-to-agent mapping for intelligent agent detection
        self.swarm_agent_tools = {}
        self.swarm_agent_details = agent_details
        logger.debug("Building tool-to-agent mapping:")
        for agent_detail in agent_details:
            agent_name = agent_detail.get("name")
            agent_tools = agent_detail.get("tools", [])
            if agent_name and agent_tools:
                self.swarm_agent_tools[agent_name] = agent_tools
                logger.debug(
                    f"  Agent '{agent_name}': {len(agent_tools)} tools - {agent_tools}"
                )

        # Initialize step counter for first agent if new
        if (
            self.current_swarm_agent
            and self.current_swarm_agent not in self.swarm_agent_steps
        ):
            self.swarm_agent_steps[self.current_swarm_agent] = 0

        # Set max iterations and handoffs from tool input (no hardcoded defaults)
        self.swarm_max_iterations = None
        try:
            if (
                "max_iterations" in tool_input
                and tool_input.get("max_iterations") is not None
            ):
                self.swarm_max_iterations = int(tool_input.get("max_iterations"))
        except Exception:
            self.swarm_max_iterations = None
        try:
            self.swarm_max_handoffs = (
                int(tool_input.get("max_handoffs"))
                if tool_input.get("max_handoffs") is not None
                else None
            )
        except Exception:
            self.swarm_max_handoffs = None
        try:
            self.swarm_max_handoffs = int(tool_input.get("max_handoffs", 20))
        except Exception:
            self.swarm_max_handoffs = 20

        # Emit a single swarm_start UI event with full agent details
        try:
            event = {
                "type": "swarm_start",
                "agent_names": agent_names,
                "agent_count": len(agent_names),
                "agent_details": agent_details,
                "task": task,
            }
            # Include config fields only if provided by tool input
            if tool_input.get("max_handoffs") is not None:
                event["max_handoffs"] = tool_input.get("max_handoffs")
            if tool_input.get("max_iterations") is not None:
                event["max_iterations"] = tool_input.get("max_iterations")
            if tool_input.get("node_timeout") is not None:
                event["node_timeout"] = tool_input.get("node_timeout")
            if tool_input.get("execution_timeout") is not None:
                event["execution_timeout"] = tool_input.get("execution_timeout")
            logger.debug(f"Emitting swarm_start event with {len(agent_names)} agents")
            self._emit_ui_event(event)
            logger.debug("=== SWARM START TRACKING COMPLETE ===")
        except Exception as e:
            logger.warning("Failed to emit swarm_start: %s", e)
            logger.debug(f"Exception details: {str(e)}", exc_info=True)

    def _detect_swarm_agent_from_callback(
        self, kwargs: Dict[str, Any]
    ) -> Optional[str]:
        """Detect active swarm agent from callback context.

        The SDK passes agent information in callbacks - we can use this
        to reliably determine which swarm agent is active.
        """
        if not self.in_swarm_operation:
            return None

        # Check for agent reference in the callback
        agent = kwargs.get("agent")
        if agent:
            # Try to get agent name from object attributes
            if hasattr(agent, "name"):
                agent_name = str(agent.name)
                # Check if this matches any of our known swarm agents
                for known_agent in self.swarm_agents:
                    # Compare normalized names (lowercase, underscores)
                    normalized_known = known_agent.lower().replace("-", "_")
                    normalized_name = (
                        agent_name.lower().replace("-", "_").replace(" ", "_")
                    )
                    if normalized_known in normalized_name:
                        logger.debug(
                            f"Detected swarm agent from callback agent.name: {known_agent}"
                        )
                        return known_agent

            # Try to get from agent ID or other attributes
            if hasattr(agent, "id"):
                agent_id = str(agent.id)
                for known_agent in self.swarm_agents:
                    if known_agent.lower() in agent_id.lower():
                        logger.debug(
                            f"Detected swarm agent from callback agent.id: {known_agent}"
                        )
                        return known_agent

        # Check for agent context in message metadata
        message = kwargs.get("message")
        if message and isinstance(message, dict):
            # Check metadata for agent information
            metadata = message.get("metadata", {})
            if isinstance(metadata, dict):
                agent_info = (
                    metadata.get("agent")
                    or metadata.get("agent_name")
                    or metadata.get("source")
                )
                if agent_info:
                    agent_str = str(agent_info).lower()
                    for known_agent in self.swarm_agents:
                        if known_agent.lower() in agent_str:
                            logger.debug(
                                f"Detected swarm agent from message metadata: {known_agent}"
                            )
                            return known_agent

        return None

    def _infer_active_swarm_agent(self, tool_name: str) -> Optional[str]:
        """Intelligently infer which swarm agent is active based on tool usage.

        Each swarm agent has specific tools. When we see a tool invocation,
        we can determine which agent must be active.
        """
        if not self.in_swarm_operation or not self.swarm_agent_tools:
            return None

        # Check which agents have this tool
        possible_agents = []
        for agent_name, tools in self.swarm_agent_tools.items():
            if tool_name in tools:
                possible_agents.append(agent_name)

        if len(possible_agents) == 1:
            # Only one agent has this tool - we found our agent!
            logger.debug(
                f"Swarm agent detected via tool {tool_name}: {possible_agents[0]}"
            )
            return possible_agents[0]
        elif len(possible_agents) > 1:
            # Multiple agents have this tool - use heuristics
            # Prefer the current agent if it's one of the possibilities
            if self.current_swarm_agent in possible_agents:
                return self.current_swarm_agent
            # Otherwise return the first possibility
            logger.debug(
                f"Multiple agents have tool {tool_name}: {possible_agents}, using {possible_agents[0]}"
            )
            return possible_agents[0]

        # Tool not found in any agent's toolkit - might be a general tool
        logger.debug(
            f"Tool {tool_name} not found in agent toolkits, keeping current agent"
        )
        return self.current_swarm_agent

    def _track_agent_handoff(self, tool_input: Dict[str, Any]) -> None:
        """Track agent handoffs in swarm and emit appropriate events."""
        if self.in_swarm_operation:
            if not isinstance(tool_input, dict):
                tool_input = self._parse_tool_input_from_stream(tool_input)
                if not isinstance(tool_input, dict):
                    tool_input = {}

            # Normalize agent field from either agent_name or handoff_to
            if not tool_input.get("agent_name") and tool_input.get("handoff_to"):
                tool_input["agent_name"] = tool_input.get("handoff_to")

            agent_name = tool_input.get("agent_name", "")
            message = tool_input.get("message", "")
            message_preview = message[:100] + "..." if len(message) > 100 else message

            from_agent = self.current_swarm_agent or "unknown"

            # Normalize agent name to match our stored agent names
            if agent_name:
                # Find matching agent from our known agents
                normalized_new = agent_name.lower().replace("-", "_").replace(" ", "_")
                for known_agent in self.swarm_agents:
                    normalized_known = known_agent.lower().replace("-", "_")
                    if (
                        normalized_known == normalized_new
                        or normalized_known in normalized_new
                    ):
                        agent_name = known_agent
                        break

                # Update current agent
                self.current_swarm_agent = agent_name
                self.swarm_handoff_count += 1
                # Initialize step count for new agent if not exists
                if agent_name not in self.swarm_agent_steps:
                    self.swarm_agent_steps[agent_name] = 0
                # Do not emit UI termination on handoff limits; SDK enforces limits internally.
            else:
                # Log warning but don't break the flow
                logger.warning("Handoff with empty agent_name from %s", from_agent)

            self._emit_ui_event(
                {
                    "type": "swarm_handoff",
                    "from_agent": from_agent,
                    "to_agent": agent_name,
                    "message": message_preview,
                    "shared_context": tool_input.get("context", {}),
                }
            )

            # Mark subsequent steps clearly by emitting a new step header on handoff
            try:
                # Only increment global step count when not in swarm operation
                if not self.in_swarm_operation:
                    self.current_step += 1
                # Guard against step limit overflow similar to initial header emission
                # Don't enforce step limit for swarm agents - they have their own limits
                if not self.in_swarm_operation and self.current_step > self.max_steps:
                    from modules.handlers.base import StepLimitReached

                    # Emit termination reason before raising
                    self._emit_termination(
                        "step_limit",
                        f"Step limit reached: {self.current_step}/{self.max_steps}",
                    )
                    raise StepLimitReached(
                        f"Step limit exceeded: {self.current_step}/{self.max_steps}"
                    )
                elif self.current_step <= self.max_steps or self.in_swarm_operation:
                    self._emit_step_header()
            except Exception as _:
                # Do not break stream on header failure
                pass

    def _track_swarm_complete(self) -> None:
        """Track swarm completion with enhanced metrics."""
        if self.in_swarm_operation:
            final_agent = self.current_swarm_agent or "unknown"
            # Compute duration relative to swarm start if available
            try:
                start_ref = getattr(self, "_swarm_start_time", None) or self.start_time
            except Exception:
                start_ref = self.start_time
            duration = time.time() - start_ref

            # Calculate agent completion stats
            completed_agents = [
                agent for agent in self.swarm_agents if agent in self.swarm_agent_steps
            ]

            # Build detailed agent activity summary
            agent_activity = {}
            for agent in self.swarm_agents:
                if agent in self.swarm_agent_steps:
                    agent_activity[agent] = {
                        "steps": self.swarm_agent_steps[agent],
                        "active": agent in completed_agents,
                    }

            # Compute token delta for this swarm (best-effort)
            try:
                current_tokens = int(self.sdk_input_tokens) + int(
                    self.sdk_output_tokens
                )
                baseline = getattr(self, "_swarm_tokens_start", 0)
                token_delta = max(0, current_tokens - baseline)
            except Exception:
                token_delta = self.sdk_input_tokens + self.sdk_output_tokens

            # Cache swarm metrics for potential timeout override
            # Use SDK-aligned iterations: sum of emitted agent sub-steps during swarm
            total_iterations = (
                sum(self.swarm_agent_steps.values()) if self.swarm_agent_steps else 0
            )

            self.last_swarm_metrics = {
                "final_agent": final_agent,
                # Align with SDK: execution_count equals total iterations (node executions)
                "execution_count": total_iterations,
                "handoff_count": self.swarm_handoff_count,
                "duration": f"{duration:.1f}s",
                "total_tokens": token_delta,
                "completed_agents": completed_agents,
                "total_agents": len(self.swarm_agents),
                "agent_activity": agent_activity,
                "total_iterations": total_iterations,
                "total_steps": total_iterations,
            }

            self._emit_ui_event(
                {
                    "type": "swarm_complete",
                    **self.last_swarm_metrics,
                    "total_steps": (
                        sum(self.swarm_agent_steps.values())
                        if self.swarm_agent_steps
                        else 0
                    ),  # Sum of all agent steps
                }
            )

            # Reset swarm state
            logger.debug("Resetting swarm tracking state")
            self.in_swarm_operation = False
            self.swarm_agents = []
            self.current_swarm_agent = None
            self.swarm_handoff_count = 0
            self.swarm_agent_steps = {}
            # No need to track a separate swarm_iteration_count; totals are derived from agent sub-steps
            self.swarm_tool_id = None
            logger.debug("=== SWARM COMPLETE TRACKING DONE ===")

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
                            return (
                                parsed
                                if isinstance(parsed, dict)
                                else {"value": parsed}
                            )
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
            return f"{int(seconds / 60)}m {int(seconds % 60)}s"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}h {mins}m"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}d {hours}h"

    # Report generation methods
    def ensure_report_generated(
        self, agent, target: str, objective: str, module: str = None
    ) -> None:
        """Ensure report is generated only once."""
        if not self._report_generated:
            self.generate_final_report(agent, target, objective, module)

    def generate_final_report(
        self, agent, target: str, objective: str, module: str = None
    ) -> None:
        """Generate final security assessment report.

        If no memories/evidence were collected, skip report generation to avoid
        producing an empty or meaningless report.
        """
        if self._report_generated:
            return

        try:
            self._report_generated = True

            # If nothing was persisted to memory/evidence, skip report generation
            try:
                mem_ops = int(getattr(self, "memory_ops", 0) or 0)
                ev_count = int(getattr(self, "evidence_count", 0) or 0)
            except Exception:
                mem_ops, ev_count = 0, 0

            if mem_ops <= 0 and ev_count <= 0:
                # Inform the UI and conclude cleanly without generating a report
                try:
                    self._emit_ui_event(
                        {
                            "type": "output",
                            "content": "◆ No memories or evidence were collected during this operation. Skipping report generation.",
                        }
                    )
                    # Emit completion marker for a clean UI transition
                    self._emit_ui_event(
                        {
                            "type": "assessment_complete",
                            "operation_id": self.operation_id,
                            "report_path": None,
                        }
                    )
                except Exception:
                    pass
                return

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
                {
                    "type": "output",
                    "content": "\n◆ Generating comprehensive security assessment report...",
                }
            )

            # Prepare config data for report generation
            # Build tools_used list reflecting true usage counts for accurate reporting
            try:
                if getattr(self, "tool_counts", None):
                    tools_used_list = []
                    # Deterministic order for reproducibility
                    for name in sorted(self.tool_counts.keys()):
                        count = int(self.tool_counts.get(name, 0) or 0)
                        if count > 0:
                            tools_used_list.extend([name] * count)
                else:
                    tools_used_list = list(self.tools_used)
            except Exception:
                tools_used_list = list(self.tools_used)

            # Get the main model ID from config for report generation
            model_id = None
            try:
                from modules.config.manager import get_config_manager

                cfg = get_config_manager()
                llm_cfg = cfg.get_llm_config(provider)
                model_id = llm_cfg.model_id
            except Exception:
                pass

            config_data = json.dumps(
                {
                    "steps_executed": self.current_step,
                    "tools_used": tools_used_list,
                    "provider": provider,
                    "module": module,
                    "model_id": model_id,  # Pass main model for reports
                }
            )

            report_content = generate_security_report(
                target=target,
                objective=objective,
                operation_id=self.operation_id,
                config_data=config_data,
            )

            # Accept any non-empty report content
            if isinstance(report_content, str) and report_content.strip():
                try:
                    from pathlib import Path

                    from modules.handlers.utils import (
                        get_output_path,
                        sanitize_target_name,
                    )

                    target_name = sanitize_target_name(target)
                    output_dir = get_output_path(
                        target_name, self.operation_id, "", "./outputs"
                    )

                    # Create output directory if it doesn't exist
                    Path(output_dir).mkdir(parents=True, exist_ok=True)

                    # Save report as markdown file
                    report_path = os.path.join(
                        output_dir, "security_assessment_report.md"
                    )
                    with open(report_path, "w", encoding="utf-8") as f:
                        f.write(report_content)

                    # Emit report content - truncate if needed to stay under IPC buffer limits
                    # Docker/IPC drops events >50KB silently. Truncate to ~200 lines (~12KB) and
                    # let React's StreamDisplay.tsx handle display/truncation from there
                    try:
                        if len(report_content) > 15000:  # 15KB threshold for IPC safety
                            # Truncate to first 200 lines to ensure event reaches React
                            lines = report_content.split("\n")
                            truncated_content = "\n".join(lines[:200])
                            logger.info(
                                f"Report truncated from {len(lines)} to 200 lines for IPC transmission ({len(report_content)} -> {len(truncated_content)} chars)"
                            )
                            self._emit_ui_event(
                                {"type": "report_content", "content": truncated_content}
                            )
                        else:
                            self._emit_ui_event(
                                {"type": "report_content", "content": report_content}
                            )
                    except Exception as e:
                        logger.warning(f"Failed to emit report content: {e}")
                        self._emit_ui_event(
                            {
                                "type": "output",
                                "content": f"Report generated: {report_path}",
                            }
                        )

                    # Also emit file path information for reference
                    self._emit_ui_event(
                        {
                            "type": "output",
                            "content": f"\n{'━' * 80}\n\nASSESSMENT COMPLETE\n\nREPORT ALSO SAVED TO:\n  • {report_path}\n\nMEMORY STORED IN:\n  • {output_dir}/memory/\n\nOPERATION LOGS:\n  • {os.path.join(output_dir, 'cyber_operations.log')}\n\n{'━' * 80}\n",
                        }
                    )

                    # Emit a completion event for clean UI transition
                    self._emit_ui_event(
                        {
                            "type": "assessment_complete",
                            "operation_id": self.operation_id,
                            "report_path": report_path,
                        }
                    )

                    if hasattr(self.emitter, "flush_immediate"):
                        self.emitter.flush_immediate()

                    logger.info("Report saved to %s", report_path)

                except Exception as save_error:
                    logger.warning("Could not save report to file: %s", save_error)
                    self._emit_ui_event(
                        {
                            "type": "output",
                            "content": f"\n⚠️ Note: Report could not be saved to file: {save_error}",
                        }
                    )
            else:
                logger.info(
                    "Report generation skipped - no evidence collected during operation"
                )

        except Exception as e:
            logger.error("Error generating final report: %s", e)
            self._emit_ui_event(
                {"type": "error", "content": f"Error generating report: {str(e)}"}
            )

    # Evaluation methods
    def trigger_evaluation_on_completion(self) -> None:
        """Trigger evaluation after operation completion."""
        from modules.evaluation.manager import EvaluationManager, TraceType

        verbose_eval = os.getenv("VERBOSE", "false").lower() == "true"

        if verbose_eval:
            logger.debug(
                "EVAL_DEBUG: trigger_evaluation_on_completion called for operation %s",
                self.operation_id,
            )

        # Check if observability is enabled first - evaluation requires Langfuse infrastructure
        if os.getenv("ENABLE_OBSERVABILITY", "false").lower() != "true":
            logger.debug(
                "Observability is disabled - skipping evaluation (requires Langfuse)"
            )
            if verbose_eval:
                logger.debug("EVAL_DEBUG: Skipping evaluation - observability disabled")
            return

        # Default evaluation to same setting as observability
        default_evaluation = os.getenv("ENABLE_OBSERVABILITY", "false")
        if os.getenv("ENABLE_AUTO_EVALUATION", default_evaluation).lower() != "true":
            logger.debug("Auto-evaluation is disabled, skipping")
            if verbose_eval:
                logger.debug(
                    "EVAL_DEBUG: Auto-evaluation disabled via ENABLE_AUTO_EVALUATION=false"
                )
            return

        try:
            if verbose_eval:
                logger.debug(
                    "EVAL_DEBUG: Starting evaluation process for operation %s",
                    self.operation_id,
                )

            eval_manager = EvaluationManager(operation_id=self.operation_id)

            eval_manager.register_trace(
                trace_id=self.operation_id,
                trace_type=TraceType.MAIN_AGENT,
                name=f"Security Assessment - {self.operation_id}",
                session_id=self.operation_id,
            )

            if verbose_eval:
                logger.debug("EVAL_DEBUG: Registered trace for evaluation")

            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            logger.info("Starting evaluation for operation %s", self.operation_id)
            if verbose_eval:
                logger.debug("EVAL_DEBUG: Starting async evaluation loop")

            results = loop.run_until_complete(eval_manager.evaluate_all_traces())

            if results:
                logger.info(
                    "Evaluation completed successfully: %d traces evaluated",
                    len(results),
                )
                if verbose_eval:
                    logger.debug("EVAL_DEBUG: Evaluation results: %s", results)
                self._emit_ui_event(
                    {
                        "type": "evaluation_complete",
                        "operation_id": self.operation_id,
                        "traces_evaluated": len(results),
                    }
                )
            else:
                logger.warning("No evaluation results returned")
                if verbose_eval:
                    logger.debug(
                        "EVAL_DEBUG: No evaluation results - check trace finding and metric evaluation"
                    )

        except Exception as e:
            logger.warning("Evaluation failed but continuing operation: %s", str(e))
            if verbose_eval:
                logger.debug(
                    "EVAL_DEBUG: Full evaluation exception details", exc_info=True
                )
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
            step_limit_reached = self.current_step > self.max_steps

        return MockState()

    def should_stop(self) -> bool:
        """Check if execution should stop.

        Also emits a termination_reason event once when a stop condition is detected.
        """
        try:
            if not self._termination_emitted:
                # Emit step limit termination immediately when exceeded
                if self.current_step > self.max_steps:
                    self._emit_termination(
                        "step_limit",
                        f"Step limit reached: {self.current_step}/{self.max_steps}",
                    )
                # For stop tool, do not emit here; termination is emitted after tool result
        except Exception:
            pass
        return self._stop_tool_used or (self.current_step > self.max_steps)

    def has_reached_limit(self) -> bool:
        """Check if step limit reached."""
        return self.current_step > self.max_steps

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
        # Build current metrics for summary
        total_tokens = self.sdk_input_tokens + self.sdk_output_tokens
        current_metrics = {
            "inputTokens": self.sdk_input_tokens,
            "outputTokens": self.sdk_output_tokens,
            "totalTokens": total_tokens,
        }

        return {
            "total_steps": self.current_step,
            "tools_created": len(self.tools_used),
            "evidence_collected": self.evidence_count,
            "memory_operations": self.memory_ops,
            "capability_expansion": list(self.tools_used),
            "memory_ops": self.memory_ops,
            "evidence_count": self.evidence_count,
            "duration": self._format_duration(time.time() - self.start_time),
            "metrics": current_metrics,
        }
