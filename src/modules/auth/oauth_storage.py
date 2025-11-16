"""OAuth token storage and management."""
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


@dataclass
class OAuthToken:
    """OAuth token with metadata."""

    access_token: str
    refresh_token: str
    expires_at: int  # Unix timestamp
    token_type: str = "Bearer"
    scope: str = ""

    def is_expired(self, buffer_minutes: int = 5) -> bool:
        """Check if token is expired or will expire soon.

        Args:
            buffer_minutes: Minutes before expiry to consider token expired

        Returns:
            True if token is expired or will expire within buffer time
        """
        if not self.expires_at:
            return True
        buffer_seconds = buffer_minutes * 60
        return time.time() + buffer_seconds >= self.expires_at


class OAuthStorage:
    """Persistent storage for OAuth tokens."""

    def __init__(self, config_dir: Optional[str] = None):
        """Initialize OAuth storage.

        Args:
            config_dir: Directory to store tokens (default: ~/.config/cyber-autoagent)
        """
        if config_dir is None:
            config_dir = os.path.join(os.path.expanduser("~"), ".config", "cyber-autoagent")
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def get_token_path(self, provider: str = "claude") -> Path:
        """Get path to token file.

        Args:
            provider: Provider identifier (default: claude)

        Returns:
            Path to token file
        """
        return self.config_dir / f".{provider}_oauth"

    def save_token(self, token: OAuthToken, provider: str = "claude") -> None:
        """Save token to disk with secure permissions.

        Args:
            token: OAuth token to save
            provider: Provider identifier (default: claude)
        """
        token_path = self.get_token_path(provider)
        temp_path = token_path.with_suffix(".tmp")

        # Write to temp file
        with open(temp_path, "w") as f:
            json.dump(asdict(token), f, indent=2)

        # Set secure permissions (owner read/write only)
        os.chmod(temp_path, 0o600)

        # Atomic rename
        temp_path.replace(token_path)

    def load_token(self, provider: str = "claude") -> Optional[OAuthToken]:
        """Load token from disk.

        Args:
            provider: Provider identifier (default: claude)

        Returns:
            OAuth token if exists, None otherwise
        """
        token_path = self.get_token_path(provider)

        if not token_path.exists():
            return None

        with open(token_path) as f:
            data = json.load(f)

        return OAuthToken(**data)

    def delete_token(self, provider: str = "claude") -> None:
        """Delete stored token.

        Args:
            provider: Provider identifier (default: claude)
        """
        token_path = self.get_token_path(provider)
        if token_path.exists():
            token_path.unlink()

    def has_valid_token(self, provider: str = "claude", buffer_minutes: int = 5) -> bool:
        """Check if a valid token exists.

        Args:
            provider: Provider identifier (default: claude)
            buffer_minutes: Minutes before expiry to consider token invalid

        Returns:
            True if valid token exists
        """
        token = self.load_token(provider)
        if token is None:
            return False
        return not token.is_expired(buffer_minutes)
