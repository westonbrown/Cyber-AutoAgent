#!/usr/bin/env python3
"""Shared conversation management and prompt budget helpers."""

from __future__ import annotations

import copy
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional, Callable, Sequence, TypedDict, Dict

from strands import Agent
from strands.agent.conversation_manager import (
    SlidingWindowConversationManager,
    SummarizingConversationManager,
)
from strands.types.content import Message
from strands.types.exceptions import ContextWindowOverflowException
from strands.hooks import BeforeModelCallEvent, AfterModelCallEvent  # type: ignore

from modules.config.models.dev_client import get_models_client

logger = logging.getLogger(__name__)

# Module-level shared conversation manager for swarm agents
# This is necessary because swarm agents (created by strands_tools/swarm.py library)
# don't inherit conversation_manager from parent agent
_SHARED_CONVERSATION_MANAGER: Optional[Any] = None


def register_conversation_manager(manager: Any) -> None:
    """
    Register a conversation manager to be shared across all agents.

    This is needed because swarm agents created by the strands_tools library
    don't automatically inherit the parent agent's conversation_manager attribute.
    By storing a module-level reference, we can provide the same manager to all
    agents (main and swarm children) for consistent context management.

    Args:
        manager: The MappingConversationManager instance to share
    """
    global _SHARED_CONVERSATION_MANAGER
    _SHARED_CONVERSATION_MANAGER = manager
    try:
        name = type(manager).__name__ if manager is not None else "None"
    except Exception:
        name = "unknown"
    logger.info("Registered shared conversation manager: %s", name)


def clear_shared_conversation_manager() -> None:
    """Clear the shared conversation manager (test cleanup helper)."""
    global _SHARED_CONVERSATION_MANAGER
    _SHARED_CONVERSATION_MANAGER = None
    logger.debug("Cleared shared conversation manager")


def get_shared_conversation_manager() -> Optional[Any]:
    """Return the shared conversation manager if one was registered."""
    return _SHARED_CONVERSATION_MANAGER


class MessageContext(TypedDict, total=False):
    """
    Rich metadata for pruning decisions.

    Provides comprehensive information about a message to enable intelligent
    pruning strategies.
    """

    token_count: int  # Estimated tokens in this message
    has_tool_use: bool  # Contains toolUse content blocks
    has_tool_result: bool  # Contains toolResult content blocks
    tool_result_size: int  # Size of tool result content in chars
    message_index: int  # Position in conversation (0-based)
    total_messages: int  # Total messages in conversation
    message_age: int  # Steps since this message (for time-based pruning)
    is_preserved: bool  # In preservation zone (initial/recent)


@dataclass
class CompressionMetadata:
    """
    Structured metadata for compressed content.

    Provides LLM-readable indicators of what was compressed and how.
    """

    compressed: bool = False
    original_size: int = 0  # Original size in chars
    compressed_size: int = 0  # Compressed size in chars
    original_token_estimate: int = 0  # Estimated tokens before compression
    compressed_token_estimate: int = 0  # Estimated tokens after compression
    compression_ratio: float = 0.0  # compressed / original
    content_type: str = "unknown"  # "text", "json", "mixed"
    n_original_keys: Optional[int] = None  # For JSON objects
    sample_data: Optional[dict[str, Any]] = None  # Sample of original data

    def to_indicator_json(self) -> dict[str, Any]:
        """Convert to structured JSON indicator for LLM comprehension."""
        indicator = {
            "_compressed": self.compressed,
            "_original_size": self.original_size,
            "_compressed_size": self.compressed_size,
            "_compression_ratio": round(self.compression_ratio, 3),
            "_type": self.content_type,
        }
        if self.n_original_keys is not None:
            indicator["_n_original_keys"] = self.n_original_keys
        if self.sample_data:
            indicator.update(self.sample_data)
        return indicator

    def to_indicator_text(self) -> str:
        """Convert to human-readable text indicator."""
        ratio_pct = int(self.compression_ratio * 100)
        text = f"[Compressed: {self.original_size} → {self.compressed_size} chars ({ratio_pct}%)"
        if self.n_original_keys is not None:
            text += f", {self.n_original_keys} keys"
        text += f", type: {self.content_type}]"
        return text


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
PROMPT_TELEMETRY_THRESHOLD = max(
    0.1, min(_get_env_float("CYBER_PROMPT_TELEMETRY_THRESHOLD", 0.8), 0.95)
)
PROMPT_CACHE_RELAX = max(0.0, min(_get_env_float("CYBER_PROMPT_CACHE_RELAX", 0.1), 0.3))
NO_REDUCTION_WARNING_RATIO = 0.8
# Compression threshold aligned with Strands SDK (185K chars ≈ 50K tokens)
TOOL_COMPRESS_THRESHOLD = _get_env_int("CYBER_TOOL_COMPRESS_THRESHOLD", 185000)
TOOL_COMPRESS_TRUNCATE = _get_env_int("CYBER_TOOL_COMPRESS_TRUNCATE", 18500)
PRESERVE_FIRST_DEFAULT = _get_env_int("CYBER_CONVERSATION_PRESERVE_FIRST", 1)
PRESERVE_LAST_DEFAULT = _get_env_int("CYBER_CONVERSATION_PRESERVE_LAST", 12)
_MAX_REDUCTION_HISTORY = 5
_NO_REDUCTION_ATTR = "_prompt_budget_warned_no_reduction"


def _record_context_reduction_event(
    agent: Agent,
    *,
    stage: str,
    reason: Optional[str],
    before_msgs: int,
    after_msgs: int,
    before_tokens: Optional[int],
    after_tokens: Optional[int],
) -> None:
    """Persist structured reduction metadata on the agent for diagnostics/tests."""
    payload = {
        "stage": stage,
        "reason": reason,
        "before_messages": before_msgs,
        "after_messages": after_msgs,
        "before_tokens": before_tokens,
        "after_tokens": after_tokens,
        "removed_messages": max(0, before_msgs - after_msgs),
    }
    history = getattr(agent, "_context_reduction_events", [])
    if not isinstance(history, list):
        history = []
    history.append(payload)
    if len(history) > _MAX_REDUCTION_HISTORY:
        history = history[-_MAX_REDUCTION_HISTORY:]
    setattr(agent, "_context_reduction_events", history)
    if hasattr(agent, _NO_REDUCTION_ATTR):
        try:
            delattr(agent, _NO_REDUCTION_ATTR)
        except Exception:
            setattr(agent, _NO_REDUCTION_ATTR, False)


class LargeToolResultMapper:
    """
    Compress overly large tool results before they hit the conversation.

    Uses structured compression indicators and rich message context for intelligent
    pruning decisions.
    """

    def __init__(
        self,
        max_tool_chars: int = TOOL_COMPRESS_THRESHOLD,
        truncate_at: int = TOOL_COMPRESS_TRUNCATE,
        sample_limit: int = 3,
    ) -> None:
        self.max_tool_chars = max_tool_chars
        self.truncate_at = truncate_at
        self.sample_limit = sample_limit
        # Cache for JSON string lengths to avoid redundant serialization
        # Key format: (message_index, block_index) tuple to prevent collisions
        self._json_cache: dict[tuple[int, int], tuple[str, int]] = {}

    def _create_message_context(
        self, message: Message, index: int, messages: list[Message]
    ) -> MessageContext:
        """
        Create rich metadata context for the message.

        Provides comprehensive information for intelligent pruning decisions.
        """
        context: MessageContext = {
            "message_index": index,
            "total_messages": len(messages),
            "has_tool_use": False,
            "has_tool_result": False,
            "tool_result_size": 0,
            "token_count": 0,
            "is_preserved": False,
        }

        # Analyze content blocks
        for block in message.get("content", []):
            if isinstance(block, dict):
                if "toolUse" in block:
                    context["has_tool_use"] = True

                if "toolResult" in block:
                    context["has_tool_result"] = True
                    tool_result = block["toolResult"]
                    size = self._tool_length(tool_result, index)
                    context["tool_result_size"] = max(context["tool_result_size"], size)

        # Estimate token count for this message
        context["token_count"] = self._estimate_message_tokens(message)

        return context

    def _estimate_message_tokens(self, message: Message) -> int:
        """Quick token estimation for a single message."""
        total_chars = len(message.get("role", "")) * 2

        for block in message.get("content", []):
            if not isinstance(block, dict):
                continue
            if "text" in block:
                total_chars += len(block["text"])
            elif "toolUse" in block:
                total_chars += len(str(block["toolUse"]))
            elif "toolResult" in block:
                total_chars += self._tool_length(block["toolResult"], 0)

        return max(1, int(total_chars / 3.7))

    def __call__(
        self, message: Message, index: int, messages: list[Message]
    ) -> Optional[Message]:
        if not message.get("content"):
            return message

        # Single pass: identify content blocks that need compression
        content_blocks = message.get("content", [])
        indices_to_compress: list[int] = []

        for idx, content_block in enumerate(content_blocks):
            tool_result = content_block.get("toolResult")
            if tool_result:
                tool_length = self._tool_length(tool_result, idx)
                if tool_length > self.max_tool_chars:
                    logger.debug(
                        "LAYER 2 COMPRESSION: Tool result at message %d block %d exceeds threshold "
                        "(length=%d, threshold=%d)",
                        index,
                        idx,
                        tool_length,
                        self.max_tool_chars,
                    )
                    indices_to_compress.append(idx)

        if not indices_to_compress:
            return message

        logger.info(
            "LAYER 2 COMPRESSION: Compressing %d tool result(s) in message %d",
            len(indices_to_compress),
            index,
        )

        # Deep copy message to prevent aliasing bugs (Strands pattern)
        # Shallow copy would share nested dicts/lists with original message
        new_message: Message = copy.deepcopy(message)
        new_content: list[dict[str, Any]] = []

        # Process each content block
        for idx, content_block in enumerate(content_blocks):
            if idx not in indices_to_compress:
                # No compression needed, keep as-is
                new_content.append(content_block)
            else:
                # Compress this content block
                tool_result = content_block.get("toolResult")
                if tool_result:
                    # Shallow copy the content block, replace only toolResult
                    new_content.append(
                        {
                            **content_block,
                            "toolResult": self._compress(tool_result, idx),
                        }
                    )
                else:
                    new_content.append(content_block)

        new_message["content"] = new_content
        return new_message

    def _tool_length(self, tool_result: dict[str, Any], cache_key: int = 0) -> int:
        """Calculate tool result length with JSON caching."""
        length = 0
        for block_idx, block in enumerate(tool_result.get("content", [])):
            if "text" in block:
                length += len(block["text"])
            elif "json" in block:
                # Use tuple-based cache key to prevent collisions
                json_cache_key = (cache_key, block_idx)
                if json_cache_key in self._json_cache:
                    _, cached_len = self._json_cache[json_cache_key]
                    length += cached_len
                else:
                    json_str = str(block["json"])
                    json_len = len(json_str)
                    # Cache for potential reuse in _compress
                    self._json_cache[json_cache_key] = (json_str, json_len)
                    length += json_len

                    # Cleanup cache if it gets too large
                    if len(self._json_cache) > 100:
                        self._json_cache.clear()

        return length

    def _compress(
        self, tool_result: dict[str, Any], cache_key: int = 0
    ) -> dict[str, Any]:
        """
        Compress tool result with structured metadata indicators.

        Uses both text and JSON indicators for better LLM comprehension
        of what was compressed.
        """
        original_size = self._tool_length(tool_result, cache_key)
        compressed_blocks: list[dict[str, Any]] = []
        json_original_keys = 0
        json_sample: dict[str, Any] = {}
        content_types: list[str] = []

        for block_idx, block in enumerate(tool_result.get("content", [])):
            if "text" in block:
                content_types.append("text")
                text = block["text"]
                if len(text) > self.truncate_at:
                    truncated = (
                        text[: self.truncate_at]
                        + f"... [truncated from {len(text)} chars]"
                    )
                    compressed_blocks.append({"text": truncated})
                else:
                    compressed_blocks.append(block)

            elif "json" in block:
                content_types.append("json")
                json_data = block["json"]

                # Try to use cached JSON string (tuple-based key)
                json_cache_key = (cache_key, block_idx)
                if json_cache_key in self._json_cache:
                    payload, payload_len = self._json_cache[json_cache_key]
                else:
                    payload = str(json_data)
                    payload_len = len(payload)

                if payload_len > self.truncate_at:
                    # Create structured compression metadata
                    if isinstance(json_data, dict):
                        json_original_keys = len(json_data)
                        # Sample first few keys with size check (Strands pattern)
                        sample_items = list(json_data.items())[: self.sample_limit]
                        json_sample = {
                            k: (str(v)[:100] + "..." if len(str(v)) > 100 else v)
                            for k, v in sample_items
                        }

                    compressed_str = str(json_sample) if json_sample else ""
                    metadata = CompressionMetadata(
                        compressed=True,
                        original_size=payload_len,
                        compressed_size=len(compressed_str),
                        original_token_estimate=payload_len // 4,
                        compressed_token_estimate=len(compressed_str) // 4,
                        compression_ratio=len(compressed_str) / payload_len
                        if payload_len > 0
                        else 0,
                        content_type="json",
                        n_original_keys=json_original_keys
                        if json_original_keys > 0
                        else None,
                        sample_data=json_sample if json_sample else None,
                    )

                    # Add text indicator first (backward compatibility)
                    compressed_blocks.append({"text": metadata.to_indicator_text()})

                    # Add structured JSON indicator for LLM comprehension
                    compressed_blocks.append({"json": metadata.to_indicator_json()})
                else:
                    compressed_blocks.append(block)

            else:
                compressed_blocks.append(block)

        # Calculate final compressed size
        compressed_size = sum(
            len(str(b.get("text", "") or b.get("json", ""))) for b in compressed_blocks
        )

        # Determine overall content type
        content_type = (
            "mixed"
            if len(set(content_types)) > 1
            else (content_types[0] if content_types else "unknown")
        )

        logger.info(
            "Compressed tool result: %d → %d chars (%.1f%% reduction, type=%s, threshold=%d)",
            original_size,
            compressed_size,
            100 * (1 - compressed_size / original_size) if original_size > 0 else 0,
            content_type,
            self.max_tool_chars,
        )

        # Add summary note at the beginning
        note = {
            "text": f"[compressed tool result – {original_size} chars → threshold {self.max_tool_chars}]"
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
        preserve_recent_messages: int = PRESERVE_LAST_DEFAULT,
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
        # Use estimation to measure reduction impact (not telemetry - see docstring)
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
        changed = after_msgs < before_msgs or (
            before_tokens is not None
            and after_tokens is not None
            and after_tokens < before_tokens
        )
        if changed:
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
            logger.debug(
                "Context reduction requested but no change detected for stage=%s", stage
            )

        reason = getattr(agent, "_pending_reduction_reason", None)
        if hasattr(agent, "_pending_reduction_reason"):
            delattr(agent, "_pending_reduction_reason")
        _record_context_reduction_event(
            agent,
            stage=stage,
            reason=reason,
            before_msgs=before_msgs,
            after_msgs=after_msgs,
            before_tokens=before_tokens,
            after_tokens=after_tokens,
        )

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
        """Apply tool result compression to messages in prunable range."""
        if not self.mapper:
            logger.debug("LAYER 2 COMPRESSION: Mapper not configured, skipping")
            return

        messages = getattr(agent, "messages", [])
        total = len(messages)

        logger.debug(
            "LAYER 2 COMPRESSION: Checking messages for compression (total=%d, threshold=%d chars)",
            total,
            self.mapper.max_tool_chars,
        )

        # Skip pruning quietly for very small conversations (common for swarm agents)
        if total < 3:
            logger.debug(
                "Skipping pruning for small conversation: %d messages (agent=%s)",
                total,
                getattr(agent, "name", "unknown"),
            )
            return

        # Validate preservation ranges don't overlap entire message list
        if self.preserve_first + self.preserve_last >= total:
            # Downgrade to DEBUG for small conversations to reduce noise
            log_level = logger.debug if total < 5 else logger.warning
            log_level(
                "Cannot prune: preservation ranges (%d first + %d last) cover all %d messages. "
                "Consider reducing CYBER_CONVERSATION_PRESERVE_LAST (currently %d). "
                "Skipping mapper.",
                self.preserve_first,
                self.preserve_last,
                total,
                self.preserve_last,
            )
            return

        # Calculate prunable range explicitly
        start_prune = self.preserve_first
        end_prune = total - self.preserve_last
        prunable_count = end_prune - start_prune

        # Sanity check for valid range
        if start_prune >= end_prune:
            logger.warning(
                "Invalid prunable range: start=%d, end=%d (total=%d). Skipping mapper.",
                start_prune,
                end_prune,
                total,
            )
            return

        logger.debug(
            "LAYER 2 COMPRESSION: Prunable range messages %d-%d (%d prunable out of %d total)",
            start_prune,
            end_prune,
            prunable_count,
            total,
        )

        compressions = 0
        new_messages: list[Message] = []
        for idx, message in enumerate(messages):
            if idx < start_prune or idx >= end_prune:
                # In preservation zone (initial or recent messages)
                new_messages.append(message)
            else:
                # In prunable zone - apply compression
                before_compression = message
                mapped = self.mapper(message, idx, messages)
                if mapped is None:
                    self.removed_message_count += 1
                elif mapped != before_compression:
                    compressions += 1
                    new_messages.append(mapped)
                else:
                    new_messages.append(mapped)

        agent.messages = new_messages

        if compressions > 0:
            logger.info(
                "LAYER 2 COMPRESSION: Applied compression to %d message(s) in prunable range",
                compressions,
            )
        else:
            logger.debug("LAYER 2 COMPRESSION: No messages required compression")


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
        messages = getattr(agent, "messages", None)
        if messages is None:
            logger.warning(
                "TOKEN ESTIMATION FAILED: agent.messages is None (agent=%s)",
                getattr(agent, "name", "unknown"),
            )
            return None

        if not isinstance(messages, list):
            logger.warning(
                "TOKEN ESTIMATION FAILED: agent.messages is not a list (type=%s, agent=%s)",
                type(messages).__name__,
                getattr(agent, "name", "unknown"),
            )
            return None

        if len(messages) == 0:
            logger.info(
                "TOKEN ESTIMATION: agent.messages is empty, returning 0 tokens (agent=%s)",
                getattr(agent, "name", "unknown"),
            )
            return 0

        estimated = _estimate_prompt_tokens(agent)
        logger.debug(
            "TOKEN ESTIMATION: Estimated %d tokens from %d messages (agent=%s)",
            estimated,
            len(messages),
            getattr(agent, "name", "unknown"),
        )
        return estimated
    except Exception as e:
        logger.error(
            "TOKEN ESTIMATION ERROR: Exception during estimation (agent=%s, error=%s)",
            getattr(agent, "name", "unknown"),
            str(e),
            exc_info=True,
        )
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
    """
    Get per-prompt input tokens from telemetry.

    Supports two sources:
    - SDK EventLoopMetrics.accumulated_usage['inputTokens'] with delta tracking
    - Fallback test/legacy hook: agent.callback_handler.sdk_input_tokens (absolute per-turn)

    Returns per-prompt input token count, or None if unavailable.
    """
    # Primary: SDK metrics with delta tracking
    metrics = getattr(agent, "event_loop_metrics", None)
    if metrics is not None and hasattr(metrics, "accumulated_usage"):
        accumulated = metrics.accumulated_usage
        if isinstance(accumulated, dict):
            current_total = accumulated.get("inputTokens", 0)
            if current_total > 0:
                previous_total = getattr(agent, "_metrics_previous_input_tokens", 0)
                delta = current_total - previous_total
                if delta < 0:
                    logger.warning(
                        "SDK metrics decreased: current=%d, previous=%d. Resetting delta tracking.",
                        current_total,
                        previous_total,
                    )
                    setattr(agent, "_metrics_previous_input_tokens", current_total)
                    return current_total
                setattr(agent, "_metrics_previous_input_tokens", current_total)
                if delta > 0:
                    return delta
    # Fallback: test/legacy callback handler injection (absolute per-turn)
    try:
        cb = getattr(agent, "callback_handler", None)
        if cb is not None and hasattr(cb, "sdk_input_tokens"):
            value = getattr(cb, "sdk_input_tokens")
            if isinstance(value, (int, float)) and int(value) > 0:
                return int(value)
    except Exception:
        pass
    return None


# Module-level cache for char/token ratios to avoid repeated lookups
_RATIO_CACHE: Dict[str, float] = {}


def _get_char_to_token_ratio_dynamic(model_id: str) -> float:
    """Get char/token ratio using models.dev provider detection.

    Different providers use different tokenizers with varying compression:
    - Claude (Anthropic): ~3.7 chars/token (aggressive)
    - GPT (OpenAI): ~4.0 chars/token (balanced)
    - Kimi (Moonshot): ~3.8 chars/token (between)
    - Gemini (Google): ~4.2 chars/token (conservative)

    Args:
        model_id: Model identifier (e.g., "azure/gpt-5", "bedrock/...")

    Returns:
        Character-to-token ratio for estimation
    """
    if not model_id:
        return 3.7  # Conservative default (slight overestimation)

    # Check cache first
    if model_id in _RATIO_CACHE:
        return _RATIO_CACHE[model_id]

    # Compute ratio
    ratio = 3.7  # Default
    try:
        client = get_models_client()
        info = client.get_model_info(model_id)

        if info:
            provider = info.provider.lower()

            # Provider-specific ratios based on tokenizer characteristics
            if "anthropic" in provider or (
                "bedrock" in provider and "claude" in model_id.lower()
            ):
                ratio = 3.7  # Claude tokenizer
            elif "google" in provider or "gemini" in provider or "vertex" in provider:
                ratio = 4.2  # Gemini tokenizer (SentencePiece)
            elif "moonshot" in provider or "moonshotai" in provider:
                ratio = 3.8  # Kimi tokenizer
            elif "openai" in provider or "azure" in provider:
                # Check if it's a GPT model
                model_lower = model_id.lower()
                if any(
                    gpt in model_lower for gpt in ["gpt-4", "gpt-5", "gpt4", "gpt5"]
                ):
                    ratio = 4.0  # GPT tokenizer
    except Exception as e:
        logger.debug(
            "models.dev lookup failed for ratio: model=%s, error=%s", model_id, e
        )

    # Cache and return
    _RATIO_CACHE[model_id] = ratio
    return ratio


def _estimate_prompt_tokens(agent: Agent) -> int:
    """
    Estimate prompt tokens with model-aware character-to-token ratio.

    Purpose: Used for measuring reduction impact (how much was reduced?)

    Provides before/after snapshots to measure reduction effectiveness.
    SDK telemetry cannot be used here because it provides cumulative totals
    that don't reflect intermediate reduction impact within a single operation.

    Includes text, toolUse, toolResult, image, and document content.
    Uses dynamic character-to-token ratio based on model provider.

    Note: We intentionally do NOT add extra weight for roles here to keep
    estimation deterministic and aligned with tests.
    """
    messages = getattr(agent, "messages", [])
    total_chars = 0

    for message in messages:
        for block in message.get("content", []):
            if not isinstance(block, dict):
                continue

            if "text" in block:
                total_chars += len(block["text"])

            elif "toolUse" in block:
                tool_use = block["toolUse"]
                # Include tool name and input roughly proportional to their length
                total_chars += len(str(tool_use.get("name", "")))
                tool_input = tool_use.get("input", {})
                total_chars += len(str(tool_input))

            elif "toolResult" in block:
                tool_result = block["toolResult"]
                # Status and metadata
                total_chars += len(str(tool_result.get("status", "")))
                total_chars += len(str(tool_result.get("toolUseId", "")))
                # Result content blocks
                for result_content in tool_result.get("content", []):
                    if "text" in result_content:
                        total_chars += len(result_content["text"])
                    elif "json" in result_content:
                        total_chars += len(str(result_content["json"]))
                    elif "document" in result_content:
                        doc = result_content["document"]
                        total_chars += len(doc.get("name", ""))
                        total_chars += 400  # conservative fixed overhead
                    elif "image" in result_content:
                        total_chars += 600  # conservative fixed overhead

            elif "image" in block:
                total_chars += 600

            elif "document" in block:
                doc = block["document"]
                total_chars += len(doc.get("name", ""))
                total_chars += 400

    # Get model-appropriate ratio dynamically from models.dev
    model_id = getattr(agent, "model", "")
    ratio = _get_char_to_token_ratio_dynamic(model_id)
    estimated_tokens = max(1, int(total_chars / ratio))

    logger.debug(
        "TOKEN ESTIMATION: %d chars / %.1f ratio = %d tokens (model=%s)",
        total_chars,
        ratio,
        estimated_tokens,
        model_id,
    )

    return estimated_tokens


def _strip_reasoning_content(agent: Agent) -> None:
    # Check agent._allow_reasoning_content attribute (set by _supports_reasoning_model())
    # True: Keep reasoning blocks (reasoning-capable models)
    # False: Strip reasoning blocks (non-reasoning models)
    if getattr(agent, "_allow_reasoning_content", True):
        return

    messages = getattr(agent, "messages", [])
    removed_blocks = 0
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        original_len = len(content)
        content[:] = [
            block
            for block in content
            if not isinstance(block, dict) or "reasoningContent" not in block
        ]
        removed_blocks += original_len - len(content)
    if removed_blocks:
        logger.warning(
            "Removed %d reasoningContent blocks for model without reasoning support",
            removed_blocks,
        )


def _ensure_prompt_within_budget(agent: Agent) -> None:
    logger.info("BUDGET CHECK: Called for agent=%s", getattr(agent, "name", "unknown"))
    _strip_reasoning_content(agent)
    token_limit = _get_prompt_token_limit(agent)
    if not token_limit or token_limit <= 0:
        logger.info("BUDGET CHECK: Skipped - no token limit (limit=%s)", token_limit)
        return

    fallback_limit = (
        PROMPT_TOKEN_FALLBACK_LIMIT if PROMPT_TOKEN_FALLBACK_LIMIT > 0 else None
    )
    effective_limit = token_limit or fallback_limit

    # Use estimation ONLY for threshold checking (measures current context size)
    # Telemetry provides cumulative totals which don't decrease after reductions
    current_tokens = _safe_estimate_tokens(agent)

    # Get telemetry for diagnostics only (not for threshold checks)
    telemetry_tokens = _get_metrics_input_tokens(agent)
    if telemetry_tokens is not None and current_tokens is not None:
        logger.debug(
            "Token tracking: context_estimated=%d, telemetry_per_turn=%d",
            current_tokens,
            telemetry_tokens,
        )

    if current_tokens is None:
        # Cannot check budget without current context size estimation
        logger.warning(
            "BUDGET CHECK FAILED: Token estimation returned None for agent=%s. "
            "Cannot perform budget enforcement without token count. "
            "This may indicate empty messages or estimation error.",
            getattr(agent, "name", "unknown"),
        )

        # Try to use telemetry as fallback
        if telemetry_tokens is not None and telemetry_tokens > 0:
            logger.info(
                "BUDGET CHECK FALLBACK: Using telemetry tokens (%d) as proxy for context size",
                telemetry_tokens,
            )
            current_tokens = telemetry_tokens
        else:
            logger.error(
                "BUDGET CHECK ABORT: No estimation and no telemetry available. "
                "Cannot enforce budget. Agent will run unbounded."
            )
            return

    # Calculate threshold for proactive reduction
    limit_for_threshold = effective_limit or token_limit or fallback_limit
    if not limit_for_threshold:
        return

    # Respect a prompt-cache hint to avoid premature reductions when provider caching is enabled
    cache_hint = False
    try:
        cache_hint = bool(getattr(agent, "_prompt_cache_hit", False))
        if not cache_hint:
            cache_hint = os.getenv("CYBER_PROMPT_CACHE_HINT", "").lower() == "true"
    except Exception:
        cache_hint = False

    threshold_ratio = PROMPT_TELEMETRY_THRESHOLD + (
        PROMPT_CACHE_RELAX if cache_hint else 0.0
    )
    threshold_ratio = min(threshold_ratio, 0.98)
    threshold = int(limit_for_threshold * threshold_ratio)
    reduction_reason: Optional[str] = None

    # Check if we've exceeded threshold using current context size (estimation only)
    # Do NOT use telemetry - it reflects cumulative usage, not current context
    if current_tokens >= threshold:
        reduction_reason = f"context size {current_tokens}"
        logger.warning(
            "THRESHOLD EXCEEDED: context=%d, threshold=%d (%.1f%%), limit=%d",
            current_tokens,
            threshold,
            (current_tokens / limit_for_threshold * 100),
            limit_for_threshold,
        )

    # Warning system: alert if near capacity but no reductions yet
    reduction_history = getattr(agent, "_context_reduction_events", [])
    warn_threshold = int(limit_for_threshold * NO_REDUCTION_WARNING_RATIO)

    if (
        current_tokens >= warn_threshold
        and not reduction_history
        and not getattr(agent, _NO_REDUCTION_ATTR, False)
    ):
        logger.warning(
            "Prompt budget near capacity (~%s tokens of %s) but no context reductions recorded yet. "
            "Verify that MappingConversationManager.reduce_context is being called.",
            current_tokens,
            limit_for_threshold,
        )
        setattr(agent, _NO_REDUCTION_ATTR, True)
    elif current_tokens < warn_threshold:
        # Reset warning flag when back under threshold
        if hasattr(agent, _NO_REDUCTION_ATTR):
            try:
                delattr(agent, _NO_REDUCTION_ATTR)
            except Exception:
                setattr(agent, _NO_REDUCTION_ATTR, False)

    if reduction_reason is None:
        return

    # Try agent's conversation_manager first, then shared singleton (for swarm agents)
    conversation_manager = getattr(agent, "conversation_manager", None)
    if conversation_manager is None:
        conversation_manager = _SHARED_CONVERSATION_MANAGER
        if conversation_manager is None:
            logger.warning(
                "Prompt budget trigger skipped: no conversation manager available "
                "(agent=%s, tokens=%d, threshold=%d). "
                "Ensure register_conversation_manager() was called during agent creation.",
                getattr(agent, "name", "unknown"),
                current_tokens,
                threshold,
            )
            return
        logger.debug(
            "Using shared conversation manager for agent=%s (swarm agent)",
            getattr(agent, "name", "unknown"),
        )

    # Track escalation state on the agent to avoid infinite loops across turns
    escalation_count = int(getattr(agent, "_prompt_budget_escalations", 0))

    before_msgs = _count_agent_messages(agent)
    # Use estimation to measure reduction impact (not telemetry - see _estimate_prompt_tokens docstring)
    before_tokens = _safe_estimate_tokens(agent)
    logger.warning(
        "Prompt budget trigger (%s / limit=%d). Initiating context reduction (escalation=%d).",
        reduction_reason,
        token_limit,
        escalation_count,
    )
    setattr(agent, "_pending_reduction_reason", reduction_reason)

    # Always attempt at least one reduction
    def _attempt_reduce() -> tuple[int, Optional[int]]:
        conversation_manager.reduce_context(agent)
        return _count_agent_messages(agent), _safe_estimate_tokens(agent)

    try:
        after_msgs, after_tokens = _attempt_reduce()
    except ContextWindowOverflowException:
        logger.debug("Context reduction triggered summarization fallback")
        after_msgs, after_tokens = (
            _count_agent_messages(agent),
            _safe_estimate_tokens(agent),
        )
    except Exception:
        logger.exception("Failed to proactively reduce context")
        if hasattr(agent, "_pending_reduction_reason"):
            delattr(agent, "_pending_reduction_reason")
        return

    # Escalate if still near/over threshold; perform up to 2 additional aggressive passes
    # with time budget to prevent hangs
    passes = 0
    escalation_start = time.time()
    MAX_ESCALATION_TIME = 30.0  # 30 seconds maximum for all escalation passes

    while (
        passes < 2
        and after_tokens is not None
        and limit_for_threshold
        and after_tokens >= int(limit_for_threshold * 0.9)
        and (time.time() - escalation_start) < MAX_ESCALATION_TIME
    ):
        passes += 1
        pass_start = time.time()
        setattr(agent, "_pending_reduction_reason", f"escalation pass {passes}")
        logger.warning(
            "Prompt still near/over limit after reduction (est ~%s / limit %s). Escalating (pass %d).",
            after_tokens,
            limit_for_threshold,
            passes,
        )
        try:
            after_msgs, after_tokens = _attempt_reduce()
            pass_duration = time.time() - pass_start
            logger.debug("Escalation pass %d completed in %.2fs", passes, pass_duration)
        except Exception:
            logger.debug("Escalation reduction pass failed", exc_info=True)
            break

    # Check if we hit time limit
    total_escalation_time = time.time() - escalation_start
    if total_escalation_time >= MAX_ESCALATION_TIME and after_tokens >= int(
        limit_for_threshold * 0.9
    ):
        logger.warning(
            "Escalation terminated after %.2fs (time budget exceeded). "
            "Final tokens: %s / limit %s",
            total_escalation_time,
            after_tokens,
            limit_for_threshold,
        )

    # Update escalation counter for next turn if still large
    if (
        after_tokens is not None
        and limit_for_threshold
        and after_tokens >= int(limit_for_threshold * 0.9)
    ):
        setattr(agent, "_prompt_budget_escalations", escalation_count + 1)
    else:
        if hasattr(agent, "_prompt_budget_escalations"):
            try:
                delattr(agent, "_prompt_budget_escalations")
            except Exception:
                setattr(agent, "_prompt_budget_escalations", 0)

    if after_msgs < before_msgs or (
        before_tokens is not None
        and after_tokens is not None
        and after_tokens < before_tokens
    ):
        logger.info(
            "Prompt budget reduction complete: messages %d->%d, est tokens %s->%s (passes=%d)",
            before_msgs,
            after_msgs,
            before_tokens if before_tokens is not None else "unknown",
            after_tokens if after_tokens is not None else "unknown",
            passes,
        )
    else:
        logger.info("Prompt budget reduction completed but no change detected")
        history = getattr(agent, "_context_reduction_events", [])
        if not history:
            logger.warning(
                "Prompt budget attempted reduction but conversation manager reported no changes. "
                "Current est tokens ~%s / limit %s. Manual trimming may be required.",
                after_tokens if after_tokens is not None else "unknown",
                limit_for_threshold,
            )


class PromptBudgetHook:
    """Hook provider that enforces prompt budget around model calls.

    Registers to production SDK events to ensure provider-agnostic behavior:
    - BeforeModelCallEvent: run budget check and enforce reductions if near/over threshold
    - AfterModelCallEvent: optional diagnostics (telemetry deltas)
    """

    def __init__(self, ensure_budget_callback: Callable[[Any], None]) -> None:
        self._callback = ensure_budget_callback

    def register_hooks(self, registry) -> None:  # type: ignore[no-untyped-def]
        logger.info(
            "HOOK REGISTRATION: Registering PromptBudgetHook callbacks for BeforeModelCallEvent and AfterModelCallEvent"
        )
        registry.add_callback(BeforeModelCallEvent, self._on_before_model_call)
        registry.add_callback(AfterModelCallEvent, self._on_after_model_call)
        logger.info(
            "HOOK REGISTRATION: PromptBudgetHook callbacks registered successfully"
        )

    def _on_before_model_call(self, event) -> None:  # type: ignore[no-untyped-def]
        logger.info(
            "HOOK EVENT: BeforeModelCallEvent fired - event=%s, has_agent=%s",
            type(event).__name__,
            getattr(event, "agent", None) is not None,
        )
        if self._callback and getattr(event, "agent", None) is not None:
            self._callback(event.agent)
        else:
            logger.warning(
                "HOOK EVENT: BeforeModelCallEvent skipped - callback=%s, agent=%s",
                self._callback is not None,
                getattr(event, "agent", None),
            )

    def _on_after_model_call(self, event) -> None:  # type: ignore[no-untyped-def]
        logger.debug(
            "HOOK EVENT: AfterModelCallEvent fired - event=%s", type(event).__name__
        )
        # Telemetry deltas are picked up by _ensure_prompt_within_budget; no-op here
        return


__all__ = [
    "MappingConversationManager",
    "LargeToolResultMapper",
    "PromptBudgetHook",
    "PROMPT_TOKEN_FALLBACK_LIMIT",
    "PROMPT_TELEMETRY_THRESHOLD",
    "register_conversation_manager",
    "_ensure_prompt_within_budget",
    "_estimate_prompt_tokens",
    "_strip_reasoning_content",
    "clear_shared_conversation_manager",
    "get_shared_conversation_manager",
]
