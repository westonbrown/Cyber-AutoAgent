"""
Lists the full catalog of MCP tools.
"""

import json
import os
import re
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List, TypedDict, Tuple
from strands.types.tools import AgentTool, ToolSpec, ToolUse, ToolGenerator, ToolResult
from modules.config.system.logger import get_logger

from strands import tool

from modules.handlers.core import sanitize_target_name

logger = get_logger("Agents.CyberAutoAgent")


def list_mcp_tools_wrapper(mcp_tools: List[AgentTool]):
    mcp_full_catalog = """
## MCP FULL TOOL CATALOG

"""
    for mcp_tool in mcp_tools:
        mcp_full_catalog += f"""
----
name: {mcp_tool.tool_name}

input schema:
{json.dumps(mcp_tool.tool_spec.get("inputSchema"))}
"""
        output_schema = mcp_tool.tool_spec.get("outputSchema", None)
        if output_schema:
            mcp_full_catalog += f"""

output schema:
{json.dumps(output_schema)}

"""

        mcp_full_catalog += f"""
{mcp_tool.tool_spec.get("description")}
----
"""

    @tool
    def list_mcp_tools() -> str:
        """
        List the full catalog of MCP tools.
        """
        return mcp_full_catalog

    return list_mcp_tools


def _snake_case(name: str) -> str:
    """Convert a string to a Pythonic snake_case identifier."""
    s = re.sub(r"[\s\-\.]+", "_", name)
    s = re.sub(r"[^\w_]", "", s)
    s = re.sub(r"__+", "_", s)
    s = s.strip("_").lower()
    if not s:
        return "func"
    if not re.match(r"^[a-zA-Z_]", s):
        s = f"f_{s}"
    return s


def _type_hint_for(prop: Dict[str, Any]) -> str:
    """Infer a Python type hint from the JSON schema property."""

    def _map_simple(t: str) -> str:
        return {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "object": "dict",
            "array": "list",
            "null": "None",
        }.get(t, "Any")

    # Handle "anyOf" or "oneOf"
    if "anyOf" in prop or "oneOf" in prop:
        options = prop.get("anyOf") or prop.get("oneOf")
        types = []
        for opt in options:
            if not isinstance(opt, dict):
                continue
            if opt.get("type") == "array":
                item_type = "Any"
                if "items" in opt and isinstance(opt["items"], dict):
                    item_type = _map_simple(opt["items"].get("type", "Any"))
                types.append(f"list[{item_type}]")
            else:
                t = _map_simple(opt.get("type", "Any"))
                types.append(t)
        types = [t for t in types if t != "None"]
        # If null is allowed, wrap in Optional
        if any(o.get("type") == "null" for o in options if isinstance(o, dict)):
            if len(types) == 1:
                return f"Optional[{types[0]}]"
            return f"Optional[Union[{', '.join(types)}]]"
        elif len(types) > 1:
            return f"Union[{', '.join(types)}]"
        return types[0] if types else "Any"

    # Handle direct type
    t = prop.get("type")
    if t == "array":
        item_type = "Any"
        if "items" in prop and isinstance(prop["items"], dict):
            item_type = _map_simple(prop["items"].get("type", "Any"))
        return f"list[{item_type}]"
    return _map_simple(t or "Any")


def _default_value_for(prop: Dict[str, Any]) -> str:
    """Infer the Python default literal for the property."""
    if "default" in prop:
        val = prop["default"]
    else:
        val = None
        if prop.get("type") == "boolean":
            val = False
        elif "anyOf" in prop or "oneOf" in prop:
            options = prop.get("anyOf") or prop.get("oneOf")
            if any(o.get("type") == "null" for o in options if isinstance(o, dict)):
                val = None
    return repr(val)


def mcp_tools_input_schema_to_function_call(
    schema: Dict[str, Any], func_name: str | None = None
) -> str:
    """
    Convert a JSON Schema object into a Python-style function signature and call example.
    """
    # Unwrap {"json": {...}} wrapper if present
    if "properties" not in schema and "json" in schema:
        schema = schema["json"]

    if func_name is None:
        func_name = _snake_case(schema.get("title", "func"))

    props = schema.get("properties", {})
    params = []
    call_args = []
    for key, prop in props.items():
        t = _type_hint_for(prop)
        d = _default_value_for(prop)
        params.append(f"{key}: {t} = {d}")
        call_args.append(f"{key}={d}")

    signature = f"{func_name}({', '.join(params)})"
    return signature
    # call_example = f"{func_name}({', '.join(call_args)})"
    # return signature + "\n\n# Example call:\n" + call_example


_VAR_PATTERN = re.compile(r"\$\{([^}]+)}")


def resolve_env_vars_in_dict(
    input_dict: Dict[str, str], env: Dict[str, str]
) -> Dict[str, str]:
    """
    Replace ${VAR} references in values with env['VAR'] where available.
    Unrecognized variables are left as-is.
    """
    if input_dict is None:
        return {}

    resolved: Dict[str, str] = {}

    for key, value in input_dict.items():

        def _sub(match: re.Match) -> str:
            var_name = match.group(1)
            return env.get(var_name, match.group(0))  # leave ${VAR} if not found

        resolved[key] = _VAR_PATTERN.sub(_sub, value)

    return resolved


def resolve_env_vars_in_list(input_array: List[str], env: Dict[str, str]) -> List[str]:
    """
    Replace ${VAR} references in values with env['VAR'] where available.
    Unrecognized variables are left as-is.
    """
    if input_array is None:
        return []

    resolved: List[str] = []

    for value in input_array:

        def _sub(match: re.Match) -> str:
            var_name = match.group(1)
            return env.get(var_name, match.group(0))  # leave ${VAR} if not found

        resolved.append(_VAR_PATTERN.sub(_sub, value))

    return resolved


class FileWritingAgentToolAdapter(AgentTool):
    """
    Adapter that wraps an AgentTool and sends its streamed events through
    FileWritingToolGenerator to persist ToolResultEvent results to files.
    """

    def __init__(self, inner: AgentTool, output_base_path: Path) -> None:
        super().__init__()
        self._inner = inner
        self._output_base_path = output_base_path

    @property
    def tool_name(self) -> str:
        return self._inner.tool_name

    @property
    def tool_spec(self) -> ToolSpec:
        return self._inner.tool_spec

    @property
    def tool_type(self) -> str:
        # Delegate if present; fall back to the inner's type or "python"
        return getattr(self._inner, "tool_type", "python")

    @property
    def supports_hot_reload(self) -> bool:
        return False

    @property
    def is_dynamic(self) -> bool:
        return False

    def stream(
        self,
        tool_use: ToolUse,
        invocation_state: dict[str, Any],
        **kwargs: Any,
    ) -> ToolGenerator:
        inner_gen = self._inner.stream(tool_use, invocation_state, **kwargs)

        async def _wrapped() -> ToolGenerator:
            async for event in inner_gen:
                if self._is_tool_result_event(event):
                    # offload sync file IO to a thread so we don't block the event loop
                    try:
                        tool_result = getattr(event, "tool_result", None)
                        output_paths, output_size = await asyncio.to_thread(
                            self._write_result, tool_result
                        )
                        if output_size > 4096:
                            summary = {"artifact_paths": output_paths, "has_more": True}
                            tool_result["content"] = [
                                {"text": json.dumps(summary), "json": summary}
                            ]
                            tool_result["structuredContent"] = summary
                        else:
                            tool_result["structuredContent"]["artifact_paths"] = (
                                output_paths
                            )
                            if "content" in tool_result and isinstance(
                                tool_result["content"], list
                            ):
                                summary = {"artifact_paths": output_paths}
                                tool_result["content"].append(
                                    {"text": json.dumps(summary), "json": summary}
                                )

                    except Exception:
                        logger.debug(
                            "Failed to write ToolResultEvent result",
                            exc_info=True,
                        )
                yield event

        return _wrapped()

    def __getattr__(self, name: str):
        # Only called if the attribute isn't found on self
        return getattr(self._inner, name)

    def _write_result(self, result: ToolResult) -> Tuple[List[str], int]:
        output_paths = []
        size = 0
        try:
            output_basename = f"output_{time.time_ns()}"
            self._output_base_path.mkdir(parents=True, exist_ok=True)
            for idx, content in enumerate(result.get("content", [])):
                # ToolResultContent

                if "json" in content:
                    output_path = Path(
                        os.path.join(
                            self._output_base_path, f"{output_basename}_{idx}.json"
                        )
                    )
                    with output_path.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(content.get("json", "")))
                    output_paths.append(output_path)
                    size += output_path.stat().st_size

                if "text" in content:
                    output_path = Path(
                        os.path.join(
                            self._output_base_path, f"{output_basename}_{idx}.txt"
                        )
                    )
                    with output_path.open("a", encoding="utf-8") as f:
                        f.write(content.get("text", ""))
                    output_paths.append(output_path)
                    size += output_path.stat().st_size

                for file_type in ["document", "image"]:
                    if file_type in content:
                        document: TypedDict = content.get(file_type)
                        ext = sanitize_target_name(document.get("format", "bin"))
                        output_path = Path(
                            os.path.join(
                                self._output_base_path, f"{output_basename}_{idx}.{ext}"
                            )
                        )
                        with output_path.open("ab") as f:
                            f.write(document.get("source", {}).get("bytes", b""))
                        output_paths.append(output_path)
                        size += output_path.stat().st_size

            return list(map(str, output_paths)), size
        except Exception:
            logger.debug(
                "Failed to write ToolResultEvent result to %s",
                str(self._output_base_path),
                exc_info=True,
            )
            return [], 0

    @staticmethod
    def _is_tool_result_event(event: Any) -> bool:
        try:
            name = event.__class__.__name__
            if name == "ToolResultEvent":
                return True
            # Heuristic fallback for environments where the class cannot be imported
            return hasattr(event, "tool_result") and not hasattr(event, "delta")
        except Exception:
            return False


def with_result_file(tool: AgentTool, output_base_path: Path) -> AgentTool:
    """
    Convenience helper to wrap an AgentTool so its streamed results
    are persisted via FileWritingToolGenerator.
    """
    return FileWritingAgentToolAdapter(tool, output_base_path)
