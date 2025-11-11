"""
Lists the full catalog of MCP tools.
"""
import json
import re
from typing import Any, Dict, List
from strands.types.tools import AgentTool

from strands import tool

def list_mcp_tools_wrapper(mcp_tools: List[AgentTool]):

    mcp_full_catalog = f"""
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


def mcp_tools_input_schema_to_function_call(schema: Dict[str, Any], func_name: str | None = None) -> str:
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
