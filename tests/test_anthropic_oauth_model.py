"""Unit tests for Anthropic OAuth model client."""
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

# Mock anthropic module and submodules
mock_anthropic = MagicMock()
mock_anthropic.Anthropic = MagicMock()
mock_anthropic.types = MagicMock()
mock_anthropic._types = MagicMock()
mock_anthropic._types.NOT_GIVEN = "NOT_GIVEN"

sys.modules["anthropic"] = mock_anthropic
sys.modules["anthropic.types"] = mock_anthropic.types
sys.modules["anthropic._types"] = mock_anthropic._types

# Import httpx for real
import httpx  # noqa: E402

# Mock httpx.Client and HTTPTransport but keep the real Headers
sys.modules["httpx"].Client = MagicMock()
sys.modules["httpx"].HTTPTransport = MagicMock
sys.modules["httpx"].Timeout = MagicMock
sys.modules["httpx"].Request = httpx.Request
sys.modules["httpx"].Response = httpx.Response
sys.modules["httpx"].Headers = httpx.Headers

from modules.models.anthropic_oauth_model import (  # noqa: E402
    AnthropicOAuthModel,
    OAuthTransport,
)


class TestOAuthTransport:
    """Test OAuthTransport class.

    Note: These tests are limited due to httpx module mocking.
    The OAuthTransport class is indirectly tested through integration tests.
    """

    def test_transport_initialization(self):
        """Test transport initialization stores token."""
        transport = OAuthTransport(access_token="my_token")
        assert transport.access_token == "my_token"


class TestAnthropicOAuthModel:
    """Test AnthropicOAuthModel class."""

    @pytest.fixture
    def mock_get_valid_token(self, mocker):
        """Mock get_valid_token function."""
        return mocker.patch(
            "modules.models.anthropic_oauth_model.get_valid_token",
            return_value="test_access_token",
        )

    @pytest.fixture
    def mock_anthropic_client(self, mocker):
        """Mock Anthropic client."""
        return mocker.patch("modules.models.anthropic_oauth_model.Anthropic")

    @pytest.fixture
    def model(self, mock_get_valid_token, mock_anthropic_client):
        """Create AnthropicOAuthModel instance."""
        return AnthropicOAuthModel(
            model_id="claude-sonnet-4-20250514",
            temperature=0.7,
            max_tokens=1000,
        )

    def test_model_initialization(self, mock_get_valid_token, mock_anthropic_client):
        """Test model initialization."""
        model = AnthropicOAuthModel(
            model_id="claude-sonnet-4-20250514",
            temperature=0.7,
            max_tokens=1000,
            top_p=0.9,
        )

        assert model.model_id == "claude-sonnet-4-20250514"
        assert model.temperature == 0.7
        assert model.max_tokens == 1000
        assert model.top_p == 0.9
        assert model.access_token == "test_access_token"
        mock_get_valid_token.assert_called_once_with("claude")

    def test_model_creates_anthropic_client(self, mock_get_valid_token, mock_anthropic_client):
        """Test that Anthropic client is created with custom HTTP client."""
        model = AnthropicOAuthModel(model_id="claude-sonnet-4-20250514")

        mock_anthropic_client.assert_called_once()
        call_kwargs = mock_anthropic_client.call_args[1]
        assert call_kwargs["api_key"] == "dummy-key-will-be-removed-by-transport"
        assert "http_client" in call_kwargs

    def test_refresh_client_gets_new_token(self, model, mock_get_valid_token, mock_anthropic_client):
        """Test that _refresh_client gets a new token."""
        mock_get_valid_token.reset_mock()
        mock_anthropic_client.reset_mock()

        model._refresh_client()

        # Should call get_valid_token again
        assert mock_get_valid_token.call_count == 1

    def test_build_system_message(self, model):
        """Test system message building."""
        system_message = model._build_system_message()

        assert isinstance(system_message, list)
        assert len(system_message) == 1
        assert system_message[0]["type"] == "text"
        assert "Claude Code" in system_message[0]["text"]

    def test_get_beta_flags_for_sonnet_4(self, mock_get_valid_token, mock_anthropic_client):
        """Test beta flags for Claude Sonnet 4."""
        model = AnthropicOAuthModel(model_id="claude-sonnet-4-20250514")

        flags = model._get_beta_flags()

        assert "oauth-2025-04-20" in flags
        assert "context-1m-2025-08-07" in flags

    def test_get_beta_flags_for_non_sonnet(self, mock_get_valid_token, mock_anthropic_client):
        """Test beta flags for non-Sonnet models."""
        model = AnthropicOAuthModel(model_id="claude-opus-4-20250514")

        flags = model._get_beta_flags()

        assert "oauth-2025-04-20" in flags
        assert "context-1m-2025-08-07" not in flags

    def test_call_sends_messages(self, model):
        """Test that __call__ sends messages to API."""
        messages = [{"role": "user", "content": "Hello"}]
        mock_response = MagicMock()

        model.client.messages.create = MagicMock(return_value=mock_response)

        result = model(messages)

        assert result == mock_response
        model.client.messages.create.assert_called_once()

    def test_call_includes_model_id(self, model):
        """Test that model_id is included in API call."""
        messages = [{"role": "user", "content": "Hello"}]
        model.client.messages.create = MagicMock()

        model(messages)

        call_kwargs = model.client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"

    def test_call_includes_system_message(self, model):
        """Test that system message is included."""
        messages = [{"role": "user", "content": "Hello"}]
        model.client.messages.create = MagicMock()

        model(messages)

        call_kwargs = model.client.messages.create.call_args[1]
        assert "system" in call_kwargs
        assert isinstance(call_kwargs["system"], list)

    def test_call_includes_temperature(self, model):
        """Test that temperature is included."""
        messages = [{"role": "user", "content": "Hello"}]
        model.client.messages.create = MagicMock()

        model(messages)

        call_kwargs = model.client.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 0.7

    def test_call_includes_max_tokens(self, model):
        """Test that max_tokens is included."""
        messages = [{"role": "user", "content": "Hello"}]
        model.client.messages.create = MagicMock()

        model(messages)

        call_kwargs = model.client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 1000

    def test_call_uses_top_p_instead_of_temperature(
        self, mock_get_valid_token, mock_anthropic_client
    ):
        """Test that top_p is used instead of temperature when provided."""
        model = AnthropicOAuthModel(
            model_id="claude-sonnet-4-20250514", temperature=0.7, top_p=0.9
        )
        messages = [{"role": "user", "content": "Hello"}]
        model.client.messages.create = MagicMock()

        model(messages)

        call_kwargs = model.client.messages.create.call_args[1]
        assert "top_p" in call_kwargs
        assert call_kwargs["top_p"] == 0.9
        assert "temperature" not in call_kwargs

    def test_call_allows_parameter_override(self, model):
        """Test that parameters can be overridden in call."""
        messages = [{"role": "user", "content": "Hello"}]
        model.client.messages.create = MagicMock()

        model(messages, temperature=0.5, max_tokens=500)

        call_kwargs = model.client.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["max_tokens"] == 500

    def test_call_includes_beta_flags_in_headers(self, model):
        """Test that beta flags are included in extra_headers."""
        messages = [{"role": "user", "content": "Hello"}]
        model.client.messages.create = MagicMock()

        model(messages)

        call_kwargs = model.client.messages.create.call_args[1]
        assert "extra_headers" in call_kwargs
        assert "anthropic-beta" in call_kwargs["extra_headers"]

    def test_call_refreshes_client(self, model, mock_get_valid_token):
        """Test that client is refreshed before each call."""
        messages = [{"role": "user", "content": "Hello"}]
        model.client.messages.create = MagicMock()
        mock_get_valid_token.reset_mock()

        model(messages)

        # Should call get_valid_token during refresh
        mock_get_valid_token.assert_called_once()

    def test_stream_yields_events(self, model):
        """Test that stream() yields events."""
        messages = [{"role": "user", "content": "Hello"}]

        # Create mock stream context manager
        mock_stream = MagicMock()
        mock_stream.__enter__.return_value = iter([MagicMock(), MagicMock()])
        mock_stream.__exit__.return_value = None

        model.client.messages.stream = MagicMock(return_value=mock_stream)

        events = list(model.stream(messages))

        assert len(events) == 2
        model.client.messages.stream.assert_called_once()

    def test_stream_includes_model_params(self, model):
        """Test that stream includes model parameters."""
        messages = [{"role": "user", "content": "Hello"}]

        mock_stream = MagicMock()
        mock_stream.__enter__.return_value = iter([])
        mock_stream.__exit__.return_value = None

        model.client.messages.stream = MagicMock(return_value=mock_stream)

        list(model.stream(messages))

        call_kwargs = model.client.messages.stream.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["max_tokens"] == 1000

    def test_stream_refreshes_client(self, model, mock_get_valid_token):
        """Test that client is refreshed before streaming."""
        messages = [{"role": "user", "content": "Hello"}]

        mock_stream = MagicMock()
        mock_stream.__enter__.return_value = iter([])
        mock_stream.__exit__.return_value = None

        model.client.messages.stream = MagicMock(return_value=mock_stream)
        mock_get_valid_token.reset_mock()

        list(model.stream(messages))

        # Should call get_valid_token during refresh
        mock_get_valid_token.assert_called_once()

    def test_stream_allows_parameter_override(self, model):
        """Test that stream parameters can be overridden."""
        messages = [{"role": "user", "content": "Hello"}]

        mock_stream = MagicMock()
        mock_stream.__enter__.return_value = iter([])
        mock_stream.__exit__.return_value = None

        model.client.messages.stream = MagicMock(return_value=mock_stream)

        list(model.stream(messages, max_tokens=2000))

        call_kwargs = model.client.messages.stream.call_args[1]
        assert call_kwargs["max_tokens"] == 2000
