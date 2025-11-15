"""Tests for models_dev_client module.

Tests cover:
- Model lookup with various ID formats
- Limit detection for known models
- Capability detection
- Pricing information
- Fuzzy matching and alias resolution
- Cache behavior
- Fallback to snapshot
- Edge cases and error handling
"""

import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from modules.config.models.dev_client import (
    ModelsDevClient,
    get_models_client,
)


# Test fixtures

@pytest.fixture
def mock_models_data():
    """Mock models.dev API response data."""
    return {
        "azure": {
            "name": "Azure OpenAI",
            "models": {
                "gpt-5": {
                    "name": "GPT-5",
                    "reasoning": True,
                    "tool_call": True,
                    "attachment": True,
                    "temperature": False,
                    "knowledge": "2024-09-30",
                    "release_date": "2025-08-07",
                    "last_updated": "2025-08-07",
                    "open_weights": False,
                    "cost": {
                        "input": 1.25,
                        "output": 10.00,
                        "cache_read": 0.13
                    },
                    "limit": {
                        "context": 272000,
                        "output": 128000
                    },
                    "modalities": {
                        "input": ["text", "image"],
                        "output": ["text"]
                    }
                },
                "gpt-4o": {
                    "name": "GPT-4o",
                    "reasoning": False,
                    "tool_call": True,
                    "attachment": True,
                    "temperature": True,
                    "knowledge": "2023-09",
                    "release_date": "2024-05-13",
                    "last_updated": "2024-05-13",
                    "open_weights": False,
                    "cost": {
                        "input": 2.50,
                        "output": 10.00,
                        "cache_read": 1.25
                    },
                    "limit": {
                        "context": 128000,
                        "output": 16384
                    },
                    "modalities": {
                        "input": ["text", "image"],
                        "output": ["text"]
                    }
                }
            }
        },
        "anthropic": {
            "name": "Anthropic",
            "models": {
                "claude-sonnet-4-5-20250929": {
                    "name": "Claude Sonnet 4.5",
                    "reasoning": True,
                    "tool_call": True,
                    "attachment": True,
                    "temperature": True,
                    "knowledge": "2025-07-31",
                    "release_date": "2025-09-29",
                    "last_updated": "2025-09-29",
                    "open_weights": False,
                    "cost": {
                        "input": 3.00,
                        "output": 15.00,
                        "cache_read": 0.30,
                        "cache_write": 3.75
                    },
                    "limit": {
                        "context": 200000,
                        "output": 64000
                    },
                    "modalities": {
                        "input": ["text", "image"],
                        "output": ["text"]
                    }
                }
            }
        },
        "amazon-bedrock": {
            "name": "Amazon Bedrock",
            "models": {
                "anthropic.claude-3-5-sonnet-20241022-v2:0": {
                    "name": "Claude Sonnet 3.5 v2",
                    "reasoning": False,
                    "tool_call": True,
                    "attachment": True,
                    "temperature": True,
                    "knowledge": "2024-04",
                    "release_date": "2024-10-22",
                    "last_updated": "2024-10-22",
                    "open_weights": False,
                    "cost": {
                        "input": 3.00,
                        "output": 15.00,
                        "cache_read": 0.30,
                        "cache_write": 3.75
                    },
                    "limit": {
                        "context": 200000,
                        "output": 8192
                    },
                    "modalities": {
                        "input": ["text", "image"],
                        "output": ["text"]
                    }
                }
            }
        },
        "moonshotai": {
            "name": "Moonshot AI",
            "models": {
                "kimi-k2-thinking": {
                    "name": "Kimi K2 Thinking",
                    "reasoning": True,
                    "tool_call": True,
                    "attachment": False,
                    "temperature": True,
                    "knowledge": "2024-08",
                    "release_date": "2025-11-06",
                    "last_updated": "2025-11-06",
                    "open_weights": True,
                    "cost": {
                        "input": 0.6,
                        "output": 2.5,
                        "cache_read": 0.15
                    },
                    "limit": {
                        "context": 262144,
                        "output": 262144
                    },
                    "modalities": {
                        "input": ["text"],
                        "output": ["text"]
                    }
                }
            }
        },
        "openai": {
            "name": "OpenAI",
            "models": {
                "text-embedding-3-large": {
                    "name": "text-embedding-3-large",
                    "reasoning": False,
                    "tool_call": False,
                    "attachment": False,
                    "temperature": False,
                    "knowledge": "2024-01",
                    "release_date": "2024-01-25",
                    "last_updated": "2024-01-25",
                    "open_weights": False,
                    "cost": {
                        "input": 0.13,
                        "output": 0.00
                    },
                    "limit": {
                        "context": 8191,
                        "output": 3072
                    },
                    "modalities": {
                        "input": ["text"],
                        "output": ["text"]
                    }
                }
            }
        }
    }


@pytest.fixture
def temp_client(tmp_path, mock_models_data):
    """Create client with temporary cache directory."""
    client = ModelsDevClient(cache_dir=tmp_path)

    # Create snapshot file
    snapshot = tmp_path / "models_snapshot.json"
    snapshot.write_text(json.dumps(mock_models_data))
    client.snapshot_file = snapshot

    return client


# Test model lookup


def test_get_model_info_with_provider_prefix(temp_client):
    """Test looking up model with provider/model format."""
    info = temp_client.get_model_info("azure/gpt-5")

    assert info is not None
    assert info.provider == "azure"
    assert info.model_id == "gpt-5"
    assert info.full_id == "azure/gpt-5"
    assert info.capabilities.name == "GPT-5"
    assert info.limits.context == 272000
    assert info.limits.output == 128000


def test_get_model_info_without_prefix(temp_client):
    """Test looking up model without provider prefix (searches all providers)."""
    info = temp_client.get_model_info("gpt-5")

    assert info is not None
    # Note: Will find first match across providers, may not be azure
    assert info.model_id == "gpt-5"
    assert "/" not in info.model_id  # Should be just the model ID


def test_get_model_info_bedrock_arn_format(temp_client):
    """Test looking up Bedrock model with ARN format."""
    info = temp_client.get_model_info("us.anthropic.claude-3-5-sonnet-20241022-v2:0")

    # Should fuzzy match to amazon-bedrock provider
    assert info is not None
    assert info.provider == "amazon-bedrock"
    assert info.limits.output == 8192  # Bedrock Claude 3.5 limit


def test_get_model_info_not_found(temp_client):
    """Test looking up non-existent model."""
    info = temp_client.get_model_info("nonexistent/model")
    assert info is None


# Test limits


def test_get_limits_azure_gpt5(temp_client):
    """Test getting limits for Azure GPT-5."""
    limits = temp_client.get_limits("azure/gpt-5")

    assert limits is not None
    assert limits.context == 272000
    assert limits.output == 128000


def test_get_limits_azure_gpt4o(temp_client):
    """Test getting limits for Azure GPT-4o."""
    limits = temp_client.get_limits("azure/gpt-4o")

    assert limits is not None
    assert limits.context == 128000
    assert limits.output == 16384


def test_get_limits_claude_sonnet(temp_client):
    """Test getting limits for Claude Sonnet 4.5."""
    limits = temp_client.get_limits("anthropic/claude-sonnet-4-5-20250929")

    assert limits is not None
    assert limits.context == 200000
    assert limits.output == 64000


def test_get_limits_bedrock_claude_35(temp_client):
    """Test getting limits for Bedrock Claude 3.5 Sonnet v2."""
    limits = temp_client.get_limits("amazon-bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0")

    assert limits is not None
    assert limits.context == 200000
    assert limits.output == 8192  # Critical: This is the limit causing specialist failures


def test_get_limits_moonshot_kimi(temp_client):
    """Test getting limits for Moonshot Kimi K2 Thinking."""
    limits = temp_client.get_limits("moonshotai/kimi-k2-thinking")

    assert limits is not None
    assert limits.context == 262144
    assert limits.output == 262144


def test_get_limits_embedding_model(temp_client):
    """Test getting limits for embedding model."""
    limits = temp_client.get_limits("openai/text-embedding-3-large")

    assert limits is not None
    assert limits.context == 8191
    assert limits.output == 3072


# Test capabilities


def test_get_capabilities_reasoning_model(temp_client):
    """Test capabilities for reasoning model."""
    caps = temp_client.get_capabilities("azure/gpt-5")

    assert caps is not None
    assert caps.reasoning is True
    assert caps.tool_call is True
    assert caps.attachment is True
    assert caps.temperature is False  # GPT-5 has fixed temperature
    assert caps.knowledge == "2024-09-30"


def test_get_capabilities_standard_model(temp_client):
    """Test capabilities for standard (non-reasoning) model."""
    caps = temp_client.get_capabilities("azure/gpt-4o")

    assert caps is not None
    assert caps.reasoning is False
    assert caps.tool_call is True
    assert caps.temperature is True


def test_get_capabilities_open_weights(temp_client):
    """Test open weights flag."""
    caps = temp_client.get_capabilities("moonshotai/kimi-k2-thinking")

    assert caps is not None
    assert caps.open_weights is True


def test_get_capabilities_modalities(temp_client):
    """Test input/output modalities."""
    # Multimodal model
    caps = temp_client.get_capabilities("azure/gpt-5")
    assert "text" in caps.modalities_input
    assert "image" in caps.modalities_input
    assert caps.modalities_output == ["text"]

    # Text-only model
    caps = temp_client.get_capabilities("moonshotai/kimi-k2-thinking")
    assert caps.modalities_input == ["text"]
    assert caps.modalities_output == ["text"]


# Test pricing


def test_get_pricing_full_data(temp_client):
    """Test pricing with all fields."""
    pricing = temp_client.get_pricing("anthropic/claude-sonnet-4-5-20250929")

    assert pricing is not None
    assert pricing.input == 3.00
    assert pricing.output == 15.00
    assert pricing.cache_read == 0.30
    assert pricing.cache_write == 3.75


def test_get_pricing_basic_data(temp_client):
    """Test pricing with basic fields only."""
    pricing = temp_client.get_pricing("azure/gpt-5")

    assert pricing is not None
    assert pricing.input == 1.25
    assert pricing.output == 10.00
    assert pricing.cache_read == 0.13
    assert pricing.cache_write is None  # Not provided
    assert pricing.reasoning is None  # Not provided


def test_get_pricing_embedding_model(temp_client):
    """Test pricing for embedding model (no output cost)."""
    pricing = temp_client.get_pricing("openai/text-embedding-3-large")

    assert pricing is not None
    assert pricing.input == 0.13
    assert pricing.output == 0.00


# Test fuzzy matching


def test_fuzzy_matching_dots_to_dashes(temp_client):
    """Test fuzzy matching with dot normalization."""
    # Search with dots (should normalize to dashes and find real model)
    info = temp_client.get_model_info("claude-3.5-haiku")

    assert info is not None
    # Real snapshot has "Claude Haiku 3.5" - just verify we found it
    assert "haiku" in info.capabilities.name.lower()
    assert info.limits.output > 0


# Test list operations


def test_list_providers(temp_client):
    """Test listing all providers."""
    providers = temp_client.list_providers()

    # Real snapshot has 58 providers
    assert len(providers) >= 50, f"Expected at least 50 providers, got {len(providers)}"
    assert "azure" in providers
    assert "anthropic" in providers
    assert "amazon-bedrock" in providers
    assert "moonshotai" in providers
    assert "openai" in providers
    assert providers == sorted(providers)  # Should be sorted


def test_list_models_all(temp_client):
    """Test listing all models across all providers."""
    models = temp_client.list_models()

    # Real snapshot has 500+ models
    assert len(models) >= 500, f"Expected at least 500 models, got {len(models)}"
    # Check some known models exist
    assert "azure/gpt-5" in models
    assert "azure/gpt-4o" in models
    assert any("claude-sonnet" in m for m in models)
    assert any("kimi" in m for m in models)


def test_list_models_by_provider(temp_client):
    """Test listing models for specific provider."""
    models = temp_client.list_models(provider="azure")

    # Real snapshot has many Azure models (GPT-3.5, GPT-4, GPT-5 variants, O-series)
    assert len(models) >= 20, f"Expected at least 20 Azure models, got {len(models)}"
    assert "gpt-5" in models
    assert "gpt-4o" in models


def test_list_models_empty_provider(temp_client):
    """Test listing models for non-existent provider."""
    models = temp_client.list_models(provider="nonexistent")
    assert len(models) == 0


# Test cache behavior


def test_cache_saves_on_api_fetch(tmp_path, mock_models_data):
    """Test that API data is saved to cache."""
    client = ModelsDevClient(cache_dir=tmp_path)

    # Mock API response
    with patch('httpx.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_models_data
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # First call should fetch from API
        data = client._get_data()

        assert data == mock_models_data
        assert client.get_data_source() == "api"

        # Cache file should exist
        cache_file = tmp_path / "models.json"
        assert cache_file.exists()

        # Verify cache content
        cached_data = json.loads(cache_file.read_text())
        assert cached_data == mock_models_data


def test_cache_used_when_valid(tmp_path, mock_models_data):
    """Test that valid cache is used instead of API."""
    client = ModelsDevClient(cache_dir=tmp_path)

    # Create valid cache
    cache_file = tmp_path / "models.json"
    cache_file.write_text(json.dumps(mock_models_data))

    # Load data - should use cache, not API
    with patch('httpx.get') as mock_get:
        data = client._get_data()

        # API should not be called
        mock_get.assert_not_called()
        assert data == mock_models_data
        assert client.get_data_source() == "cache"


def test_cache_expired_fetches_api(tmp_path, mock_models_data):
    """Test that expired cache triggers API fetch."""
    client = ModelsDevClient(cache_dir=tmp_path)

    # Create expired cache
    cache_file = tmp_path / "models.json"
    cache_file.write_text(json.dumps({"old": "data"}))

    # Set modification time to 25 hours ago (expired)
    old_time = (datetime.now() - timedelta(hours=25)).timestamp()
    cache_file.touch()
    import os
    os.utime(cache_file, (old_time, old_time))

    # Mock API response
    with patch('httpx.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_models_data
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        data = client._get_data()

        # API should be called because cache expired
        mock_get.assert_called_once()
        assert data == mock_models_data
        assert client.get_data_source() == "api"


def test_clear_cache(tmp_path, mock_models_data):
    """Test clearing cache."""
    client = ModelsDevClient(cache_dir=tmp_path)

    # Create cache
    cache_file = tmp_path / "models.json"
    cache_file.write_text(json.dumps(mock_models_data))

    # Clear cache
    client.clear_cache()

    assert not cache_file.exists()
    assert client._data is None


# Test fallback behavior


def test_fallback_to_snapshot_on_api_failure(tmp_path, mock_models_data):
    """Test fallback to snapshot when API fails."""
    client = ModelsDevClient(cache_dir=tmp_path)

    # Create snapshot
    snapshot = tmp_path / "models_snapshot.json"
    snapshot.write_text(json.dumps(mock_models_data))
    client.snapshot_file = snapshot

    # Mock API failure
    with patch('httpx.get', side_effect=Exception("API down")):
        data = client._get_data()

        assert data == mock_models_data
        assert client.get_data_source() == "snapshot"


def test_fallback_returns_empty_when_all_fail(tmp_path):
    """Test that empty dict is returned when all sources fail."""
    client = ModelsDevClient(cache_dir=tmp_path)
    client.snapshot_file = tmp_path / "nonexistent.json"  # No snapshot

    # Mock API failure
    with patch('httpx.get', side_effect=Exception("API down")):
        data = client._get_data()

        assert data == {}


# Test singleton pattern


def test_get_models_client_singleton():
    """Test that get_models_client returns singleton."""
    client1 = get_models_client()
    client2 = get_models_client()

    assert client1 is client2


# Test edge cases


def test_model_without_pricing(temp_client, mock_models_data):
    """Test model without pricing information."""
    # Add model without cost data
    mock_models_data["test-provider"] = {
        "name": "Test Provider",
        "models": {
            "test-model": {
                "name": "Test Model",
                "reasoning": False,
                "tool_call": False,
                "attachment": False,
                "temperature": True,
                "knowledge": "2024-01",
                "release_date": "2024-01-01",
                "last_updated": "2024-01-01",
                "open_weights": False,
                "limit": {"context": 100000, "output": 4096},
                "modalities": {"input": ["text"], "output": ["text"]}
            }
        }
    }

    temp_client.snapshot_file.write_text(json.dumps(mock_models_data))
    temp_client._data = None

    pricing = temp_client.get_pricing("test-provider/test-model")
    assert pricing is None


def test_empty_model_id(temp_client):
    """Test with empty model ID."""
    info = temp_client.get_model_info("")
    assert info is None


def test_model_id_with_multiple_slashes(temp_client):
    """Test model ID with multiple slashes."""
    # Should only split on first slash
    info = temp_client.get_model_info("provider/namespace/model")

    # Won't find it, but shouldn't crash
    assert info is None


# Integration tests with real models


def test_real_models_from_user_examples(temp_client):
    """Test all models from user's Docker commands."""
    # Azure GPT-5
    limits = temp_client.get_limits("azure/gpt-5")
    assert limits is not None
    assert limits.context == 272000
    assert limits.output == 128000

    # Azure GPT-4o (swarm model)
    limits = temp_client.get_limits("azure/gpt-4o")
    assert limits is not None
    assert limits.context == 128000
    assert limits.output == 16384

    # Moonshot Kimi K2 Thinking
    limits = temp_client.get_limits("moonshotai/kimi-k2-thinking")
    assert limits is not None
    assert limits.context == 262144
    assert limits.output == 262144

    # Azure text-embedding-3-large
    limits = temp_client.get_limits("openai/text-embedding-3-large")
    assert limits is not None
    assert limits.context == 8191


def test_critical_bedrock_limit(temp_client):
    """Test the critical Bedrock Claude 3.5 Sonnet v2 limit that causes specialist failures."""
    # This is the model causing 77% specialist failure rate
    limits = temp_client.get_limits("amazon-bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0")

    assert limits is not None
    assert limits.output == 8192, "Critical: Bedrock Claude 3.5 Sonnet v2 has 8,192 token output limit"

    # Verify safe max_tokens (50% of limit)
    safe_max = limits.output // 2
    assert safe_max == 4096, "Safe max_tokens should be 4,096 (50% of 8,192)"
