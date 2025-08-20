#!/usr/bin/env python3
"""Agent creation and management for Cyber-AutoAgent."""

import os
import logging
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple, Any
from pathlib import Path

from strands import Agent
from strands.models import BedrockModel
from strands.models.ollama import OllamaModel
from strands.models.litellm import LiteLLMModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands_tools import shell, editor, load_tool, stop, http_request, swarm, python_repl, handoff_to_user

from modules import prompts
from modules.config.manager import get_config_manager
from modules.handlers import ReasoningHandler
from modules.handlers.utils import sanitize_target_name, print_status
from modules.tools.memory import mem0_memory, initialize_memory_system, get_memory_client

warnings.filterwarnings("ignore", category=DeprecationWarning)

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration object for agent creation."""
    target: str
    objective: str
    max_steps: int = 100
    available_tools: Optional[List[str]] = None
    op_id: Optional[str] = None
    model_id: Optional[str] = None
    region_name: Optional[str] = None
    provider: str = "bedrock"
    memory_path: Optional[str] = None
    memory_mode: str = "auto"
    module: str = "general"


def check_existing_memories(target: str, _provider: str = "bedrock") -> bool:
    """Check if existing memories exist for a target.

    Args:
        target: Target system being assessed
        provider: Provider type for configuration

    Returns:
        True if existing memories are detected, False otherwise
    """
    try:
        # Sanitize target name for consistent path handling
        target_name = sanitize_target_name(target)

        # Check based on backend type
        if os.environ.get("MEM0_API_KEY"):
            # Mem0 Platform - always check (cloud-based)
            return True

        elif os.environ.get("OPENSEARCH_HOST"):
            # OpenSearch - always check (remote service)
            return True

        else:
            # FAISS - check if local store exists with actual memory content
            # Create unified output structure path
            memory_base_path = os.path.join("outputs", target_name, "memory")

            # Check if memory directory exists and has FAISS index files
            if os.path.exists(memory_base_path):
                faiss_file = os.path.join(memory_base_path, "mem0.faiss")
                pkl_file = os.path.join(memory_base_path, "mem0.pkl")

                # Verify both FAISS index files exist and have non-zero size
                if (
                    os.path.exists(faiss_file)
                    and os.path.getsize(faiss_file) > 0
                    and os.path.exists(pkl_file)
                    and os.path.getsize(pkl_file) > 0
                ):
                    return True

        return False

    except Exception as e:
        logger.debug("Error checking existing memories: %s", str(e))
        return False


def _create_remote_model(
    model_id: str,
    region_name: str,
    provider: str = "bedrock",
) -> BedrockModel:
    """Create AWS Bedrock model instance using centralized configuration."""

    # Get centralized configuration
    config_manager = get_config_manager()

    if config_manager.is_thinking_model(model_id):
        # Use thinking model configuration
        config = config_manager.get_thinking_model_config(model_id, region_name)
        return BedrockModel(
            model_id=config["model_id"],
            region_name=config["region_name"],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
            additional_request_fields=config["additional_request_fields"],
        )
    # Standard model configuration
    config = config_manager.get_standard_model_config(model_id, region_name, provider)
    return BedrockModel(
        model_id=config["model_id"],
        region_name=config["region_name"],
        temperature=config["temperature"],
        max_tokens=config["max_tokens"],
        top_p=config["top_p"],
    )


def _create_local_model(
    model_id: str,
    provider: str = "ollama",
) -> Any:
    """Create Ollama model instance using centralized configuration."""

    # Get centralized configuration
    config_manager = get_config_manager()
    config = config_manager.get_local_model_config(model_id, provider)

    return OllamaModel(
        host=config["host"],
        model_id=config["model_id"],
        temperature=config["temperature"],
        max_tokens=config["max_tokens"],
    )


def _create_litellm_model(
    model_id: str,
    region_name: str,
    provider: str = "litellm",
) -> LiteLLMModel:
    """Create LiteLLM model instance for universal provider access."""

    # Get centralized configuration
    config_manager = get_config_manager()

    # Get standard configuration (LiteLLM doesn't have special thinking mode handling)
    config = config_manager.get_standard_model_config(model_id, region_name, provider)

    # Prepare client args based on model prefix
    client_args = {}

    # Configure AWS Bedrock models via LiteLLM
    if model_id.startswith("bedrock/"):
        client_args["aws_region_name"] = region_name

    return LiteLLMModel(
        client_args=client_args,
        model_id=config["model_id"],
        params={
            "temperature": config["temperature"],
            "max_tokens": config["max_tokens"],
            "top_p": config.get("top_p", 0.95),
        },
    )


def _handle_model_creation_error(provider: str, error: Exception) -> None:
    """Provide helpful error messages based on provider type"""

    error_messages = {
        "ollama": [
            "Ensure Ollama is installed: https://ollama.ai",
            "Start Ollama: ollama serve",
            "Pull required models (see config.py file)",
        ],
        "bedrock": [
            "Check AWS credentials and region settings",
            "Verify AWS_ACCESS_KEY_ID or AWS_BEARER_TOKEN_BEDROCK",
            "Ensure Bedrock access is enabled in your AWS account",
        ],
        "litellm": [
            "Check environment variables for your model provider",
            "For Bedrock: AWS_ACCESS_KEY_ID (bearer tokens not supported)",
            "For OpenAI: OPENAI_API_KEY",
            "For Anthropic: ANTHROPIC_API_KEY",
        ],
    }

    print_status(f"{provider.title()} model creation failed: {error}", "ERROR")
    if provider in error_messages:
        print_status("Troubleshooting steps:", "WARNING")
        for i, step in enumerate(error_messages[provider], 1):
            print_status(f"    {i}. {step}", "INFO")


def create_agent(
    target: str,
    objective: str,
    config: Optional[AgentConfig] = None,
) -> Tuple[Agent, ReasoningHandler]:
    """Create autonomous agent"""

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
        overrides['model_id'] = config.model_id
    
    server_config = config_manager.get_server_config(config.provider, **overrides)

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
        print_status("Using fresh memory mode - ignoring any existing memories", "WARNING")
    else:
        has_existing_memories = check_existing_memories(config.target, config.provider)

    # Initialize memory system
    target_name = sanitize_target_name(config.target)
    initialize_memory_system(memory_config, operation_id, target_name, has_existing_memories)
    print_status(f"Memory system initialized for operation: {operation_id}", "SUCCESS")
    # memory_overview = None  # Reserved for future system prompt enhancement

    # Get memory overview for system prompt enhancement and UI display
    memory_overview = None
    if has_existing_memories or config.memory_path:
        try:
            memory_client = get_memory_client()
            if memory_client:
                memory_overview = memory_client.get_memory_overview(user_id="cyber_agent")
        except Exception as e:
            agent_logger.debug("Could not get memory overview for system prompt: %s", str(e))

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
                    spec = importlib.util.spec_from_file_location(module_name, tool_path)
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
                    agent_logger.warning("Failed to load tool from %s: %s", tool_path, e)

            tool_names = [tool.__name__ for tool in loaded_module_tools] if loaded_module_tools else []

            if tool_names:
                print_status(
                    f"Loaded {len(tool_names)} module-specific tools for '{module}': {', '.join(tool_names)}", "SUCCESS"
                )
            else:
                # Fallback to just showing discovered tools
                tool_names = [Path(tool_path).stem for tool_path in module_tool_paths]
                print_status(
                    f"Discovered {len(module_tool_paths)} module-specific tools for '{module}' (will need load_tool)",
                    "INFO",
                )

            # Create specific tool examples for system prompt
            tool_examples = []
            if loaded_module_tools:
                # Tools are pre-loaded
                for tool_name in tool_names:
                    tool_examples.append(f"{tool_name}()  # Pre-loaded and ready to use")
            else:
                # Fallback to load_tool instructions
                for tool_name in tool_names:
                    tool_examples.append(
                        f'load_tool(path="/app/src/modules/operation_plugins/{module}/tools/{tool_name}.py", name="{tool_name}")'
                    )

            module_tools_context = f"""
## MODULE-SPECIFIC TOOLS

Available {module} module tools:
{", ".join(tool_names)}

{"Ready to use:" if loaded_module_tools else "Load these tools when needed:"}
{chr(10).join(f"- {example}" for example in tool_examples)}
"""
        else:
            print_status(f"No module-specific tools found for '{module}'", "INFO")
    except Exception as e:
        logger.warning("Error discovering module tools for '%s': %s", config.module, e)

    tools_context = ""
    if config.available_tools:
        tools_context = f"""
## ENVIRONMENTAL CONTEXT

Professional tools discovered in your environment:
{", ".join(config.available_tools)}

Leverage these tools directly via shell. 
"""

    # Combine environmental and module tools context
    # Combined tools context available for future use\n    # full_tools_context = tools_context + module_tools_context

    # Load module-specific execution prompt
    module_execution_prompt = None
    try:
        module_loader = prompts.get_module_loader()
        module_execution_prompt = module_loader.load_module_execution_prompt(config.module)
        if module_execution_prompt:
            print_status(f"Loaded module-specific execution prompt for '{config.module}'", "SUCCESS")
        else:
            print_status(f"No module-specific execution prompt found for '{config.module}' - using default", "INFO")
    except Exception as e:
        logger.warning("Error loading module execution prompt for '%s': %s", config.module, e)

    system_prompt = prompts.get_system_prompt(
        target=config.target,
        objective=config.objective,
        remaining_steps=config.max_steps,  # The new prompt uses remaining_steps
    )

    # Always use the React bridge handler as it has all the functionality we need
    # It works in both CLI and React modes
    from modules.handlers.react.react_bridge_handler import ReactBridgeHandler
    
    # Set up output interception to prevent duplicate output
    # This must be done before creating the handler to ensure all stdout is captured
    import os
    if os.environ.get("__REACT_INK__"):
        from modules.handlers.output_interceptor import setup_output_interception
        setup_output_interception()

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
            "tools_available": len(config.available_tools) if config.available_tools else 0,
            "memory": {
                "mode": config.memory_mode,
                "path": config.memory_path or None,
                "has_existing": has_existing_memories if 'has_existing_memories' in locals() else False,
                "reused": (has_existing_memories and config.memory_mode != "fresh") if 'has_existing_memories' in locals() else False,
                "backend": "mem0_cloud" if os.getenv("MEM0_API_KEY") else ("opensearch" if os.getenv("OPENSEARCH_HOST") else "faiss"),
                **(memory_overview if memory_overview and isinstance(memory_overview, dict) else {}),
            },
            "observability": (os.getenv("ENABLE_OBSERVABILITY", "false").lower() == "true"),
            "ui_mode": "react" if os.getenv("__REACT_INK__") else "cli",
        },
    )

    # No hooks needed - the callback handler handles everything
    hooks = None

    # Create model based on provider type
    try:
        if config.provider == "ollama":
            agent_logger.debug("Configuring OllamaModel")
            model = _create_local_model(config.model_id, config.provider)
            print_status(f"Ollama model initialized: {config.model_id}", "SUCCESS")
        elif config.provider == "bedrock":
            agent_logger.debug("Configuring BedrockModel")
            model = _create_remote_model(config.model_id, config.region_name, config.provider)
            print_status(f"Bedrock model initialized: {config.model_id}", "SUCCESS")
        elif config.provider == "litellm":
            agent_logger.debug("Configuring LiteLLMModel")
            model = _create_litellm_model(config.model_id, config.region_name, config.provider)
            print_status(f"LiteLLM model initialized: {config.model_id}", "SUCCESS")
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

    except Exception as e:
        _handle_model_creation_error(config.provider, e)
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
        handoff_to_user,
    ]

    # Inject module-specific tools if available
    if "loaded_module_tools" in locals() and loaded_module_tools:
        tools_list.extend(loaded_module_tools)
        agent_logger.info("Injected %d module tools into agent", len(loaded_module_tools))

    agent_logger.debug("Creating autonomous agent")

    # Update conversation window size from SDK config
    conversation_window = server_config.sdk.conversation_window_size

    # Create agent with telemetry for token tracking
    agent_kwargs = {
        "model": model,
        "name": f"Cyber-AutoAgent {config.op_id or operation_id}",
        "tools": tools_list,
        "system_prompt": system_prompt,
        "callback_handler": callback_handler,
        "hooks": hooks if hooks else None,  # Add hooks if available
        "conversation_manager": SlidingWindowConversationManager(window_size=conversation_window),
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
            "langfuse.environment": os.getenv("DEPLOYMENT_ENV", "production"),
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
            "model.region": config.region_name if config.provider in ["bedrock", "litellm"] else "local",
            "gen_ai.request.model": config.model_id,
            # Tool configuration
            "tools.available": 11,  # Number of core tools
            "tools.names": [
                "swarm",
                "shell",
                "editor",
                "load_tool",
                "mem0_memory",
                "stop",
                "http_request",
                "python_repl",
                "handoff_to_user",
            ],
            "tools.parallel_limit": 8,
            # Memory configuration
            "memory.enabled": True,
            "memory.path": config.memory_path if config.memory_path else "ephemeral",
        },
    }

    # Create agent (telemetry is handled globally by Strands SDK)
    agent = Agent(**agent_kwargs)

    agent_logger.debug("Agent initialized successfully")
    return agent, callback_handler
