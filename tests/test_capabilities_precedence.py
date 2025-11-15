"""Test unified precedence order for model capabilities."""

import os
import pytest

from modules.config.models.capabilities import (
    get_capabilities,
    get_model_input_limit,
    get_model_output_limit,
    get_model_pricing,
    ModelCapabilitiesResolver,
)


class TestCapabilitiesPrecedence:
    """Validate models.dev takes precedence over LiteLLM for capabilities."""

    def setup_method(self):
        ModelCapabilitiesResolver.capabilities.cache_clear()

    def test_moonshot_kimi_k2_reasoning_via_models_dev(self):
        """Verify moonshot/kimi-k2-thinking uses models.dev data."""
        caps = get_capabilities("litellm", "moonshot/kimi-k2-thinking")
        assert caps.supports_reasoning is True, "Should detect reasoning via models.dev"

    def test_azure_gpt5_reasoning_via_models_dev(self):
        """Verify azure/gpt-5 uses models.dev data."""
        caps = get_capabilities("litellm", "azure/gpt-5")
        assert caps.supports_reasoning is True

    def test_claude_sonnet_45_reasoning(self):
        """Verify Claude Sonnet 4.5 detected correctly."""
        caps = get_capabilities("bedrock", "claude-sonnet-4-5-20250929")
        assert caps.supports_reasoning is True

    def test_env_override_allows_reasoning(self):
        """Verify CYBER_REASONING_ALLOW forces reasoning support."""
        os.environ["CYBER_REASONING_ALLOW"] = "test-model-xyz"
        ModelCapabilitiesResolver.capabilities.cache_clear()

        caps = get_capabilities("litellm", "test-model-xyz")
        assert caps.supports_reasoning is True

        del os.environ["CYBER_REASONING_ALLOW"]
        ModelCapabilitiesResolver.capabilities.cache_clear()

    def test_env_override_denies_reasoning(self):
        """Verify CYBER_REASONING_DENY disables reasoning support."""
        os.environ["CYBER_REASONING_DENY"] = "gpt-5"
        ModelCapabilitiesResolver.capabilities.cache_clear()

        caps = get_capabilities("litellm", "azure/gpt-5")
        assert caps.supports_reasoning is False

        del os.environ["CYBER_REASONING_DENY"]
        ModelCapabilitiesResolver.capabilities.cache_clear()


class TestTokenLimitPrecedence:
    """Validate models.dev used for token limits."""

    def test_moonshot_context_limit_from_models_dev(self):
        """Verify context limit retrieved from models.dev."""
        limit = get_model_input_limit("moonshot/kimi-k2-thinking")
        assert limit is not None
        assert limit > 200000, "Kimi K2 should have large context window"

    def test_azure_gpt5_context_limit(self):
        """Verify GPT-5 context limit from models.dev."""
        limit = get_model_input_limit("azure/gpt-5")
        assert limit == 272000, "GPT-5 has 272K context window"

    def test_output_limit_from_models_dev(self):
        """Verify output limit retrieved from models.dev."""
        limit = get_model_output_limit("azure/gpt-5")
        assert limit is not None
        assert limit > 100000, "GPT-5 should have large output limit"

    def test_output_limit_env_override_reasoning(self):
        """Verify MAX_COMPLETION_TOKENS (UI reasoning models) overrides models.dev."""
        os.environ["MAX_COMPLETION_TOKENS"] = "50000"

        limit = get_model_output_limit("azure/gpt-5")
        assert limit == 50000, "MAX_COMPLETION_TOKENS should override models.dev"

        del os.environ["MAX_COMPLETION_TOKENS"]

    def test_output_limit_env_override_general(self):
        """Verify MAX_TOKENS (UI general setting) overrides models.dev."""
        os.environ["MAX_TOKENS"] = "60000"

        limit = get_model_output_limit("azure/gpt-5")
        assert limit == 60000, "MAX_TOKENS should override models.dev"

        del os.environ["MAX_TOKENS"]

    def test_output_limit_precedence_order(self):
        """Verify correct precedence: MAX_COMPLETION_TOKENS > MAX_TOKENS."""
        os.environ["MAX_COMPLETION_TOKENS"] = "50000"
        os.environ["MAX_TOKENS"] = "60000"

        limit = get_model_output_limit("azure/gpt-5")
        assert limit == 50000, "MAX_COMPLETION_TOKENS should have highest precedence"

        del os.environ["MAX_COMPLETION_TOKENS"]

        limit = get_model_output_limit("azure/gpt-5")
        assert limit == 60000, "MAX_TOKENS should be second priority"

        del os.environ["MAX_TOKENS"]


class TestPricingSupport:
    """Validate pricing data from models.dev."""

    def test_get_pricing_for_known_model(self):
        """Verify pricing retrieved from models.dev."""
        pricing = get_model_pricing("azure/gpt-5")
        assert pricing is not None
        assert len(pricing) == 2
        input_cost, output_cost = pricing
        assert input_cost > 0, "Should have input cost"
        assert output_cost > 0, "Should have output cost"

    def test_get_pricing_for_moonshot(self):
        """Verify pricing for Moonshot models."""
        pricing = get_model_pricing("moonshot/kimi-k2-thinking")
        assert pricing is not None
        input_cost, output_cost = pricing
        assert input_cost == 0.6, "Kimi K2 input: $0.60/M"
        assert output_cost == 2.5, "Kimi K2 output: $2.50/M"

    def test_get_pricing_unknown_model(self):
        """Verify unknown model returns None."""
        pricing = get_model_pricing("unknown/fake-model")
        assert pricing is None


class TestPrecedenceOrder:
    """Validate precedence order across all parameters."""

    def setup_method(self):
        ModelCapabilitiesResolver.capabilities.cache_clear()

    def test_models_dev_preferred_over_litellm(self):
        """Verify models.dev takes precedence over LiteLLM."""
        # moonshot/kimi-k2-thinking:
        # - models.dev says: reasoning=True
        # - LiteLLM says: reasoning=False
        # - Should use models.dev
        caps = get_capabilities("litellm", "moonshot/kimi-k2-thinking")
        assert caps.supports_reasoning is True, "models.dev should win"

    def test_static_patterns_fallback(self):
        """Verify static patterns work when models.dev unavailable."""
        # Test with model that might not be in models.dev
        caps = get_capabilities("bedrock", "claude-4-opus")
        # Static pattern should detect opus models
        assert caps.supports_reasoning is True

    def test_env_override_highest_precedence(self):
        """Verify ENV overrides everything else."""
        os.environ["CYBER_REASONING_DENY"] = "kimi"
        ModelCapabilitiesResolver.capabilities.cache_clear()

        # Even though models.dev says True, ENV should force False
        caps = get_capabilities("litellm", "moonshot/kimi-k2-thinking")
        assert caps.supports_reasoning is False, "ENV override highest precedence"

        del os.environ["CYBER_REASONING_DENY"]
        ModelCapabilitiesResolver.capabilities.cache_clear()

    def test_multiple_models_consistent(self):
        """Verify precedence works consistently across multiple models."""
        test_cases = [
            ("bedrock", "claude-sonnet-4-5", True),
            ("litellm", "azure/gpt-5", True),
            ("litellm", "moonshot/kimi-k2-thinking", True),
        ]

        for provider, model, expected_reasoning in test_cases:
            caps = get_capabilities(provider, model)
            assert (
                caps.supports_reasoning == expected_reasoning
            ), f"{model} reasoning should be {expected_reasoning}"
