#!/usr/bin/env python3
"""Agent creation and management for Cyber-AutoAgent."""

import atexit
import json
import logging
import os
import signal
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

from strands import Agent
from strands.types.tools import AgentTool
from strands.tools.mcp.mcp_client import MCPClient
from strands_tools.editor import editor
from strands_tools.http_request import http_request
from strands_tools.load_tool import load_tool
from strands_tools.python_repl import python_repl
from strands_tools.shell import shell
from strands_tools.stop import stop
from strands_tools.swarm import swarm
from mcp import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.sse import sse_client

from modules import prompts
from modules.config import (
    AgentConfig,
    align_mem0_config,
    check_existing_memories,
    configure_sdk_logging,
    get_config_manager,
)
from modules.config.types import MCPConnection, ServerConfig
from modules.config.system.logger import get_logger
from modules.config.models.factory import (
    create_bedrock_model,
    create_ollama_model,
    create_litellm_model,
    _handle_model_creation_error,
    _resolve_prompt_token_limit,
)
from modules.handlers import ReasoningHandler
from modules.handlers.conversation_budget import (
    MappingConversationManager,
    PromptBudgetHook,
    LargeToolResultMapper,
    register_conversation_manager,
    _ensure_prompt_within_budget,
    PRESERVE_LAST_DEFAULT,
    PRESERVE_FIRST_DEFAULT,
)
from modules.handlers.tool_router import ToolRouterHook
from modules.config.models.capabilities import get_capabilities
from modules.handlers.utils import print_status, sanitize_target_name, get_output_path
from modules.tools.browser import (
    initialize_browser,
    browser_goto_url,
    browser_observe_page,
    browser_get_page_html,
    browser_set_headers,
    browser_perform_action,
    browser_evaluate_js,
    browser_get_cookies,
)
from modules.tools.mcp import (
    list_mcp_tools_wrapper,
    mcp_tools_input_schema_to_function_call,
    with_result_file,
    resolve_env_vars_in_dict,
    resolve_env_vars_in_list,
)
from modules.tools.memory import (
    get_memory_client,
    initialize_memory_system,
    mem0_memory,
)
from modules.handlers.hitl import FeedbackInputHandler, FeedbackManager, HITLHookProvider
from modules.config.manager import get_config_manager
from modules.handlers import ReasoningHandler
from modules.handlers.hitl import (
    FeedbackInputHandler,
    FeedbackManager,
    HITLHookProvider,
    setup_hitl_logging,
)
from modules.handlers.hitl.feedback_injection_hook import HITLFeedbackInjectionHook
from modules.handlers.hitl.hitl_logger import log_hitl
from modules.handlers.utils import print_status, sanitize_target_name
from modules.tools.memory import (
    get_memory_client,
    initialize_memory_system,
    mem0_memory,
)
from modules.tools.prompt_optimizer import prompt_optimizer

warnings.filterwarnings("ignore", category=DeprecationWarning)

logger = get_logger("Agents.CyberAutoAgent")

# Backward compatibility: expose get_system_prompt from modules.prompts for legacy imports/tests
get_system_prompt = prompts.get_system_prompt

# Model creation logic has been extracted to modules.config.models.factory
# for better separation of concerns. See imports above for available functions.


def _discover_mcp_tools(config: AgentConfig, server_config: ServerConfig) -> List[AgentTool]:
    """Discover and register MCP tools from configured connections."""
    mcp_tools = []
    environ = os.environ.copy()
    for mcp_conn in (config.mcp_connections or []):
        if '*' in mcp_conn.plugins or config.module in mcp_conn.plugins:
            logger.debug("Discover MCP tools from: %s", mcp_conn)
            try:
                headers = resolve_env_vars_in_dict(mcp_conn.headers, environ)
                match mcp_conn.transport:
                    case "stdio":
                        if not mcp_conn.command:
                            raise ValueError(f"{mcp_conn.transport} requires command")
                        command_list: List[str] = resolve_env_vars_in_list(mcp_conn.command, environ)
                        transport = lambda: stdio_client(StdioServerParameters(
                            command = command_list[0], args=command_list[1:],
                            env=environ,
                        ))
                    case "streamable-http":
                        transport = lambda: streamablehttp_client(
                            url=mcp_conn.server_url,
                            headers=headers,
                            timeout=mcp_conn.timeoutSeconds if mcp_conn.timeoutSeconds else 30,
                        )
                    case "sse":
                        transport = lambda: sse_client(
                            url=mcp_conn.server_url,
                            headers=headers,
                            timeout=mcp_conn.timeoutSeconds if mcp_conn.timeoutSeconds else 30,
                        )
                    case _:
                        raise ValueError(f"Unsupported MCP transport {mcp_conn.transport}")
                client = MCPClient(transport, prefix=mcp_conn.id)
                prefix_idx = len(mcp_conn.id) + 1
                client.start()
                client_used = False
                page_token = None
                while len(tools := client.list_tools_sync(page_token)) > 0:
                    page_token = tools.pagination_token
                    for tool in tools:
                        logger.debug(f"Considering tool: {tool.tool_name}")
                        if '*' in mcp_conn.allowed_tools or tool.tool_name[prefix_idx:] in mcp_conn.allowed_tools:
                            logger.debug(f"Allowed tool: {tool.tool_name}")
                            # Wrap output and save into output path
                            output_base_path = get_output_path(
                                sanitize_target_name(config.target),
                                config.op_id,
                                sanitize_target_name(tool.tool_name),
                                server_config.output.base_dir,
                            )
                            tool = with_result_file(tool, Path(output_base_path))
                            mcp_tools.append(tool)
                            client_used = True
                    if not page_token:
                        break
                client_stop = lambda *_: client.stop(exc_type=None, exc_val=None, exc_tb=None)
                if client_used:
                    atexit.register(client_stop)
                    signal.signal(signal.SIGTERM, client_stop)
                else:
                    client_stop()
            except Exception as e:
                logger.error(f"Communicating with MCP: {repr(mcp_conn)}", exc_info=e)
                raise e

    return mcp_tools


def create_agent(
    target: str,
    objective: str,
    config: Optional[AgentConfig] = None,
) -> Tuple[Agent, ReasoningHandler]:
    """Create autonomous agent"""

    # Enable comprehensive SDK logging for debugging
    configure_sdk_logging(enable_debug=True)

    # Use provided config or create default
    if config is None:
        config = AgentConfig(target=target, objective=objective)
    else:
        config.target = target
        config.objective = objective

    agent_logger = logging.getLogger("CyberAutoAgent")
    agent_logger.debug(
        "Creating agent for target: %s, objective: %s, provider: %s",
        config.target,
        config.objective,
        config.provider,
    )

    # Get configuration from ConfigManager
    config_manager = get_config_manager()
    config_manager.validate_requirements(config.provider)

    # Prepare overrides if user specified a model
    overrides = {}
    if config.model_id:
        # Override both LLM and memory LLM with the user-specified model
        overrides["model_id"] = config.model_id

    server_config = config_manager.get_server_config(config.provider, **overrides)

    # Get HITL configuration
    hitl_config = server_config.hitl

    # Get centralized region configuration
    if config.region_name is None:
        config.region_name = config_manager.get_default_region()

    # Use provided model_id or default
    if config.model_id is None:
        config.model_id = server_config.llm.model_id

    # Use provided operation_id or generate new one
    if not config.op_id:
        operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    else:
        operation_id = config.op_id

    # Configure memory system using centralized configuration
    memory_config = config_manager.get_mem0_service_config(config.provider)
    align_mem0_config(config.model_id, memory_config)

    # Configure vector store with memory path if provided
    if config.memory_path:
        # Validate existing memory store path
        if not os.path.exists(config.memory_path):
            raise ValueError(f"Memory path does not exist: {config.memory_path}")
        if not os.path.isdir(config.memory_path):
            raise ValueError(f"Memory path is not a directory: {config.memory_path}")

        # Override vector store path in centralized config
        memory_config["vector_store"] = {"config": {"path": config.memory_path}}
        print_status(f"Loading existing memory from: {config.memory_path}", "SUCCESS")

    # Check for existing memories before initializing to avoid race conditions
    # Skip check if user explicitly wants fresh memory
    if config.memory_mode == "fresh":
        has_existing_memories = False
        print_status(
            "Using fresh memory mode - ignoring any existing memories", "WARNING"
        )
    else:
        has_existing_memories = check_existing_memories(config.target, config.provider)
        # Log the result for debugging container vs local issues
        if has_existing_memories:
            print_status(
                f"Previous memories detected for {config.target} - will be loaded",
                "SUCCESS",
            )
        else:
            print_status(
                f"No previous memories found for {config.target} - will create new",
                "INFO",
            )

    # Initialize memory system
    target_name = sanitize_target_name(config.target)

    # Ensure unified output directories (root + artifacts + tools) exist before any tools run
    paths: dict[str, str] = {}
    try:
        paths = config_manager.ensure_operation_output_dirs(
            config.provider, target_name, operation_id, module=config.module
        )
        print_status(
            f"Output directories ready: {paths.get('artifacts', '')}", "SUCCESS"
        )
    except Exception:
        # Non-fatal: proceed even if directory creation logs an error
        logger.debug("Failed to pre-create operation directories", exc_info=True)

    try:
        if paths:
            root_path = paths.get("root")
            artifacts_path = paths.get("artifacts")
            tools_path = paths.get("tools")
            if isinstance(root_path, str) and root_path:
                os.environ["CYBER_OPERATION_ROOT"] = root_path
            if isinstance(artifacts_path, str) and artifacts_path:
                os.environ["CYBER_ARTIFACTS_DIR"] = artifacts_path
            if isinstance(tools_path, str) and tools_path:
                os.environ["CYBER_TOOLS_DIR"] = tools_path
            if operation_id:
                os.environ["CYBER_OPERATION_ID"] = operation_id
            if target_name:
                os.environ["CYBER_TARGET_NAME"] = target_name

        # Fix python_repl race condition by disabling PTY mode
        os.environ["PYTHON_REPL_INTERACTIVE"] = "false"
    except Exception:
        logger.debug("Unable to set overlay environment context", exc_info=True)

    initialize_browser(
        provider=config.provider,
        model=config.model_id,
        artifacts_dir=os.getenv("CYBER_ARTIFACTS_DIR"),
    )
    initialize_memory_system(
        memory_config, operation_id, target_name, has_existing_memories
    )
    print_status(f"Memory system initialized for operation: {operation_id}", "SUCCESS")

    # Get memory overview for system prompt enhancement and UI display
    memory_overview = None
    if has_existing_memories or config.memory_path:
        try:
            memory_client = get_memory_client()
            if memory_client:
                memory_overview = memory_client.get_memory_overview(
                    user_id="cyber_agent"
                )
        except Exception as e:
            agent_logger.debug(
                "Could not get memory overview for system prompt: %s", str(e)
            )

    # Load module-specific tools and prepare for injection
    module_tools_context = ""
    loaded_module_tools = []

    try:
        module_loader = prompts.get_module_loader()
        module_tool_paths = module_loader.discover_module_tools(config.module)

        if module_tool_paths:
            import importlib.util
            import sys

            # Dynamically load each tool module
            for tool_path in module_tool_paths:
                try:
                    # Load the module
                    module_name = f"operation_plugin_tool_{Path(tool_path).stem}"
                    spec = importlib.util.spec_from_file_location(
                        module_name, tool_path
                    )
                    if spec and spec.loader:
                        tool_module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = tool_module
                        spec.loader.exec_module(tool_module)

                        # Find all @tool decorated functions
                        for attr_name in dir(tool_module):
                            attr = getattr(tool_module, attr_name)
                            if callable(attr) and hasattr(attr, "__wrapped__"):
                                # Check if this is a @tool decorated function
                                loaded_module_tools.append(attr)
                                agent_logger.debug("Found module tool: %s", attr_name)

                except Exception as e:
                    agent_logger.warning(
                        "Failed to load tool from %s: %s", tool_path, e
                    )

            tool_names = (
                [tool.__name__ for tool in loaded_module_tools]
                if loaded_module_tools
                else []
            )

            if tool_names:
                print_status(
                    f"Loaded {len(tool_names)} module-specific tools for '{config.module}': {', '.join(tool_names)}",
                    "SUCCESS",
                )
            else:
                # Fallback to just showing discovered tools
                tool_names = [Path(tool_path).stem for tool_path in module_tool_paths]
                print_status(
                    f"Discovered {len(module_tool_paths)} module-specific tools for '{config.module}' (will need load_tool)",
                    "INFO",
                )
            # Log module and tool discovery explicitly for validation
            try:
                agent_logger.info(
                    "CYBERAUTOAGENT: module='%s', tools_discovered=%d, tools='%s'",
                    config.module,
                    len(tool_names),
                    ", ".join(tool_names),
                )
            except Exception:
                pass

            # Create specific tool examples for system prompt
            tool_examples = []
            if loaded_module_tools:
                # Tools are pre-loaded
                for tool_name in tool_names:
                    tool_examples.append(
                        f"{tool_name}()  # Pre-loaded and ready to use"
                    )
            else:
                # Fallback to load_tool instructions using discovered absolute paths
                # This works in both local CLI and Docker since module_tool_paths are resolved in the current runtime
                for tool_path in module_tool_paths:
                    try:
                        abs_path = str(Path(tool_path).resolve())
                        tool_name = Path(tool_path).stem
                        tool_examples.append(
                            f'load_tool(path="{abs_path}", name="{tool_name}")'
                        )
                    except Exception:
                        # As a last resort, include a name-only hint
                        tool_name = Path(tool_path).stem
                        tool_examples.append(
                            f"# load_tool path resolution failed for {tool_name}"
                        )

            module_tools_context = f"""
## MODULE-SPECIFIC TOOLS

Available {config.module} module tools:
{", ".join(tool_names)}

{"Ready to use:" if loaded_module_tools else "Load these tools when needed:"}
{chr(10).join(f"- {example}" for example in tool_examples)}
"""
        else:
            print_status(
                f"No module-specific tools found for '{config.module}'", "INFO"
            )
    except Exception as e:
        logger.warning("Error discovering module tools for '%s': %s", config.module, e)

    tools_context = ""
    if config.available_tools:
        tools_context = f"""
## ENVIRONMENTAL CONTEXT

Cyber Tools available in this environment:
{", ".join(config.available_tools)}

Guidance and tool names in prompts are illustrative, not prescriptive. Always check availability and prefer tools present in this list. If a capability is missing, follow Ask-Enable-Retry for minimal, non-interactive enablement, or choose an equivalent available tool.
"""

    # Load MCP tools and prepare for injection
    mcp_tools = _discover_mcp_tools(config, server_config)
    if mcp_tools:
        mcp_tools_context = f"""
## MCP TOOLS

Available {config.module} MCP tools:
- list_mcp_tools()  # full MCP tool catalog including input schema, output schema, description
{chr(10).join(f"- {mcp_tools_input_schema_to_function_call(mcp_tool.tool_spec.get('inputSchema'), mcp_tool.tool_name)}" for mcp_tool in mcp_tools)}
"""
    else:
        mcp_tools_context = ""

    # Combine environmental and module tools context
    # Prefer to include both environment-detected tools and module-specific tools
    full_tools_context = ""
    if tools_context:
        full_tools_context += str(tools_context)
    for tools_ctx in [module_tools_context, mcp_tools_context]:
        if tools_ctx:
            if full_tools_context:
                full_tools_context += "\n\n"
            full_tools_context += str(tools_ctx)

    # Load module-specific execution prompt
    module_execution_prompt = None
    try:
        module_loader = prompts.get_module_loader()
        # Pass operation root to enable loading optimized execution prompt
        operation_root_path = paths.get("root") if paths else None
        module_execution_prompt = module_loader.load_module_execution_prompt(
            config.module, operation_root=operation_root_path
        )
        if module_execution_prompt:
            print_status(
                f"Loaded module-specific execution prompt for '{config.module}'",
                "SUCCESS",
            )
        else:
            print_status(
                f"No module-specific execution prompt found for '{config.module}' - using default",
                "INFO",
            )
        # Emit explicit config log for module and execution prompt source
        exec_src = (
            getattr(module_loader, "last_loaded_execution_prompt_source", None)
            or "default (none found)"
        )
        agent_logger.info(
            "CYBERAUTOAGENT: module='%s', execution_prompt_source='%s'",
            config.module,
            exec_src,
        )
    except Exception as e:
        logger.warning(
            "Error loading module execution prompt for '%s': %s", config.module, e
        )

    # Optionally build a concise plan snapshot from memory (best-effort, no hard dependency)
    plan_snapshot = None
    plan_current_phase = None
    try:
        memory_client = get_memory_client(silent=True)
        if memory_client:
            active_plan = memory_client.get_active_plan(user_id="cyber_agent")
            if active_plan:
                # First try to get JSON from metadata
                plan_json = active_plan.get("metadata", {}).get("plan_json")

                # If we have JSON, create a rich snapshot
                if plan_json and isinstance(plan_json, dict):
                    try:
                        plan_current_phase = plan_json.get("current_phase", 1)
                        objective = plan_json.get("objective", "Unknown objective")
                        phases = plan_json.get("phases", [])

                        # Find current phase details
                        current_phase_info = None
                        for phase in phases:
                            if (
                                phase.get("id") == plan_current_phase
                                or phase.get("status") == "active"
                            ):
                                current_phase_info = phase
                                break

                        # Build comprehensive snapshot
                        snap_lines = []
                        snap_lines.append(f"Objective: {objective}")
                        if current_phase_info:
                            snap_lines.append(
                                f"CurrentPhase: {current_phase_info.get('title', 'Unknown')} (Phase {plan_current_phase}/{len(phases)})"
                            )
                            snap_lines.append(
                                f"Criteria: {current_phase_info.get('criteria', 'No criteria defined')}"
                            )

                        plan_snapshot = "\n".join(snap_lines)
                    except Exception as e:
                        logger.debug("Error creating plan snapshot from JSON: %s", e)

                # Fallback to text extraction if no JSON
                if not plan_snapshot:
                    raw = active_plan.get("memory") or active_plan.get("content", "")
                    if isinstance(raw, str) and raw:
                        # Best-effort extraction: find first active/pending phase and any criteria line
                        phase_line = None
                        criteria_line = None
                        for line in raw.split("\n"):
                            ls = line.strip()
                            # Look for phase lines in format: "Phase X [STATUS]: title - criteria"
                            if not phase_line and ls.lower().startswith("phase"):
                                # Check if it's an active phase
                                if "[ACTIVE]" in ls or "[active]" in ls.upper():
                                    phase_line = ls
                                    # Extract criteria from the same line (after the dash)
                                    if " - " in ls and not criteria_line:
                                        criteria_line = ls.split(" - ", 1)[1]
                            if phase_line and criteria_line:
                                break
                    # Try JSON extraction first (plan stored as JSON or within [PLAN] {json})
                    plan_json = None
                    try:
                        brace = raw.find("{")
                        if brace != -1:
                            plan_json = json.loads(raw[brace:])
                    except Exception:
                        plan_json = None
                    if isinstance(plan_json, dict):
                        try:
                            cph = plan_json.get("current_phase")
                            if isinstance(cph, int):
                                plan_current_phase = cph
                            else:
                                phases = plan_json.get("phases") or []
                                if isinstance(phases, list):
                                    for ph in phases:
                                        if (
                                            isinstance(ph, dict)
                                            and ph.get("status") == "active"
                                        ):
                                            pid = ph.get("id")
                                            if isinstance(pid, int):
                                                plan_current_phase = pid
                                                break
                        except Exception:
                            pass
                    # Compose snapshot with up to three lines
                    snap_lines = []
                    if phase_line:
                        # Clean up the phase line for display
                        clean_phase = (
                            phase_line.replace("[ACTIVE]", "")
                            .replace("[PENDING]", "")
                            .replace("[COMPLETED]", "")
                            .strip()
                        )
                        snap_lines.append(f"CurrentPhase: {clean_phase}")
                    # Derive sub-objective from phase goal portion if present
                    sub_obj = None
                    try:
                        # Extract title from format: "Phase X [STATUS]: title - criteria"
                        if phase_line and ":" in phase_line:
                            after_colon = phase_line.split(":", 1)[1].strip()
                            if " - " in after_colon:
                                sub_obj = after_colon.split(" - ", 1)[0].strip()
                            else:
                                sub_obj = after_colon
                    except Exception:
                        sub_obj = None
                    if sub_obj:
                        snap_lines.append(f"Objective: {sub_obj}")
                    if criteria_line:
                        snap_lines.append(f"Criteria: {criteria_line}")
                    plan_snapshot = "\n".join(snap_lines[:3]).strip() or None
    except Exception as e:
        logger.debug("Plan snapshot not available: %s", e)

    # Build system prompt using centralized prompt factory (memory-aware)
    system_prompt = prompts.get_system_prompt(
        target=config.target,
        objective=config.objective,
        operation_id=operation_id,
        max_steps=config.max_steps,
        provider=config.provider,
        has_memory_path=bool(config.memory_path),
        has_existing_memories=has_existing_memories,
        memory_overview=memory_overview,
        tools_context=full_tools_context if full_tools_context else None,
        output_config={
            "base_dir": server_config.output.base_dir,
            "target_name": target_name,
            "artifacts_path": paths.get("artifacts"),
            "tools_path": paths.get("tools"),
        },
        plan_snapshot=plan_snapshot,
        plan_current_phase=plan_current_phase,
    )

    # If a module-specific execution prompt exists, append it to the system prompt
    if module_execution_prompt:
        system_prompt = (
            system_prompt
            + "\n\n## MODULE EXECUTION GUIDANCE\n"
            + module_execution_prompt.strip()
        )

    # Build SystemContentBlock[] to enable provider-side prompt caching where supported
    # Keep legacy string fallback for providers that may not support block lists
    system_prompt_payload: Any
    try:
        if config.provider in ("bedrock", "litellm"):
            # Minimal segmentation: treat the composed system prompt as a single block and
            # add a cache point so supported backends can cache the stable portion.
            # Providers that do not support caching simply ignore the hint.
            system_prompt_payload = [
                {"text": system_prompt},
                {"cachePoint": {"type": "default"}},
            ]
        else:
            system_prompt_payload = system_prompt
    except Exception:
        system_prompt_payload = system_prompt

    # It works in both CLI and React modes
    from modules.handlers.react.react_bridge_handler import ReactBridgeHandler

    # Set up output interception to prevent duplicate output
    # This must be done before creating the handler to ensure all stdout is captured
    if os.environ.get("CYBER_UI_MODE", "cli").lower() == "react":
        from modules.handlers.output_interceptor import setup_output_interception

        setup_output_interception()

    # Ensure react package namespace is importable even if some submodules are removed
    # Tests import modules.handlers.react.react_bridge_handler directly
    try:
        from modules.handlers.react import ReactBridgeHandler as _RBH  # noqa: F401
    except Exception:
        pass

    # Check if HITL is enabled before creating handler so we can include it in init_context
    hitl_enabled = hitl_config.enabled

    callback_handler = ReactBridgeHandler(
        max_steps=config.max_steps,
        operation_id=operation_id,
        model_id=config.model_id,
        swarm_model_id=server_config.swarm.llm.model_id,
        init_context={
            "objective": config.objective,
            "target": config.target,
            "module": config.module,
            "provider": config.provider,
            "model": config.model_id,
            "region": config.region_name,
            "tools_available": len(config.available_tools)
            if config.available_tools
            else 0,
            "memory": {
                "mode": config.memory_mode,
                "path": config.memory_path or None,
                "has_existing": has_existing_memories
                if "has_existing_memories" in locals()
                else False,
                "reused": (
                    (has_existing_memories and config.memory_mode != "fresh")
                    if "has_existing_memories" in locals()
                    else False
                ),
                "backend": (
                    "mem0_cloud"
                    if config_manager.getenv("MEM0_API_KEY")
                    else (
                        "opensearch"
                        if config_manager.getenv("OPENSEARCH_HOST")
                        else "faiss"
                    )
                ),
                **(
                    memory_overview
                    if memory_overview and isinstance(memory_overview, dict)
                    else {}
                ),
            },
            "observability": (
                os.getenv("ENABLE_OBSERVABILITY", "false").lower() == "true"
            ),
            "ui_mode": os.getenv("CYBER_UI_MODE", "cli").lower(),
            "hitl_enabled": hitl_enabled,
        },
    )

    # Create hooks for SDK lifecycle events (tool invocations, etc.)
    # These work alongside the callback handler to capture all events
    from modules.handlers.react.hooks import ReactHooks

    # Use the same emitter as the callback handler for consistency
    react_hooks = ReactHooks(
        emitter=callback_handler.emitter, operation_id=operation_id
    )

    # Tool router to prevent unknown-tool failures by routing to shell before execution
    # Allow configurable truncation of large tool outputs via env var
    try:
        max_result_chars = int(os.getenv("CYBER_TOOL_MAX_RESULT_CHARS", "10000"))
    except Exception:
        max_result_chars = 10000
    try:
        artifact_threshold = int(
            os.getenv("CYBER_TOOL_RESULT_ARTIFACT_THRESHOLD", str(max_result_chars))
        )
    except Exception:
        artifact_threshold = max_result_chars
    tool_router_hook = ToolRouterHook(
        shell,
        max_result_chars=max_result_chars,
        artifacts_dir=paths.get("artifacts"),
        artifact_threshold=artifact_threshold,
    )

    # Create prompt rebuild hook for intelligent prompt updates
    from modules.handlers.prompt_rebuild_hook import PromptRebuildHook

    prompt_budget_hook = PromptBudgetHook(_ensure_prompt_within_budget)
    hooks = [tool_router_hook, react_hooks, prompt_budget_hook]
    agent_logger.info(
        "HOOK REGISTRATION: Created PromptBudgetHook, will register %d hooks total",
        len(hooks),
    )

    enable_prompt_optimization = (
        os.getenv("CYBER_ENABLE_PROMPT_OPTIMIZATION", "false").lower() == "true"
    )

    if enable_prompt_optimization:
        prompt_rebuild_hook = PromptRebuildHook(
            callback_handler=callback_handler,
            memory_instance=memory_client,
            config=config,
            target=config.target,
            objective=config.objective,
            operation_id=operation_id,
            max_steps=config.max_steps,
            module=config.module,
            rebuild_interval=20,
        )
        hooks.append(prompt_rebuild_hook)
    # Create HITL hook if enabled
    hitl_hook = None
    feedback_manager = None
    feedback_handler = None

    if hitl_enabled:
        # Setup HITL logging to dedicated file
        log_dir = os.path.join(artifacts_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        setup_hitl_logging(log_dir)
        log_hitl("CyberAgent", "HITL logging initialized", "INFO", operation_id=operation_id)

        # Initialize feedback manager with configuration
        feedback_manager = FeedbackManager(
            memory=memory_client,
            operation_id=operation_id,
            emitter=callback_handler.emitter,
            hitl_config=hitl_config,
        )
        log_hitl("CyberAgent", "FeedbackManager created", "INFO")

        # Initialize feedback input handler for receiving UI commands
        feedback_handler = FeedbackInputHandler(feedback_manager=feedback_manager)
        feedback_handler.start_listening()
        log_hitl("CyberAgent", "FeedbackInputHandler started listening", "INFO")

        # Create HITL hook provider using centralized configuration
        hitl_hook = HITLHookProvider(
            feedback_manager=feedback_manager,
            auto_pause_on_destructive=hitl_config.auto_pause_on_destructive,
            auto_pause_on_low_confidence=hitl_config.auto_pause_on_low_confidence,
            confidence_threshold=hitl_config.confidence_threshold,
        )
        log_hitl("CyberAgent", "HITLHookProvider created", "INFO")

        # Create feedback injection hook for system prompt modification
        feedback_injection_hook = HITLFeedbackInjectionHook(
            feedback_manager=feedback_manager
        )
        log_hitl("CyberAgent", "HITLFeedbackInjectionHook created", "INFO")

        print_status("HITL system enabled - human feedback available", "SUCCESS")

    hooks = [react_hooks, prompt_rebuild_hook]
    if hitl_hook:
        hooks.append(hitl_hook)
        hooks.append(feedback_injection_hook)
        log_hitl(
            "CyberAgent",
            f"Hooks registered: {[type(h).__name__ for h in hooks]}",
            "INFO"
        )

    # Create model based on provider type
    try:
        if config.provider == "ollama":
            agent_logger.debug("Configuring OllamaModel")
            model = create_ollama_model(config.model_id, config.provider)
            print_status(f"Ollama model initialized: {config.model_id}", "SUCCESS")
        elif config.provider == "bedrock":
            agent_logger.debug("Configuring BedrockModel")
            model = create_bedrock_model(
                config.model_id, config.region_name, config.provider
            )
            print_status(f"Bedrock model initialized: {config.model_id}", "SUCCESS")
        elif config.provider == "litellm":
            agent_logger.debug("Configuring LiteLLMModel")
            model = create_litellm_model(
                config.model_id, config.region_name, config.provider
            )
            print_status(f"LiteLLM model initialized: {config.model_id}", "SUCCESS")
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

    except Exception as e:
        _handle_model_creation_error(config.provider, e)
        # Re-raise to satisfy tests expecting exception propagation after logging
        raise

    # Always use original tools - event emission is handled by callback
    tools_list = [
        swarm,
        shell,
        editor,
        load_tool,
        mem0_memory,
        stop,
        http_request,
        python_repl,
        browser_set_headers,
        browser_get_page_html,
        browser_goto_url,
        browser_perform_action,
        browser_observe_page,
        browser_evaluate_js,
        browser_get_cookies,
    ]

    if enable_prompt_optimization:
        tools_list.append(prompt_optimizer)

    # Capability-based warning if tool calls are unsupported for this model
    try:
        caps = get_capabilities(config.provider, config.model_id or "")
        if not caps.supports_tools and tools_list:
            agent_logger.warning(
                "Model %s does not support tool calls; tools will be ignored.",
                config.model_id,
            )
    except Exception:
        pass

    # Inject module-specific tools if available
    if "loaded_module_tools" in locals() and loaded_module_tools:
        tools_list.extend(loaded_module_tools)
        agent_logger.info(
            "Injected %d module tools into agent", len(loaded_module_tools)
        )

    # Inject MCP tools if available
    if "mcp_tools" in locals() and mcp_tools:
        tools_list.append(list_mcp_tools_wrapper(mcp_tools))
        tools_list.extend(mcp_tools)
        agent_logger.info("Injected %d MCP tools into agent", len(mcp_tools))

    agent_logger.debug("Creating autonomous agent")

    # Update conversation window size from SDK config (kept for reference)
    conversation_window = getattr(server_config.sdk, "conversation_window_size", None)
    try:
        window_size = (
            int(conversation_window) if conversation_window is not None else 30
        )
    except (TypeError, ValueError):
        window_size = 30
    window_size = max(10, window_size)

    # Create and register conversation manager for all agents (including swarm children)
    # Use environment variable for preserve_last (default 12) to enable effective pruning
    # If preserve_first (1) + preserve_last (20) >= total_messages, no pruning occurs
    conversation_manager = MappingConversationManager(
        window_size=window_size,
        summary_ratio=0.3,
        preserve_recent_messages=PRESERVE_LAST_DEFAULT,  # Use env default (12) instead of hardcoded 20
        preserve_first_messages=PRESERVE_FIRST_DEFAULT,  # Explicit (default 1)
        tool_result_mapper=LargeToolResultMapper(),
    )
    register_conversation_manager(conversation_manager)
    agent_logger.info(
        "Conversation manager created: window=%d, preserve_first=%d, preserve_last=%d",
        window_size,
        PRESERVE_FIRST_DEFAULT,
        PRESERVE_LAST_DEFAULT,
    )

    # Create agent with telemetry for token tracking
    prompt_token_limit = _resolve_prompt_token_limit(
        config.provider, server_config, config.model_id
    )

    agent_kwargs = {
        "model": model,
        "name": f"Cyber-AutoAgent {config.op_id or operation_id}",
        "tools": tools_list,
        "system_prompt": system_prompt_payload,
        "callback_handler": callback_handler,
        "hooks": hooks if hooks else None,  # Add hooks if available
        # Use proactive sliding + summarization fallback
        "conversation_manager": conversation_manager,
        "load_tools_from_directory": True,
        "trace_attributes": {
            # Core identification - session_id is the key for Langfuse trace naming
            "langfuse.session.id": operation_id,
            "langfuse.user.id": f"cyber-agent-{config.target}",
            # Human-readable name that Langfuse will pick up
            "name": f"Security Assessment - {config.target} - {operation_id}",
            # Tags for filtering and categorization
            "langfuse.tags": [
                "Cyber-AutoAgent",
                config.provider.upper(),
                operation_id,
            ],
            "langfuse.environment": config_manager.getenv(
                "DEPLOYMENT_ENV", "production"
            ),
            "langfuse.agent.type": "main_orchestrator",
            "langfuse.capabilities.swarm": True,
            # Standard OTEL attributes
            "session.id": operation_id,
            "user.id": f"cyber-agent-{config.target}",
            # Agent identification
            "agent.name": "Cyber-AutoAgent",
            "agent.version": "1.0.0",
            "gen_ai.agent.name": "Cyber-AutoAgent",
            "gen_ai.system": "Cyber-AutoAgent",
            # Operation metadata
            "operation.id": operation_id,
            "operation.type": "security_assessment",
            "operation.start_time": datetime.now().isoformat(),
            "operation.max_steps": config.max_steps,
            # Target and objective
            "target.host": config.target,
            "objective.description": config.objective,
            # Model configuration
            "model.provider": config.provider,
            "model.id": config.model_id,
            "model.region": config.region_name
            if config.provider in ["bedrock", "litellm"]
            else "local",
            "gen_ai.request.model": config.model_id,
            # Tool configuration
            "tools.available": len(tools_list),
            "tools.names": [
                "swarm",
                "shell",
                "editor",
                "load_tool",
                "mem0_memory",
                "stop",
                "http_request",
                "python_repl",
                "browser_set_headers",
                "browser_goto_url",
                "browser_get_page_html",
                "browser_perform_action",
                "browser_observe_page",
            ],
            "tools.parallel_limit": 8,
            # Memory configuration
            "memory.enabled": True,
            "memory.path": config.memory_path if config.memory_path else "ephemeral",
        },
    }

    # Create agent (telemetry is handled globally by Strands SDK)
    agent = Agent(**agent_kwargs)
    # Allow reasoning deltas only when the provider/model supports them
    try:
        caps = get_capabilities(config.provider, config.model_id or "")
        setattr(agent, "_allow_reasoning_content", bool(caps.supports_reasoning))
    except Exception:
        setattr(agent, "_allow_reasoning_content", False)
    if prompt_token_limit:
        setattr(agent, "_prompt_token_limit", prompt_token_limit)
    # Ensure legacy-compatible system prompt is directly accessible for tests
    try:
        setattr(agent, "system_prompt", system_prompt)
    except Exception:
        pass

    agent_logger.debug("Agent initialized successfully")
    return agent, callback_handler, feedback_manager
