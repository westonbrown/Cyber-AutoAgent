"""Anthropic OAuth model with automatic fallback on rate limits.

This wrapper provides automatic model fallback when hitting rate limits,
allowing you to maximize Claude Max usage by starting with Opus and
falling back to Sonnet when needed.
"""
import logging
import time
from typing import Any, Dict, Iterator, List, Optional

from anthropic import RateLimitError
from anthropic.types import Message, MessageStreamEvent

from modules.models.anthropic_oauth_model import AnthropicOAuthModel

logger = logging.getLogger(__name__)


class AnthropicOAuthFallbackModel:
    """OAuth model with automatic fallback on rate limits.

    This model tries to use the primary model (e.g., Opus) and automatically
    falls back to a secondary model (e.g., Sonnet) when hitting rate limits.
    """

    def __init__(
        self,
        primary_model_id: str,
        fallback_model_id: str,
        temperature: float = 0.95,
        max_tokens: int = 32000,
        top_p: Optional[float] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs,
    ):
        """Initialize fallback model.

        Args:
            primary_model_id: Primary model to try first (e.g., claude-opus-4-20250514)
            fallback_model_id: Fallback model on rate limit (e.g., claude-sonnet-4-20250514)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            max_retries: Maximum retry attempts on rate limit
            retry_delay: Delay between retries in seconds
            **kwargs: Additional parameters
        """
        self.primary_model_id = primary_model_id
        self.fallback_model_id = fallback_model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.kwargs = kwargs

        # Track current model and stats
        self.current_model_id = primary_model_id
        self.primary_attempts = 0
        self.fallback_uses = 0
        self.rate_limit_hits = 0

        # Create primary model
        self.primary_model = AnthropicOAuthModel(
            model_id=primary_model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            **kwargs,
        )

        # Lazy-create fallback model (only when needed)
        self._fallback_model: Optional[AnthropicOAuthModel] = None

        logger.info(
            "Initialized OAuth fallback model: primary=%s, fallback=%s",
            primary_model_id,
            fallback_model_id,
        )

    @property
    def fallback_model(self) -> AnthropicOAuthModel:
        """Get fallback model, creating if needed."""
        if self._fallback_model is None:
            logger.info("Creating fallback model: %s", self.fallback_model_id)
            self._fallback_model = AnthropicOAuthModel(
                model_id=self.fallback_model_id,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                **self.kwargs,
            )
        return self._fallback_model

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is a rate limit error.

        Args:
            error: Exception to check

        Returns:
            True if rate limit error
        """
        if isinstance(error, RateLimitError):
            return True

        # Check error message for rate limit indicators
        error_str = str(error).lower()
        rate_limit_keywords = [
            "rate limit",
            "rate_limit",
            "too many requests",
            "429",
            "quota exceeded",
            "request limit",
        ]

        return any(keyword in error_str for keyword in rate_limit_keywords)

    def _should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if we should retry the request.

        Args:
            attempt: Current attempt number (0-indexed)
            error: Exception that occurred

        Returns:
            True if should retry
        """
        if attempt >= self.max_retries:
            return False

        return self._is_rate_limit_error(error)

    def __call__(
        self,
        messages: List[Dict[str, Any]],
        **kwargs,
    ) -> Message:
        """Send a completion request with automatic fallback.

        Args:
            messages: List of message dictionaries
            **kwargs: Override parameters

        Returns:
            Anthropic Message object

        Raises:
            Exception: If all retry attempts fail
        """
        last_error = None
        used_fallback = False

        # Try primary model with retries
        for attempt in range(self.max_retries + 1):
            try:
                self.primary_attempts += 1
                response = self.primary_model(messages, **kwargs)
                self.current_model_id = self.primary_model_id

                if used_fallback:
                    logger.info("Primary model recovered after rate limit")

                return response

            except Exception as e:
                last_error = e

                if self._is_rate_limit_error(e):
                    self.rate_limit_hits += 1
                    logger.warning(
                        "Rate limit hit on primary model %s (attempt %d/%d): %s",
                        self.primary_model_id,
                        attempt + 1,
                        self.max_retries + 1,
                        str(e),
                    )

                    if self._should_retry(attempt, e):
                        # Wait before retry
                        delay = self.retry_delay * (2**attempt)  # Exponential backoff
                        logger.info("Retrying primary model in %.1fs...", delay)
                        time.sleep(delay)
                        continue
                    else:
                        # Max retries reached, try fallback
                        logger.warning(
                            "Max retries reached on primary model, switching to fallback: %s",
                            self.fallback_model_id,
                        )
                        break
                else:
                    # Non-rate-limit error, propagate immediately
                    raise

        # Try fallback model
        try:
            logger.info("Using fallback model: %s", self.fallback_model_id)
            self.fallback_uses += 1
            response = self.fallback_model(messages, **kwargs)
            self.current_model_id = self.fallback_model_id
            used_fallback = True
            return response

        except Exception as fallback_error:
            logger.error(
                "Fallback model also failed: %s",
                str(fallback_error),
            )
            # Both models failed, raise the fallback error
            raise fallback_error from last_error

    def stream(
        self,
        messages: List[Dict[str, Any]],
        **kwargs,
    ) -> Iterator[MessageStreamEvent]:
        """Send a streaming completion request with automatic fallback.

        Args:
            messages: List of message dictionaries
            **kwargs: Override parameters

        Yields:
            Message stream events

        Raises:
            Exception: If all retry attempts fail
        """
        last_error = None

        # Try primary model with retries
        for attempt in range(self.max_retries + 1):
            try:
                self.primary_attempts += 1
                for event in self.primary_model.stream(messages, **kwargs):
                    yield event
                self.current_model_id = self.primary_model_id
                return

            except Exception as e:
                last_error = e

                if self._is_rate_limit_error(e):
                    self.rate_limit_hits += 1
                    logger.warning(
                        "Rate limit hit on primary model %s (stream, attempt %d/%d)",
                        self.primary_model_id,
                        attempt + 1,
                        self.max_retries + 1,
                    )

                    if self._should_retry(attempt, e):
                        delay = self.retry_delay * (2**attempt)
                        logger.info("Retrying primary model stream in %.1fs...", delay)
                        time.sleep(delay)
                        continue
                    else:
                        logger.warning("Switching to fallback model for streaming")
                        break
                else:
                    raise

        # Try fallback model
        try:
            logger.info("Streaming with fallback model: %s", self.fallback_model_id)
            self.fallback_uses += 1
            for event in self.fallback_model.stream(messages, **kwargs):
                yield event
            self.current_model_id = self.fallback_model_id

        except Exception as fallback_error:
            logger.error("Fallback model stream also failed")
            raise fallback_error from last_error

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics.

        Returns:
            Dictionary with usage stats
        """
        return {
            "primary_model": self.primary_model_id,
            "fallback_model": self.fallback_model_id,
            "current_model": self.current_model_id,
            "primary_attempts": self.primary_attempts,
            "fallback_uses": self.fallback_uses,
            "rate_limit_hits": self.rate_limit_hits,
        }

    def reset_stats(self) -> None:
        """Reset usage statistics."""
        self.primary_attempts = 0
        self.fallback_uses = 0
        self.rate_limit_hits = 0
        self.current_model_id = self.primary_model_id
