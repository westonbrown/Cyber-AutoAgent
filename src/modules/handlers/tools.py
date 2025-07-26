"""
Tool execution and result handling for the handlers module.

This module contains functions for displaying tool execution details and
processing tool results with proper formatting.
"""

from typing import Dict, Any, List, Set
from .utils import Colors
from .base import CONTENT_PREVIEW_LENGTH, MAX_CONTENT_DISPLAY_LENGTH, StepLimitReached


# Constants for tool display
MAX_TOOL_CODE_LINES = 50
METADATA_PREVIEW_LENGTH = 100


def show_tool_execution(tool_use: Dict[str, Any], state: Any) -> None:
    """Display tool execution with clean formatting.

    Args:
        tool_use: Dictionary containing tool information (name, input, etc.)
        state: Handler state object containing execution context
    """
    # Enforce step limit - only check for main agent operations, not swarm sub-operations
    if not state.in_swarm_operation and state.steps >= state.max_steps and not state.step_limit_reached:
        state.step_limit_reached = True
        print("\n%sStep limit reached (%d). Assessment complete.%s" % (Colors.BLUE, state.max_steps, Colors.RESET))
        raise StepLimitReached(f"Step limit of {state.max_steps} reached")

    # Only increment main step counter for non-swarm operations
    if not state.in_swarm_operation:
        state.steps += 1

    tool_name = tool_use.get("name", "unknown")
    tool_input = tool_use.get("input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}

    # Format output
    if state.last_was_reasoning:
        print()

    # Display step header with swarm context
    print("%s" % ("─" * 80))

    # Use separate step counters for swarm vs main agent operations
    if state.in_swarm_operation:
        state.swarm_step_count += 1
        # Show agent name in step header when in swarm operation
        if state.current_swarm_agent:
            # Format agent name for display
            agent_display = state.current_swarm_agent.replace("_", " ").title()
            print(
                "Swarm Step %d: %s%s%s - %s%s%s"
                % (
                    state.swarm_step_count,
                    Colors.CYAN,
                    tool_name,
                    Colors.RESET,
                    Colors.YELLOW,
                    agent_display,
                    Colors.RESET,
                )
            )
        else:
            # First swarm step or no agent identified yet
            print(
                "Swarm Step %d: %s%s%s %s(Initializing)%s"
                % (
                    state.swarm_step_count,
                    Colors.CYAN,
                    tool_name,
                    Colors.RESET,
                    Colors.DIM,
                    Colors.RESET,
                )
            )
    else:
        # Regular main agent step - only increment main counter for non-swarm operations
        print("Step %d/%d: %s%s%s" % (state.steps, state.max_steps, Colors.CYAN, tool_name, Colors.RESET))

    print("%s" % ("─" * 80))

    # Display tool-specific details
    _display_tool_details(tool_name, tool_input, state)


def _display_tool_details(tool_name: str, tool_input: Dict[str, Any], state: Any) -> None:
    """Display tool-specific execution details.

    Args:
        tool_name: Name of the tool being executed
        tool_input: Tool input parameters
        state: Handler state object
    """
    if tool_name == "shell":
        _display_shell_tool(tool_input, state)
    elif tool_name == "file_write":
        _display_file_write_tool(tool_input, state)
    elif tool_name == "editor":
        _display_editor_tool(tool_input, state)
    elif tool_name == "load_tool":
        _display_load_tool(tool_input, state)
    elif tool_name == "stop":
        _display_stop_tool(tool_input, state)
    elif tool_name == "mem0_memory":
        _display_memory_tool(tool_input, state)
    elif tool_name == "swarm":
        _display_swarm_tool(tool_input, state)
    elif tool_name == "http_request":
        _display_http_request_tool(tool_input, state)
    elif tool_name == "thought":
        _display_thought_tool(tool_input, state)
    elif tool_name == "handoff_to_agent":
        _display_handoff_tool(tool_input, state)
    else:
        # Generic tool display
        print("↳ Executing: %s%s%s" % (Colors.CYAN, tool_name, Colors.RESET))
        if tool_input:
            # Show first few parameters
            param_count = 0
            for key, value in tool_input.items():
                if param_count >= 3:  # Limit to first 3 parameters
                    remaining = len(tool_input) - 3
                    if remaining > 0:
                        print("  %s... and %d more parameters%s" % (Colors.DIM, remaining, Colors.RESET))
                    break
                value_str = str(value)[:100]
                if len(str(value)) > 100:
                    value_str += "..."
                print("  %s: %s" % (key, value_str))
                param_count += 1
        state.tools_used.append(tool_name)


def _display_shell_tool(tool_input: Dict[str, Any], state: Any) -> None:
    """Display shell command execution details."""
    command = tool_input.get("command", "")
    parallel = tool_input.get("parallel", False)

    # Process command input
    if isinstance(command, list):
        mode = "parallel" if parallel else "sequential"
        # Remove duplicate commands
        seen = set()
        unique_commands = []
        for cmd in command:
            cmd_str = cmd if isinstance(cmd, str) else cmd.get("command", str(cmd))
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
            print("↳ Executing %d commands (%s):" % (len(unique_commands), mode))

        for i, (cmd, cmd_str) in enumerate(unique_commands):
            print("  %d. %s%s%s" % (i + 1, Colors.GREEN, cmd_str, Colors.RESET))
        state.tools_used.append(f"shell: {len(unique_commands)} commands ({mode})")
    else:
        print("↳ Running: %s%s%s" % (Colors.GREEN, command, Colors.RESET))
        state.tools_used.append(f"shell: {command}")


def _display_file_write_tool(tool_input: Dict[str, Any], state: Any) -> None:
    """Display file write operation details."""
    path = tool_input.get("path", "")
    content_preview = str(tool_input.get("content", ""))[:50]
    print("↳ Writing: %s%s%s" % (Colors.YELLOW, path, Colors.RESET))
    if content_preview:
        print("  Content: %s%s...%s" % (Colors.DIM, content_preview, Colors.RESET))

    # Record created tools if applicable
    if hasattr(state, "created_tools") and path and path.startswith("tools/"):
        state.created_tools.append(path.replace("tools/", "").replace(".py", ""))

    state.tools_used.append(f"file_write: {path}")


def _display_editor_tool(tool_input: Dict[str, Any], state: Any) -> None:
    """Display editor operation details."""
    command = tool_input.get("command", "")
    path = tool_input.get("path", "")
    file_text = tool_input.get("file_text", "")

    print("↳ Editor: %s%s%s" % (Colors.CYAN, command, Colors.RESET))
    print("  Path: %s%s%s" % (Colors.YELLOW, path, Colors.RESET))

    # Display file content
    if command == "create" and file_text:
        # Record tool files
        if hasattr(state, "created_tools") and path and path.startswith("tools/") and path.endswith(".py"):
            state.created_tools.append(path.replace("tools/", "").replace(".py", ""))
            print("\n%s" % ("─" * 70))
            print("📄 %sMETA-TOOL CODE:%s" % (Colors.YELLOW, Colors.RESET))
        else:
            print("\n%s" % ("─" * 70))
            print("📄 %sFILE CONTENT:%s" % (Colors.CYAN, Colors.RESET))

        print("%s" % ("─" * 70))

        # Show file content with syntax highlighting
        _display_file_content(file_text, path)
        print("%s" % ("─" * 70))

    state.tools_used.append(f"editor: {command} {path}")


def _display_file_content(file_text: str, path: str) -> None:
    """Display file content with syntax highlighting for Python files."""
    lines = file_text.split("\n")
    for line in lines[:MAX_TOOL_CODE_LINES]:
        # Apply syntax highlighting for Python files
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
        print("%s... (%d more lines)%s" % (Colors.DIM, len(lines) - MAX_TOOL_CODE_LINES, Colors.RESET))


def _display_load_tool(tool_input: Dict[str, Any], state: Any) -> None:
    """Display tool loading details."""
    path = tool_input.get("path", "")
    print("↳ Loading: %s%s%s" % (Colors.GREEN, path, Colors.RESET))
    state.tools_used.append(f"load_tool: {path}")


def _display_stop_tool(tool_input: Dict[str, Any], state: Any) -> None:
    """Display stop tool execution."""
    reason = tool_input.get("reason", "No reason provided")
    print("↳ Stopping: %s%s%s" % (Colors.RED, reason, Colors.RESET))
    if hasattr(state, "stop_tool_used"):
        state.stop_tool_used = True
    state.tools_used.append(f"stop: {reason}")


def _display_memory_tool(tool_input: Dict[str, Any], state: Any) -> None:
    """Display memory operation details."""
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
                "..." if len(str(tool_input.get("content", ""))) > CONTENT_PREVIEW_LENGTH else "",
                Colors.RESET,
            )
        )
        if metadata:
            print(
                "  Metadata: %s%s%s%s"
                % (
                    Colors.DIM,
                    str(metadata)[:METADATA_PREVIEW_LENGTH],
                    "..." if len(str(metadata)) > METADATA_PREVIEW_LENGTH else "",
                    Colors.RESET,
                )
            )
    elif action == "search":
        query = tool_input.get("query", "")
        print("↳ Searching: %s%s%s" % (Colors.CYAN, query, Colors.RESET))
    elif action == "get":
        memory_id = tool_input.get("memory_id", "unknown")
        print("↳ Retrieving: %s%s%s" % (Colors.CYAN, memory_id, Colors.RESET))
    elif action == "update":
        memory_id = tool_input.get("memory_id", "unknown")
        print("↳ Updating: %s%s%s" % (Colors.YELLOW, memory_id, Colors.RESET))
    elif action == "delete":
        memory_id = tool_input.get("memory_id", "unknown")
        print("↳ Deleting: %s%s%s" % (Colors.RED, memory_id, Colors.RESET))

    state.tools_used.append(f"mem0_memory: {action}")


def _display_swarm_tool(tool_input: Dict[str, Any], state: Any) -> None:
    """Display swarm configuration details."""
    task = tool_input.get("task", "")
    agents = tool_input.get("agents", [])
    max_handoffs = tool_input.get("max_handoffs", 20)
    max_iterations = tool_input.get("max_iterations", 20)
    execution_timeout = tool_input.get("execution_timeout", 900.0)
    node_timeout = tool_input.get("node_timeout", 300.0)

    # Get repetitive handoff detection parameters
    repetitive_window = tool_input.get("repetitive_handoff_detection_window", 8)
    repetitive_min_agents = tool_input.get("repetitive_handoff_min_unique_agents", 3)

    # Track swarm operation start
    state.in_swarm_operation = True
    state.swarm_agents = [agent.get("name", f"agent_{i+1}") for i, agent in enumerate(agents)]
    state.swarm_step_count = 0

    print("↳ %sOrchestrating Swarm Intelligence%s" % (Colors.BOLD, Colors.RESET))

    # Display task
    if task:
        # Format task display
        task_lines = task.split("\n")
        if len(task_lines) > 1:
            print("  %sTask:%s" % (Colors.DIM, Colors.RESET))
            for line in task_lines[:5]:  # Limit to 5 lines
                print("    %s" % line.strip())
            if len(task_lines) > 5:
                print("    %s... (%d more lines)%s" % (Colors.DIM, len(task_lines) - 5, Colors.RESET))
        else:
            print("  %sTask:%s %s" % (Colors.DIM, Colors.RESET, task[:200]))
            if len(task) > 200:
                print("    %s...%s" % (Colors.DIM, Colors.RESET))

    # Display agent specifications
    print("\n  %sSwarm Configuration:%s" % (Colors.CYAN, Colors.RESET))
    print("    %sAgents (%d):%s" % (Colors.CYAN, len(agents), Colors.RESET))
    for i, agent_spec in enumerate(agents):
        agent_name = agent_spec.get("name", f"agent_{i+1}")
        agent_prompt = agent_spec.get("system_prompt", "")
        model_provider = agent_spec.get("model_provider", "inherited")
        model_id = ""
        if "model_settings" in agent_spec and isinstance(agent_spec["model_settings"], dict):
            model_id = agent_spec["model_settings"].get("model_id", "")

        print("      %s• %s%s%s" % (Colors.GREEN, Colors.BOLD, agent_name, Colors.RESET))
        # Show full system prompt
        print("        %sRole:%s %s" % (Colors.DIM, Colors.RESET, agent_prompt))
        if model_provider != "inherited" or model_id:
            model_info = f"{model_provider}"
            if model_id:
                model_info += f" ({model_id})"
            print("        %sModel:%s %s" % (Colors.DIM, Colors.RESET, model_info))

    # Display execution parameters
    print("\n    %sExecution Parameters:%s" % (Colors.DIM, Colors.RESET))
    print("      Max Handoffs: %s%d%s" % (Colors.DIM, max_handoffs, Colors.RESET))
    print("      Max Iterations: %s%d%s" % (Colors.DIM, max_iterations, Colors.RESET))
    print("      Execution Timeout: %s%.1fs%s" % (Colors.DIM, execution_timeout, Colors.RESET))
    print("      Node Timeout: %s%.1fs%s" % (Colors.DIM, node_timeout, Colors.RESET))

    # Display repetitive handoff detection if enabled
    if repetitive_window > 0:
        print("\n    %sRepetitive Handoff Detection:%s" % (Colors.DIM, Colors.RESET))
        print("      Detection Window: %s%d%s" % (Colors.DIM, repetitive_window, Colors.RESET))
        print("      Min Unique Agents: %s%d%s" % (Colors.DIM, repetitive_min_agents, Colors.RESET))

    state.tools_used.append(f"swarm: {len(agents)} agents")


def _display_http_request_tool(tool_input: Dict[str, Any], state: Any) -> None:
    """Display HTTP request details."""
    method = tool_input.get("method", "GET")
    url = tool_input.get("url", "")
    auth_type = tool_input.get("auth_type", "")
    headers = tool_input.get("headers", {})
    body = tool_input.get("body", "")

    # Format method with color
    method_color = {
        "GET": Colors.GREEN,
        "POST": Colors.YELLOW,
        "PUT": Colors.YELLOW,
        "DELETE": Colors.RED,
        "PATCH": Colors.YELLOW,
        "HEAD": Colors.CYAN,
    }.get(method, Colors.CYAN)

    print("↳ HTTP Request: %s%s%s %s" % (method_color, method, Colors.RESET, url))

    # Display auth if present
    if auth_type:
        auth_display = auth_type
        if auth_type in ["Bearer", "token"] and tool_input.get("auth_env_var"):
            auth_display += f" (from {tool_input['auth_env_var']})"
        print("  Auth: %s%s%s" % (Colors.DIM, auth_display, Colors.RESET))

    # Display headers if present
    if headers:
        print("  Headers: %s%s%s" % (Colors.DIM, str(headers)[:100], Colors.RESET))
        if len(str(headers)) > 100:
            print("    %s...%s" % (Colors.DIM, Colors.RESET))

    # Display body preview if present
    if body:
        body_preview = str(body)[:100]
        print("  Body: %s%s%s" % (Colors.DIM, body_preview, Colors.RESET))
        if len(str(body)) > 100:
            print("    %s...%s" % (Colors.DIM, Colors.RESET))

    state.tools_used.append(f"http_request: {method} {url}")


def _display_thought_tool(tool_input: Dict[str, Any], state: Any) -> None:
    """Display metacognitive thought process."""
    thought = tool_input.get("thought", "")
    cycle_count = tool_input.get("cycle_count", 1)

    print("↳ %sMetacognitive Assessment%s" % (Colors.MAGENTA, Colors.RESET))
    if cycle_count > 1:
        print("  %s(Cycle %d)%s" % (Colors.DIM, cycle_count, Colors.RESET))

    # Display thought content
    if thought:
        thought_lines = thought.strip().split("\n")
        for line in thought_lines[:10]:  # Limit to 10 lines
            print("  %s%s%s" % (Colors.DIM, line, Colors.RESET))
        if len(thought_lines) > 10:
            print("  %s... (%d more lines)%s" % (Colors.DIM, len(thought_lines) - 10, Colors.RESET))

    state.tools_used.append("thought: metacognitive assessment")


def _display_handoff_tool(tool_input: Dict[str, Any], state: Any) -> None:
    """Display agent handoff details."""
    target_agent = tool_input.get("agent_name", "unknown")
    message = tool_input.get("message", "")

    # Format target agent name for display
    target_display = target_agent.replace("_", " ").title()

    print("↳ %sHandoff to: %s%s%s" % (Colors.MAGENTA, Colors.YELLOW, target_display, Colors.RESET))

    # Show brief message preview
    if message:
        message_preview = message[:150]
        if len(message) > 150:
            message_preview += "..."
        print("  %sMessage:%s %s" % (Colors.DIM, Colors.RESET, message_preview))

    state.tools_used.append(f"handoff_to_agent: {target_agent}")


def show_tool_result(tool_id: str, tool_result: Dict[str, Any], state: Any) -> None:
    """Display tool execution results.

    Args:
        tool_id: The tool use ID
        tool_result: The tool result dictionary
        state: Handler state object
    """
    if tool_id not in state.tool_use_map:
        return

    tool_use = state.tool_use_map[tool_id]
    tool_name = tool_use.get("name", "unknown")
    status = tool_result.get("status", "")
    result_content = tool_result.get("content", [])

    # Format display based on status
    if status == "error":
        print("\n↳ %s❌ Error%s" % (Colors.RED, Colors.RESET))
        for content_block in result_content:
            if isinstance(content_block, dict) and "text" in content_block:
                error_text = content_block.get("text", "")
                if error_text:
                    print("  %s%s%s" % (Colors.RED, error_text, Colors.RESET))
    else:
        # Success - display based on tool type
        if tool_name in ["mem0_memory", "load_tool", "stop"]:
            # These tools handle their own success display
            pass
        else:
            # Display tool output
            for content_block in result_content:
                if isinstance(content_block, dict) and "text" in content_block:
                    output_text = content_block.get("text", "")
                    if output_text.strip():
                        # Use specialized display for certain tools
                        if tool_name == "swarm":
                            from .display import display_swarm_result

                            display_swarm_result(output_text, tool_result)
                            # Mark end of swarm operation
                            state.in_swarm_operation = False
                            state.swarm_agents = []
                            state.swarm_step_count = 0
                            state.current_swarm_agent = None
                        elif tool_name == "http_request":
                            from .display import display_http_response

                            display_http_response(output_text, tool_result)
                        else:
                            # Display truncated output
                            _display_generic_output(output_text)

    print("%s" % ("─" * 80))


def _display_generic_output(output_text: str, max_lines: int = 50) -> None:
    """Display generic tool output with truncation."""
    lines = output_text.strip().split("\n")
    if len(lines) > max_lines:
        for line in lines[:max_lines]:
            print(line)
        print("%s... (%d more lines)%s" % (Colors.DIM, len(lines) - max_lines, Colors.RESET))
    else:
        print(output_text)


def track_tool_effectiveness(tool_id: str, tool_result: Dict[str, Any], state: Any) -> None:
    """Track tool effectiveness metrics.

    Args:
        tool_id: The tool use ID
        tool_result: The tool result dictionary
        state: Handler state object
    """
    if tool_id not in state.tool_use_map:
        return

    tool_use = state.tool_use_map[tool_id]
    tool_name = tool_use.get("name", "unknown")
    status = tool_result.get("status", "success")

    # Initialize tool effectiveness tracking if needed
    if tool_name not in state.tool_effectiveness:
        state.tool_effectiveness[tool_name] = {"uses": 0, "successes": 0, "errors": 0}

    # Update metrics
    state.tool_effectiveness[tool_name]["uses"] += 1
    if status == "error":
        state.tool_effectiveness[tool_name]["errors"] += 1
    else:
        state.tool_effectiveness[tool_name]["successes"] += 1
