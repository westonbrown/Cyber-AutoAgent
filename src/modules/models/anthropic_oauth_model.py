"""Anthropic model using OAuth authentication (Claude Max billing).

This model implementation uses OAuth authentication to bill against Claude Max
unlimited usage instead of per-token API billing. It spoofs Claude Code to
ensure requests are treated as coming from the official CLI.
"""
from typing import Any, Dict, Iterator, List, Optional

import httpx
from anthropic import Anthropic
from anthropic.types import Message, MessageStreamEvent
from anthropic._types import NOT_GIVEN

from modules.auth.anthropic_oauth import get_valid_token


class OAuthTransport(httpx.HTTPTransport):
    """Custom HTTP transport that removes X-Api-Key and adds OAuth headers."""

    def __init__(self, access_token: str, *args, **kwargs):
        """Initialize transport with OAuth token.

        Args:
            access_token: OAuth access token
        """
        super().__init__(*args, **kwargs)
        self.access_token = access_token

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle request, removing X-Api-Key and adding OAuth headers.

        Args:
            request: HTTP request

        Returns:
            HTTP response
        """
        # Remove X-Api-Key header if present (OAuth doesn't use it)
        if "x-api-key" in request.headers:
            del request.headers["x-api-key"]

        # Add OAuth Bearer token
        request.headers["authorization"] = f"Bearer {self.access_token}"

        # Add OAuth beta flag (preserve existing if present)
        existing_beta = request.headers.get("anthropic-beta", "")
        oauth_beta = "oauth-2025-04-20"
        if existing_beta:
            request.headers["anthropic-beta"] = f"{existing_beta},{oauth_beta}"
        else:
            request.headers["anthropic-beta"] = oauth_beta

        # Set User-Agent to match AI SDK
        request.headers["user-agent"] = "ai-sdk/anthropic"

        return super().handle_request(request)


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

        # Create custom HTTP client with OAuth transport
        # This removes X-Api-Key header and adds OAuth headers
        http_client = httpx.Client(
            transport=OAuthTransport(self.access_token),
            timeout=httpx.Timeout(300.0, connect=60.0),  # 5 min timeout, 1 min connect
        )

        # Create Anthropic client with custom HTTP client
        # API key is required by SDK but will be removed by our transport
        self.client = Anthropic(
            api_key="dummy-key-will-be-removed-by-transport",
            http_client=http_client,
        )

    def _refresh_client(self) -> None:
        """Refresh client with new OAuth token."""
        self.access_token = get_valid_token("claude")

        # Create new HTTP client with refreshed token
        http_client = httpx.Client(
            transport=OAuthTransport(self.access_token),
            timeout=httpx.Timeout(300.0, connect=60.0),
        )

        # Update client with refreshed token
        self.client = Anthropic(
            api_key="dummy-key-will-be-removed-by-transport",
            http_client=http_client,
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
