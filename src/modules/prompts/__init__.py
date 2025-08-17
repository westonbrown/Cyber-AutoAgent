#!/usr/bin/env python3
"""
Prompts module for Cyber-AutoAgent.

This module provides a centralized factory for creating and managing
all prompts used by the agent, including system prompts, report generation
prompts, and dynamic prompts for different operational modules.
"""

from .factory import (
    get_system_prompt,
    get_report_generation_prompt,
    get_report_agent_system_prompt,
    format_evidence_for_report,
    format_tools_summary,
    get_module_loader,
    ModulePromptLoader,
    load_prompt_template,
)

__all__ = [
    "get_system_prompt",
    "get_report_generation_prompt",
    "get_report_agent_system_prompt",
    "format_evidence_for_report",
    "format_tools_summary",
    "get_module_loader",
    "ModulePromptLoader",
    "load_prompt_template",
]
