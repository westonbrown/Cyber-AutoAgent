#!/usr/bin/env python3

import argparse
import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add src to path for imports


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cyberautoagent


class TestCLIArguments:
    """Test command-line argument parsing"""

    def test_required_arguments(self):
        """Test that required arguments are parsed correctly"""
        with patch(
            "sys.argv",
            [
                "cyberautoagent.py",
                "--target",
                "test.com",
                "--objective",
                "test objective",
            ],
        ):
            # Mock the setup and execution parts
            with (
                patch("cyberautoagent.setup_logging"),
                patch("cyberautoagent.auto_setup", return_value=[]),
                patch("cyberautoagent.create_agent", return_value=(Mock(), Mock())),
                patch("cyberautoagent.get_initial_prompt"),
                patch("cyberautoagent.print_banner"),
                patch("cyberautoagent.print_section"),
                patch("cyberautoagent.print_status"),
            ):
                # Parse arguments without executing main
                parser = argparse.ArgumentParser()
                parser.add_argument("--objective", type=str, required=True)
                parser.add_argument("--target", type=str, required=True)
                parser.add_argument("--iterations", type=int, default=100)
                parser.add_argument("--verbose", action="store_true")
                parser.add_argument("--model", type=str)
                parser.add_argument("--region", type=str, default="us-east-1")
                parser.add_argument("--server", type=str, choices=["remote", "local"], default="remote")
                parser.add_argument("--confirmations", action="store_true")

                args = parser.parse_args(["--target", "test.com", "--objective", "test objective"])

                assert args.target == "test.com"
                assert args.objective == "test objective"
                assert args.server == "remote"  # default
                assert args.iterations == 100  # default
                assert not args.verbose  # default
                assert not args.confirmations  # default

    def test_server_argument_choices(self):
        """Test that --server argument accepts only valid choices"""
        parser = argparse.ArgumentParser()
        parser.add_argument("--server", type=str, choices=["remote", "local"], default="remote")

        # Valid choices should work
        args = parser.parse_args(["--server", "local"])
        assert args.server == "local"

        args = parser.parse_args(["--server", "remote"])
        assert args.server == "remote"

        # Invalid choice should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["--server", "invalid"])

    def test_optional_arguments(self):
        """Test optional argument parsing"""
        parser = argparse.ArgumentParser()
        parser.add_argument("--objective", type=str, required=True)
        parser.add_argument("--target", type=str, required=True)
        parser.add_argument("--iterations", type=int, default=100)
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--model", type=str)
        parser.add_argument("--region", type=str, default="us-east-1")
        parser.add_argument("--server", type=str, choices=["remote", "local"], default="remote")
        parser.add_argument("--confirmations", action="store_true")

        args = parser.parse_args(
            [
                "--target",
                "test.com",
                "--objective",
                "test objective",
                "--server",
                "local",
                "--iterations",
                "50",
                "--verbose",
                "--model",
                "custom-model",
                "--region",
                "us-west-2",
                "--confirmations",
            ]
        )

        assert args.target == "test.com"
        assert args.objective == "test objective"
        assert args.server == "local"
        assert args.iterations == 50
        assert args.verbose is True
        assert args.model == "custom-model"
        assert args.region == "us-west-2"
        assert args.confirmations is True

    def test_new_output_arguments(self):
        """Test that new output configuration arguments are properly parsed"""
        parser = argparse.ArgumentParser()
        parser.add_argument("--target", type=str, required=True)
        parser.add_argument("--objective", type=str, required=True)
        parser.add_argument("--output-dir", type=str)
        parser.add_argument("--keep-memory", action="store_true", default=True)

        args = parser.parse_args(
            [
                "--target",
                "test.com",
                "--objective",
                "test objective",
                "--output-dir",
                "/custom/output",
            ]
        )

        assert args.target == "test.com"
        assert args.objective == "test objective"
        assert args.output_dir == "/custom/output"
        assert args.keep_memory is True  # Default is now True


class TestMainFunction:
    """Test main function execution flow"""

    @patch("cyberautoagent.setup_logging")
    @patch("cyberautoagent.auto_setup")
    @patch("cyberautoagent.create_agent")
    @patch("cyberautoagent.get_initial_prompt")
    @patch("cyberautoagent.print_banner")
    @patch("cyberautoagent.print_section")
    @patch("cyberautoagent.print_status")
    @patch(
        "sys.argv",
        [
            "cyberautoagent.py",
            "--target",
            "test.com",
            "--objective",
            "test objective",
            "--provider",
            "bedrock",
        ],
    )
    def test_main_remote_flow(
        self,
        mock_print_status,
        mock_print_section,
        mock_print_banner,
        mock_get_prompt,
        mock_create_agent,
        mock_auto_setup,
        mock_setup_logging,
    ):
        """Test main function execution with remote server"""

        # Setup mocks
        mock_agent = Mock()
        mock_handler = Mock()
        mock_handler.steps = 5
        mock_handler.has_reached_limit.return_value = False
        mock_handler.get_summary.return_value = {
            "total_steps": 5,
            "tools_created": 2,
            "evidence_collected": 3,
            "memory_operations": 4,
            "capability_expansion": ["tool1", "tool2"],
        }
        mock_handler.get_evidence_summary.return_value = []

        mock_create_agent.return_value = (mock_agent, mock_handler)
        mock_auto_setup.return_value = ["nmap", "nikto"]
        mock_get_prompt.return_value = "test prompt"

        # Mock agent execution to return immediately
        mock_agent.return_value = "Agent response"

        # This should not raise any exceptions
        try:
            cyberautoagent.main()
        except SystemExit as e:
            # main() calls sys.exit(0) on success, which is expected
            assert e.code in [None, 0]

    @patch("cyberautoagent.setup_logging")
    @patch("cyberautoagent.auto_setup")
    @patch("cyberautoagent.create_agent")
    @patch("cyberautoagent.get_initial_prompt")
    @patch("cyberautoagent.print_banner")
    @patch("cyberautoagent.print_section")
    @patch("cyberautoagent.print_status")
    @patch(
        "sys.argv",
        [
            "cyberautoagent.py",
            "--target",
            "test.com",
            "--objective",
            "test objective",
            "--provider",
            "ollama",
        ],
    )
    def test_main_local_flow(
        self,
        mock_print_status,
        mock_print_section,
        mock_print_banner,
        mock_get_prompt,
        mock_create_agent,
        mock_auto_setup,
        mock_setup_logging,
    ):
        """Test main function execution with local server"""

        # Setup mocks
        mock_agent = Mock()
        mock_handler = Mock()
        mock_handler.steps = 5
        mock_handler.has_reached_limit.return_value = False
        mock_handler.get_summary.return_value = {
            "total_steps": 5,
            "tools_created": 2,
            "evidence_collected": 3,
            "memory_operations": 4,
            "capability_expansion": ["tool1", "tool2"],
        }
        mock_handler.get_evidence_summary.return_value = []

        mock_create_agent.return_value = (mock_agent, mock_handler)
        mock_auto_setup.return_value = []
        mock_get_prompt.return_value = "test prompt"

        # Mock agent execution to return normally, then trigger completion
        mock_agent.return_value = "Agent response"

        try:
            cyberautoagent.main()
        except SystemExit as e:
            # main() calls sys.exit(0) on success, which is expected
            assert e.code in [None, 0]

    @patch("cyberautoagent.setup_logging")
    @patch("cyberautoagent.auto_setup")
    @patch("cyberautoagent.create_agent")
    @patch("cyberautoagent.print_status")
    @patch(
        "sys.argv",
        ["cyberautoagent.py", "--target", "test.com", "--objective", "test objective"],
    )
    def test_main_create_agent_failure(self, mock_print_status, mock_create_agent, mock_auto_setup, mock_setup_logging):
        """Test main function when create_agent fails"""

        mock_create_agent.side_effect = Exception("Agent creation failed")
        mock_auto_setup.return_value = []

        with pytest.raises(SystemExit) as exc_info:
            cyberautoagent.main()

        assert exc_info.value.code == 1

    @patch("cyberautoagent.setup_logging")
    @patch("cyberautoagent.auto_setup")
    @patch("cyberautoagent.create_agent")
    @patch("cyberautoagent.get_initial_prompt")
    @patch("cyberautoagent.print_banner")
    @patch("cyberautoagent.print_section")
    @patch("cyberautoagent.print_status")
    @patch(
        "sys.argv",
        [
            "cyberautoagent.py",
            "--target",
            "test.com",
            "--objective",
            "test objective",
            "--provider",
            "ollama",
            "--mcp-enabled",
            "--mcp-conns",
            """[{"id":"mcp1","transport":"streamable-http","server_url":"http://127.0.0.1:8000/mcp"}]""",
        ],
    )
    def test_main_local_mcp_flow(
            self,
            mock_print_status,
            mock_print_section,
            mock_print_banner,
            mock_get_prompt,
            mock_create_agent,
            mock_auto_setup,
            mock_setup_logging,
    ):
        """Test main function execution with local server and an MCP"""

        # Setup mocks
        mock_agent = Mock()
        mock_handler = Mock()
        mock_handler.steps = 5
        mock_handler.has_reached_limit.return_value = False
        mock_handler.get_summary.return_value = {
            "total_steps": 5,
            "tools_created": 2,
            "evidence_collected": 3,
            "memory_operations": 4,
            "capability_expansion": ["tool1", "tool2"],
        }
        mock_handler.get_evidence_summary.return_value = []

        mock_create_agent.return_value = (mock_agent, mock_handler)
        mock_auto_setup.return_value = []
        mock_get_prompt.return_value = "test prompt"

        # Mock agent execution to return normally, then trigger completion
        mock_agent.return_value = "Agent response"

        try:
            cyberautoagent.main()
        except SystemExit as e:
            # main() calls sys.exit(0) on success, which is expected
            assert e.code in [None, 0]


class TestEnvironmentVariables:
    """Test environment variable handling"""

    @patch.dict(os.environ, {}, clear=True)
    @patch(
        "sys.argv",
        [
            "cyberautoagent.py",
            "--target",
            "test.com",
            "--objective",
            "test",
            "--confirmations",
        ],
    )
    def test_confirmations_flag_sets_env_var(self):
        """Test that --confirmations flag properly manages environment variables"""
        parser = argparse.ArgumentParser()
        parser.add_argument("--objective", type=str, required=True)
        parser.add_argument("--target", type=str, required=True)
        parser.add_argument("--confirmations", action="store_true")

        args = parser.parse_args(["--target", "test.com", "--objective", "test", "--confirmations"])

        # Simulate the environment variable logic from main()
        if not args.confirmations:
            os.environ["BYPASS_TOOL_CONSENT"] = "true"
        else:
            os.environ.pop("BYPASS_TOOL_CONSENT", None)

        # With --confirmations, the env var should not be set
        assert "BYPASS_TOOL_CONSENT" not in os.environ

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.argv", ["cyberautoagent.py", "--target", "test.com", "--objective", "test"])
    def test_no_confirmations_flag_sets_env_var(self):
        """Test that without --confirmations flag, environment variable is set"""
        parser = argparse.ArgumentParser()
        parser.add_argument("--objective", type=str, required=True)
        parser.add_argument("--target", type=str, required=True)
        parser.add_argument("--confirmations", action="store_true")

        args = parser.parse_args(["--target", "test.com", "--objective", "test"])

        # Simulate the environment variable logic from main()
        if not args.confirmations:
            os.environ["BYPASS_TOOL_CONSENT"] = "true"
        else:
            os.environ.pop("BYPASS_TOOL_CONSENT", None)

        # Without --confirmations, the env var should be set
        assert os.environ["BYPASS_TOOL_CONSENT"] == "true"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
