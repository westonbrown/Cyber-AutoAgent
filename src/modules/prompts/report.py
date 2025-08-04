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
    module_report_prompt: str = None,
    memory_timeline: str = None,
    attack_path: str = None,
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
        memory_timeline: Timeline of findings from memory
        attack_path: Attack path visualization data

    Returns:
        The complete report generation prompt
    """
    # Add memory context if available
    memory_context = ""
    if memory_timeline:
        memory_context = f"\n\nATTACK TIMELINE:\n{memory_timeline}"
    if attack_path:
        memory_context += f"\n\nATTACK PATH:\n{attack_path}"

    # Use module-specific report guidance if provided
    if module_report_prompt:
        report_guidance = f"""
[MODULE REPORT GUIDANCE]
{module_report_prompt}

[ASSESSMENT DATA]
TARGET: {target}
OBJECTIVE: {objective}
OPERATION ID: {operation_id}
STEPS EXECUTED: {steps_executed}

TOOLS USED:
{tools_text}

EVIDENCE COLLECTED:
{evidence_text}
{memory_context}

Based on the module-specific guidance above and the assessment data, generate a professional security report that follows the domain-specific approach while ensuring all findings are properly documented."""
    else:
        # Streamlined security report format
        report_guidance = f"""Ghost's Security Assessment Report

TARGET: {target} | OBJECTIVE: {objective} | OP: {operation_id} | STEPS: {steps_executed}

TOOLS: {tools_text}
EVIDENCE: {evidence_text}
{memory_context}

Generate concise security report (max 500 words):

# EXECUTIVE SUMMARY
3 sentences: What was tested, key findings, business impact.

# ATTACK FLOW
```mermaid
graph TD
    A[Recon] --> B[Discovery]
    B --> C[Exploit]
    C --> D[Impact]
```

# FINDINGS TABLE
| Vulnerability | Severity | Impact | Evidence |
|--------------|----------|---------|----------|
| [Vuln] | Critical/High/Medium/Low | [Impact] | [Proof] |

# ATTACK NARRATIVE
Brief story of compromise:
1. **Recon**: Surface mapping
2. **Discovery**: Vulnerabilities found
3. **Exploit**: Compromise achieved
4. **Impact**: Access/data obtained

# RECOMMENDATIONS
- **Immediate**: Critical fixes
- **Short-term**: Hardening
- **Long-term**: Architecture

# CONCLUSION
Security score [X/10]. Key gaps. Next steps.

Ghost's voice: Confident. Precise. No fluff."""

    return report_guidance


def get_report_agent_system_prompt() -> str:
    """
    Get the system prompt for the report generation agent.

    Returns:
        The system prompt for report generation
    """
    return (
        "You are Ghost's report generator, creating professional security assessment reports. "
        "Generate comprehensive reports with visual elements (Mermaid diagrams, tables). "
        "Write with Ghost's distinctive voice - confident, precise, seeing attack paths others miss. "
        "Output ONLY the final report content. Begin directly with the report header."
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
