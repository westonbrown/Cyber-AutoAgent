#!/usr/bin/env python3
"""
Report Generation Prompts for Cyber-AutoAgent

This module contains prompts for generating security assessment reports.
Centralizes all report-related prompts to avoid duplication.
"""

from typing import Dict, List, Any


def get_report_generation_prompt(
    target: str,
    objective: str,
    operation_id: str,
    steps_executed: int,
    tools_text: str,
    evidence_text: str,
) -> str:
    """
    Get the prompt for generating a security assessment report.
    
    Args:
        target: The target system that was assessed
        objective: The security assessment objective
        operation_id: The operation identifier
        steps_executed: Number of steps executed during assessment
        tools_text: Formatted summary of tools used
        evidence_text: Formatted summary of evidence collected
        
    Returns:
        The complete report generation prompt
    """
    return f"""Based on the penetration testing operation, generate a comprehensive security assessment report.

TARGET: {target}
OBJECTIVE: {objective}
OPERATION ID: {operation_id}
STEPS EXECUTED: {steps_executed}

TOOLS USED:
{tools_text}

EVIDENCE COLLECTED:
{evidence_text}

Generate a professional penetration testing report with the following sections:

1. EXECUTIVE SUMMARY
   - Brief overview of the assessment
   - Key findings and risk level
   - Main recommendations

2. TECHNICAL FINDINGS
   - Detailed vulnerabilities discovered
   - Severity ratings (Critical/High/Medium/Low)
   - Evidence and proof of concept
   - Affected components

3. ATTACK NARRATIVE
   - Step-by-step attack chain
   - Tools and techniques used
   - Access gained and data exposed

4. RECOMMENDATIONS
   - Immediate actions required
   - Short-term remediation steps
   - Long-term security improvements

5. CONCLUSION
   - Overall security posture assessment
   - Risk summary
   - Next steps

Format the report professionally with clear sections and bullet points where appropriate.
Focus on actionable findings and practical recommendations.
Be specific about vulnerabilities found and provide technical details."""


def get_report_agent_system_prompt() -> str:
    """
    Get the system prompt for the report generation agent.
    
    Returns:
        The system prompt for report generation
    """
    return (
        "You are a cybersecurity report generator. Generate comprehensive, professional "
        "penetration testing reports. Output ONLY the final report content without any "
        "preamble, thinking, or commentary. Begin directly with the report header and content."
    )


def format_evidence_for_report(evidence: List[Dict[str, Any]], max_items: int = 30) -> str:
    """
    Format evidence list into readable text for the report.
    
    Args:
        evidence: List of evidence dictionaries
        max_items: Maximum number of items to include
        
    Returns:
        Formatted evidence text
    """
    if not evidence:
        return "No specific evidence collected during assessment."
        
    evidence_text = ""
    for i, item in enumerate(evidence[:max_items]):
        category = item.get("category", "unknown").upper()
        content = item.get("content", "")[:500]
        
        if item.get("category") == "finding":
            severity = item.get("severity", "unknown").upper()
            confidence = item.get("confidence", "unknown")
            if confidence != "unknown":
                evidence_text += f"\n{i+1}. [{category} | {severity} | {confidence}] {content}"
            else:
                evidence_text += f"\n{i+1}. [{category} | {severity}] {content}"
        else:
            evidence_text += f"\n{i+1}. [{category}] {content}"
            
        if len(item.get("content", "")) > 500:
            evidence_text += "..."
            
    return evidence_text


def format_tools_summary(tools_used: List[str]) -> str:
    """
    Format tools list into a summary.
    
    Args:
        tools_used: List of tool usage strings
        
    Returns:
        Formatted tools summary
    """
    if not tools_used:
        return "No specific tools recorded."
        
    # Count tool usage
    tools_summary = {}
    for tool in tools_used:
        tool_name = tool.split(":")[0]
        if tool_name in tools_summary:
            tools_summary[tool_name] += 1
        else:
            tools_summary[tool_name] = 1
            
    # Format as text
    return "\n".join([f"- {name}: {count} uses" for name, count in tools_summary.items()])