# Authentication Module

This module handles OAuth authentication for Anthropic's API, enabling billing against Claude Max unlimited quota instead of per-token API usage.

## Components

### `oauth_storage.py`
Persistent storage for OAuth tokens with secure permissions (0600).

**Classes:**
- `OAuthToken`: Dataclass for token metadata (access_token, refresh_token, expires_at)
- `OAuthStorage`: Token persistence in `~/.config/cyber-autoagent/.claude_oauth`

**Features:**
- Atomic file writes for safety
- Token expiry checking with configurable buffer
- Secure permissions (owner read/write only)

### `anthropic_oauth.py`
OAuth authentication flow implementation.

**Functions:**
- `run_oauth_flow()`: Interactive OAuth flow with browser-based authentication
- `refresh_token()`: Refresh expired tokens
- `get_valid_token()`: Get valid token, auto-refreshing if needed
- `generate_pkce()`: Generate PKCE code verifier and challenge for security

**OAuth Configuration:**
- Client ID: `9d1c250a-e61b-44d9-88ed-5944d1962f5e` (Claude Code's official client)
- Auth URL: `https://claude.ai/oauth/authorize`
- Token URL: `https://console.anthropic.com/v1/oauth/token`
- Redirect URL: `https://console.anthropic.com/oauth/code/callback`
- Scopes: `org:create_api_key`, `user:profile`, `user:inference`

**Flow:**
1. Generate PKCE code verifier and challenge
2. Open browser with authorization URL
3. User authenticates and gets code
4. Exchange code for access_token + refresh_token
5. Store tokens securely
6. Auto-refresh when within 5 minutes of expiry
7. Re-authenticate if refresh fails (human-in-loop)

## Usage

```python
from modules.auth import get_valid_token

# Get valid token (will prompt for OAuth on first use)
token = get_valid_token("claude")

# Use in requests
headers = {
    "Authorization": f"Bearer {token}",
    "anthropic-beta": "oauth-2025-04-20",
    "User-Agent": "ai-sdk/anthropic",
}
```

## Security Notes

- Tokens stored with 0600 permissions (owner only)
- Uses PKCE for OAuth security
- Atomic file writes prevent corruption
- 5-minute expiry buffer for safety
- Auto-refresh prevents expired token errors

## Token Location

Tokens are stored in:
```
~/.config/cyber-autoagent/.claude_oauth
```

To revoke access, simply delete this file and re-authenticate.

## Integration with Anthropic SDK

The `AnthropicOAuthModel` in `src/modules/models/anthropic_oauth_model.py` integrates this authentication with the Anthropic SDK:

1. Fetches valid token via `get_valid_token()`
2. Creates Anthropic client with OAuth headers
3. Adds Claude Code spoofing system message
4. Auto-refreshes token before each request

This ensures all requests bill against Claude Max unlimited quota.
