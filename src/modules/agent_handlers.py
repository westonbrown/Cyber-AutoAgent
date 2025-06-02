#!/usr/bin/env python3

import sys
import io
from datetime import datetime
from typing import List, Dict
from strands.handlers import PrintingCallbackHandler
from .utils import Colors

# Constants for display formatting
CONTENT_PREVIEW_LENGTH = 60
METADATA_PREVIEW_LENGTH = 40
MAX_TOOL_CODE_LINES = 100
EVIDENCE_PREVIEW_LENGTH = 80
FALLBACK_EVIDENCE_PREVIEW_LENGTH = 200

class ReasoningHandler(PrintingCallbackHandler):
    """Enhanced callback handler based on working implementation with proper step enforcement"""
    
    def __init__(self, max_steps=100):
        super().__init__()
        self.steps = 0
        self.max_steps = max_steps
        self.memory_operations = 0
        self.created_tools = []
        self.tools_used = []
        self.tool_effectiveness = {}
        self.last_was_reasoning = False
        self.last_was_tool = False
        self.shown_tools = set()  # Track shown tools to avoid duplicates
        self.tool_use_map = {}  # Map tool IDs to tool info
        self.tool_results = {}  # Store tool results for output display
        self.suppress_parent_output = False  # Flag to control parent handler
        self.step_limit_reached = False  # Flag to track if we've hit the limit
        self.report_generated = False  # Flag to prevent duplicate reports
        
        # Generate operation ID and show clean header
        self.operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Clean header with full-width break lines
        print(f"\n{Colors.DIM}{'─' * 80}{Colors.RESET}")
        print(f"🔐 {Colors.CYAN}{Colors.BOLD}Cyber Security Assessment{Colors.RESET}")
        print(f"   Operation: {Colors.DIM}{self.operation_id}{Colors.RESET}")
        print(f"   Started:   {Colors.DIM}{timestamp}{Colors.RESET}")
        print(f"{Colors.DIM}{'─' * 80}{Colors.RESET}")
        print()
    
    def __call__(self, **kwargs):
        """Process callback events with proper step limiting and clean formatting"""
        
        # Handle streaming text data (reasoning/thinking)
        if "data" in kwargs:
            text = kwargs.get("data", "")
            self._handle_text_block(text)
            return
        
        # Handle message events (tool uses and results)
        if "message" in kwargs:
            message = kwargs["message"]
            if isinstance(message, dict):
                content = message.get("content", [])
                
                # First, handle any text blocks (reasoning)
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        self._handle_text_block(text)
                
                # Process tool uses
                for block in content:
                    if isinstance(block, dict) and "toolUse" in block:
                        tool_use = block["toolUse"]
                        tool_id = tool_use.get("toolUseId", "")
                        
                        # Only process if not already shown and has valid input
                        if tool_id not in self.shown_tools:
                            tool_input = tool_use.get("input", {})
                            if self._is_valid_tool_use(tool_use.get("name", ""), tool_input):
                                # Step limit is now checked in _show_tool_execution - no need for pre-check
                                self.shown_tools.add(tool_id)
                                self.tool_use_map[tool_id] = tool_use
                                self._show_tool_execution(tool_use)
                                self.last_was_tool = True
                                self.last_was_reasoning = False
                
                # Process tool results
                for block in content:
                    if isinstance(block, dict) and "toolResult" in block:
                        tool_result = block["toolResult"]
                        tool_id = tool_result.get("toolUseId", "")
                        
                        # Store result for later display
                        if tool_id in self.tool_use_map:
                            self.tool_results[tool_id] = tool_result
                            self._show_tool_result(tool_id, tool_result)
                            
                            # Track tool effectiveness
                            self._track_tool_effectiveness(tool_id, tool_result)
                            
                            # Track memory operations
                            tool_name = self.tool_use_map[tool_id].get("name", "")
                            if tool_name == "memory_store":
                                self.memory_operations += 1
                
                # Suppress parent output to avoid duplication
                self.suppress_parent_output = True
                return
        
        # Handle tool usage announcement from streaming
        if "current_tool_use" in kwargs:
            tool = kwargs["current_tool_use"]
            tool_id = tool.get("toolUseId", "")
            
            # Check if this tool has valid input
            tool_input = tool.get("input", {})
            if self._is_valid_tool_use(tool.get("name", ""), tool_input):
                # Only show if not already shown
                if tool_id not in self.shown_tools:
                    # Step limit is now checked in _show_tool_execution - no need for pre-check
                    self.shown_tools.add(tool_id)
                    self.tool_use_map[tool_id] = tool
                    self._show_tool_execution(tool)
                    self.last_was_tool = True
                    self.last_was_reasoning = False
            return
        
        # Handle tool result events
        if "toolResult" in kwargs:
            tool_result = kwargs["toolResult"]
            tool_id = tool_result.get("toolUseId", "")
            
            if tool_id in self.tool_use_map:
                self._show_tool_result(tool_id, tool_result)
                self._track_tool_effectiveness(tool_id, tool_result)
            return
        
        # For lifecycle events, pass to parent but respect suppression flag
        if any(k in kwargs for k in ["init_event_loop", "start_event_loop", "start", "complete", "force_stop"]):
            if not self.suppress_parent_output:
                super().__call__(**kwargs)
            return
    
    def _is_valid_tool_use(self, tool_name, tool_input):
        """Check if this tool use has valid input (not empty)"""
        if not tool_input:
            return False
        
        # Ensure tool_input is a dictionary
        if not isinstance(tool_input, dict):
            return False
            
        if tool_name == "shell":
            return bool(tool_input.get("command", "").strip())
        elif tool_name == "memory_store":
            return bool(tool_input.get("content", "").strip())
        elif tool_name == "memory_retrieve":
            return bool(tool_input.get("query", "").strip())
        elif tool_name == "memory_list":
            return True  # Always valid
        elif tool_name == "file_write":
            return bool(tool_input.get("path") and tool_input.get("content"))
        elif tool_name == "editor":
            return bool(tool_input.get("command") and tool_input.get("path"))
        elif tool_name == "load_tool":
            return bool(tool_input.get("path", "").strip())
        else:
            # For other tools, assume valid if there's any input
            return bool(tool_input)
    
    def _handle_text_block(self, text):
        """Handle text blocks (reasoning/thinking) with proper formatting"""
        if text and not text.isspace():
            # Add spacing before reasoning if last was a tool
            if self.last_was_tool:
                print()  # Add spacing
                self.last_was_tool = False
            
            print(text, end='', flush=True)
            self.last_was_reasoning = True
    
    def _show_tool_execution(self, tool_use):
        """Display tool execution with clean formatting based on working implementation"""
        self.steps += 1
        
        # Check step limit immediately after incrementing
        if self.has_reached_limit() and not self.step_limit_reached:
            self.step_limit_reached = True
            print(f"\n{Colors.BLUE}✅ Step limit reached ({self.max_steps}). Assessment complete.{Colors.RESET}")
            # Stop all further processing by raising StopIteration
            raise StopIteration("Step limit reached - clean termination")
        
        tool_name = tool_use.get("name", "unknown")
        tool_input = tool_use.get("input", {})
        if not isinstance(tool_input, dict):
            tool_input = {}
        
        # Add reasoning separator if needed
        if self.last_was_reasoning:
            print()  # Add line after reasoning
        
        # Print step header with exact format from working version
        print(f"{'─' * 80}")
        print(f"Step {self.steps}/{self.max_steps}: {Colors.CYAN}{tool_name}{Colors.RESET}")
        print(f"{'─' * 80}")
        
        # Show detailed tool information
        if tool_name == "shell":
            command = tool_input.get("command", "")
            print(f"↳ Running: {Colors.GREEN}{command}{Colors.RESET}")
            self.tools_used.append(f"shell: {command}")
            
        elif tool_name == "file_write":
            path = tool_input.get("path", "")
            content_preview = str(tool_input.get("content", ""))[:50]
            print(f"↳ Writing: {Colors.YELLOW}{path}{Colors.RESET}")
            if content_preview:
                print(f"  Content: {Colors.DIM}{content_preview}...{Colors.RESET}")
            
            # Track tool creation
            if path and path.startswith("tools/"):
                self.created_tools.append(path.replace("tools/", "").replace(".py", ""))
            
            self.tools_used.append(f"file_write: {path}")
            
        elif tool_name == "editor":
            command = tool_input.get("command", "")
            path = tool_input.get("path", "")
            file_text = tool_input.get("file_text", "")
            
            print(f"↳ Editor: {Colors.CYAN}{command}{Colors.RESET}")
            print(f"  Path: {Colors.YELLOW}{path}{Colors.RESET}")
            
            # Store and show content if creating a tool
            if command == "create" and path and path.startswith("tools/") and file_text:
                self.created_tools.append(path.replace("tools/", "").replace(".py", ""))
                print(f"\n{'─' * 70}")
                print(f"📄 {Colors.YELLOW}META-TOOL CODE:{Colors.RESET}")
                print(f"{'─' * 70}")
                # Display the tool code with syntax highlighting
                for line in file_text.split('\n')[:MAX_TOOL_CODE_LINES]:  # Show first 100 lines
                    if line.strip().startswith("@tool"):
                        print(f"{Colors.GREEN}{line}{Colors.RESET}")
                    elif line.strip().startswith("def "):
                        print(f"{Colors.CYAN}{line}{Colors.RESET}")
                    elif line.strip().startswith("#"):
                        print(f"{Colors.DIM}{line}{Colors.RESET}")
                    else:
                        print(line)
                if len(file_text.split('\n')) > 20:
                    print(f"{Colors.DIM}... ({len(file_text.split('\n')) - 20} more lines){Colors.RESET}")
                print(f"{'─' * 70}")
            
            self.tools_used.append(f"editor: {command} {path}")
            
        elif tool_name == "load_tool":
            path = tool_input.get("path", "")
            print(f"↳ Loading: {Colors.GREEN}{path}{Colors.RESET}")
            self.tools_used.append(f"load_tool: {path}")
            
        elif tool_name in ["memory_store", "memory_retrieve", "memory_list"]:
            if tool_name == "memory_store":
                category = tool_input.get("category", "general")
                content = str(tool_input.get("content", ""))[:CONTENT_PREVIEW_LENGTH]
                metadata = tool_input.get("metadata", {})
                print(f"↳ Storing [{Colors.CYAN}{category}{Colors.RESET}]: {Colors.DIM}{content}{'...' if len(str(tool_input.get('content', ''))) > CONTENT_PREVIEW_LENGTH else ''}{Colors.RESET}")
                if metadata:
                    print(f"  Metadata: {Colors.DIM}{str(metadata)[:METADATA_PREVIEW_LENGTH]}{'...' if len(str(metadata)) > METADATA_PREVIEW_LENGTH else ''}{Colors.RESET}")
            elif tool_name == "memory_retrieve":
                query = tool_input.get("query", "")
                category = tool_input.get("category")
                limit = tool_input.get("limit", 10)
                print(f"↳ Searching: {Colors.CYAN}\"{query}\"{Colors.RESET}")
                if category:
                    print(f"  Category: {Colors.CYAN}{category}{Colors.RESET}, Limit: {limit}")
            elif tool_name == "memory_list":
                category = tool_input.get("category", "all")
                limit = tool_input.get("limit", 50)
                print(f"↳ Listing evidence: {Colors.CYAN}{category}{Colors.RESET} (max: {limit})")
            
            self.tools_used.append(f"{tool_name}: executed")
            
        else:
            # Custom tool
            if tool_input:
                # Show first 2 most relevant parameters
                key_params = list(tool_input.keys())[:2]
                if key_params:
                    params_str = ", ".join(f"{k}={str(tool_input[k])[:20]}{'...' if len(str(tool_input[k])) > 20 else ''}" for k in key_params)
                    print(f"↳ Parameters: {Colors.DIM}{params_str}{Colors.RESET}")
                else:
                    print(f"↳ Executing: {Colors.MAGENTA}{tool_name}{Colors.RESET}")
            else:
                print(f"↳ Executing: {Colors.MAGENTA}{tool_name}{Colors.RESET}")
            
            self.tools_used.append(f"{tool_name}: {list(tool_input.keys())}")
        
        # Add blank line for readability
        print()
        self.last_was_tool = True
        self.last_was_reasoning = False
    
    def _show_tool_result(self, tool_id, tool_result):
        """Display tool execution results if they contain meaningful output"""
        tool_use = self.tool_use_map.get(tool_id, {})
        tool_name = tool_use.get("name", "unknown")
        
        # Extract result content
        result_content = tool_result.get("content", [])
        status = tool_result.get("status", "unknown")
        
        # Show output based on tool type - following working implementation pattern
        if tool_name == "shell" and result_content:
            # Shell command output - process only first text block to avoid duplicates
            for content_block in result_content:
                if isinstance(content_block, dict) and "text" in content_block:
                    output_text = content_block.get("text", "")
                    if output_text.strip():
                        # Filter out execution summary lines (same as working version)
                        lines = output_text.strip().split('\n')
                        filtered_lines = []
                        skip_summary = False
                        for line in lines:
                            # Skip execution summary section
                            if "Execution Summary:" in line:
                                skip_summary = True
                                continue
                            if skip_summary and ("Total commands:" in line or "Successful:" in line or "Failed:" in line):
                                continue
                            if skip_summary and line.strip() == "":
                                skip_summary = False
                                continue
                            if not skip_summary:
                                filtered_lines.append(line)
                        
                        # Only show output if there's content after filtering
                        if filtered_lines and any(line.strip() for line in filtered_lines):
                            for line in filtered_lines:
                                print(line)
                    break 
        elif status == "error":
            # Show errors for any tool, but filter out empty error messages
            for content_block in result_content:
                if isinstance(content_block, dict) and "text" in content_block:
                    error_text = content_block.get("text", "").strip()
                    if error_text and error_text != "Error:":
                        print(f"{Colors.RED}Error: {error_text}{Colors.RESET}")
        
        # Add separator line after tool result
        print(f"{Colors.DIM}{'─' * 80}{Colors.RESET}")
    
    def _track_tool_effectiveness(self, tool_id, tool_result):
        """Track tool effectiveness for analysis"""
        tool_use = self.tool_use_map.get(tool_id, {})
        tool_name = tool_use.get("name", "unknown")
        status = tool_result.get("status", "unknown")
        
        if tool_name not in self.tool_effectiveness:
            self.tool_effectiveness[tool_name] = {"success": 0, "error": 0}
        
        if status == "success":
            self.tool_effectiveness[tool_name]["success"] += 1
        else:
            self.tool_effectiveness[tool_name]["error"] += 1
    
    def has_reached_limit(self):
        """Check if step limit reached"""
        return self.steps >= self.max_steps
    
    def get_remaining_steps(self):
        """Get remaining steps for budget management"""
        return max(0, self.max_steps - self.steps)
    
    def get_budget_urgency_level(self):
        """Get current budget urgency level for decision making"""
        remaining = self.get_remaining_steps()
        if remaining > 20:
            return "ABUNDANT"
        elif remaining > 10:
            return "CONSTRAINED" 
        elif remaining > 5:
            return "CRITICAL"
        else:
            return "EMERGENCY"
    
    def get_summary(self):
        """Generate operation summary"""
        return {
            "total_steps": self.steps,
            "tools_created": len(self.created_tools),
            "evidence_collected": self.memory_operations,
            "capability_expansion": self.created_tools,
            "memory_operations": self.memory_operations,
            "operation_id": self.operation_id
        }
    
    def get_evidence_summary(self):
        """Get evidence summary from local memory if available"""
        from .memory_tools import mem0_instance
        if mem0_instance is None:
            return []
            
        try:
            # Retrieve all evidence from mem0
            memories = mem0_instance.get_all(user_id="cyber_agent")
            
            # Handle different response formats
            if not isinstance(memories, list):
                return []
                
            op_memories = [m for m in memories if isinstance(m, dict) and m.get("metadata", {}).get("operation_id") == self.operation_id]
            
            return [
                {
                    "id": m.get("metadata", {}).get("evidence_id", m.get("id", "unknown")),
                    "content": m.get("memory", ""),
                    "category": m.get("metadata", {}).get("category", "unknown"),
                    "timestamp": m.get("metadata", {}).get("timestamp", "")
                }
                for m in op_memories
            ]
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Error in evidence summary: {str(e)}{Colors.RESET}")
            return []
    
    def generate_final_report(self, agent, target: str, objective: str) -> None:
        """
        Generate comprehensive final assessment report using LLM analysis.
        
        Args:
            agent: The agent instance for generating the report
            target: Target system being assessed
            objective: Assessment objective/goals
        """
        # Prevent duplicate report generation
        if self.report_generated:
            return
        self.report_generated = True
        
        print(f"\n{Colors.DIM}{'═' * 80}{Colors.RESET}")
        print(f"📊 {Colors.CYAN}{Colors.BOLD}Generating Final Assessment Report{Colors.RESET}")
        print(f"{Colors.DIM}{'═' * 80}{Colors.RESET}")
        
        # Retrieve evidence from memory system
        evidence = self._retrieve_evidence()
        
        if not evidence:
            self._display_no_evidence_message()
            return
        
        # Generate LLM-based assessment report
        try:
            report_content = self._generate_llm_report(agent, target, objective, evidence)
            self._display_final_report(report_content)
            
        except Exception as e:
            print(f"{Colors.RED}Error generating final report: {str(e)}{Colors.RESET}")
            self._display_fallback_evidence(evidence)
    
    def _retrieve_evidence(self) -> List[Dict]:
        """Retrieve all collected evidence from memory system."""
        evidence = []
        
        # Access memory tools module
        from . import memory_tools
        
        if memory_tools.mem0_instance is not None:
            try:
                all_memories = memory_tools.mem0_instance.get_all(user_id="cyber_agent")
                
                # Handle different mem0 response formats
                if isinstance(all_memories, dict) and "memories" in all_memories:
                    all_memories = all_memories["memories"]
                elif isinstance(all_memories, dict) and "results" in all_memories:
                    all_memories = all_memories["results"]
                elif not isinstance(all_memories, list):
                    all_memories = []
                
                # Convert to standardized evidence format
                for memory in all_memories:
                    if isinstance(memory, dict):
                        evidence.append({
                            "id": memory.get("id", "unknown"),
                            "content": memory.get("memory", ""),
                            "category": memory.get("metadata", {}).get("category", "unknown"),
                            "timestamp": memory.get("metadata", {}).get("timestamp", "")
                        })
                        
                print(f"{Colors.DIM}Retrieved {len(evidence)} evidence items from memory{Colors.RESET}")
                        
            except Exception as e:
                print(f"{Colors.YELLOW}Warning: Error retrieving memories: {str(e)}{Colors.RESET}")
        
        return evidence
    
    def _display_no_evidence_message(self) -> None:
        """Display message when no evidence is available."""
        print(f"{Colors.YELLOW}No evidence collected during operation{Colors.RESET}")
        print(f"{Colors.DIM}Steps completed: {self.steps}/{self.max_steps}{Colors.RESET}")
        print(f"{Colors.DIM}Memory operations: {self.memory_operations}{Colors.RESET}")
    
    def _generate_llm_report(self, agent, target: str, objective: str, evidence: List[Dict]) -> str:
        """Generate assessment report using LLM analysis."""
        # Format evidence for LLM analysis
        evidence_text = [f"[{item['category'].upper()}] {item['content']}" for item in evidence]
        
        report_prompt = f"""Based on the evidence collected during this cyber security assessment, generate a comprehensive final report.

TARGET: {target}
OBJECTIVE: {objective}
EVIDENCE COLLECTED ({len(evidence)} items):

{chr(10).join(evidence_text)}

Please provide:
1. Executive Summary of findings
2. Critical vulnerabilities discovered
3. Attack vectors identified
4. Risk assessment
5. Recommendations for remediation
6. Overall security posture evaluation

Format this as a professional penetration testing report."""

        print(f"{Colors.DIM}Analyzing collected evidence and generating insights...{Colors.RESET}")
        
        if not (agent and callable(agent)):
            raise ValueError("Agent not available for report generation")
            
        # Capture stdout to prevent duplicate display
        original_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            # Generate report with suppressed output
            raw_report = agent(report_prompt, messages=[])
            return self._clean_duplicate_content(str(raw_report))
        finally:
            # Restore stdout
            sys.stdout = original_stdout
    
    def _clean_duplicate_content(self, report_content: str) -> str:
        """Remove duplicate sections from LLM-generated content."""
        report_lines = report_content.split('\n')
        clean_lines = []
        seen_section_markers = set()
        
        i = 0
        while i < len(report_lines):
            line = report_lines[i]
            
            # Check for report start markers that indicate duplication
            if (line.strip().startswith('# Penetration Testing Report') or
                line.strip().startswith('**Target:') or
                (line.strip().startswith('# ') and 'Report' in line)):
                
                # If we've seen this exact marker before, stop processing
                if line.strip() in seen_section_markers:
                    break
                    
                # For the main report header, also check if we already have content
                if (line.strip().startswith('# Penetration Testing Report') and 
                    len(clean_lines) > 10):  # Already have substantial content
                    break
                    
                seen_section_markers.add(line.strip())
            
            # Check for duplicate executive summary sections
            elif (line.strip().startswith('## 1. Executive Summary') and
                  any('## 1. Executive Summary' in existing_line for existing_line in clean_lines)):
                # Found duplicate executive summary, stop here
                break
                
            clean_lines.append(line)
            i += 1
        
        return '\n'.join(clean_lines)
    
    def _display_final_report(self, report_content: str) -> None:
        """Display the final assessment report."""
        print(f"\n{Colors.DIM}{'─' * 80}{Colors.RESET}")
        print(f"📋 {Colors.GREEN}{Colors.BOLD}FINAL ASSESSMENT REPORT{Colors.RESET}")
        print(f"{Colors.DIM}{'─' * 80}{Colors.RESET}")
        print(f"\n{report_content}")
        print(f"\n{Colors.DIM}{'─' * 80}{Colors.RESET}")
    
    def _display_fallback_evidence(self, evidence: List[Dict]) -> None:
        """Display evidence summary as fallback when LLM generation fails."""
        print(f"\n{Colors.YELLOW}Displaying collected evidence instead:{Colors.RESET}")
        for i, item in enumerate(evidence, 1):
            print(f"\n{i}. {Colors.GREEN}[{item['category']}]{Colors.RESET}")
            content_preview = item['content'][:FALLBACK_EVIDENCE_PREVIEW_LENGTH]
            print(f"   {content_preview}{'...' if len(item['content']) > FALLBACK_EVIDENCE_PREVIEW_LENGTH else ''}")
            if len(item['content']) > FALLBACK_EVIDENCE_PREVIEW_LENGTH:
                print(f"   {Colors.DIM}(truncated){Colors.RESET}")