#!/usr/bin/env python3

import os
import logging
import warnings
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands_tools import shell, file_write, editor, load_tool
from mem0 import Memory

# Conditional imports with graceful fallback
try:
    from strands.models.ollama import OllamaModel
    import ollama
    import requests

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    # Define placeholder types for when imports are not available
    OllamaModel = None  # type: ignore
    ollama = None  # type: ignore
    requests = None  # type: ignore

from . import memory_tools
from .memory_tools import memory_store, memory_retrieve, memory_list
from .system_prompts import get_system_prompt
from .agent_handlers import ReasoningHandler
from .utils import Colors, get_data_path

warnings.filterwarnings("ignore", category=DeprecationWarning)


def _test_ollama_connection(host: str, timeout: int = 2) -> bool:
    """Test if Ollama server is accessible at the given host"""
    if requests is None:
        return False
    
    try:
        response = requests.get(f"{host}/api/version", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False



def _get_ollama_host() -> str:
    """
    Determine appropriate Ollama host based on environment.
    Tests actual connectivity to find working host in Docker environments.
    """
    # Environment variable override from e.g. .env for full control
    env_host = os.getenv("OLLAMA_HOST")
    if env_host:
        return env_host
    
    # Check if running in Docker
    if os.path.exists('/.dockerenv'):
        # In Docker - test both options to find what works
        candidates = ["http://localhost:11434", "http://host.docker.internal:11434"]
        for host in candidates:
            if _test_ollama_connection(host):
                return host
        # Fallback to host.docker.internal if no connection works (Docker on Windows/ Macos)
        return "http://host.docker.internal:11434"
    else:
        # Native execution - use localhost (Docker on Linux & non-docker)
        return "http://localhost:11434"


def _get_default_model_configs(server: str) -> Dict[str, Any]:
    """Get default model configurations based on server type"""
    if server == "local":
        return {
            "llm_model": "MFDoom/qwen3:4b",
            "embedding_model": "mxbai-embed-large",
            "embedding_dims": 1024,
        }
    else:  # remote
        return {
            "llm_model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "embedding_model": "amazon.titan-embed-text-v2:0",
            "embedding_dims": 1024,
        }


def _create_remote_model(
    model_id: str,
    region_name: str,
    temperature: float = 0.95,
    max_tokens: int = 4096,
    top_p: float = 0.95,
) -> BedrockModel:
    """Create AWS Bedrock model instance"""
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
    if not OLLAMA_AVAILABLE or OllamaModel is None:
        raise ImportError(
            "Ollama not available. Install with: uv add ollama && uv add 'strands-agents[ollama]'"
        )

    if host is None:
        host = _get_ollama_host()

    return OllamaModel(
        host=host, model_id=model_id, temperature=temperature, max_tokens=max_tokens
    )


def _create_memory_config(
    server: str, operation_id: str, defaults: Dict[str, Any]
) -> Dict[str, Any]:
    """Create mem0 configuration based on server type"""
    base_path = os.path.join(get_data_path("evidence"), f"evidence_{operation_id}")

    if server == "local":
        ollama_host = _get_ollama_host()
        return {
            "llm": {
                "provider": "ollama",
                "config": {
                    "model": defaults["llm_model"],
                    "temperature": 0.1,
                    "max_tokens": 1024,
                    "ollama_base_url": ollama_host,
                },
            },
            "embedder": {
                "provider": "ollama",
                "config": {
                    "model": defaults["embedding_model"],
                    "ollama_base_url": ollama_host,
                },
            },
            "vector_store": {
                "provider": "faiss",
                "config": {
                    "embedding_model_dims": defaults["embedding_dims"],
                    "path": base_path,
                },
            },
            "history_db_path": os.path.join(base_path, "history.db"),
            "version": "v1.1",
        }
    else:  # remote
        return {
            "llm": {
                "provider": "aws_bedrock",
                "config": {
                    "model": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
                    "temperature": 0.1,
                    "max_tokens": 1024,
                    "top_p": 0.9,
                },
            },
            "embedder": {
                "provider": "aws_bedrock",
                "config": {"model": defaults["embedding_model"]},
            },
            "vector_store": {
                "provider": "faiss",
                "config": {
                    "embedding_model_dims": defaults["embedding_dims"],
                    "path": base_path,
                },
            },
            "history_db_path": os.path.join(base_path, "history.db"),
            "version": "v1.1",
        }


def _validate_server_requirements(server: str) -> None:
    """Validate server requirements before creating agent"""
    if server == "local":
        # Get dynamic host configuration
        ollama_host = _get_ollama_host()
        
        # Check if Ollama is running
        if requests is None:
            raise ImportError("Requests module not available")
        
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
        if not OLLAMA_AVAILABLE or ollama is None:
            raise ImportError(
                "Ollama client not available. Install with: uv add ollama"
            )

        try:
            client = ollama.Client(host=ollama_host)
            models_response = client.list()
            available_models = [m.get("model", m.get("name", "")) for m in models_response["models"]]
            required_models = ["MFDoom/qwen3:4b", "mxbai-embed-large"]
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
        # Validate AWS credentials exist
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
        print("       ollama pull MFDoom/qwen3:4b")
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
) -> Tuple[Agent, ReasoningHandler]:
    """Create autonomous agent"""

    logger = logging.getLogger("CyberAutoAgent")
    logger.debug(
        "Creating agent for target: %s, objective: %s, server: %s",
        target,
        objective,
        server,
    )

    # Pre-flight validation
    _validate_server_requirements(server)

    # Get default configurations
    defaults = _get_default_model_configs(server)

    # Use provided model_id or default
    if model_id is None:
        model_id = str(defaults["llm_model"])

    # Use provided operation_id or generate new one
    if not op_id:
        operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    else:
        operation_id = op_id

    # Create memory configuration
    memory_config = _create_memory_config(server, operation_id, defaults)

    # Initialize memory system
    memory_tools.mem0_instance = Memory.from_config(memory_config)
    memory_tools.operation_id = operation_id

    print(f"{Colors.GREEN}[+] Memory system initialized ({server} mode){Colors.RESET}")

    tools_context = ""
    if available_tools:
        tools_context = f"""
## ENVIRONMENTAL CONTEXT

Professional tools discovered in your environment:
{", ".join(available_tools)}

Leverage these tools directly via shell. 
"""

    # Get system prompt
    system_prompt = get_system_prompt(
        target, objective, max_steps, operation_id, tools_context
    )

    # Create callback handler
    callback_handler = ReasoningHandler(max_steps=max_steps)

    # Create model based on server type
    try:
        if server == "local":
            logger.debug("Configuring OllamaModel")
            model = _create_local_model(model_id)
            print(
                f"{Colors.GREEN}[+] Local model initialized: {model_id}{Colors.RESET}"
            )
        else:
            # Set AWS region for remote mode
            os.environ["AWS_REGION"] = region_name
            logger.debug("Configuring BedrockModel")
            model = _create_remote_model(model_id, region_name)
            print(
                f"{Colors.GREEN}[+] Remote model initialized: {model_id}{Colors.RESET}"
            )

    except Exception as e:
        _handle_model_creation_error(server, e)
        raise

    logger.debug("Creating autonomous agent")
    agent = Agent(
        model=model,
        tools=[
            shell,
            file_write,
            editor,
            load_tool,
            memory_store,
            memory_retrieve,
            memory_list,
        ],
        system_prompt=system_prompt,
        callback_handler=callback_handler,
        conversation_manager=SlidingWindowConversationManager(window_size=120),
        load_tools_from_directory=True,
        max_parallel_tools=8,
    )

    logger.debug("Agent initialized successfully")
    return agent, callback_handler
