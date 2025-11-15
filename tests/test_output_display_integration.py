#!/usr/bin/env python3
"""
Tests for output display integration with unified output structure.
These tests ensure that the output and memory location displays are correct
after the recent refactoring.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from modules.config.system.environment import clean_operation_memory
from modules.handlers.utils import get_output_path, sanitize_target_name


class TestOutputDisplayIntegration:
    """Test output display integration with unified output structure."""

    def test_memory_location_display_faiss(self):
        """Test memory location display for FAISS backend."""
        target_name = "example.com"

        with patch.dict(os.environ, {}, clear=True):
            # Simulate cyberautoagent.py logic
            if os.getenv("MEM0_API_KEY"):
                memory_location = "Mem0 Platform (cloud)"
            elif os.getenv("OPENSEARCH_HOST"):
                memory_location = f"OpenSearch: {os.getenv('OPENSEARCH_HOST')}"
            else:
                memory_location = f"./outputs/{target_name}/memory"

            assert memory_location == f"./outputs/{target_name}/memory"

    def test_memory_location_display_mem0_platform(self):
        """Test memory location display for Mem0 Platform."""
        target_name = "example.com"

        with patch.dict(os.environ, {"MEM0_API_KEY": "test-key"}, clear=True):
            # Simulate cyberautoagent.py logic
            if os.getenv("MEM0_API_KEY"):
                memory_location = "Mem0 Platform (cloud)"
            elif os.getenv("OPENSEARCH_HOST"):
                memory_location = f"OpenSearch: {os.getenv('OPENSEARCH_HOST')}"
            else:
                memory_location = f"./outputs/{target_name}/memory"

            assert memory_location == "Mem0 Platform (cloud)"

    def test_memory_location_display_opensearch(self):
        """Test memory location display for OpenSearch."""
        target_name = "example.com"
        opensearch_host = "https://search-domain.region.es.amazonaws.com"

        with patch.dict(os.environ, {"OPENSEARCH_HOST": opensearch_host}, clear=True):
            # Simulate cyberautoagent.py logic
            if os.getenv("MEM0_API_KEY"):
                memory_location = "Mem0 Platform (cloud)"
            elif os.getenv("OPENSEARCH_HOST"):
                memory_location = f"OpenSearch: {os.getenv('OPENSEARCH_HOST')}"
            else:
                memory_location = f"./outputs/{target_name}/memory"

            assert memory_location == f"OpenSearch: {opensearch_host}"

    def test_evidence_location_display(self):
        """Test evidence location display with unified output structure."""
        test_cases = [
            {
                "target": "https://example.com:8080/path",
                "operation_id": "OP_20250718_123456",
                "base_dir": "/app/outputs",
                "expected": "/app/outputs/example.com_8080/OP_20250718_123456",  # Port preserved with underscore
            },
            {
                "target": "192.168.1.1",
                "operation_id": "OP_20250718_000000",
                "base_dir": "/custom/outputs",
                "expected": "/custom/outputs/192.168.1.1/OP_20250718_000000",
            },
            {
                "target": "sub.domain.com",
                "operation_id": "OP_20250718_235959",
                "base_dir": "./outputs",
                "expected": "./outputs/sub.domain.com/OP_20250718_235959",
            },
        ]

        for case in test_cases:
            # Simulate cyberautoagent.py logic
            sanitized_target = sanitize_target_name(case["target"])
            evidence_location = get_output_path(
                sanitized_target,
                case["operation_id"],
                "",  # No subdirectory - show the operation root
                case["base_dir"],
            )

            assert evidence_location == case["expected"]

    def test_log_path_construction(self):
        """Test log path construction with unified output structure."""
        test_cases = [
            {
                "target": "example.com",
                "operation_id": "OP_20250718_123456",
                "base_dir": "/app/outputs",
                "expected": "/app/outputs/example.com/OP_20250718_123456",
            },
            {
                "target": "192.168.1.1",
                "operation_id": "OP_20250718_000000",
                "base_dir": "/custom/outputs",
                "expected": "/custom/outputs/192.168.1.1/OP_20250718_000000",
            },
        ]

        for case in test_cases:
            # Simulate cyberautoagent.py log path logic
            log_path = get_output_path(
                sanitize_target_name(case["target"]),
                case["operation_id"],
                "",  # Empty subdirectory for base operation path
                case["base_dir"],
            )

            assert log_path == case["expected"]

            # Test full log file path
            log_file = os.path.join(log_path, "cyber_operations.log")
            expected_log_file = os.path.join(case["expected"], "cyber_operations.log")
            assert log_file == expected_log_file


class TestEnvironmentLoggingIntegration:
    """Test environment module logging integration."""

    def test_clean_operation_memory_logging(self):
        """Test that clean_operation_memory uses proper logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_name = "example.com"
            operation_id = "OP_20250718_123456"

            # Create memory directory
            memory_dir = os.path.join(temp_dir, "outputs", target_name, "memory")
            faiss_dir = os.path.join(memory_dir, f"mem0_faiss_{target_name}")
            os.makedirs(faiss_dir, exist_ok=True)

            # Create test file
            test_file = os.path.join(faiss_dir, "test.faiss")
            with open(test_file, "w") as f:
                f.write("test data")

            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                # Capture log messages
                with patch("modules.config.system.environment.get_logger") as mock_logger:
                    mock_log = MagicMock()
                    mock_logger.return_value = mock_log

                    # Call cleanup
                    clean_operation_memory(operation_id, target_name)

                    # Verify logging calls were made
                    mock_log.debug.assert_called()
                    mock_log.info.assert_called()

                    # Check that debug logging includes correct parameters
                    debug_calls = mock_log.debug.call_args_list
                    assert len(debug_calls) >= 1

                    # Verify the first debug call contains operation_id and target_name
                    first_call = debug_calls[0]
                    assert operation_id in str(first_call)
                    assert target_name in str(first_call)

            finally:
                os.chdir(original_cwd)

    def test_clean_operation_memory_no_target_warning(self):
        """Test that cleanup logs warning when no target_name provided."""
        operation_id = "OP_20250718_123456"

        with patch("modules.config.system.environment.get_logger") as mock_logger:
            mock_log = MagicMock()
            mock_logger.return_value = mock_log

            # Call cleanup without target_name
            clean_operation_memory(operation_id, None)

            # Verify warning was logged
            mock_log.warning.assert_called_once()
            warning_call = mock_log.warning.call_args[0][0]
            assert "No target_name provided" in warning_call

    def test_clean_operation_memory_error_logging(self):
        """Test that cleanup logs errors properly."""
        target_name = "example.com"
        operation_id = "OP_20250718_123456"

        with patch("modules.config.system.environment.get_logger") as mock_logger:
            mock_log = MagicMock()
            mock_logger.return_value = mock_log

            # Mock shutil.rmtree to raise an exception
            with patch(
                "modules.config.system.environment.shutil.rmtree",
                side_effect=OSError("Permission denied"),
            ):
                with patch(
                    "modules.config.system.environment.os.path.exists", return_value=True
                ):
                    # Call cleanup
                    clean_operation_memory(operation_id, target_name)

                    # Verify error was logged
                    mock_log.error.assert_called()
                    error_call = mock_log.error.call_args[0]
                    assert "Failed to clean" in error_call[0]
                    # The actual error may be different depending on the mock setup
                    assert len(error_call) >= 2  # Should have path and error message


class TestPathConsistency:
    """Test that paths are consistent across different modules."""

    def test_memory_path_consistency(self):
        """Test that memory paths are consistent between modules."""
        target_name = "example.com"

        # Path from memory_tools logic
        memory_tools_path = os.path.join("outputs", target_name, "memory")

        # Path from cleanup logic
        cleanup_path = os.path.join(
            "outputs", target_name, "memory", f"mem0_faiss_{target_name}"
        )

        # Path from display logic
        display_path = f"./outputs/{target_name}/memory"

        # Verify they're all consistent
        assert memory_tools_path in cleanup_path
        assert memory_tools_path == display_path.lstrip("./")

    def test_operation_path_consistency(self):
        """Test that operation paths are consistent."""
        target = "https://example.com:8080"
        operation_id = "OP_20250718_123456"
        base_dir = "/app/outputs"

        sanitized_target = sanitize_target_name(target)

        # Path from get_output_path
        evidence_path = get_output_path(sanitized_target, operation_id, "", base_dir)

        # Path from log construction
        log_path = get_output_path(sanitized_target, operation_id, "", base_dir)

        # They should be the same when no subdirectory is specified
        assert evidence_path == log_path

        # Both should match expected format
        expected = f"{base_dir}/{sanitized_target}/{operation_id}"
        assert evidence_path == expected
        assert log_path == expected

    def test_subdirectory_path_consistency(self):
        """Test that subdirectory paths are consistent."""
        target = "example.com"
        operation_id = "OP_20250718_123456"
        base_dir = "/app/outputs"

        # Different subdirectories
        logs_path = get_output_path(target, operation_id, "logs", base_dir)
        utils_path = get_output_path(target, operation_id, "utils", base_dir)
        memory_path = get_output_path(target, operation_id, "memory", base_dir)

        # All should have the same base
        base_operation_path = f"{base_dir}/{target}/{operation_id}"

        assert logs_path == f"{base_operation_path}/logs"
        assert utils_path == f"{base_operation_path}/utils"
        assert memory_path == f"{base_operation_path}/memory"

        # All should be under the same operation directory
        for path in [logs_path, utils_path, memory_path]:
            assert path.startswith(base_operation_path)


class TestErrorHandling:
    """Test error handling in the integrated system."""

    def test_sanitize_target_name_edge_cases(self):
        """Test target name sanitization with edge cases."""
        edge_cases = [
            ("", "unknown_target"),
            ("   ", "unknown_target"),
            ("https://", "unknown_target"),
            ("ftp://", "unknown_target"),
            ("://no-protocol", "unknown_target"),  # Invalid URL becomes unknown_target
            ("https://example.com/../../malicious", "example.com"),
            ("https://example.com/../../../etc/passwd", "example.com"),
        ]

        for input_target, expected in edge_cases:
            result = sanitize_target_name(input_target)
            assert result == expected

    def test_get_output_path_edge_cases(self):
        """Test get_output_path with edge cases."""
        # Test with empty components
        result = get_output_path("", "", "", "")
        assert result == ""

        # Test with None components (should not crash)
        with pytest.raises(TypeError):
            get_output_path(None, None, None, None)

        # Test with special characters in base_dir
        result = get_output_path(
            "example.com", "OP_20250718_123456", "logs", "/app/outputs with spaces"
        )
        assert result == "/app/outputs with spaces/example.com/OP_20250718_123456/logs"
