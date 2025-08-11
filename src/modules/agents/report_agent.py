#!/usr/bin/env python3
"""
Report Generation Utilities for Cyber-AutoAgent

This module provides utility functions for report generation that work
with the report generation tool to maintain clean architecture and
avoid code duplication.
"""

import logging
from typing import Optional

from strands import Agent
from strands.models import BedrockModel
from strands.models.ollama import OllamaModel
from strands.models.litellm import LiteLLMModel

from modules.prompts.factory import get_report_agent_system_prompt

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Utility class for report generation with clean agent creation."""

    @staticmethod
    def create_report_agent(
        provider: str = "bedrock",
        model_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        target: Optional[str] = None,
    ) -> Agent:
        """
        Create a clean agent instance for report generation.

        This method creates a new agent with appropriate configuration
        for report generation, ensuring proper trace hierarchy when
        used within a tool context.

        Args:
            provider: Model provider (bedrock, ollama, litellm)
            model_id: Specific model to use (optional)
            operation_id: Operation ID for trace continuity
            target: Target system for trace metadata

        Returns:
            Configured Agent instance for report generation
        """
        # Get appropriate model based on provider
        if provider == "bedrock":
            model = BedrockModel(model_id=model_id or "us.anthropic.claude-3-5-sonnet-20241022-v2:0")
        elif provider == "ollama":
            # Get Ollama host from environment or use default
            from modules.config.manager import get_config_manager
            config_manager = get_config_manager()
            host = config_manager.get_ollama_host()
            model = OllamaModel(
                host=host,
                model_id=model_id or "llama3.2:3b"
            )
        else:  # litellm
            model = LiteLLMModel(model_id=model_id or "bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0")

        # Create agent with report-specific configuration
        trace_attrs = {
            # Core identification - CRITICAL for trace continuity
            "langfuse.session.id": operation_id,
            "langfuse.user.id": f"cyber-agent-{target}" if target else "cyber-agent",
            # Agent identification
            "langfuse.agent.type": "report_generator",
            "agent.name": "Cyber-ReportGenerator",
            "agent.role": "report_generation",
            # Operation context
            "operation.id": operation_id,
            "operation.phase": "reporting",
            "target.host": target or "unknown",
        }

        # Only add trace attributes if operation_id is provided
        # This ensures proper parent-child relationship
        return Agent(
            model=model,
            name="Cyber-ReportGenerator",
            system_prompt=get_report_agent_system_prompt(),
            tools=[],  # No tools needed for report generation
            trace_attributes=trace_attrs if operation_id else None,
        )

    # Removed extract_report_content() - no longer needed with structured prompts
    # The new system prompt explicitly instructs the LLM to begin directly with
    # "# SECURITY ASSESSMENT REPORT" making content extraction unnecessary

    # Removed clean_duplicate_content() - harmful to structured XML output
    # The function could corrupt XML tags and remove legitimate repeated content
    # like numbered findings. The structured prompt system handles formatting.


# For backward compatibility - in case anything is importing ReportAgent
ReportAgent = ReportGenerator
