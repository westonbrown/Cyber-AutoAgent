"""Anthropic OAuth authentication flow.

This module implements OAuth authentication for Anthropic's API, allowing
usage to be billed against Claude Max unlimited quota instead of per-token API billing.
"""
import base64
import hashlib
import json
import secrets
import subprocess
import time
import urllib.parse
from typing import Optional, Tuple

import requests

from .oauth_storage import OAuthStorage, OAuthToken

# OAuth configuration (from Claude Code client)
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
AUTH_URL = "https://claude.ai/oauth/authorize"
TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"
REDIRECT_URL = "https://console.anthropic.com/oauth/code/callback"
SCOPES = ["org:create_api_key", "user:profile", "user:inference"]


def generate_pkce() -> Tuple[str, str]:
    """Generate PKCE code verifier and challenge.

    Returns:
        Tuple of (verifier, challenge)
    """
    # Generate 32 random bytes
    verifier_bytes = secrets.token_bytes(32)
    verifier = base64.urlsafe_b64encode(verifier_bytes).decode("utf-8").rstrip("=")

    # Create challenge from verifier
    challenge_bytes = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(challenge_bytes).decode("utf-8").rstrip("=")

    return verifier, challenge


def open_browser(url: str) -> None:
    """Attempt to open URL in default browser.

    Args:
        url: URL to open
    """
    commands = [
        ["xdg-open", url],  # Linux
        ["open", url],  # macOS
        ["cmd", "/c", "start", url],  # Windows
    ]

    for cmd in commands:
        try:
            subprocess.run(cmd, check=False, capture_output=True)
            return
        except (subprocess.SubprocessError, FileNotFoundError):
            continue


def run_oauth_flow(provider: str = "claude") -> str:
    """Execute OAuth authorization flow and return access token.

    Args:
        provider: Provider identifier (default: claude)

    Returns:
        Access token

    Raises:
        ValueError: If authorization code cannot be extracted
        Exception: If token exchange fails
    """
    storage = OAuthStorage()

    # Check if we have an existing valid token
    existing_token = storage.load_token(provider)
    if existing_token and not existing_token.is_expired(5):
        return existing_token.access_token

    # If expired, try refresh first
    if existing_token and existing_token.refresh_token:
        try:
            return refresh_token(provider)
        except Exception as e:
            print(f"Token refresh failed: {e}")
            print("Starting new OAuth flow...")

    # Generate PKCE parameters
    verifier, challenge = generate_pkce()

    # Build authorization URL
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URL,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": verifier,
    }

    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    # Open browser and prompt user
    print("\n" + "=" * 70)
    print("ANTHROPIC OAUTH AUTHENTICATION")
    print("=" * 70)
    print("\nOpening your browser for authentication...")
    print(f"\nIf it doesn't open automatically, visit:\n{auth_url}\n")
    open_browser(auth_url)

    print("After authorizing, paste the full URL or just the code here:")
    code_input = input("Authorization code: ").strip()

    # Extract code from full URL if needed
    if code_input.startswith("http"):
        parsed = urllib.parse.urlparse(code_input)
        code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]
        if not code and "#" in code_input:
            # Handle fragment format
            code = code_input.split("code=")[1].split("&")[0] if "code=" in code_input else None
    else:
        code = code_input.split("#")[0] if "#" in code_input else code_input

    if not code:
        raise ValueError("Could not extract authorization code")

    # Exchange code for token
    token_data = {
        "code": code,
        "state": verifier,
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URL,
        "code_verifier": verifier,
    }

    response = requests.post(TOKEN_URL, json=token_data, headers={"Content-Type": "application/json"})

    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.status_code} - {response.text}")

    result = response.json()

    # Save token
    oauth_token = OAuthToken(
        access_token=result["access_token"],
        refresh_token=result.get("refresh_token", ""),
        expires_at=int(time.time()) + result.get("expires_in", 3600),
        token_type=result.get("token_type", "Bearer"),
        scope=result.get("scope", ""),
    )

    storage.save_token(oauth_token, provider)

    print("\n✓ Authentication successful!")
    print("=" * 70 + "\n")

    return oauth_token.access_token


def refresh_token(provider: str = "claude") -> str:
    """Refresh an expired OAuth token.

    Args:
        provider: Provider identifier (default: claude)

    Returns:
        New access token

    Raises:
        ValueError: If no refresh token is available
        Exception: If token refresh fails
    """
    storage = OAuthStorage()
    token = storage.load_token(provider)

    if not token or not token.refresh_token:
        raise ValueError("No refresh token available")

    refresh_data = {
        "grant_type": "refresh_token",
        "refresh_token": token.refresh_token,
        "client_id": CLIENT_ID,
    }

    response = requests.post(TOKEN_URL, json=refresh_data, headers={"Content-Type": "application/json"})

    if response.status_code != 200:
        raise Exception(f"Token refresh failed: {response.status_code} - {response.text}")

    result = response.json()

    # Update stored token
    new_token = OAuthToken(
        access_token=result["access_token"],
        refresh_token=result.get("refresh_token", token.refresh_token),  # Reuse old if not provided
        expires_at=int(time.time()) + result.get("expires_in", 3600),
        token_type=result.get("token_type", "Bearer"),
        scope=result.get("scope", token.scope),
    )

    storage.save_token(new_token, provider)

    return new_token.access_token


def get_valid_token(provider: str = "claude") -> str:
    """Get a valid access token, refreshing or re-authenticating if needed.

    Args:
        provider: Provider identifier (default: claude)

    Returns:
        Valid access token
    """
    storage = OAuthStorage()
    token = storage.load_token(provider)

    # No token exists
    if not token:
        return run_oauth_flow(provider)

    # Token expired
    if token.is_expired(5):
        try:
            return refresh_token(provider)
        except Exception:
            # Refresh failed, re-authenticate
            print("Token refresh failed. Re-authenticating...")
            return run_oauth_flow(provider)

    # Token still valid
    return token.access_token
