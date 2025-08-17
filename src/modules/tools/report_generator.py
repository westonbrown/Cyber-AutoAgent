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

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from strands import tool

from modules.agents.report_agent import ReportGenerator
from modules.prompts.factory import get_report_generation_prompt
from modules.tools.memory import get_memory_client


@dataclass
class ReportConfig:
    """Configuration object for security report generation to reduce parameter count."""
    target: str
    objective: str
    operation_id: str
    steps_executed: int
    tools_used: List[str]
    evidence: Optional[List[Dict[str, Any]]] = None
    provider: str = "bedrock"
    model_id: Optional[str] = None
    module: Optional[str] = None


logger = logging.getLogger(__name__)


@tool
def generate_security_report(
    target: str,
    objective: str,
    operation_id: str,
    config_data: Optional[str] = None,
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
        config_data: JSON string containing additional config (steps_executed, tools_used, 
                    evidence, provider, model_id, module)

    Returns:
        The generated security assessment report as a string

    Example:
        generate_security_report(
            target="example.com",
            objective="Identify web application vulnerabilities",
            operation_id="OP_20240115_143022",
            config_data='{"steps_executed": 15, "tools_used": ["nmap", "nikto"], "provider": "bedrock"}'
        )
    """
    try:
        # Log the report generation request
        logger.info("Generating security report for operation: %s", operation_id)

        # Parse config data
        config_params = {}
        if config_data:
            try:
                config_params = json.loads(config_data)
            except json.JSONDecodeError:
                return "Error: Invalid JSON in config_data parameter"
        
        # Extract parameters with defaults
        steps_executed = config_params.get('steps_executed', 0)
        tools_used = config_params.get('tools_used', [])
        evidence = config_params.get('evidence')
        provider = config_params.get('provider', 'bedrock')
        model_id = config_params.get('model_id')
        module = config_params.get('module')

        # If evidence not provided, retrieve from memory
        if evidence is None:
            evidence = _retrieve_evidence_from_memory(operation_id)

        # Validate evidence collection
        if not evidence or len(evidence) == 0:
            logger.warning("No evidence retrieved for operation %s - report may be incomplete", operation_id)
            # Add system warning to indicate missing evidence
            evidence = [
                {
                    "category": "system_warning",
                    "content": "⚠️ WARNING: No evidence collected during assessment - this may indicate incomplete operation or configuration issues",
                    "severity": "MEDIUM",
                    "confidence": "SYSTEM",
                }
            ]
        else:
            finding_count = len([e for e in evidence if e.get("category") == "finding"])
            logger.info(
                "Retrieved %d pieces of evidence (%d findings) for report generation", len(evidence), finding_count
            )

        # Get module report prompt if available
        module_report_prompt = _get_module_report_prompt(module)

        # Get the report prompt from centralized prompts
        report_prompt = get_report_generation_prompt(
            target=target,
            objective=objective,
            operation_id=operation_id,
            steps_executed=steps_executed,
            evidence=evidence,
            tools_used=tools_used,
            module_prompt=module_report_prompt,
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

                # Simple validation - trust the structured prompt system
                if not report_text.strip().startswith("# SECURITY ASSESSMENT REPORT"):
                    logger.warning("Report doesn't start with expected header, but proceeding with output")

                logger.info("Report generated successfully (%d characters)", len(report_text))

                # Validate report length and content
                report_length = len(report_text.strip())
                if report_length < 50:
                    logger.warning(
                        "Generated report is unusually short (%d chars) - may indicate generation issues", report_length
                    )
                    # Don't fail completely, but add warning to report
                    report_text = f"⚠️ **REPORT GENERATION WARNING**: Unusually short report ({report_length} characters) - please verify completeness.\n\n{report_text}"
                elif report_length < 200:
                    logger.info("Generated report is shorter than typical (%d chars) but proceeding", report_length)

                return report_text

        logger.error("Failed to generate report - no content in response")
        return "Error: Failed to generate security assessment report"

    except Exception as e:
        logger.error("Error generating security report: %s", e, exc_info=True)
        return f"Error: {str(e)}"


def _retrieve_evidence_from_memory(_operation_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve evidence from memory system for the operation.

    Args:
        operation_id: The operation ID to retrieve evidence for

    Returns:
        List of evidence dictionaries
    """
    evidence = []

    try:
        # Use pre-imported memory client

        memory_client = get_memory_client()
        if not memory_client:
            error_msg = (
                "Critical: Memory service unavailable - cannot generate comprehensive report with stored evidence"
            )
            logger.error(error_msg)
            # Still proceed but with clear indication of missing data
            evidence.append(
                {
                    "category": "system_warning",
                    "content": "⚠️ WARNING: Memory service unavailable - report generated without stored evidence from previous assessment steps",
                    "severity": "HIGH",
                    "confidence": "SYSTEM",
                }
            )
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
        from modules.prompts import get_module_loader  # Dynamic import required

        module_loader = get_module_loader()
        module_report_prompt = module_loader.load_module_report_prompt(module_name)

        if module_report_prompt:
            logger.info("Loaded report prompt for module '%s' (%d chars)", module_name, len(module_report_prompt))
        else:
            logger.debug("No report prompt found for module '%s'", module_name)

        return module_report_prompt

    except Exception as e:
        logger.warning("Error loading report prompt for module '%s': %s. Using default guidance.", module_name, e)
        # Return default security assessment guidance as fallback
        return (
            "DOMAIN_LENS:\n"
            "overview: Security assessment focused on identifying vulnerabilities and risks\n"
            "analysis: Analyze findings for exploitability and business impact\n"
            "immediate: Address critical security vulnerabilities immediately\n"
            "short_term: Implement security controls and monitoring\n"
            "long_term: Establish comprehensive security program\n"
        )
