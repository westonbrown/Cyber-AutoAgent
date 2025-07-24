"""Cyber-AutoAgent modules package."""

__version__ = "1.0.0"
__author__ = "Cyber-AutoAgent Team"

# Import main components for easier access
from .agents.cyber_autoagent import Agent
from .agents.report_agent import ReportAgent
from .config.manager import get_config_manager, ConfigManager
from .config.environment import auto_setup, setup_logging, clean_operation_memory
from .evaluation.evaluation import CyberAgentEvaluator
from .prompts.system import get_system_prompt, get_initial_prompt, get_continuation_prompt
from .prompts.manager import PromptManager, get_prompt_manager
from .tools.memory import get_memory_client, Mem0ServiceClient
from .handlers import ReasoningHandler

__all__ = [
    # Agents
    "Agent",
    "ReportAgent",
    # Config
    "get_config_manager",
    "ConfigManager",
    "auto_setup",
    "setup_logging",
    "clean_operation_memory",
    # Evaluation
    "CyberAgentEvaluator",
    # Prompts
    "get_system_prompt",
    "get_initial_prompt",
    "get_continuation_prompt",
    "PromptManager",
    "get_prompt_manager",
    # Tools
    "get_memory_client",
    "Mem0ServiceClient",
    # Handlers
    "ReasoningHandler",
]
