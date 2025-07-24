"""
Display formatting and output utilities for the handlers module.

This module contains functions for formatting and displaying various types of
output including HTTP responses, swarm results, and tool execution results.
"""

import json
import re
from typing import Dict, Any, Optional, Tuple

from .utils import Colors


def display_http_response(output_text: str, tool_result: Dict[str, Any]) -> None:
    """Display HTTP response in a structured, readable format.

    Args:
        output_text: The raw response text to parse and display
        tool_result: The tool result dictionary (currently unused but kept for compatibility)
    """
    # Parse the response text to extract components
    lines = output_text.strip().split("\n")
    status_code = None
    headers = {}
    body = ""
    metrics = {}
    redirects = None

    for i, line in enumerate(lines):
        if line.startswith("Status Code:"):
            status_code = line.split(":", 1)[1].strip()
        elif line.startswith("Redirects:"):
            redirects = line.split(":", 1)[1].strip()
        elif line.startswith("Headers:"):
            # Try to parse headers dict
            headers_str = line.split(":", 1)[1].strip()
            try:
                headers = json.loads(headers_str)
            except:
                headers = {"raw": headers_str}
        elif line.startswith("Body:"):
            # Get everything after "Body: "
            first_body_line = line.split(":", 1)[1].strip() if ":" in line else ""
            if first_body_line:
                body = first_body_line
            if i + 1 < len(lines):
                # Join all remaining lines as body
                body = "\n".join([first_body_line] + lines[i + 1 :])
                # Remove metrics if they were included
                if "\nMetrics:" in body:
                    body = body.split("\nMetrics:")[0]
            break
        elif line.startswith("Metrics:"):
            metrics_str = line.split(":", 1)[1].strip()
            try:
                metrics = json.loads(metrics_str)
            except:
                metrics = {"raw": metrics_str}

    # Display formatted response
    if status_code:
        # Determine status color
        try:
            code = int(status_code)
            if 200 <= code < 300:
                status_color = Colors.GREEN
                status_icon = "✅"
            elif 300 <= code < 400:
                status_color = Colors.YELLOW
                status_icon = "↻"
            elif 400 <= code < 500:
                status_color = Colors.YELLOW
                status_icon = "⚠️"
            else:
                status_color = Colors.RED
                status_icon = "❌"
        except:
            status_color = Colors.CYAN
            status_icon = "ℹ️"

        print("%s %sHTTP %s%s" % (status_icon, status_color, status_code, Colors.RESET))

    # Display redirects if any
    if redirects and "followed" in redirects:
        print("  %s↻ %s%s" % (Colors.YELLOW, redirects, Colors.RESET))

    # Display headers
    if headers and isinstance(headers, dict):
        print("  %sHeaders:%s" % (Colors.DIM, Colors.RESET))
        for key, value in headers.items():
            if key != "raw":
                print("    %s%s:%s %s" % (Colors.DIM, key, Colors.RESET, value))

    # Display body
    if body.strip():
        print("  %sResponse:%s" % (Colors.DIM, Colors.RESET))
        _display_formatted_body(body)

    # Display metrics if available
    if metrics and isinstance(metrics, dict) and metrics.get("duration"):
        print("  %s⏱ Duration: %.3fs%s" % (Colors.DIM, metrics["duration"], Colors.RESET))


def _display_formatted_body(body: str, max_lines: int = 30) -> None:
    """Display response body with formatting and syntax highlighting.

    Args:
        body: The body content to display
        max_lines: Maximum number of lines to display
    """
    # Try to detect and format JSON
    try:
        # Check if body looks like JSON
        if body.strip().startswith("{") or body.strip().startswith("["):
            json_obj = json.loads(body)
            json_str = json.dumps(json_obj, indent=2)
            lines = json_str.split("\n")

            # Display formatted JSON with syntax highlighting
            for line in lines[:max_lines]:
                # Simple JSON syntax highlighting
                if '"' in line:
                    # Highlight keys in cyan
                    line = re.sub(r'"([^"]+)":', f'"{Colors.CYAN}\\1{Colors.RESET}":', line)
                    # Highlight string values in green
                    line = re.sub(r': "([^"]*)"', f': "{Colors.GREEN}\\1{Colors.RESET}"', line)
                # Highlight numbers in yellow
                line = re.sub(r": (\d+)", f": {Colors.YELLOW}\\1{Colors.RESET}", line)
                # Highlight booleans in magenta
                line = re.sub(r": (true|false)", f": {Colors.MAGENTA}\\1{Colors.RESET}", line)
                # Highlight null in red
                line = re.sub(r": (null)", f": {Colors.RED}\\1{Colors.RESET}", line)

                print("    %s" % line)

            if len(lines) > max_lines:
                print("    %s... (%d more lines)%s" % (Colors.DIM, len(lines) - max_lines, Colors.RESET))
        else:
            # Not JSON, display as text
            _display_plain_text(body, max_lines)
    except:
        # Failed to parse as JSON, display as plain text
        _display_plain_text(body, max_lines)


def _display_plain_text(text: str, max_lines: int = 20, max_line_length: int = 120) -> None:
    """Display plain text with line limits.

    Args:
        text: The text to display
        max_lines: Maximum number of lines to display
        max_line_length: Maximum length per line before truncation
    """
    lines = text.strip().split("\n")
    for line in lines[:max_lines]:
        if len(line) > max_line_length:
            print("    %s..." % line[:max_line_length])
        else:
            print("    %s" % line)
    if len(lines) > max_lines:
        print("    %s... (%d more lines)%s" % (Colors.DIM, len(lines) - max_lines, Colors.RESET))


def display_swarm_result(output_text: str, tool_result: Dict[str, Any]) -> None:  # pylint: disable=unused-argument
    """Display swarm execution results in a structured, readable format.

    Args:
        output_text: The swarm execution output text
        tool_result: The tool result dictionary (currently unused but kept for compatibility)
    """
    lines = output_text.strip().split("\n")

    # Parse swarm result components
    status = None
    execution_time = None
    team_size = None
    iterations = None
    collaboration_chain = None
    agent_contributions = {}
    final_result = ""
    resource_usage = {}

    current_agent = None
    current_content = []
    in_agent_section = False
    in_final_result = False
    in_resource_section = False

    # Parse the output
    for line in lines:
        # Skip the header emoji lines
        if line.strip().startswith("🎯") or line.strip().startswith("📊"):
            continue

        # Status line - handle markdown bold format
        if "**Status:**" in line:
            status_match = re.search(r"\*\*Status:\*\*\s*(.+)", line)
            if status_match:
                status = status_match.group(1).strip()

        # Execution metrics - handle markdown bold format
        elif "**Execution Time:**" in line:
            time_match = re.search(r"\*\*Execution Time:\*\*\s*(\d+)ms", line)
            if time_match:
                execution_time = int(time_match.group(1))

        elif "**Team Size:**" in line:
            team_match = re.search(r"\*\*Team Size:\*\*\s*(\d+)\s*agents", line)
            if team_match:
                team_size = int(team_match.group(1))

        elif "**Iterations:**" in line:
            iter_match = re.search(r"\*\*Iterations:\*\*\s*(\d+)", line)
            if iter_match:
                iterations = int(iter_match.group(1))

        # Collaboration chain
        elif "**Collaboration Chain:**" in line:
            chain_match = re.search(r"\*\*Collaboration Chain:\*\*\s*(.+)", line)
            if chain_match:
                collaboration_chain = chain_match.group(1).strip()

        # Agent sections - look for bold agent names in uppercase
        elif (
            line.strip().startswith("**")
            and line.strip().endswith(":**")
            and not any(
                header in line
                for header in ["Individual Agent Contributions", "Final Team Result", "Team Resource Usage"]
            )
        ):
            # Start of agent section
            if current_agent and current_content:
                agent_contributions[current_agent] = "\n".join(current_content)

            # Extract agent name
            agent_match = re.match(r"\*\*([^*]+):\*\*", line.strip())
            if agent_match:
                current_agent = agent_match.group(1).strip()
                current_content = []
                in_agent_section = True
                in_final_result = False
                in_resource_section = False

        elif "Individual Agent Contributions:" in line:
            # Just a header, continue
            pass

        elif "Final Team Result:" in line:
            if current_agent and current_content:
                agent_contributions[current_agent] = "\n".join(current_content)
            current_agent = None
            current_content = []
            in_final_result = True
            in_agent_section = False
            in_resource_section = False

        elif "Team Resource Usage:" in line:
            if current_agent and current_content:
                agent_contributions[current_agent] = "\n".join(current_content)
            elif in_final_result and current_content:
                final_result = "\n".join(current_content)
            current_agent = None
            current_content = []
            in_resource_section = True
            in_agent_section = False
            in_final_result = False

        elif in_agent_section and current_agent and line.strip() and not line.strip().startswith("**"):
            current_content.append(line)
        elif in_final_result and line.strip() and not line.strip().startswith("**"):
            current_content.append(line)
        elif in_resource_section and line.strip():
            # Parse resource usage with bullet points
            token_match = re.match(r"[•·]?\s*(Input|Output|Total)\s*tokens:\s*([\d,]+)", line.strip())
            if token_match:
                token_type = token_match.group(1).lower()
                tokens = int(token_match.group(2).replace(",", ""))
                resource_usage[f"{token_type}_tokens"] = tokens

    # Handle remaining content
    if current_agent and current_content:
        agent_contributions[current_agent] = "\n".join(current_content)
    elif in_final_result and current_content:
        final_result = "\n".join(current_content)

    # Display formatted results
    print("\n%s🤖 Swarm Execution Complete%s" % (Colors.BOLD, Colors.RESET))

    # Status and metrics
    if status:
        status_color = Colors.GREEN if "COMPLETED" in status.upper() else Colors.RED
        status_icon = "✅" if "COMPLETED" in status.upper() else "❌"
        print("  %s%s Status:%s %s%s%s" % (status_icon, Colors.DIM, Colors.RESET, status_color, status, Colors.RESET))

    if execution_time:
        print("  %s⏱  Duration:%s %dms" % (Colors.DIM, Colors.RESET, execution_time))

    if team_size is not None and iterations is not None:
        print("  %s👥 Team:%s %d agents (%d iterations)" % (Colors.DIM, Colors.RESET, team_size, iterations))

    # Collaboration flow
    if collaboration_chain:
        print("  %s🔗 Flow:%s %s" % (Colors.DIM, Colors.RESET, collaboration_chain))

    # Display individual agent contributions
    if agent_contributions:
        print("\n  %sAgent Contributions:%s" % (Colors.DIM, Colors.RESET))
        for agent_name, content in agent_contributions.items():
            # Format agent name nicely - handle both uppercase and mixed case
            if agent_name.isupper():
                display_name = agent_name.replace("_", " ")
            else:
                display_name = agent_name.replace("_", " ").title()
            print("    %s• %s:%s" % (Colors.CYAN, display_name, Colors.RESET))

            # Display content with proper indentation
            content_lines = content.strip().split("\n")
            for line in content_lines[:3]:  # Limit to first 3 lines per agent
                print("      %s" % line.strip())
            if len(content_lines) > 3:
                print("      %s... (%d more lines)%s" % (Colors.DIM, len(content_lines) - 3, Colors.RESET))

    # Display final result
    if final_result:
        print("\n  %s📊 Final Result:%s" % (Colors.DIM, Colors.RESET))
        result_lines = final_result.strip().split("\n")
        for line in result_lines[:5]:  # Limit to first 5 lines
            print("    %s" % line.strip())
        if len(result_lines) > 5:
            print("    %s... (%d more lines)%s" % (Colors.DIM, len(result_lines) - 5, Colors.RESET))

    # Display resource usage
    if resource_usage:
        print("\n  %s📈 Team Resource Usage:%s" % (Colors.DIM, Colors.RESET))
        if "input_tokens" in resource_usage:
            print("    • Input tokens: %s%d%s" % (Colors.YELLOW, resource_usage["input_tokens"], Colors.RESET))
        if "output_tokens" in resource_usage:
            print("    • Output tokens: %s%d%s" % (Colors.YELLOW, resource_usage["output_tokens"], Colors.RESET))
        if "total_tokens" in resource_usage:
            print("    • Total tokens: %s%d%s" % (Colors.BOLD, resource_usage["total_tokens"], Colors.RESET))

    # Always print a separator at the end to clearly show completion
    print("\n%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))
