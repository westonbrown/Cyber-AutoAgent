#!/usr/bin/env python3
"""Agent creation and management for Cyber-AutoAgent."""

import os
import logging
import warnings
from datetime import datetime
from typing import Optional, List, Tuple, Any
from pathlib import Path

from strands import Agent
from strands.models import BedrockModel
from strands.models.ollama import OllamaModel
from strands.models.litellm import LiteLLMModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands_tools import shell, editor, load_tool, stop, http_request, swarm, think, python_repl, handoff_to_user

from modules.prompts.system import get_system_prompt
from modules.prompts.module_loader import get_module_loader
from modules.config.manager import get_config_manager
from modules.handlers import ReasoningHandler
from modules.handlers.utils import Colors, sanitize_target_name, print_status
from modules.tools.memory import mem0_memory, initialize_memory_system, get_memory_client

warnings.filterwarnings("ignore", category=DeprecationWarning)

logger = logging.getLogger(__name__)


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
    max_steps: int = 100,
    available_tools: Optional[List[str]] = None,
    op_id: Optional[str] = None,
    model_id: Optional[str] = None,
    region_name: Optional[str] = None,
    provider: str = "bedrock",
    memory_path: Optional[str] = None,
    memory_mode: str = "auto",
    module: str = "general",
) -> Tuple[Agent, ReasoningHandler]:
    """Create autonomous agent"""

    agent_logger = logging.getLogger("CyberAutoAgent")
    agent_logger.debug(
        "Creating agent for target: %s, objective: %s, provider: %s",
        target,
        objective,
        provider,
    )

    # Get configuration from ConfigManager
    config_manager = get_config_manager()
    config_manager.validate_requirements(provider)
    server_config = config_manager.get_server_config(provider)

    # Get centralized region configuration
    if region_name is None:
        region_name = config_manager.get_default_region()

    # Use provided model_id or default
    if model_id is None:
        model_id = server_config.llm.model_id

    # Use provided operation_id or generate new one
    if not op_id:
        operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    else:
        operation_id = op_id

    # Configure memory system using centralized configuration
    memory_config = config_manager.get_mem0_service_config(provider)

    # Configure vector store with memory path if provided
    if memory_path:
        # Validate existing memory store path
        if not os.path.exists(memory_path):
            raise ValueError(f"Memory path does not exist: {memory_path}")
        if not os.path.isdir(memory_path):
            raise ValueError(f"Memory path is not a directory: {memory_path}")

        # Override vector store path in centralized config
        memory_config["vector_store"] = {"config": {"path": memory_path}}
        print_status(f"Loading existing memory from: {memory_path}", "SUCCESS")

    # Check for existing memories before initializing to avoid race conditions
    # Skip check if user explicitly wants fresh memory
    if memory_mode == "fresh":
        has_existing_memories = False
        print_status("Using fresh memory mode - ignoring any existing memories", "WARNING")
    else:
        has_existing_memories = check_existing_memories(target, provider)

    # Initialize memory system
    target_name = sanitize_target_name(target)
    initialize_memory_system(memory_config, operation_id, target_name, has_existing_memories)
    print_status(f"Memory system initialized for operation: {operation_id}", "SUCCESS")
    memory_overview = None

    # Get memory overview for system prompt enhancement
    if has_existing_memories or memory_path:
        try:
            memory_client = get_memory_client()
            if memory_client:
                memory_overview = memory_client.get_memory_overview(user_id="cyber_agent")
        except Exception as e:
            agent_logger.debug("Could not get memory overview for system prompt: %s", str(e))

    # Load module-specific tools information
    module_tools_context = ""
    try:
        module_loader = get_module_loader()
        module_tool_paths = module_loader.discover_module_tools(module)

        if module_tool_paths:
            tool_names = [Path(tool_path).stem for tool_path in module_tool_paths]
            print_status(f"Discovered {len(module_tool_paths)} module-specific tools for '{module}'", "SUCCESS")

            module_tools_context = f"""
## MODULE-SPECIFIC TOOLS

Available {module} module tools (use load_tool to activate):
{", ".join(tool_names)}

Load these tools when needed: load_tool(tool_name="tool_name")
"""
        else:
            print_status(f"No module-specific tools found for '{module}'", "INFO")
    except Exception as e:
        logger.warning(f"Error discovering module tools for '{module}': {e}")

    tools_context = ""
    if available_tools:
        tools_context = f"""
## ENVIRONMENTAL CONTEXT

Professional tools discovered in your environment:
{", ".join(available_tools)}

Leverage these tools directly via shell. 
"""

    # Combine environmental and module tools context
    full_tools_context = tools_context + module_tools_context

    # Load module-specific execution prompt
    module_execution_prompt = None
    try:
        module_loader = get_module_loader()
        module_execution_prompt = module_loader.load_module_execution_prompt(module)
        if module_execution_prompt:
            print_status(f"Loaded module-specific execution prompt for '{module}'", "SUCCESS")
        else:
            print_status(f"No module-specific execution prompt found for '{module}' - using default", "INFO")
    except Exception as e:
        logger.warning(f"Error loading module execution prompt for '{module}': {e}")

    system_prompt = get_system_prompt(
        target,
        objective,
        max_steps,
        operation_id,
        full_tools_context,
        provider,
        has_memory_path=bool(memory_path),
        has_existing_memories=has_existing_memories,
        memory_overview=memory_overview,
        module_context=module_execution_prompt,
    )

    # Always use the React bridge handler as it has all the functionality we need
    # It works in both CLI and React modes
    from modules.handlers.react.react_bridge_handler import ReactBridgeHandler

    callback_handler = ReactBridgeHandler(
        max_steps=max_steps,
        operation_id=operation_id,
    )

    # No hooks needed - the callback handler handles everything
    hooks = []

    # Create model based on provider type
    try:
        if provider == "ollama":
            agent_logger.debug("Configuring OllamaModel")
            model = _create_local_model(model_id, provider)
            print_status(f"Ollama model initialized: {model_id}", "SUCCESS")
        elif provider == "bedrock":
            agent_logger.debug("Configuring BedrockModel")
            model = _create_remote_model(model_id, region_name, provider)
            print_status(f"Bedrock model initialized: {model_id}", "SUCCESS")
        elif provider == "litellm":
            agent_logger.debug("Configuring LiteLLMModel")
            model = _create_litellm_model(model_id, region_name, provider)
            print_status(f"LiteLLM model initialized: {model_id}", "SUCCESS")
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    except Exception as e:
        _handle_model_creation_error(provider, e)
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
        think,
        python_repl,
        handoff_to_user,
    ]

    agent_logger.debug("Creating autonomous agent")

    # Update conversation window size from SDK config
    conversation_window = server_config.sdk.conversation_window_size

    agent = Agent(
        model=model,
        name=f"Cyber-AutoAgent {op_id}",
        tools=tools_list,
        system_prompt=system_prompt,
        callback_handler=callback_handler,
        hooks=hooks if hooks else None,  # Add hooks if available
        conversation_manager=SlidingWindowConversationManager(window_size=conversation_window),
        load_tools_from_directory=True,
        trace_attributes={
            # Core identification - session_id is the key for Langfuse trace naming
            "langfuse.session.id": operation_id,
            "langfuse.user.id": f"cyber-agent-{target}",
            # Human-readable name that Langfuse will pick up
            "name": f"Security Assessment - {target} - {operation_id}",
            # Tags for filtering and categorization
            "langfuse.tags": [
                "Cyber-AutoAgent",
                provider.upper(),
                operation_id,
            ],
            "langfuse.environment": os.getenv("DEPLOYMENT_ENV", "production"),
            "langfuse.agent.type": "main_orchestrator",
            "langfuse.capabilities.swarm": True,
            # Standard OTEL attributes
            "session.id": operation_id,
            "user.id": f"cyber-agent-{target}",
            # Agent identification
            "agent.name": "Cyber-AutoAgent",
            "agent.version": "1.0.0",
            "gen_ai.agent.name": "Cyber-AutoAgent",
            "gen_ai.system": "Cyber-AutoAgent",
            # Operation metadata
            "operation.id": operation_id,
            "operation.type": "security_assessment",
            "operation.start_time": datetime.now().isoformat(),
            "operation.max_steps": max_steps,
            # Target and objective
            "target.host": target,
            "objective.description": objective,
            # Model configuration
            "model.provider": provider,
            "model.id": model_id,
            "model.region": region_name if provider in ["bedrock", "litellm"] else "local",
            "gen_ai.request.model": model_id,
            # Tool configuration
            "tools.available": 10,  # Number of core tools
            "tools.names": [
                "swarm",
                "shell",
                "editor",
                "load_tool",
                "mem0_memory",
                "stop",
                "http_request",
                "think",
                "python_repl",
            ],
            "tools.parallel_limit": 8,
            # Memory configuration
            "memory.enabled": True,
            "memory.path": memory_path if memory_path else "ephemeral",
        },
    )

    agent_logger.debug("Agent initialized successfully")
    return agent, callback_handler
