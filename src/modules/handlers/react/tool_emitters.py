"""
Tool-specific event emitters for the React UI bridge.

This module contains specialized event emitters for different tool types,
converting tool inputs and outputs into structured events for the React UI.
"""

import json
from typing import Any, Dict, List, Callable


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
            "handoff_to_user": self._emit_user_handoff,
            "swarm": self._emit_swarm_operation,
            "python_repl": self._emit_python_repl,
            "load_tool": self._emit_load_tool,
            "stop": self._emit_stop_tool,
            "generate_security_report": self._emit_report_generator,
            "handoff_to_agent": self._emit_agent_handoff,
            "complete_swarm_task": self._emit_swarm_complete,
            "think": self._emit_think_operation,
        }

        emitter = emitter_map.get(tool_name, self._emit_generic_tool_params)
        if emitter is self._emit_generic_tool_params:
            # Generic emitter needs tool_name
            emitter(tool_name, tool_input)
        else:
            # Specific emitters only need tool_input
            emitter(tool_input)

    def _emit_shell_commands(self, tool_input: Any) -> None:
        """Extract and emit shell commands for display."""
        commands = []

        if isinstance(tool_input, str):
            commands = [tool_input]
        elif isinstance(tool_input, dict):
            # Check various field names that tools might use
            for field in ["command", "commands", "cmd", "script", "bash_command", "shell_command"]:
                if field in tool_input:
                    value = tool_input[field]
                    if isinstance(value, list):
                        commands = value
                    elif isinstance(value, str):
                        # Handle JSON string format like '["cmd1", "cmd2"]'
                        try:
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

        # Emit each command individually
        for cmd in commands:
            if cmd:
                self.emit_ui_event({"type": "command", "content": str(cmd)})

        # Signal completion of command emission
        if commands:
            self.emit_ui_event({"type": "tool_commands_complete"})

    def _emit_memory_operation(self, tool_input: Any) -> None:
        """Emit memory operation details."""
        if isinstance(tool_input, dict):
            action = tool_input.get("action", "unknown")
            if action == "store":
                content = tool_input.get("content", "")
                preview = content[:100] + "..." if len(content) > 100 else content
                self.emit_ui_event({"type": "metadata", "content": {"action": "storing memory", "preview": preview}})
            elif action == "retrieve":
                query = tool_input.get("query", "")
                self.emit_ui_event({"type": "metadata", "content": {"action": "retrieving memory", "query": query}})

    def _emit_http_request(self, tool_input: Any) -> None:
        """Emit HTTP request details."""
        if isinstance(tool_input, dict):
            method = tool_input.get("method", "GET")
            url = tool_input.get("url", "")
            self.emit_ui_event({"type": "metadata", "content": {"method": method, "url": url}})

    def _emit_file_write(self, tool_input: Any) -> None:
        """Emit file write operation details."""
        if isinstance(tool_input, dict):
            path = tool_input.get("path", "")
            content = str(tool_input.get("content", ""))
            preview = content[:50] + "..." if len(content) > 50 else content
            self.emit_ui_event({"type": "metadata", "content": {"path": path, "preview": preview}})

    def _emit_editor_operation(self, tool_input: Any) -> None:
        """Emit editor operation details."""
        if isinstance(tool_input, dict):
            command = tool_input.get("command", "")
            path = tool_input.get("path", "")
            self.emit_ui_event({"type": "metadata", "content": {"command": command, "path": path}})

    def _emit_user_handoff(self, tool_input: Any) -> None:
        """Emit user handoff event."""
        if isinstance(tool_input, dict):
            message = tool_input.get("message", "")
            breakout = tool_input.get("breakout_of_loop", False)
        else:
            message = str(tool_input) if tool_input else ""
            breakout = False

        self.emit_ui_event({"type": "user_handoff", "message": message, "breakout": breakout})

    def _emit_generic_tool_params(self, tool_name: str, tool_input: Any) -> None:  # pylint: disable=unused-argument
        """Emit generic tool parameters for tools without specialized handlers."""
        if isinstance(tool_input, dict) and tool_input:
            metadata = {}
            for i, (key, value) in enumerate(tool_input.items()):
                if i >= 3:  # Limit to first 3 parameters for readability
                    metadata["..."] = f"and {len(tool_input) - 3} more"
                    break
                value_str = str(value)[:50]
                if len(str(value)) > 50:
                    value_str += "..."
                metadata[key] = value_str

            if metadata:
                self.emit_ui_event({"type": "metadata", "content": metadata})

    def _emit_swarm_operation(self, tool_input: Any) -> None:
        """Emit swarm orchestration details."""
        if isinstance(tool_input, dict):
            agents = tool_input.get("agents", [])
            task = tool_input.get("task", "")
            agent_count = len(agents) if isinstance(agents, list) else 0
            task_preview = task[:100] + "..." if len(task) > 100 else task

            # Extract agent names for display
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

            # Emit swarm start event
            self.emit_ui_event(
                {
                    "type": "swarm_start",
                    "agent_names": agent_names,
                    "agent_count": agent_count,
                    "task": task_preview,
                    "max_handoffs": tool_input.get("max_handoffs", 20),
                }
            )

            # Also emit metadata for backward compatibility
            self.emit_ui_event(
                {"type": "metadata", "content": {"agents": f"{agent_count} agents", "task": task_preview}}
            )

    def _emit_python_repl(self, tool_input: Any) -> None:
        """Emit Python REPL execution details."""
        if isinstance(tool_input, dict):
            code = tool_input.get("code", "")
            # Show first few lines of code
            code_lines = code.split("\n")
            if len(code_lines) > 3:
                preview = "\n".join(code_lines[:3]) + "\n..."
            else:
                preview = code

            self.emit_ui_event({"type": "metadata", "content": {"code": preview}})

    def _emit_load_tool(self, tool_input: Any) -> None:
        """Emit dynamic tool loading details."""
        if isinstance(tool_input, dict):
            tool_name = tool_input.get("tool_name", "")
            path = tool_input.get("path", "")
            self.emit_ui_event({"type": "metadata", "content": {"loading": tool_name, "path": path}})

    def _emit_stop_tool(self, tool_input: Any) -> None:
        """Emit stop execution details."""
        if isinstance(tool_input, dict):
            reason = tool_input.get("reason", "No reason provided")
        else:
            reason = str(tool_input) if tool_input else "No reason provided"

        self.emit_ui_event({"type": "metadata", "content": {"stopping": reason}})

    def _emit_report_generator(self, tool_input: Any) -> None:
        """Emit report generation details."""
        if isinstance(tool_input, dict):
            target = tool_input.get("target", "")
            report_type = tool_input.get("report_type", "security_assessment")
            self.emit_ui_event({"type": "metadata", "content": {"target": target, "type": report_type}})

    def _emit_agent_handoff(self, tool_input: Any) -> None:
        """Emit agent handoff details."""
        if isinstance(tool_input, dict):
            agent_name = tool_input.get("agent_name", "")
            message = tool_input.get("message", "")
            message_preview = message[:100] + "..." if len(message) > 100 else message
            self.emit_ui_event({"type": "metadata", "content": {"handoff_to": agent_name, "message": message_preview}})

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
                        "content": {"thinking": thought[:100] + "..." if len(thought) > 100 else thought},
                    }
                )
        elif isinstance(tool_input, str):
            self.emit_ui_event(
                {
                    "type": "metadata",
                    "content": {"thinking": tool_input[:100] + "..." if len(tool_input) > 100 else tool_input},
                }
            )
