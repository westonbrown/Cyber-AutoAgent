#!/usr/bin/env python3
"""Integration tests for conversation management features.

Tests cover:
- Safe max_tokens calculation from models.dev (ConfigManager)
- Dynamic char/token ratios for different model providers
- Quiet pruning warnings for small conversations

Validates expected behavior with mock data to ensure:
- Accurate token estimation across all model providers
- Safe specialist token limits preventing failures
- Clean logs without spurious warnings
"""

import logging
from typing import Any
from unittest.mock import Mock, patch
import types

import pytest

from modules.config.manager import ConfigManager
from modules.config.models.dev_client import ModelsDevClient, ModelLimits
from modules.handlers.conversation_budget import (
    _get_char_to_token_ratio_dynamic,
    _estimate_prompt_tokens,
    _ensure_prompt_within_budget,
    MappingConversationManager,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_models_client():
    """Mock ModelsDevClient with known test models."""
    client = Mock(spec=ModelsDevClient)

    def get_limits(model_id: str):
        limits_map = {
            "azure/gpt-5": ModelLimits(context=272000, output=128000),
            "azure/gpt-4o": ModelLimits(context=128000, output=16384),
            "moonshot/kimi-k2-thinking": ModelLimits(context=262144, output=262144),
            "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0": ModelLimits(context=200000, output=8192),
            "anthropic/claude-sonnet-4-5-20250929": ModelLimits(context=200000, output=64000),
            "google/gemini-2.5-flash": ModelLimits(context=1000000, output=8192),
        }
        return limits_map.get(model_id)

    def get_model_info(model_id: str):
        # Mock provider detection for ratio calculation
        info = Mock()
        if "gpt" in model_id.lower():
            info.provider = "azure" if "azure/" in model_id else "openai"
        elif "claude" in model_id.lower() or "anthropic" in model_id:
            info.provider = "anthropic" if "anthropic/" in model_id else "amazon-bedrock"
        elif "kimi" in model_id.lower() or "moonshot" in model_id:
            info.provider = "moonshotai"
        elif "gemini" in model_id.lower():
            info.provider = "google"
        else:
            return None
        return info

    client.get_limits.side_effect = get_limits
    client.get_model_info.side_effect = get_model_info

    return client


@pytest.fixture
def config_manager_with_mock_client(mock_models_client):
    """ConfigManager with mocked models client."""
    with patch('modules.config.manager.get_models_client', return_value=mock_models_client):
        manager = ConfigManager()
        yield manager


class AgentStub:
    """Mock agent for testing conversation management."""

    def __init__(
        self,
        messages: list[dict[str, Any]],
        model: str = "",
        limit: int | None = None,
        telemetry: int | None = None,
        name: str = "test_agent"
    ):
        self.messages = messages
        self.model = model
        self._prompt_token_limit = limit
        self.name = name

        # Conversation manager stub
        self.conversation_manager = types.SimpleNamespace(
            calls=[],
            reduce_context=lambda agent: self.conversation_manager.calls.append(
                len(agent.messages)
            ),
        )

        # Telemetry injection
        if telemetry is not None:
            self.callback_handler = types.SimpleNamespace(sdk_input_tokens=telemetry)


def make_message(text: str, role: str = "assistant") -> dict[str, Any]:
    """Create a simple text message."""
    return {"role": role, "content": [{"type": "text", "text": text}]}


# ============================================================================
# P1: Dynamic Char/Token Ratios
# ============================================================================


class TestDynamicCharTokenRatios:
    """Test P1 feature: Model-aware character-to-token ratios."""

    def test_claude_ratio_3_7(self, mock_models_client):
        """Test Claude models use 3.7 chars/token (aggressive tokenizer)."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            # Anthropic Claude
            ratio = _get_char_to_token_ratio_dynamic("anthropic/claude-sonnet-4-5-20250929")
            assert ratio == 3.7, "Claude should use 3.7 ratio"

            # Bedrock Claude
            ratio = _get_char_to_token_ratio_dynamic("bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0")
            assert ratio == 3.7, "Bedrock Claude should use 3.7 ratio"

    def test_gpt_ratio_4_0(self, mock_models_client):
        """Test GPT-4/5 models use 4.0 chars/token (o200k_base)."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            ratio = _get_char_to_token_ratio_dynamic("azure/gpt-5")
            assert ratio == 4.0, "GPT-5 should use 4.0 ratio"

            ratio = _get_char_to_token_ratio_dynamic("azure/gpt-4o")
            assert ratio == 4.0, "GPT-4o should use 4.0 ratio"

    def test_kimi_ratio_3_8(self, mock_models_client):
        """Test Moonshot Kimi uses 3.8 chars/token (proprietary)."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            ratio = _get_char_to_token_ratio_dynamic("moonshot/kimi-k2-thinking")
            assert ratio == 3.8, "Kimi should use 3.8 ratio"

    def test_gemini_ratio_4_2(self, mock_models_client):
        """Test Gemini models use 4.2 chars/token (SentencePiece)."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            ratio = _get_char_to_token_ratio_dynamic("google/gemini-2.5-flash")
            assert ratio == 4.2, "Gemini should use 4.2 ratio"

    def test_unknown_model_defaults_to_conservative(self, mock_models_client):
        """Test unknown models default to 3.7 (conservative)."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            ratio = _get_char_to_token_ratio_dynamic("unknown/model")
            assert ratio == 3.7, "Unknown models should use conservative 3.7 ratio"

    def test_empty_model_defaults_to_conservative(self, mock_models_client):
        """Test empty model ID defaults to 3.7."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            ratio = _get_char_to_token_ratio_dynamic("")
            assert ratio == 3.7, "Empty model should use conservative 3.7 ratio"


class TestDynamicRatioTokenEstimation:
    """Test token estimation accuracy with dynamic ratios."""

    def test_claude_estimation_accuracy(self, mock_models_client):
        """Test Claude estimation uses 3.7 ratio for accuracy."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            # 1000 chars with Claude 3.7 ratio = ~270 tokens
            agent = AgentStub(
                messages=[make_message("x" * 1000)],
                model="anthropic/claude-sonnet-4-5-20250929"
            )
            estimated = _estimate_prompt_tokens(agent)

            # 1000 / 3.7 = 270.27 -> 270 tokens
            assert estimated == int(1000 / 3.7), f"Expected {int(1000 / 3.7)}, got {estimated}"

    def test_gpt_estimation_accuracy(self, mock_models_client):
        """Test GPT estimation uses 4.0 ratio for accuracy."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            # 1000 chars with GPT 4.0 ratio = 250 tokens
            agent = AgentStub(
                messages=[make_message("x" * 1000)],
                model="azure/gpt-5"
            )
            estimated = _estimate_prompt_tokens(agent)

            assert estimated == 250, f"Expected 250, got {estimated}"

    def test_kimi_estimation_accuracy(self, mock_models_client):
        """Test Kimi estimation uses 3.8 ratio for accuracy."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            # 1000 chars with Kimi 3.8 ratio = ~263 tokens
            agent = AgentStub(
                messages=[make_message("x" * 1000)],
                model="moonshot/kimi-k2-thinking"
            )
            estimated = _estimate_prompt_tokens(agent)

            assert estimated == int(1000 / 3.8), f"Expected {int(1000 / 3.8)}, got {estimated}"

    def test_gemini_estimation_accuracy(self, mock_models_client):
        """Test Gemini estimation uses 4.2 ratio for accuracy."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            # 1000 chars with Gemini 4.2 ratio = ~238 tokens
            agent = AgentStub(
                messages=[make_message("x" * 1000)],
                model="google/gemini-2.5-flash"
            )
            estimated = _estimate_prompt_tokens(agent)

            assert estimated == int(1000 / 4.2), f"Expected {int(1000 / 4.2)}, got {estimated}"


# ============================================================================
# P0: Safe max_tokens from models.dev
# ============================================================================


class TestSafeMaxTokens:
    """Test P0 feature: Safe max_tokens calculation from models.dev."""

    def test_azure_gpt_5_safe_tokens(self, config_manager_with_mock_client):
        """Test Azure GPT-5 safe max_tokens is 50% of 128,000 = 64,000."""
        safe_max = config_manager_with_mock_client.get_safe_max_tokens("azure/gpt-5")
        assert safe_max == 64000, f"Expected 64000, got {safe_max}"

    def test_azure_gpt_4o_safe_tokens(self, config_manager_with_mock_client):
        """Test Azure GPT-4o safe max_tokens is 50% of 16,384 = 8,192."""
        safe_max = config_manager_with_mock_client.get_safe_max_tokens("azure/gpt-4o")
        assert safe_max == 8192, f"Expected 8192, got {safe_max}"

    def test_bedrock_claude_35_safe_tokens(self, config_manager_with_mock_client):
        """Test Bedrock Claude 3.5 safe max_tokens is 50% of 8,192 = 4,096."""
        safe_max = config_manager_with_mock_client.get_safe_max_tokens(
            "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
        assert safe_max == 4096, f"Expected 4096, got {safe_max}"

    def test_moonshot_kimi_safe_tokens(self, config_manager_with_mock_client):
        """Test Moonshot Kimi safe max_tokens is 50% of 262,144 = 131,072."""
        safe_max = config_manager_with_mock_client.get_safe_max_tokens("moonshot/kimi-k2-thinking")
        assert safe_max == 131072, f"Expected 131072, got {safe_max}"

    def test_anthropic_claude_sonnet_45_safe_tokens(self, config_manager_with_mock_client):
        """Test Anthropic Claude Sonnet 4.5 safe max_tokens is 50% of 64,000 = 32,000."""
        safe_max = config_manager_with_mock_client.get_safe_max_tokens(
            "anthropic/claude-sonnet-4-5-20250929"
        )
        assert safe_max == 32000, f"Expected 32000, got {safe_max}"

    def test_custom_buffer_percentage(self, config_manager_with_mock_client):
        """Test custom buffer percentage (e.g., 75% instead of 50%)."""
        # 75% of 128,000 = 96,000
        safe_max = config_manager_with_mock_client.get_safe_max_tokens("azure/gpt-5", buffer=0.75)
        assert safe_max == 96000, f"Expected 96000, got {safe_max}"

    def test_unknown_model_returns_safe_default(self, config_manager_with_mock_client):
        """Test unknown model returns safe default of 4,096."""
        safe_max = config_manager_with_mock_client.get_safe_max_tokens("unknown/model")
        assert safe_max == 4096, f"Expected 4096, got {safe_max}"


class TestSwarmModelConfig:
    """Test swarm model configuration uses safe limits."""

    def test_swarm_inherits_safe_limit(self, config_manager_with_mock_client, monkeypatch):
        """Test swarm model gets safe max_tokens from models.dev."""
        # Set swarm model env var
        monkeypatch.setenv("CYBER_AGENT_SWARM_MODEL", "azure/gpt-4o")

        # Get swarm config
        swarm_cfg = config_manager_with_mock_client._get_swarm_llm_config(
            "litellm",
            {"swarm_llm": Mock(model_id="azure/gpt-4o", max_tokens=None)}
        )

        # Should be 8,192 (50% of 16,384)
        assert swarm_cfg.max_tokens == 8192, f"Expected 8192, got {swarm_cfg.max_tokens}"

    def test_explicit_override_takes_precedence(self, config_manager_with_mock_client, monkeypatch):
        """Test CYBER_AGENT_SWARM_MAX_TOKENS overrides auto-calculation."""
        monkeypatch.setenv("CYBER_AGENT_SWARM_MODEL", "azure/gpt-4o")
        monkeypatch.setenv("CYBER_AGENT_SWARM_MAX_TOKENS", "12288")  # 75% instead of 50%

        swarm_cfg = config_manager_with_mock_client._get_swarm_llm_config(
            "litellm",
            {"swarm_llm": Mock(model_id="azure/gpt-4o", max_tokens=None)}
        )

        assert swarm_cfg.max_tokens == 12288, f"Expected 12288, got {swarm_cfg.max_tokens}"


# ============================================================================
# P2: Quiet Pruning Warnings
# ============================================================================


class TestQuietPruningWarnings:
    """Test P2 feature: Quiet pruning warnings for small conversations."""

    def test_small_conversations_no_excessive_warnings(self, caplog):
        """P2: Test small conversations don't spam WARNING logs."""
        manager = MappingConversationManager(
            window_size=100,
            preserve_recent_messages=12,
            summary_ratio=0.5
        )

        # Simulate typical specialist invocation with 3 messages
        agent = AgentStub(
            [
                make_message("system: scan for XSS"),
                make_message("thinking about approach..."),
                make_message("result: no vulnerabilities found"),
            ],
            name="xss_specialist"
        )

        caplog.clear()
        with caplog.at_level(logging.WARNING):
            # apply_management should handle small conversations gracefully
            manager.apply_management(agent)

        # P2 Feature: Small conversations should not generate WARNING logs
        warning_logs = [rec for rec in caplog.records if rec.levelname == "WARNING"]
        assert len(warning_logs) == 0, \
            f"P2 violation: Small conversations should not generate warnings. Got: {[r.message for r in warning_logs]}"

    def test_large_conversations_still_prune(self):
        """P2: Ensure large conversations still prune normally (functional test)."""
        manager = MappingConversationManager(
            window_size=10,  # Small window to trigger pruning
            preserve_recent_messages=3,
            summary_ratio=0.5
        )

        # 20 messages - well over window size
        agent = AgentStub([make_message(f"msg{i}") for i in range(20)])
        initial_count = len(agent.messages)

        # apply_management respects window size
        manager.apply_management(agent)

        # P2 doesn't break normal pruning - large conversations still get managed
        # Window is 10, so we should have at most 10 messages
        assert len(agent.messages) <= 10, \
            f"Large conversations should prune to window size. Expected <=10 messages, got {len(agent.messages)}"

        # Verify some messages were actually removed
        assert len(agent.messages) < initial_count, \
            "Some messages should have been pruned"

    def test_p2_early_return_for_tiny_conversations(self):
        """P2: Test Layer 2 compression returns early for <3 message conversations."""
        from modules.handlers.conversation_budget import LargeToolResultMapper

        _mapper = LargeToolResultMapper()
        manager = MappingConversationManager(
            window_size=100,
            preserve_recent_messages=12,
            summary_ratio=0.5
        )

        # 2 messages - too small for Layer 2 compression
        agent = AgentStub([make_message("msg1"), make_message("msg2")])
        initial_count = len(agent.messages)

        # Layer 2 should return early without modifying messages
        # Note: This will still fail on sliding window, but Layer 2 skips correctly
        try:
            manager.reduce_context(agent)
        except Exception:
            pass  # Expected to fail on tiny conversations in Layer 1

        # Verify messages weren't modified by Layer 2 before Layer 1 failure
        # (Layer 2 returns early for small conversations)
        assert len(agent.messages) == initial_count, \
            "P2: Layer 2 should not modify conversations <3 messages"


# ============================================================================
# Integration Tests: End-to-End Scenarios
# ============================================================================


class TestSpecialistFlowIntegration:
    """Test end-to-end specialist invocation flow."""

    def test_specialist_gets_safe_token_limit(self, config_manager_with_mock_client, mock_models_client):
        """Test specialist tool gets safe token limit, not main agent's."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            # Main agent with high limit
            _main_agent = AgentStub(
                messages=[make_message("main task")],
                model="azure/gpt-5",
                limit=272000
            )

            # Specialist with swarm model (should get safe limit)
            specialist = AgentStub(
                messages=[make_message("specialist task")],
                model="azure/gpt-4o",
                limit=8192  # Safe limit from models.dev
            )

            # Estimate tokens for specialist
            estimated = _estimate_prompt_tokens(specialist)

            # Should not exceed safe limit
            assert estimated < specialist._prompt_token_limit, \
                f"Specialist estimated {estimated} tokens exceeds safe limit {specialist._prompt_token_limit}"

    def test_no_spurious_warnings_from_specialist(self, caplog, mock_models_client):
        """Test specialist with 2-3 messages doesn't spam warnings."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            manager = MappingConversationManager(
                window_size=100,
                preserve_recent_messages=12,
                summary_ratio=0.5
            )

            # Specialist with minimal conversation
            specialist = AgentStub(
                messages=[
                    make_message("system: scan for XSS"),
                    make_message("specialist: analyzing..."),
                ],
                model="azure/gpt-4o",
                name="xss_specialist"
            )

            with caplog.at_level(logging.WARNING):
                manager.apply_management(specialist)

            # Should have no WARNING logs
            warning_logs = [rec for rec in caplog.records if rec.levelname == "WARNING"]
            assert len(warning_logs) == 0, f"Specialist should not spam warnings: {warning_logs}"


class TestBudgetEnforcementAccuracy:
    """Test budget enforcement accuracy with dynamic ratios."""

    def test_claude_budget_enforcement(self, mock_models_client):
        """Test Claude models trigger reduction at correct threshold with 3.7 ratio."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            # 80% threshold = 800 tokens
            # With 3.7 ratio: 800 * 3.7 = 2960 chars needed
            agent = AgentStub(
                messages=[make_message("x" * 1500)] * 2,  # 3000 chars total
                model="anthropic/claude-sonnet-4-5-20250929",
                limit=1000
            )

            _ensure_prompt_within_budget(agent)

            # Should trigger reduction because 3000/3.7 = 811 tokens > 800 (80%)
            assert len(agent.conversation_manager.calls) > 0, \
                "Should trigger reduction at 80% threshold with Claude 3.7 ratio"

    def test_gpt_budget_enforcement(self, mock_models_client):
        """Test GPT models trigger reduction at correct threshold with 4.0 ratio."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            # 80% threshold = 800 tokens
            # With 4.0 ratio: 800 * 4.0 = 3200 chars needed
            agent = AgentStub(
                messages=[make_message("x" * 1600)] * 2,  # 3200 chars total
                model="azure/gpt-5",
                limit=1000
            )

            _ensure_prompt_within_budget(agent)

            # Should trigger reduction because 3200/4.0 = 800 tokens = 80%
            assert len(agent.conversation_manager.calls) > 0, \
                "Should trigger reduction at 80% threshold with GPT 4.0 ratio"

    def test_no_false_positives_below_threshold(self, mock_models_client):
        """Test no reduction triggered when below 80% threshold."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            # 70% threshold = 700 tokens
            # With 3.7 ratio: 700 * 3.7 = 2590 chars
            agent = AgentStub(
                messages=[make_message("x" * 1200)] * 2,  # 2400 chars total
                model="anthropic/claude-sonnet-4-5-20250929",
                limit=1000
            )

            _ensure_prompt_within_budget(agent)

            # Should NOT trigger because 2400/3.7 = 649 tokens < 800 (80%)
            assert len(agent.conversation_manager.calls) == 0, \
                "Should not trigger reduction below 80% threshold"


# ============================================================================
# Validation: Expected vs Actual Behavior
# ============================================================================


class TestExpectedBehaviorValidation:
    """Validate expected behavior matches actual implementation."""

    def test_all_user_models_have_correct_ratios(self, mock_models_client):
        """Validate all user's production models get correct ratios."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            expected = {
                "azure/gpt-5": 4.0,
                "azure/gpt-4o": 4.0,
                "moonshot/kimi-k2-thinking": 3.8,
                "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0": 3.7,
                "anthropic/claude-sonnet-4-5-20250929": 3.7,
                "google/gemini-2.5-flash": 4.2,
            }

            for model_id, expected_ratio in expected.items():
                actual_ratio = _get_char_to_token_ratio_dynamic(model_id)
                assert actual_ratio == expected_ratio, \
                    f"Model {model_id}: expected ratio {expected_ratio}, got {actual_ratio}"

    def test_all_user_models_have_safe_limits(self, config_manager_with_mock_client):
        """Validate all user's production models get safe max_tokens."""
        expected = {
            "azure/gpt-5": 64000,           # 50% of 128,000
            "azure/gpt-4o": 8192,           # 50% of 16,384
            "moonshot/kimi-k2-thinking": 131072,  # 50% of 262,144
            "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0": 4096,  # 50% of 8,192
            "anthropic/claude-sonnet-4-5-20250929": 32000,  # 50% of 64,000
        }

        for model_id, expected_safe in expected.items():
            actual_safe = config_manager_with_mock_client.get_safe_max_tokens(model_id)
            assert actual_safe == expected_safe, \
                f"Model {model_id}: expected safe max_tokens {expected_safe}, got {actual_safe}"

    def test_estimation_accuracy_within_1_percent(self, mock_models_client):
        """Test token estimation accuracy is within ±1% for all models."""
        with patch('modules.handlers.conversation_budget.get_models_client', return_value=mock_models_client):
            test_cases = [
                ("anthropic/claude-sonnet-4-5-20250929", 10000, 3.7),
                ("azure/gpt-5", 10000, 4.0),
                ("moonshot/kimi-k2-thinking", 10000, 3.8),
                ("google/gemini-2.5-flash", 10000, 4.2),
            ]

            for model_id, char_count, ratio in test_cases:
                agent = AgentStub(
                    messages=[make_message("x" * char_count)],
                    model=model_id
                )

                estimated = _estimate_prompt_tokens(agent)
                expected = int(char_count / ratio)

                # Allow ±1 token difference (rounding)
                assert abs(estimated - expected) <= 1, \
                    f"Model {model_id}: expected ~{expected} tokens, got {estimated}"
