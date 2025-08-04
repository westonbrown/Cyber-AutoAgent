#!/usr/bin/env python3
"""
Report Generation Utilities for Cyber-AutoAgent

This module provides utility functions for report generation that work
with the report generation tool to maintain clean architecture and
avoid code duplication.
"""

import logging
import re
from typing import Dict, Any, List, Optional

from strands import Agent
from strands.models import BedrockModel
from strands.models.ollama import OllamaModel
from strands.models.litellm import LiteLLMModel

from modules.prompts.report import get_report_agent_system_prompt

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
            model = OllamaModel(model_id=model_id or "llama3.2:3b")
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

    @staticmethod
    def extract_report_content(raw_content: str) -> str:
        """
        Extract the actual report content from LLM response.

        The LLM sometimes includes thinking/preamble before the actual report.
        This method extracts only the report starting from the first report header.

        Args:
            raw_content: Raw content from LLM including possible preamble

        Returns:
            Extracted report content
        """
        # Look for common report headers
        report_markers = [
            "# PENETRATION TESTING REPORT",
            "# PENETRATION TESTING SECURITY ASSESSMENT REPORT",
            "# Security Assessment Report",
            "# SECURITY ASSESSMENT REPORT",
            "## EXECUTIVE SUMMARY",
            "## 1. EXECUTIVE SUMMARY",
            "PENETRATION TESTING SECURITY ASSESSMENT REPORT",
            "1. EXECUTIVE SUMMARY",
            "EXECUTIVE SUMMARY",
        ]

        lines = raw_content.split("\n")
        report_start_idx = None

        # Find the first occurrence of a report marker
        for i, line in enumerate(lines):
            for marker in report_markers:
                if marker in line:
                    report_start_idx = i
                    break
            if report_start_idx is not None:
                break

        if report_start_idx is not None:
            # Return content from the report start
            return "\n".join(lines[report_start_idx:])

        # If no marker found, log and return original content
        logger.warning("No report markers found in content. Returning original content.")
        return raw_content

    @staticmethod
    def clean_duplicate_content(report_content: str) -> str:
        """
        Remove duplicate sections from report content.

        Args:
            report_content: The raw report content

        Returns:
            Cleaned report content
        """
        lines = report_content.split("\n")
        seen_lines = set()
        cleaned_lines = []

        # Track section headers to avoid duplicate sections
        section_pattern = re.compile(r"^#+\s+(.+)$|^[A-Z][A-Z\s]+:?\s*$")
        seen_sections = set()

        skip_until_next_section = False

        for line in lines:
            # Check if this is a section header
            section_match = section_pattern.match(line.strip())
            if section_match:
                section_name = section_match.group(1) if section_match.group(1) else line.strip()
                section_name = section_name.upper().strip(":")

                if section_name in seen_sections:
                    skip_until_next_section = True
                    continue

                seen_sections.add(section_name)
                skip_until_next_section = False

            # Skip content if we're in a duplicate section
            if skip_until_next_section:
                continue

            # Add non-duplicate lines
            if line.strip() and line not in seen_lines:
                cleaned_lines.append(line)
                seen_lines.add(line)
            elif not line.strip():  # Preserve blank lines
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)


# For backward compatibility - in case anything is importing ReportAgent
ReportAgent = ReportGenerator
