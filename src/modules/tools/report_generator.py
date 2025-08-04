#!/usr/bin/env python3
"""
Report Generation Tool for Cyber-AutoAgent

This tool provides report generation capabilities that can be called by the main agent,
ensuring proper trace hierarchy and span management through the Strands SDK.

Key Features:
- Generates comprehensive security assessment reports
- Automatically creates proper child spans when called by agent
- Maintains trace continuity without manual span management
- Integrates with memory system to retrieve evidence
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from strands import tool

from modules.handlers.utils import Colors
from modules.agents.report_agent import ReportGenerator
from modules.prompts.report import get_report_generation_prompt

logger = logging.getLogger(__name__)


@tool
def generate_security_report(
    target: str,
    objective: str,
    operation_id: str,
    steps_executed: int,
    tools_used: List[str],
    evidence: Optional[List[Dict[str, Any]]] = None,
    provider: str = "bedrock",
    model_id: Optional[str] = None,
    module: Optional[str] = None,
) -> str:
    """
    Generate a comprehensive security assessment report based on the operation results.

    This tool creates a professional penetration testing report by analyzing the
    evidence collected during the security assessment. It uses an LLM to generate
    a well-structured report with findings, recommendations, and risk assessments.

    Args:
        target: The target system that was assessed
        objective: The security assessment objective
        operation_id: The operation identifier
        steps_executed: Number of steps executed during assessment
        tools_used: List of tools used during the assessment
        evidence: List of evidence/findings collected (optional - will retrieve from memory if not provided)
        provider: Model provider (bedrock, ollama, litellm)
        model_id: Specific model to use for generation (optional)
        module: Security module used for assessment (optional - enables module-specific report prompts)

    Returns:
        The generated security assessment report as a string

    Example:
        generate_security_report(
            target="example.com",
            objective="Identify web application vulnerabilities",
            operation_id="OP_20240115_143022",
            steps_executed=15,
            tools_used=["nmap", "nikto", "sqlmap", "curl"],
            evidence=[{"category": "finding", "content": "SQL injection in login form", "severity": "high"}]
        )
    """
    try:
        # Log the report generation request
        logger.info("Generating security report for operation: %s", operation_id)

        # If evidence not provided, retrieve from memory
        if evidence is None:
            evidence = _retrieve_evidence_from_memory(operation_id)

        # Use centralized formatting functions from prompts module
        from modules.prompts.report import format_evidence_for_report, format_tools_summary

        evidence_text = format_evidence_for_report(evidence)
        tools_text = format_tools_summary(tools_used)

        # Get module report prompt if available
        module_report_prompt = _get_module_report_prompt(module)

        # Get the report prompt from centralized prompts
        report_prompt = get_report_generation_prompt(
            target=target,
            objective=objective,
            operation_id=operation_id,
            steps_executed=steps_executed,
            tools_text=tools_text,
            evidence_text=evidence_text,
            module_report_prompt=module_report_prompt,
        )

        # Create report agent using utility class with trace attributes
        report_agent = ReportGenerator.create_report_agent(
            provider=provider, model_id=model_id, operation_id=operation_id, target=target
        )

        # Generate the report
        logger.info("Invoking report generation agent...")
        result = report_agent(report_prompt)

        # Extract the report content
        if result and hasattr(result, "message"):
            content = result.message.get("content", [])
            if content and isinstance(content, list):
                report_text = ""
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        report_text += block["text"]

                # Use utility methods for cleaning
                report_text = ReportGenerator.extract_report_content(report_text)
                report_text = ReportGenerator.clean_duplicate_content(report_text)

                logger.info("Report generated successfully (%d characters)", len(report_text))
                return report_text

        logger.error("Failed to generate report - no content in response")
        return "Error: Failed to generate security assessment report"

    except Exception as e:
        logger.error("Error generating security report: %s", e, exc_info=True)
        return f"Error: {str(e)}"


def _retrieve_evidence_from_memory(operation_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve evidence from memory system for the operation.

    Args:
        operation_id: The operation ID to retrieve evidence for

    Returns:
        List of evidence dictionaries
    """
    evidence = []

    try:
        # Import memory client
        from .memory import get_memory_client

        memory_client = get_memory_client()
        if not memory_client:
            logger.warning("Memory client not available - proceeding without stored evidence")
            return evidence

        # Retrieve memories for this operation
        memories_response = memory_client.list_memories(user_id="cyber_agent")

        # Parse memory response
        if isinstance(memories_response, dict):
            raw_memories = memories_response.get("memories", memories_response.get("results", []))
        elif isinstance(memories_response, list):
            raw_memories = memories_response
        else:
            raw_memories = []

        # Filter and format memories
        for mem in raw_memories:
            metadata = mem.get("metadata", {})
            memory_content = mem.get("memory", "")
            memory_id = mem.get("id", "")

            # Only include findings and relevant memories
            if metadata.get("category") == "finding":
                evidence.append(
                    {
                        "category": "finding",
                        "content": memory_content,
                        "id": memory_id,
                        "severity": metadata.get("severity", "unknown"),
                        "confidence": metadata.get("confidence", "unknown"),
                    }
                )
            elif "category" not in metadata and memory_content and len(memory_content.split()) < 100:
                evidence.append(
                    {
                        "category": "general",
                        "content": memory_content,
                        "id": memory_id,
                        "severity": "unknown",
                        "confidence": "unknown",
                    }
                )

        logger.info("Retrieved %d pieces of evidence from memory", len(evidence))

    except Exception as e:
        logger.warning("Error retrieving evidence from memory: %s", e)

    return evidence


# Note: formatting and cleaning functions are now imported from
# modules.prompts.report and modules.agents.report_agent to maintain modularity


def _get_module_report_prompt(module_name: Optional[str]) -> Optional[str]:
    """Get the module-specific report prompt if available.

    Args:
        module_name: Name of the module to load report prompt for

    Returns:
        Module report prompt string or None if not available
    """
    if not module_name:
        return None

    try:
        from modules.prompts.module_loader import get_module_loader

        module_loader = get_module_loader()
        module_report_prompt = module_loader.load_module_report_prompt(module_name)

        if module_report_prompt:
            logger.info("Loaded report prompt for module '%s' (%d chars)", module_name, len(module_report_prompt))
        else:
            logger.debug("No report prompt found for module '%s'", module_name)

        return module_report_prompt

    except Exception as e:
        logger.error("Error loading report prompt for module '%s': %s", module_name, e)
        return None
