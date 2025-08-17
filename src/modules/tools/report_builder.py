#!/usr/bin/env python3
"""
Report Builder Tool for Cyber-AutoAgent

A single, comprehensive tool that the report agent can use to build
security assessment reports from operation evidence.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from strands import tool

from modules.tools.memory import get_memory_client
from modules.prompts.factory import (
    format_evidence_for_report,
    format_tools_summary,
    _extract_domain_lens,
    _transform_evidence_to_content
)

logger = logging.getLogger(__name__)


@tool
def build_report_sections(
    operation_id: str,
    target: str,
    objective: str,
    module: str = "general",
    steps_executed: int = 0,
    tools_used: List[str] = None
) -> Dict[str, Any]:
    """
    Build all sections needed for a security assessment report.
    
    This tool retrieves evidence from memory and transforms it into
    structured report sections that can be used to generate the final report.
    
    Args:
        operation_id: The operation identifier
        target: Assessment target (URL/system)
        objective: Assessment objective
        module: Operation module used (default: general)
        steps_executed: Number of steps executed in operation
        tools_used: List of tools used during assessment
        
    Returns:
        Dictionary containing all report sections:
        - overview: Executive summary overview
        - evidence_text: Formatted evidence collection
        - findings_table: Vulnerability findings matrix
        - severity_counts: Dictionary of severity counts
        - analysis: Detailed vulnerability analysis
        - recommendations: Immediate/short/long-term recommendations
        - tools_summary: Summary of tools used
        - metadata: Operation metadata
    """
    try:
        logger.info("Building report sections for operation: %s", operation_id)
        
        # Retrieve evidence from memory
        evidence = []
        # Initialize memory client for the specific target
        from modules.tools.memory import Mem0ServiceClient
        import os
        
        # Set up memory client with correct target path
        config = Mem0ServiceClient.get_default_config()
        if config and "vector_store" in config and "config" in config["vector_store"]:
            # Update path to use the target-specific memory location
            config["vector_store"]["config"]["path"] = f"outputs/{target.replace('https://', '').replace('http://', '').replace('/', '_')}/memory"
        
        try:
            memory_client = Mem0ServiceClient(config)
            logger.info("Initialized memory client for target: %s", target)
        except Exception as e:
            logger.warning("Could not initialize target-specific memory client: %s. Using default.", e)
            memory_client = get_memory_client()
        
        if memory_client:
            try:
                memories = memory_client.list_memories(user_id="cyber_agent")
                if memories and "results" in memories:
                    for memory_item in memories["results"]:
                        memory_content = memory_item.get("memory", "")
                        metadata = memory_item.get("metadata", {})
                        
                        # Check metadata for finding category first
                        if metadata.get("category") == "finding":
                            evidence.append({
                                "category": "finding",
                                "severity": metadata.get("severity", "MEDIUM"),
                                "content": memory_content,
                                "confidence": metadata.get("confidence", "HIGH"),
                                "id": memory_item.get("id", "")
                            })
                        # Parse JSON memories
                        elif memory_content.startswith("{"):
                            try:
                                parsed = json.loads(memory_content)
                                if parsed.get("category") == "finding":
                                    evidence.append(parsed)
                            except json.JSONDecodeError:
                                pass
                        # Parse text-based findings
                        elif "[FINDING]" in memory_content or "[SIGNAL]" in memory_content:
                            # Extract severity from metadata or content
                            severity = metadata.get("severity", "INFO")
                            if severity == "INFO":  # Only check content if metadata doesn't have severity
                                if "[CRITICAL]" in memory_content:
                                    severity = "CRITICAL"
                                elif "[HIGH]" in memory_content or metadata.get("severity") == "high":
                                    severity = "HIGH"
                                elif "[MEDIUM]" in memory_content or metadata.get("severity") == "medium":
                                    severity = "MEDIUM"
                                elif "[LOW]" in memory_content:
                                    severity = "LOW"
                            
                            evidence.append({
                                "category": "finding",
                                "severity": severity.upper(),
                                "content": memory_content,
                                "confidence": metadata.get("confidence", "HIGH").upper(),
                                "id": memory_item.get("id", "")
                            })
                
                logger.info("Retrieved %d pieces of evidence from memory", len(evidence))
            except Exception as e:
                logger.error("Failed to retrieve evidence: %s", e)
        
        # If no evidence, add a warning
        if not evidence:
            evidence = [{
                "category": "system_warning",
                "severity": "INFO",
                "content": "No evidence collected during assessment - report may be incomplete",
                "confidence": "SYSTEM"
            }]
        
        # Format evidence for report
        evidence_text = format_evidence_for_report(evidence)
        
        # Count severities from actual evidence, not just text
        severity_counts = {
            "critical": sum(1 for e in evidence if e.get("severity", "").upper() == "CRITICAL"),
            "high": sum(1 for e in evidence if e.get("severity", "").upper() == "HIGH"),
            "medium": sum(1 for e in evidence if e.get("severity", "").upper() == "MEDIUM"),
            "low": sum(1 for e in evidence if e.get("severity", "").upper() == "LOW")
        }
        
        # Generate findings table
        findings_table = _generate_findings_table(evidence_text, severity_counts)
        
        # Load module report prompt for domain lens
        domain_lens = {}
        try:
            from modules.prompts.factory import get_module_loader
            module_loader = get_module_loader()
            module_prompt = module_loader.load_module_report_prompt(module)
            if module_prompt:
                domain_lens = _extract_domain_lens(module_prompt)
                logger.info("Loaded domain lens for module '%s'", module)
        except Exception as e:
            logger.warning("Could not load module prompt: %s", e)
        
        # Transform evidence to content using domain lens
        report_content = _transform_evidence_to_content(
            evidence=evidence,
            domain_lens=domain_lens,
            target=target,
            objective=objective
        )
        
        # Format tools summary
        tools_summary = format_tools_summary(tools_used or [])
        
        # Build complete sections dictionary
        sections = {
            "operation_id": operation_id,
            "target": target,
            "objective": objective,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "steps_executed": steps_executed,
            "severity_counts": severity_counts,
            "overview": report_content.get("overview", f"Security assessment of {target}"),
            "evidence_text": evidence_text,
            "findings_table": findings_table,
            "analysis": report_content.get("analysis", ""),
            "immediate_recommendations": report_content.get("immediate", ""),
            "short_term_recommendations": report_content.get("short_term", ""),
            "long_term_recommendations": report_content.get("long_term", ""),
            "tools_summary": tools_summary,
            "analysis_framework": domain_lens.get("framework", "OWASP Top 10 2021"),
            "module": module,
            "evidence_count": len(evidence)
        }
        
        logger.info(
            "Report sections built: %d findings (%d critical, %d high)",
            len(evidence),
            severity_counts["critical"],
            severity_counts["high"]
        )
        
        return sections
        
    except Exception as e:
        logger.error("Error building report sections: %s", e, exc_info=True)
        return {
            "error": str(e),
            "operation_id": operation_id,
            "target": target,
            "objective": objective
        }


def _generate_findings_table(evidence_text: str, severity_counts: Dict[str, int]) -> str:
    """Generate a formatted findings table."""
    table = "| Severity | Count | Key Findings |\n"
    table += "|----------|-------|--------------|\n"
    
    if severity_counts["critical"] > 0:
        table += f"| CRITICAL | {severity_counts['critical']} | Immediate action required - exploitable vulnerabilities |\n"
    if severity_counts["high"] > 0:
        table += f"| HIGH | {severity_counts['high']} | Significant risk requiring urgent attention |\n"
    if severity_counts["medium"] > 0:
        table += f"| MEDIUM | {severity_counts['medium']} | Notable issues to address in remediation |\n"
    if severity_counts["low"] > 0:
        table += f"| LOW | {severity_counts['low']} | Minor issues for security hardening |\n"
    
    if sum(severity_counts.values()) == 0:
        table += "| INFO | 0 | No security findings identified |\n"
    
    return table