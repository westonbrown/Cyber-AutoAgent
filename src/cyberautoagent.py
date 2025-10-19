#!/usr/bin/env python3
"""
Cyber-AutoAgent - Autonomous Cybersecurity Assessment Tool
=========================================================

An autonomous cybersecurity agent powered by Strands framework.
Conducts authorized penetration testing with intelligent tool selection and
evidence collection capabilities.

⚠️  EXPERIMENTAL SOFTWARE - USE ONLY IN AUTHORIZED, SAFE, SANDBOXED ENVIRONMENTS ⚠️

For educational and authorized security testing purposes only.
Ensure you have explicit permission before testing any targets.

Author: Aaron Brown
License: MIT
"""

import argparse
import atexit
import base64
import os
import re
import signal
import socket
import sys
import threading
import time
import traceback
import warnings
from datetime import datetime

# Third-party imports
import requests
from opentelemetry import trace
from strands.telemetry.config import StrandsTelemetry
from requests.exceptions import (
    ReadTimeout as RequestsReadTimeout,
    ConnectionError as RequestsConnectionError,
)
from botocore.exceptions import (
    ReadTimeoutError as BotoReadTimeoutError,
    EndpointConnectionError as BotoEndpointConnectionError,
    ConnectTimeoutError as BotoConnectTimeoutError,
)

# Local imports
from modules.agents.cyber_autoagent import AgentConfig, create_agent
from modules.config.environment import auto_setup, clean_operation_memory, setup_logging
from modules.config.manager import get_config_manager
from modules.handlers.base import StepLimitReached
from strands.types.exceptions import MaxTokensReachedException
from modules.handlers.utils import (
    Colors,
    get_output_path,
    get_terminal_width,
    print_banner,
    print_section,
    print_status,
    sanitize_target_name,
)

warnings.filterwarnings("ignore", category=DeprecationWarning)


# Backward-compatibility: provide a placeholder symbol so tests can patch it
# The real value is set later during runtime execution.
def get_initial_prompt():  # noqa: D401
    """Placeholder function; patched in tests and set at runtime."""
    return ""


def detect_deployment_mode():
    """
    Detect deployment mode for appropriate observability defaults.

    Returns:
        str: 'cli' (Python CLI), 'container' (single container), or 'compose' (full stack)
    """

    def is_docker():
        """Check if running inside a Docker container."""
        return os.path.exists("/.dockerenv") or os.path.exists("/app")

    def is_langfuse_available():
        """Check if Langfuse service is available."""
        try:
            if is_docker():
                # In Docker, try to connect to langfuse-web service
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(("langfuse-web", 3000))
                sock.close()
                return result == 0
            else:
                # Outside Docker, check localhost
                if requests is None:
                    return False  # requests not installed
                response = requests.get(
                    "http://localhost:3000/api/public/health", timeout=2
                )
                return response.status_code == 200
        except Exception:
            return False

    if is_docker():
        if is_langfuse_available():
            return "compose"  # Full Docker Compose stack
        else:
            return "container"  # Single container mode
    else:
        if is_langfuse_available():
            return "compose"  # Local development with Langfuse
        else:
            return "cli"  # Pure Python CLI mode


def setup_telemetry(logger):
    """
    Setup telemetry system with separated concerns:
    1. Local telemetry (always enabled) - for token counting, cost tracking, metrics
    2. Remote observability (deployment-aware) - for Langfuse trace export

    Local telemetry provides essential metrics for UI display regardless of deployment mode.
    Remote observability is only enabled when Langfuse infrastructure is available.
    """
    deployment_mode = detect_deployment_mode()

    # Set smart defaults based on deployment mode
    if deployment_mode == "compose":
        default_observability = "true"
        logger.info(
            "Detected full-stack deployment mode - observability enabled by default"
        )
    else:
        default_observability = "false"
        logger.info(
            "Detected %s deployment mode - observability disabled by default",
            deployment_mode,
        )
        logger.info(
            "To enable observability, set ENABLE_OBSERVABILITY=true and ensure Langfuse is running"
        )

    # Always initialize Strands telemetry for local metrics (token counting, cost tracking)
    # This sets up the global tracer provider that the Agent will use
    telemetry = StrandsTelemetry()
    logger.info("Strands telemetry initialized - token counting enabled")

    # Check if remote observability (Langfuse export) is enabled
    # Keep it simple: in React UI mode, the app is the source of truth; otherwise fall back to previous default
    ui_mode = os.getenv("CYBER_UI_MODE", "").lower()
    if ui_mode == "react":
        observability_enabled = (
            os.getenv("ENABLE_OBSERVABILITY", "false").lower() == "true"
        )
        logger.info(
            "React UI mode: observability %s by application",
            "enabled" if observability_enabled else "disabled",
        )
    else:
        observability_enabled = (
            os.getenv("ENABLE_OBSERVABILITY", default_observability).lower() == "true"
        )
        logger.info(
            "Non-UI/CLI mode: observability %s (fallback defaults)",
            "enabled" if observability_enabled else "disabled",
        )

    if observability_enabled:
        logger.info("Remote observability enabled - configuring Langfuse export")

        # Configure Langfuse connection parameters first
        setup_langfuse_connection(logger, deployment_mode)

        # Then setup OTLP exporter which will use the environment variables
        telemetry.setup_otlp_exporter()
        logger.info("OTLP exporter configured - traces will be exported to Langfuse")
    else:
        logger.info("Remote observability disabled - metrics available locally only")
        logger.debug("Token counting and cost tracking enabled via local telemetry")

    return telemetry


def setup_langfuse_connection(logger, deployment_mode):
    """Setup Langfuse connection parameters for remote observability."""

    def is_docker():
        """Check if running inside a Docker container."""
        return os.path.exists("/.dockerenv") or os.path.exists("/app")

    # Use langfuse-web:3000 when in Docker, localhost:3000 otherwise
    default_host = (
        "http://langfuse-web:3000" if is_docker() else "http://localhost:3000"
    )
    host = os.getenv("LANGFUSE_HOST", default_host)
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "cyber-public")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "cyber-secret")

    # Create auth token for Langfuse
    auth_token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

    # Set OpenTelemetry environment variables that Strands SDK will use
    os.environ["OTEL_SERVICE_NAME"] = "cyber-autoagent"
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{host}/api/public/otel"
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth_token}"

    logger.info("Langfuse connection configured at %s", host)
    logger.info("OTLP endpoint: %s", os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"])
    logger.info("View traces at %s (login: admin@cyber-autoagent.com/changeme)", host)


# Global flag for interrupt handling
interrupted = False


def signal_handler(signum, frame):  # pylint: disable=unused-argument
    """Handle interrupt signals gracefully"""
    global interrupted
    interrupted = True

    # Determine signal type for appropriate message
    if signum == signal.SIGINT:
        signal_name = "SIGINT (Ctrl+C)"
    elif signum == signal.SIGTSTP:
        signal_name = "SIGTSTP (Ctrl+Z)"
    elif signum == signal.SIGTERM:
        signal_name = "SIGTERM (ESC Kill Switch)"
    else:
        signal_name = f"Signal {signum}"

    print(f"\n\033[93m[!] {signal_name} received. Stopping agent gracefully...\033[0m")

    # For swarm operations, we need to be more forceful
    # Check if we're in a swarm operation by looking at the call stack
    stack = traceback.extract_stack()
    in_swarm = any(
        "swarm" in str(frame_info.filename).lower()
        or "swarm" in str(frame_info.name).lower()
        for frame_info in stack
    )

    if in_swarm:
        print(
            "\033[91m[!] Swarm operation detected - forcing immediate termination\033[0m"
        )

        # Force exit after a short delay to allow cleanup
        def force_exit():
            time.sleep(2)
            print("\033[91m[!] Force terminating swarm operation\033[0m")
            os._exit(1)

        threading.Thread(target=force_exit, daemon=True).start()

    # Raise KeyboardInterrupt to interrupt current operation
    raise KeyboardInterrupt("User interrupted operation")


def main():
    """Main execution function"""
    global interrupted

    # Initialize telemetry variable for use in finally block
    telemetry = None

    # Set up signal handlers for Ctrl+C, Ctrl+Z, and SIGTERM (ESC in UI)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTSTP, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check for service mode before normal argument parsing to avoid validation issues
    is_service_mode = "--service-mode" in sys.argv

    # Parse command line arguments first to get the confirmations flag
    parser = argparse.ArgumentParser(
        description="Cyber-AutoAgent - Autonomous Cybersecurity Assessment Tool",
        epilog="⚠️  Use only on authorized targets in safe environments ⚠️",
    )
    parser.add_argument(
        "--module",
        type=str,
        default="general",
        help="Security operational plugins to use (e.g., general, ctf, etc.)",
    )
    parser.add_argument(
        "--objective",
        type=str,
        required=not is_service_mode,
        help="Security assessment objective (required unless in service mode)",
    )
    parser.add_argument(
        "--target",
        type=str,
        required=not is_service_mode,
        help="Target system/network to assess (ensure you have permission!)",
    )
    parser.add_argument(
        "--service-mode",
        action="store_true",
        help="Run in service mode for containerized deployments (keeps container alive)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Maximum tool executions before stopping (default: 100)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output with detailed debug logging",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model ID to use (defaults configured in config.py)",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        help="AWS region for Bedrock (default: from AWS_REGION or us-east-1)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["bedrock", "ollama", "litellm"],
        default=os.getenv("CYBER_AGENT_PROVIDER", "bedrock"),
        help="Model provider: 'bedrock' for AWS Bedrock, 'ollama' for local models, 'litellm' for universal access (default: from CYBER_AGENT_PROVIDER or bedrock)",
    )
    parser.add_argument(
        "--confirmations",
        action="store_true",
        help="Enable tool confirmation prompts (default: disabled)",
    )
    parser.add_argument(
        "--memory-path",
        type=str,
        help="Path to existing FAISS memory store to load past memories (e.g., /outputs/target_name/OP_20240320_101530)",
    )
    parser.add_argument(
        "--memory-mode",
        type=str,
        choices=["auto", "fresh"],
        default="auto",
        help="Memory initialization mode: 'auto' loads existing memory if found (default), 'fresh' starts with new memory",
    )
    parser.add_argument(
        "--keep-memory",
        action="store_true",
        default=True,
        help="Keep memory data after operation completes (default: true)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Base directory for output artifacts (default: ./outputs)",
    )
    parser.add_argument(
        "--eval-rubric",
        action="store_true",
        help="Enable rubric-based evaluation in addition to Ragas metrics",
    )

    args = parser.parse_args()

    # Always check environment variable first for objective (React UI passes it this way)
    env_objective = os.environ.get("CYBER_OBJECTIVE")
    if env_objective:
        args.objective = env_objective  # Env var takes precedence

    # Persist provider/model selections to environment for downstream configuration
    if args.provider:
        os.environ["CYBER_AGENT_PROVIDER"] = args.provider
    if args.model:
        os.environ["CYBER_AGENT_LLM_MODEL"] = args.model

    # Handle service mode
    if args.service_mode:
        # If full parameters are provided (common when the app execs into the service
        # container with explicit args/env), auto-run a one-shot assessment instead of idling.
        has_params = bool(args.target and args.objective)
        ui_mode_env = os.environ.get("CYBER_UI_MODE", "").lower()
        auto_run = has_params and ui_mode_env == "react"

        if auto_run:
            print(
                "Service mode detected with parameters - running one-shot assessment."
            )
            # Fall through to normal execution path below
        else:
            print("Starting Cyber-AutoAgent in service mode...")
            print("Container will stay alive and wait for external requests.")
            print("Use the React UI to submit assessment requests.")

            # Keep the container alive
            try:
                while True:
                    time.sleep(30)  # Check every 30 seconds
                    # Health check endpoint implementation pending
            except KeyboardInterrupt:
                print("Service mode interrupted. Shutting down...")
                return
            except Exception as e:
                print(f"Service mode error: {e}")
                return

    if not args.confirmations:
        os.environ["BYPASS_TOOL_CONSENT"] = "true"
    else:
        # Remove the variable if confirmations are enabled
        os.environ.pop("BYPASS_TOOL_CONSENT", None)

    os.environ["DEV"] = "true"

    # Provide a safer default for shell command timeouts unless user overrides
    if not os.environ.get("SHELL_DEFAULT_TIMEOUT"):
        # Many external tools (e.g., nmap, curl to slow hosts) can exceed low defaults
        # Use a safer default to reduce spurious timeouts while keeping responsiveness
        os.environ["SHELL_DEFAULT_TIMEOUT"] = "600"

    # Get centralized region configuration if not provided
    if args.region is None:
        config_manager = get_config_manager()
        args.region = config_manager.get_default_region()

    os.environ["AWS_REGION"] = args.region

    # Get configuration from ConfigManager with CLI overrides
    config_manager = get_config_manager()
    config_overrides = {}
    if args.output_dir:
        config_overrides["output_dir"] = args.output_dir
    # Always enable unified output system
    config_overrides["enable_unified_output"] = True
    if args.model:
        config_overrides["model_id"] = args.model

    # Toggle rubric evaluation via CLI flag
    if args.eval_rubric:
        os.environ["EVAL_RUBRIC_ENABLED"] = "true"

    # Ensure PROVIDER env reflects CLI for downstream modules (evaluator)
    os.environ["PROVIDER"] = args.provider

    server_config = config_manager.get_server_config(args.provider, **config_overrides)

    # Set mem0 environment variables based on configuration
    os.environ["MEM0_LLM_PROVIDER"] = server_config.memory.llm.provider.value
    os.environ["MEM0_LLM_MODEL"] = server_config.memory.llm.model_id
    os.environ["MEM0_EMBEDDING_MODEL"] = server_config.embedding.model_id

    # Log operation start
    operation_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_operation_id = f"OP_{operation_timestamp}"

    # Expose operation ID to tools via environment for consistent evidence tagging
    os.environ["CYBER_OPERATION_ID"] = local_operation_id

    # Initialize logger using unified output system
    log_path = get_output_path(
        sanitize_target_name(args.target),
        local_operation_id,
        "",
        server_config.output.base_dir,
    )
    log_file = os.path.join(log_path, "cyber_operations.log")

    # Enable verbose logging in React mode to capture debug information
    ui_mode = os.environ.get("CYBER_UI_MODE", "cli").lower()
    verbose_mode = bool(args.verbose or ui_mode == "react")
    logger = setup_logging(log_file=log_file, verbose=verbose_mode)

    # Setup telemetry (always enabled for token counting) and observability (deployment-aware)
    telemetry = setup_telemetry(logger)

    # Suppress benign OpenTelemetry context cleanup errors that occur during normal operation
    # These happen when async generators are terminated and don't affect functionality
    import logging as stdlib_logging

    otel_logger = stdlib_logging.getLogger("opentelemetry.context")
    otel_logger.setLevel(stdlib_logging.CRITICAL)

    # Register cleanup function to properly close log files
    def cleanup_logging():
        """Ensure log files are properly closed on exit"""
        try:
            # Write session end marker before closing (skip in React mode)
            if os.environ.get("CYBER_UI_MODE", "cli").lower() != "react":
                width = get_terminal_width()
                print("\n" + "=" * width)
                print(
                    f"CYBER-AUTOAGENT SESSION ENDED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                print("=" * width + "\n")
        except Exception:
            pass

        if hasattr(sys.stdout, "close") and callable(sys.stdout.close):
            try:
                sys.stdout.close()
            except Exception:
                pass
        if hasattr(sys.stderr, "close") and callable(sys.stderr.close):
            try:
                sys.stderr.close()
            except Exception:
                pass

    atexit.register(cleanup_logging)

    if os.environ.get("CYBERAGENT_NO_BANNER", "").lower() not in ("1", "true", "yes"):
        print_banner()

        # Safety warning (only show with banner)
        print_section(
            "⚠️  SAFETY WARNING",
            f"""
{Colors.RED}{Colors.BOLD}EXPERIMENTAL SOFTWARE - AUTHORIZED USE ONLY{Colors.RESET}

• This tool is for {Colors.BOLD}authorized security testing only{Colors.RESET}
• Use only in {Colors.BOLD}safe, sandboxed environments{Colors.RESET}
• Ensure you have {Colors.BOLD}explicit written permission{Colors.RESET} for target testing
• Users are {Colors.BOLD}fully responsible{Colors.RESET} for compliance with applicable laws
• Misuse may result in {Colors.BOLD}legal consequences{Colors.RESET}

{Colors.GREEN}✓{Colors.RESET} I understand and accept these terms before proceeding.
""",
            Colors.RED,
            "⚠️",
        )

    # Auto-setup and environment discovery
    # Pass memory_path to auto_setup to skip cleanup if using existing memory
    available_tools = auto_setup(skip_mem0_cleanup=bool(args.memory_path))

    logger.info("Operation %s initiated", local_operation_id)
    logger.info("Objective: %s", args.objective)
    logger.info("Target: %s", args.target)
    logger.info("Max steps: %d", args.iterations)
    logger.info("Provider: %s", args.provider)
    logger.info("Model: %s", server_config.llm.model_id)
    logger.info("Temperature: %s", server_config.llm.temperature)
    logger.info("Max tokens: %d", server_config.llm.max_tokens)
    if server_config.llm.top_p is not None:
        logger.info("Top P: %s", server_config.llm.top_p)

    # Log extended parameters from environment (model-agnostic)
    thinking_budget = os.getenv("THINKING_BUDGET")
    reasoning_effort = os.getenv("REASONING_EFFORT")
    max_completion = os.getenv("MAX_COMPLETION_TOKENS")

    if thinking_budget:
        logger.info("Thinking budget: %s", thinking_budget)
    if reasoning_effort:
        logger.info("Reasoning effort: %s", reasoning_effort)
    if max_completion:
        logger.info("Max completion tokens: %s", max_completion)

    # Display operation details with unified output information
    target_sanitized = sanitize_target_name(args.target)
    output_base_path = get_output_path(
        target_sanitized, operation_timestamp, "", server_config.output.base_dir
    )

    # Detect if running in Docker for path display
    is_docker = os.path.exists("/.dockerenv") or os.environ.get("CONTAINER") == "docker"

    # Prepare path display based on environment
    if is_docker:
        output_path_display = f"{output_base_path}\n{Colors.BOLD}Host Path:{Colors.RESET}     {output_base_path.replace('/app/outputs', './outputs')}"
    else:
        output_path_display = output_base_path

    if os.environ.get("CYBER_UI_MODE", "cli").lower() != "react":
        print_section(
            "MISSION PARAMETERS",
            f"""
{Colors.BOLD}Operation ID:{Colors.RESET} {Colors.CYAN}{local_operation_id}{Colors.RESET}
{Colors.BOLD}Objective:{Colors.RESET}    {Colors.YELLOW}{args.objective}{Colors.RESET}
{Colors.BOLD}Target:{Colors.RESET}       {Colors.RED}{args.target}{Colors.RESET} (sanitized: {target_sanitized})
{Colors.BOLD}Max Iterations:{Colors.RESET} {args.iterations} steps
{Colors.BOLD}Environment:{Colors.RESET} {len(available_tools)} existing cyber tools available
{Colors.BOLD}Output Path:{Colors.RESET}  {output_path_display}
""",
            Colors.CYAN,
            "🎯",
        )

    # Initialize timing
    start_time = time.time()
    callback_handler = None

    try:
        # Create agent
        logger.warning("Creating agent with iterations=%d", args.iterations)
        config = AgentConfig(
            target=args.target,
            objective=args.objective,
            max_steps=args.iterations,
            available_tools=available_tools,
            op_id=local_operation_id,
            model_id=args.model,
            region_name=args.region,
            provider=args.provider,
            memory_path=args.memory_path,
            memory_mode=args.memory_mode,
            module=args.module,
        )
        agent, callback_handler, feedback_manager = create_agent(
            target=args.target,
            objective=args.objective,
            config=config,
        )
        print_status("Cyber-AutoAgent online and starting", "SUCCESS")

        # Initial user message to start the agent
        initial_prompt = (
            f"Begin security assessment of {args.target} for: {args.objective}"
        )

        # Backward-compat helper for tests expecting get_initial_prompt to exist
        def _initial_prompt_accessor():
            return initial_prompt

        # Expose at module level for tests patching cyberautoagent.get_initial_prompt
        globals()["get_initial_prompt"] = _initial_prompt_accessor

        print(f"\n{Colors.DIM}{'─' * 80}{Colors.RESET}\n")

        # Execute autonomous operation
        try:
            operation_start = time.time()
            current_message = initial_prompt

            # SDK-aligned execution loop with continuation support
            print_status(
                f"Agent processing: {initial_prompt[:100]}{'...' if len(initial_prompt) > 100 else ''}",
                "THINKING",
            )

            current_message = initial_prompt
            feedback_injected_this_turn = False

            # Continue until stop condition is met
            while not interrupted:
                try:
                    # Check for HITL feedback before executing agent
                    if feedback_manager:
                        feedback_message = (
                            feedback_manager.get_pending_feedback_message()
                        )
                        if feedback_message:
                            logger.info(
                                "[HITL] Feedback detected for operation %s - preparing injection",
                                local_operation_id,
                            )
                            logger.info(
                                "[HITL] Feedback message content (length=%d chars):\n%s",
                                len(feedback_message),
                                feedback_message[:500] + "..."
                                if len(feedback_message) > 500
                                else feedback_message,
                            )
                            current_message = feedback_message
                            feedback_manager.clear_pending_feedback()
                            feedback_injected_this_turn = True
                            logger.info(
                                "[HITL] Feedback injection prepared, will pass to agent on next call"
                            )

                    # Execute agent with current message
                    logger.debug(
                        "[HITL] Calling agent with message (feedback_injected=%s, message_length=%d)",
                        feedback_injected_this_turn,
                        len(current_message),
                    )
                    result = agent(current_message)
                    logger.debug(
                        "[HITL] Agent call completed (feedback_injected=%s)",
                        feedback_injected_this_turn,
                    )

                    # Pass the metrics from the result to the callback handler
                    if (
                        callback_handler
                        and hasattr(result, "metrics")
                        and result.metrics
                    ):
                        if hasattr(result.metrics, "accumulated_usage"):
                            if result.metrics.accumulated_usage:
                                # Create an object that matches what _process_metrics expects
                                # It expects event_loop_metrics.accumulated_usage to be accessible
                                class MetricsObject:
                                    def __init__(self, accumulated_usage):
                                        self.accumulated_usage = accumulated_usage

                                metrics_obj = MetricsObject(
                                    result.metrics.accumulated_usage
                                )
                                callback_handler._process_metrics(metrics_obj)

                    # Check if we should continue
                    if callback_handler and callback_handler.should_stop():
                        if callback_handler.stop_tool_used:
                            print_status("Stop tool used - terminating", "SUCCESS")
                            # Generate report immediately when stop tool is used
                            logger.info(
                                "Stop tool detected - generating report before termination"
                            )
                            callback_handler.ensure_report_generated(
                                agent, args.target, args.objective, args.module
                            )
                        elif callback_handler.has_reached_limit():
                            print_status("Step limit reached - terminating", "SUCCESS")
                        break

                    # If agent hasn't done anything substantial for a while, break to avoid infinite loop
                    # Allow at least one assistant turn to emit reasoning before concluding no action
                    if callback_handler.current_step == 0:
                        # If we've seen any reasoning emitted, give the agent one more cycle
                        # This prevents premature termination when the first turn is pure reasoning
                        if getattr(callback_handler, "_emitted_any_reasoning", False):
                            logger.debug(
                                "Initial reasoning observed with no tools yet; continuing one more cycle"
                            )
                        else:
                            print_status("No actions taken - completing", "SUCCESS")
                            break

                    # Generate continuation prompt (skip if feedback was just injected)
                    if feedback_injected_this_turn:
                        # Feedback was injected this turn, don't overwrite with continuation
                        logger.info(
                            "[HITL] Skipping continuation prompt - feedback was injected this turn"
                        )
                        feedback_injected_this_turn = False
                        logger.debug(
                            "[HITL] Feedback injection flag reset - next iteration will use continuation"
                        )
                    else:
                        remaining_steps = (
                            args.iterations - callback_handler.current_step
                            if callback_handler
                            else args.iterations
                        )
                        logger.warning(
                            "Remaining steps check: iterations=%d, current_step=%d, remaining=%d",
                            args.iterations,
                            callback_handler.current_step if callback_handler else 0,
                            remaining_steps,
                        )
                        if remaining_steps > 0:
                            # Simple continuation message
                            current_message = f"Continue the security assessment. You have {remaining_steps} steps remaining out of {args.iterations} total. Focus on achieving the objective efficiently."
                            logger.debug(
                                "[HITL] Generated continuation message for next iteration (length=%d)",
                                len(current_message),
                            )
                        else:
                            logger.info(
                                "[HITL] No remaining steps - breaking execution loop"
                            )
                            break

                except StepLimitReached:
                    # Handle step limit reached gracefully without context errors
                    print_status(
                        f"Step limit reached ({callback_handler.max_steps} steps)",
                        "SUCCESS",
                    )
                    logger.debug("Step limit reached - terminating gracefully")
                    break

                except StopIteration as error:
                    # Strands agent completed normally - continue if we have steps left
                    logger.debug("Agent iteration completed: %s", str(error))
                    if (
                        callback_handler
                        and callback_handler.current_step > callback_handler.max_steps
                    ):
                        print_status("Step limit reached", "SUCCESS")
                        break
                    # Continue to next iteration

                except MaxTokensReachedException:
                    # Emit explicit termination event for UI and generate final report
                    print_status(
                        "Token limit reached - generating final report", "WARNING"
                    )
                    try:
                        if callback_handler:
                            # Emit a single termination_reason event for clarity in the UI
                            termination_event = {
                                "type": "termination_reason",
                                "reason": "max_tokens",
                                "message": "Model token limit reached. Switching to final report.",
                                "current_step": getattr(
                                    callback_handler, "current_step", 0
                                ),
                                "max_steps": getattr(
                                    callback_handler, "max_steps", args.iterations
                                ),
                            }
                            # Use handler's emitter directly
                            callback_handler._emit_ui_event(termination_event)  # noqa: SLF001 (internal method okay for UI)
                            # Generate the report immediately
                            callback_handler.ensure_report_generated(
                                agent, args.target, args.objective, args.module
                            )
                    except Exception:
                        logger.debug("Failed to emit termination event for max_tokens")
                    break

                except (
                    RequestsReadTimeout,
                    RequestsConnectionError,
                    BotoReadTimeoutError,
                    BotoEndpointConnectionError,
                    BotoConnectTimeoutError,
                ):
                    # Network/provider timeout: emit termination_reason and pivot to report
                    print_status(
                        "Network/provider timeout - generating final report", "WARNING"
                    )
                    try:
                        if callback_handler:
                            termination_event = {
                                "type": "termination_reason",
                                "reason": "network_timeout",
                                "message": "Provider/network timeout detected. Switching to final report.",
                                "current_step": getattr(
                                    callback_handler, "current_step", 0
                                ),
                                "max_steps": getattr(
                                    callback_handler, "max_steps", args.iterations
                                ),
                            }
                            callback_handler._emit_ui_event(termination_event)  # noqa: SLF001
                            callback_handler.ensure_report_generated(
                                agent, args.target, args.objective, args.module
                            )
                    except Exception:
                        logger.debug(
                            "Failed to emit termination event for network timeout"
                        )
                    break

                except Exception as error:
                    # Handle other termination scenarios
                    error_str = str(error).lower()
                    if "maxtokensreached" in error_str or "max_tokens" in error_str:
                        # Fallback path if the specific exception type wasn't available
                        print_status(
                            "Token limit reached - generating final report", "WARNING"
                        )
                        try:
                            if callback_handler:
                                termination_event = {
                                    "type": "termination_reason",
                                    "reason": "max_tokens",
                                    "message": "Model token limit reached. Switching to final report.",
                                    "current_step": getattr(
                                        callback_handler, "current_step", 0
                                    ),
                                    "max_steps": getattr(
                                        callback_handler, "max_steps", args.iterations
                                    ),
                                }
                                callback_handler._emit_ui_event(termination_event)  # noqa: SLF001
                                callback_handler.ensure_report_generated(
                                    agent, args.target, args.objective, args.module
                                )
                        except Exception:
                            logger.debug(
                                "Failed to emit termination event for max_tokens (fallback)"
                            )
                        break

                    if "event loop cycle stop requested" in error_str:
                        # Extract the reason from the error message
                        reason_match = re.search(r"Reason: (.+?)(?:\\n|$)", str(error))
                        reason = (
                            reason_match.group(1)
                            if reason_match
                            else "Objective achieved"
                        )
                        print_status(f"Agent terminated: {reason}", "SUCCESS")
                    elif "step limit" in error_str:
                        print_status("Step limit reached", "SUCCESS")
                    elif (
                        "read timed out" in error_str or "readtimeouterror" in error_str
                    ):
                        # Handle AWS Bedrock timeouts - these are now less likely with our config
                        # but if they occur, we should save progress and report it
                        logger.warning(
                            "AWS Bedrock timeout detected - operation interrupted but progress saved"
                        )
                        print_status("Network timeout - progress saved", "WARNING")
                        # Don't break - let finally block handle report generation
                    else:
                        print_status(f"Agent error: {str(error)}", "ERROR")
                        logger.exception("Unexpected agent error occurred")
                    break

            execution_time = time.time() - operation_start
            logger.info("Operation completed in %.2f seconds", execution_time)

        except Exception as e:
            logger.error("Operation error: %s", str(e))
            raise

        # Display operation results (suppressed in React mode where handler emits UI events)
        if os.environ.get("CYBER_UI_MODE", "cli").lower() != "react":
            print(f"\n{'=' * 80}")
            print(f"{Colors.BOLD}OPERATION SUMMARY{Colors.RESET}")
            print(f"{'=' * 80}")

        # Generate operation summary
        if callback_handler:
            summary = callback_handler.get_summary()
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)

            # Display summary in terminal mode only
            if os.environ.get("CYBER_UI_MODE", "cli").lower() != "react":
                print(
                    f"{Colors.BOLD}Operation ID:{Colors.RESET}      {local_operation_id}"
                )

                # Determine status based on completion
                if callback_handler.stop_tool_used:
                    status_text = f"{Colors.GREEN}Objective Achieved{Colors.RESET}"
                elif callback_handler.has_reached_limit():
                    status_text = f"{Colors.YELLOW}Step Limit Reached{Colors.RESET}"
                else:
                    status_text = f"{Colors.GREEN}Operation Completed{Colors.RESET}"

                print(f"{Colors.BOLD}Status:{Colors.RESET}            {status_text}")
                print(
                    f"{Colors.BOLD}Duration:{Colors.RESET}          {minutes}m {seconds}s"
                )

                print(f"\n{Colors.BOLD}Execution Metrics:{Colors.RESET}")
                print(f"  • Total Steps: {summary['total_steps']}/{args.iterations}")
                print(f"  • Tools Created: {summary['tools_created']}")
                print(f"  • Evidence Collected: {summary['evidence_collected']} items")
                print(f"  • Memory Operations: {summary['memory_operations']} total")

                if summary["capability_expansion"]:
                    print(f"\n{Colors.BOLD}Capabilities Created:{Colors.RESET}")
                    for tool in summary["capability_expansion"]:
                        print(f"  • {Colors.GREEN}{tool}{Colors.RESET}")

            # Display evidence summary in terminal mode
            if (
                callback_handler
                and os.environ.get("CYBER_UI_MODE", "cli").lower() != "react"
            ):
                evidence_summary = callback_handler.get_evidence_summary()
                if isinstance(evidence_summary, list) and evidence_summary:
                    print(f"\n{Colors.BOLD}Key Evidence:{Colors.RESET}")
                    if isinstance(evidence_summary[0], dict):
                        for ev in evidence_summary[:5]:
                            cat = ev.get("category", "unknown")
                            content = ev.get("content", "")[:60]
                            print(f"  • [{cat}] {content}...")
                        if len(evidence_summary) > 5:
                            print(f"  • ... and {len(evidence_summary) - 5} more items")

            # Show where evidence and memories are stored
            # Determine memory location based on backend and unified output structure
            target_name = sanitize_target_name(args.target)
            if os.getenv("MEM0_API_KEY"):
                memory_location = "Mem0 Platform (cloud)"
            elif os.getenv("OPENSEARCH_HOST"):
                memory_location = f"OpenSearch: {os.getenv('OPENSEARCH_HOST')}"
            else:
                memory_location = f"./outputs/{target_name}/memory"

            # Use unified output paths for evidence storage
            evidence_location = get_output_path(
                sanitize_target_name(args.target),
                local_operation_id,
                "",  # No subdirectory - show the operation root
                server_config.output.base_dir,
            )

            # Display output paths in terminal mode
            if os.environ.get("CYBER_UI_MODE", "cli").lower() != "react":
                is_docker = (
                    os.path.exists("/.dockerenv")
                    or os.environ.get("CONTAINER") == "docker"
                )

                if is_docker:
                    # Docker environment: show both container and host paths
                    host_evidence_location = evidence_location.replace(
                        "/app/outputs", "./outputs"
                    )
                    host_memory_location = memory_location.replace(
                        "./outputs", "./outputs"
                    )
                    print(
                        f"\n{Colors.BOLD}Outputs stored in:{Colors.RESET}"
                        f"\n  {Colors.DIM}Container:{Colors.RESET} {evidence_location}"
                        f"\n  {Colors.GREEN}Host:{Colors.RESET} {host_evidence_location}"
                    )
                    print(
                        f"{Colors.BOLD}Memory stored in:{Colors.RESET}"
                        f"\n  {Colors.DIM}Container:{Colors.RESET} {memory_location}"
                        f"\n  {Colors.GREEN}Host:{Colors.RESET} {host_memory_location}"
                    )
                else:
                    # Local environment: show direct paths
                    print(
                        f"\n{Colors.BOLD}Outputs stored in:{Colors.RESET} {evidence_location}"
                    )
                    print(
                        f"{Colors.BOLD}Memory stored in:{Colors.RESET} {memory_location}"
                    )
                print(f"{'=' * 80}")

    except KeyboardInterrupt:
        ui_mode = os.environ.get("CYBER_UI_MODE", "cli").lower()
        if ui_mode == "react":
            # Emit a structured termination event so the UI shows a clear end-of-operation
            try:
                if callback_handler:
                    # Idempotent termination helper emits thinking_end, a final TERMINATED header, and the reason
                    callback_handler._emit_termination(
                        "user_abort", "Operation cancelled by user"
                    )  # noqa: SLF001
            except Exception:
                pass
            # Exit gracefully to allow event flushing and frontend to handle "stopped" state
            # Use 130 (SIGINT) to indicate an intentional interrupt
            sys.exit(130)
        else:
            print_status("\nOperation cancelled by user", "WARNING")
            # Skip cleanup on interrupt for faster exit
            os._exit(1)

    except Exception as e:
        print_status(f"\nOperation failed: {str(e)}", "ERROR")
        logger.exception("Operation failed")
        sys.exit(1)

    finally:
        # Ensure log files are properly closed before exit
        def close_log_outputs():
            if hasattr(sys.stdout, "close") and hasattr(sys.stdout, "log"):
                try:
                    sys.stdout.close()
                except Exception:
                    pass
            if hasattr(sys.stderr, "close") and hasattr(sys.stderr, "log"):
                try:
                    sys.stderr.close()
                except Exception:
                    pass

        # Skip cleanup if interrupted
        if interrupted:
            ui_mode = os.environ.get("CYBER_UI_MODE", "cli").lower()
            if ui_mode == "react":
                # In React UI mode, we've already emitted a structured termination event above.
                # Just close log outputs and return without forcing an abrupt process exit so the
                # event can reach the frontend cleanly.
                close_log_outputs()
                return
            else:
                print_status("Exiting immediately due to interrupt", "WARNING")
                close_log_outputs()
                os._exit(1)

        # Ensure final report is generated - single trigger point
        if callback_handler:
            try:
                callback_handler.ensure_report_generated(
                    agent, args.target, args.objective, args.module
                )

                # Trigger evaluation after report generation
                logger.info("Triggering evaluation on completion")
                callback_handler.trigger_evaluation_on_completion()

                # Wait for evaluation to complete if running (uses same defaults as observability)
                default_evaluation = os.getenv("ENABLE_OBSERVABILITY", "false")
                if (
                    os.getenv("ENABLE_AUTO_EVALUATION", default_evaluation).lower()
                    == "true"
                ):
                    callback_handler.wait_for_evaluation_completion(timeout=300)

            except Exception as error:
                logger.warning("Error in final report/evaluation: %s", error)
        else:
            logger.warning("No callback_handler available for evaluation trigger")

        # Clean up resources
        should_cleanup = not args.keep_memory and not args.memory_path

        if should_cleanup:
            try:
                # Extract target name for unified output structure cleanup
                target_name = sanitize_target_name(args.target)
                logger.debug(
                    "Calling clean_operation_memory with target_name=%s", target_name
                )
                clean_operation_memory(local_operation_id, target_name)
                logger.info("Memory cleaned up for operation %s", local_operation_id)
            except Exception as cleanup_error:
                logger.warning("Error cleaning up memory: %s", cleanup_error)
        else:
            logger.debug("Skipping cleanup - memory will be preserved")

        # Log operation end
        end_time = time.time()
        total_time = end_time - start_time
        logger.info("Operation %s ended after %.2fs", local_operation_id, total_time)

        # Flush OpenTelemetry traces before exit
        try:
            # Use the telemetry instance if available, otherwise use global tracer provider
            if telemetry and hasattr(telemetry, "tracer_provider"):
                tracer_provider = telemetry.tracer_provider
            else:
                tracer_provider = trace.get_tracer_provider()

            if hasattr(tracer_provider, "force_flush"):
                logger.debug("Flushing OpenTelemetry traces...")
                # Force flush with timeout to ensure traces are sent
                # This is critical for capturing all tool calls and swarm operations
                tracer_provider.force_flush(timeout_millis=10000)  # 10 second timeout
                # Short delay to ensure network transmission completes
                time.sleep(2)
                logger.debug("Traces flushed successfully")
        except Exception as e:
            logger.warning("Error flushing traces: %s", e)

        # Final cleanup of log outputs before exit
        close_log_outputs()


if __name__ == "__main__":
    main()
