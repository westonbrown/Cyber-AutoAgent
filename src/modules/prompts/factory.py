#!/usr/bin/env python3
"""
Prompt Factory for Cyber-AutoAgent

This module constructs all prompts for the agent, including the system prompt,
report generation prompts, and module-specific prompts.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# --- Template and Utility Functions ---


def load_prompt_template(template_name: str) -> str:
    """Load a prompt template from the templates directory."""
    try:
        template_path = Path(__file__).parent / "templates" / template_name
        if not template_path.exists():
            logger.error("Prompt template not found: %s", template_path)
            return f"ERROR: Prompt template '{template_name}' not found."
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.exception("Failed to load prompt template '%s': %s", template_name, e)
        return f"ERROR: Failed to load prompt template '{template_name}'."


def _extract_domain_lens(module_prompt: str) -> Dict[str, str]:
    """Extract domain-specific guidance from module prompt."""
    if not module_prompt:
        return {}
    domain_lens = {}
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


# --- Report Generation Functions ---


def _get_current_date() -> str:
    """Get current date in report format."""
    return datetime.now().strftime("%Y-%m-%d")


def _generate_findings_table(evidence_text: str) -> str:
    """Generate a markdown table summarizing findings by severity."""
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


def format_evidence_for_report(evidence: List[Dict[str, Any]], max_items: int = 100) -> str:
    """Format evidence list into structured text for the report."""
    if not evidence:
        return "<no_evidence>No specific evidence collected during assessment.</no_evidence>"
    evidence_text = "<evidence_collection>\n"
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
    finding_number = 1
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        if severity_groups[severity]:
            evidence_text += f"\n<{severity.lower()}_findings>\n"
            for item in severity_groups[severity]:
                category = item.get("category", "unknown").upper()
                content = item.get("content", "")[:800]
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
    """Format tools list into a summary."""
    if not tools_used:
        return "No specific tools recorded."
    tools_summary = {}
    for tool in tools_used:
        tool_name = tool.split(":")[0]
        if tool_name in tools_summary:
            tools_summary[tool_name] += 1
        else:
            tools_summary[tool_name] = 1
    return "\n".join([f"- {name}: {count} uses" for name, count in tools_summary.items()])


def _transform_evidence_to_content(
    evidence: List[Dict[str, Any]], 
    domain_lens: Dict[str, str],
    target: str,
    objective: str
) -> Dict[str, str]:
    """
    Transform evidence into report content guided by domain lens.
    
    This function bridges the semantic gap between raw evidence and report sections
    by using the domain lens as a transformation guide. It maintains the structure
    and meaning of evidence while preparing content for the report template.
    
    Args:
        evidence: List of evidence dictionaries with severity, category, content
        domain_lens: Module-specific guidance for report sections
        target: Assessment target
        objective: Assessment objective
        
    Returns:
        Dictionary with keys matching report template placeholders
    """
    # Group evidence by severity for structured analysis
    severity_groups = {"critical": [], "high": [], "medium": [], "low": [], "info": []}
    
    for item in evidence:
        severity = item.get("severity", "info").lower()
        if severity in severity_groups:
            severity_groups[severity].append(item)
    
    # Count findings for overview context
    total_findings = len(evidence)
    critical_count = len(severity_groups["critical"])
    high_count = len(severity_groups["high"])
    
    # Initialize content with domain lens defaults or evidence-based summaries
    content = {}
    
    # Overview: Combine assessment context with domain guidance
    if domain_lens.get("overview"):
        # Use domain lens overview as foundation
        content["overview"] = domain_lens["overview"]
    else:
        # Build from evidence if no domain guidance
        content["overview"] = (
            f"Security assessment of {target} identified {total_findings} findings. "
            f"Objective: {objective}. "
        )
        if critical_count > 0:
            content["overview"] += f"Critical vulnerabilities require immediate attention. "
    
    # Analysis: Structure findings with domain perspective
    if domain_lens.get("analysis"):
        # Prepend domain analysis framework
        content["analysis"] = f"{domain_lens['analysis']}\n\n"
    else:
        content["analysis"] = ""
    
    # Add evidence summary to analysis
    for severity in ["critical", "high", "medium"]:
        if severity_groups[severity]:
            content["analysis"] += f"\n### {severity.upper()} Severity Findings\n"
            # Include top findings per category
            for finding in severity_groups[severity][:3]:
                finding_content = finding.get("content", "")[:150]
                content["analysis"] += f"- {finding_content}\n"
    
    # Recommendations: Use domain lens with evidence context
    # Map domain lens keys to recommendation timeframes
    recommendation_map = {
        "immediate": (severity_groups["critical"] + severity_groups["high"][:2]),
        "short_term": (severity_groups["high"][2:] + severity_groups["medium"]),
        "long_term": (severity_groups["low"] + severity_groups["info"])
    }
    
    for timeframe, relevant_evidence in recommendation_map.items():
        if domain_lens.get(timeframe):
            # Use domain lens recommendation as base
            content[timeframe] = domain_lens[timeframe]
        elif relevant_evidence:
            # Generate basic recommendation from evidence
            severity_label = timeframe.replace("_", " ").title()
            content[timeframe] = (
                f"{severity_label} actions needed to address "
                f"{len(relevant_evidence)} identified issues"
            )
        else:
            # Default when no evidence or guidance
            content[timeframe] = ""
    
    return content


def get_report_generation_prompt(
    target: str,
    objective: str,
    operation_id: str,
    steps_executed: int,
    evidence: List[Dict[str, Any]],
    tools_used: List[str],
    module_prompt: Optional[str] = None,
) -> str:
    """Generate the full report generation prompt."""
    evidence_text = format_evidence_for_report(evidence)
    tools_summary = format_tools_summary(tools_used)
    findings_table = _generate_findings_table(evidence_text)
    critical_count = evidence_text.count("[CRITICAL]") + evidence_text.count("| CRITICAL")
    high_count = evidence_text.count("[HIGH]") + evidence_text.count("| HIGH")
    medium_count = evidence_text.count("[MEDIUM]") + evidence_text.count("| MEDIUM")
    low_count = evidence_text.count("[LOW]") + evidence_text.count("| LOW")
    
    # Extract domain lens to guide content generation
    domain_lens = _extract_domain_lens(module_prompt) if module_prompt else {}
    
    # Transform evidence into structured content using domain lens
    report_content = _transform_evidence_to_content(
        evidence=evidence,
        domain_lens=domain_lens,
        target=target,
        objective=objective
    )
    
    template = load_prompt_template("report_template.md")
    report_body = template.format(
        target=target,
        objective=objective,
        operation_id=operation_id,
        date=_get_current_date(),
        steps_executed=steps_executed,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        overview=report_content.get("overview", ""),
        findings_table=findings_table,
        analysis_details=report_content.get("analysis", ""),
        evidence_text=evidence_text,
        immediate_recommendations=report_content.get("immediate", ""),
        short_term_recommendations=report_content.get("short_term", ""),
        long_term_recommendations=report_content.get("long_term", ""),
        tools_summary=tools_summary,
        analysis_framework=domain_lens.get("framework", ""),
        module_report=(module_prompt or ""),
    )
    return report_body


def get_report_agent_system_prompt() -> str:
    """Get the system prompt for the report generation agent."""
    return load_prompt_template("report_agent_system_prompt.md")


# --- Core System Prompt and Module Loading ---


def get_system_prompt(
    target: Optional[str] = None,
    objective: Optional[str] = None,
    operation_id: Optional[str] = None,
    current_step: int = 0,
    max_steps: int = 0,
    remaining_steps: int = 0,
    tools_context: str = "",
    module_execution_prompt: Optional[str] = None,
    persona: Optional[str] = None,
    workflow: Optional[str] = None,
    tools_guide: Optional[str] = None,
) -> str:
    """Construct the system prompt.

    Supports two usage modes:
    - Template mode: pass target/objective/operation_id/steps and it will render `templates/system_prompt.md`,
      inserting `tools_guide` (from template if not provided) and optional `tools_context` and `module_execution_prompt` sections.
    - Fallback mode: if `persona` and `workflow` are provided, constructs a simple composed prompt.
    """

    # Preferred: render from template with variables
    if target is not None and objective is not None:
        base = load_prompt_template("system_prompt.md")
        # Load tools guide template if not supplied
        if tools_guide is None:
            tools_guide = load_prompt_template("tools_guide.md")

        # Simple placeholder replacement for {{ var }} occurrences
        def _subst(s: str, mapping: Dict[str, Any]) -> str:
            if not s:
                return ""
            out = s
            for k, v in mapping.items():
                out = out.replace(f"{{{{ {k} }}}}", str(v))
            return out

        rendered = _subst(
            base,
            {
                "target": target,
                "objective": objective,
                "operation_id": operation_id or "",
                "current_step": current_step,
                "max_steps": max_steps,
                "remaining_steps": remaining_steps,
                "tools_guide": tools_guide,
            },
        )

        # Append optional sections
        if tools_context:
            rendered += f"\n\n<tools_context>\n{tools_context}\n</tools_context>"
        if module_execution_prompt:
            rendered += f"\n\n<module_execution_guidance>\n{module_execution_prompt}\n</module_execution_guidance>"
        return rendered

    # Fallback mode
    if persona is not None and workflow is not None and tools_guide is not None:
        system_prompt = (
            f"# CYBER-AUTOAGENT\n\n"
            f"<persona>\n{persona}\n</persona>\n\n"
            f"<workflow>\n{workflow}\n</workflow>\n\n"
            f"<tools_guide>\n{tools_guide}\n</tools_guide>\n\n"
        )
        if tools_context:
            system_prompt += f"<tools_context>\n{tools_context}\n</tools_context>\n"
        if module_execution_prompt:
            system_prompt += f"<module_execution_guidance>\n{module_execution_prompt}\n</module_execution_guidance>"
        return system_prompt

    logger.warning("get_system_prompt called without sufficient parameters; returning empty system prompt")
    return ""


class ModulePromptLoader:
    """Loads module-specific prompts, metadata, and tools."""

    def __init__(self, modules_base_path: Optional[str] = None):
        """Initialize with path to modules directory."""
        if modules_base_path:
            self.modules_path = Path(modules_base_path)
        else:
            current_file = Path(__file__)
            potential_paths = [
                current_file.parent.parent / "operation_plugins",
                Path.cwd() / "src" / "modules" / "operation_plugins",
                Path("/app/src/modules/operation_plugins"),
                current_file.parent.parent.parent.parent / "src" / "modules" / "operation_plugins",
            ]
            for path in potential_paths:
                if path.exists():
                    self.modules_path = path
                    logger.info("Found operation_plugins at: %s", path)
                    break
            else:
                self.modules_path = current_file.parent.parent / "operation_plugins"
                logger.warning("Operation_plugins directory not found, using fallback: %s", self.modules_path)
        logger.debug("ModulePromptLoader initialized with path: %s", self.modules_path)

    def load_module_execution_prompt(self, module_name: str) -> Optional[str]:
        """Load the execution prompt for a specific module."""
        if not module_name:
            logger.warning("Empty module_name provided")
            return None
        prompt_path = self.modules_path / module_name / "execution_prompt.txt"
        try:
            if not prompt_path.exists():
                logger.debug("No execution prompt found for module '%s' at %s", module_name, prompt_path)
                return None
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                logger.info("Loaded execution prompt for module '%s' (%d chars)", module_name, len(content))
                return content
            else:
                logger.warning("Empty execution prompt file for module '%s'", module_name)
                return None
        except Exception as e:
            logger.error("Error loading execution prompt for module '%s': %s", module_name, e)
            return None

    def load_module_report_prompt(self, module_name: str) -> Optional[str]:
        """Load the report prompt for a specific module."""
        if not module_name:
            logger.warning("Empty module_name provided")
            return None
        prompt_path = self.modules_path / module_name / "report_prompt.txt"
        try:
            if not prompt_path.exists():
                logger.debug("No report prompt found for module '%s' at %s", module_name, prompt_path)
                return None
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                logger.info("Loaded report prompt for module '%s' (%d chars)", module_name, len(content))
                return content
            else:
                logger.warning("Empty report prompt file for module '%s'", module_name)
                return None
        except Exception as e:
            logger.error("Error loading report prompt for module '%s': %s", module_name, e)
            return None

    def load_module_metadata(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Load module metadata from module.yaml."""
        if not module_name:
            return None
        yaml_path = self.modules_path / module_name / "module.yaml"
        try:
            if not yaml_path.exists():
                logger.debug("No module.yaml found for module '%s'", module_name)
                return None
            with open(yaml_path, "r", encoding="utf-8") as f:
                metadata = yaml.safe_load(f)
            logger.debug("Loaded metadata for module '%s'", module_name)
            return metadata
        except Exception as e:
            logger.error("Error loading metadata for module '%s': %s", module_name, e)
            return None

    def discover_module_tools(self, module_name: str) -> List[str]:
        """Discover Python tool files in a module's tools directory."""
        if not module_name:
            return []
        tools_path = self.modules_path / module_name / "tools"
        tools = []
        try:
            if not tools_path.exists() or not tools_path.is_dir():
                logger.debug("No tools directory found for module '%s'", module_name)
                return []
            for tool_file in tools_path.glob("*.py"):
                if tool_file.name != "__init__.py":
                    tools.append(str(tool_file))
            if tools:
                logger.info(
                    f"Discovered {len(tools)} tools for module '{module_name}': {[Path(t).name for t in tools]}"
                )
            else:
                logger.debug("No tool files found for module '%s'", module_name)
            return tools
        except Exception as e:
            logger.error("Error discovering tools for module '%s': %s", module_name, e)
            return []

    def get_available_modules(self) -> List[str]:
        """Get list of available modules by scanning the modules directory."""
        modules = []
        try:
            if not self.modules_path.exists():
                logger.warning("Modules directory not found: %s", self.modules_path)
                return []
            for item in self.modules_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    modules.append(item.name)
            logger.debug("Found %d available modules: %s", len(modules), modules)
            return sorted(modules)
        except Exception as e:
            logger.error("Error scanning modules directory: %s", e)
            return []

    def validate_module(self, module_name: str) -> bool:
        """Validate if a module exists and has required structure."""
        if not module_name:
            return False
        module_path = self.modules_path / module_name
        if not module_path.exists() or not module_path.is_dir():
            logger.warning("Module directory does not exist: %s", module_path)
            return False
        has_yaml = (module_path / "module.yaml").exists()
        has_exec_prompt = (module_path / "execution_prompt.txt").exists()
        has_report_prompt = (module_path / "report_prompt.txt").exists()
        if not (has_yaml or has_exec_prompt or has_report_prompt):
            logger.warning(
                f"Module '{module_name}' missing key files (module.yaml, execution_prompt.txt, report_prompt.txt)"
            )
            return False
        logger.debug("Module '%s' validation passed", module_name)
        return True


_module_loader = None


def get_module_loader() -> ModulePromptLoader:
    """Get the global module prompt loader instance."""
    global _module_loader
    if _module_loader is None:
        _module_loader = ModulePromptLoader()
    return _module_loader
