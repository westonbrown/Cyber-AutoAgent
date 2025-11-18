"""Unit tests for Anthropic OAuth authentication flow."""
import base64
import hashlib
import time
import urllib.parse
from unittest.mock import MagicMock, patch

import pytest
import requests

from modules.auth.anthropic_oauth import (
    generate_pkce,
    get_valid_token,
    open_browser,
    refresh_token,
    run_oauth_flow,
)
from modules.auth.oauth_storage import OAuthToken


class TestGeneratePKCE:
    """Test PKCE generation."""

    def test_generate_pkce_returns_tuple(self):
        """Test that generate_pkce returns a tuple of two strings."""
        verifier, challenge = generate_pkce()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)

    def test_generate_pkce_verifier_length(self):
        """Test that verifier has correct length (32 bytes = 43 chars base64)."""
        verifier, _ = generate_pkce()
        # 32 bytes encoded as base64 without padding is 43 characters
        assert len(verifier) == 43

    def test_generate_pkce_challenge_derivation(self):
        """Test that challenge is correctly derived from verifier."""
        verifier, challenge = generate_pkce()

        # Recreate challenge from verifier
        challenge_bytes = hashlib.sha256(verifier.encode("utf-8")).digest()
        expected_challenge = base64.urlsafe_b64encode(challenge_bytes).decode("utf-8").rstrip("=")

        assert challenge == expected_challenge

    def test_generate_pkce_randomness(self):
        """Test that multiple calls generate different values."""
        v1, c1 = generate_pkce()
        v2, c2 = generate_pkce()

        assert v1 != v2
        assert c1 != c2

    def test_generate_pkce_no_padding(self):
        """Test that generated values have no base64 padding."""
        verifier, challenge = generate_pkce()
        assert "=" not in verifier
        assert "=" not in challenge


class TestOpenBrowser:
    """Test browser opening functionality."""

    @patch("subprocess.run")
    def test_open_browser_tries_commands(self, mock_run):
        """Test that open_browser tries to run browser commands."""
        open_browser("http://example.com")
        # Should have been called at least once
        assert mock_run.called

    @patch("subprocess.run")
    def test_open_browser_handles_exceptions(self, mock_run):
        """Test that open_browser handles subprocess exceptions gracefully."""
        mock_run.side_effect = FileNotFoundError()
        # Should not raise exception
        open_browser("http://example.com")


class TestRunOAuthFlow:
    """Test OAuth flow execution."""

    @pytest.fixture
    def mock_storage(self, mocker):
        """Mock OAuthStorage."""
        return mocker.patch("modules.auth.anthropic_oauth.OAuthStorage")

    @pytest.fixture
    def mock_requests_post(self, mocker):
        """Mock requests.post."""
        return mocker.patch("modules.auth.anthropic_oauth.requests.post")

    @pytest.fixture
    def mock_open_browser(self, mocker):
        """Mock open_browser."""
        return mocker.patch("modules.auth.anthropic_oauth.open_browser")

    @pytest.fixture
    def mock_input(self, mocker):
        """Mock input()."""
        return mocker.patch("builtins.input")

    @pytest.fixture
    def mock_print(self, mocker):
        """Mock print()."""
        return mocker.patch("builtins.print")

    def test_run_oauth_flow_returns_existing_valid_token(self, mock_storage):
        """Test that existing valid token is returned without new flow."""
        # Setup existing valid token
        existing_token = OAuthToken(
            access_token="existing_token",
            refresh_token="refresh_token",
            expires_at=int(time.time()) + 3600,
        )
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = existing_token
        mock_storage.return_value = mock_storage_instance

        result = run_oauth_flow()

        assert result == "existing_token"
        mock_storage_instance.load_token.assert_called_once_with("claude")

    def test_run_oauth_flow_refreshes_expired_token(self, mock_storage, mocker):
        """Test that expired token triggers refresh."""
        # Setup expired token with refresh token
        expired_token = OAuthToken(
            access_token="old_token",
            refresh_token="refresh_token",
            expires_at=int(time.time()) - 100,
        )
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = expired_token
        mock_storage.return_value = mock_storage_instance

        # Mock refresh_token function
        mock_refresh = mocker.patch(
            "modules.auth.anthropic_oauth.refresh_token", return_value="refreshed_token"
        )

        result = run_oauth_flow()

        assert result == "refreshed_token"
        mock_refresh.assert_called_once_with("claude")

    def test_run_oauth_flow_full_flow(
        self,
        mock_storage,
        mock_requests_post,
        mock_open_browser,
        mock_input,
        mock_print,
    ):
        """Test complete OAuth flow."""
        # Setup no existing token
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = None
        mock_storage.return_value = mock_storage_instance

        # Setup user input (just the code)
        mock_input.return_value = "test_auth_code"

        # Setup token exchange response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "user:profile",
        }
        mock_requests_post.return_value = mock_response

        result = run_oauth_flow()

        assert result == "new_access_token"
        mock_open_browser.assert_called_once()
        mock_storage_instance.save_token.assert_called_once()

    def test_run_oauth_flow_extracts_code_from_url(
        self,
        mock_storage,
        mock_requests_post,
        mock_open_browser,
        mock_input,
        mock_print,
    ):
        """Test extracting authorization code from full URL."""
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = None
        mock_storage.return_value = mock_storage_instance

        # User pastes full callback URL
        mock_input.return_value = "https://example.com/callback?code=test_code&state=xyz"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_in": 3600,
        }
        mock_requests_post.return_value = mock_response

        result = run_oauth_flow()

        assert result == "token"
        # Verify code was extracted
        call_args = mock_requests_post.call_args
        assert call_args[1]["json"]["code"] == "test_code"

    def test_run_oauth_flow_extracts_code_from_fragment_url(
        self,
        mock_storage,
        mock_requests_post,
        mock_open_browser,
        mock_input,
        mock_print,
    ):
        """Test extracting code from URL with fragment (#)."""
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = None
        mock_storage.return_value = mock_storage_instance

        # User pastes URL with fragment
        mock_input.return_value = "https://example.com/callback#code=fragment_code&state=xyz"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_in": 3600,
        }
        mock_requests_post.return_value = mock_response

        result = run_oauth_flow()

        assert result == "token"

    def test_run_oauth_flow_raises_on_missing_code(
        self,
        mock_storage,
        mock_open_browser,
        mock_input,
        mock_print,
    ):
        """Test that missing code raises ValueError."""
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = None
        mock_storage.return_value = mock_storage_instance

        # User provides URL without code
        mock_input.return_value = "https://example.com/callback?state=xyz"

        with pytest.raises(ValueError, match="Could not extract authorization code"):
            run_oauth_flow()

    def test_run_oauth_flow_raises_on_token_exchange_failure(
        self,
        mock_storage,
        mock_requests_post,
        mock_open_browser,
        mock_input,
        mock_print,
    ):
        """Test that token exchange failure raises exception."""
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = None
        mock_storage.return_value = mock_storage_instance

        mock_input.return_value = "test_code"

        # Setup failed response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid request"
        mock_requests_post.return_value = mock_response

        with pytest.raises(Exception, match="Token exchange failed"):
            run_oauth_flow()


class TestRefreshToken:
    """Test token refresh functionality."""

    @pytest.fixture
    def mock_storage(self, mocker):
        """Mock OAuthStorage."""
        return mocker.patch("modules.auth.anthropic_oauth.OAuthStorage")

    @pytest.fixture
    def mock_requests_post(self, mocker):
        """Mock requests.post."""
        return mocker.patch("modules.auth.anthropic_oauth.requests.post")

    def test_refresh_token_success(self, mock_storage, mock_requests_post):
        """Test successful token refresh."""
        # Setup existing token
        existing_token = OAuthToken(
            access_token="old_token",
            refresh_token="refresh_token",
            expires_at=int(time.time()) - 100,
        )
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = existing_token
        mock_storage.return_value = mock_storage_instance

        # Setup refresh response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }
        mock_requests_post.return_value = mock_response

        result = refresh_token()

        assert result == "new_token"
        mock_storage_instance.save_token.assert_called_once()

    def test_refresh_token_reuses_old_refresh_token(self, mock_storage, mock_requests_post):
        """Test that old refresh token is reused if not provided in response."""
        existing_token = OAuthToken(
            access_token="old_token",
            refresh_token="old_refresh",
            expires_at=int(time.time()) - 100,
        )
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = existing_token
        mock_storage.return_value = mock_storage_instance

        # Response doesn't include refresh_token
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 3600,
        }
        mock_requests_post.return_value = mock_response

        refresh_token()

        # Verify saved token has old refresh token
        saved_token = mock_storage_instance.save_token.call_args[0][0]
        assert saved_token.refresh_token == "old_refresh"

    def test_refresh_token_raises_on_missing_token(self, mock_storage):
        """Test that missing token raises ValueError."""
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = None
        mock_storage.return_value = mock_storage_instance

        with pytest.raises(ValueError, match="No refresh token available"):
            refresh_token()

    def test_refresh_token_raises_on_missing_refresh_token(self, mock_storage):
        """Test that token without refresh_token raises ValueError."""
        token_without_refresh = OAuthToken(
            access_token="token",
            refresh_token="",
            expires_at=int(time.time()) - 100,
        )
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = token_without_refresh
        mock_storage.return_value = mock_storage_instance

        with pytest.raises(ValueError, match="No refresh token available"):
            refresh_token()

    def test_refresh_token_raises_on_api_failure(self, mock_storage, mock_requests_post):
        """Test that API failure raises exception."""
        existing_token = OAuthToken(
            access_token="old_token",
            refresh_token="refresh_token",
            expires_at=int(time.time()) - 100,
        )
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = existing_token
        mock_storage.return_value = mock_storage_instance

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid refresh token"
        mock_requests_post.return_value = mock_response

        with pytest.raises(Exception, match="Token refresh failed"):
            refresh_token()


class TestGetValidToken:
    """Test get_valid_token functionality."""

    @pytest.fixture
    def mock_storage(self, mocker):
        """Mock OAuthStorage."""
        return mocker.patch("modules.auth.anthropic_oauth.OAuthStorage")

    def test_get_valid_token_returns_valid_token(self, mock_storage):
        """Test that valid token is returned directly."""
        valid_token = OAuthToken(
            access_token="valid_token",
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
        )
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = valid_token
        mock_storage.return_value = mock_storage_instance

        result = get_valid_token()

        assert result == "valid_token"

    def test_get_valid_token_runs_oauth_flow_when_no_token(self, mock_storage, mocker):
        """Test that OAuth flow runs when no token exists."""
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = None
        mock_storage.return_value = mock_storage_instance

        mock_run_oauth = mocker.patch(
            "modules.auth.anthropic_oauth.run_oauth_flow", return_value="new_token"
        )

        result = get_valid_token()

        assert result == "new_token"
        mock_run_oauth.assert_called_once_with("claude")

    def test_get_valid_token_refreshes_expired_token(self, mock_storage, mocker):
        """Test that expired token triggers refresh."""
        expired_token = OAuthToken(
            access_token="expired",
            refresh_token="refresh",
            expires_at=int(time.time()) - 100,
        )
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = expired_token
        mock_storage.return_value = mock_storage_instance

        mock_refresh = mocker.patch(
            "modules.auth.anthropic_oauth.refresh_token", return_value="refreshed_token"
        )

        result = get_valid_token()

        assert result == "refreshed_token"
        mock_refresh.assert_called_once_with("claude")

    def test_get_valid_token_falls_back_to_oauth_flow_on_refresh_failure(
        self, mock_storage, mocker
    ):
        """Test that OAuth flow runs if refresh fails."""
        expired_token = OAuthToken(
            access_token="expired",
            refresh_token="refresh",
            expires_at=int(time.time()) - 100,
        )
        mock_storage_instance = MagicMock()
        mock_storage_instance.load_token.return_value = expired_token
        mock_storage.return_value = mock_storage_instance

        # Refresh fails
        mock_refresh = mocker.patch(
            "modules.auth.anthropic_oauth.refresh_token", side_effect=Exception("Refresh failed")
        )

        # OAuth flow succeeds
        mock_run_oauth = mocker.patch(
            "modules.auth.anthropic_oauth.run_oauth_flow", return_value="new_token"
        )

        # Mock print to suppress output
        mocker.patch("builtins.print")

        result = get_valid_token()

        assert result == "new_token"
        mock_refresh.assert_called_once()
        mock_run_oauth.assert_called_once_with("claude")
