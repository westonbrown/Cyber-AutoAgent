"""Standardized tool output protocol."""

from typing import Any, Dict


class ToolOutputProtocol:
    """Standardizes tool outputs for consistent UI rendering.

    All tools emit the same structure, eliminating tool-specific
    handling in both backend and frontend.
    """

    @staticmethod
    def format_start(tool_name: str, tool_input: Any) -> Dict[str, Any]:
        """Format tool start event.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters

        Returns:
            Standardized tool start event
        """
        return {
            "type": "tool_start",
            "tool": tool_name,
            "input": ToolOutputProtocol._normalize_input(tool_input),
        }

    @staticmethod
    def format_output(
        tool_name: str, result: Any, status: str = "success"
    ) -> Dict[str, Any]:
        """Format tool output event.

        Args:
            tool_name: Name of the tool
            result: Tool execution result
            status: Status (success/error)

        Returns:
            Standardized tool output event
        """
        # Extract text content
        text = ToolOutputProtocol._extract_text(result)

        return {
            "type": "tool_output",
            "tool": tool_name,
            "status": status,
            "output": {
                "text": text,
                "lines": text.split("\n") if text else [],
                "structured": result if isinstance(result, dict) else None,
            },
        }

    @staticmethod
    def _normalize_input(tool_input: Any) -> Dict[str, Any]:
        """Normalize tool input to consistent structure.

        Args:
            tool_input: Raw tool input

        Returns:
            Normalized input dictionary
        """
        if isinstance(tool_input, dict):
            return tool_input
        elif isinstance(tool_input, str):
            # Assume command-like input
            return {"command": tool_input}
        elif isinstance(tool_input, list):
            return {"commands": tool_input}
        else:
            return {"raw": str(tool_input)}

    @staticmethod
    def _extract_text(result: Any) -> str:
        """Extract text from various result formats.

        Args:
            result: Tool result in any format

        Returns:
            Text representation
        """
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            # SDK format
            if "content" in result:
                content = result["content"]
                if isinstance(content, list):
                    texts = []
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            texts.append(item["text"])
                        elif isinstance(item, str):
                            texts.append(item)
                    return "\n".join(texts)
                return str(content)
            # Direct text field
            elif "text" in result:
                return str(result["text"])
            # Output field
            elif "output" in result:
                return str(result["output"])
            # Fallback to string representation
            return str(result)
        elif isinstance(result, list):
            # List of lines
            return "\n".join(str(item) for item in result)
        else:
            return str(result) if result else ""
