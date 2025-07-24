#!/usr/bin/env python3

import pytest
import os
import sys
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.handlers import ReasoningHandler
from modules.handlers.reporting import _retrieve_evidence


class TestReportGenerationWithFAISS:
    """Test report generation with FAISS memory backend"""

    def test_report_generation_faiss_backend(self):
        """Test report generation with FAISS backend configuration"""
        memory_config = {
            "target_name": "test.com",
            "operation_id": "OP_20240101_120000",
            "vector_store": {
                "provider": "faiss",
                "config": {"path": "outputs/test.com/memory"},
            },
            "embedder": {
                "provider": "ollama",
                "config": {"model": "mxbai-embed-large"},
            },
            "llm": {"provider": "ollama", "config": {"model": "llama3.2:3b"}},
        }

        mock_memories = [
            {
                "id": "mem1",
                "memory": "SQL injection found in login form",
                "metadata": {
                    "category": "finding",
                    "severity": "high",
                    "confidence": "90%",
                },
            }
        ]

        with patch("modules.tools.memory.Mem0ServiceClient") as mock_mem0_client:
            mock_outer_client = Mock()
            mock_outer_client.list_memories.return_value = {"results": mock_memories}
            mock_mem0_client.return_value = mock_outer_client

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
                memory_config=memory_config,
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            # Verify FAISS client was created with correct config
            mock_mem0_client.assert_called_once()
            call_config = mock_mem0_client.call_args.kwargs["config"]
            assert call_config["vector_store"]["provider"] == "faiss"
            assert (
                call_config["vector_store"]["config"]["path"]
                == "outputs/test.com/memory"
            )

            # Verify evidence was retrieved
            assert len(evidence) == 1
            assert evidence[0]["category"] == "finding"

    def test_report_generation_faiss_with_custom_path(self):
        """Test report generation with FAISS backend and custom memory path"""
        memory_config = {
            "target_name": "test.com",
            "operation_id": "OP_20240101_120000",
            "vector_store": {
                "provider": "faiss",
                "config": {"path": "/custom/memory/path"},
            },
            "embedder": {
                "provider": "ollama",
                "config": {"model": "mxbai-embed-large"},
            },
            "llm": {"provider": "ollama", "config": {"model": "llama3.2:3b"}},
        }

        with patch("modules.tools.memory.Mem0ServiceClient") as mock_mem0_client:
            mock_client = Mock()
            mock_client.list_memories.return_value = {"results": []}
            mock_mem0_client.return_value = mock_client

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
                memory_config=memory_config,
            )

            _retrieve_evidence(handler.state, handler.memory_config)

            # Verify custom path was used
            call_config = mock_mem0_client.call_args.kwargs["config"]
            assert (
                call_config["vector_store"]["config"]["path"] == "/custom/memory/path"
            )


class TestReportGenerationWithOpenSearch:
    """Test report generation with OpenSearch memory backend"""

    @patch.dict(os.environ, {"OPENSEARCH_HOST": "test-opensearch.com"})
    def test_report_generation_opensearch_backend(self):
        """Test report generation with OpenSearch backend configuration"""
        memory_config = {
            "target_name": "test.com",
            "operation_id": "OP_20240101_120000",
            "vector_store": {
                "provider": "opensearch",
                "config": {
                    "host": "test-opensearch.com",
                    "port": 9200,
                    "index_name": "cyber_agent_memories",
                },
            },
            "embedder": {
                "provider": "aws_bedrock",
                "config": {
                    "model": "amazon.titan-embed-text-v2:0",
                    "aws_region": "us-east-1",
                },
            },
            "llm": {
                "provider": "aws_bedrock",
                "config": {
                    "model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    "aws_region": "us-east-1",
                },
            },
        }

        mock_memories = [
            {
                "id": "mem1",
                "memory": "XSS vulnerability found in search parameter",
                "metadata": {
                    "category": "finding",
                    "severity": "medium",
                    "confidence": "85%",
                },
            }
        ]

        with patch("modules.tools.memory.Mem0ServiceClient") as mock_mem0_client:
            mock_outer_client = Mock()
            mock_outer_client.list_memories.return_value = {"results": mock_memories}
            mock_mem0_client.return_value = mock_outer_client

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
                memory_config=memory_config,
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            # Verify OpenSearch client was created with correct config
            mock_mem0_client.assert_called_once()
            call_config = mock_mem0_client.call_args.kwargs["config"]
            assert call_config["vector_store"]["provider"] == "opensearch"
            assert (
                call_config["vector_store"]["config"]["host"] == "test-opensearch.com"
            )

            # Verify evidence was retrieved
            assert len(evidence) == 1
            assert evidence[0]["category"] == "finding"


class TestReportGenerationWithMem0Platform:
    """Test report generation with Mem0 Platform memory backend"""

    @patch.dict(os.environ, {"MEM0_API_KEY": "test-api-key"})
    def test_report_generation_mem0_platform_backend(self):
        """Test report generation with Mem0 Platform backend configuration"""
        memory_config = {
            "target_name": "test.com",
            "operation_id": "OP_20240101_120000",
            "vector_store": {
                "provider": "mem0_platform",
                "config": {"api_key": "test-api-key"},
            },
            "embedder": {
                "provider": "openai",
                "config": {"model": "text-embedding-3-large"},
            },
            "llm": {"provider": "openai", "config": {"model": "gpt-4"}},
        }

        mock_memories = [
            {
                "id": "mem1",
                "memory": "Admin credentials found: admin/password123",
                "metadata": {
                    "category": "finding",
                    "severity": "critical",
                    "confidence": "95%",
                },
            },
            {
                "id": "mem2",
                "memory": "RCE vulnerability in file upload",
                "metadata": {
                    "category": "finding",
                    "severity": "critical",
                    "confidence": "90%",
                },
            },
        ]

        with patch("modules.tools.memory.Mem0ServiceClient") as mock_mem0_client:
            mock_outer_client = Mock()
            mock_outer_client.list_memories.return_value = {"results": mock_memories}
            mock_mem0_client.return_value = mock_outer_client

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
                memory_config=memory_config,
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            # Verify Mem0 Platform client was created
            mock_mem0_client.assert_called_once()
            call_config = mock_mem0_client.call_args.kwargs["config"]
            assert call_config["vector_store"]["provider"] == "mem0_platform"

            # Verify evidence was retrieved
            assert len(evidence) == 2
            assert evidence[0]["category"] == "finding"
            assert evidence[1]["category"] == "finding"


class TestReportGenerationBackendFallback:
    """Test report generation fallback behavior"""

    def test_report_generation_fallback_to_global_client(self):
        """Test report generation falls back to global client when no config is stored"""
        mock_memories = [
            {
                "id": "mem1",
                "memory": "Network scan completed",
                "metadata": {"category": "finding", "severity": "low"},
            }
        ]

        handler = ReasoningHandler(
            max_steps=50,
            operation_id="OP_20240101_120000",
            target="test.com",
        )

        evidence = _retrieve_evidence(handler.state, handler.memory_config)

        # Should return empty list when no memory config
        assert evidence == []

    def test_report_generation_handles_backend_failure(self):
        """Test report generation handles backend initialization failures"""
        memory_config = {
            "target_name": "test.com",
            "operation_id": "OP_20240101_120000",
            "vector_store": {
                "provider": "invalid_provider",
                "config": {"invalid": "config"},
            },
        }

        with patch("modules.tools.memory.Mem0ServiceClient") as mock_mem0_client:
            mock_mem0_client.side_effect = Exception("Invalid backend configuration")

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
                memory_config=memory_config,
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            # Should return empty evidence on failure
            assert evidence == []


class TestReportGenerationMemoryFormats:
    """Test report generation with different memory response formats"""

    def test_report_generation_handles_dict_response(self):
        """Test report generation handles dictionary response format"""
        memory_config = {
            "target_name": "test.com",
            "operation_id": "OP_20240101_120000",
        }

        mock_memories = [
            {
                "id": "mem1",
                "memory": "Finding 1",
                "metadata": {"category": "finding", "severity": "high"},
            }
        ]

        with patch("modules.tools.memory.Mem0ServiceClient") as mock_mem0_client:
            mock_outer_client = Mock()
            mock_outer_client.list_memories.return_value = {"results": mock_memories}
            mock_mem0_client.return_value = mock_outer_client

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
                memory_config=memory_config,
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            assert len(evidence) == 1
            assert evidence[0]["content"] == "Finding 1"

    def test_report_generation_handles_results_format(self):
        """Test report generation handles results format"""
        memory_config = {
            "target_name": "test.com",
            "operation_id": "OP_20240101_120000",
        }

        mock_memories = [
            {
                "id": "mem1",
                "memory": "Finding 1",
                "metadata": {"category": "finding", "severity": "high"},
            }
        ]

        with patch("modules.tools.memory.Mem0ServiceClient") as mock_mem0_client:
            mock_outer_client = Mock()
            mock_outer_client.list_memories.return_value = {"results": mock_memories}
            mock_mem0_client.return_value = mock_outer_client

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
                memory_config=memory_config,
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            assert len(evidence) == 1
            assert evidence[0]["content"] == "Finding 1"

    def test_report_generation_handles_direct_list_response(self):
        """Test report generation handles direct list response"""
        memory_config = {
            "target_name": "test.com",
            "operation_id": "OP_20240101_120000",
        }

        mock_memories = [
            {
                "id": "mem1",
                "memory": "Finding 1",
                "metadata": {"category": "finding", "severity": "high"},
            }
        ]

        with patch("modules.tools.memory.Mem0ServiceClient") as mock_mem0_client:
            mock_outer_client = Mock()
            mock_outer_client.list_memories.return_value = {"results": mock_memories}
            mock_mem0_client.return_value = mock_outer_client

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
                memory_config=memory_config,
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            assert len(evidence) == 1
            assert evidence[0]["content"] == "Finding 1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
