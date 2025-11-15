#!/usr/bin/env python3
"""
Report Generation Utilities for Cyber-AutoAgent

This module provides utility functions for report generation that work
with the report generation tool to maintain clean architecture and
avoid code duplication.
"""

from typing import Optional

from strands import Agent
from strands.handlers import PrintingCallbackHandler
from strands.models import BedrockModel
from strands.models.litellm import LiteLLMModel
from strands.models.ollama import OllamaModel

from modules.config.manager import get_config_manager
from modules.config.system.logger import get_logger
from modules.prompts.factory import get_report_agent_system_prompt

logger = get_logger("Agents.ReportAgent")


class NoOpCallbackHandler(PrintingCallbackHandler):
    """Minimal callback handler that suppresses SDK output during report generation."""

    def __call__(self, **kwargs):  # type: ignore[override]
        return


class ReportGenerator:
    """Factory for a report-generation Agent with a single builder tool.

    The agent is configured with a concise system prompt and the
    build_report_sections tool. Output is returned to the caller.
    """

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
        # Select model via central configuration, with sensible defaults
        cfg = get_config_manager()
        prov = (provider or "bedrock").lower()
        if prov == "bedrock":
            # Always use the primary bedrock model from config
            llm_cfg = cfg.get_llm_config("bedrock")
            # Only override if explicitly provided, otherwise use config
            mid = model_id if model_id else llm_cfg.model_id

            # Harden Bedrock client similar to main agent to avoid timeouts
            from botocore.config import Config as BotocoreConfig

            boto_config = BotocoreConfig(
                region_name=cfg.get_server_config("bedrock").region,
                retries={"max_attempts": 10, "mode": "adaptive"},
                read_timeout=1200,
                connect_timeout=1200,
                max_pool_connections=100,
            )

            # Use the same max_tokens budget as the primary Bedrock model
            try:
                max_tokens = int(getattr(llm_cfg, "max_tokens", 0) or 0)
                if max_tokens <= 0:
                    raise ValueError
            except Exception:
                max_tokens = 32000

            # Ensure explicit region to avoid environment inconsistencies
            region = cfg.get_server_config("bedrock").region
            model = BedrockModel(
                model_id=mid,
                region_name=region,
                max_tokens=max_tokens,
                temperature=0.3,
                boto_client_config=boto_config,
            )
        elif prov == "ollama":
            host = cfg.get_ollama_host()
            llm_cfg = cfg.get_llm_config("ollama")
            # Only override if explicitly provided, otherwise use config
            mid = model_id if model_id else llm_cfg.model_id
            model = OllamaModel(host=host, model_id=mid)
        else:  # litellm
            llm_cfg = cfg.get_llm_config("litellm")
            # Only override if explicitly provided, otherwise use config
            mid = model_id if model_id else llm_cfg.model_id
            # Pass both token params - LiteLLM drop_params removes unsupported one
            try:
                llm_max = int(getattr(llm_cfg, "max_tokens", 0) or 0)
                if llm_max <= 0:
                    raise ValueError
            except Exception:
                llm_max = 4000
            params = {
                "temperature": 0.3,
                "max_tokens": llm_max,
                "max_completion_tokens": llm_max,
            }
            client_args = {
                "num_retries": 5,
                "timeout": 600,
            }
            model = LiteLLMModel(model_id=mid, params=params, client_args=client_args)

        # Import the report builder tool
        from modules.tools.report_builder import build_report_sections

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

        # Configure trace attributes for observability
        # Only add if operation_id is provided to ensure proper parent-child relationship

        # Create a silent callback handler to prevent duplicate output
        # The report will be returned and handled by the caller
        return Agent(
            model=model,
            name="Cyber-ReportGenerator",
            system_prompt=get_report_agent_system_prompt(),
            tools=[build_report_sections],
            trace_attributes=trace_attrs if operation_id else None,
            callback_handler=NoOpCallbackHandler(),
        )


# For backward compatibility - in case anything is importing ReportAgent
ReportAgent = ReportGenerator
