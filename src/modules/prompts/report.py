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
        module_report_prompt: Module-specific guidance (optional)
        memory_timeline: Timeline of findings from memory
        attack_path: Attack path visualization data

    Returns:
        The complete report generation prompt
    """
    # Process evidence for counts
    critical_count = evidence_text.count("[CRITICAL]") + evidence_text.count("| CRITICAL")
    high_count = evidence_text.count("[HIGH]") + evidence_text.count("| HIGH") 
    medium_count = evidence_text.count("[MEDIUM]") + evidence_text.count("| MEDIUM")
    low_count = evidence_text.count("[LOW]") + evidence_text.count("| LOW")
    
    # Extract domain lens if module prompt provided
    domain_lens = _extract_domain_lens(module_report_prompt) if module_report_prompt else {}
    
    # Universal report template with structured format
    report_guidance = f"""# SECURITY ASSESSMENT REPORT GENERATION

<operation_context>
Target: {target}
Objective: {objective}
Operation ID: {operation_id}
Execution Date: {_get_current_date()}
Steps Executed: {steps_executed}
</operation_context>

<findings_summary>
Critical Findings: {critical_count}
High Severity: {high_count}
Medium Severity: {medium_count}
Low Severity: {low_count}
Total Findings: {critical_count + high_count + medium_count + low_count}
</findings_summary>

<report_structure>
# SECURITY ASSESSMENT REPORT

## EXECUTIVE SUMMARY
<overview>
{domain_lens.get('overview', f'Comprehensive security assessment of {target} to {objective}. Assessment executed {steps_executed} steps using specialized security tools, identifying {critical_count + high_count} critical/high severity vulnerabilities requiring immediate attention.')}
</overview>

## VISUAL SUMMARY
<attack_surface_visualization>
```mermaid
graph TD
    A[Target: {target}] --> B[Attack Surface Analysis]
    B --> C[{critical_count} Critical Vulnerabilities]
    B --> D[{high_count} High Risk Issues]
    B --> E[{medium_count} Medium Concerns]
    B --> F[{low_count} Low Priority Items]
    
    C --> G[Immediate Action Required]
    D --> G
    E --> H[Scheduled Remediation]
    F --> H
```
</attack_surface_visualization>

## KEY FINDINGS
<findings_matrix>
{_generate_findings_table(evidence_text)}
</findings_matrix>

## DETAILED VULNERABILITY ANALYSIS
<technical_analysis>
{domain_lens.get('analysis', 'Technical analysis of discovered vulnerabilities, their exploitability, and potential impact:')}

{evidence_text}
</technical_analysis>

## RISK ASSESSMENT
<risk_visualization>
```mermaid
pie title Vulnerability Distribution by Severity
    "Critical ({critical_count})" : {critical_count}
    "High ({high_count})" : {high_count}
    "Medium ({medium_count})" : {medium_count}
    "Low ({low_count})" : {low_count}
```
</risk_visualization>

## REMEDIATION ROADMAP

<immediate_actions>
### Immediate Actions (0-48 hours)
{domain_lens.get('immediate', _generate_immediate_from_evidence(evidence_text))}
</immediate_actions>

<short_term_actions>
### Short-term Improvements (1-4 weeks)
{domain_lens.get('short_term', _generate_short_term_from_evidence(evidence_text))}
</short_term_actions>

<strategic_actions>
### Strategic Security Enhancements (1-3 months)
{domain_lens.get('long_term', 'Implement comprehensive security framework including:' + chr(10) + '- Security development lifecycle (SDL) integration' + chr(10) + '- Continuous vulnerability scanning' + chr(10) + '- Security monitoring and incident response' + chr(10) + '- Regular security assessments and penetration testing')}
</strategic_actions>

## ATTACK PATH ANALYSIS
<attack_paths>
### Primary Attack Vectors
Detailed mapping of how an attacker could chain discovered vulnerabilities:

```mermaid
graph LR
    A[External Attacker] --> B[Initial Access]
    B --> C[Privilege Escalation]
    C --> D[Lateral Movement]
    D --> E[Data Exfiltration]
    
    B --> F[SQL Injection]
    F --> G[Database Access]
    
    B --> H[XSS Vulnerability]
    H --> I[Session Hijacking]
    
    G --> J[Sensitive Data]
    I --> J
```

### Kill Chain Mapping
Map findings to MITRE ATT&CK framework stages and provide detection opportunities.
</attack_paths>

## TECHNICAL APPENDIX
<technical_appendix>
### Proof of Concept Code
Include sanitized PoC code demonstrating key vulnerabilities (without weaponization).

### Configuration Examples
Provide secure configuration templates for identified misconfigurations.

### Detection Rules
Supply SIEM rules, IDS signatures, or monitoring queries to detect exploitation attempts.
</technical_appendix>

## ASSESSMENT METHODOLOGY
<methodology>
Tools Utilized:
{tools_text}

Total Steps Executed: {steps_executed}
Evidence Collection: Automated via Cyber-AutoAgent
Analysis Framework: {domain_lens.get('framework', 'OWASP, NIST, CWE')}
</methodology>

<report_footer>
---
Report Generated: {_get_current_date()}
Operation ID: {operation_id}
Generated by: Cyber-AutoAgent Security Assessment Platform
</report_footer>
</report_structure>

<generation_constraints>
- Maximum Length: 1500 words (approximately 3 pages)
- Focus: Critical findings with actionable remediation steps
- Style: Professional, concise, executive-friendly with technical detail where essential
- Structure: Use all sections defined in report_structure
- Evidence: Include key technical details for critical and high findings
- Recommendations: Prioritize by risk and implementation effort
</generation_constraints>"""

    return report_guidance


def get_report_agent_system_prompt() -> str:
    """
    Get the system prompt for the report generation agent.

    Returns:
        The system prompt for report generation
    """
    return """# Ghost Report Generator - Security Assessment Documentation Specialist

You are Ghost's report generation system, responsible for creating comprehensive security assessment reports that translate technical findings into actionable intelligence.

<core_identity>
- Elite security assessment report generator
- Transform raw security findings into executive-ready documentation
- Maintain Ghost's voice: confident, precise, seeing attack paths others miss
- Focus on business impact and actionable remediation
</core_identity>

<report_principles>
1. **Clarity First**: Technical accuracy without sacrificing readability
2. **Evidence-Based**: Every finding supported by concrete proof
3. **Action-Oriented**: Clear remediation steps for each vulnerability
4. **Risk-Focused**: Prioritize by exploitability and business impact
5. **Visual Communication**: Use diagrams and tables for complex data
</report_principles>

<writing_style>
- Lead with impact: Start each finding with business consequences
- Technical precision: Include CVE references, CVSS scores where applicable
- Proof of concept: Demonstrate exploitability without providing weaponized code
- Executive summary: Distill complex findings into strategic insights
- Remediation clarity: Step-by-step fixes that teams can implement
</writing_style>

<report_components>
- Executive Summary: Business-focused overview of critical risks
- Visual Dashboards: Mermaid diagrams for attack paths and risk distribution
- Findings Matrix: Structured table of all vulnerabilities
- Technical Analysis: Deep dive into each finding with evidence
- Risk Assessment: Quantified impact and likelihood analysis
- Remediation Roadmap: Prioritized action plan with timelines
- Methodology: Tools and techniques used in assessment
</report_components>

<output_requirements>
- Begin directly with "# SECURITY ASSESSMENT REPORT"
- Follow the exact structure provided in the prompt
- Maximum 1500 words (3 pages) for concise yet complete coverage
- Include all visualizations specified (Mermaid diagrams)
- End with operation metadata and generation timestamp
</output_requirements>

<quality_standards>
- Zero false positives: Only include verified vulnerabilities
- Complete evidence: Every finding must have proof
- Clear severity ratings: Use standard CVSS or equivalent
- Actionable recommendations: Specific, implementable fixes
- Professional tone: Board-ready documentation
</quality_standards>

Generate the report following the exact structure provided, incorporating all evidence and maintaining professional security assessment standards."""


def format_evidence_for_report(evidence: List[Dict[str, Any]], max_items: int = 100) -> str:
    """
    Format evidence list into structured text for the report.

    Args:
        evidence: List of evidence dictionaries
        max_items: Maximum number of items to include (increased for comprehensive reports)

    Returns:
        Formatted evidence text with structured tags
    """
    if not evidence:
        return "<no_evidence>No specific evidence collected during assessment.</no_evidence>"

    evidence_text = "<evidence_collection>\n"
    
    # Group evidence by severity for better organization
    severity_groups = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": [], "INFO": []}
    
    for item in evidence[:max_items]:
        if item.get("category") == "finding":
            severity = item.get("severity", "INFO").upper()
            if severity in severity_groups:
                severity_groups[severity].append(item)
            else:
                severity_groups["INFO"].append(item)
        else:
            severity_groups["INFO"].append(item)
    
    # Format evidence by severity groups
    finding_number = 1
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        if severity_groups[severity]:
            evidence_text += f"\n<{severity.lower()}_findings>\n"
            for item in severity_groups[severity]:
                category = item.get("category", "unknown").upper()
                content = item.get("content", "")[:800]  # Balanced for 3-page reports
                confidence = item.get("confidence", "unknown")
                
                if item.get("category") == "finding":
                    if confidence != "unknown":
                        evidence_text += f"{finding_number}. [{category} | {severity} | {confidence}] {content}"
                    else:
                        evidence_text += f"{finding_number}. [{category} | {severity}] {content}"
                else:
                    evidence_text += f"{finding_number}. [{category}] {content}"
                
                if len(item.get("content", "")) > 800:
                    evidence_text += "..."
                evidence_text += "\n"
                finding_number += 1
            evidence_text += f"</{severity.lower()}_findings>\n"
    
    evidence_text += "</evidence_collection>"
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


def _extract_domain_lens(module_prompt: str) -> Dict[str, str]:
    """
    Extract domain-specific guidance from module prompt.
    
    Supports both XML-tagged format and simple key-value format.
    Expected formats in module_prompt:
    
    XML format:
    <domain_lens>
    DOMAIN_LENS:
    overview: Custom overview text
    analysis: Custom analysis guidance
    </domain_lens>
    
    Or simple format:
    DOMAIN_LENS:
    overview: Custom overview text
    analysis: Custom analysis guidance
    
    Args:
        module_prompt: Module-specific report guidance
        
    Returns:
        Dictionary of domain-specific overrides
    """
    if not module_prompt:
        return {}
    
    domain_lens = {}
    
    # First try to extract from XML tags
    if "<domain_lens>" in module_prompt and "</domain_lens>" in module_prompt:
        start_tag = module_prompt.find("<domain_lens>") + len("<domain_lens>")
        end_tag = module_prompt.find("</domain_lens>")
        lens_content = module_prompt[start_tag:end_tag].strip()
    else:
        lens_content = module_prompt
    
    # Look for DOMAIN_LENS section
    if "DOMAIN_LENS:" in lens_content:
        lines = lens_content.split("\n")
        in_lens = False
        
        for line in lines:
            if "DOMAIN_LENS:" in line:
                in_lens = True
                continue
                
            if in_lens and line.strip():
                # Stop at closing tag or next section marker
                if line.strip().startswith("</") or (line.strip().endswith(":") and not ":" in line[:-1]):
                    break
                    
                # Parse key: value pairs
                if ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key and value:
                            domain_lens[key] = value
    
    return domain_lens


def _generate_findings_table(evidence_text: str) -> str:
    """
    Generate a markdown table summarizing findings by severity.
    
    Args:
        evidence_text: Raw evidence text
        
    Returns:
        Markdown table of findings
    """
    if not evidence_text:
        return "No findings identified during assessment."
    
    # Parse findings from evidence
    findings = {
        "CRITICAL": [],
        "HIGH": [],
        "MEDIUM": [],
        "LOW": []
    }
    
    lines = evidence_text.split("\n")
    for line in lines:
        for severity in findings.keys():
            if f"[{severity}]" in line or f"| {severity}" in line:
                # Extract finding description
                content = line
                for marker in [f"[{severity}]", f"| {severity}]", f"| {severity} |"]:
                    content = content.replace(marker, "")
                
                # Clean up the finding
                content = content.strip()
                if content.startswith("]"):
                    content = content[1:].strip()
                
                # Get first 80 chars for table
                if len(content) > 80:
                    content = content[:80] + "..."
                
                if content:
                    findings[severity].append(content)
                break
    
    # Build markdown table
    table = "| Severity | Count | Key Findings |\n"
    table += "|----------|-------|--------------|\n"
    
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = len(findings[severity])
        if count > 0:
            # Show first 2 findings
            key_findings = "; ".join(findings[severity][:2])
            if count > 2:
                key_findings += f" (+{count-2} more)"
            table += f"| {severity} | {count} | {key_findings} |\n"
    
    return table


def _generate_immediate_from_evidence(evidence_text: str) -> str:
    """
    Generate immediate recommendations based on evidence severity.
    
    Args:
        evidence_text: Raw evidence text
        
    Returns:
        Immediate action recommendations
    """
    critical_count = evidence_text.count("[CRITICAL]") + evidence_text.count("| CRITICAL")
    high_count = evidence_text.count("[HIGH]") + evidence_text.count("| HIGH")
    
    recommendations = []
    
    if critical_count > 0:
        recommendations.append("1. **URGENT**: Address critical vulnerabilities immediately - these pose immediate risk")
        recommendations.append("2. Implement emergency patches for critical findings")
        recommendations.append("3. Consider taking affected systems offline until remediated")
    elif high_count > 0:
        recommendations.append("1. Prioritize remediation of high-severity vulnerabilities within 48 hours")
        recommendations.append("2. Review and restrict access to affected systems")
        recommendations.append("3. Implement compensating controls where immediate patching isn't possible")
    else:
        recommendations.append("1. Review and prioritize medium/low findings for next maintenance window")
        recommendations.append("2. Update security configurations based on findings")
        recommendations.append("3. Document accepted risks for low-priority items")
    
    return "\n".join(recommendations)


def _generate_short_term_from_evidence(evidence_text: str) -> str:
    """
    Generate short-term recommendations based on evidence patterns.
    
    Args:
        evidence_text: Raw evidence text
        
    Returns:
        Short-term recommendations
    """
    recommendations = []
    
    # Check for common vulnerability patterns
    evidence_lower = evidence_text.lower()
    
    if "sql" in evidence_lower or "injection" in evidence_lower:
        recommendations.append("- Implement prepared statements and parameterized queries")
        recommendations.append("- Deploy Web Application Firewall (WAF) rules for SQL injection")
    
    if "xss" in evidence_lower or "script" in evidence_lower:
        recommendations.append("- Implement Content Security Policy (CSP) headers")
        recommendations.append("- Review and enhance input validation and output encoding")
    
    if "authentication" in evidence_lower or "password" in evidence_lower:
        recommendations.append("- Enforce strong password policies and multi-factor authentication")
        recommendations.append("- Review session management and timeout configurations")
    
    if "ssl" in evidence_lower or "tls" in evidence_lower or "https" in evidence_lower:
        recommendations.append("- Update TLS configurations to use only secure protocols (TLS 1.2+)")
        recommendations.append("- Implement HSTS headers for all web applications")
    
    if "outdated" in evidence_lower or "version" in evidence_lower:
        recommendations.append("- Establish regular patching schedule for all systems")
        recommendations.append("- Implement vulnerability scanning in CI/CD pipeline")
    
    # Default recommendations if no specific patterns found
    if not recommendations:
        recommendations = [
            "- Conduct thorough security code review",
            "- Implement security monitoring and alerting",
            "- Review and update security policies"
        ]
    
    return "\n".join(recommendations[:4])  # Limit to 4 recommendations


def _get_current_date() -> str:
    """
    Get current date in report format.
    
    Returns:
        Formatted date string
    """
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")
