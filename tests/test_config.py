#!/usr/bin/env python3
"""
Unit tests for the centralized model configuration system.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# Import the modules we're testing
from modules.config import (
    ModelProvider,
    ModelConfig,
    LLMConfig,
    EmbeddingConfig,
    MemoryConfig,
    MemoryLLMConfig,
    MemoryEmbeddingConfig,
    MemoryVectorStoreConfig,
    EvaluationConfig,
    SwarmConfig,
    ServerConfig,
    ConfigManager,
    get_config_manager,
    get_model_config,
    get_default_model_configs,
    get_ollama_host,
)


class TestModelProvider:
    """Test ModelProvider enum."""

    def test_provider_values(self):
        """Test that all expected providers are available."""
        assert ModelProvider.AWS_BEDROCK.value == "aws_bedrock"
        assert ModelProvider.OLLAMA.value == "ollama"
        assert ModelProvider.OPENAI.value == "openai"


class TestModelConfig:
    """Test ModelConfig dataclass."""

    def test_valid_config(self):
        """Test creating valid model configuration."""
        config = ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_id="llama3.2:3b",
            parameters={"temperature": 0.5},
        )
        assert config.provider == ModelProvider.OLLAMA
        assert config.model_id == "llama3.2:3b"
        assert config.parameters["temperature"] == 0.5

    def test_empty_model_id_raises_error(self):
        """Test that empty model_id raises ValueError."""
        with pytest.raises(ValueError, match="model_id cannot be empty"):
            ModelConfig(provider=ModelProvider.OLLAMA, model_id="")

    def test_invalid_provider_raises_error(self):
        """Test that invalid provider raises ValueError."""
        with pytest.raises(ValueError, match="provider must be a ModelProvider enum"):
            ModelConfig(provider="invalid", model_id="test")


class TestLLMConfig:
    """Test LLMConfig dataclass."""

    def test_default_parameters(self):
        """Test LLM config with default parameters."""
        config = LLMConfig(provider=ModelProvider.OLLAMA, model_id="llama3.2:3b")
        assert config.temperature == 0.95
        assert config.max_tokens == 4096
        assert config.top_p == 0.95
        assert config.parameters["temperature"] == 0.95
        assert config.parameters["max_tokens"] == 4096
        assert config.parameters["top_p"] == 0.95

    def test_custom_parameters(self):
        """Test LLM config with custom parameters."""
        config = LLMConfig(
            provider=ModelProvider.OLLAMA,
            model_id="llama3.2:3b",
            temperature=0.7,
            max_tokens=2000,
            top_p=0.8,
        )
        assert config.temperature == 0.7
        assert config.max_tokens == 2000
        assert config.top_p == 0.8
        assert config.parameters["temperature"] == 0.7


class TestEmbeddingConfig:
    """Test EmbeddingConfig dataclass."""

    def test_default_dimensions(self):
        """Test embedding config with default dimensions."""
        config = EmbeddingConfig(
            provider=ModelProvider.OLLAMA, model_id="mxbai-embed-large"
        )
        assert config.dimensions == 1024
        assert config.parameters["dimensions"] == 1024

    def test_custom_dimensions(self):
        """Test embedding config with custom dimensions."""
        config = EmbeddingConfig(
            provider=ModelProvider.OLLAMA, model_id="mxbai-embed-large", dimensions=512
        )
        assert config.dimensions == 512
        assert config.parameters["dimensions"] == 512


class TestMemoryLLMConfig:
    """Test MemoryLLMConfig dataclass."""

    def test_default_parameters(self):
        """Test memory LLM config with default parameters."""
        config = MemoryLLMConfig(provider=ModelProvider.OLLAMA, model_id="llama3.2:3b")
        assert config.temperature == 0.1
        assert config.max_tokens == 2000
        assert config.aws_region == "us-east-1"
        assert config.parameters["temperature"] == 0.1
        assert config.parameters["max_tokens"] == 2000
        assert config.parameters["aws_region"] == "us-east-1"

    def test_custom_parameters(self):
        """Test memory LLM config with custom parameters."""
        config = MemoryLLMConfig(
            provider=ModelProvider.OLLAMA,
            model_id="llama3.2:3b",
            temperature=0.2,
            max_tokens=1500,
            aws_region="eu-west-1",
        )
        assert config.temperature == 0.2
        assert config.max_tokens == 1500
        assert config.aws_region == "eu-west-1"
        assert config.parameters["temperature"] == 0.2


class TestMemoryEmbeddingConfig:
    """Test MemoryEmbeddingConfig dataclass."""

    def test_default_parameters(self):
        """Test memory embedding config with default parameters."""
        config = MemoryEmbeddingConfig(
            provider=ModelProvider.OLLAMA, model_id="mxbai-embed-large"
        )
        assert config.aws_region == "us-east-1"
        assert config.dimensions == 1024
        assert config.parameters["aws_region"] == "us-east-1"
        assert config.parameters["dimensions"] == 1024

    def test_custom_parameters(self):
        """Test memory embedding config with custom parameters."""
        config = MemoryEmbeddingConfig(
            provider=ModelProvider.OLLAMA,
            model_id="mxbai-embed-large",
            aws_region="eu-west-1",
            dimensions=512,
        )
        assert config.aws_region == "eu-west-1"
        assert config.dimensions == 512
        assert config.parameters["aws_region"] == "eu-west-1"


class TestMemoryVectorStoreConfig:
    """Test MemoryVectorStoreConfig dataclass."""

    def test_default_provider(self):
        """Test default vector store configuration."""
        config = MemoryVectorStoreConfig()
        assert config.provider == "faiss"
        assert "embedding_model_dims" in config.faiss_config
        assert config.faiss_config["embedding_model_dims"] == 1024

    def test_opensearch_config(self):
        """Test OpenSearch configuration."""
        config = MemoryVectorStoreConfig()
        opensearch_config = config.get_config_for_provider("opensearch")
        assert opensearch_config["port"] == 443
        assert opensearch_config["collection_name"] == "mem0_memories"
        assert opensearch_config["embedding_model_dims"] == 1024

    def test_faiss_config(self):
        """Test FAISS configuration."""
        config = MemoryVectorStoreConfig()
        faiss_config = config.get_config_for_provider("faiss")
        assert faiss_config["embedding_model_dims"] == 1024

    def test_config_overrides(self):
        """Test configuration overrides."""
        config = MemoryVectorStoreConfig()
        opensearch_config = config.get_config_for_provider(
            "opensearch", host="test-host"
        )
        assert opensearch_config["host"] == "test-host"
        assert opensearch_config["port"] == 443  # Default preserved


class TestConfigManager:
    """Test ConfigManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config_manager = ConfigManager()

    def test_initialization(self):
        """Test ConfigManager initialization."""
        assert self.config_manager._config_cache == {}
        assert "local" in self.config_manager._default_configs
        assert "remote" in self.config_manager._default_configs

    def test_get_local_server_config(self):
        """Test getting local server configuration."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear cache to ensure fresh config
            self.config_manager._config_cache = {}
            config = self.config_manager.get_server_config("local")

            assert config.server_type == "local"
            assert config.llm.provider == ModelProvider.OLLAMA
            assert config.llm.model_id == "llama3.2:3b"
            assert config.embedding.provider == ModelProvider.OLLAMA
            assert config.embedding.model_id == "mxbai-embed-large"
            assert config.region == "local"

    def test_get_remote_server_config(self):
        """Test getting remote server configuration."""
        config = self.config_manager.get_server_config("remote")

        assert config.server_type == "remote"
        assert config.llm.provider == ModelProvider.AWS_BEDROCK
        assert "claude-sonnet-4" in config.llm.model_id
        assert config.embedding.provider == ModelProvider.AWS_BEDROCK
        assert "titan-embed" in config.embedding.model_id
        assert config.region == "us-east-1"

    def test_invalid_server_type(self):
        """Test that invalid server type raises error."""
        with pytest.raises(ValueError, match="Unsupported server type"):
            self.config_manager.get_server_config("invalid")

    def test_config_caching(self):
        """Test that configurations are cached properly."""
        # Clear cache first
        self.config_manager._config_cache = {}

        # First call should cache the result
        config1 = self.config_manager.get_server_config("local")
        assert len(self.config_manager._config_cache) == 1

        # Second call should return cached result
        config2 = self.config_manager.get_server_config("local")
        assert config1 is config2
        assert len(self.config_manager._config_cache) == 1

    def test_get_llm_config(self):
        """Test getting LLM configuration."""
        config = self.config_manager.get_llm_config("local")

        assert isinstance(config, LLMConfig)
        assert config.provider == ModelProvider.OLLAMA
        assert config.model_id == "llama3.2:3b"

    def test_get_embedding_config(self):
        """Test getting embedding configuration."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear cache to ensure fresh config
            self.config_manager._config_cache = {}
            config = self.config_manager.get_embedding_config("local")

            assert isinstance(config, EmbeddingConfig)
            assert config.provider == ModelProvider.OLLAMA
            assert config.model_id == "mxbai-embed-large"

    def test_get_memory_config(self):
        """Test getting memory configuration."""
        config = self.config_manager.get_memory_config("local")

        assert isinstance(config, MemoryConfig)
        assert isinstance(config.embedder, MemoryEmbeddingConfig)
        assert config.embedder.provider == ModelProvider.OLLAMA
        assert isinstance(config.llm, MemoryLLMConfig)
        assert config.llm.provider == ModelProvider.OLLAMA
        assert isinstance(config.vector_store, MemoryVectorStoreConfig)

    def test_get_evaluation_config(self):
        """Test getting evaluation configuration."""
        config = self.config_manager.get_evaluation_config("local")

        assert isinstance(config, EvaluationConfig)
        assert config.llm.provider == ModelProvider.OLLAMA
        assert config.embedding.provider == ModelProvider.OLLAMA

    def test_get_swarm_config(self):
        """Test getting swarm configuration."""
        # Test local swarm config
        local_config = self.config_manager.get_swarm_config("local")
        assert isinstance(local_config, SwarmConfig)
        assert local_config.llm.provider == ModelProvider.OLLAMA
        assert local_config.llm.model_id == "llama3.2:3b"
        assert local_config.llm.temperature == 0.7
        assert local_config.llm.max_tokens == 500

        # Test remote swarm config
        remote_config = self.config_manager.get_swarm_config("remote")
        assert isinstance(remote_config, SwarmConfig)
        assert remote_config.llm.provider == ModelProvider.AWS_BEDROCK
        assert "claude" in remote_config.llm.model_id
        assert remote_config.llm.temperature == 0.7
        assert remote_config.llm.max_tokens == 500

    def test_get_mem0_service_config(self):
        """Test getting Mem0 service configuration."""
        # Test local config
        with patch.dict(os.environ, {}, clear=True):
            # Clear cache to ensure fresh config
            self.config_manager._config_cache = {}
            local_config = self.config_manager.get_mem0_service_config("local")
            assert isinstance(local_config, dict)
            assert "embedder" in local_config
            assert "llm" in local_config
            assert "vector_store" in local_config

            # Test embedder config
            embedder_config = local_config["embedder"]
            assert embedder_config["provider"] == "ollama"
            assert embedder_config["config"]["model"] == "mxbai-embed-large"

            # Test LLM config
            llm_config = local_config["llm"]
            assert llm_config["provider"] == "ollama"
            assert llm_config["config"]["model"] == "llama3.2:3b"
            assert llm_config["config"]["temperature"] == 0.1
            assert llm_config["config"]["max_tokens"] == 2000

            # Test vector store config (should default to FAISS for local)
            vector_store_config = local_config["vector_store"]
            assert vector_store_config["provider"] == "faiss"
            assert vector_store_config["config"]["embedding_model_dims"] == 1024

        # Test remote config
        remote_config = self.config_manager.get_mem0_service_config("remote")
        assert isinstance(remote_config, dict)

        # Test embedder config
        embedder_config = remote_config["embedder"]
        assert embedder_config["provider"] == "aws_bedrock"
        assert "titan-embed" in embedder_config["config"]["model"]
        assert embedder_config["config"]["aws_region"] == "us-east-1"

        # Test LLM config
        llm_config = remote_config["llm"]
        assert llm_config["provider"] == "aws_bedrock"
        assert "claude" in llm_config["config"]["model"]
        assert llm_config["config"]["temperature"] == 0.1
        assert llm_config["config"]["max_tokens"] == 2000
        assert llm_config["config"]["aws_region"] == "us-east-1"

    @patch.dict(os.environ, {"OPENSEARCH_HOST": "test-opensearch.com"})
    def test_get_mem0_service_config_with_opensearch(self):
        """Test Mem0 service configuration with OpenSearch."""
        # Clear cache to ensure fresh config
        self.config_manager._config_cache = {}

        config = self.config_manager.get_mem0_service_config("remote")

        # Should use OpenSearch when OPENSEARCH_HOST is set
        vector_store_config = config["vector_store"]
        assert vector_store_config["provider"] == "opensearch"
        assert vector_store_config["config"]["host"] == "test-opensearch.com"
        assert vector_store_config["config"]["port"] == 443
        assert vector_store_config["config"]["collection_name"] == "mem0_memories"

    @patch.dict(os.environ, {"CYBER_AGENT_LLM_MODEL": "custom-llm"})
    def test_environment_variable_override(self):
        """Test that environment variables override default config."""
        # Clear cache to force re-evaluation
        self.config_manager._config_cache = {}

        config = self.config_manager.get_server_config("local")
        assert config.llm.model_id == "custom-llm"

    @patch.dict(os.environ, {"RAGAS_EVALUATOR_MODEL": "custom-evaluator"})
    def test_legacy_environment_variable_support(self):
        """Test that legacy environment variables are supported."""
        # Clear cache to force re-evaluation
        self.config_manager._config_cache = {}

        config = self.config_manager.get_server_config("local")
        assert config.evaluation.llm.model_id == "custom-evaluator"

    @patch.dict(os.environ, {"CYBER_AGENT_SWARM_MODEL": "custom-swarm-model"})
    def test_swarm_model_environment_variable_override(self):
        """Test that swarm model can be overridden with environment variables."""
        # Clear cache to force re-evaluation
        self.config_manager._config_cache = {}

        config = self.config_manager.get_server_config("local")
        assert config.swarm.llm.model_id == "custom-swarm-model"

    def test_parameter_overrides(self):
        """Test that function parameters override configuration."""
        # This would require more complex override logic
        # For now, just test that the method accepts overrides
        config = self.config_manager.get_server_config("local", custom_param="value")
        assert config.server_type == "local"

    @patch("modules.config.os.path.exists")
    @patch("modules.config.requests.get")
    def test_get_ollama_host_docker(self, mock_get, mock_exists):
        """Test Ollama host detection in Docker environment."""
        mock_exists.return_value = True  # Simulate Docker environment
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        host = self.config_manager.get_ollama_host()
        assert host == "http://localhost:11434"

    @patch("modules.config.os.path.exists")
    def test_get_ollama_host_native(self, mock_exists):
        """Test Ollama host detection in native environment."""
        mock_exists.return_value = False  # Simulate native environment

        host = self.config_manager.get_ollama_host()
        assert host == "http://localhost:11434"

    @patch.dict(os.environ, {"OLLAMA_HOST": "http://custom:11434"})
    def test_get_ollama_host_environment_override(self):
        """Test that OLLAMA_HOST environment variable overrides detection."""
        host = self.config_manager.get_ollama_host()
        assert host == "http://custom:11434"

    @patch("modules.config.requests.get")
    def test_validate_ollama_requirements_success(self, mock_get):
        """Test successful Ollama requirements validation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        with patch("ollama.Client") as mock_client:
            # Clear environment to ensure we get the expected local config
            with patch.dict(os.environ, {}, clear=True):
                mock_client.return_value.list.return_value = {
                    "models": [{"model": "llama3.2:3b"}, {"model": "mxbai-embed-large"}]
                }

                # Should not raise an exception
                self.config_manager.validate_requirements("local")

    @patch("modules.config.requests.get")
    def test_validate_ollama_requirements_server_down(self, mock_get):
        """Test Ollama requirements validation when server is down."""
        mock_get.side_effect = ConnectionError("Connection refused")

        with pytest.raises(ConnectionError, match="Ollama server not accessible"):
            self.config_manager.validate_requirements("local")

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_aws_requirements_no_credentials(self):
        """Test AWS requirements validation without credentials."""
        with pytest.raises(EnvironmentError, match="AWS credentials not configured"):
            self.config_manager.validate_requirements("remote")

    @patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test-key"})
    def test_validate_aws_requirements_with_credentials(self):
        """Test AWS requirements validation with credentials."""
        # Should not raise an exception
        self.config_manager.validate_requirements("remote")

    @patch.dict(os.environ, {"AWS_PROFILE": "test-profile"})
    def test_validate_aws_requirements_with_profile(self):
        """Test AWS requirements validation with profile."""
        # Should not raise an exception
        self.config_manager.validate_requirements("remote")

    def test_set_environment_variables_local(self):
        """Test setting environment variables for local mode."""
        with patch.dict(os.environ, {}, clear=True):
            self.config_manager.set_environment_variables("local")

            assert os.environ["MEM0_LLM_PROVIDER"] == "ollama"
            assert os.environ["MEM0_LLM_MODEL"] == "llama3.2:3b"
            assert os.environ["MEM0_EMBEDDING_MODEL"] == "mxbai-embed-large"

    def test_set_environment_variables_remote(self):
        """Test setting environment variables for remote mode."""
        with patch.dict(os.environ, {}, clear=True):
            self.config_manager.set_environment_variables("remote")

            assert "claude-3-5-sonnet" in os.environ["MEM0_LLM_MODEL"]
            assert "titan-embed" in os.environ["MEM0_EMBEDDING_MODEL"]


class TestGlobalFunctions:
    """Test global convenience functions."""

    def test_get_config_manager_singleton(self):
        """Test that get_config_manager returns singleton instance."""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        assert manager1 is manager2

    def test_get_model_config(self):
        """Test get_model_config function."""
        config = get_model_config("local")
        assert isinstance(config, ServerConfig)
        assert config.server_type == "local"

    def test_get_default_model_configs_backward_compatibility(self):
        """Test backward compatibility function."""
        config = get_default_model_configs("local")

        assert isinstance(config, dict)
        assert "llm_model" in config
        assert "embedding_model" in config
        assert "embedding_dims" in config
        assert config["llm_model"] == "llama3.2:3b"
        assert config["embedding_model"] == "mxbai-embed-large"
        assert config["embedding_dims"] == 1024

    def test_get_ollama_host_backward_compatibility(self):
        """Test backward compatibility function."""
        host = get_ollama_host()
        assert host.startswith("http://")
        assert "11434" in host


class TestEnvironmentIntegration:
    """Test environment variable integration."""

    def test_multiple_environment_overrides(self):
        """Test multiple environment variable overrides."""
        env_vars = {
            "CYBER_AGENT_LLM_MODEL": "custom-llm",
            "CYBER_AGENT_EMBEDDING_MODEL": "custom-embedding",
            "CYBER_AGENT_EVALUATION_MODEL": "custom-evaluator",
            "AWS_REGION": "us-west-2",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            config_manager = ConfigManager()
            config = config_manager.get_server_config("remote")

            assert config.llm.model_id == "custom-llm"
            assert config.embedding.model_id == "custom-embedding"
            assert config.evaluation.llm.model_id == "custom-evaluator"
            assert config.region == "us-west-2"

    def test_legacy_environment_variable_precedence(self):
        """Test that new environment variables take precedence over legacy ones."""
        env_vars = {
            "CYBER_AGENT_EVALUATION_MODEL": "new-evaluator",
            "RAGAS_EVALUATOR_MODEL": "legacy-evaluator",
        }

        with patch.dict(os.environ, env_vars):
            config_manager = ConfigManager()
            config = config_manager.get_server_config("local")

            assert config.evaluation.llm.model_id == "new-evaluator"

    def test_centralized_region_configuration(self):
        """Test that AWS regions are centralized and consistent across all components."""
        # Test with custom region
        with patch.dict(os.environ, {"AWS_REGION": "eu-west-1"}, clear=True):
            config_manager = ConfigManager()

            # Test get_default_region method
            assert config_manager.get_default_region() == "eu-west-1"

            # Test server config uses centralized region
            server_config = config_manager.get_server_config("remote")
            assert server_config.region == "eu-west-1"

            # Test memory config uses centralized region
            memory_config = config_manager.get_memory_config("remote")
            assert memory_config.llm.aws_region == "eu-west-1"
            assert memory_config.embedder.aws_region == "eu-west-1"

            # Test mem0 service config uses centralized region
            mem0_config = config_manager.get_mem0_service_config("remote")
            assert mem0_config["llm"]["config"]["aws_region"] == "eu-west-1"
            assert mem0_config["embedder"]["config"]["aws_region"] == "eu-west-1"

        # Test without environment variable (should use default)
        with patch.dict(os.environ, {}, clear=True):
            config_manager = ConfigManager()

            # Test get_default_region method
            assert config_manager.get_default_region() == "us-east-1"

            # Test server config uses default region
            server_config = config_manager.get_server_config("remote")
            assert server_config.region == "us-east-1"

    def test_thinking_models_configuration(self):
        """Test centralized thinking models configuration."""
        config_manager = ConfigManager()

        # Test get_thinking_models method
        thinking_models = config_manager.get_thinking_models()
        assert isinstance(thinking_models, list)
        assert len(thinking_models) > 0

        # Test specific thinking models
        expected_models = [
            "us.anthropic.claude-opus-4-20250514-v1:0",
            "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "us.anthropic.claude-sonnet-4-20250514-v1:0",
        ]
        for model in expected_models:
            assert model in thinking_models

        # Test is_thinking_model method
        assert config_manager.is_thinking_model(
            "us.anthropic.claude-opus-4-20250514-v1:0"
        )
        assert config_manager.is_thinking_model(
            "us.anthropic.claude-sonnet-4-20250514-v1:0"
        )
        assert not config_manager.is_thinking_model(
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
        assert not config_manager.is_thinking_model("llama3.2:3b")

    def test_centralized_model_configuration_methods(self):
        """Test the new centralized model configuration methods."""
        config_manager = ConfigManager()

        # Test thinking model configuration
        thinking_config = config_manager.get_thinking_model_config(
            "us.anthropic.claude-opus-4-20250514-v1:0", "us-east-1"
        )
        assert thinking_config["temperature"] == 1.0
        assert thinking_config["max_tokens"] == 4096
        assert "additional_request_fields" in thinking_config
        assert "anthropic_beta" in thinking_config["additional_request_fields"]
        assert "thinking" in thinking_config["additional_request_fields"]

        # Test standard model configuration
        standard_config = config_manager.get_standard_model_config(
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0", "us-east-1", "remote"
        )
        assert standard_config["temperature"] == 0.95
        assert standard_config["max_tokens"] == 4096
        assert standard_config["top_p"] == 0.95

        # Test local model configuration
        local_config = config_manager.get_local_model_config("llama3.2:3b", "local")
        assert local_config["temperature"] == 0.95
        assert local_config["max_tokens"] == 4096
        assert "host" in local_config
        assert local_config["host"].startswith("http://")

    def test_centralized_mem0_service_config_local_vs_remote(self):
        """Test that local and remote Mem0 configurations are properly differentiated."""
        config_manager = ConfigManager()

        # Test local config has ollama_base_url
        local_config = config_manager.get_mem0_service_config("local")
        assert local_config["embedder"]["config"]["ollama_base_url"].startswith(
            "http://"
        )
        assert local_config["llm"]["config"]["ollama_base_url"].startswith("http://")
        assert "aws_region" not in local_config["embedder"]["config"]
        assert "aws_region" not in local_config["llm"]["config"]

        # Test remote config has aws_region
        remote_config = config_manager.get_mem0_service_config("remote")
        assert "aws_region" in remote_config["embedder"]["config"]
        assert "aws_region" in remote_config["llm"]["config"]
        assert "ollama_base_url" not in remote_config["embedder"]["config"]
        assert "ollama_base_url" not in remote_config["llm"]["config"]
