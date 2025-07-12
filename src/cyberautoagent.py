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
import argparse
import time
import atexit
import re
import base64
from datetime import datetime
from opentelemetry import trace

from modules.agent import create_agent
from modules.system_prompts import get_initial_prompt, get_continuation_prompt

from modules.utils import (
    Colors,
    print_banner,
    print_section,
    print_status,
    analyze_objective_completion,
    get_data_path,
)
from modules.environment import auto_setup, setup_logging, clean_operation_memory

warnings.filterwarnings("ignore", category=DeprecationWarning)


def setup_observability(logger):
    """
    Setup Langfuse observability by configuring OpenTelemetry environment variables
    and initializing the OTLP exporter.
    """
    # Check if observability is enabled via environment (default: true)
    if os.getenv("ENABLE_OBSERVABILITY", "true").lower() != "true":
        logger.debug("Observability is disabled (set ENABLE_OBSERVABILITY=false)")
        return False
    
    # Get configuration from environment with defaults for self-hosted Langfuse
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "cyber-public")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "cyber-secret")
    
    # Create auth token for Langfuse
    auth_token = base64.b64encode(
        f"{public_key}:{secret_key}".encode()
    ).decode()
    
    # Set OpenTelemetry environment variables that Strands SDK will use
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{host}/api/public/otel/v1/traces"
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth_token}"
    
    # Initialize Strands tracer with OTLP exporter
    from strands.telemetry import get_tracer
    
    logger.debug("Initializing Strands tracer with OTLP exporter")
    # The tracer will automatically use OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS
    # environment variables that we set above
    tracer = get_tracer(
        service_name="cyber-autoagent",
        otlp_endpoint=f"{host}/api/public/otel/v1/traces",
        otlp_headers={"Authorization": f"Basic {auth_token}"}
    )
    
    logger.info("Langfuse observability enabled at %s", host)
    logger.info("OTLP endpoint: %s", os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"])
    logger.info("View traces at %s (login: admin@cyber-autoagent.com/changeme)", host)
    
    return True


def main():
    """Main execution function"""

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
        help="Model ID to use (default: remote=claude-sonnet, local=llama3.2:3b)",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        help="AWS region for Bedrock (default: us-east-1)",
    )
    parser.add_argument(
        "--server",
        type=str,
        choices=["remote", "local"],
        default="remote",
        help="Model provider: 'remote' for AWS Bedrock, 'local' for Ollama (default: remote)",
    )
    parser.add_argument(
        "--confirmations",
        action="store_true",
        help="Enable tool confirmation prompts (default: disabled)",
    )
    parser.add_argument(
        "--memory-path",
        type=str,
        help="Path to existing FAISS memory store to load past memories (e.g., /tmp/mem0_OP_20240320_101530)",
    )
    parser.add_argument(
        "--keep-memory",
        action="store_true",
        help="Keep memory data after operation completes (default: remove)",
    )

    args = parser.parse_args()

    if not args.confirmations:
        os.environ["BYPASS_TOOL_CONSENT"] = "true"
    else:
        # Remove the variable if confirmations are enabled
        os.environ.pop("BYPASS_TOOL_CONSENT", None)

    os.environ["DEV"] = "true"
    
    os.environ["AWS_REGION"] = args.region
    
    if args.server == "local":
        os.environ["MEM0_LLM_PROVIDER"] = "ollama"
        os.environ["MEM0_LLM_MODEL"] = "llama3.2:3b"  # mem0 always uses the smaller model
        os.environ["MEM0_EMBEDDING_MODEL"] = "mxbai-embed-large"
    else:
        os.environ["MEM0_LLM_PROVIDER"] = "aws_bedrock"
        os.environ["MEM0_LLM_MODEL"] = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"  # mem0 uses Claude 3.5 Sonnet
        os.environ["MEM0_EMBEDDING_MODEL"] = "amazon.titan-embed-text-v2:0"

    # Initialize logger with volume path
    logger = setup_logging(
        log_file=os.path.join(get_data_path("logs"), "cyber_operations.log"),
        verbose=args.verbose,
    )
    
    # Setup observability (enabled by default via ENABLE_OBSERVABILITY env var)
    setup_observability(logger)
    
    # Register cleanup function to properly close log files
    def cleanup_logging():
        """Ensure log files are properly closed on exit"""
        try:
            # Write session end marker before closing
            print("\n" + "="*80)
            print(f"CYBER-AUTOAGENT SESSION ENDED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80 + "\n")
        except Exception:
            pass
        
        if hasattr(sys.stdout, 'close') and callable(sys.stdout.close):
            try:
                sys.stdout.close()
            except Exception:
                pass
        if hasattr(sys.stderr, 'close') and callable(sys.stderr.close):
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

    # Log operation start
    local_operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info("Operation %s initiated", local_operation_id)
    logger.info("Objective: %s", args.objective)
    logger.info("Target: %s", args.target)
    logger.info("Max steps: %d", args.iterations)

    # Display operation details
    print_section(
        "MISSION PARAMETERS",
        f"""
{Colors.BOLD}Operation ID:{Colors.RESET} {Colors.CYAN}{local_operation_id}{Colors.RESET}
{Colors.BOLD}Objective:{Colors.RESET}    {Colors.YELLOW}{args.objective}{Colors.RESET}
{Colors.BOLD}Target:{Colors.RESET}       {Colors.RED}{args.target}{Colors.RESET}
{Colors.BOLD}Max Iterations:{Colors.RESET} {args.iterations} steps
{Colors.BOLD}Environment:{Colors.RESET} {len(available_tools)} existing cyber tools available
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
            server=args.server,
            memory_path=args.memory_path,
        )
        print_status("Cyber-AutoAgent online and starting", "SUCCESS")

        # Initial strategic prompt
        initial_prompt = get_initial_prompt(
            args.target, args.objective, args.iterations, available_tools
        )

        print("\n%s%s%s\n" % (Colors.DIM, "─" * 80, Colors.RESET))

        # Execute autonomous operation
        try:
            operation_start = time.time()
            messages = []
            current_message = initial_prompt

            # Main autonomous execution loop
            while True:
                try:
                    # For newer strands versions, pass the prompt directly without messages on first call
                    if not messages:
                        # First call - don't pass messages parameter
                        result = agent(current_message)
                    else:
                        # Subsequent calls - pass messages
                        result = agent(current_message, messages=messages)

                    # Update conversation history
                    # Structure content properly for Strands integration
                    messages.append({
                        "role": "user", 
                        "content": [{"text": current_message}]
                    })
                    
                    # For thinking-enabled models, preserve the original response structure
                    # For non-thinking models, wrap in text block
                    if hasattr(result, 'content') and isinstance(result.content, list):
                        # Result already has proper structure (thinking + text blocks)
                        messages.append({
                            "role": "assistant", 
                            "content": result.content
                        })
                    else:
                        # Fallback for simple text responses
                        messages.append({
                            "role": "assistant", 
                            "content": [{"text": str(result)}]
                        })

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
                            reason_match = re.search(r'Reason: (.+?)(?:\n|$)', str(error))
                            reason = reason_match.group(1) if reason_match else "Objective achieved"
                            print_status(f"Agent terminated: {reason}", "SUCCESS")
                        
                        if callback_handler:
                            callback_handler.generate_final_report(
                                agent, args.target, args.objective
                            )
                    else:
                        print_status("Agent error: %s" % str(error), "ERROR")
                        logger.exception("Unexpected agent error occurred")
                        if callback_handler:
                            callback_handler.generate_final_report(
                                agent, args.target, args.objective
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
                            "Memory operations: %d" % summary["memory_operations"],
                            "INFO",
                        )
                        print_status(
                            "Capabilities created: %d" % summary["tools_created"],
                            "INFO",
                        )
                        print_status(
                            "Evidence collected: %d items"
                            % summary["evidence_collected"],
                            "INFO",
                        )
                        callback_handler.generate_final_report(
                            agent, args.target, args.objective
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
        print("\n%s" % ("=" * 80))
        print("%sOPERATION SUMMARY%s" % (Colors.BOLD, Colors.RESET))
        print("%s" % ("=" * 80))

        # Operation summary
        if callback_handler:
            summary = callback_handler.get_summary()
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)

            print(
                "%sOperation ID:%s      %s"
                % (Colors.BOLD, Colors.RESET, local_operation_id)
            )

            # Determine status based on completion
            if analyze_objective_completion(messages):
                status_text = "%sObjective Achieved%s" % (Colors.GREEN, Colors.RESET)
            elif callback_handler.has_reached_limit():
                status_text = "%sStep Limit Reached - Final Report Generated%s" % (
                    Colors.YELLOW,
                    Colors.RESET,
                )
            else:
                status_text = "%sOperation Completed%s" % (Colors.BLUE, Colors.RESET)

            print(
                "%sStatus:%s            %s" % (Colors.BOLD, Colors.RESET, status_text)
            )
            print(
                "%sDuration:%s          %dm %ds"
                % (Colors.BOLD, Colors.RESET, minutes, seconds)
            )

            print("\n%sExecution Metrics:%s" % (Colors.BOLD, Colors.RESET))
            print("  • Total Steps: %d/%d" % (summary["total_steps"], args.iterations))
            print("  • Tools Created: %d" % summary["tools_created"])
            print("  • Evidence Collected: %d items" % summary["evidence_collected"])
            print("  • Memory Operations: %d total" % summary["memory_operations"])

            if summary["capability_expansion"]:
                print("\n%sCapabilities Created:%s" % (Colors.BOLD, Colors.RESET))
                for tool in summary["capability_expansion"]:
                    print("  • %s%s%s" % (Colors.GREEN, tool, Colors.RESET))

            # Show evidence summary if available
            if callback_handler:
                evidence_summary = callback_handler.get_evidence_summary()
                if isinstance(evidence_summary, list) and evidence_summary:
                    print("\n%sKey Evidence:%s" % (Colors.BOLD, Colors.RESET))
                    if isinstance(evidence_summary[0], dict):
                        for ev in evidence_summary[:5]:
                            cat = ev.get("category", "unknown")
                            content = ev.get("content", "")[:60]
                            print("  • [%s] %s..." % (cat, content))
                        if len(evidence_summary) > 5:
                            print(
                                "  • ... and %d more items"
                                % (len(evidence_summary) - 5)
                            )

            # Show where evidence and memories are stored
            memory_location = os.environ.get("MEM0_FAISS_PATH", "Not configured")
            print(
                "\n%sEvidence stored in:%s /app/evidence/evidence_%s"
                % (Colors.BOLD, Colors.RESET, local_operation_id)
            )
            print(
                "%sMemory stored in:%s %s"
                % (Colors.BOLD, Colors.RESET, memory_location)
            )
            print("%s" % ("=" * 80))

    except KeyboardInterrupt:
        print_status("\nOperation cancelled by user", "WARNING")
        sys.exit(1)

    except Exception as e:
        print_status(f"\nOperation failed: {str(e)}", "ERROR")
        logger.exception("Operation failed")
        sys.exit(1)

    finally:
        # Ensure final report is generated if callback_handler exists and report not yet generated
        if callback_handler and not getattr(
            callback_handler, "report_generated", False
        ):
            try:
                callback_handler.generate_final_report(
                    agent, args.target, args.objective
                )
            except Exception as report_error:
                logger.warning("Error generating final report: %s", report_error)

        # Clean up resources
        if not args.keep_memory and not args.memory_path:
            try:
                clean_operation_memory(local_operation_id)
            except Exception as cleanup_error:
                logger.warning("Error cleaning up memory: %s", cleanup_error)

        # Log operation end
        end_time = time.time()
        total_time = end_time - start_time
        logger.info("Operation %s ended after %.2fs", local_operation_id, total_time)
        
        # Flush OpenTelemetry traces before exit
        try:
            from opentelemetry import trace
            tracer_provider = trace.get_tracer_provider()
            if hasattr(tracer_provider, 'force_flush'):
                logger.debug("Flushing OpenTelemetry traces...")
                tracer_provider.force_flush()
                # Give a moment for traces to be sent
                time.sleep(2)
        except Exception as e:
            logger.warning("Error flushing traces: %s", e)


if __name__ == "__main__":
    main()
