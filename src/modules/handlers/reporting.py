"""
Report generation and evaluation utilities for the handlers module.

This module contains functions for generating final reports, sending operation
metadata, and triggering evaluation processes.
"""

import os
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from .utils import Colors, get_output_path
from .base import LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
from ..agents.report_agent import ReportAgent


def generate_final_report(
    handler_state: Any, agent: Any, target: str, objective: str, memory_config: Optional[Dict[str, Any]] = None
) -> None:
    """Generate comprehensive final report using LLM analysis.

    Args:
        handler_state: The handler object containing operation data and state
        agent: The agent instance
        target: The target system
        objective: The operation objective
        memory_config: Optional memory configuration
    """
    # Ensure single report generation
    if handler_state.state.report_generated:
        return
    handler_state.state.report_generated = True

    # Send operation metadata to Langfuse
    _send_operation_metadata(handler_state.state)

    # Collect evidence from memory first
    evidence = _retrieve_evidence(handler_state.state, memory_config)

    # Only generate report if evidence was collected
    if not evidence:
        print("\n%s%s%s" % (Colors.DIM, "═" * 80, Colors.RESET))
        print(
            "%s%sNo evidence collected - skipping final report generation%s"
            % (Colors.YELLOW, Colors.BOLD, Colors.RESET)
        )
        print("%s%s%s" % (Colors.DIM, "═" * 80, Colors.RESET))
        return

    print("\n%s%s%s" % (Colors.DIM, "═" * 80, Colors.RESET))
    print("%s🔍 GENERATING COMPREHENSIVE SECURITY ASSESSMENT REPORT%s" % (Colors.BOLD, Colors.RESET))
    print("%s%s%s" % (Colors.DIM, "═" * 80, Colors.RESET))

    # Generate report using LLM
    # Create report agent with same model as main agent
    report_agent = ReportAgent(model=agent.model if hasattr(agent, "model") else None)

    # Generate report using dedicated agent
    report_content = report_agent.generate_report(
        target=target,
        objective=objective,
        operation_id=handler_state.state.operation_id,
        steps_executed=handler_state.state.steps,
        evidence=evidence,
        tools_used=handler_state.state.tools_used,
    )

    if report_content:
        # Display the report
        _display_final_report(report_content)

        # Save report to file
        _save_report_to_file(handler_state, report_content, target, objective)

        # Trigger evaluation if enabled
        _trigger_evaluation_if_enabled(handler_state)
    else:
        print("%s%sFailed to generate report%s" % (Colors.RED, Colors.BOLD, Colors.RESET))


def _retrieve_evidence(
    handler_state: Any, memory_config: Optional[Dict[str, Any]]
) -> List[Dict]:  # pylint: disable=unused-argument
    """Retrieve evidence from memory system.

    Args:
        handler_state: The handler state object
        memory_config: Memory configuration

    Returns:
        List of evidence dictionaries
    """
    evidence = []
    memory_client = _get_memory_client_for_report(memory_config)

    if not memory_client:
        return evidence

    try:
        # Retrieve memories using list_memories method
        # The memory system uses "cyber_agent" as the default user_id
        memories_response = memory_client.list_memories(user_id="cyber_agent")

        # Parse memory response format (same as old implementation)
        if isinstance(memories_response, dict):
            # Extract from dictionary response
            raw_memories = memories_response.get("memories", memories_response.get("results", []))
        elif isinstance(memories_response, list):
            # Process list response
            raw_memories = memories_response
        else:
            # Handle unexpected format
            raw_memories = []
            print(
                f"  %sWarning: Unexpected memory response format: {type(memories_response)}%s"
                % (Colors.YELLOW, Colors.RESET)
            )

        # Process memories according to category and content length
        for mem in raw_memories:
            metadata = mem.get("metadata", {})
            memory_content = mem.get("memory", "")
            memory_id = mem.get("id", "")

            # Process memories with category "finding" in metadata
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
            # Process uncategorized memories (no category in metadata)
            elif "category" not in metadata and memory_content:
                # Only include short uncategorized memories
                if len(memory_content.split()) < 100:
                    evidence.append(
                        {
                            "category": "general",
                            "content": memory_content,
                            "id": memory_id,
                            "severity": "unknown",
                            "confidence": "unknown",
                        }
                    )

        print(f"  %sCollected {len(evidence)} pieces of evidence from memory%s" % (Colors.GREEN, Colors.RESET))

    except Exception as e:
        print(f"  %sError retrieving evidence: {e}%s" % (Colors.RED, Colors.RESET))

    return evidence


def _get_memory_client_for_report(memory_config: Optional[Dict[str, Any]]) -> Optional[Any]:
    """Get memory client for report generation.

    Args:
        memory_config: Memory configuration

    Returns:
        Memory client instance or None
    """
    if not memory_config:
        # Fall back to global memory client
        try:
            from ..tools.memory import get_memory_client

            # Return the wrapper itself, not the inner mem0 client
            return get_memory_client()
        except Exception:
            return None

    try:
        # Try to get memory client from config
        from ..tools.memory import Mem0ServiceClient

        # Initialize memory client with config
        # Return the wrapper itself which has list_memories method
        return Mem0ServiceClient(config=memory_config)

    except Exception as e:
        print(f"  %sWarning: Could not access memory for report: {e}%s" % (Colors.YELLOW, Colors.RESET))
        return None


def _generate_llm_report(
    handler_state: Any, agent: Any, target: str, objective: str, evidence: List[Dict]
) -> Optional[str]:
    """Generate report content using LLM analysis.

    Args:
        handler_state: The handler state object
        agent: The agent instance
        target: The target system
        objective: The operation objective
        evidence: List of evidence from memory

    Returns:
        Generated report content or None
    """
    # Prepare evidence summary
    evidence_text = ""
    for i, item in enumerate(evidence[:30]):  # Limit to top 30 for context
        # Format based on category and available metadata
        category = item["category"].upper()
        content = item["content"][:500]

        if item["category"] == "finding":
            severity = item.get("severity", "unknown").upper()
            confidence = item.get("confidence", "unknown")
            if confidence != "unknown":
                evidence_text += f"\n{i+1}. [{category} | {severity} | {confidence}] {content}"
            else:
                evidence_text += f"\n{i+1}. [{category} | {severity}] {content}"
        else:
            evidence_text += f"\n{i+1}. [{category}] {content}"

        if len(item["content"]) > 500:
            evidence_text += "..."

    # Prepare tools used summary
    tools_summary = {}
    for tool in handler_state.tools_used:
        tool_name = tool.split(":")[0]
        if tool_name in tools_summary:
            tools_summary[tool_name] += 1
        else:
            tools_summary[tool_name] = 1

    tools_text = "\n".join([f"- {name}: {count} uses" for name, count in tools_summary.items()])

    # Generate report prompt
    report_prompt = f"""Based on the penetration testing operation, generate a comprehensive security assessment report.

TARGET: {target}
OBJECTIVE: {objective}
OPERATION ID: {handler_state.operation_id}
STEPS EXECUTED: {handler_state.steps}

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

    try:
        # Use the agent to generate the report
        print("  %sAnalyzing evidence and generating report...%s" % (Colors.CYAN, Colors.RESET))
        result = agent(report_prompt)

        if result and hasattr(result, "message"):
            content = result.message.get("content", [])
            if content and isinstance(content, list):
                report_text = ""
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        report_text += block["text"]

                # Clean up any duplicate content
                report_text = _clean_duplicate_content(report_text)
                return report_text

        return None

    except Exception as e:
        print(f"  %sError generating report: {e}%s" % (Colors.RED, Colors.RESET))
        return None


def _clean_duplicate_content(report_content: str) -> str:
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


def _display_final_report(report_content: str) -> None:
    """Display the final report with formatting.

    Args:
        report_content: The report content to display
    """
    print("\n" + "─" * 80)
    print(report_content)
    print("─" * 80 + "\n")


def _save_report_to_file(handler_state: Any, report_content: str, target: str, objective: str) -> None:
    """Save report to file in operation directory.

    Args:
        handler_state: The handler object
        report_content: The report content
        target: The target system
        objective: The operation objective
    """
    try:
        # Determine output path
        if handler_state.output_base_dir:
            from .utils import sanitize_target_name

            target_name = sanitize_target_name(target)
            report_dir = get_output_path(
                target_name=target_name,
                operation_id=handler_state.state.operation_id,
                base_dir=handler_state.output_base_dir,
            )
        else:
            report_dir = "."

        # Create directory if needed
        os.makedirs(report_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"security_assessment_report_{timestamp}.md"
        report_path = os.path.join(report_dir, report_filename)

        # Write report
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Security Assessment Report\n\n")
            f.write(f"**Target:** {target}\n")
            f.write(f"**Objective:** {objective}\n")
            f.write(f"**Operation ID:** {handler_state.state.operation_id}\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Total Steps:** {handler_state.state.steps}\n\n")
            f.write("---\n\n")
            f.write(report_content)

        print("\n%s📄 Report saved to: %s%s%s" % (Colors.GREEN, Colors.BOLD, report_path, Colors.RESET))

    except Exception as e:
        print("\n%sError saving report: %s%s" % (Colors.RED, e, Colors.RESET))


def _trigger_evaluation_if_enabled(handler_state: Any) -> None:
    """Trigger evaluation process if enabled.

    Args:
        handler_state: The handler object
    """
    if not os.getenv("ENABLE_AUTO_EVALUATION", "").lower() == "true":
        return

    try:
        print("\n%s🔬 Triggering operation evaluation...%s" % (Colors.CYAN, Colors.RESET))
        
        # The evaluation is already triggered in the callback handler
        # This function is kept for backward compatibility but the actual
        # evaluation happens in callback.py using trigger_evaluation_on_completion()
        print("%s✅ Evaluation triggered in background%s" % (Colors.GREEN, Colors.RESET))

    except Exception as e:
        print("%sError triggering evaluation: %s%s" % (Colors.RED, e, Colors.RESET))


def _send_operation_metadata(handler_state: Any) -> None:  # pylint: disable=unused-argument
    """Send operation metadata to Langfuse for tracking.

    Args:
        handler_state: The handler state object
    """
    try:
        # Check if Langfuse is configured
        if not all([LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY]):
            return

        # Import here to avoid circular imports
        try:
            from langfuse import Langfuse
        except ImportError:
            return

        # Initialize Langfuse client
        Langfuse(host=LANGFUSE_HOST, public_key=LANGFUSE_PUBLIC_KEY, secret_key=LANGFUSE_SECRET_KEY)

        # Could send operation metadata here if needed
        # metadata = {
        #     "operation_id": handler_state.operation_id,
        #     "steps_executed": handler_state.steps,
        #     "tools_used": len(handler_state.tools_used),
        #     "memory_operations": handler_state.memory_operations,
        #     "tool_effectiveness": handler_state.tool_effectiveness,
        #     "unique_tools": list({t.split(":")[0] for t in handler_state.tools_used}),
        # }

    except Exception:
        # Silently fail - don't interrupt operation for telemetry
        pass
