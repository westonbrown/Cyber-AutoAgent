#!/usr/bin/env python3
"""
Report Builder Tool for Cyber-AutoAgent

A single, comprehensive tool that the report agent can use to build
security assessment reports from operation evidence.
"""

import json
import logging
import re
from typing import Dict, Any, List
from datetime import datetime

from strands import tool

from modules.tools.memory import get_memory_client
from modules.prompts.factory import (
    format_evidence_for_report,
    format_tools_summary,
    _extract_domain_lens,
    _transform_evidence_to_content,
)

logger = logging.getLogger(__name__)


def sanitize_target_for_path(target: str) -> str:
    """Sanitize a target URL/string for safe use in filesystem paths.

    Prevents directory traversal attacks and ensures the resulting path
    is safe for use in file operations.

    Args:
        target: The target URL or string to sanitize (e.g., "https://example.com/path")

    Returns:
        A sanitized string safe for use in filesystem paths

    Examples:
        >>> sanitize_target_for_path("https://example.com/test")
        'example.com_test'
        >>> sanitize_target_for_path("../../etc/passwd")
        'etc_passwd'
    """
    # Remove protocol prefixes
    clean = re.sub(r"^https?://", "", target)

    # Remove directory traversal attempts
    clean = clean.replace("..", "").replace("./", "")

    # Keep only safe characters: alphanumeric, dots, hyphens, underscores
    clean = re.sub(r"[^a-zA-Z0-9._-]", "_", clean)

    # Normalize multiple underscores to single
    clean = re.sub(r"_+", "_", clean)

    # Enforce maximum length and trim special chars
    clean = clean[:100].strip("_.")

    # Provide fallback for empty results
    return clean or "unknown_target"


@tool
def build_report_sections(
    operation_id: str,
    target: str,
    objective: str,
    module: str = "general",
    steps_executed: int = 0,
    tools_used: List[str] = None,
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

        # Initialize memory client and retrieve evidence
        evidence = []
        from modules.tools.memory import Mem0ServiceClient

        # Configure memory client with target-specific path
        config = Mem0ServiceClient.get_default_config()
        if config and "vector_store" in config and "config" in config["vector_store"]:
            safe_target_name = sanitize_target_for_path(target)
            config["vector_store"]["config"]["path"] = f"outputs/{safe_target_name}/memory"

        try:
            # Use silent mode to suppress initialization output during report generation
            memory_client = Mem0ServiceClient(config, silent=True)
            logger.info("Initialized memory client for target: %s", target)
        except Exception as e:
            logger.warning("Could not initialize target-specific memory client: %s. Using default.", e)
            # Fallback to global client with silent mode
            memory_client = get_memory_client(silent=True)

        if memory_client:
            try:
                memories = memory_client.list_memories(user_id="cyber_agent")
                if memories and "results" in memories:
                    for memory_item in memories["results"]:
                        memory_content = memory_item.get("memory", "")
                        metadata = memory_item.get("metadata", {})

                        # Check metadata for finding category first
                        if metadata.get("category") == "finding":
                            evidence.append(
                                {
                                    "category": "finding",
                                    "severity": metadata.get("severity", "MEDIUM"),
                                    "content": memory_content,
                                    "confidence": metadata.get("confidence", "HIGH"),
                                    "id": memory_item.get("id", ""),
                                }
                            )
                        # Parse JSON memories
                        elif memory_content.startswith("{"):
                            try:
                                parsed = json.loads(memory_content)
                                if parsed.get("category") == "finding":
                                    evidence.append(parsed)
                            except json.JSONDecodeError:
                                pass
                        # Parse text-based findings with structured evidence
                        elif any(
                            marker in memory_content
                            for marker in ["[FINDING]", "[SIGNAL]", "[VULNERABILITY]", "[DISCOVERY]"]
                        ):
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

                            # Parse structured evidence from content
                            parsed_evidence = _parse_structured_evidence(memory_content)

                            evidence.append(
                                {
                                    "category": "finding",
                                    "severity": severity.upper(),
                                    "content": memory_content,  # Full content, not truncated
                                    "parsed": parsed_evidence,  # Structured evidence components
                                    "confidence": metadata.get("confidence", "HIGH").upper(),
                                    "id": memory_item.get("id", ""),
                                }
                            )

                logger.info("Retrieved %d pieces of evidence from memory", len(evidence))
            except Exception as e:
                logger.error("Failed to retrieve evidence: %s", e)

        # If no evidence, add a warning
        if not evidence:
            evidence = [
                {
                    "category": "system_warning",
                    "severity": "INFO",
                    "content": "No evidence collected during assessment - report may be incomplete",
                    "confidence": "SYSTEM",
                }
            ]

        # Format evidence for report
        evidence_text = format_evidence_for_report(evidence)

        # Count severities from actual evidence, not just text
        severity_counts = {
            "critical": sum(1 for e in evidence if e.get("severity", "").upper() == "CRITICAL"),
            "high": sum(1 for e in evidence if e.get("severity", "").upper() == "HIGH"),
            "medium": sum(1 for e in evidence if e.get("severity", "").upper() == "MEDIUM"),
            "low": sum(1 for e in evidence if e.get("severity", "").upper() == "LOW"),
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
            evidence=evidence, domain_lens=domain_lens, target=target, objective=objective
        )

        # Format tools summary
        tools_summary = format_tools_summary(tools_used or [])

        # Separate findings for detailed vs summary treatment
        critical_findings, high_findings, summary_findings = _prioritize_findings(evidence)

        # Generate structured finding sections
        critical_section = _format_detailed_findings(critical_findings, "CRITICAL")
        high_section = _format_detailed_findings(high_findings[:5], "HIGH")  # Limit to 5 for token efficiency
        summary_table = (
            _format_summary_table(high_findings[5:] + summary_findings)
            if len(high_findings) > 5 or summary_findings
            else ""
        )

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
            "critical_findings": critical_section,
            "high_findings": high_section,
            "summary_table": summary_table,
            "analysis": report_content.get("analysis", ""),
            "immediate_recommendations": report_content.get("immediate", ""),
            "short_term_recommendations": report_content.get("short_term", ""),
            "long_term_recommendations": report_content.get("long_term", ""),
            "tools_summary": tools_summary,
            "analysis_framework": domain_lens.get("framework", "OWASP Top 10 2021"),
            "module": module,
            "evidence_count": len(evidence),
        }

        logger.info(
            "Report sections built: %d findings (%d critical, %d high)",
            len(evidence),
            severity_counts["critical"],
            severity_counts["high"],
        )

        return sections

    except Exception as e:
        logger.error("Error building report sections: %s", e, exc_info=True)
        return {"error": str(e), "operation_id": operation_id, "target": target, "objective": objective}


def _parse_structured_evidence(content: str) -> Dict[str, str]:
    """
    Parse structured evidence from memory content.

    Extracts components like [VULNERABILITY], [WHERE], [IMPACT], [EVIDENCE], [STEPS]
    from the stored finding content.

    Args:
        content: Raw memory content with structured markers

    Returns:
        Dictionary with parsed evidence components
    """
    components = {
        "vulnerability": "",
        "where": "",
        "impact": "",
        "evidence": "",
        "steps": "",
        "remediation": "",
        "confidence": "",
    }

    # Define markers to extract
    markers = {
        "VULNERABILITY": "vulnerability",
        "FINDING": "vulnerability",  # Alternative marker
        "WHERE": "where",
        "IMPACT": "impact",
        "EVIDENCE": "evidence",
        "STEPS": "steps",
        "REMEDIATION": "remediation",
        "CONFIDENCE": "confidence",
        "DISCOVERY": "vulnerability",  # Alternative marker
        "SIGNAL": "vulnerability",  # Alternative marker
    }

    for marker, key in markers.items():
        # Extract content between markers using regex
        pattern = rf"\[{marker}\]\s*(.*?)(?=\[|$)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match and not components[key]:  # Don't override if already found
            components[key] = match.group(1).strip()

    return components


def _prioritize_findings(evidence: List[Dict[str, Any]]) -> tuple:
    """
    Separate findings by severity for structured presentation.

    Returns:
        Tuple of (critical_findings, high_findings, other_findings)
    """
    critical = []
    high = []
    other = []

    for finding in evidence:
        severity = finding.get("severity", "").upper()
        if severity == "CRITICAL":
            critical.append(finding)
        elif severity == "HIGH":
            high.append(finding)
        else:
            other.append(finding)

    return critical, high, other


def _format_detailed_findings(findings: List[Dict[str, Any]], severity: str) -> str:
    """
    Format findings with evidence-first structure.

    Provides concise, professional presentation with full evidence.
    """
    if not findings:
        return ""

    output = []
    for i, finding in enumerate(findings, 1):
        title = ""
        evidence = ""
        impact = ""
        remediation = ""
        confidence = ""

        # Extract from parsed structure if available
        if "parsed" in finding and finding["parsed"]:
            parsed = finding["parsed"]
            title = parsed.get("vulnerability", f"{severity} Finding #{i}")
            location = parsed.get("where", "")
            if location:
                title += f" - {location}"
            evidence = parsed.get("evidence", "")
            impact = parsed.get("impact", "")
            remediation = parsed.get("remediation", "")
            confidence = parsed.get("confidence", finding.get("confidence", ""))
        else:
            # Fallback to content parsing
            content = finding.get("content", "")
            title = f"{severity} Finding #{i}"
            evidence = content
            impact = "Requires further investigation"
            confidence = finding.get("confidence", "")

        # Build structured finding
        output.append(f"#### {i}. {title}")

        # Show confidence if available
        if confidence:
            output.append(f"**Confidence:** {confidence}")

        # Evidence first (full for critical/high)
        if evidence:
            if severity in ["CRITICAL", "HIGH"]:
                output.append(f"**Evidence:**\n```\n{evidence}\n```")
            else:
                if len(evidence) > 500:
                    evidence = evidence[:500] + "\n[Truncated - see appendix]"
                output.append(f"**Evidence:**\n```\n{evidence}\n```")

        # Impact and remediation
        if impact:
            output.append(f"**Impact:** {impact[:200]}")

        if remediation and remediation.lower() != "not determined":
            output.append(f"**Remediation:**\n{remediation}")
        elif not remediation or remediation.lower() == "not determined":
            output.append("**Remediation:** Investigation required to determine appropriate fix")

        output.append("")  # Blank line between findings

    return "\n".join(output)


def _format_summary_table(findings: List[Dict[str, Any]]) -> str:
    """
    Create a summary table for remaining findings.

    Token-efficient presentation for lower priority findings.
    """
    if not findings:
        return ""

    table = ["| # | Severity | Finding | Location | Confidence |", "|---|----------|---------|----------|------------|"]

    for i, finding in enumerate(findings[:20], 1):  # Limit to 20 for space
        severity = finding.get("severity", "MEDIUM")
        confidence = finding.get("confidence", "N/A")

        # Extract title and location
        if "parsed" in finding and finding["parsed"]:
            parsed = finding["parsed"]
            title = parsed.get("vulnerability", "Finding")[:50]
            location = parsed.get("where", "N/A")[:30]
        else:
            content = finding.get("content", "")[:50]
            title = content.split("[WHERE]")[0] if "[WHERE]" in content else content
            location = "See appendix"

        table.append(f"| {i} | {severity} | {title} | {location} | {confidence} |")

    if len(findings) > 20:
        table.append(f"\n*Additional {len(findings) - 20} findings documented in appendix*")

    return "\n".join(table)


def _generate_findings_table(evidence_text: str, severity_counts: Dict[str, int]) -> str:
    """Generate a formatted findings table."""
    table = "| Severity | Count | Key Findings |\n"
    table += "|----------|-------|--------------|\n"

    if severity_counts["critical"] > 0:
        table += (
            f"| CRITICAL | {severity_counts['critical']} | Immediate action required - exploitable vulnerabilities |\n"
        )
    if severity_counts["high"] > 0:
        table += f"| HIGH | {severity_counts['high']} | Significant risk requiring urgent attention |\n"
    if severity_counts["medium"] > 0:
        table += f"| MEDIUM | {severity_counts['medium']} | Notable issues to address in remediation |\n"
    if severity_counts["low"] > 0:
        table += f"| LOW | {severity_counts['low']} | Minor issues for security hardening |\n"

    if sum(severity_counts.values()) == 0:
        table += "| INFO | 0 | No security findings identified |\n"

    return table
