"""
Human-in-the-Loop (HITL) feedback system for Cyber-AutoAgent.

This module provides real-time intervention capabilities during agent execution,
allowing users to pause, review, correct, and guide agent actions.
"""

from .feedback_manager import FeedbackManager
from .hitl_hook_provider import HITLHookProvider

__all__ = ["FeedbackManager", "HITLHookProvider"]
