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
from datetime import datetime

from modules.utils import Colors, print_banner, print_section, print_status, analyze_objective_completion
from modules.environment import auto_setup, setup_logging  
from modules.agent_factory import create_agent
from modules.system_prompts import get_initial_prompt, get_continuation_prompt

# Simple warning suppression
warnings.filterwarnings('ignore', category=DeprecationWarning)

def main():
    """Main execution function"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Cyber-AutoAgent - Autonomous Cybersecurity Assessment Tool",
        epilog="⚠️  Use only on authorized targets in safe environments ⚠️"
    )
    parser.add_argument(
        "--objective",
        type=str,
        required=True,
        help="Security assessment objective"
    )
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        help="Target system/network to assess (ensure you have permission!)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Maximum tool executions before stopping (default: 100)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output with detailed debug logging"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        help="Bedrock model ID to use (default: us.anthropic.claude-3-7-sonnet-20250219-v1:0)"
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        help="AWS region for Bedrock (default: us-east-1)"
    )
    
    args = parser.parse_args()
    
    # Initialize logger
    logger = setup_logging(verbose=args.verbose)
    
    # Display banner
    print_banner()
    
    # Safety warning
    print_section("⚠️  SAFETY WARNING", f"""
{Colors.RED}{Colors.BOLD}EXPERIMENTAL SOFTWARE - AUTHORIZED USE ONLY{Colors.RESET}

• This tool is for {Colors.BOLD}authorized security testing only{Colors.RESET}
• Use only in {Colors.BOLD}safe, sandboxed environments{Colors.RESET}  
• Ensure you have {Colors.BOLD}explicit written permission{Colors.RESET} for target testing
• Users are {Colors.BOLD}fully responsible{Colors.RESET} for compliance with applicable laws
• Misuse may result in {Colors.BOLD}legal consequences{Colors.RESET}

{Colors.GREEN}✓{Colors.RESET} I understand and accept these terms before proceeding.
""", Colors.RED, "⚠️")
    
    # Auto-setup and environment discovery
    available_tools = auto_setup()
    
    # Log operation start
    local_operation_id = f"OP-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    logger.info("Operation %s initiated", local_operation_id)
    logger.info("Objective: %s", args.objective)
    logger.info("Target: %s", args.target)
    logger.info("Max steps: %d", args.iterations)
    
    # Display operation details
    print_section("MISSION PARAMETERS", f"""
{Colors.BOLD}Operation ID:{Colors.RESET} {Colors.CYAN}{local_operation_id}{Colors.RESET}
{Colors.BOLD}Objective:{Colors.RESET}    {Colors.YELLOW}{args.objective}{Colors.RESET}
{Colors.BOLD}Target:{Colors.RESET}       {Colors.RED}{args.target}{Colors.RESET}
{Colors.BOLD}Max Iterations:{Colors.RESET} {args.iterations} steps
{Colors.BOLD}Environment:{Colors.RESET} {len(available_tools)} existing cyber tools available
""", Colors.CYAN, "🎯")
    
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
            model_id=args.model,
            region_name=args.region
        )
        print_status("Cyber-AutoAgent online and starting", "SUCCESS")
        
        # Set environment variables
        os.environ["DEV"] = "true"
        
        # Initial strategic prompt
        initial_prompt = get_initial_prompt(args.target, args.objective, args.iterations, available_tools)
        
        print("\n%s%s%s\n" % (Colors.DIM, '─'*80, Colors.RESET))
        
        # Execute autonomous operation
        try:
            operation_start = time.time()
            messages = []
            current_message = initial_prompt
            
            # Main autonomous execution loop
            while True:
                try:
                    # Execute agent step and get response
                    result = agent(current_message, messages=messages)
                    
                    # Update conversation history
                    if messages:
                        messages.append({"role": "user", "content": current_message})
                    messages.append({"role": "assistant", "content": str(result)})
                    
                except (StopIteration, Exception) as error:
                    # Handle termination scenarios
                    if "step limit" in str(error).lower() or "clean termination" in str(error).lower():
                        if callback_handler:
                            callback_handler.generate_final_report(agent, args.target, args.objective)
                    else:
                        print_status("Agent error: %s" % str(error), "ERROR")
                        logger.exception("Unexpected agent error occurred")
                        if callback_handler:
                            callback_handler.generate_final_report(agent, args.target, args.objective)
                    break
                
                # Check for successful objective completion
                if analyze_objective_completion(messages):
                    print_status("Objective achieved through autonomous execution!", "SUCCESS")
                    if callback_handler:
                        summary = callback_handler.get_summary()
                        print_status("Memory operations: %d" % summary['memory_operations'], "INFO")
                        print_status("Capabilities created: %d" % summary['tools_created'], "INFO")
                        print_status("Evidence collected: %d items" % summary['evidence_collected'], "INFO")
                        callback_handler.generate_final_report(agent, args.target, args.objective)
                    break
                
                # Generate continuation prompt for next iteration
                remaining_steps = args.iterations - callback_handler.steps if callback_handler else args.iterations
                current_message = get_continuation_prompt(remaining_steps, args.iterations)
                
                time.sleep(0.3)  # Shorter delay for better responsiveness
            
            execution_time = time.time() - operation_start
            logger.info("Operation completed in %.2f seconds", execution_time)
            
        except Exception as e:
            logger.error("Operation error: %s", str(e))
            raise
        
        # Display comprehensive results
        print("\n%s" % ('='*80))
        print("🧠 %sOPERATION SUMMARY%s" % (Colors.BOLD, Colors.RESET))
        print("%s" % ('='*80))
        
        # Operation summary
        if callback_handler:
            summary = callback_handler.get_summary()
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            
            print("%sOperation ID:%s      %s" % (Colors.BOLD, Colors.RESET, local_operation_id))
            
            # Determine status based on completion
            if analyze_objective_completion(messages):
                status_text = "%s✅ Objective Achieved%s" % (Colors.GREEN, Colors.RESET)
            elif callback_handler.has_reached_limit():
                status_text = "%s⚠️  Step Limit Reached - Final Report Generated%s" % (Colors.YELLOW, Colors.RESET)
            else:
                status_text = "%sℹ️  Operation Completed%s" % (Colors.BLUE, Colors.RESET)
            
            print("%sStatus:%s            %s" % (Colors.BOLD, Colors.RESET, status_text))
            print("%sDuration:%s          %dm %ds" % (Colors.BOLD, Colors.RESET, minutes, seconds))
            
            print("\n%s📊 Execution Metrics:%s" % (Colors.BOLD, Colors.RESET))
            print("  • Total Steps: %d/%d" % (summary['total_steps'], args.iterations))
            print("  • Tools Created: %d" % summary['tools_created'])
            print("  • Evidence Collected: %d items" % summary['evidence_collected'])
            print("  • Memory Operations: %d total" % summary['memory_operations'])
            
            if summary['capability_expansion']:
                print("\n%s🔧 Capabilities Created:%s" % (Colors.BOLD, Colors.RESET))
                for tool in summary['capability_expansion']:
                    print("  • %s%s%s" % (Colors.GREEN, tool, Colors.RESET))
            
            # Show evidence summary if available
            if callback_handler:
                evidence_summary = callback_handler.get_evidence_summary()
                if isinstance(evidence_summary, list) and evidence_summary:
                    print("\n%s🎯 Key Evidence:%s" % (Colors.BOLD, Colors.RESET))
                    if isinstance(evidence_summary[0], dict):
                        for ev in evidence_summary[:5]:
                            cat = ev.get('category', 'unknown')
                            content = ev.get('content', '')[:60]
                            print("  • [%s] %s..." % (cat, content))
                        if len(evidence_summary) > 5:
                            print("  • ... and %d more items" % (len(evidence_summary) - 5))
            
            print("\n%s💾 Evidence stored in:%s ./evidence_%s.faiss" % (Colors.BOLD, Colors.RESET, local_operation_id))
            print("%s" % ('='*80))
        
    except KeyboardInterrupt:
        print_status("\nOperation cancelled by user", "WARNING")
        sys.exit(1)
        
    except Exception as e:
        print_status(f"\nOperation failed: {str(e)}", "ERROR")
        logger.exception("Operation failed")
        sys.exit(1)
        
    finally:
        # Clean up resources
        from modules.memory_tools import mem0_instance
        if mem0_instance:
            try:
                # Attempt graceful cleanup if mem0 supports it
                # Note: mem0 typically handles cleanup automatically
                pass
            except Exception as cleanup_error:
                logger.warning("Error during cleanup: %s", cleanup_error)
        
        # Log operation end
        end_time = time.time()
        total_time = end_time - start_time
        logger.info("Operation %s ended after %.2fs", local_operation_id, total_time)


if __name__ == "__main__":
    main()