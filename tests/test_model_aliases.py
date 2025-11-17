#!/usr/bin/env python3
"""
Test script to validate Anthropic model aliases work correctly.

This verifies that:
1. -latest aliases are supported by Anthropic API
2. They resolve to actual model versions
3. Response metadata shows which model was used
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_model_alias(model_id: str) -> dict:
    """Test a model alias and return metadata.

    Args:
        model_id: Model ID to test (e.g., claude-opus-4-latest)

    Returns:
        Dict with test results
    """
    print(f"\n{'='*70}")
    print(f"Testing model: {model_id}")
    print('='*70)

    try:
        from modules.models.anthropic_oauth_model import AnthropicOAuthModel

        # Create model
        print(f"Creating model instance...")
        model = AnthropicOAuthModel(
            model_id=model_id,
            temperature=0.7,
            max_tokens=50,
        )

        print(f"✅ Model instance created successfully")

        # Send test request
        print(f"Sending test request...")
        messages = [
            {"role": "user", "content": "Say 'test' and nothing else"}
        ]

        response = model(messages)

        # Extract metadata
        actual_model = response.model
        response_text = response.content[0].text
        usage = response.usage

        print(f"\n✅ Request successful!")
        print(f"   Requested model: {model_id}")
        print(f"   Actual model used: {actual_model}")
        print(f"   Response: {response_text}")
        print(f"   Usage: {usage.input_tokens} in, {usage.output_tokens} out")

        # Check if alias resolved to a specific version
        if model_id.endswith("-latest"):
            if actual_model == model_id:
                print(f"   ⚠️  Warning: Model returned same ID (alias might not resolve)")
            else:
                print(f"   ✅ Alias resolved: {model_id} → {actual_model}")

        return {
            "success": True,
            "requested": model_id,
            "actual": actual_model,
            "response": response_text,
            "usage": usage,
        }

    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        import traceback
        traceback.print_exc()

        return {
            "success": False,
            "requested": model_id,
            "error": str(e),
        }


def main():
    """Run model alias tests."""
    print("\n" + "="*70)
    print("ANTHROPIC MODEL ALIAS VALIDATION")
    print("="*70)

    # Test different model aliases
    test_models = [
        # Test -latest aliases
        ("claude-opus-4-latest", "Latest Opus 4 alias"),
        ("claude-sonnet-4-latest", "Latest Sonnet 4 alias"),
        ("claude-3-5-haiku-latest", "Latest Haiku alias"),

        # Test specific versions for comparison
        ("claude-opus-4-20250514", "Specific Opus version"),
        ("claude-3-haiku-20240307", "Specific Haiku version"),
    ]

    results = []

    for model_id, description in test_models:
        print(f"\n{'='*70}")
        print(f"Test: {description}")
        result = test_model_alias(model_id)
        results.append(result)

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70 + "\n")

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")

    if successful:
        print("\n📊 Model Resolution:")
        for result in successful:
            requested = result["requested"]
            actual = result["actual"]
            if requested != actual:
                print(f"   {requested} → {actual} ✅")
            else:
                print(f"   {requested} (no alias resolution)")

    if failed:
        print("\n❌ Failed Tests:")
        for result in failed:
            print(f"   {result['requested']}: {result.get('error', 'Unknown error')}")

    # Validation
    print("\n" + "="*70)
    print("VALIDATION")
    print("="*70 + "\n")

    # Check if -latest aliases work
    latest_tests = [r for r in successful if "-latest" in r["requested"]]
    if latest_tests:
        # Check if any resolved to different versions
        resolved = [r for r in latest_tests if r["requested"] != r["actual"]]
        if resolved:
            print("✅ VALIDATED: -latest aliases are supported and working!")
            print("   They resolve to specific model versions as expected.")
            print("\n   Examples:")
            for r in resolved[:3]:  # Show first 3
                print(f"   - {r['requested']} → {r['actual']}")
        else:
            print("⚠️  WARNING: -latest aliases accepted but don't resolve to versions")
            print("   This might mean:")
            print("   1. The API treats them as literal model IDs")
            print("   2. The response doesn't show the resolved version")
            print("   3. The aliases need to be used differently")
    else:
        print("❌ FAILED: Could not test -latest aliases")

    # Check if specific versions work
    specific_tests = [r for r in successful if not "-latest" in r["requested"]]
    if specific_tests:
        print(f"\n✅ Specific versions work: {len(specific_tests)} tested")

    return 0 if len(failed) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
