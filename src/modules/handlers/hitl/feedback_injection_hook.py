"""HITL feedback injection hook for modifying agent system prompt."""

import logging
import sys
from typing import TYPE_CHECKING

from strands.experimental.hooks.events import BeforeModelInvocationEvent
from strands.hooks import HookProvider, HookRegistry

from .hitl_logger import log_hitl

if TYPE_CHECKING:
    from .feedback_manager import FeedbackManager

logger = logging.getLogger(__name__)


def direct_log(msg: str):
    """Write directly to stdout bypassing all logging infrastructure."""
    try:
        sys.stdout.write(f"[HITL-HOOK-DIRECT] {msg}\n")
        sys.stdout.flush()
    except Exception:
        pass  # Fail silently if stdout unavailable


class HITLFeedbackInjectionHook(HookProvider):
    """Hook that injects pending HITL feedback into agent system prompt.

    This hook uses the BeforeModelInvocationEvent to append pending user
    feedback to the agent's system prompt before each model invocation.
    This ensures feedback is processed as part of the agent's core context
    rather than as a conversation message.

    Pattern based on prompt_rebuild_hook.py which modifies
    event.agent.system_prompt directly.
    """

    def __init__(self, feedback_manager: "FeedbackManager"):
        """Initialize hook with feedback manager.

        Args:
            feedback_manager: FeedbackManager instance to check for pending feedback
        """
        self.feedback_manager = feedback_manager
        logger.info(
            "[HITL-HOOK] HITLFeedbackInjectionHook initialized for operation %s",
            feedback_manager.operation_id,
        )
        direct_log(
            f"HITLFeedbackInjectionHook initialized for operation {feedback_manager.operation_id}"
        )

    def register_hooks(self, registry: HookRegistry):
        """Register BeforeModelInvocationEvent callback.

        Args:
            registry: Hook registry to register callback with
        """
        registry.add_callback(BeforeModelInvocationEvent, self.inject_feedback)
        logger.debug("[HITL-HOOK] Registered BeforeModelInvocationEvent callback")
        direct_log("Registered BeforeModelInvocationEvent callback")

    def inject_feedback(self, event: BeforeModelInvocationEvent):
        """Inject pending feedback into system prompt before model invocation.

        This method is called before each model invocation. If feedback is
        pending, it appends the formatted feedback message to the agent's
        system prompt and clears the pending feedback.

        Args:
            event: BeforeModelInvocationEvent containing agent context
        """
        direct_log("inject_feedback() called - checking for pending feedback")
        log_hitl(
            "InjectionHook",
            "inject_feedback() triggered - BeforeModelInvocationEvent fired",
            "INFO",
        )

        original_prompt_len = len(event.agent.system_prompt) if event.agent.system_prompt else 0
        log_hitl(
            "InjectionHook",
            f"Current system prompt length: {original_prompt_len} chars",
            "DEBUG",
        )

        feedback_message = self.feedback_manager.get_pending_feedback_message()

        if feedback_message:
            direct_log(f"Found pending feedback ({len(feedback_message)} chars)")
            log_hitl(
                "InjectionHook",
                f"✓ Pending feedback found: {len(feedback_message)} chars",
                "INFO",
            )

            logger.info(
                "[HITL-HOOK] Injecting feedback into system prompt (length=%d chars)",
                len(feedback_message),
            )
            logger.debug(
                "[HITL-HOOK] Feedback preview:\n%s",
                feedback_message[:300] + "..."
                if len(feedback_message) > 300
                else feedback_message,
            )

            # Append feedback to system prompt (production mode)
            direct_log("Appending feedback to event.agent.system_prompt")
            log_hitl("InjectionHook", "Appending feedback to system prompt", "INFO")

            event.agent.system_prompt += f"\n\n{feedback_message}"
            new_prompt_len = len(event.agent.system_prompt)

            direct_log("Feedback appended successfully")
            log_hitl(
                "InjectionHook",
                f"✓ Prompt modified: {original_prompt_len} → {new_prompt_len} chars (+{new_prompt_len - original_prompt_len})",
                "INFO",
            )

            # Verify the prompt was actually set
            verification_prompt = event.agent.system_prompt
            direct_log(f"VERIFICATION: Prompt after setting = {len(verification_prompt)} chars")
            direct_log(f"VERIFICATION: First 100 chars = {verification_prompt[:100]}")
            log_hitl(
                "InjectionHook",
                f"VERIFICATION: event.agent.system_prompt = {len(verification_prompt)} chars",
                "WARNING",
                first_100_chars=verification_prompt[:100],
            )

            # Clear feedback after injection to prevent duplicate injection
            self.feedback_manager.clear_pending_feedback()
            direct_log("Cleared pending feedback after injection")

            logger.info("[HITL-HOOK] Feedback successfully injected into system prompt")
            log_hitl(
                "InjectionHook",
                "✓ Feedback injection complete - agent will receive modified prompt",
                "INFO",
            )
        else:
            direct_log("No pending feedback found")
            logger.debug("[HITL-HOOK] No pending feedback to inject")
            log_hitl(
                "InjectionHook",
                "No pending feedback - skipping injection",
                "DEBUG",
            )
