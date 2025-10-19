"""HITL feedback injection hook for modifying agent system prompt."""

import logging
from typing import TYPE_CHECKING

from strands.experimental.hooks.events import BeforeModelInvocationEvent
from strands.hooks import HookProvider, HookRegistry

if TYPE_CHECKING:
    from .feedback_manager import FeedbackManager

logger = logging.getLogger(__name__)


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

    def register_hooks(self, registry: HookRegistry):
        """Register BeforeModelInvocationEvent callback.

        Args:
            registry: Hook registry to register callback with
        """
        registry.add_callback(BeforeModelInvocationEvent, self.inject_feedback)
        logger.debug("[HITL-HOOK] Registered BeforeModelInvocationEvent callback")

    def inject_feedback(self, event: BeforeModelInvocationEvent):
        """Inject pending feedback into system prompt before model invocation.

        This method is called before each model invocation. If feedback is
        pending, it appends the formatted feedback message to the agent's
        system prompt and clears the pending feedback.

        Args:
            event: BeforeModelInvocationEvent containing agent context
        """
        feedback_message = self.feedback_manager.get_pending_feedback_message()

        if feedback_message:
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

            # Append feedback to system prompt (like prompt_optimizer does)
            event.agent.system_prompt += f"\n\n{feedback_message}"

            # Clear feedback after injection to prevent duplicate injection
            self.feedback_manager.clear_pending_feedback()

            logger.info("[HITL-HOOK] Feedback successfully injected into system prompt")
        else:
            logger.debug("[HITL-HOOK] No pending feedback to inject")
