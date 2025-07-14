#!/usr/bin/env python3

import os
import logging
import warnings
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

import requests
import ollama
from strands import Agent
from strands.models import BedrockModel
from strands.models.ollama import OllamaModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands_tools import shell, editor, load_tool, stop, http_request
from strands_tools.swarm import swarm

from .system_prompts import get_system_prompt, _get_default_model_configs, _get_ollama_host
from .agent_handlers import ReasoningHandler
from .utils import Colors
from .memory_tools import mem0_memory, initialize_memory_system

warnings.filterwarnings("ignore", category=DeprecationWarning)


def _create_remote_model(
    model_id: str,
    region_name: str,
    temperature: float = 0.95,
    max_tokens: int = 4096,
    top_p: float = 0.95,
) -> BedrockModel:
    """Create AWS Bedrock model instance"""
    
    # Check if this is a thinking-enabled model
    thinking_models = [
        "us.anthropic.claude-opus-4-20250514-v1:0",
        "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        "us.anthropic.claude-sonnet-4-20250514-v1:0"
    ]
    
    if model_id in thinking_models:
        # Use thinking parameters for these models
        return BedrockModel(
            model_id=model_id,
            region_name=region_name,
            temperature=1.0,  
            max_tokens=4026,  
            additional_request_fields={
                "anthropic_beta": ["interleaved-thinking-2025-05-14"],
                "thinking": {"type": "enabled", "budget_tokens": 8000},
            },
        )
    else:
        # Standard model configuration
        return BedrockModel(
            model_id=model_id,
            region_name=region_name,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )


def _create_local_model(
    model_id: str,
    host: Optional[str] = None,
    temperature: float = 0.95,
    max_tokens: int = 4096,
) -> Any:
    """Create Ollama model instance"""

    if host is None:
        host = _get_ollama_host()

    return OllamaModel(
        host=host, model_id=model_id, temperature=temperature, max_tokens=max_tokens
    )



def _validate_server_requirements(server: str) -> None:
    """Validate server requirements before creating agent"""
    if server == "local":
        # Get dynamic host configuration
        ollama_host = _get_ollama_host()
        
        # Check if Ollama is running
        try:
            response = requests.get(f"{ollama_host}/api/version", timeout=5)
            if response.status_code != 200:
                raise ConnectionError("Ollama server not responding")
        except Exception:
            raise ConnectionError(
                f"Ollama server not accessible at {ollama_host}. "
                "Please ensure Ollama is installed and running."
            )

        # Check if required models are available

        try:
            client = ollama.Client(host=ollama_host)
            models_response = client.list()
            available_models = [m.get("model", m.get("name", "")) for m in models_response["models"]]
            required_models = ["llama3.2:3b", "mxbai-embed-large"]
            missing = [
                m
                for m in required_models
                if not any(m in model for model in available_models)
            ]
            if missing:
                raise ValueError(
                    f"Required models not found: {missing}. "
                    f"Pull them with: ollama pull {' && ollama pull '.join(missing)}"
                )
        except Exception as e:
            if "Required models not found" in str(e):
                raise e
            raise ConnectionError(f"Could not verify Ollama models: {e}")

    elif server == "remote":
        if not (os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE")):
            raise EnvironmentError(
                "AWS credentials not configured for remote mode. "
                "Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or configure AWS_PROFILE"
            )


def _handle_model_creation_error(server: str, error: Exception) -> None:
    """Provide helpful error messages based on server type"""
    if server == "local":
        print(f"{Colors.RED}[!] Local model creation failed: {error}{Colors.RESET}")
        print(f"{Colors.YELLOW}[?] Troubleshooting steps:{Colors.RESET}")
        print("    1. Ensure Ollama is installed: https://ollama.ai")
        print("    2. Start Ollama: ollama serve")
        print("    3. Pull required models:")
        print("       ollama pull llama3.2:3b")
        print("       ollama pull mxbai-embed-large")
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
    region_name: str = "us-east-1",
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

    _validate_server_requirements(server)

    defaults = _get_default_model_configs(server)

    # Use provided model_id or default
    if model_id is None:
        model_id = str(defaults["llm_model"])

    # Use provided operation_id or generate new one
    if not op_id:
        operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    else:
        operation_id = op_id

    # Configure memory system based on server type
    memory_config = {}
    
    if server == "local":
        # Local mode with Ollama
        ollama_host = _get_ollama_host()
        memory_config = {
            "embedder": {
                "provider": "ollama",
                "config": {
                    "model": defaults["embedding_model"],
                    "base_url": ollama_host
                }
            },
            "llm": {
                "provider": "ollama",
                "config": {
                    "model": model_id,
                    "base_url": ollama_host,
                    "temperature": 0.1,
                    "max_tokens": 2000
                }
            }
        }
    else:
        memory_config = {
            "embedder": {
                "provider": "aws_bedrock",
                "config": {
                    "model": defaults["embedding_model"],
                    "aws_region": region_name
                }
            },
            "llm": {
                "provider": "aws_bedrock",
                "config": {
                    "model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "aws_region": region_name
                }
            }
        }
    
    # Configure vector store with memory path if provided
    if memory_path:
        # Validate existing memory store path
        if not os.path.exists(memory_path):
            raise ValueError(f"Memory path does not exist: {memory_path}")
        if not os.path.isdir(memory_path):
            raise ValueError(f"Memory path is not a directory: {memory_path}")
        
        memory_config["vector_store"] = {
            "config": {
                "path": memory_path
            }
        }
        print(f"{Colors.GREEN}[+] Loading existing memory from: {memory_path}{Colors.RESET}")
    
    # Initialize the memory system with configuration
    initialize_memory_system(memory_config, operation_id)
    print(f"{Colors.GREEN}[+] Memory system initialized for operation: {operation_id}{Colors.RESET}")

    tools_context = ""
    if available_tools:
        tools_context = f"""
## ENVIRONMENTAL CONTEXT

Professional tools discovered in your environment:
{", ".join(available_tools)}

Leverage these tools directly via shell. 
"""

    system_prompt = get_system_prompt(
        target, objective, max_steps, operation_id, tools_context, server, has_memory_path=bool(memory_path)
    )

    # Create callback handler with operation_id
    callback_handler = ReasoningHandler(max_steps=max_steps, operation_id=operation_id)

    # Create model based on server type
    try:
        if server == "local":
            logger.debug("Configuring OllamaModel")
            model = _create_local_model(model_id)
            print(
                f"{Colors.GREEN}[+] Local model initialized: {model_id}{Colors.RESET}"
            )
        else:
            logger.debug("Configuring BedrockModel")
            model = _create_remote_model(model_id, region_name)
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
            "tools.names": ["swarm", "shell", "editor", "load_tool", "mem0_memory", "stop", "http_request"],
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
        }
    )

    logger.debug("Agent initialized successfully")
    return agent, callback_handler
