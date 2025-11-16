"""Anthropic model using OAuth authentication (Claude Max billing).

This model implementation uses OAuth authentication to bill against Claude Max
unlimited usage instead of per-token API billing. It spoofs Claude Code to
ensure requests are treated as coming from the official CLI.
"""
import http.client
from typing import Any, Dict, Iterator, List, Optional, Union

from anthropic import Anthropic, Stream
from anthropic.types import Message, MessageStreamEvent
from anthropic._types import NOT_GIVEN, NotGiven

from modules.auth.anthropic_oauth import get_valid_token


class OAuthHTTPConnection(http.client.HTTPSConnection):
    """Custom HTTPS connection that adds OAuth headers."""

    def __init__(self, *args, **kwargs):
        self.access_token = kwargs.pop("access_token", None)
        super().__init__(*args, **kwargs)

    def request(self, method, url, body=None, headers=None, **kwargs):
        """Override request to inject OAuth headers."""
        if headers is None:
            headers = {}

        # Add OAuth Bearer token
        headers["Authorization"] = f"Bearer {self.access_token}"

        # Add OAuth beta flag
        existing_beta = headers.get("anthropic-beta", "")
        oauth_beta = "oauth-2025-04-20"
        if existing_beta:
            headers["anthropic-beta"] = f"{existing_beta},{oauth_beta}"
        else:
            headers["anthropic-beta"] = oauth_beta

        # Set User-Agent to match AI SDK
        headers["User-Agent"] = "ai-sdk/anthropic"

        # Remove x-api-key header if present (OAuth doesn't use it)
        headers.pop("x-api-key", None)

        return super().request(method, url, body, headers, **kwargs)


class AnthropicOAuthModel:
    """Anthropic model that uses OAuth instead of API keys.

    This bills against Claude Max unlimited usage instead of per-token API billing.
    """

    def __init__(
        self,
        model_id: str,
        temperature: float = 0.95,
        max_tokens: int = 32000,
        top_p: Optional[float] = None,
        **kwargs,
    ):
        """Initialize OAuth model.

        Args:
            model_id: Model identifier (e.g., claude-sonnet-4-20250514)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter (optional)
            **kwargs: Additional parameters
        """
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.kwargs = kwargs

        # Get OAuth token (will prompt user if needed)
        self.access_token = get_valid_token("claude")

        # Create Anthropic client
        # We use a dummy API key since the SDK requires it, but we override with OAuth in headers
        self.client = Anthropic(
            api_key="dummy-key-oauth-will-override",
            default_headers={
                "Authorization": f"Bearer {self.access_token}",
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": "ai-sdk/anthropic",
            },
        )

    def _refresh_client(self) -> None:
        """Refresh client with new OAuth token."""
        self.access_token = get_valid_token("claude")
        self.client = Anthropic(
            api_key="dummy-key-oauth-will-override",
            default_headers={
                "Authorization": f"Bearer {self.access_token}",
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": "ai-sdk/anthropic",
            },
        )

    def _build_system_message(self) -> List[Dict[str, str]]:
        """Build system message with Claude Code spoofing.

        Returns:
            List of system message blocks
        """
        return [{"type": "text", "text": "You are Claude Code, Anthropic's official CLI for Claude."}]

    def _get_beta_flags(self) -> Optional[str]:
        """Get model-specific beta flags.

        Returns:
            Comma-separated beta flags or None
        """
        flags = ["oauth-2025-04-20"]

        # Add 1M context support for Claude Sonnet 4 and 4.5
        if "claude-sonnet-4" in self.model_id:
            flags.append("context-1m-2025-08-07")

        return ",".join(flags)

    def __call__(
        self,
        messages: List[Dict[str, Any]],
        **kwargs,
    ) -> Message:
        """Send a completion request.

        Args:
            messages: List of message dictionaries
            **kwargs: Override parameters

        Returns:
            Anthropic Message object
        """
        # Refresh token if needed
        self._refresh_client()

        # Build params with Claude Code spoofing
        params = {
            "model": self.model_id,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "messages": messages,
            "system": self._build_system_message(),
        }

        # Add temperature or top_p (not both for some models)
        if "top_p" in kwargs:
            params["top_p"] = kwargs["top_p"]
        elif self.top_p is not None:
            params["top_p"] = self.top_p
        else:
            params["temperature"] = kwargs.get("temperature", self.temperature)

        # Add beta flags if needed
        beta_flags = self._get_beta_flags()
        extra_headers = {}
        if beta_flags:
            extra_headers["anthropic-beta"] = beta_flags

        return self.client.messages.create(**params, extra_headers=extra_headers if extra_headers else NOT_GIVEN)

    def stream(
        self,
        messages: List[Dict[str, Any]],
        **kwargs,
    ) -> Iterator[MessageStreamEvent]:
        """Send a streaming completion request.

        Args:
            messages: List of message dictionaries
            **kwargs: Override parameters

        Yields:
            Message stream events
        """
        # Refresh token if needed
        self._refresh_client()

        params = {
            "model": self.model_id,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "messages": messages,
            "system": self._build_system_message(),
        }

        # Add temperature or top_p (not both for some models)
        if "top_p" in kwargs:
            params["top_p"] = kwargs["top_p"]
        elif self.top_p is not None:
            params["top_p"] = self.top_p
        else:
            params["temperature"] = kwargs.get("temperature", self.temperature)

        # Add beta flags if needed
        beta_flags = self._get_beta_flags()
        extra_headers = {}
        if beta_flags:
            extra_headers["anthropic-beta"] = beta_flags

        with self.client.messages.stream(**params, extra_headers=extra_headers if extra_headers else NOT_GIVEN) as stream:
            for event in stream:
                yield event
