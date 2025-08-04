"""
Evaluation Module for Cyber-AutoAgent
=====================================

This module provides evaluation capabilities for the cybersecurity assessment agent,
integrating with Langfuse for observability and Ragas for metrics computation.
"""

from modules.evaluation.evaluation import CyberAgentEvaluator
from modules.evaluation.manager import EvaluationManager, TraceType, TraceInfo
from modules.evaluation.trace_parser import TraceParser, ParsedTrace, ParsedMessage, ParsedToolCall

__all__ = [
    "CyberAgentEvaluator",
    "EvaluationManager",
    "TraceType",
    "TraceInfo",
    "TraceParser",
    "ParsedTrace",
    "ParsedMessage",
    "ParsedToolCall",
]
