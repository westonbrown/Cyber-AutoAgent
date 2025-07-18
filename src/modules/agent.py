#!/usr/bin/env python3
"""Agent creation and management for Cyber-AutoAgent."""

import os
import logging
import warnings
from datetime import datetime
from typing import Optional, List, Tuple, Any

from strands import Agent
from strands.models import BedrockModel
from strands.models.ollama import OllamaModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands_tools import shell, editor, load_tool, stop, http_request
from strands_tools.swarm import swarm

from .system_prompts import get_system_prompt
from .config import get_config_manager
from .agent_handlers import ReasoningHandler
from .utils import Colors, sanitize_target_name
from .memory_tools import mem0_memory, initialize_memory_system

warnings.filterwarnings("ignore", category=DeprecationWarning)

logger = logging.getLogger(__name__)


def check_existing_memories(target: str, server: str = "remote") -> bool:
    """Check if existing memories exist for a target.

    Args:
        target: Target system being assessed
        server: Server type for configuration

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
            # FAISS - check if local store exists
            # Create unified output structure path
            memory_base_path = os.path.join("outputs", target_name, "memory")

            # Check if memory directory exists and has content
            if os.path.exists(memory_base_path) and os.listdir(memory_base_path):
                return True

        return False

    except Exception as e:
        logger.debug("Error checking existing memories: %s", str(e))
        return False


def _create_remote_model(
    model_id: str,
    region_name: str,
    server: str = "remote",
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
    config = config_manager.get_standard_model_config(model_id, region_name, server)
    return BedrockModel(
        model_id=config["model_id"],
        region_name=config["region_name"],
        temperature=config["temperature"],
        max_tokens=config["max_tokens"],
        top_p=config["top_p"],
    )


def _create_local_model(
    model_id: str,
    server: str = "local",
) -> Any:
    """Create Ollama model instance using centralized configuration."""

    # Get centralized configuration
    config_manager = get_config_manager()
    config = config_manager.get_local_model_config(model_id, server)

    return OllamaModel(
        host=config["host"],
        model_id=config["model_id"],
        temperature=config["temperature"],
        max_tokens=config["max_tokens"],
    )


def _handle_model_creation_error(server: str, error: Exception) -> None:
    """Provide helpful error messages based on server type"""
    if server == "local":
        print(f"{Colors.RED}[!] Local model creation failed: {error}{Colors.RESET}")
        print(f"{Colors.YELLOW}[?] Troubleshooting steps:{Colors.RESET}")
        print("    1. Ensure Ollama is installed: https://ollama.ai")
        print("    2. Start Ollama: ollama serve")
        print("    3. Pull required models (see config.py file)")
    else:
        print(f"{Colors.RED}[!] Remote model creation failed: {error}{Colors.RESET}")
        print(
            f"{Colors.YELLOW}[?] Check AWS credentials and region settings{Colors.RESET}"
        )


def create_agent(
    target: str,
    objective: str,
    max_steps: int = 100,
    available_tools: Optional[List[str]] = None,
    op_id: Optional[str] = None,
    model_id: Optional[str] = None,
    region_name: str = None,
    server: str = "remote",
    memory_path: Optional[str] = None,
) -> Tuple[Agent, ReasoningHandler]:
    """Create autonomous agent"""

    logger = logging.getLogger("CyberAutoAgent")
    logger.debug(
        "Creating agent for target: %s, objective: %s, server: %s",
        target,
        objective,
        server,
    )

    # Get configuration from ConfigManager
    config_manager = get_config_manager()
    config_manager.validate_requirements(server)
    server_config = config_manager.get_server_config(server)

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
    memory_config = config_manager.get_mem0_service_config(server)

    # Configure vector store with memory path if provided
    if memory_path:
        # Validate existing memory store path
        if not os.path.exists(memory_path):
            raise ValueError(f"Memory path does not exist: {memory_path}")
        if not os.path.isdir(memory_path):
            raise ValueError(f"Memory path is not a directory: {memory_path}")

        # Override vector store path in centralized config
        memory_config["vector_store"] = {"config": {"path": memory_path}}
        print(
            f"{Colors.GREEN}[+] Loading existing memory from: {memory_path}{Colors.RESET}"
        )

    # Initialize the memory system with configuration
    # Extract and sanitize target name for unified output structure
    target_name = sanitize_target_name(target)
    initialize_memory_system(memory_config, operation_id, target_name)
    print(
        f"{Colors.GREEN}[+] Memory system initialized for operation: {operation_id}{Colors.RESET}"
    )

    # Check for existing memories (in addition to explicit memory_path)
    has_existing_memories = check_existing_memories(target, server)

    tools_context = ""
    if available_tools:
        tools_context = f"""
## ENVIRONMENTAL CONTEXT

Professional tools discovered in your environment:
{", ".join(available_tools)}

Leverage these tools directly via shell. 
"""

    system_prompt = get_system_prompt(
        target,
        objective,
        max_steps,
        operation_id,
        tools_context,
        server,
        has_memory_path=bool(memory_path),
        has_existing_memories=has_existing_memories,
    )

    # Create callback handler with operation_id and target information
    callback_handler = ReasoningHandler(
        max_steps=max_steps,
        operation_id=operation_id,
        target=target,
        output_base_dir=server_config.output.base_dir,
    )

    # Create model based on server type
    try:
        if server == "local":
            logger.debug("Configuring OllamaModel")
            model = _create_local_model(model_id, server)
            print(
                f"{Colors.GREEN}[+] Local model initialized: {model_id}{Colors.RESET}"
            )
        else:
            logger.debug("Configuring BedrockModel")
            model = _create_remote_model(model_id, region_name, server)
            print(
                f"{Colors.GREEN}[+] Remote agent model initialized: {model_id}{Colors.RESET}"
            )

    except Exception as e:
        _handle_model_creation_error(server, e)
        raise

    logger.debug("Creating autonomous agent")
    agent = Agent(
        model=model,
        tools=[
            swarm,
            shell,
            editor,
            load_tool,
            mem0_memory,
            stop,
            http_request,
        ],
        system_prompt=system_prompt,
        callback_handler=callback_handler,
        conversation_manager=SlidingWindowConversationManager(window_size=120),
        load_tools_from_directory=True,
        max_parallel_tools=8,
        trace_attributes={
            # Session and user identification
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
            # Target information
            "target.host": target,
            # Objective and scope
            "objective.description": objective,
            # Model configuration
            "model.provider": server,
            "model.id": model_id,
            "model.region": region_name if server == "remote" else "local",
            "gen_ai.request.model": model_id,
            # Tool configuration
            "tools.available": 7,  # Number of core tools
            "tools.names": [
                "swarm",
                "shell",
                "editor",
                "load_tool",
                "mem0_memory",
                "stop",
                "http_request",
            ],
            "tools.parallel_limit": 8,
            # Memory configuration
            "memory.enabled": True,
            "memory.path": memory_path if memory_path else "ephemeral",
            # Tags for filtering
            "langfuse.tags": [
                "Cyber-AutoAgent",
                server.upper(),
                operation_id,
            ],
        },
    )

    logger.debug("Agent initialized successfully")
    return agent, callback_handler
