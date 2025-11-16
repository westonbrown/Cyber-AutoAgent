#!/usr/bin/env python3
"""
Verification script to test OAuth billing against Claude Max.

This script helps verify that OAuth authentication bills against Claude Max
unlimited quota instead of API credits.

Usage:
    python tests/verify_oauth_billing.py
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from modules.auth import get_valid_token
from modules.auth.oauth_storage import OAuthStorage


def check_oauth_token():
    """Check if OAuth token exists and is valid."""
    print("\n" + "=" * 70)
    print("OAUTH TOKEN STATUS")
    print("=" * 70 + "\n")

    storage = OAuthStorage()
    token = storage.load_token("claude")

    if not token:
        print("❌ No OAuth token found")
        print("   Run the agent with --provider anthropic_oauth to authenticate")
        return False

    print(f"✅ OAuth token found")
    print(f"   Token type: {token.token_type}")
    print(f"   Scopes: {token.scope}")
    print(f"   Expires at: {token.expires_at}")
    print(f"   Is expired: {token.is_expired(5)}")

    if token.is_expired(5):
        print("\n⚠️  Token is expired or will expire soon")
        print("   Will auto-refresh on next use")
    else:
        print("\n✅ Token is valid")

    # Check token file permissions
    token_path = storage.get_token_path("claude")
    if token_path.exists():
        import stat
        mode = oct(stat.S_IMODE(token_path.stat().st_mode))
        print(f"   File permissions: {mode} (should be 0o600)")
        if mode == '0o600':
            print("   ✅ Permissions are secure")
        else:
            print("   ⚠️  Permissions should be 0o600 for security")

    return True


def verify_oauth_headers():
    """Verify OAuth headers are set correctly."""
    print("\n" + "=" * 70)
    print("OAUTH HEADERS VERIFICATION")
    print("=" * 70 + "\n")

    try:
        from modules.models.anthropic_oauth_model import AnthropicOAuthModel

        # Create model instance (will prompt for auth if needed)
        print("Creating OAuth model instance...")
        model = AnthropicOAuthModel(
            model_id="claude-3-haiku-20240307",
            temperature=0.7,
            max_tokens=100,
        )

        print("\n✅ OAuth model created successfully")
        print(f"   Model ID: {model.model_id}")
        print(f"   Access token (first 20 chars): {model.access_token[:20]}...")

        # Check client headers
        headers = model.client.default_headers
        print("\n📋 Client Headers:")
        for key, value in headers.items():
            if key == "Authorization":
                print(f"   {key}: Bearer {value[7:27]}... ✅")
            else:
                print(f"   {key}: {value}")

        # Verify required headers
        required_headers = {
            "Authorization": lambda v: v.startswith("Bearer "),
            "anthropic-beta": lambda v: "oauth-2025-04-20" in v,
            "User-Agent": lambda v: v == "ai-sdk/anthropic",
        }

        all_good = True
        for header, check in required_headers.items():
            if header not in headers:
                print(f"   ❌ Missing header: {header}")
                all_good = False
            elif not check(headers[header]):
                print(f"   ❌ Invalid header value: {header}")
                all_good = False

        if all_good:
            print("\n✅ All required OAuth headers are present and correct")
        else:
            print("\n❌ Some OAuth headers are missing or incorrect")

        return all_good

    except Exception as e:
        print(f"\n❌ Error creating OAuth model: {e}")
        return False


def test_simple_request():
    """Test a simple API request with OAuth."""
    print("\n" + "=" * 70)
    print("SIMPLE REQUEST TEST")
    print("=" * 70 + "\n")

    try:
        from modules.models.anthropic_oauth_model import AnthropicOAuthModel

        print("Creating OAuth model...")
        model = AnthropicOAuthModel(
            model_id="claude-3-haiku-20240307",
            temperature=0.7,
            max_tokens=50,
        )

        print("Sending test request...")
        messages = [
            {"role": "user", "content": "Say 'OAuth test successful' and nothing else."}
        ]

        response = model(messages)

        print("\n✅ Request successful!")
        print(f"   Response: {response.content[0].text}")
        print(f"   Model: {response.model}")
        print(f"   Usage: {response.usage.input_tokens} in, {response.usage.output_tokens} out")

        print("\n📊 Check your Claude.ai account settings:")
        print("   https://claude.ai/settings/account")
        print("   Look for usage under Claude Max/Pro (NOT API credits)")

        return True

    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def compare_billing_methods():
    """Instructions for comparing OAuth vs API key billing."""
    print("\n" + "=" * 70)
    print("BILLING COMPARISON GUIDE")
    print("=" * 70 + "\n")

    print("To verify OAuth bills against Claude Max instead of API:")
    print()
    print("1. Check Claude Max Usage (SHOULD increment with OAuth):")
    print("   URL: https://claude.ai/settings/account")
    print("   Look for: Usage statistics under 'Claude Pro' or 'Claude Max'")
    print("   Expected: API calls show up here when using OAuth")
    print()
    print("2. Check API Credits (should NOT increment with OAuth):")
    print("   URL: https://console.anthropic.com/settings/usage")
    print("   Look for: API usage and costs")
    print("   Expected: This should NOT increment when using --provider anthropic_oauth")
    print()
    print("3. Compare with API Key method:")
    print("   # Using API key (bills against API credits)")
    print("   export ANTHROPIC_API_KEY=sk-ant-...")
    print("   python -c 'from anthropic import Anthropic; c = Anthropic(); c.messages.create(...)'")
    print()
    print("   # Using OAuth (bills against Claude Max)")
    print("   python src/cyberautoagent.py --provider anthropic_oauth ...")
    print()
    print("4. Rate Limits Differ:")
    print("   - API Key: Tier-based limits (varies by API plan)")
    print("   - Claude Max: Same limits as claude.ai web interface")
    print()


def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("ANTHROPIC OAUTH BILLING VERIFICATION")
    print("=" * 70)

    results = []

    # Check 1: Token status
    results.append(("OAuth Token Status", check_oauth_token()))

    # Check 2: Headers
    results.append(("OAuth Headers", verify_oauth_headers()))

    # Check 3: Simple request
    results.append(("Simple Request Test", test_simple_request()))

    # Display comparison guide
    compare_billing_methods()

    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70 + "\n")

    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check_name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n🎉 All checks passed!")
        print("\nNext steps:")
        print("1. Visit https://claude.ai/settings/account to see usage")
        print("2. Run actual operations with --provider anthropic_oauth")
        print("3. Verify usage shows under Claude Max, not API credits")
    else:
        print("\n⚠️  Some checks failed. Review the output above.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
