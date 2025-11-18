"""Unit tests for Anthropic OAuth fallback model."""
import sys
from unittest.mock import MagicMock, patch

import pytest


# Create a real RateLimitError class for testing
class RateLimitError(Exception):
    """Mock RateLimitError for testing."""

    def __init__(self, message, response, body):
        super().__init__(message)
        self.response = response
        self.body = body


# Mock anthropic module and submodules before importing our code
mock_anthropic = MagicMock()
mock_anthropic.Anthropic = MagicMock()
mock_anthropic.RateLimitError = RateLimitError
mock_anthropic.types = MagicMock()
mock_anthropic._types = MagicMock()
mock_anthropic._types.NOT_GIVEN = "NOT_GIVEN"

sys.modules["anthropic"] = mock_anthropic
sys.modules["anthropic.types"] = mock_anthropic.types
sys.modules["anthropic._types"] = mock_anthropic._types

# Mock httpx module
sys.modules["httpx"] = MagicMock()
sys.modules["httpx"].Client = MagicMock()
sys.modules["httpx"].HTTPTransport = MagicMock
sys.modules["httpx"].Timeout = MagicMock

from modules.models.anthropic_oauth_fallback import (  # noqa: E402
    AnthropicOAuthFallbackModel,
)


class TestAnthropicOAuthFallbackModel:
    """Test AnthropicOAuthFallbackModel class."""

    @pytest.fixture
    def mock_oauth_model(self, mocker):
        """Mock AnthropicOAuthModel."""
        return mocker.patch("modules.models.anthropic_oauth_fallback.AnthropicOAuthModel")

    @pytest.fixture
    def fallback_model(self, mock_oauth_model):
        """Create fallback model instance."""
        return AnthropicOAuthFallbackModel(
            primary_model_id="claude-opus-4-20250514",
            fallback_model_id="claude-sonnet-4-20250514",
            temperature=0.7,
            max_tokens=1000,
            max_retries=2,
            retry_delay=0.1,  # Short delay for tests
        )

    def test_initialization(self, mock_oauth_model):
        """Test fallback model initialization."""
        model = AnthropicOAuthFallbackModel(
            primary_model_id="claude-opus-4-20250514",
            fallback_model_id="claude-sonnet-4-20250514",
            temperature=0.7,
            max_tokens=1000,
        )

        assert model.primary_model_id == "claude-opus-4-20250514"
        assert model.fallback_model_id == "claude-sonnet-4-20250514"
        assert model.temperature == 0.7
        assert model.max_tokens == 1000
        assert model.current_model_id == "claude-opus-4-20250514"
        assert model.primary_attempts == 0
        assert model.fallback_uses == 0
        assert model.rate_limit_hits == 0

    def test_primary_model_created_on_init(self, mock_oauth_model):
        """Test that primary model is created during initialization."""
        model = AnthropicOAuthFallbackModel(
            primary_model_id="claude-opus-4-20250514",
            fallback_model_id="claude-sonnet-4-20250514",
        )

        # Primary model should be created immediately
        assert mock_oauth_model.call_count == 1
        call_kwargs = mock_oauth_model.call_args[1]
        assert call_kwargs["model_id"] == "claude-opus-4-20250514"

    def test_fallback_model_lazy_created(self, mock_oauth_model, fallback_model):
        """Test that fallback model is created lazily."""
        # Reset call count from primary model creation
        mock_oauth_model.reset_mock()

        # Access fallback_model property
        _ = fallback_model.fallback_model

        # Should create fallback model now
        assert mock_oauth_model.call_count == 1
        call_kwargs = mock_oauth_model.call_args[1]
        assert call_kwargs["model_id"] == "claude-sonnet-4-20250514"

    def test_is_rate_limit_error_detects_rate_limit_error(self, fallback_model):
        """Test rate limit error detection."""
        error = RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(),
            body={},
        )
        assert fallback_model._is_rate_limit_error(error)

    def test_is_rate_limit_error_detects_from_message(self, fallback_model):
        """Test rate limit error detection from error message."""
        test_cases = [
            Exception("Rate limit exceeded"),
            Exception("too many requests"),
            Exception("HTTP 429 error"),
            Exception("quota exceeded"),
        ]

        for error in test_cases:
            assert fallback_model._is_rate_limit_error(error), f"Failed to detect: {error}"

    def test_is_rate_limit_error_rejects_other_errors(self, fallback_model):
        """Test that non-rate-limit errors are not detected as rate limits."""
        error = Exception("Connection failed")
        assert not fallback_model._is_rate_limit_error(error)

    def test_should_retry_returns_true_within_max_retries(self, fallback_model):
        """Test retry decision within max retries."""
        error = RateLimitError(message="Rate limit", response=MagicMock(), body={})

        assert fallback_model._should_retry(0, error)
        assert fallback_model._should_retry(1, error)

    def test_should_retry_returns_false_at_max_retries(self, fallback_model):
        """Test retry decision at max retries."""
        error = RateLimitError(message="Rate limit", response=MagicMock(), body={})

        # max_retries is 2, so attempt 2 should not retry
        assert not fallback_model._should_retry(2, error)

    def test_should_retry_returns_false_for_non_rate_limit(self, fallback_model):
        """Test retry decision for non-rate-limit errors."""
        error = Exception("Connection failed")

        assert not fallback_model._should_retry(0, error)

    def test_call_uses_primary_model_on_success(self, fallback_model):
        """Test that successful call uses primary model."""
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MagicMock()
        fallback_model.primary_model = MagicMock(return_value=mock_response)

        result = fallback_model(messages)

        assert result == mock_response
        fallback_model.primary_model.assert_called_once_with(messages)
        assert fallback_model.primary_attempts == 1
        assert fallback_model.fallback_uses == 0

    def test_call_falls_back_on_rate_limit(self, fallback_model, mocker):
        """Test fallback on rate limit error."""
        messages = [{"role": "user", "content": "Hello"}]

        # Primary model fails with rate limit
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded", response=MagicMock(), body={}
        )
        fallback_model.primary_model = MagicMock(side_effect=rate_limit_error)

        # Fallback succeeds - set _fallback_model directly
        mock_fallback_response = MagicMock()
        mock_fallback_instance = MagicMock(return_value=mock_fallback_response)
        fallback_model._fallback_model = mock_fallback_instance

        # Mock sleep to speed up test
        mocker.patch("time.sleep")

        result = fallback_model(messages)

        assert result == mock_fallback_response
        # Should try primary max_retries + 1 times
        assert fallback_model.primary_model.call_count == 3  # max_retries=2, so 3 attempts
        assert fallback_model.fallback_uses == 1
        assert fallback_model.rate_limit_hits == 3
        assert fallback_model.current_model_id == "claude-sonnet-4-20250514"

    def test_call_retries_with_exponential_backoff(self, fallback_model, mocker):
        """Test that retries use exponential backoff."""
        messages = [{"role": "user", "content": "Hello"}]

        rate_limit_error = RateLimitError(
            message="Rate limit exceeded", response=MagicMock(), body={}
        )
        fallback_model.primary_model = MagicMock(side_effect=rate_limit_error)

        mock_fallback_instance = MagicMock(return_value=MagicMock())
        fallback_model._fallback_model = mock_fallback_instance

        mock_sleep = mocker.patch("time.sleep")

        fallback_model(messages)

        # Check sleep was called with exponential backoff
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        # retry_delay=0.1, so delays should be 0.1, 0.2, etc.
        assert len(sleep_calls) >= 1
        assert sleep_calls[0] == pytest.approx(0.1)  # 0.1 * 2^0
        if len(sleep_calls) > 1:
            assert sleep_calls[1] == pytest.approx(0.2)  # 0.1 * 2^1

    def test_call_raises_non_rate_limit_errors_immediately(self, fallback_model):
        """Test that non-rate-limit errors are raised immediately."""
        messages = [{"role": "user", "content": "Hello"}]

        connection_error = Exception("Connection failed")
        fallback_model.primary_model = MagicMock(side_effect=connection_error)

        with pytest.raises(Exception, match="Connection failed"):
            fallback_model(messages)

        # Should only try once, not retry
        assert fallback_model.primary_model.call_count == 1
        assert fallback_model.fallback_uses == 0

    def test_call_raises_when_both_models_fail(self, fallback_model, mocker):
        """Test that exception is raised when both models fail."""
        messages = [{"role": "user", "content": "Hello"}]

        rate_limit_error = RateLimitError(
            message="Rate limit exceeded", response=MagicMock(), body={}
        )
        fallback_model.primary_model = MagicMock(side_effect=rate_limit_error)

        fallback_error = Exception("Fallback also rate limited")
        mock_fallback_instance = MagicMock(side_effect=fallback_error)
        fallback_model._fallback_model = mock_fallback_instance

        mocker.patch("time.sleep")

        with pytest.raises(Exception, match="Fallback also rate limited"):
            fallback_model(messages)

    def test_stream_uses_primary_model_on_success(self, fallback_model):
        """Test that successful stream uses primary model."""
        messages = [{"role": "user", "content": "Hello"}]
        mock_events = [MagicMock(), MagicMock()]
        fallback_model.primary_model.stream = MagicMock(return_value=iter(mock_events))

        events = list(fallback_model.stream(messages))

        assert events == mock_events
        assert fallback_model.primary_attempts == 1
        assert fallback_model.fallback_uses == 0

    def test_stream_falls_back_on_rate_limit(self, fallback_model, mocker):
        """Test stream fallback on rate limit."""
        messages = [{"role": "user", "content": "Hello"}]

        rate_limit_error = RateLimitError(
            message="Rate limit exceeded", response=MagicMock(), body={}
        )
        fallback_model.primary_model.stream = MagicMock(side_effect=rate_limit_error)

        mock_fallback_events = [MagicMock(), MagicMock()]
        mock_fallback_instance = MagicMock()
        mock_fallback_instance.stream = MagicMock(return_value=iter(mock_fallback_events))
        fallback_model._fallback_model = mock_fallback_instance

        mocker.patch("time.sleep")

        events = list(fallback_model.stream(messages))

        assert events == mock_fallback_events
        assert fallback_model.fallback_uses == 1

    def test_stream_raises_non_rate_limit_errors_immediately(self, fallback_model):
        """Test that stream raises non-rate-limit errors immediately."""
        messages = [{"role": "user", "content": "Hello"}]

        connection_error = Exception("Connection failed")
        fallback_model.primary_model.stream = MagicMock(side_effect=connection_error)

        with pytest.raises(Exception, match="Connection failed"):
            list(fallback_model.stream(messages))

        assert fallback_model.primary_model.stream.call_count == 1
        assert fallback_model.fallback_uses == 0

    def test_get_stats_returns_usage_statistics(self, fallback_model):
        """Test get_stats returns correct statistics."""
        fallback_model.primary_attempts = 5
        fallback_model.fallback_uses = 2
        fallback_model.rate_limit_hits = 3
        fallback_model.current_model_id = "claude-sonnet-4-20250514"

        stats = fallback_model.get_stats()

        assert stats["primary_model"] == "claude-opus-4-20250514"
        assert stats["fallback_model"] == "claude-sonnet-4-20250514"
        assert stats["current_model"] == "claude-sonnet-4-20250514"
        assert stats["primary_attempts"] == 5
        assert stats["fallback_uses"] == 2
        assert stats["rate_limit_hits"] == 3

    def test_reset_stats_clears_statistics(self, fallback_model):
        """Test reset_stats clears usage statistics."""
        fallback_model.primary_attempts = 5
        fallback_model.fallback_uses = 2
        fallback_model.rate_limit_hits = 3
        fallback_model.current_model_id = "claude-sonnet-4-20250514"

        fallback_model.reset_stats()

        assert fallback_model.primary_attempts == 0
        assert fallback_model.fallback_uses == 0
        assert fallback_model.rate_limit_hits == 0
        assert fallback_model.current_model_id == "claude-opus-4-20250514"

    def test_initialization_with_custom_parameters(self, mock_oauth_model):
        """Test initialization with all custom parameters."""
        model = AnthropicOAuthFallbackModel(
            primary_model_id="claude-opus-4-20250514",
            fallback_model_id="claude-sonnet-4-20250514",
            temperature=0.5,
            max_tokens=2000,
            top_p=0.9,
            max_retries=5,
            retry_delay=2.0,
            custom_param="value",
        )

        assert model.temperature == 0.5
        assert model.max_tokens == 2000
        assert model.top_p == 0.9
        assert model.max_retries == 5
        assert model.retry_delay == 2.0
        assert "custom_param" in model.kwargs

    def test_call_passes_kwargs_to_models(self, fallback_model):
        """Test that call passes kwargs to underlying models."""
        messages = [{"role": "user", "content": "Hello"}]
        fallback_model.primary_model = MagicMock(return_value=MagicMock())

        fallback_model(messages, custom_param="test_value")

        call_kwargs = fallback_model.primary_model.call_args[1]
        assert call_kwargs["custom_param"] == "test_value"

    def test_stream_passes_kwargs_to_models(self, fallback_model):
        """Test that stream passes kwargs to underlying models."""
        messages = [{"role": "user", "content": "Hello"}]
        fallback_model.primary_model.stream = MagicMock(return_value=iter([]))

        list(fallback_model.stream(messages, custom_param="test_value"))

        call_kwargs = fallback_model.primary_model.stream.call_args[1]
        assert call_kwargs["custom_param"] == "test_value"
