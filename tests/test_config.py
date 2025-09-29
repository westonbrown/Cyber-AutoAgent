#!/usr/bin/env python3
"""
Unit tests for the centralized model configuration system.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the modules we're testing
from modules.config.manager import (
    ConfigManager,
    EmbeddingConfig,
    EvaluationConfig,
    LLMConfig,
    MemoryConfig,
    MemoryEmbeddingConfig,
    MemoryLLMConfig,
    MemoryVectorStoreConfig,
    ModelConfig,
    ModelProvider,
    OutputConfig,
    ServerConfig,
    SwarmConfig,
    get_config_manager,
    get_default_base_dir,
    get_default_model_configs,
    get_model_config,
    get_ollama_host,
)


class TestModelProvider:
    """Test ModelProvider enum."""

    def test_provider_values(self):
        """Test that all expected providers are available."""
        assert ModelProvider.AWS_BEDROCK.value == "aws_bedrock"
        assert ModelProvider.OLLAMA.value == "ollama"
        assert ModelProvider.LITELLM.value == "litellm"


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
        config = EmbeddingConfig(provider=ModelProvider.OLLAMA, model_id="mxbai-embed-large")
        assert config.dimensions == 1024
        assert config.parameters["dimensions"] == 1024

    def test_custom_dimensions(self):
        """Test embedding config with custom dimensions."""
        config = EmbeddingConfig(provider=ModelProvider.OLLAMA, model_id="mxbai-embed-large", dimensions=512)
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
        config = MemoryEmbeddingConfig(provider=ModelProvider.OLLAMA, model_id="mxbai-embed-large")
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
        opensearch_config = config.get_config_for_provider("opensearch", host="test-host")
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
        assert "ollama" in self.config_manager._default_configs
        assert "bedrock" in self.config_manager._default_configs

    def test_get_local_server_config(self):
        """Test getting local server configuration."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear cache to ensure fresh config
            self.config_manager._config_cache = {}
            config = self.config_manager.get_server_config("ollama")

            assert config.server_type == "ollama"
            assert config.llm.provider == ModelProvider.OLLAMA
            assert config.llm.model_id == "llama3.2:3b"
            assert config.embedding.provider == ModelProvider.OLLAMA
            assert config.embedding.model_id == "mxbai-embed-large"
            assert config.region == "ollama"

    def test_get_remote_server_config(self):
        """Test getting remote server configuration."""
        config = self.config_manager.get_server_config("bedrock")

        assert config.server_type == "bedrock"
        assert config.llm.provider == ModelProvider.AWS_BEDROCK
        assert "claude-sonnet-4" in config.llm.model_id
        assert config.embedding.provider == ModelProvider.AWS_BEDROCK
        assert "titan-embed" in config.embedding.model_id
        assert config.region == "us-east-1"

    def test_invalid_server_type(self):
        """Test that invalid server type raises error."""
        with pytest.raises(ValueError, match="Unsupported provider type"):
            self.config_manager.get_server_config("invalid")

    def test_config_caching(self):
        """Test that configurations are cached properly."""
        # Clear cache first
        self.config_manager._config_cache = {}

        # First call should cache the result
        config1 = self.config_manager.get_server_config("ollama")
        assert len(self.config_manager._config_cache) == 1

        # Second call should return cached result
        config2 = self.config_manager.get_server_config("ollama")
        assert config1 is config2
        assert len(self.config_manager._config_cache) == 1

    def test_get_llm_config(self):
        """Test getting LLM configuration."""
        config = self.config_manager.get_llm_config("ollama")

        assert isinstance(config, LLMConfig)
        assert config.provider == ModelProvider.OLLAMA
        assert config.model_id == "llama3.2:3b"

    def test_get_embedding_config(self):
        """Test getting embedding configuration."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear cache to ensure fresh config
            self.config_manager._config_cache = {}
            config = self.config_manager.get_embedding_config("ollama")

            assert isinstance(config, EmbeddingConfig)
            assert config.provider == ModelProvider.OLLAMA
            assert config.model_id == "mxbai-embed-large"

    def test_get_memory_config(self):
        """Test getting memory configuration."""
        config = self.config_manager.get_memory_config("ollama")

        assert isinstance(config, MemoryConfig)
        assert isinstance(config.embedder, MemoryEmbeddingConfig)
        assert config.embedder.provider == ModelProvider.OLLAMA
        assert isinstance(config.llm, MemoryLLMConfig)
        assert config.llm.provider == ModelProvider.OLLAMA
        assert isinstance(config.vector_store, MemoryVectorStoreConfig)

    def test_get_evaluation_config(self):
        """Test getting evaluation configuration."""
        config = self.config_manager.get_evaluation_config("ollama")

        assert isinstance(config, EvaluationConfig)
        assert config.llm.provider == ModelProvider.OLLAMA
        assert config.embedding.provider == ModelProvider.OLLAMA

    def test_get_swarm_config(self):
        """Test getting swarm configuration."""
        # Test local swarm config
        local_config = self.config_manager.get_swarm_config("ollama")
        assert isinstance(local_config, SwarmConfig)
        assert local_config.llm.provider == ModelProvider.OLLAMA
        assert local_config.llm.model_id == "llama3.2:3b"
        assert local_config.llm.temperature == 0.7
        assert local_config.llm.max_tokens == 500

        # Test remote swarm config
        remote_config = self.config_manager.get_swarm_config("bedrock")
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
            local_config = self.config_manager.get_mem0_service_config("ollama")
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
        remote_config = self.config_manager.get_mem0_service_config("bedrock")
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
        # aws_region is no longer passed to LLM config; Mem0 infers region from environment

    @patch.dict(os.environ, {"OPENSEARCH_HOST": "test-opensearch.com"})
    def test_get_mem0_service_config_with_opensearch(self):
        """Test Mem0 service configuration with OpenSearch."""
        # Clear cache to ensure fresh config
        self.config_manager._config_cache = {}

        config = self.config_manager.get_mem0_service_config("bedrock")

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

        config = self.config_manager.get_server_config("ollama")
        assert config.llm.model_id == "custom-llm"

    @patch.dict(os.environ, {"RAGAS_EVALUATOR_MODEL": "custom-evaluator"})
    def test_legacy_environment_variable_support(self):
        """Test that legacy environment variables are supported."""
        # Clear cache to force re-evaluation
        self.config_manager._config_cache = {}

        config = self.config_manager.get_server_config("ollama")
        assert config.evaluation.llm.model_id == "custom-evaluator"

    @patch.dict(os.environ, {"CYBER_AGENT_SWARM_MODEL": "custom-swarm-model"})
    def test_swarm_model_environment_variable_override(self):
        """Test that swarm model can be overridden with environment variables."""
        # Clear cache to force re-evaluation
        self.config_manager._config_cache = {}

        config = self.config_manager.get_server_config("ollama")
        assert config.swarm.llm.model_id == "custom-swarm-model"

    def test_parameter_overrides(self):
        """Test that function parameters override configuration."""
        # This would require more complex override logic
        # For now, just test that the method accepts overrides
        config = self.config_manager.get_server_config("ollama", custom_param="value")
        assert config.server_type == "ollama"

    @patch("modules.config.manager.os.path.exists")
    @patch("modules.config.manager.requests.get")
    def test_get_ollama_host_docker(self, mock_get, mock_exists):
        """Test Ollama host detection in Docker environment."""
        mock_exists.return_value = True  # Simulate Docker environment
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        host = self.config_manager.get_ollama_host()
        assert host == "http://localhost:11434"

    @patch("modules.config.manager.os.path.exists")
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

    @patch("modules.config.manager.requests.get")
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
                self.config_manager.validate_requirements("ollama")

    @patch("modules.config.manager.requests.get")
    def test_validate_ollama_requirements_server_down(self, mock_get):
        """Test Ollama requirements validation when server is down."""
        mock_get.side_effect = ConnectionError("Connection refused")

        with pytest.raises(ConnectionError, match="Ollama server not accessible"):
            self.config_manager.validate_requirements("ollama")

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_aws_requirements_no_credentials(self):
        """Test AWS requirements validation without credentials."""
        with pytest.raises(EnvironmentError, match="AWS credentials not configured"):
            self.config_manager.validate_requirements("bedrock")

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "AWS_REGION": "us-east-1",
        },
    )
    @patch("boto3.client")
    def test_validate_bedrock_model_access_success(self, mock_boto_client):
        """Test successful Bedrock model validation."""
        # Mock bedrock client
        mock_bedrock = MagicMock()
        mock_bedrock.list_foundation_models.return_value = {
            "modelSummaries": [
                {"modelId": "us.anthropic.claude-sonnet-4-20250514-v1:0"},
                {"modelId": "amazon.titan-embed-text-v2:0"},
            ]
        }

        # Mock bedrock-runtime client
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.return_value = {"statusCode": 200}

        # Configure boto3.client to return appropriate mocks
        def client_side_effect(service_name, **kwargs):
            if service_name == "bedrock":
                return mock_bedrock
            elif service_name == "bedrock-runtime":
                return mock_runtime
            return MagicMock()

        mock_boto_client.side_effect = client_side_effect

        # Should not raise an exception
        self.config_manager.validate_requirements("bedrock")

        # Verify bedrock-runtime client was created
        mock_boto_client.assert_any_call("bedrock-runtime", region_name="us-east-1")

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "AWS_REGION": "us-east-1",
        },
    )
    @patch("boto3.client")
    def test_validate_bedrock_service_access_denied(self, mock_boto_client):
        """Test Bedrock validation when service access is denied."""
        from botocore.exceptions import ClientError

        mock_runtime = MagicMock()
        mock_runtime.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "client",
        )

        mock_boto_client.side_effect = mock_runtime

        # Should not raise an exception - errors are handled by strands-agents
        self.config_manager.validate_requirements("bedrock")

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "AWS_REGION": "us-east-1",
        },
    )
    @patch("boto3.client")
    def test_validate_bedrock_missing_models(self, mock_boto_client):
        """Test Bedrock validation when required models are missing."""
        # The new implementation delegates model validation to strands-agents
        # So this test now verifies that validation completes without error
        mock_bedrock = MagicMock()
        mock_bedrock.list_foundation_models.return_value = {"modelSummaries": [{"modelId": "some.other.model:1.0"}]}

        mock_boto_client.return_value = mock_bedrock

        # Should not raise - model validation is handled by strands-agents
        self.config_manager.validate_requirements("bedrock")

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "AWS_REGION": "us-east-1",
        },
    )
    @patch("boto3.client")
    def test_validate_bedrock_model_access_denied(self, mock_boto_client):
        """Test Bedrock validation when model access is denied."""
        from botocore.exceptions import ClientError

        # Mock runtime invoke failure
        mock_runtime = MagicMock()
        mock_runtime.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "InvokeModel",
        )

        mock_boto_client.side_effect = mock_runtime

        # Should not raise an exception - model errors handled by strands-agents
        self.config_manager.validate_requirements("bedrock")

    @patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test"})
    @patch("boto3.client")
    def test_validate_bedrock_no_region(self, mock_boto_client):
        """Test Bedrock validation when region returns None."""
        with patch.object(self.config_manager, "get_default_region", return_value=None):
            with pytest.raises(EnvironmentError, match="AWS region not configured"):
                self.config_manager.validate_requirements("bedrock")

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_REGION": "us-east-1",
        },
    )
    @patch("boto3.client")
    def test_validate_aws_requirements_with_credentials(self, mock_boto_client):
        """Test AWS requirements validation with credentials."""
        # Mock bedrock client
        mock_bedrock = MagicMock()
        mock_bedrock.list_foundation_models.return_value = {
            "modelSummaries": [
                {"modelId": "us.anthropic.claude-sonnet-4-20250514-v1:0"},
                {"modelId": "amazon.titan-embed-text-v2:0"},
            ]
        }

        # Mock bedrock-runtime client
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.return_value = {"statusCode": 200}

        def client_side_effect(service_name, **kwargs):
            if service_name == "bedrock":
                return mock_bedrock
            elif service_name == "bedrock-runtime":
                return mock_runtime
            return MagicMock()

        mock_boto_client.side_effect = client_side_effect

        # Should not raise an exception
        self.config_manager.validate_requirements("bedrock")

    @patch.dict(os.environ, {"AWS_PROFILE": "test-profile", "AWS_REGION": "us-east-1"})
    @patch("boto3.client")
    def test_validate_aws_requirements_with_profile(self, mock_boto_client):
        """Test AWS requirements validation with profile."""
        # Mock bedrock client
        mock_bedrock = MagicMock()
        mock_bedrock.list_foundation_models.return_value = {
            "modelSummaries": [
                {"modelId": "us.anthropic.claude-sonnet-4-20250514-v1:0"},
                {"modelId": "amazon.titan-embed-text-v2:0"},
            ]
        }

        # Mock bedrock-runtime client
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.return_value = {"statusCode": 200}

        def client_side_effect(service_name, **kwargs):
            if service_name == "bedrock":
                return mock_bedrock
            elif service_name == "bedrock-runtime":
                return mock_runtime
            return MagicMock()

        mock_boto_client.side_effect = client_side_effect

        # Should not raise an exception
        self.config_manager.validate_requirements("bedrock")

    def test_set_environment_variables_local(self):
        """Test setting environment variables for local mode."""
        with patch.dict(os.environ, {}, clear=True):
            self.config_manager.set_environment_variables("ollama")

            assert os.environ["MEM0_LLM_PROVIDER"] == "ollama"
            assert os.environ["MEM0_LLM_MODEL"] == "llama3.2:3b"
            assert os.environ["MEM0_EMBEDDING_MODEL"] == "mxbai-embed-large"

    def test_set_environment_variables_remote(self):
        """Test setting environment variables for remote mode."""
        with patch.dict(os.environ, {}, clear=True):
            self.config_manager.set_environment_variables("bedrock")

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
        config = get_model_config("ollama")
        assert isinstance(config, ServerConfig)
        assert config.server_type == "ollama"

    def test_get_default_model_configs_backward_compatibility(self):
        """Test backward compatibility function."""
        config = get_default_model_configs("ollama")

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
            config = config_manager.get_server_config("bedrock")

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
            config = config_manager.get_server_config("ollama")

            assert config.evaluation.llm.model_id == "new-evaluator"

    def test_centralized_region_configuration(self):
        """Test that AWS regions are centralized and consistent across all components."""
        # Test with custom region
        with patch.dict(os.environ, {"AWS_REGION": "eu-west-1"}, clear=True):
            config_manager = ConfigManager()

            # Test get_default_region method
            assert config_manager.get_default_region() == "eu-west-1"

            # Test server config uses centralized region
            server_config = config_manager.get_server_config("bedrock")
            assert server_config.region == "eu-west-1"

            # Test memory config uses centralized region
            memory_config = config_manager.get_memory_config("bedrock")
            assert memory_config.llm.aws_region == "eu-west-1"
            assert memory_config.embedder.aws_region == "eu-west-1"

            # Test mem0 service config uses centralized region
            mem0_config = config_manager.get_mem0_service_config("bedrock")
            # LLM no longer includes aws_region; region is inferred from environment
            assert mem0_config["embedder"]["config"]["aws_region"] == "eu-west-1"

        # Test without environment variable (should use default)
        with patch.dict(os.environ, {}, clear=True):
            config_manager = ConfigManager()

            # Test get_default_region method
            assert config_manager.get_default_region() == "us-east-1"

            # Test server config uses default region
            server_config = config_manager.get_server_config("bedrock")
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
        assert config_manager.is_thinking_model("us.anthropic.claude-opus-4-20250514-v1:0")
        assert config_manager.is_thinking_model("us.anthropic.claude-sonnet-4-20250514-v1:0")
        assert not config_manager.is_thinking_model("us.anthropic.claude-3-5-sonnet-20241022-v2:0")
        assert not config_manager.is_thinking_model("llama3.2:3b")

    def test_centralized_model_configuration_methods(self):
        """Test the new centralized model configuration methods."""
        config_manager = ConfigManager()

        # Test thinking model configuration
        thinking_config = config_manager.get_thinking_model_config(
            "us.anthropic.claude-opus-4-20250514-v1:0", "us-east-1"
        )
        assert thinking_config["temperature"] == 1.0
        assert thinking_config["max_tokens"] == 32000
        assert "additional_request_fields" in thinking_config
        assert "anthropic_beta" in thinking_config["additional_request_fields"]
        assert "thinking" in thinking_config["additional_request_fields"]

        # Test standard model configuration
        standard_config = config_manager.get_standard_model_config(
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0", "us-east-1", "bedrock"
        )
        assert standard_config["temperature"] == 0.95
        assert standard_config["max_tokens"] == 32000
        assert standard_config["top_p"] == 0.95

        # Test local model configuration
        local_config = config_manager.get_local_model_config("llama3.2:3b", "ollama")
        assert local_config["temperature"] == 0.95
        assert local_config["max_tokens"] == 65000
        assert "host" in local_config
        assert local_config["host"].startswith("http://")

    def test_centralized_mem0_service_config_local_vs_remote(self):
        """Test that local and remote Mem0 configurations are properly differentiated."""
        config_manager = ConfigManager()

        # Test local config has ollama_base_url
        local_config = config_manager.get_mem0_service_config("ollama")
        assert local_config["embedder"]["config"]["ollama_base_url"].startswith("http://")
        assert local_config["llm"]["config"]["ollama_base_url"].startswith("http://")
        assert "aws_region" not in local_config["embedder"]["config"]
        assert "aws_region" not in local_config["llm"]["config"]

        # Test remote config region handling
        remote_config = config_manager.get_mem0_service_config("bedrock")
        assert "aws_region" in remote_config["embedder"]["config"]
        assert "aws_region" not in remote_config["llm"]["config"]
        assert "ollama_base_url" not in remote_config["embedder"]["config"]
        assert "ollama_base_url" not in remote_config["llm"]["config"]


class TestOutputConfig:
    """Test OutputConfig dataclass."""

    def test_default_output_config(self):
        """Test default output configuration."""
        config = OutputConfig()
        assert config.base_dir == get_default_base_dir()
        assert config.target_name is None
        assert config.enable_unified_output is True

    def test_custom_output_config(self):
        """Test custom output configuration."""
        config = OutputConfig(
            base_dir="/tmp/custom_outputs",
            target_name="test_target",
            enable_unified_output=True,
        )
        assert config.base_dir == "/tmp/custom_outputs"
        assert config.target_name == "test_target"
        assert config.enable_unified_output is True

    def test_get_default_base_dir_project_root(self):
        """Test get_default_base_dir when in project root."""
        # Since we're running tests from project root, this should return ./outputs
        base_dir = get_default_base_dir()
        assert base_dir.endswith("outputs")

    def test_get_default_base_dir_detects_project_root(self):
        """Test that get_default_base_dir can detect project root."""
        # The method should find the project root by looking for pyproject.toml
        base_dir = get_default_base_dir()
        project_root = os.path.dirname(base_dir)
        assert os.path.exists(os.path.join(project_root, "pyproject.toml"))


class TestOutputConfigIntegration:
    """Test output configuration integration with ConfigManager."""

    def test_get_output_config_default(self):
        """Test getting default output configuration."""
        config_manager = ConfigManager()
        output_config = config_manager.get_output_config("bedrock")

        assert isinstance(output_config, OutputConfig)
        assert output_config.base_dir == get_default_base_dir()
        assert output_config.target_name is None
        assert output_config.enable_unified_output is True

    def test_get_output_config_with_overrides(self):
        """Test getting output configuration with overrides."""
        config_manager = ConfigManager()
        output_config = config_manager.get_output_config(
            "bedrock",
            output_dir="/tmp/custom",
            target_name="test_target",
            enable_unified_output=True,
        )

        assert output_config.base_dir == "/tmp/custom"
        assert output_config.target_name == "test_target"
        assert output_config.enable_unified_output is True

    @patch.dict(
        os.environ,
        {
            "CYBER_AGENT_OUTPUT_DIR": "/env/outputs",
            "CYBER_AGENT_ENABLE_UNIFIED_OUTPUT": "true",
        },
    )
    def test_get_output_config_with_env_vars(self):
        """Test getting output configuration with environment variables."""
        config_manager = ConfigManager()
        output_config = config_manager.get_output_config("bedrock")

        assert output_config.base_dir == "/env/outputs"
        assert output_config.enable_unified_output is True

    def test_output_config_in_server_config(self):
        """Test that output configuration is included in server configuration."""
        config_manager = ConfigManager()
        server_config = config_manager.get_server_config("bedrock")

        assert hasattr(server_config, "output")
        assert isinstance(server_config.output, OutputConfig)
        assert server_config.output.base_dir == get_default_base_dir()

    def test_output_config_precedence(self):
        """Test that overrides take precedence over environment variables."""
        with patch.dict(os.environ, {"CYBER_AGENT_OUTPUT_DIR": "/env/outputs"}):
            config_manager = ConfigManager()
            output_config = config_manager.get_output_config("bedrock", output_dir="/override/outputs")

            # Override should take precedence over environment variable
            assert output_config.base_dir == "/override/outputs"


