"""
Tool-specific event emitters for the React UI bridge.

This module contains specialized event emitters for different tool types,
converting tool inputs and outputs into structured events for the React UI.
"""

from typing import Any, Callable, Dict


class ToolEventEmitter:
    """Handles emission of tool-specific events for the React UI."""

    def __init__(self, emit_func: Callable[[Dict[str, Any]], None]):
        """
        Initialize the tool event emitter.

        Args:
            emit_func: Function to emit UI events
        """
        self.emit_ui_event = emit_func

    def emit_tool_specific_events(self, tool_name: str, tool_input: Any) -> None:
        """
        Route tool inputs to appropriate specialized emitters.

        Args:
            tool_name: Name of the tool being executed
            tool_input: Input parameters for the tool
        """
        emitter_map = {
            "shell": self._emit_shell_commands,
            "mem0_memory": self._emit_memory_operation,
            "http_request": self._emit_http_request,
            "file_write": self._emit_file_write,
            "editor": self._emit_editor_operation,
            "swarm": self._emit_swarm_operation,
            "python_repl": self._emit_python_repl,
            "load_tool": self._emit_load_tool,
            "stop": self._emit_stop_tool,
            "generate_security_report": self._emit_report_generator,
            "handoff_to_agent": self._emit_agent_handoff,
            "complete_swarm_task": self._emit_swarm_complete,
            "think": self._emit_think_operation,
        }

        emitter = emitter_map.get(tool_name)
        if emitter:
            # Specific emitters only need tool_input
            emitter(tool_input)
        else:
            # Generic emitter needs tool_name and tool_input
            self._emit_generic_tool_params(tool_name, tool_input)

    def _emit_shell_commands(self, tool_input: Any) -> None:
        """Emit shell commands for display."""
        # StreamDisplay renders shell commands directly from the 'tool_start' event's tool_input.
        # Emitting separate 'command' events here causes duplicate "⎿" lines.
        return

    def _emit_memory_operation(self, tool_input: Any) -> None:
        """Emit memory operation details."""
        # Skip redundant metadata - tool formatter already shows this

    def _emit_http_request(self, tool_input: Any) -> None:
        """Emit HTTP request details."""
        if isinstance(tool_input, dict):
            method = tool_input.get("method", "GET")
            url = tool_input.get("url", "")
            # Emit structured event for request tracking (not for display)
            if url:
                self.emit_ui_event(
                    {"type": "http_request_start", "method": method, "url": url}
                )

    def _emit_file_write(self, tool_input: Any) -> None:
        """Emit file write operation details."""
        # Skip redundant metadata - tool formatter already shows this

    def _emit_editor_operation(self, tool_input: Any) -> None:
        """No-op for editor details.

        Rationale: arguments for editor operations are already rendered from the
        tool_start payload. Emitting an additional metadata event here caused
        duplicate and occasionally out-of-order argument lines. Keeping a single
        source of truth (tool_start) avoids duplication and preserves ordering.
        """
        return

    def _emit_generic_tool_params(self, tool_name: str, tool_input: Any) -> None:  # pylint: disable=unused-argument
        """Emit generic tool parameters for tools without specialized handlers."""
        # REMOVED: Generic tools no longer emit metadata events
        # The StreamDisplay component already properly formats tool parameters
        # from the tool_start event in the default case. Emitting metadata here
        # causes duplicate display of the same information.
        # This was the root cause of the duplicate tool parameter display issue.
        pass

    def _emit_swarm_operation(self, tool_input: Any) -> None:
        """Emit swarm orchestration details."""
        if isinstance(tool_input, dict):
            agents = tool_input.get("agents", [])
            task = tool_input.get("task", "")

            # Don't emit empty swarm events - these are invalid and cause UI spam
            if not agents and not task:
                return

            # Get agent specifications
            agent_details = []
            for i, agent in enumerate(agents):
                if isinstance(agent, dict):
                    # Get name or generate default
                    name = agent.get("name", f"agent_{i + 1}")

                    # Get full system prompt without parsing
                    system_prompt = agent.get("system_prompt", "")

                    # Get tools list
                    tools = agent.get("tools", [])
                    if not isinstance(tools, list):
                        tools = []

                    # Get model info with defaults
                    model_provider = agent.get("model_provider", "default")
                    model_settings = agent.get("model_settings", {})
                    if isinstance(model_settings, dict):
                        model_id = model_settings.get("model_id", "default")
                    else:
                        model_id = "default"

                    detail = {
                        "name": str(name),
                        "system_prompt": str(system_prompt),
                        "tools": [str(t) for t in tools],
                        "model_provider": str(model_provider),
                        "model_id": str(model_id),
                    }
                    agent_details.append(detail)
                elif isinstance(agent, str):
                    # Handle simple string agent definitions
                    agent_details.append(
                        {
                            "name": agent,
                            "system_prompt": "",
                            "tools": [],
                            "model_provider": "default",
                            "model_id": "default",
                        }
                    )

            # Only emit swarm start event if we have valid data
            if len(agent_details) > 0 or task:
                # Extract agent names for backward compatibility
                agent_names = [
                    agent.get("name", f"agent_{i}")
                    for i, agent in enumerate(agent_details)
                ]

                # Emit rich swarm_start event with both names and full details
                self.emit_ui_event(
                    {
                        "type": "swarm_start",
                        "task": str(task),
                        "agent_count": len(agent_details),
                        "agent_names": agent_names,
                        "agent_details": agent_details,
                        "max_handoffs": tool_input.get("max_handoffs", 20),
                        "max_iterations": tool_input.get("max_iterations", 20),
                        "node_timeout": tool_input.get("node_timeout", 4800),
                        "execution_timeout": tool_input.get("execution_timeout", 5400),
                    }
                )

    def _emit_python_repl(self, tool_input: Any) -> None:
        """Emit Python REPL execution details."""
        if isinstance(tool_input, dict):
            code = tool_input.get("code", "")
            if code:
                # Emit code execution event for tracking/metrics (not for display)
                # StreamDisplay already handles the visual display
                lines = code.count("\n") + 1
                self.emit_ui_event(
                    {
                        "type": "code_execution",
                        "language": "python",
                        "lines": lines,
                        "preview": code[:100] + "..." if len(code) > 100 else code,
                    }
                )

    def _emit_load_tool(self, tool_input: Any) -> None:
        """No-op for load_tool details.

        The UI renders load_tool parameters from the tool_start payload. Emitting
        a separate metadata event here led to duplicate lines. We rely on the
        tool_start args for a single, consistent view of the operation.
        """
        return

    def _emit_stop_tool(self, tool_input: Any) -> None:
        """Stop tool: no extra metadata emission to avoid duplicate 'stop reason' lines.

        The StreamDisplay renders a concise 'tool: stop' block using the tool_input.
        """
        return

    def _emit_report_generator(self, tool_input: Any) -> None:
        """Emit report generation details."""
        if isinstance(tool_input, dict):
            target = tool_input.get("target", "")
            report_type = tool_input.get("report_type", "security_assessment")
            self.emit_ui_event(
                {"type": "metadata", "content": {"target": target, "type": report_type}}
            )

    def _emit_agent_handoff(self, tool_input: Any) -> None:
        """No-op for agent handoff details.

        The StreamDisplay renders the handoff_to_agent tool header with
        handoff target and message directly from tool_start/tool_input.
        Emitting an extra metadata event here duplicates those lines.
        """
        return

    def _emit_swarm_complete(self, tool_input: Any) -> None:
        """Emit swarm completion event (placeholder for main handler)."""
        # This is handled by the main handler due to state dependencies

    def _emit_think_operation(self, tool_input: Any) -> None:
        """Emit think operation details."""
        if isinstance(tool_input, dict):
            # Check various possible field names
            thought = ""
            for field in ["thought", "thinking", "content", "text"]:
                if field in tool_input:
                    thought = str(tool_input[field])
                    break

            if thought:
                self.emit_ui_event(
                    {
                        "type": "metadata",
                        "content": {
                            "thinking": thought[:100] + "..."
                            if len(thought) > 100
                            else thought
                        },
                    }
                )
        elif isinstance(tool_input, str):
            self.emit_ui_event(
                {
                    "type": "metadata",
                    "content": {
                        "thinking": tool_input[:100] + "..."
                        if len(tool_input) > 100
                        else tool_input
                    },
                }
            )
