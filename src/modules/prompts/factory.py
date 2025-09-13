#!/usr/bin/env python3
"""
Prompt Factory for Cyber-AutoAgent

This module constructs all prompts for the agent, including the system prompt,
report generation prompts, and module-specific prompts.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # Fallback when PyYAML is unavailable

logger = logging.getLogger(__name__)

# --- Template and Utility Functions ---


def load_prompt_template(template_name: str) -> str:
    """Load a prompt template from the templates directory.

    Returns an error string if the template is not found. Callers should provide
    a minimal fallback if needed (less is more philosophy).
    """
    try:
        template_path = Path(__file__).parent / "templates" / template_name
        if not template_path.exists():
            logger.warning("Prompt template not found: %s", template_path)
            return ""
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.exception("Failed to load prompt template '%s': %s", template_name, e)
        return ""


def _extract_domain_lens(module_prompt: str) -> Dict[str, str]:
    """Extract domain-specific guidance from module prompt (best-effort)."""
    if not module_prompt:
        return {}
    domain_lens: Dict[str, str] = {}
    if "<domain_lens>" in module_prompt and "</domain_lens>" in module_prompt:
        start_tag = module_prompt.find("<domain_lens>") + len("<domain_lens>")
        end_tag = module_prompt.find("</domain_lens>")
        lens_content = module_prompt[start_tag:end_tag].strip()
    else:
        lens_content = module_prompt
    if "DOMAIN_LENS:" in lens_content:
        lines = lens_content.split("\n")
        in_lens = False
        for line in lines:
            if "DOMAIN_LENS:" in line:
                in_lens = True
                continue
            if in_lens and line.strip():
                if line.strip().startswith("</") or (line.strip().endswith(":") and ":" not in line[:-1]):
                    break
                if ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key and value:
                            domain_lens[key] = value
    return domain_lens


# --- Memory Context Guidance (centralized) ---


def get_memory_context_guidance(
    *,
    has_memory_path: bool,
    has_existing_memories: bool,
    memory_overview: Optional[Dict[str, Any]] = None,
) -> str:
    """Return memory context guidance text used in system prompts.

    Matches expectations from tests by including specific phrases/assertions.
    """
    lines: List[str] = ["## MEMORY CONTEXT"]

    # Determine memory count if available
    total_count = 0
    if isinstance(memory_overview, dict):
        if memory_overview.get("has_memories"):
            try:
                total_count = int(memory_overview.get("total_count") or 0)
            except Exception:
                total_count = 0

    if not has_memory_path and not has_existing_memories:
        # Fresh operation guidance
        lines.extend(
            [
                "Starting fresh assessment with no previous context",
                "Do NOT check memory on fresh operations",
                "Begin with reconnaissance and target information gathering",
                'Store all findings immediately with category="finding"',
            ]
        )
    else:
        # Continuing assessment guidance
        count_str = str(total_count) if total_count else "0"
        lines.append(f"Continuing assessment with {count_str} existing memories")
        # Critical directive expected by tests
        lines.append(
            '**CRITICAL FIRST ACTION**: Load all memories with mem0_memory(action="list", user_id="cyber_agent")'
        )
        lines.append("Analyze retrieved memories before taking any actions")
        lines.append("Avoid repeating work already completed")
        lines.append("Build upon previous discoveries")

    return "\n".join(lines)


# --- Core System Prompt Builders (minimal, robust) ---


def get_system_prompt(
    target: str,
    objective: str,
    operation_id: str,
    current_step: int = 0,
    max_steps: int = 100,
    remaining_steps: Optional[int] = None,
    has_existing_memories: bool = False,
    memory_overview: Optional[Dict[str, Any]] = None,
    # Extended, centralized parameters
    provider: Optional[str] = None,
    has_memory_path: bool = False,
    tools_context: Optional[str] = None,
    output_config: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the system prompt used by the main agent (centralized).

    Produces a concise, structured prompt with memory context and environment context.
    Also appends a planning block and tools guidance when available.
    """
    if not remaining_steps:
        remaining_steps = max(0, max_steps - current_step)

    parts: List[str] = []
    parts.append("# SECURITY ASSESSMENT SYSTEM PROMPT")
    parts.append(f"Target: {target}")
    parts.append(f"Objective: {objective}")
    parts.append(f"Operation: {operation_id}")
    parts.append(f"Budget: {max_steps} steps")
    if provider:
        parts.append(f"Provider: {provider}")
        parts.append(f'model_provider: "{provider}"')

    # Memory context section
    memory_context_text = get_memory_context_guidance(
        has_memory_path=has_memory_path,
        has_existing_memories=has_existing_memories,
        memory_overview=memory_overview,
    )
    parts.append(memory_context_text)

    # Include tools context if provided
    if tools_context:
        parts.append("## ENVIRONMENTAL CONTEXT")
        parts.append(str(tools_context).strip())

    # Output directory structure
    if isinstance(output_config, dict) and output_config:
        base_dir = output_config.get("base_dir") or output_config.get("base") or "./outputs"
        target_name = output_config.get("target_name") or target
        parts.append("## OUTPUT DIRECTORY STRUCTURE")
        parts.append(f"Base directory: {base_dir}")
        parts.append(f"Target: {target_name}")
        parts.append(f"Target organization: {base_dir.rstrip('/')}/{target_name}/")
        parts.append("Evidence and logs will be stored under a unified operation path.")

    # Fresh operation hint (tests expect this phrase when fresh)
    if not has_memory_path and not has_existing_memories:
        parts.append("Begin with reconnaissance")

    # Append explicit planning and reflection block from template if available
    try:
        system_template = load_prompt_template("system_prompt.md")
        if system_template:
            # Extract the PLANNING AND REFLECTION section
            marker = "## PLANNING AND REFLECTION"
            start = system_template.find(marker)
            if start != -1:
                # Find next section header or end
                next_header_idx = system_template.find("\n## ", start + len(marker))
                planning_block = (
                    system_template[start:next_header_idx] if next_header_idx != -1 else system_template[start:]
                )
                # Replace minimal placeholders we rely on
                planning_block = (
                    planning_block.replace("{{ memory_context }}", memory_context_text)
                    .replace("{{ objective }}", str(objective))
                    .replace("{{ max_steps }}", str(max_steps))
                )
                parts.append(planning_block.strip())
    except Exception:
        # Best-effort: ignore template failures
        pass

    # Append tools guide if available
    try:
        tools_guide = load_prompt_template("tools_guide.md")
        if tools_guide:
            parts.append(tools_guide.strip())
    except Exception:
        pass

    return "\n".join(parts)


def get_report_generation_prompt(
    target: str,
    objective: str,
    evidence_text: str = "",
    tools_used: Optional[List[str]] = None,
) -> str:
    """Build the report generation prompt used by the report agent or step."""
    template = load_prompt_template("report_generation_prompt.md")
    tools_summary = "\n".join(f"- {t}" for t in (tools_used or []))
    base = (
        f"Generate a concise security assessment report for target '{target}' with objective '{objective}'.\n"
        f"Use the provided evidence verbatim where possible."
    )
    if not template:
        return base + (f"\n\nEvidence:\n{evidence_text}" if evidence_text else "")
    try:
        return (
            template.replace("{{target}}", str(target))
            .replace("{{objective}}", str(objective))
            .replace("{{evidence}}", evidence_text or "")
            .replace("{{tools_used}}", tools_summary)
        )
    except Exception:
        return base


def get_report_agent_system_prompt() -> str:
    """Minimal system prompt for the dedicated report agent."""
    template = load_prompt_template("report_agent_system_prompt.md")
    if template:
        return template
    return (
        "You are a reporting specialist. Produce a clear, structured security assessment report\n"
        "with an executive summary, key findings, and remediation recommendations."
    )


# --- Module Prompt Loader ---


class ModulePromptLoader:
    """Lightweight loader for module-specific prompts (execution/report)."""

    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = templates_dir or (Path(__file__).parent / "templates")
        # Base dir for operation plugins: modules/operation_plugins
        self.plugins_dir = (Path(__file__).parent.parent / "operation_plugins").resolve()

    def load_module_execution_prompt(self, module_name: str) -> str:
        """Load a module-specific execution prompt if available.

        Prefer module plugin prompts under operation_plugins/<module>/execution_prompt.(md|txt).
        Fallback to common filenames in prompts/templates.
        Returns empty string if not found.
        """
        # 1) Prefer operation_plugins/<module>/execution_prompt first to avoid noisy missing-template warnings
        try:
            for fname in ("execution_prompt.md", "execution_prompt.txt"):
                p = (self.plugins_dir / module_name / fname)
                if p.exists() and p.is_file():
                    return p.read_text(encoding="utf-8").strip()
        except Exception:
            # best-effort
            pass
        
        # 2) Fallback to templates directory candidates
        candidates = [
            f"{module_name}_execution_prompt.md",
            f"module_{module_name}_execution_prompt.md",
            f"{module_name}.md",
        ]
        for name in candidates:
            content = load_prompt_template(name)
            if content:
                return content
        return ""

    def load_module_report_prompt(self, module_name: str) -> str:
        """Load module-specific report prompt guidance if available.

        Looks in operation_plugins/<module>/report_prompt.txt (or .md).
        Returns empty string if none present.
        """
        try:
            candidates = [
                self.plugins_dir / module_name / "report_prompt.txt",
                self.plugins_dir / module_name / "report_prompt.md",
            ]
            for path in candidates:
                if path.exists() and path.is_file():
                    return path.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.debug("Failed to load module report prompt for '%s': %s", module_name, e)
        return ""

    def discover_module_tools(self, module_name: str) -> List[str]:
        """Discover module-specific tool files under operation_plugins.

        Returns a list of Python file paths for tools in modules/operation_plugins/<module>/tools.
        """
        results: List[str] = []
        try:
            tools_dir = self.plugins_dir / module_name / "tools"
            if tools_dir.exists() and tools_dir.is_dir():
                for py in tools_dir.glob("*.py"):
                    if py.name != "__init__.py":
                        results.append(str(py.resolve()))
        except Exception as e:
            logger.debug("discover_module_tools failed for '%s': %s", module_name, e)
        return results


def get_module_loader() -> ModulePromptLoader:
    """Return a module prompt loader instance."""
    return ModulePromptLoader()


# --- Report Generation Functions ---


def _get_current_date() -> str:
    """Get current date in report format."""
    return datetime.now().strftime("%Y-%m-%d")


def _generate_findings_table(evidence_text: str) -> str:
    """Generate a simple findings table from evidence_text (legacy).

    Note: This parser is heuristic and retained for backward compatibility.
    Prefer generate_findings_summary_table(evidence) for structured output.
    """
    if not evidence_text:
        return "No findings identified during assessment."
    findings = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    lines = evidence_text.split("\n")
    for line in lines:
        for severity in findings:
            if f"[{severity}]" in line or f"| {severity}" in line:
                content = line
                for marker in [f"[{severity}]", f"| {severity}]", f"| {severity} |"]:
                    content = content.replace(marker, "")
                content = content.strip()
                if content.startswith("]"):
                    content = content[1:].strip()
                if len(content) > 80:
                    content = content[:80] + "..."
                if content:
                    findings[severity].append(content)
                break
    table = "| Severity | Count | Key Findings |\n"
    table += "|----------|-------|--------------|\n"
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = len(findings[severity])
        if count > 0:
            key_findings = "; ".join(findings[severity][:2])
            if count > 2:
                key_findings += f" (+{count-2} more)"
            table += f"| {severity} | {count} | {key_findings} |\n"
    return table


def generate_findings_summary_table(evidence: List[Dict[str, Any]]) -> str:
    """Generate an actionable KEY FINDINGS table from structured evidence.

    Columns: Severity | Count | Canonical Finding (anchor) | Primary Location | Verified | Confidence (range)
    - Canonical Finding links to the first detailed finding within that severity section
      by constructing a markdown anchor from the detailed heading text
      (format: "#### 1. <vulnerability> - <where>")
    - Primary Location is the parsed [WHERE] of the canonical finding, or "Multiple" if diverse
    - Verified reflects the canonical finding's validation_status when available
    - Confidence shows min–max range across findings in the severity group using numeric confidences
    """
    # Helper: slugify heading text to markdown anchor (GitHub-style best effort)
    import re as _re

    def _slugify(text: str) -> str:
        s = text.lower()
        s = _re.sub(r"[^a-z0-9\-\s]", "", s)
        s = _re.sub(r"\s+", "-", s)
        s = _re.sub(r"-+", "-", s)
        return s.strip("-")

    def _parse_num_conf(val: str) -> Optional[float]:
        if not val:
            return None
        m = _re.search(r"([0-9]+(?:\.[0-9]+)?)", str(val))
        if not m:
            return None
        try:
            num = float(m.group(1))
            if 0 <= num <= 100:
                return num
        except Exception:
            return None
        return None

    # Group evidence by severity using parsed fields when available
    groups: Dict[str, List[Dict[str, Any]]] = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for item in evidence or []:
        if item.get("category") != "finding":
            continue
        sev = str(item.get("severity", "")).upper()
        if sev in groups:
            groups[sev].append(item)

    header = (
        "| Severity | Count | Canonical Finding | Primary Location | Verified | Confidence |\n"
        "|----------|-------|-------------------|------------------|----------|------------|\n"
    )

    rows: List[str] = []
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        items = groups[sev]
        if not items:
            continue
        count = len(items)
        # Canonical finding = first item within this severity section
        top = items[0]
        parsed = top.get("parsed", {}) if isinstance(top.get("parsed"), dict) else {}
        vuln = (parsed.get("vulnerability") or _safe_truncate(str(top.get("content", "")), 60)).strip()
        where = (parsed.get("where") or "").strip()
        if not where:
            # Derive primary location across the group if available
            wheres = []
            for it in items:
                p = it.get("parsed", {}) if isinstance(it.get("parsed"), dict) else {}
                w = (p.get("where") or "").strip()
                if w:
                    wheres.append(w)
            where = wheres[0] if wheres and len(set(wheres)) == 1 else ("Multiple" if wheres else "-")

        # Verified status from canonical finding
        vstat = str(top.get("validation_status") or "").strip().lower()
        verified = "Verified" if vstat == "verified" else ("Unverified" if vstat else "-")

        # Confidence range across group
        nums: List[float] = []
        for it in items:
            c = it.get("confidence") or (it.get("metadata", {}) or {}).get("confidence")
            n = _parse_num_conf(c)
            if n is not None:
                nums.append(n)
        if nums:
            cmin, cmax = min(nums), max(nums)
            if abs(cmin - cmax) < 1e-9:
                conf_str = f"{cmin:.1f}%"
            else:
                conf_str = f"{cmin:.1f}%–{cmax:.1f}%"
        else:
            conf_str = "-"

        # Build anchor link to detailed heading: "#### 1. {vuln} - {where}"
        heading_text = f"1. {vuln} - {where}" if where and where not in {"-", "Multiple"} else f"1. {vuln}"
        anchor = _slugify(heading_text)
        link_text = vuln if vuln else "-"
        canonical_link = f"[{link_text}](#{anchor})"

        rows.append(f"| {sev} | {count} | {canonical_link} | {where or '-'} | {verified} | {conf_str} |")

    return (
        header + "\n".join(rows)
        if rows
        else (
            "| Severity | Count | Canonical Finding | Primary Location | Verified | Confidence |\n"
            "|----------|-------|-------------------|------------------|----------|------------|\n"
            "| NONE | 0 | - | - | - | - |"
        )
    )


def _safe_truncate(text: str, n: int) -> str:
    text = text.strip()
    return text if len(text) <= n else text[: n - 3] + "..."


def _indent_text(text: str, spaces: int) -> str:
    """
    Indent text by specified number of spaces.

    Helper function for formatting multi-line evidence in reports.
    """
    if not text:
        return ""
    indent = " " * spaces
    return "\n".join(indent + line for line in text.split("\n"))


def format_evidence_for_report(evidence: List[Dict[str, Any]], max_items: int = 400) -> str:
    """
    Format evidence list into structured text for the report.

    Processes full evidence content including parsed components for detailed reporting.
    Normalizes severity casing and confidence display, and includes status badges when available.
    """
    if not evidence:
        return ""

    evidence_text = ""
    severity_groups = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": [], "INFO": []}

    for item in evidence[:max_items]:
        if item.get("category") == "finding":
            severity = str(item.get("severity", "INFO")).upper()
            if severity in severity_groups:
                severity_groups[severity].append(item)
            else:
                severity_groups["INFO"].append(item)
        else:
            severity_groups["INFO"].append(item)

    finding_number = 1
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        if severity_groups[severity]:
            # Use markdown heading for the section
            evidence_text += f"\n### {severity.capitalize()} Findings\n\n"
            for item in severity_groups[severity]:
                category = str(item.get("category", "unknown")).upper()
                confidence = str(item.get("confidence", "N/A"))
                status = str(item.get("validation_status") or "").strip()

                # Format the finding with parsed evidence if available
                if "parsed" in item and item["parsed"]:
                    parsed = item["parsed"]
                    vuln_title = parsed.get("vulnerability", "Finding")
                    if vuln_title:
                        evidence_text += f"#### {finding_number}. {vuln_title}\n"
                    else:
                        evidence_text += f"#### {finding_number}. Finding\n"

                    # Display raw item severity if available, otherwise use group label
                    disp_sev = item.get("severity", severity)
                    line = f"**Severity:** {disp_sev} | **Confidence:** {confidence}"
                    if status:
                        st_norm = "Verified" if status.lower() == "verified" else "Unverified"
                        line += f" | **Status:** {st_norm}"
                    evidence_text += line + "\n\n"

                    if parsed.get("where"):
                        evidence_text += f"**Location:** {parsed['where']}\n\n"

                    if parsed.get("impact"):
                        evidence_text += f"**Impact:** {parsed['impact']}\n\n"

                    if parsed.get("evidence"):
                        evidence_text += f"**Evidence:**\n```\n{parsed['evidence']}\n```\n\n"

                    if parsed.get("steps"):
                        steps = parsed["steps"]
                        # Format steps if they're inline
                        if " 1." in steps or " 2." in steps:
                            steps = steps.replace(" 1.", "\n1.")
                            steps = steps.replace(" 2.", "\n2.")
                            steps = steps.replace(" 3.", "\n3.")
                            steps = steps.replace(" 4.", "\n4.")
                            steps = steps.replace(" 5.", "\n5.")
                        evidence_text += f"**Reproduction Steps:**\n```\n{steps}\n```\n\n"

                    if parsed.get("remediation"):
                        evidence_text += f"**Remediation:** {parsed['remediation']}\n"
                else:
                    # Use full content without truncation
                    content = item.get("content", "")

                    # If content has inline markers, format them better
                    if "[VULNERABILITY]" in content and "[WHERE]" in content:
                        # Split markers onto separate lines for readability
                        formatted_content = content
                        for marker in [
                            "[VULNERABILITY]",
                            "[WHERE]",
                            "[IMPACT]",
                            "[EVIDENCE]",
                            "[STEPS]",
                            "[REMEDIATION]",
                            "[CONFIDENCE]",
                        ]:
                            formatted_content = formatted_content.replace(f" {marker}", f"\n{marker}")
                            formatted_content = formatted_content.replace(f"]{marker}", f"]\n{marker}")
                        content = formatted_content.strip()

                    if item.get("category") == "finding":
                        evidence_text += f"#### {finding_number}. Finding\n"
                        disp_sev = item.get("severity", severity)
                        line = f"**Severity:** {disp_sev} | **Confidence:** {confidence}"
                        if status:
                            st_norm = "Verified" if status.lower() == "verified" else "Unverified"
                            line += f" | **Status:** {st_norm}"
                        evidence_text += line + "\n\n"
                        evidence_text += f"**Details:**\n```\n{content}\n```"
                    else:
                        evidence_text += f"#### {finding_number}. {category}\n"
                        evidence_text += f"```\n{content}\n```"

                evidence_text += "\n"
                finding_number += 1
            evidence_text += "\n"  # Add spacing between severity groups
    return evidence_text.strip()


def format_tools_summary(tools_used: List[str] | Dict[str, int]) -> str:
    """Format tools into a readable usage summary.

    Accepts either:
    - List[str]: a list of tool names (duplicates indicate multiple uses)
    - Dict[str, int]: mapping of tool name to usage count
    """
    if not tools_used:
        return ""

    # Normalize to a dict of counts
    tools_summary: Dict[str, int] = {}
    if isinstance(tools_used, dict):
        for k, v in tools_used.items():
            try:
                count = int(v)
            except Exception:
                count = 0
            if count > 0:
                tools_summary[str(k)] = count
    else:
        for tool in tools_used:
            tool_name = str(tool).split(":")[0]
            tools_summary[tool_name] = tools_summary.get(tool_name, 0) + 1

    # Deterministic order: by descending count then name
    items = sorted(tools_summary.items(), key=lambda kv: (-kv[1], kv[0]))

    def pluralize(n: int, word: str) -> str:
        return f"{n} {word}" + ("es" if word.endswith("s") else ("s" if n != 1 else ""))

    # Use proper pluralization for "use"
    lines = []
    for name, count in items:
        unit = "use" if count == 1 else "uses"
        lines.append(f"- {name}: {count} {unit}")
    return "\n".join(lines)


def _transform_evidence_to_content(
    evidence: List[Dict[str, Any]], domain_lens: Dict[str, str], target: str, objective: str
) -> Dict[str, str]:
    """
    Return empty content - LLM generates everything from raw_evidence.
    """
    content = {
        "overview": domain_lens.get("overview", ""),
        "analysis": domain_lens.get("analysis", ""),
        "immediate": domain_lens.get("immediate", ""),
        "short_term": domain_lens.get("short_term", ""),
        "long_term": domain_lens.get("long_term", ""),
    }
    return content
