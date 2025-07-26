#!/usr/bin/env python3
"""Report generation agent for Cyber-AutoAgent."""

import logging
import re
from typing import Dict, Any, List, Optional

from strands import Agent

logger = logging.getLogger(__name__)


class ReportAgent:
    """Specialized agent for generating security assessment reports."""

    def __init__(self, model=None, model_config=None):
        """Initialize the report agent with the same model configuration as main agent.

        Args:
            model: The model instance to use (same as main agent)
            model_config: Model configuration if creating new instance
        """
        self.model = model
        self.model_config = model_config

        # Create agent instance for report generation
        if model:
            self.agent = Agent(
                model=model, name="Cyber-ReportAgent", description="Professional security report generator"
            )
        else:
            # Will be initialized when needed with proper model
            self.agent = None

    def generate_report(
        self,
        target: str,
        objective: str,
        operation_id: str,
        steps_executed: int,
        evidence: List[Dict],
        tools_used: List[str],
    ) -> Optional[str]:
        """Generate a comprehensive security assessment report.

        Args:
            target: The target system
            objective: The operation objective
            operation_id: Unique operation identifier
            steps_executed: Number of steps executed
            evidence: List of evidence from memory
            tools_used: List of tools used during operation

        Returns:
            Generated report content or None
        """
        # Prepare evidence summary
        evidence_text = self._format_evidence(evidence)

        # Prepare tools summary
        tools_text = self._format_tools(tools_used)

        # Get report prompt
        report_prompt = self._get_report_prompt(
            target=target,
            objective=objective,
            operation_id=operation_id,
            steps_executed=steps_executed,
            tools_text=tools_text,
            evidence_text=evidence_text,
        )

        try:
            # Use the agent to generate the report
            if not self.agent:
                raise ValueError("Report agent not properly initialized with model")

            result = self.agent(report_prompt)

            if result and hasattr(result, "message"):
                content = result.message.get("content", [])
                if content and isinstance(content, list):
                    report_text = ""
                    for block in content:
                        if isinstance(block, dict) and "text" in block:
                            report_text += block["text"]

                    # Extract only the actual report, removing any preamble
                    report_text = self._extract_report_content(report_text)

                    # Clean up any duplicate content
                    report_text = self._clean_duplicate_content(report_text)
                    return report_text

            return None

        except Exception as e:
            logger.error("Error generating report: %s", e)
            return None

    def _format_evidence(self, evidence: List[Dict]) -> str:
        """Format evidence for report generation.

        Args:
            evidence: List of evidence items

        Returns:
            Formatted evidence text
        """
        evidence_text = ""
        for i, item in enumerate(evidence[:30]):  # Limit to top 30 for context
            # Format based on category and available metadata
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

    def _format_tools(self, tools_used: List[str]) -> str:
        """Format tools used summary.

        Args:
            tools_used: List of tool usage strings

        Returns:
            Formatted tools summary
        """
        tools_summary = {}
        for tool in tools_used:
            tool_name = tool.split(":")[0]
            if tool_name in tools_summary:
                tools_summary[tool_name] += 1
            else:
                tools_summary[tool_name] = 1

        return "\n".join([f"- {name}: {count} uses" for name, count in tools_summary.items()])

    def _get_report_prompt(
        self, target: str, objective: str, operation_id: str, steps_executed: int, tools_text: str, evidence_text: str
    ) -> str:
        """Get the report generation prompt.

        Args:
            target: Target system
            objective: Operation objective
            operation_id: Operation ID
            steps_executed: Number of steps
            tools_text: Formatted tools summary
            evidence_text: Formatted evidence summary

        Returns:
            Complete report generation prompt
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

    def _extract_report_content(self, raw_content: str) -> str:
        """Extract the actual report content from LLM response.

        The LLM sometimes includes thinking/preamble before the actual report.
        This method extracts only the report starting from the first report header.

        Args:
            raw_content: Raw content from LLM including possible preamble

        Returns:
            Extracted report content
        """
        # Look for common report headers
        report_markers = [
            "# PENETRATION TESTING SECURITY ASSESSMENT REPORT",
            "# Security Assessment Report",
            "# SECURITY ASSESSMENT REPORT",
            "## EXECUTIVE SUMMARY",
            "## 1. EXECUTIVE SUMMARY",
            "PENETRATION TESTING SECURITY ASSESSMENT REPORT",
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

        # If no marker found, return original content
        return raw_content

    def _clean_duplicate_content(self, report_content: str) -> str:
        """Remove duplicate sections from report content.

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
