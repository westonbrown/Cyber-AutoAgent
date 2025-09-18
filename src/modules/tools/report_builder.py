#!/usr/bin/env python3
"""
Report Builder Tool for Cyber-AutoAgent

A single, comprehensive tool that the report agent can use to build
security assessment reports from operation evidence.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from strands import tool

from modules.prompts.factory import (
    _extract_domain_lens,
    _transform_evidence_to_content,
    format_evidence_for_report,
    format_tools_summary,
    generate_findings_summary_table,
)
from modules.tools.memory import get_memory_client, Mem0ServiceClient

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


def _safe_truncate(text: str, n: int) -> str:
    """Safely truncate text to n characters, preserving readability.

    Adds an ellipsis when truncation occurs and handles None/empty inputs.
    """
    if text is None:
        return ""
    s = str(text).strip()
    if len(s) <= max(0, n):
        return s
    if n <= 3:
        return s[:max(0, n)]
    return s[: n - 3] + "..."


def _clean_remediation_text(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    if t.lower() in {"not determined", "unknown", "n/a"}:
        return "TBD — requires protocol review"
    return t


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
    Build structured sections for the security assessment report.

    Retrieves operation-scoped evidence and plan, summarizes findings,
    and returns preformatted sections for the final report template.

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

        # Initialize memory client and retrieve evidence and plans
        evidence = []
        operation_plan = None

        # Prefer the existing global memory client to ensure identical backend/path
        try:
            from modules.tools.memory import get_memory_client as _get_mem_client
            memory_client = _get_memory_client(silent=True)  # type: ignore[name-defined]
        except Exception:
            memory_client = None

        if not memory_client:
            # Configure memory client with target-specific path as a fallback
            config = Mem0ServiceClient.get_default_config()
            if config and "vector_store" in config and "config" in config["vector_store"]:
                safe_target_name = sanitize_target_for_path(target)
                config["vector_store"]["config"]["path"] = f"outputs/{safe_target_name}/memory"
            # Use silent mode to suppress initialization output during report generation
            memory_client = Mem0ServiceClient(config, silent=True)
            logger.info("Initialized memory client (fallback) for target: %s", target)
        else:
            logger.info("Using existing memory client for report sections")

        if memory_client:
            try:
                memories = memory_client.list_memories(user_id="cyber_agent")
                raw_memories = []
                if isinstance(memories, dict):
                    raw_memories = memories.get("results", []) or memories.get("memories", []) or []
                elif isinstance(memories, list):
                    raw_memories = memories

                # Do not filter by operation_id; include all relevant memories for the report
                # Select an active plan if available; otherwise the first plan found
                for memory_item in raw_memories:
                    memory_content = memory_item.get("memory", "")
                    metadata = memory_item.get("metadata", {})

                    # Operation plan selection
                    if metadata and metadata.get("category") == "plan" and not operation_plan:
                        if metadata.get("active", True):
                            operation_plan = memory_content
                            logger.info("Selected active operation plan from memory")
                            continue
                        # Defer non-active plans in case an active shows up later

                    # Always include original content in evidence for downstream filters/tests
                    base_evidence = {
                        "category": "finding",
                        "content": memory_content,
                        "id": memory_item.get("id", ""),
                        "anchor_id": ("finding-" + str(memory_item.get("id", ""))) if memory_item.get("id") else "",
                        "anchor": ("#finding-" + str(memory_item.get("id", ""))) if memory_item.get("id") else "",
                    }

                    # Findings via metadata
                    if metadata and metadata.get("category") == "finding":
                        item = base_evidence.copy()
                        sev = metadata.get("severity", "MEDIUM")
                        conf = str(metadata.get("confidence", ""))
                        # Parse structured markers from the content so downstream sections have clean fields
                        parsed_evidence = _parse_structured_evidence(memory_content)
                        item.update(
                            {
                                "severity": sev,
                                "confidence": conf,
                                "parsed": parsed_evidence if isinstance(parsed_evidence, dict) else {},
                                "validation_status": str(metadata.get("validation_status", "")).strip() or None,
                            }
                        )
                        evidence.append(item)
                        continue

                    # JSON-encoded finding
                    if memory_content.startswith("{"):
                        try:
                            parsed = json.loads(memory_content)
                            if parsed.get("category") == "finding":
                                item = base_evidence.copy()
                                item.update(parsed)
                                evidence.append(item)
                                continue
                        except json.JSONDecodeError:
                            pass

                    # Text-based structured evidence (markers)
                    if any(
                        marker in memory_content
                        for marker in ["[FINDING]", "[SIGNAL]", "[VULNERABILITY]", "[DISCOVERY]"]
                    ):
                        severity = str(metadata.get("severity", "INFO"))
                        if severity == "INFO":
                            if "[CRITICAL]" in memory_content:
                                severity = "CRITICAL"
                            elif "[HIGH]" in memory_content or metadata.get("severity") == "high":
                                severity = "HIGH"
                            elif "[MEDIUM]" in memory_content or metadata.get("severity") == "medium":
                                severity = "MEDIUM"
                            elif "[LOW]" in memory_content:
                                severity = "LOW"

                        parsed_evidence = _parse_structured_evidence(memory_content)

                        # Confidence preference: parsed value if present else metadata (pass-through)
                        parsed_conf = parsed_evidence.get("confidence") if isinstance(parsed_evidence, dict) else ""
                        conf = parsed_conf or str(metadata.get("confidence", ""))

                        item = base_evidence.copy()
                        item.update(
                            {
                                "severity": severity,
                                "parsed": parsed_evidence,
                                "confidence": conf,
                                "validation_status": str(metadata.get("validation_status", "")).strip() or None,
                            }
                        )
                        evidence.append(item)

                # If no active plan was found, pick the first plan present (if any)
                if not operation_plan:
                    for memory_item in raw_memories:
                        meta = memory_item.get("metadata", {})
                        if meta and meta.get("category") == "plan":
                            operation_plan = memory_item.get("memory", "")
                            logger.info("Selected first available plan from memory")
                            break

                logger.info("Retrieved %d pieces of evidence from memory", len(evidence))
            except Exception as e:
                logger.error("Failed to retrieve evidence: %s", e)

        # If no evidence, let LLM handle empty evidence
        if not evidence:
            evidence = []

        # Format evidence for report
        evidence_text = format_evidence_for_report(evidence)

        # Count severities from actual evidence, not just text
        severity_counts = {
            "critical": sum(1 for e in evidence if str(e.get("severity", "")).upper() == "CRITICAL"),
            "high": sum(1 for e in evidence if str(e.get("severity", "")).upper() == "HIGH"),
            "medium": sum(1 for e in evidence if str(e.get("severity", "")).upper() == "MEDIUM"),
            "low": sum(1 for e in evidence if str(e.get("severity", "")).upper() == "LOW"),
        }

        # Generate findings table (structured, deterministic)
        findings_table = generate_findings_summary_table(evidence)

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

        # Format tools summary (accepts dict or list); prefer accurate counts if provided
        tools_summary = ""
        try:
            # If caller passed repeated names, we’ll get counts automatically
            # If caller passed a unique set, counts will be 1 each
            tools_summary = format_tools_summary(tools_used or [])
        except Exception:
            tools_summary = format_tools_summary([])

        # Separate findings for detailed vs summary treatment
        critical_findings, high_findings, summary_findings = _prioritize_findings(evidence)

        # Generate structured finding sections - include ALL findings for comprehensive report
        critical_section = _format_detailed_findings(critical_findings, "CRITICAL")
        high_section = _format_detailed_findings(high_findings, "HIGH")  # Include ALL high findings
        summary_table = _format_summary_table(summary_findings) if summary_findings else ""

        # Format the operation plan
        operation_plan_formatted = _format_operation_plan(operation_plan)

        # Prepare raw evidence for LLM to generate attack paths and technical content
        raw_evidence = []
        for finding in evidence:
            if finding.get("category") == "finding":
                parsed = finding.get("parsed", {}) if isinstance(finding.get("parsed"), dict) else {}
                location = parsed.get("where", "")
                if not location:
                    # Fallback: try to extract [WHERE] from content text
                    content_text = finding.get("content", "") or ""
                    try:
                        import re as _re
                        m = _re.search(r"\[WHERE\]\s*([^\n\r]+)", content_text)
                        if m:
                            location = m.group(1).strip()
                    except Exception:
                        pass

                raw_evidence.append(
                    {
                        "id": finding.get("id", ""),
                        "severity": finding.get("severity"),
                        "vulnerability": parsed.get("vulnerability", ""),
                        "location": location,
                        "impact": parsed.get("impact", ""),
                        "evidence": parsed.get("evidence", ""),
                        "steps": parsed.get("steps", ""),
                        "remediation": _clean_remediation_text(parsed.get("remediation", "")),
                        "confidence": finding.get("confidence", ""),
                        "validation_status": finding.get("validation_status"),
                        "content": finding.get("content", ""),
                    }
                )

        # Extract token/duration/cost metrics from the operation log (best-effort)
        metrics_input = 0
        metrics_output = 0
        metrics_total = 0
        metrics_duration = ""
        metrics_cost = None
        try:
            safe_target_name = sanitize_target_for_path(target)
            log_path = os.path.join("outputs", safe_target_name, operation_id, "cyber_operations.log")
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "__CYBER_EVENT__" in line and '"type": "metrics_update"' in line:
                            # Extract JSON between markers
                            try:
                                start = line.index("__CYBER_EVENT__") + len("__CYBER_EVENT__")
                                end = line.index("__CYBER_EVENT_END__")
                                payload = json.loads(line[start:end])
                                m = payload.get("metrics", {}) if isinstance(payload, dict) else {}
                                # Prefer the most recent values (overwrite as we go)
                                metrics_input = int(m.get("inputTokens", metrics_input) or 0)
                                metrics_output = int(m.get("outputTokens", metrics_output) or 0)
                                metrics_total = int(m.get("totalTokens", m.get("tokens", metrics_total) or 0))
                                metrics_duration = str(m.get("duration", metrics_duration) or metrics_duration)
                                if "cost" in m:
                                    try:
                                        metrics_cost = float(m.get("cost"))
                                    except Exception:
                                        pass
                            except Exception:
                                continue
        except Exception:
            # Ignore metrics extraction failures silently
            pass

        # Build canonical findings (first per severity) with stable anchors
        canonical_findings: Dict[str, Dict[str, Any]] = {}
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            sev_items = [e for e in evidence if str(e.get("severity", "")).upper() == sev]
            if not sev_items:
                continue
            top = sev_items[0]
            p = top.get("parsed", {}) if isinstance(top.get("parsed"), dict) else {}
            anchor_link = str(top.get("anchor") or "").strip()
            if not anchor_link and str(top.get("id") or "").strip():
                anchor_link = f"#finding-{top['id']}"
            canonical_findings[sev] = {
                "id": top.get("id", ""),
                "title": (p.get("vulnerability") or _safe_truncate(str(top.get("content", "")), 60)).strip(),
                "where": (p.get("where") or "").strip(),
                "anchor": anchor_link,
            }

        # Build complete sections dictionary
        sections = {
            "operation_id": operation_id,
            "target": target,
            "objective": objective,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "steps_executed": steps_executed,
            "severity_counts": severity_counts,
            "critical_count": severity_counts["critical"],
            "high_count": severity_counts["high"],
            "medium_count": severity_counts["medium"],
            "low_count": severity_counts["low"],
            "module_report": "",  # LLM generates from context
            "visual_summary": "",  # LLM generates mermaid diagram
            "overview": report_content.get("overview", ""),
            "operation_plan": operation_plan_formatted,
            "evidence_text": evidence_text,
            "findings_table": findings_table,
            "critical_findings": critical_section,
            "high_findings": high_section,
            "summary_table": summary_table,
            "analysis": report_content.get("analysis", ""),
            "immediate_recommendations": report_content.get("immediate", ""),
            "short_term_recommendations": report_content.get("short_term", ""),
            "long_term_recommendations": report_content.get("long_term", ""),
            "raw_evidence": raw_evidence,  # For LLM to generate attack paths and technical content
            "tools_summary": tools_summary,
            "analysis_framework": domain_lens.get("framework", ""),
            "module": module,
            "evidence_count": len(evidence),
            "canonical_findings": canonical_findings,
            # Execution metrics for direct insertion into the template
            "input_tokens": metrics_input,
            "output_tokens": metrics_output,
            "total_tokens": metrics_total or (metrics_input + metrics_output),
            "total_duration": metrics_duration,
            "estimated_cost": (
                f"${metrics_cost:.4f}" if isinstance(metrics_cost, (int, float)) and metrics_cost > 0 else "N/A"
            ),
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
        # Updated pattern to better handle multi-line content
        pattern = rf"\[{marker}\]\s*(.*?)(?=\[(?:VULNERABILITY|FINDING|WHERE|IMPACT|EVIDENCE|STEPS|REMEDIATION|CONFIDENCE|DISCOVERY|SIGNAL)|$)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match and not components[key]:  # Don't override if already found
            extracted = match.group(1).strip()
            # Clean up the extracted content
            if extracted:
                components[key] = extracted

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
        severity = str(finding.get("severity", "")).upper()
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
        status = str(finding.get("validation_status") or "").strip()

        # Extract from parsed structure if available
        if "parsed" in finding and finding["parsed"]:
            parsed = finding["parsed"]
            title = parsed.get("vulnerability", "")
            location = parsed.get("where", "")
            if location:
                title += f" - {location}"
            evidence = parsed.get("evidence", "")
            impact = parsed.get("impact", "")
            remediation = parsed.get("remediation", "")
            confidence = parsed.get("confidence", "")
        else:
            # Use raw content if no parsed structure
            content = finding.get("content", "")
            title = ""
            evidence = content
            impact = ""
            remediation = ""
            confidence = finding.get("confidence", "")

        # Normalize fields (only remediation cleanup; display confidence as-is)
        confidence = confidence or finding.get("confidence", "")
        remediation = _clean_remediation_text(remediation)

        # If impact missing, attempt to parse from original content
        if not impact:
            parsed_fallback = _parse_structured_evidence(finding.get("content", "") or "")
            impact = parsed_fallback.get("impact", "") if isinstance(parsed_fallback, dict) else ""

        # Build structured finding
        anchor_id = str(finding.get("anchor_id") or "").strip()
        if anchor_id:
            output.append(f"<a id=\"{anchor_id}\"></a>")
        output.append(f"#### {i}. {title}")

        # Status badge and confidence
        if status:
            status_norm = "Verified" if status.lower() == "verified" else ("Unverified" if status else "")
            if status_norm:
                output.append(f"**Status:** {status_norm}")
        if confidence:
            output.append(f"**Confidence:** {confidence}")

        # Evidence first (full for critical/high)
        if evidence:
            # For critical/high, show full evidence
            if severity in ["CRITICAL", "HIGH"]:
                # If evidence is the full content with markers, format it better
                if "[VULNERABILITY]" in evidence and "[WHERE]" in evidence:
                    # Parse inline for display
                    formatted_evidence = evidence
                    for marker in [
                        "[VULNERABILITY]",
                        "[WHERE]",
                        "[IMPACT]",
                        "[EVIDENCE]",
                        "[STEPS]",
                        "[REMEDIATION]",
                        "[CONFIDENCE]",
                    ]:
                        formatted_evidence = formatted_evidence.replace(marker, f"\n{marker}")
                    output.append(f"**Evidence:**\n```\n{formatted_evidence.strip()}\n```")
                else:
                    output.append(f"**Evidence:**\n```\n{evidence}\n```")
            else:
                if len(evidence) > 500:
                    evidence = evidence[:500] + "\n[Truncated - see appendix]"
                output.append(f"**Evidence:**\n```\n{evidence}\n```")

        # Impact and remediation - always show them
        impact_text = impact if impact else "N/A"
        output.append(f"**Impact:** {impact_text}")
        output.append(f"**Remediation:** {remediation if remediation else 'TBD — requires protocol review'}")

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

    for i, finding in enumerate(findings[:50], 1):  # Include up to 50 findings in summary
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

    # Include all findings count if more than shown
    if len(findings) > 50:
        table.append(f"\n*Total findings: {len(findings)}*")

    return "\n".join(table)


def _format_operation_plan(plan_content: str) -> str:
    """Format the operation plan for inclusion in the report."""
    if not plan_content:
        return ""

    # Try to parse JSON plan
    if plan_content.startswith("[PLAN]"):
        plan_content = plan_content.replace("[PLAN]", "").strip()

    try:
        import json

        plan_data = json.loads(plan_content)

        # Return raw plan data as JSON for LLM to format
        return json.dumps(plan_data, indent=2)
    except (json.JSONDecodeError, TypeError):
        # Return raw plan if not JSON
        return plan_content


def _generate_findings_table(evidence_text: str, severity_counts: Dict[str, int]) -> str:
    """Generate the Key Findings table with richer context.

    Columns:
    - Severity
    - Count
    - Top Finding (from evidence)
    - Typical Location (if available)
    - Confidence (if available)
    """

    # Derive a simple top-finding and location per severity from evidence_text using heuristics.
    # evidence_text is grouped by headings and includes structured blocks.
    def _extract_top_finding_and_location(block: str) -> tuple[str, str, str]:
        title = ""
        location = ""
        confidence = ""
        # Try to parse VULNERABILITY and WHERE markers
        import re

        m_v = re.search(r"\[VULNERABILITY\]\s*(.+)", block)
        if m_v:
            title = m_v.group(1).strip()
        m_w = re.search(r"\[WHERE\]\s*(.+)", block)
        if m_w:
            location = m_w.group(1).strip()
        m_c = re.search(r"\[CONFIDENCE\]\s*([0-9]{1,3}%)(?:\s*-.*)?", block)
        if m_c:
            confidence = m_c.group(1).strip()
        # Fall back to first header-like line if no marker
        if not title:
            m_h = re.search(r"^####\s*\d+\.\s*(.+)$", block, re.MULTILINE)
            if m_h:
                title = m_h.group(1).strip()
        return title, location, confidence

    # Segment evidence_text per severity group and pick first finding
    def _first_finding_for(sev_label: str) -> tuple[str, str, str]:
        if not evidence_text:
            return "", "", ""
        import re

        # Find the section starting with the severity heading
        pattern = rf"###\s*{sev_label}\s*Findings(.*?)(?:\n###\s*[A-Z][a-z]+\s*Findings|\Z)"
        m = re.search(pattern, evidence_text, flags=re.DOTALL)
        if not m:
            return "", "", ""
        block = m.group(1)
        # Split by '#### N. ' blocks
        parts = re.split(r"\n####\s*\d+\.\s*", block)
        if len(parts) < 2:
            return "", "", ""
        # The first element before the split header is preamble; take next non-empty
        for p in parts[1:]:
            if p.strip():
                return _extract_top_finding_and_location(p)
        return "", "", ""

    rows = []
    for sev_display, key in [("CRITICAL", "critical"), ("HIGH", "high"), ("MEDIUM", "medium"), ("LOW", "low")]:
        count = int(severity_counts.get(key, 0) or 0)
        if count > 0:
            title, location, confidence = _first_finding_for(sev_display)
            # Truncate for table cleanliness
            if len(title) > 60:
                title = title[:57] + "..."
            if len(location) > 40:
                location = location[:37] + "..."
            rows.append((sev_display, count, title, location, confidence))

    # Build markdown table (no extra leading pipes)
    header = "| Severity | Count | Top Finding | Location | Confidence |\n"
    header += "|----------|-------|-------------|----------|------------|\n"
    table = header
    for sev, cnt, title, loc, conf in rows:
        table += f"| {sev} | {cnt} | {title or '-'} | {loc or '-'} | {conf or '-'} |\n"
    return table
