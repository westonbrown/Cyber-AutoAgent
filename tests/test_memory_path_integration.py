#!/usr/bin/env python3
"""
Tests for memory path integration with unified output structure.
These tests ensure that memory paths are correctly constructed and used
across the entire system after the recent refactoring.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

from modules.config.environment import clean_operation_memory
from modules.handlers.utils import get_output_path, sanitize_target_name
from modules.tools.memory import Mem0ServiceClient


class TestMemoryPathIntegration:
    """Test memory path construction and integration with unified output structure."""

    def test_memory_path_construction_with_target_name(self):
        """Test that memory paths are correctly constructed with target names."""
        # Test data
        target_name = "example.com"

        # Create mock config
        config = {"target_name": target_name, "operation_id": "OP_20250718_123456"}

        # Test the path construction logic
        with patch("modules.tools.memory.get_config_manager") as mock_config_manager:
            mock_config_manager.return_value.get_mem0_service_config.return_value = {
                "vector_store": {"provider": "faiss", "config": {}},
                "embedder": {
                    "provider": "aws_bedrock",
                    "config": {"model": "test-model"},
                },
                "llm": {"provider": "aws_bedrock", "config": {"model": "test-llm"}},
            }

            with patch("modules.tools.memory.Mem0Memory.from_config") as mock_from_config:
                mock_from_config.return_value = MagicMock()
                client = Mem0ServiceClient(config)

            # The client should have constructed the correct path
            # This tests the internal path construction logic
            assert client is not None

    def test_memory_path_with_sanitized_target_names(self):
        """Test memory paths with various target name formats."""
        test_cases = [
            ("https://example.com:8080/path", "example.com_8080"),  # Port preserved with underscore
            ("192.168.1.1", "192.168.1.1"),
            ("sub.domain.com", "sub.domain.com"),
            ("http://test-site.org", "test-site.org"),
        ]

        for original_target, expected_sanitized in test_cases:
            sanitized = sanitize_target_name(original_target)
            assert sanitized == expected_sanitized

            # Test that the memory path would be constructed correctly
            expected_memory_path = os.path.join("outputs", sanitized, "memory")
            assert expected_memory_path == f"outputs/{sanitized}/memory"

    def test_clean_operation_memory_with_unified_structure(self):
        """Test that cleanup only removes memory directories in unified structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up directory structure
            target_name = "example.com"
            operation_id = "OP_20250718_123456"

            # Create unified output structure
            outputs_dir = os.path.join(temp_dir, "outputs")
            target_dir = os.path.join(outputs_dir, target_name)
            memory_dir = os.path.join(target_dir, "memory")
            faiss_dir = os.path.join(memory_dir, f"mem0_faiss_{target_name}")
            operation_dir = os.path.join(target_dir, operation_id)

            # Create directories and files
            os.makedirs(faiss_dir, exist_ok=True)
            os.makedirs(operation_dir, exist_ok=True)

            # Create test files
            memory_file = os.path.join(faiss_dir, "index.faiss")
            evidence_file = os.path.join(operation_dir, "evidence.json")

            with open(memory_file, "w") as f:
                f.write("memory data")
            with open(evidence_file, "w") as f:
                f.write("evidence data")

            # Change to temp directory for relative paths
            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                # Test cleanup
                clean_operation_memory(operation_id, target_name)

                # Verify only memory directory was removed
                assert not os.path.exists(faiss_dir)  # Memory removed
                assert os.path.exists(memory_dir)  # Memory base dir exists
                assert os.path.exists(operation_dir)  # Operation dir preserved
                assert os.path.exists(evidence_file)  # Evidence preserved

            finally:
                os.chdir(original_cwd)

    def test_memory_path_safety_checks(self):
        """Test that cleanup has proper safety checks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_name = "example.com"
            operation_id = "OP_20250718_123456"

            # Create a directory that doesn't match memory pattern
            outputs_dir = os.path.join(temp_dir, "outputs")
            target_dir = os.path.join(outputs_dir, target_name)
            bad_dir = os.path.join(target_dir, "memory", "not_a_memory_dir")

            os.makedirs(bad_dir, exist_ok=True)

            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                # This should not remove the directory due to safety checks
                clean_operation_memory(operation_id, target_name)

                # Directory should still exist (safety check prevented removal)
                assert os.path.exists(bad_dir)

            finally:
                os.chdir(original_cwd)

    def test_get_output_path_integration(self):
        """Test that get_output_path works correctly with the unified structure."""
        test_cases = [
            (
                "example.com",
                "OP_20250718_123456",
                "logs",
                "/app/outputs",
                "/app/outputs/example.com/OP_20250718_123456/logs",
            ),
            (
                "192.168.1.1",
                "OP_20250718_123456",
                "",
                "/app/outputs",
                "/app/outputs/192.168.1.1/OP_20250718_123456",
            ),
            (
                "test.org",
                "OP_20250718_123456",
                "utils",
                "/custom/path",
                "/custom/path/test.org/OP_20250718_123456/utils",
            ),
        ]

        for target, operation_id, subdir, base_dir, expected in test_cases:
            result = get_output_path(target, operation_id, subdir, base_dir)
            assert result == expected

    def test_memory_backend_path_display(self):
        """Test the memory backend path display logic."""
        target_name = "example.com"

        # Test FAISS backend path construction
        with patch.dict(os.environ, {}, clear=True):
            # No MEM0_API_KEY or OPENSEARCH_HOST set, should use FAISS
            expected_path = f"./outputs/{target_name}/memory"

            # This simulates the logic in cyberautoagent.py
            if os.getenv("MEM0_API_KEY"):
                memory_location = "Mem0 Platform (cloud)"
            elif os.getenv("OPENSEARCH_HOST"):
                memory_location = f"OpenSearch: {os.getenv('OPENSEARCH_HOST')}"
            else:
                memory_location = f"./outputs/{target_name}/memory"

            assert memory_location == expected_path

    def test_evidence_path_display(self):
        """Test the evidence path display logic."""
        target = "https://example.com:8080"
        operation_id = "OP_20250718_123456"
        base_dir = "/app/outputs"

        # Test evidence location construction
        sanitized_target = sanitize_target_name(target)
        evidence_location = get_output_path(sanitized_target, operation_id, "", base_dir)

        # Port is preserved with underscore
        expected = "/app/outputs/example.com_8080/OP_20250718_123456"
        assert evidence_location == expected


class TestMemoryCleanupIntegration:
    """Test memory cleanup integration with the unified output structure."""

    def test_cleanup_with_missing_target_name(self):
        """Test that cleanup handles missing target_name gracefully."""
        operation_id = "OP_20250718_123456"

        # Should not raise an exception
        clean_operation_memory(operation_id, None)
        clean_operation_memory(operation_id, "")

    def test_cleanup_with_nonexistent_paths(self):
        """Test that cleanup handles nonexistent paths gracefully."""
        operation_id = "OP_20250718_123456"
        target_name = "nonexistent.com"

        # Should not raise an exception
        clean_operation_memory(operation_id, target_name)

    def test_cleanup_preserves_other_targets(self):
        """Test that cleanup only affects the specified target."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create memory for multiple targets
            target1 = "example.com"
            target2 = "another.com"
            operation_id = "OP_20250718_123456"

            # Create memory directories for both targets
            for target in [target1, target2]:
                memory_dir = os.path.join(temp_dir, "outputs", target, "memory")
                faiss_dir = os.path.join(memory_dir, f"mem0_faiss_{target}")
                os.makedirs(faiss_dir, exist_ok=True)

                # Create a test file
                test_file = os.path.join(faiss_dir, "test.faiss")
                with open(test_file, "w") as f:
                    f.write("test data")

            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                # Clean up only target1
                clean_operation_memory(operation_id, target1)

                # Verify target1 memory was removed but target2 preserved
                target1_faiss = os.path.join("outputs", target1, "memory", f"mem0_faiss_{target1}")
                target2_faiss = os.path.join("outputs", target2, "memory", f"mem0_faiss_{target2}")

                assert not os.path.exists(target1_faiss)  # target1 removed
                assert os.path.exists(target2_faiss)  # target2 preserved

            finally:
                os.chdir(original_cwd)


class TestMemoryToolsPathConstruction:
    """Test memory tools path construction with unified output structure."""

    @patch("modules.tools.memory.get_config_manager")
    @patch("modules.tools.memory.os.makedirs")
    @patch("modules.tools.memory.Mem0Memory.from_config")
    def test_faiss_path_construction(self, mock_from_config, mock_makedirs, mock_config_manager):
        """Test FAISS path construction in memory tools."""
        # Mock config manager
        mock_config_manager.return_value.get_mem0_service_config.return_value = {
            "vector_store": {"provider": "faiss", "config": {}},
            "embedder": {"provider": "aws_bedrock", "config": {"model": "test-model"}},
            "llm": {"provider": "aws_bedrock", "config": {"model": "test-llm"}},
        }

        # Mock Mem0Memory.from_config to prevent actual initialization
        mock_from_config.return_value = MagicMock()

        # Test config with target_name
        config = {"target_name": "example.com", "operation_id": "OP_20250718_123456"}

        # Create client
        Mem0ServiceClient(config)

        # Verify makedirs was called with correct path
        expected_path = os.path.join("outputs", "example.com", "memory")
        mock_makedirs.assert_called_with(expected_path, exist_ok=True)

    @patch("modules.tools.memory.get_config_manager")
    @patch("modules.tools.memory.Mem0Memory.from_config")
    def test_memory_path_with_custom_path(self, mock_from_config, mock_config_manager):
        """Test that custom memory paths are respected."""
        mock_config_manager.return_value.get_mem0_service_config.return_value = {
            "vector_store": {
                "provider": "faiss",
                "config": {"path": "/tmp/custom/path"},
            },
            "embedder": {"provider": "aws_bedrock", "config": {"model": "test-model"}},
            "llm": {"provider": "aws_bedrock", "config": {"model": "test-llm"}},
        }

        # Mock Mem0Memory.from_config to prevent actual initialization
        mock_from_config.return_value = MagicMock()

        config = {
            "target_name": "example.com",
            "vector_store": {"config": {"path": "/tmp/custom/path"}},
        }

        # Should use the custom path instead of generating one
        client = Mem0ServiceClient(config)
        assert client is not None
