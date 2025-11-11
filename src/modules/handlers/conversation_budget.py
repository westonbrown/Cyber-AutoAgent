#!/usr/bin/env python3
"""Shared conversation management and prompt budget helpers."""

from __future__ import annotations

import copy
import logging
import os
from typing import Any, Optional, Callable, Sequence

from strands import Agent
from strands.agent.conversation_manager import (
    SlidingWindowConversationManager,
    SummarizingConversationManager,
)
from strands.types.content import Message
from strands.types.exceptions import ContextWindowOverflowException
from strands.hooks.events import BeforeInvocationEvent  # type: ignore

logger = logging.getLogger(__name__)


def _get_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def _get_env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default


PROMPT_TOKEN_FALLBACK_LIMIT = _get_env_int("CYBER_PROMPT_FALLBACK_TOKENS", 200000)
PROMPT_TELEMETRY_THRESHOLD = max(0.1, min(_get_env_float("CYBER_PROMPT_TELEMETRY_THRESHOLD", 0.8), 0.95))
TOOL_COMPRESS_THRESHOLD = _get_env_int("CYBER_TOOL_COMPRESS_THRESHOLD", 20000)
TOOL_COMPRESS_TRUNCATE = _get_env_int("CYBER_TOOL_COMPRESS_TRUNCATE", 2000)
PRESERVE_FIRST_DEFAULT = _get_env_int("CYBER_CONVERSATION_PRESERVE_FIRST", 1)
PRESERVE_LAST_DEFAULT = _get_env_int("CYBER_CONVERSATION_PRESERVE_LAST", 20)


class LargeToolResultMapper:
    """Compress overly large tool results before they hit the conversation."""

    def __init__(
        self,
        max_tool_chars: int = TOOL_COMPRESS_THRESHOLD,
        truncate_at: int = TOOL_COMPRESS_TRUNCATE,
        sample_limit: int = 3,
    ) -> None:
        self.max_tool_chars = max_tool_chars
        self.truncate_at = truncate_at
        self.sample_limit = sample_limit

    def __call__(self, message: Message, index: int, messages: list[Message]) -> Optional[Message]:
        if not message.get("content"):
            return message
        needs_compress = any(self._needs_compress(item) for item in message["content"])
        if not needs_compress:
            return message
        new_message = copy.deepcopy(message)
        for content in new_message.get("content", []):
            tool_result = content.get("toolResult")
            if tool_result and self._tool_length(tool_result) > self.max_tool_chars:
                content["toolResult"] = self._compress(tool_result)
        return new_message

    def _needs_compress(self, content: dict[str, Any]) -> bool:
        tool = content.get("toolResult")
        if not tool:
            return False
        return self._tool_length(tool) > self.max_tool_chars

    def _tool_length(self, tool_result: dict[str, Any]) -> int:
        length = 0
        for block in tool_result.get("content", []):
            if "text" in block:
                length += len(block["text"])
            elif "json" in block:
                length += len(str(block["json"]))
        return length

    def _compress(self, tool_result: dict[str, Any]) -> dict[str, Any]:
        original = self._tool_length(tool_result)
        compressed_blocks: list[dict[str, Any]] = []
        for block in tool_result.get("content", []):
            if "text" in block:
                text = block["text"]
                if len(text) > self.truncate_at:
                    truncated = text[: self.truncate_at] + f"... [truncated from {len(text)} chars]"
                    compressed_blocks.append({"text": truncated})
                else:
                    compressed_blocks.append(block)
            elif "json" in block:
                payload = str(block["json"])
                if len(payload) > self.truncate_at:
                    compressed_blocks.append(
                        {
                            "text": self._summarize_json(block["json"], len(payload)),
                        }
                    )
                else:
                    compressed_blocks.append(block)
            else:
                compressed_blocks.append(block)

        logger.info(
            "Compressed tool result: %d chars -> threshold %d (truncate %d)",
            original,
            self.max_tool_chars,
            self.truncate_at,
        )

        note = {
            "text": "[compressed tool result – "
            f"{original} chars -> threshold {self.max_tool_chars}]"
        }
        return {
            **tool_result,
            "content": [note, *compressed_blocks],
        }

    def _summarize_json(self, data: Any, original_len: int) -> str:
        if isinstance(data, dict):
            samples = self._sample_items(data.items())
            return (
                f"[json dict truncated from {original_len} chars, keys={len(data)}"
                f"{', sample: ' + samples if samples else ''}]"
            )
        if isinstance(data, list):
            rendered = self._sample_sequence(data)
            return (
                f"[json list truncated from {original_len} chars, len={len(data)}"
                f"{', sample: ' + rendered if rendered else ''}]"
            )
        return f"[json truncated from {original_len} chars]"

    def _sample_items(self, items: Any) -> str:
        rendered: list[str] = []
        for idx, (key, value) in enumerate(items):
            if idx >= self.sample_limit:
                break
            snippet = str(value)
            if len(snippet) > 80:
                snippet = snippet[:80] + "..."
            rendered.append(f"{key}={snippet}")
        return ", ".join(rendered)

    def _sample_sequence(self, seq: Sequence[Any]) -> str:
        rendered: list[str] = []
        for idx, value in enumerate(seq):
            if idx >= self.sample_limit:
                break
            snippet = str(value)
            if len(snippet) > 80:
                snippet = snippet[:80] + "..."
            rendered.append(snippet)
        return ", ".join(rendered)


class MappingConversationManager(SummarizingConversationManager):
    """Sliding window trimming with summarization fallback and tool compression."""

    def __init__(
        self,
        *,
        window_size: int = 30,
        summary_ratio: float = 0.3,
        preserve_recent_messages: int = 20,
        preserve_first_messages: int = PRESERVE_FIRST_DEFAULT,
        tool_result_mapper: Optional[LargeToolResultMapper] = None,
    ) -> None:
        super().__init__(
            summary_ratio=summary_ratio,
            preserve_recent_messages=preserve_recent_messages,
        )
        self._sliding = SlidingWindowConversationManager(
            window_size=window_size,
            should_truncate_results=True,
        )
        self.mapper = tool_result_mapper or LargeToolResultMapper()
        self.preserve_first = max(0, preserve_first_messages)
        self.preserve_last = max(0, preserve_recent_messages)
        self.removed_message_count = 0

    def apply_management(self, agent: Agent, **kwargs: Any) -> None:
        self._apply_mapper(agent)
        self._sliding.apply_management(agent, **kwargs)

    def reduce_context(
        self,
        agent: Agent,
        e: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        self._apply_mapper(agent)
        before_msgs = _count_agent_messages(agent)
        before_tokens = _safe_estimate_tokens(agent)
        stage = "sliding"
        try:
            self._sliding.reduce_context(agent, e, **kwargs)
        except ContextWindowOverflowException as overflow_exc:
            stage = "summarizing"
            logger.warning("Sliding window overflow; invoking summarizing fallback")
            super().reduce_context(agent, e or overflow_exc, **kwargs)
        after_msgs = _count_agent_messages(agent)
        after_tokens = _safe_estimate_tokens(agent)
        if after_msgs < before_msgs or (
            before_tokens is not None and after_tokens is not None and after_tokens < before_tokens
        ):
            removed = max(0, before_msgs - after_msgs)
            logger.info(
                "Context reduced via %s manager: messages %d->%d (%d removed), est tokens %s->%s",
                stage,
                before_msgs,
                after_msgs,
                removed,
                before_tokens if before_tokens is not None else "unknown",
                after_tokens if after_tokens is not None else "unknown",
            )
        else:
            logger.debug("Context reduction requested but no change detected for stage=%s", stage)

    def get_state(self) -> dict[str, Any]:
        state = super().get_state()
        state["sliding_state"] = self._sliding.get_state()
        state["removed_message_count"] = self.removed_message_count
        return state

    def restore_from_session(self, state: dict[str, Any]) -> Optional[list[Message]]:
        sliding_state = (state or {}).get("sliding_state")
        if sliding_state:
            self._sliding.restore_from_session(sliding_state)
        self.removed_message_count = (state or {}).get("removed_message_count", 0)
        return super().restore_from_session(state)

    def _apply_mapper(self, agent: Agent) -> None:
        if not self.mapper:
            return
        messages = getattr(agent, "messages", [])
        total = len(messages)
        if total <= self.preserve_first + self.preserve_last:
            return
        new_messages: list[Message] = []
        for idx, message in enumerate(messages):
            if idx < self.preserve_first or idx >= total - self.preserve_last:
                new_messages.append(message)
                continue
            mapped = self.mapper(message, idx, messages)
            if mapped is None:
                self.removed_message_count += 1
                continue
            new_messages.append(mapped)
        agent.messages = new_messages


def _count_agent_messages(agent: Agent) -> int:
    try:
        messages = getattr(agent, "messages", [])
        if isinstance(messages, list):
            return len(messages)
    except Exception:
        logger.debug("Unable to count agent messages", exc_info=True)
    return 0


def _safe_estimate_tokens(agent: Agent) -> Optional[int]:
    try:
        return _estimate_prompt_tokens(agent)
    except Exception:
        logger.debug("Unable to estimate prompt tokens for logging", exc_info=True)
        return None


def _get_prompt_token_limit(agent: Agent) -> Optional[int]:
    limit = getattr(agent, "_prompt_token_limit", None)
    try:
        if isinstance(limit, (int, float)) and limit > 0:
            return int(limit)
    except Exception:
        logger.debug("Invalid prompt token limit on agent", exc_info=True)
    if PROMPT_TOKEN_FALLBACK_LIMIT > 0:
        setattr(agent, "_prompt_token_limit", PROMPT_TOKEN_FALLBACK_LIMIT)
        logger.info(
            "Prompt token limit unavailable; using fallback limit of %d tokens",
            PROMPT_TOKEN_FALLBACK_LIMIT,
        )
        return PROMPT_TOKEN_FALLBACK_LIMIT
    return None


def _get_metrics_input_tokens(agent: Agent) -> Optional[int]:
    handler = getattr(agent, "callback_handler", None)
    candidate = None
    if handler is not None:
        candidate = getattr(handler, "sdk_input_tokens", None)
    if candidate is None:
        metrics = getattr(agent, "event_loop_metrics", None)
        usage = getattr(metrics, "accumulated_usage", None)
        if isinstance(usage, dict):
            candidate = usage.get("inputTokens")
    try:
        if isinstance(candidate, (int, float)):
            return int(candidate)
    except Exception:
        logger.debug("Failed to parse telemetry input tokens", exc_info=True)
    return None


def _estimate_prompt_tokens(agent: Agent) -> int:
    messages = getattr(agent, "messages", [])
    total_chars = 0
    for message in messages:
        for block in message.get("content", []):
            if isinstance(block, dict):
                if "text" in block:
                    total_chars += len(block["text"])
                elif "toolUse" in block:
                    total_chars += len(str(block["toolUse"].get("name", "")))
                    tool_input = block["toolUse"].get("input")
                    total_chars += len(str(tool_input))
    estimated_tokens = max(1, total_chars // 4)
    return estimated_tokens


def _strip_reasoning_content(agent: Agent) -> None:
    if getattr(agent, "_allow_reasoning_content", True):
        return
    messages = getattr(agent, "messages", [])
    removed_blocks = 0
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        original_len = len(content)
        content[:] = [block for block in content if not isinstance(block, dict) or "reasoningContent" not in block]
        removed_blocks += original_len - len(content)
    if removed_blocks:
        logger.warning("Removed %d reasoningContent blocks for model without reasoning support", removed_blocks)


def _ensure_prompt_within_budget(agent: Agent) -> None:
    _strip_reasoning_content(agent)
    token_limit = _get_prompt_token_limit(agent)
    if not token_limit or token_limit <= 0:
        return

    telemetry_tokens = _get_metrics_input_tokens(agent)
    telemetry_threshold = max(1, int(token_limit * PROMPT_TELEMETRY_THRESHOLD))
    reduction_reason: Optional[str] = None

    if telemetry_tokens is not None and telemetry_tokens >= telemetry_threshold:
        reduction_reason = f"telemetry tokens {telemetry_tokens}"

    estimated = _safe_estimate_tokens(agent)
    if reduction_reason is None and estimated is not None:
        if estimated >= int(token_limit * 0.85):
            reduction_reason = f"estimated prompt tokens {estimated}"

    if reduction_reason is None:
        return

    conversation_manager = getattr(agent, "conversation_manager", None)
    if conversation_manager is None:
        logger.debug("Prompt budget trigger skipped because conversation manager is missing")
        return

    before_msgs = _count_agent_messages(agent)
    before_tokens = estimated if estimated is not None else _safe_estimate_tokens(agent)
    logger.warning(
        "Prompt budget trigger (%s / limit=%d). Initiating context reduction.",
        reduction_reason,
        token_limit,
    )
    try:
        conversation_manager.reduce_context(agent)
    except ContextWindowOverflowException:
        logger.debug("Context reduction triggered summarization fallback")
    except Exception:
        logger.exception("Failed to proactively reduce context")
        return

    after_msgs = _count_agent_messages(agent)
    after_tokens = _safe_estimate_tokens(agent)
    if after_msgs < before_msgs or (
        before_tokens is not None and after_tokens is not None and after_tokens < before_tokens
    ):
        logger.info(
            "Prompt budget reduction complete: messages %d->%d, est tokens %s->%s",
            before_msgs,
            after_msgs,
            before_tokens if before_tokens is not None else "unknown",
            after_tokens if after_tokens is not None else "unknown",
        )
    else:
        logger.info("Prompt budget reduction completed but no change detected")


class PromptBudgetHook:
    """Simple BeforeInvocation hook that applies the prompt budget callback."""

    def __init__(self, ensure_budget_callback: Callable[[Any], None]) -> None:
        self._callback = ensure_budget_callback

    def register_hooks(self, registry) -> None:  # type: ignore[no-untyped-def]
        registry.add_callback(BeforeInvocationEvent, self._on_before_invocation)

    def _on_before_invocation(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._callback:
            self._callback(event.agent)


__all__ = [
    "MappingConversationManager",
    "LargeToolResultMapper",
    "PromptBudgetHook",
    "PROMPT_TOKEN_FALLBACK_LIMIT",
    "PROMPT_TELEMETRY_THRESHOLD",
    "_ensure_prompt_within_budget",
    "_estimate_prompt_tokens",
    "_strip_reasoning_content",
]
