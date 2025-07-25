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

import warnings
import os
import sys
import signal
import argparse
import time
import atexit
import re
import base64
import threading
from datetime import datetime
import requests
from opentelemetry import trace
from strands.telemetry.config import StrandsTelemetry
# Local imports
from modules.agents.cyber_autoagent import create_agent
from modules.prompts.system import get_initial_prompt, get_continuation_prompt
from modules.config.manager import get_config_manager
from modules.handlers.utils import (
    Colors,
    print_banner,
    print_section,
    print_status,
    analyze_objective_completion,
    get_output_path,
    sanitize_target_name,
)
from modules.config.environment import auto_setup, setup_logging, clean_operation_memory

warnings.filterwarnings("ignore", category=DeprecationWarning)


def setup_observability(logger):
    """
    Setup Langfuse observability by configuring OpenTelemetry environment variables
    and initializing the OTLP exporter.
    """
    # Check if observability is enabled via environment (default: true)
    if os.getenv("ENABLE_OBSERVABILITY", "true").lower() != "true":
        logger.debug("Observability is disabled (set ENABLE_OBSERVABILITY=false)")
        return None

    # Get configuration from environment with defaults for self-hosted Langfuse
    # Helper function to detect if running in Docker
    def is_docker():
        """Check if running inside a Docker container."""
        return os.path.exists("/.dockerenv") or os.path.exists("/app")
    
    # Use langfuse-web:3000 when in Docker, localhost:3000 otherwise
    default_host = "http://langfuse-web:3000" if is_docker() else "http://localhost:3000"
    host = os.getenv("LANGFUSE_HOST", default_host)
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "cyber-public")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "cyber-secret")

    # Create auth token for Langfuse
    auth_token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

    # Set OpenTelemetry environment variables that Strands SDK will use
    # IMPORTANT: OTEL_EXPORTER_OTLP_ENDPOINT should be the base URL, not the traces endpoint
    # The SDK will append /v1/traces automatically
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{host}/api/public/otel"
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth_token}"
    
    # Initialize Strands telemetry system with OTLP export
    telemetry = StrandsTelemetry()
    telemetry.setup_otlp_exporter()
    
    logger.debug("OTEL environment configured for Strands SDK")
    logger.debug("Strands telemetry initialized with OTLP exporter")
    
    logger.info("Langfuse observability enabled at %s", host)
    logger.info("OTLP endpoint: %s", os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"])
    logger.info("View traces at %s (login: admin@cyber-autoagent.com/changeme)", host)
    
    return telemetry


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
    else:
        signal_name = f"Signal {signum}"
    
    print(f"\n\033[93m[!] {signal_name} received. Stopping agent gracefully...\033[0m")
    
    # For swarm operations, we need to be more forceful
    # Check if we're in a swarm operation by looking at the call stack
    import traceback
    stack = traceback.extract_stack()
    in_swarm = any('swarm' in str(frame_info.filename).lower() or 
                   'swarm' in str(frame_info.name).lower() 
                   for frame_info in stack)
    
    if in_swarm:
        print("\033[91m[!] Swarm operation detected - forcing immediate termination\033[0m")
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
    
    # Set up signal handlers for both Ctrl+C and Ctrl+Z
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTSTP, signal_handler)

    # Parse command line arguments first to get the confirmations flag
    parser = argparse.ArgumentParser(
        description="Cyber-AutoAgent - Autonomous Cybersecurity Assessment Tool",
        epilog="⚠️  Use only on authorized targets in safe environments ⚠️",
    )
    parser.add_argument(
        "--objective", type=str, required=True, help="Security assessment objective"
    )
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        help="Target system/network to assess (ensure you have permission!)",
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
        default="bedrock",
        help="Model provider: 'bedrock' for AWS Bedrock, 'ollama' for local models, 'litellm' for universal access (default: bedrock)",
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

    args = parser.parse_args()

    if not args.confirmations:
        os.environ["BYPASS_TOOL_CONSENT"] = "true"
    else:
        # Remove the variable if confirmations are enabled
        os.environ.pop("BYPASS_TOOL_CONSENT", None)

    os.environ["DEV"] = "true"

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

    server_config = config_manager.get_server_config(args.provider, **config_overrides)

    # Set mem0 environment variables based on configuration
    os.environ["MEM0_LLM_PROVIDER"] = server_config.memory.llm.provider.value
    os.environ["MEM0_LLM_MODEL"] = server_config.memory.llm.model_id
    os.environ["MEM0_EMBEDDING_MODEL"] = server_config.embedding.model_id

    # Log operation start
    operation_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_operation_id = f"OP_{operation_timestamp}"

    # Initialize logger using unified output system
    log_path = get_output_path(
        sanitize_target_name(args.target),
        local_operation_id,
        "",
        server_config.output.base_dir,
    )
    log_file = os.path.join(log_path, "cyber_operations.log")

    logger = setup_logging(log_file=log_file, verbose=args.verbose)

    # Setup observability (enabled by default via ENABLE_OBSERVABILITY env var)
    telemetry = setup_observability(logger)

    # Register cleanup function to properly close log files
    def cleanup_logging():
        """Ensure log files are properly closed on exit"""
        try:
            # Write session end marker before closing
            from modules.handlers.utils import get_terminal_width
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

    # Display banner
    print_banner()

    # Safety warning
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
        agent, callback_handler = create_agent(
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
        )
        print_status("Cyber-AutoAgent online and starting", "SUCCESS")

        # Initial strategic prompt
        initial_prompt = get_initial_prompt(
            args.target, args.objective, args.iterations, available_tools
        )

        print(f"\n{Colors.DIM}{'─' * 80}{Colors.RESET}\n")

        # Execute autonomous operation
        try:
            operation_start = time.time()
            messages = []
            current_message = initial_prompt

            # Main autonomous execution loop
            while not interrupted:
                try:
                    # Execute agent with current message
                    # The agent handles its own tracing internally via Strands SDK
                    if not messages:
                        # First call - don't pass messages parameter
                        result = agent(current_message)
                    else:
                        # Subsequent calls - pass messages for conversation context
                        result = agent(current_message, messages=messages)

                    # Update conversation history
                    # Structure content properly for Strands integration
                    messages.append(
                        {"role": "user", "content": [{"text": current_message}]}
                    )

                    # For thinking-enabled models, preserve the original response structure
                    # For non-thinking models, wrap in text block
                    if hasattr(result, "content") and isinstance(result.content, list):
                        # Result already has proper structure (thinking + text blocks)
                        messages.append(
                            {"role": "assistant", "content": result.content}
                        )
                    else:
                        # Fallback for simple text responses
                        messages.append(
                            {"role": "assistant", "content": [{"text": str(result)}]}
                        )

                except (StopIteration, Exception) as error:
                    # Handle termination scenarios
                    error_str = str(error).lower()
                    if (
                        "step limit" in error_str
                        or "clean termination" in error_str
                        or "event loop cycle stop requested" in error_str
                    ):
                        # Check if this was from the stop tool
                        if "event loop cycle stop requested" in error_str:
                            # Extract the reason from the error message
                            reason_match = re.search(
                                r"Reason: (.+?)(?:\n|$)", str(error)
                            )
                            reason = (
                                reason_match.group(1)
                                if reason_match
                                else "Objective achieved"
                            )
                            print_status(f"Agent terminated: {reason}", "SUCCESS")

                        if callback_handler:
                            callback_handler.generate_final_report(
                                agent, args.target, args.objective
                            )
                            # Trigger evaluation after clean termination
                            try:
                                logger.info(
                                    "Triggering evaluation after clean termination"
                                )
                                callback_handler.trigger_evaluation_on_completion()
                            except Exception as eval_error:
                                logger.warning(
                                    "Error triggering evaluation: %s", eval_error
                                )
                    else:
                        print_status(f"Agent error: {str(error)}", "ERROR")
                        logger.exception("Unexpected agent error occurred")
                        if callback_handler:
                            callback_handler.generate_final_report(
                                agent, args.target, args.objective
                            )
                            # Trigger evaluation after error
                            try:
                                logger.info("Triggering evaluation after error")
                                callback_handler.trigger_evaluation_on_completion()
                            except Exception as eval_error:
                                logger.warning(
                                    "Error triggering evaluation: %s", eval_error
                                )
                    break

                # Check if agent has determined objective completion
                is_complete, completion_summary, metadata = (
                    analyze_objective_completion(messages)
                )

                if is_complete:
                    print_status(f"Objective achieved: {completion_summary}", "SUCCESS")
                    if metadata.get("confidence"):
                        print_status(
                            f"Agent confidence: {metadata['confidence']}%", "INFO"
                        )

                    if callback_handler:
                        summary = callback_handler.get_summary()
                        print_status(
                            f"Memory operations: {summary['memory_operations']}",
                            "INFO",
                        )
                        print_status(
                            f"Capabilities created: {summary['tools_created']}",
                            "INFO",
                        )
                        print_status(
                            f"Evidence collected: {summary['evidence_collected']} items",
                            "INFO",
                        )
                        callback_handler.generate_final_report(
                            agent, args.target, args.objective
                        )
                        # Trigger evaluation after successful completion
                        try:
                            logger.info(
                                "Triggering evaluation after successful completion"
                            )
                            callback_handler.trigger_evaluation_on_completion()
                        except Exception as eval_error:
                            logger.warning(
                                "Error triggering evaluation: %s", eval_error
                            )
                    break

                # Check if step limit reached or stop tool was used
                if callback_handler and callback_handler.should_stop():
                    if callback_handler.stop_tool_used:
                        print_status("Stop tool used - terminating", "SUCCESS")
                    elif callback_handler.has_reached_limit():
                        print_status("Step limit reached - terminating", "SUCCESS")
                    callback_handler.generate_final_report(
                        agent, args.target, args.objective
                    )
                    # Trigger evaluation after completion
                    try:
                        logger.info(
                            "Triggering evaluation after step limit/stop completion"
                        )
                        callback_handler.trigger_evaluation_on_completion()
                    except Exception as eval_error:
                        logger.warning("Error triggering evaluation: %s", eval_error)
                    break

                # Generate continuation prompt for next iteration
                remaining_steps = (
                    args.iterations - callback_handler.steps
                    if callback_handler
                    else args.iterations
                )
                current_message = get_continuation_prompt(
                    remaining_steps, args.iterations
                )

                time.sleep(0.3)  # Shorter delay for better responsiveness

            execution_time = time.time() - operation_start
            logger.info("Operation completed in %.2f seconds", execution_time)

        except Exception as e:
            logger.error("Operation error: %s", str(e))
            raise

        # Display comprehensive results
        print(f"\n{'=' * 80}")
        print(f"{Colors.BOLD}OPERATION SUMMARY{Colors.RESET}")
        print(f"{'=' * 80}")

        # Operation summary
        if callback_handler:
            summary = callback_handler.get_summary()
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)

            print(f"{Colors.BOLD}Operation ID:{Colors.RESET}      {local_operation_id}")

            # Determine status based on completion
            if analyze_objective_completion(messages):
                status_text = f"{Colors.GREEN}Objective Achieved{Colors.RESET}"
            elif callback_handler.has_reached_limit():
                status_text = f"{Colors.YELLOW}Step Limit Reached - Final Report Generated{Colors.RESET}"
            else:
                status_text = f"{Colors.BLUE}Operation Completed{Colors.RESET}"

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

            # Show evidence summary if available
            if callback_handler:
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

            # Detect if running in Docker
            is_docker = os.path.exists("/.dockerenv") or os.environ.get("CONTAINER") == "docker"
            
            # Show appropriate paths based on environment
            if is_docker:
                # In Docker, show both container and host paths
                host_evidence_location = evidence_location.replace("/app/outputs", "./outputs")
                host_memory_location = memory_location.replace("./outputs", "./outputs")
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
                # Running locally, just show the paths
                print(
                    f"\n{Colors.BOLD}Outputs stored in:{Colors.RESET} {evidence_location}"
                )
                print(f"{Colors.BOLD}Memory stored in:{Colors.RESET} {memory_location}")
            print(f"{'=' * 80}")

    except KeyboardInterrupt:
        print_status("\nOperation cancelled by user", "WARNING")
        # Skip cleanup on interrupt for faster exit
        os._exit(1)

    except Exception as e:
        print_status(f"\nOperation failed: {str(e)}", "ERROR")
        logger.exception("Operation failed")
        sys.exit(1)

    finally:
        # Skip cleanup if interrupted
        if interrupted:
            print_status("Exiting immediately due to interrupt", "WARNING")
            os._exit(1)
            
        # Ensure final report is generated if callback_handler exists and report not yet generated
        if callback_handler and not getattr(
            callback_handler.state, "report_generated", False
        ):
            try:
                callback_handler.generate_final_report(
                    agent, args.target, args.objective
                )
            except Exception as report_error:
                logger.warning("Error generating final report: %s", report_error)

        # Trigger evaluation regardless of completion status (success or failure)
        if callback_handler:
            try:
                logger.info("Triggering evaluation on completion")
                callback_handler.trigger_evaluation_on_completion()

                # Wait for evaluation to complete if running
                if os.getenv("ENABLE_AUTO_EVALUATION", "false").lower() == "true":
                    callback_handler.wait_for_evaluation_completion(timeout=300)

            except Exception as eval_error:
                logger.warning("Error triggering evaluation: %s", eval_error)
        else:
            logger.warning("No callback_handler available for evaluation trigger")

        # Clean up resources
        should_cleanup = not args.keep_memory and not args.memory_path

        logger.debug(
            "Cleanup evaluation: keep_memory=%s, memory_path=%s, should_cleanup=%s",
            args.keep_memory,
            args.memory_path,
            should_cleanup,
        )

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
            if telemetry and hasattr(telemetry, 'tracer_provider'):
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


if __name__ == "__main__":
    main()
