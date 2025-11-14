"""
Evaluation Module for Cyber-AutoAgent
=====================================

This module provides evaluation capabilities for the cybersecurity assessment agent,
integrating with Langfuse for observability and Ragas for metrics computation.
"""

from modules.evaluation.evaluation import CyberAgentEvaluator
from modules.evaluation.manager import EvaluationManager, TraceInfo, TraceType
from modules.evaluation.trace_parser import (
    ParsedMessage,
    ParsedToolCall,
    ParsedTrace,
    TraceParser,
)

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
