"""Unit tests for OAuth storage module."""
import json
import os
import time
from pathlib import Path

import pytest

from modules.auth.oauth_storage import OAuthStorage, OAuthToken


class TestOAuthToken:
    """Test OAuthToken dataclass."""

    def test_token_creation(self):
        """Test basic token creation."""
        token = OAuthToken(
            access_token="test_access",
            refresh_token="test_refresh",
            expires_at=int(time.time()) + 3600,
        )
        assert token.access_token == "test_access"
        assert token.refresh_token == "test_refresh"
        assert token.token_type == "Bearer"
        assert token.scope == ""

    def test_token_with_custom_fields(self):
        """Test token with custom token_type and scope."""
        token = OAuthToken(
            access_token="test_access",
            refresh_token="test_refresh",
            expires_at=int(time.time()) + 3600,
            token_type="CustomBearer",
            scope="read write",
        )
        assert token.token_type == "CustomBearer"
        assert token.scope == "read write"

    def test_is_expired_returns_false_for_valid_token(self):
        """Test that valid token is not expired."""
        # Token expires in 1 hour
        token = OAuthToken(
            access_token="test",
            refresh_token="test",
            expires_at=int(time.time()) + 3600,
        )
        assert not token.is_expired()

    def test_is_expired_returns_true_for_expired_token(self):
        """Test that expired token is detected."""
        # Token expired 1 hour ago
        token = OAuthToken(
            access_token="test",
            refresh_token="test",
            expires_at=int(time.time()) - 3600,
        )
        assert token.is_expired()

    def test_is_expired_with_buffer_time(self):
        """Test expiry check with buffer time."""
        # Token expires in 3 minutes
        token = OAuthToken(
            access_token="test",
            refresh_token="test",
            expires_at=int(time.time()) + 180,
        )
        # With 5 minute buffer, should be considered expired
        assert token.is_expired(buffer_minutes=5)
        # With 1 minute buffer, should be valid
        assert not token.is_expired(buffer_minutes=1)

    def test_is_expired_with_zero_expires_at(self):
        """Test that zero expires_at is considered expired."""
        token = OAuthToken(
            access_token="test",
            refresh_token="test",
            expires_at=0,
        )
        assert token.is_expired()

    def test_is_expired_with_none_expires_at(self):
        """Test that None expires_at is considered expired."""
        token = OAuthToken(
            access_token="test",
            refresh_token="test",
            expires_at=None,
        )
        assert token.is_expired()


class TestOAuthStorage:
    """Test OAuthStorage class."""

    @pytest.fixture
    def temp_config_dir(self, tmp_path):
        """Create temporary config directory."""
        return str(tmp_path / "test_config")

    @pytest.fixture
    def storage(self, temp_config_dir):
        """Create OAuthStorage instance with temp directory."""
        return OAuthStorage(config_dir=temp_config_dir)

    @pytest.fixture
    def sample_token(self):
        """Create sample OAuth token."""
        return OAuthToken(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_at=int(time.time()) + 3600,
            token_type="Bearer",
            scope="read write",
        )

    def test_storage_initialization(self, temp_config_dir):
        """Test storage initialization creates directory."""
        storage = OAuthStorage(config_dir=temp_config_dir)
        assert storage.config_dir.exists()
        assert storage.config_dir.is_dir()

    def test_storage_default_directory(self, mocker, tmp_path):
        """Test default config directory is used."""
        temp_home = str(tmp_path / "home" / "user")
        mock_expanduser = mocker.patch("os.path.expanduser", return_value=temp_home)
        storage = OAuthStorage()
        mock_expanduser.assert_called_once_with("~")
        assert str(storage.config_dir) == f"{temp_home}/.config/cyber-autoagent"

    def test_get_token_path_default_provider(self, storage):
        """Test token path for default provider."""
        path = storage.get_token_path()
        assert path.name == ".claude_oauth"
        assert path.parent == storage.config_dir

    def test_get_token_path_custom_provider(self, storage):
        """Test token path for custom provider."""
        path = storage.get_token_path(provider="custom")
        assert path.name == ".custom_oauth"

    def test_save_and_load_token(self, storage, sample_token):
        """Test saving and loading token."""
        storage.save_token(sample_token)
        loaded = storage.load_token()

        assert loaded is not None
        assert loaded.access_token == sample_token.access_token
        assert loaded.refresh_token == sample_token.refresh_token
        assert loaded.expires_at == sample_token.expires_at
        assert loaded.token_type == sample_token.token_type
        assert loaded.scope == sample_token.scope

    def test_save_token_with_custom_provider(self, storage, sample_token):
        """Test saving token with custom provider name."""
        storage.save_token(sample_token, provider="custom")
        loaded = storage.load_token(provider="custom")

        assert loaded is not None
        assert loaded.access_token == sample_token.access_token

    def test_save_token_creates_secure_permissions(self, storage, sample_token):
        """Test that saved token has secure permissions (600)."""
        storage.save_token(sample_token)
        token_path = storage.get_token_path()

        # Check file permissions
        stat_info = os.stat(token_path)
        permissions = oct(stat_info.st_mode)[-3:]
        assert permissions == "600"

    def test_save_token_atomic_write(self, storage, sample_token):
        """Test that token save uses atomic write."""
        # Save initial token
        storage.save_token(sample_token)

        # Modify and save again
        modified_token = OAuthToken(
            access_token="modified",
            refresh_token="modified",
            expires_at=sample_token.expires_at,
        )
        storage.save_token(modified_token)

        # Should have new token, not corrupted
        loaded = storage.load_token()
        assert loaded.access_token == "modified"

    def test_load_token_nonexistent(self, storage):
        """Test loading token when none exists."""
        loaded = storage.load_token()
        assert loaded is None

    def test_load_token_invalid_json(self, storage):
        """Test loading token with invalid JSON."""
        token_path = storage.get_token_path()
        token_path.write_text("invalid json")

        with pytest.raises(json.JSONDecodeError):
            storage.load_token()

    def test_delete_token(self, storage, sample_token):
        """Test deleting stored token."""
        storage.save_token(sample_token)
        assert storage.load_token() is not None

        storage.delete_token()
        assert storage.load_token() is None

    def test_delete_token_nonexistent(self, storage):
        """Test deleting token when none exists (should not raise)."""
        storage.delete_token()  # Should not raise

    def test_delete_token_custom_provider(self, storage, sample_token):
        """Test deleting token for custom provider."""
        storage.save_token(sample_token, provider="custom")
        storage.delete_token(provider="custom")
        assert storage.load_token(provider="custom") is None

    def test_has_valid_token_returns_true(self, storage, sample_token):
        """Test has_valid_token returns True for valid token."""
        storage.save_token(sample_token)
        assert storage.has_valid_token()

    def test_has_valid_token_returns_false_no_token(self, storage):
        """Test has_valid_token returns False when no token exists."""
        assert not storage.has_valid_token()

    def test_has_valid_token_returns_false_expired(self, storage):
        """Test has_valid_token returns False for expired token."""
        expired_token = OAuthToken(
            access_token="test",
            refresh_token="test",
            expires_at=int(time.time()) - 3600,  # Expired 1 hour ago
        )
        storage.save_token(expired_token)
        assert not storage.has_valid_token()

    def test_has_valid_token_with_buffer(self, storage):
        """Test has_valid_token respects buffer time."""
        # Token expires in 3 minutes
        soon_expiring_token = OAuthToken(
            access_token="test",
            refresh_token="test",
            expires_at=int(time.time()) + 180,
        )
        storage.save_token(soon_expiring_token)

        # With 5 minute buffer, should be invalid
        assert not storage.has_valid_token(buffer_minutes=5)
        # With 1 minute buffer, should be valid
        assert storage.has_valid_token(buffer_minutes=1)

    def test_multiple_providers(self, storage, sample_token):
        """Test storing tokens for multiple providers."""
        token1 = OAuthToken(
            access_token="provider1",
            refresh_token="refresh1",
            expires_at=int(time.time()) + 3600,
        )
        token2 = OAuthToken(
            access_token="provider2",
            refresh_token="refresh2",
            expires_at=int(time.time()) + 3600,
        )

        storage.save_token(token1, provider="provider1")
        storage.save_token(token2, provider="provider2")

        loaded1 = storage.load_token(provider="provider1")
        loaded2 = storage.load_token(provider="provider2")

        assert loaded1.access_token == "provider1"
        assert loaded2.access_token == "provider2"

    def test_token_isolation_between_providers(self, storage):
        """Test that deleting one provider's token doesn't affect others."""
        token1 = OAuthToken(
            access_token="provider1",
            refresh_token="refresh1",
            expires_at=int(time.time()) + 3600,
        )
        token2 = OAuthToken(
            access_token="provider2",
            refresh_token="refresh2",
            expires_at=int(time.time()) + 3600,
        )

        storage.save_token(token1, provider="provider1")
        storage.save_token(token2, provider="provider2")

        storage.delete_token(provider="provider1")

        assert storage.load_token(provider="provider1") is None
        assert storage.load_token(provider="provider2") is not None
