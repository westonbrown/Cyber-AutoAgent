#!/usr/bin/env python3

import pytest
import os
import sys
from unittest.mock import Mock, patch

# Add src to path for imports

from modules.handlers import ReasoningHandler
from modules.handlers import reporting
from modules.handlers.reporting import _get_memory_client_for_report, _retrieve_evidence

class TestReasoningHandlerMemoryConfig:
    """Test the ReasoningHandler memory configuration handling"""

    def test_init_with_memory_config(self):
        """Test ReasoningHandler initialization with memory configuration"""
        memory_config = {
            "target_name": "test.com",
            "operation_id": "OP_20240101_120000",
            "vector_store": {"provider": "faiss", "config": {"path": "/test/path"}},
        }

        handler = ReasoningHandler(
            max_steps=50,
            operation_id="OP_20240101_120000",
            target="test.com",
            output_base_dir="/test/output",
            memory_config=memory_config,
        )

        assert handler.memory_config == memory_config
        assert handler.operation_id == "OP_20240101_120000"
        assert handler.target == "test.com"

    def test_init_without_memory_config(self):
        """Test ReasoningHandler initialization without memory configuration"""
        handler = ReasoningHandler(
            max_steps=50,
            operation_id="OP_20240101_120000",
            target="test.com",
            output_base_dir="/test/output",
        )

        assert handler.memory_config is None
        assert handler.operation_id == "OP_20240101_120000"
        assert handler.target == "test.com"

class TestMemoryClientForReport:
    """Test the memory client creation for report generation"""

    @patch("modules.tools.memory.Mem0ServiceClient")
    @patch("modules.tools.memory.get_memory_client")
    def test_get_memory_client_with_stored_config(self, mock_get_memory_client, mock_mem0_client):
        """Test getting memory client with stored configuration"""
        memory_config = {
            "target_name": "test.com",
            "operation_id": "OP_20240101_120000",
            "vector_store": {"provider": "faiss", "config": {"path": "/test/path"}},
        }

        mock_inner_client = Mock()
        mock_outer_client = Mock()
        mock_outer_client.client = mock_inner_client
        mock_mem0_client.return_value = mock_outer_client

        handler = ReasoningHandler(
            max_steps=50,
            operation_id="OP_20240101_120000",
            target="test.com",
            memory_config=memory_config,
        )

        result = _get_memory_client_for_report(handler.memory_config)

        mock_mem0_client.assert_called_once()
        mock_get_memory_client.assert_not_called()
        assert result == mock_outer_client

    @patch("modules.tools.memory.Mem0ServiceClient")
    @patch("modules.tools.memory.get_memory_client")
    def test_get_memory_client_without_stored_config(self, mock_get_memory_client, mock_mem0_client):
        """Test getting memory client without stored configuration"""
        mock_global_client = Mock()
        mock_get_memory_client.return_value = mock_global_client

        handler = ReasoningHandler(
            max_steps=50,
            operation_id="OP_20240101_120000",
            target="test.com",
        )

        result = _get_memory_client_for_report(handler.memory_config)

        mock_get_memory_client.assert_called_once()
        mock_mem0_client.assert_not_called()
        assert result == mock_global_client

    @patch("modules.tools.memory.Mem0ServiceClient")
    def test_get_memory_client_with_simple_config(self, mock_mem0_client):
        """Test that memory client uses config as-is without enhancement"""
        memory_config = {
            "vector_store": {"provider": "faiss", "config": {"path": "/test/path"}},
        }

        mock_outer_client = Mock()
        mock_mem0_client.return_value = mock_outer_client

        handler = ReasoningHandler(
            max_steps=50,
            operation_id="OP_20240101_120000",
            target="test.com",
            memory_config=memory_config,
        )

        result = _get_memory_client_for_report(handler.memory_config)

        mock_mem0_client.assert_called_once()
        call_config = mock_mem0_client.call_args.kwargs["config"]
        assert call_config == memory_config  # Should be exactly the same
        assert result == mock_outer_client

    @patch("modules.tools.memory.Mem0ServiceClient")
    @patch("modules.tools.memory.get_memory_client")
    def test_get_memory_client_handles_error(self, mock_get_memory_client, mock_mem0_client):
        """Test memory client handles initialization errors gracefully"""
        memory_config = {
            "vector_store": {"provider": "faiss", "config": {"path": "/test/path"}},
        }

        mock_mem0_client.side_effect = Exception("Initialization failed")

        handler = ReasoningHandler(
            max_steps=50,
            operation_id="OP_20240101_120000",
            target="test.com",
            memory_config=memory_config,
        )

        result = _get_memory_client_for_report(handler.memory_config)

        assert result is None

class TestRetrieveEvidence:
    """Test the evidence retrieval functionality"""

    def test_retrieve_evidence_with_no_client(self):
        """Test evidence retrieval when memory client is not available"""
        with patch.object(reporting, "_get_memory_client_for_report") as mock_get_client:
            mock_get_client.return_value = None

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            assert evidence == []

    def test_retrieve_evidence_with_findings(self):
        """Test evidence retrieval with security findings"""
        mock_client = Mock()
        mock_client.list_memories.return_value = {
            "results": [
                {
                    "id": "mem1",
                    "memory": "SQL injection found in login form",
                    "metadata": {
                        "category": "finding",
                        "severity": "high",
                        "confidence": "90%",
                    },
                    "score": 0.95,
                },
                {
                    "id": "mem2",
                    "memory": "XSS vulnerability in search parameter",
                    "metadata": {
                        "category": "finding",
                        "severity": "medium",
                        "confidence": "80%",
                    },
                    "score": 0.85,
                },
            ]
        }

        with patch.object(reporting, "_get_memory_client_for_report") as mock_get_client:
            mock_get_client.return_value = mock_client

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            assert len(evidence) == 2
            assert evidence[0]["category"] == "finding"
            assert evidence[0]["severity"] == "high"
            assert evidence[0]["confidence"] == "90%"
            assert evidence[1]["category"] == "finding"
            assert evidence[1]["severity"] == "medium"

    def test_retrieve_evidence_with_uncategorized(self):
        """Test evidence retrieval with uncategorized memories"""
        mock_client = Mock()
        mock_client.list_memories.return_value = {
            "results": [
                {"id": "mem1", "memory": "Port 22 is open", "metadata": {}, "score": 0.5},
                {
                    "id": "mem2",
                    "memory": "This is a very long uncategorized memory that contains more than 100 words " * 10,
                    "metadata": {},
                    "score": 0.3,
                },
            ]
        }

        with patch.object(reporting, "_get_memory_client_for_report") as mock_get_client:
            mock_get_client.return_value = mock_client

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            assert len(evidence) == 1
            assert evidence[0]["category"] == "general"
            assert evidence[0]["content"] == "Port 22 is open"

    def test_retrieve_evidence_handles_list_response(self):
        """Test evidence retrieval with list response format"""
        mock_client = Mock()
        mock_client.list_memories.return_value = {
            "results": [
                {
                    "id": "mem1",
                    "memory": "Critical vulnerability found",
                    "metadata": {"category": "finding", "severity": "critical"},
                    "score": 0.99,
                }
            ]
        }

        with patch.object(reporting, "_get_memory_client_for_report") as mock_get_client:
            mock_get_client.return_value = mock_client

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            assert len(evidence) == 1
            assert evidence[0]["category"] == "finding"
            assert evidence[0]["severity"] == "critical"

    def test_retrieve_evidence_handles_error(self):
        """Test evidence retrieval handles errors gracefully"""
        mock_client = Mock()
        mock_client.list_memories.side_effect = Exception("Memory retrieval failed")

        with patch.object(reporting, "_get_memory_client_for_report") as mock_get_client:
            mock_get_client.return_value = mock_client

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
            )

            evidence = _retrieve_evidence(handler.state, handler.memory_config)

            assert evidence == []

class TestGenerateReport:
    """Test the report generation functionality"""

    def test_generate_report_with_evidence(self):
        """Test report generation with evidence"""
        evidence = [
            {
                "category": "finding",
                "content": "SQL injection vulnerability found",
                "severity": "high",
                "confidence": "90%",
            },
            {
                "category": "general",
                "content": "Port 80 is open",
                "severity": "unknown",
                "confidence": "unknown",
            },
        ]

        mock_agent = Mock()

        with patch("modules.handlers.reporting._retrieve_evidence") as mock_retrieve:
            mock_retrieve.return_value = evidence

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
            )

            # Mock the _generate_llm_report function
            with patch("modules.handlers.reporting._generate_llm_report") as mock_generate:
                mock_generate.return_value = "Generated security report content"

                with patch("modules.handlers.reporting._display_final_report") as mock_display:
                    with patch("modules.handlers.reporting._save_report_to_file") as mock_save:
                        handler.generate_final_report(mock_agent, "test.com", "security assessment")

                        mock_display.assert_called_once()
                        mock_save.assert_called_once()
                        assert handler.report_generated is True

    def test_generate_report_no_evidence(self):
        """Test report generation when no evidence is found"""
        mock_agent = Mock()

        with patch("modules.handlers.reporting._retrieve_evidence") as mock_retrieve:
            mock_retrieve.return_value = []

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
            )

            # No need to mock _generate_llm_report since it won't be called with no evidence
            with patch("modules.handlers.reporting._display_final_report") as mock_display:
                with patch("modules.handlers.reporting._save_report_to_file") as mock_save:
                    handler.generate_final_report(mock_agent, "test.com", "security assessment")

                    mock_display.assert_not_called()
                    mock_save.assert_not_called()
                    assert handler.report_generated is True

    def test_generate_report_single_execution(self):
        """Test report generation only executes once"""
        evidence = [
            {
                "category": "finding",
                "content": "Test finding",
                "severity": "high",
                "confidence": "90%",
            }
        ]
        mock_agent = Mock()

        with patch("modules.handlers.reporting._retrieve_evidence") as mock_retrieve:
            mock_retrieve.return_value = evidence

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
            )

            with patch("modules.handlers.reporting._generate_llm_report") as mock_generate:
                mock_generate.return_value = "Generated report"

                with patch("modules.handlers.reporting._display_final_report"):
                    with patch("modules.handlers.reporting._save_report_to_file"):
                        handler.generate_final_report(mock_agent, "test.com", "security assessment")
                        assert handler.report_generated is True

                        handler.generate_final_report(mock_agent, "test.com", "security assessment")
                        mock_retrieve.assert_called_once()

    def test_format_evidence_with_metadata(self):
        """Test evidence formatting includes metadata"""
        evidence = [
            {
                "category": "finding",
                "content": "SQL injection found",
                "severity": "high",
                "confidence": "90%",
            },
            {
                "category": "finding",
                "content": "XSS vulnerability",
                "severity": "medium",
                "confidence": "unknown",
            },
            {
                "category": "general",
                "content": "Port scan results",
                "severity": "unknown",
                "confidence": "unknown",
            },
        ]

        mock_agent = Mock()

        with patch("modules.handlers.reporting._retrieve_evidence") as mock_retrieve:
            mock_retrieve.return_value = evidence

            handler = ReasoningHandler(
                max_steps=50,
                operation_id="OP_20240101_120000",
                target="test.com",
            )

            # Mock the _generate_llm_report to check formatted evidence
            with patch("modules.handlers.reporting._generate_llm_report") as mock_generate:
                mock_generate.return_value = "Generated report"

                with patch("modules.handlers.reporting._display_final_report"):
                    with patch("modules.handlers.reporting._save_report_to_file"):
                        handler.generate_final_report(mock_agent, "test.com", "security assessment")

                        # Check that _generate_llm_report was called with proper arguments
                        mock_generate.assert_called_once()
                        call_args = mock_generate.call_args[1]
                        assert call_args["agent"] == mock_agent
                        assert call_args["target"] == "test.com"
                        assert call_args["objective"] == "security assessment"
                        assert call_args["evidence"] == evidence

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
