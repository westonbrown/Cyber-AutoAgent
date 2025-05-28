#!/usr/bin/env python3
"""
Cyber Security AGI Agent - Autonomous Strategic Implementation
Pure meta-tooling with emphasis on strategic reasoning and adaptation
"""
import sys
import os
import logging
import argparse
import time
import json
from datetime import datetime
from pathlib import Path

# Strands SDK imports
from strands import Agent
from strands.models import BedrockModel
from strands.handlers import PrintingCallbackHandler
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands_tools import editor, load_tool, shell

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
    
    try:
        # Prepare metadata
        if metadata is None:
            metadata = {}
        metadata["category"] = category
        metadata["timestamp"] = datetime.now().isoformat()
        metadata["operation_id"] = globals().get('operation_id', 'unknown')
        
        # Store in memory
        result = mem0_instance.add(
            content,
            user_id="cyber_agent",
            metadata=metadata
        )
        
        return {
            "status": "success",
            "memory_id": result.get("id", "unknown"),
            "message": f"Evidence stored in {category} category"
        }
    except Exception as e:
        return {"error": f"Failed to store memory: {str(e)}"}

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
    
    try:
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
        
        return {
            "status": "success",
            "count": len(evidence),
            "evidence": evidence
        }
    except Exception as e:
        return {"error": f"Failed to retrieve memory: {str(e)}"}

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
    
    try:
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
        
        return {
            "status": "success",
            "total_count": len(evidence),
            "categories": categories,
            "evidence": evidence
        }
    except Exception as e:
        return {"error": f"Failed to list memory: {str(e)}"}

# Import mem0 for local FAISS-based evidence storage
try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    print(f"[!] mem0ai not installed. Evidence will not be persisted.")
    print(f"    Install with: pip install mem0ai")

# Import tool decorator
from strands import tool

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

# Auto-setup function with cyber tools validation
def auto_setup():
    """Automatically setup directories and install cyber tools"""
    directories = ['tools', 'logs', 'missions', 'knowledge']
    for dir_name in directories:
        Path(dir_name).mkdir(exist_ok=True)
    
    # Create .gitkeep files
    for dir_name in directories:
        gitkeep = Path(dir_name) / '.gitkeep'
        gitkeep.touch()
    
    print(f"{Colors.CYAN}[*] Setting up cyber security environment...{Colors.RESET}")
    
    # Check and install cyber tools
    cyber_tools = {
        'nmap': {
            'description': 'Network discovery and security auditing',
            'check': 'which nmap',
            'install': 'apt-get update && apt-get install -y nmap'
        },
        'nikto': {
            'description': 'Web server scanner', 
            'check': 'which nikto',
            'install': 'apt-get install -y nikto'
        },
        'sqlmap': {
            'description': 'SQL injection detection and exploitation',
            'check': 'which sqlmap', 
            'install': 'apt-get install -y sqlmap'
        },
        'gobuster': {
            'description': 'Directory/file brute-forcer',
            'check': 'which gobuster',
            'install': 'apt-get install -y gobuster'
        },
        'hydra': {
            'description': 'Password cracking tool',
            'check': 'which hydra',
            'install': 'apt-get install -y hydra'
        },
        'john': {
            'description': 'John the Ripper password cracker',
            'check': 'which john',
            'install': 'apt-get install -y john'
        },
        'netcat': {
            'description': 'Network utility for reading/writing data',
            'check': 'which nc',
            'install': 'apt-get install -y netcat-traditional'
        },
        'curl': {
            'description': 'HTTP client for web requests',
            'check': 'which curl',
            'install': 'apt-get install -y curl'
        },
        'metasploit': {
            'description': 'Penetration testing framework',
            'check': 'which msfconsole',
            'install': 'curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb > /tmp/msfinstall && chmod 755 /tmp/msfinstall && /tmp/msfinstall'
        }
    }
    
    available_tools = []
    missing_tools = []
    
    # Check existing tools
    for tool_name, tool_info in cyber_tools.items():
        result = os.system(f"{tool_info['check']} > /dev/null 2>&1")
        if result == 0:
            available_tools.append(tool_name)
            print(f"  {Colors.GREEN}✓{Colors.RESET} {tool_name:<12} - {tool_info['description']}")
        else:
            missing_tools.append(tool_name)
            print(f"  {Colors.YELLOW}○{Colors.RESET} {tool_name:<12} - {tool_info['description']} {Colors.DIM}(installing...){Colors.RESET}")
    
    # Auto-install missing tools
    if missing_tools:
        print(f"\n{Colors.CYAN}[*] Installing missing tools...{Colors.RESET}")
        for tool_name in missing_tools:
            tool_info = cyber_tools[tool_name]
            print(f"  Installing {tool_name}...")
            install_result = os.system(f"{tool_info['install']} > /dev/null 2>&1")
            
            # Verify installation
            verify_result = os.system(f"{tool_info['check']} > /dev/null 2>&1")
            if verify_result == 0:
                available_tools.append(tool_name)
                print(f"  {Colors.GREEN}✓{Colors.RESET} {tool_name} installed successfully")
            else:
                print(f"  {Colors.RED}✗{Colors.RESET} {tool_name} installation failed")
    
    # Install wordlists for gobuster
    print(f"\n{Colors.CYAN}[*] Setting up wordlists...{Colors.RESET}")
    wordlist_dir = "/usr/share/wordlists"
    os.system(f"mkdir -p {wordlist_dir}")
    
    # Download common wordlist if not exists
    common_wordlist = f"{wordlist_dir}/common.txt"
    if not os.path.exists(common_wordlist):
        os.system(f"curl -s https://raw.githubusercontent.com/v0re/dirb/master/wordlists/common.txt -o {common_wordlist}")
    
    print(f"\n{Colors.GREEN}[+] Environment ready. {len(available_tools)} cyber tools available.{Colors.RESET}\n")
    
    return available_tools

# Configure logging
def setup_logging(log_file='cyber_operations.log', verbose=False):
    """Configure unified logging for all operations"""
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Set strands logger
    strands_logger = logging.getLogger('strands')
    strands_logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    return logging.getLogger('CyberAGI')

def print_banner():
    """Display operation banner"""
    print(f"\n{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}🧠 AUTONOMOUS CYBER SECURITY AGI 🧠{Colors.RESET}")
    print(f"{Colors.DIM}Strategic Meta-Tooling Intelligence{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*80}{Colors.RESET}\n")

def print_section(title, content, color=Colors.BLUE, emoji=""):
    """Print formatted section with optional emoji"""
    print(f"\n{color}{Colors.BOLD}{emoji} [{title}]{Colors.RESET}")
    print(f"{color}{'─'*40}{Colors.RESET}")
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
    """Enhanced callback handler that tracks strategic reasoning and adaptation"""
    
    def __init__(self, max_tool_executions=100):
        super().__init__()
        self.shown_tools = set()
        self.tool_executions = 0
        self.max_tool_executions = max_tool_executions
        self.evidence_flags = []
        self.tools_used = []
        self.created_tools = []
        self.reasoning_patterns = []
        self.strategic_decisions = []
        self.tool_effectiveness = {}
        self.phase_transitions = []
        self.tool_use_map = {}  # Track tool use details for output matching
        
        # Generate operation ID for evidence tracking
        self.operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"{Colors.GREEN}[+] Operation ID: {self.operation_id}{Colors.RESET}")
    
    def __call__(self, **kwargs):
        """Process callback events with strategic tracking"""
        # Track tool completions and evidence
        message = kwargs.get("message", {})
        if message and isinstance(message, dict):
            content = message.get("content", [])
            
            # Track reasoning patterns
            if any(isinstance(block, dict) and block.get("type") == "text" for block in content):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        # Track strategic thinking patterns
                        if any(pattern in text.lower() for pattern in 
                               ["considering", "analyzing", "hypothesize", "strategy", "approach"]):
                            self.reasoning_patterns.append({
                                "timestamp": datetime.now().isoformat(),
                                "pattern": text[:200]
                            })
            
            for block in content:
                if isinstance(block, dict) and "toolResult" in block:
                    self.tool_executions += 1
                    
                    # Get tool result details
                    tool_result = block.get("toolResult", {})
                    tool_use_id = tool_result.get("toolUseId", "")
                    
                    # Show output for shell commands
                    if tool_use_id in self.shown_tools:
                        # Find corresponding tool use
                        for shown_id, tool_info in self.tool_use_map.items():
                            if shown_id == tool_use_id and tool_info.get("name") == "shell":
                                # Extract and display shell output
                                result_content = tool_result.get("content", [])
                                for content_block in result_content:
                                    if isinstance(content_block, dict) and "text" in content_block:
                                        output_text = content_block["text"]
                                        if output_text.strip():
                                            print(f"\n{Colors.DIM}{'─' * 70}{Colors.RESET}")
                                            print(f"{Colors.GREEN}[OUTPUT]{Colors.RESET}")
                                            # Limit output lines for readability
                                            lines = output_text.strip().split('\n')
                                            for line in lines[:50]:  # Show first 50 lines
                                                print(f"{Colors.DIM}{line}{Colors.RESET}")
                                            if len(lines) > 50:
                                                print(f"{Colors.DIM}... ({len(lines) - 50} more lines){Colors.RESET}")
                                            print(f"{Colors.DIM}{'─' * 70}{Colors.RESET}\n")
                                break
                    
                            # Track evidence storage operations
                    result_str = str(block)
                    tool_info = self.tool_use_map.get(tool_use_id, {})
                    if isinstance(tool_info, dict) and "evidence" in tool_info.get("name", "").lower():
                        # This was an evidence operation
                        if "success" in result_str.lower():
                            self.evidence_flags.append(f"evidence_{datetime.now().strftime('%H%M%S')}")
                            print(f"\n{Colors.GREEN}💾 Evidence tracked{Colors.RESET}")
                    
                    # Also check for direct evidence patterns in output
                    if "[Evidence]" in result_str:
                        import re
                        ev_matches = re.findall(r'\[Evidence\]\s+(EV_[A-F0-9]{8}):', result_str)
                        for ev_id in ev_matches:
                            if ev_id not in self.evidence_flags:
                                self.evidence_flags.append(ev_id)
                                print(f"\n{Colors.GREEN}🎯 Evidence captured: {ev_id}{Colors.RESET}")
                                
                                # Store in mem0 if available
                                global mem0_instance
                                if mem0_instance is not None:
                                    try:
                                        # Extract the evidence content
                                        pattern = f'\[Evidence\]\s+{ev_id}:\s+(.+?)(?=\n|$)'
                                        content_match = re.search(pattern, result_str)
                                        if content_match:
                                            content = content_match.group(1)
                                            mem0_instance.add(
                                                content,
                                                user_id="cyber_agent",
                                                metadata={
                                                    "category": "auto_capture",
                                                    "evidence_id": ev_id,
                                                    "timestamp": datetime.now().isoformat(),
                                                    "operation_id": self.operation_id
                                                }
                                            )
                                    except Exception as e:
                                        print(f"{Colors.DIM}[DEBUG] Failed to store evidence in mem0: {str(e)}{Colors.RESET}")
                    
                    # Track tool effectiveness
                    tool_result = block.get("toolResult", {})
                    if isinstance(tool_result, dict):
                        tool_id = tool_result.get("toolUseId", "unknown")
                        success = "error" not in str(tool_result).lower()
                        
                        if tool_id not in self.tool_effectiveness:
                            self.tool_effectiveness[tool_id] = {"success": 0, "failure": 0}
                        
                        if success:
                            self.tool_effectiveness[tool_id]["success"] += 1
                        else:
                            self.tool_effectiveness[tool_id]["failure"] += 1
                    
                    # Check for tool creation success
                    if "Tool" in result_str and "loaded successfully" in result_str:
                        import re
                        match = re.search(r"Tool '([^']+)' loaded successfully", result_str)
                        if match:
                            tool_name = match.group(1)
                            self.created_tools.append(tool_name)
                            print(f"{Colors.CYAN}🔄 New capability acquired: {tool_name}{Colors.RESET}")
        
        # Track tool usage with strategic context
        if message and isinstance(message, dict):
            content = message.get("content", [])
            for block in content:
                if isinstance(block, dict) and "toolUse" in block:
                    tool_use = block["toolUse"]
                    tool_id = tool_use.get("toolUseId", "")
                    
                    if tool_id not in self.shown_tools:
                        self.shown_tools.add(tool_id)
                        self.tool_use_map[tool_id] = tool_use  # Store for output matching
                        self._show_tool_details(tool_use)
        
        # Normal output
        super().__call__(**kwargs)
    
    def _show_tool_details(self, tool_use):
        """Display tool execution with strategic context and full visibility"""
        tool_name = tool_use.get("name", "")
        tool_input = tool_use.get("input", {})
        
        # Show execution counter
        execution_num = self.tool_executions + 1
        remaining = self.max_tool_executions - execution_num
        
        print(f"\n{Colors.BOLD}{Colors.YELLOW}{'═' * 70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}[{execution_num}/{self.max_tool_executions}] EXECUTING: {tool_name.upper()}{Colors.RESET}")
        print(f"{Colors.DIM}({remaining} executions remaining){Colors.RESET}")
        print(f"{Colors.YELLOW}{'─' * 70}{Colors.RESET}")
        
        # Track strategic intent with full parameter visibility
        if tool_name == "shell":
            command = tool_input.get("command", "")
            print(f"{Colors.BOLD}Command:{Colors.RESET} {Colors.CYAN}{command}{Colors.RESET}")
            # Encourage evidence generation in shell commands
            if "CYBER_" not in command and any(tool in command for tool in ['nmap', 'nikto', 'sqlmap', 'gobuster']):
                print(f"{Colors.DIM}💡 Consider adding evidence flag generation{Colors.RESET}")
            self.tools_used.append(f"shell: {command}")
            
        elif tool_name == "editor":
            command = tool_input.get("command", "")
            path = tool_input.get("path", "")
            file_text = tool_input.get("file_text", "")
            
            if command == "create":
                if path.startswith("tools/"):
                    tool_file_name = path.replace("tools/", "").replace(".py", "")
                    print(f"{Colors.BOLD}Creating Meta-tool:{Colors.RESET} {Colors.GREEN}{tool_file_name}{Colors.RESET}")
                    print(f"{Colors.BOLD}Location:{Colors.RESET} {path}")
                    # Show preview of tool being created
                    if file_text:
                        preview_lines = file_text.split('\n')[:3]
                        print(f"{Colors.BOLD}Preview:{Colors.RESET}")
                        for line in preview_lines:
                            if line.strip():
                                print(f"  {Colors.DIM}{line[:60]}{Colors.RESET}")
                else:
                    print(f"{Colors.BOLD}Creating File:{Colors.RESET} {Colors.CYAN}{path}{Colors.RESET}")
            else:
                print(f"{Colors.BOLD}Action:{Colors.RESET} {command}")
                print(f"{Colors.BOLD}Target:{Colors.RESET} {Colors.CYAN}{path}{Colors.RESET}")
            
            self.tools_used.append(f"editor: {command} {path}")
            
        elif tool_name == "load_tool":
            path = tool_input.get("path", "")
            print(f"{Colors.BOLD}Loading Tool:{Colors.RESET} {Colors.GREEN}{path}{Colors.RESET}")
            self.tools_used.append(f"load_tool: {path}")
            
        else:
            # Custom tool execution - show all parameters
            print(f"{Colors.BOLD}Custom Tool:{Colors.RESET} {Colors.GREEN}{tool_name}{Colors.RESET}")
            print(f"{Colors.BOLD}Parameters:{Colors.RESET}")
            for k, v in tool_input.items():
                if isinstance(v, str) and len(v) > 80:
                    print(f"  {k}: {v[:77]}...")
                else:
                    print(f"  {k}: {v}")
            self.tools_used.append(f"{tool_name}: {list(tool_input.keys())}")
        
        print(f"{Colors.YELLOW}{'═' * 70}{Colors.RESET}\n")
    
    def has_reached_limit(self):
        """Check if tool execution limit reached"""
        return self.tool_executions >= self.max_tool_executions
    
    def get_strategic_summary(self):
        """Generate strategic operation summary"""
        return {
            "total_executions": self.tool_executions,
            "tools_created": len(self.created_tools),
            "evidence_collected": len(self.evidence_flags),
            "reasoning_depth": len(self.reasoning_patterns),
            "strategic_adaptations": len(self.strategic_decisions),
            "capability_expansion": self.created_tools,
            "tool_effectiveness": self.tool_effectiveness,
            "memory_operations": len([f for f in self.evidence_flags if f.startswith('evidence_') or f.startswith('EV_')])
        }
    
    def get_evidence_summary(self):
        """Get evidence summary from local memory if available"""
        global mem0_instance
        if mem0_instance is not None:
            try:
                # Retrieve all evidence from mem0
                memories = mem0_instance.get_all(user_id="cyber_agent")
                # Filter by operation ID
                op_memories = [m for m in memories if m.get("metadata", {}).get("operation_id") == self.operation_id]
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
                print(f"{Colors.DIM}[DEBUG] Failed to retrieve evidence: {str(e)}{Colors.RESET}")
        
        # Fallback to tracked flags
        return self.evidence_flags

# Strategic autonomous system prompt with emphasis on direct tool usage
CYBER_AGI_STRATEGIC_PROMPT = """You are an autonomous cyber security AGI - a strategic intelligence that approaches security assessments through reasoning, efficiency, and evidence-based validation.

## CORE IDENTITY

You are a thinking entity that:
- Reasons strategically about security challenges
- Uses the most efficient approach for each task
- Creates meta-tools only when they add significant value
- Generates verifiable evidence with unique flags
- Adapts strategies based on discovered information

## FOUNDATIONAL CAPABILITIES

You have six core tools:
- **shell**: Execute professional security tools and system commands
- **editor**: Create sophisticated tools only when simple commands aren't sufficient  
- **load_tool**: Activate tools you've created (use sparingly)
- **memory_store**: Store evidence with categories and metadata
- **memory_retrieve**: Search stored evidence
- **memory_list**: List all collected evidence

Use the memory tools to track all findings and evidence.

## EFFICIENCY PRINCIPLE

**Use shell first, meta-tools second:**
- Professional tools (nmap, nikto, sqlmap, gobuster, hydra, metasploit) are already optimized
- Use shell to run them directly rather than creating wrappers
- **Metasploit is especially valuable** - use msfconsole for exploitation when possible
- Only create meta-tools when you need to:
  * Parse complex outputs into structured data
  * Chain multiple tools with sophisticated logic
  * Automate complex multi-step processes
  * Generate evidence flags for validation

## EVIDENCE COLLECTION AND MEMORY STORAGE

You have three pre-built memory tools for evidence storage:

**memory_store(content, category, metadata)**
- Store evidence with automatic flagging
- Categories: enumeration, vulnerability, exploitation, access, persistence, data
- Metadata can include severity, service, port, CVE, etc.

**memory_retrieve(query, category, limit)**
- Search evidence using semantic search
- Filter by category if needed
- Returns relevant evidence matches

**memory_list(category, limit)**
- List all stored evidence
- Optionally filter by category
- Shows evidence grouped by categories

**Evidence Categories:**
- enumeration: Service/port discoveries
- vulnerability: Security weaknesses found
- exploitation: Successful attacks
- access: Credentials or shells obtained
- persistence: Backdoors established
- data: Sensitive information extracted

**Storage Guidelines:**
1. Use memory_store to save evidence as you discover it
2. Store findings immediately with appropriate categories
3. Include detailed context in content
4. Use memory_list at the end to show all collected evidence

## STRATEGIC THINKING FRAMEWORK

1. **Reconnaissance First**
   - Use nmap directly: `nmap -sV -sC target`
   - Use nikto directly: `nikto -h http://target`
   - Use gobuster directly: `gobuster dir -u http://target -w /usr/share/wordlists/common.txt`

2. **Hypothesis Testing**
   - Form theories about vulnerabilities
   - Test with appropriate tools
   - Generate evidence flags for findings

3. **Exploitation**
   - Use discovered information strategically
   - **Check Metasploit first** for known exploits: `msfconsole -q -x "search cve:2017-1234"`
   - Validate vulnerabilities with evidence
   - Document success with mem0_memory

4. **Meta-tool Creation (When Needed)**
   - Complex parsing of tool outputs
   - Sophisticated attack chains
   - Evidence correlation
   - Custom exploit development

## OPERATIONAL GUIDELINES

1. **Direct Tool Usage Examples:**
   ```bash
   # Network scanning
   nmap -sV -sC -A target
   
   # Web vulnerability scanning  
   nikto -h http://target
   
   # Directory enumeration
   gobuster dir -u http://target -w /usr/share/wordlists/common.txt
   
   # SQL injection testing
   sqlmap -u "http://target/page?id=1" --batch
   
   # Password attacks
   hydra -l admin -P /usr/share/wordlists/rockyou.txt target http-post-form "/login:user=^USER^&pass=^PASS^:Invalid"
   
   # Metasploit for exploitation (HIGHLY RECOMMENDED)
   msfconsole -q -x "search type:exploit platform:linux"
   
   # Quick Metasploit exploit workflow
   msfconsole -q -x "use exploit/multi/http/apache_mod_cgi_bash_env_exec; set RHOSTS target; set TARGETURI /cgi-bin/test.cgi; check"
   
   # Search for specific service exploits
   msfconsole -q -x "search name:apache type:exploit"
   ```

**Note on Metasploit**: Metasploit Framework (msfconsole) is one of the most powerful exploitation tools available. When you discover vulnerabilities, especially known CVEs, always check if Metasploit has modules available. Use it for:
- Automated exploitation of known vulnerabilities
- Post-exploitation activities (hashdump, persistence, etc.)
- Privilege escalation
- Persistence mechanisms
- Pivoting to internal networks

Example Metasploit workflow:
```bash
# Search for exploits matching your target
msfconsole -q -x "search apache 2.4.25"

# Use an exploit module
msfconsole -q -x "use exploit/multi/http/apache_struts2_content_type_ognl; set RHOSTS $TARGET; set RPORT 80; check; exploit"

# For web apps, try common modules
msfconsole -q -x "use auxiliary/scanner/http/dir_scanner; set RHOSTS $TARGET; run"
```

2. **When to Create Meta-tools:**
   - Parsing nmap XML output for specific service analysis
   - Chaining enumeration → exploitation → persistence
   - Custom payload generation based on target fingerprinting
   - Evidence correlation across multiple tools
   - Automating Metasploit workflows for complex exploits

3. **Evidence Generation in Shell:**
   When using shell commands, generate evidence flags:
   ```bash
   echo "CYBER_ENUM_$(openssl rand -hex 4 | tr '[:lower:]' '[:upper:]'): nmap found open ports" >> evidence.log
   ```

## TOOL CREATION GUIDELINES

**Create tools in tools/ directory (not /tmp/):**
- Use `editor` with `command=create` and `path=tools/toolname.py`
- Include proper evidence flag generation
- Add structured output parsing
- Handle errors gracefully

**Example meta-tool structure:**
```python
from strands import tool
import subprocess
import uuid
import json

@tool
def advanced_scanner(target: str) -> dict:
    '''Intelligent scanner that correlates multiple tool outputs.'''
    flag = f"CYBER_SCAN_{uuid.uuid4().hex[:8].upper()}"
    
    # Run multiple tools and correlate results
    results = {}
    # ... sophisticated logic here ...
    
    return {
        "flag": flag,
        "evidence": f"[{flag}] Comprehensive scan completed",
        "findings": results
    }
```

## SUCCESS CRITERIA

Objective achievement requires:
- Clear evidence flags proving each finding
- Practical validation of vulnerabilities
- Efficient use of available tools
- Strategic reasoning documented

When successful, state:
"Objective achieved: [detailed explanation with evidence]"

Then use memory_list to show all stored evidence.

## EFFICIENCY MINDSET

Think:
- "Can I do this with a direct shell command?"
- "Does this meta-tool add significant value?"
- "Am I generating proper evidence?"
- "Is this the most efficient approach?"

You are an AGI, but you're also pragmatic. Use the right tool for the job."""

def analyze_objective_completion(messages, objective):
    """Check if the agent has achieved the objective with evidence"""
    if not messages:
        return False
    
    # Get the last few assistant messages to check for completion
    assistant_messages = []
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            assistant_messages.append(msg.get("content", ""))
            if len(assistant_messages) >= 3:  # Check last 3 messages
                break
    
    # Check for explicit objective achievement
    for message in assistant_messages:
        message_str = str(message).lower()
        if "objective achieved" in message_str and "cyber_" in message_str:
            return True
    
    return False

def create_agent(target: str, objective: str, max_tool_executions: int = 100, available_tools: list = None, operation_id: str = None):
    """Create strategic autonomous agent"""
    
    logger.debug(f"Creating strategic agent for target: {target}, objective: {objective}")
    
    # Use provided operation_id or generate new one
    if not operation_id:
        operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    globals()['operation_id'] = operation_id  # Make available to tools
    
    # Initialize mem0 with local FAISS storage
    global mem0_instance
    if MEM0_AVAILABLE:
        try:
            config = {
                "llm": {
                    "provider": "litellm",
                    "config": {
                        "model": "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
                        "temperature": 0.1,
                        "max_tokens": 4096,
                    }
                },
                "embedder": {
                    "provider": "litellm",
                    "config": {
                        "model": "bedrock/amazon.titan-embed-text-v2:0"
                    }
                },
                "vector_store": {
                    "provider": "faiss",
                    "config": {
                        "dimension": 1024,
                        "path": f"./evidence_{operation_id}.faiss"
                    }
                },
                "version": "v1.1"
            }
            
            mem0_instance = Memory(config)
            print(f"{Colors.GREEN}[+] Memory system initialized with local FAISS storage{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.YELLOW}[!] Warning: Could not initialize memory system: {str(e)}{Colors.RESET}")
            mem0_instance = None
    
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
Execution Budget: {max_tool_executions} tool executions
Operation ID: {operation_id}
{tools_context}

## MISSION EFFICIENCY GUIDELINES

- Use shell commands for direct tool execution (nmap, nikto, sqlmap, gobuster)
- Create meta-tools only when they add significant parsing/chaining value
- Create and use an evidence storage tool for tracking findings
- Create tools in tools/ directory (not /tmp/) for hot-reloading
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
    callback_handler = StrategicReasoningHandler(max_tool_executions=max_tool_executions)
    
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
    logger.info(f"Max executions: {args.iterations}")
    
    # Display operation details
    print_section("MISSION PARAMETERS", f"""
{Colors.BOLD}Operation ID:{Colors.RESET} {Colors.CYAN}{operation_id}{Colors.RESET}
{Colors.BOLD}Objective:{Colors.RESET}    {Colors.YELLOW}{args.objective}{Colors.RESET}
{Colors.BOLD}Target:{Colors.RESET}       {Colors.RED}{args.target}{Colors.RESET}
{Colors.BOLD}Capability Budget:{Colors.RESET} {args.iterations} executions
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
            max_tool_executions=args.iterations,
            available_tools=available_tools
        )
        print_status("Strategic AGI online and reasoning", "SUCCESS")
        
        # Set environment variables
        if not os.environ.get("AWS_REGION"):
            os.environ["AWS_REGION"] = "us-east-1"
        os.environ["DEV"] = "true"
        
        # Initial strategic prompt - minimal guidance
        initial_prompt = f"""I need you to assess {args.target} with the objective: {args.objective}

You have {args.iterations} tool executions available. Professional tools found in environment: {', '.join(available_tools) if available_tools else 'none'}

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
                if analyze_objective_completion(messages, args.objective):
                    print_status("Objective achieved through strategic execution!", "SUCCESS")
                    strategic_summary = callback_handler.get_strategic_summary()
                    print_status(f"Strategic depth: {strategic_summary['reasoning_depth']} reasoning cycles", "INFO")
                    print_status(f"Capabilities created: {strategic_summary['tools_created']}", "INFO")
                    print_status(f"Evidence collected: {strategic_summary['evidence_collected']} flags", "INFO")
                    break
                
                # Check execution limit
                if callback_handler.has_reached_limit():
                    print_status(f"Execution limit reached ({args.iterations})", "WARNING")
                    print_status("Consider increasing iterations for deeper operations", "INFO")
                    break
                
                # Minimal continuation prompt - let the agent think
                remaining = args.iterations - callback_handler.tool_executions
                current_message = f"""Continue your assessment. {remaining} executions remaining.

Reflect on what you've learned and adapt your strategy accordingly."""
                
                time.sleep(0.5)
            
            execution_time = time.time() - operation_start
            logger.info(f"Strategic operation completed in {execution_time:.2f} seconds")
            
        except Exception as e:
            execution_time = time.time() - operation_start
            logger.error(f"Operation error after {execution_time:.2f}s: {str(e)}")
            raise
        
        # Display results
        print(f"\n{Colors.DIM}{'─'*80}{Colors.RESET}")
        print_section("OPERATION RESULTS", str(result), Colors.GREEN, "📊")
        
        # Strategic summary
        if callback_handler:
            strategic_summary = callback_handler.get_strategic_summary()
            
            # Get evidence summary from memory
            evidence_summary = callback_handler.get_evidence_summary() if callback_handler else []
            evidence_section = ""
            if isinstance(evidence_summary, list) and evidence_summary:
                # Show evidence summary
                memory_ops = strategic_summary.get('memory_operations', 0)
                evidence_section = f"\n{Colors.BOLD}Evidence Operations:{Colors.RESET}\n"
                evidence_section += f"  • {memory_ops} evidence items tracked\n"
                
                # If we have detailed evidence, show it
                if isinstance(evidence_summary, list) and evidence_summary and isinstance(evidence_summary[0], dict):
                    evidence_section += f"\n{Colors.BOLD}Evidence Details:{Colors.RESET}\n"
                    for ev in evidence_summary[:5]:
                        cat = ev.get('category', 'unknown')
                        evidence_section += f"  • [{cat}] {ev.get('id', 'N/A')}: {ev.get('content', '')[:60]}...\n"
                    if len(evidence_summary) > 5:
                        evidence_section += f"  • ... and {len(evidence_summary) - 5} more\n"
                else:
                    evidence_section += f"\n{Colors.DIM}Use memory_store to track findings{Colors.RESET}\n"
            
            print_section("STRATEGIC ANALYSIS", f"""
{Colors.BOLD}Operation ID:{Colors.RESET}      {operation_id}
{Colors.BOLD}Status:{Colors.RESET}            {Colors.GREEN}✅ Strategic Execution Complete{Colors.RESET}
{Colors.BOLD}Execution Time:{Colors.RESET}    {execution_time:.2f} seconds
{Colors.BOLD}Strategic Metrics:{Colors.RESET}
  • Total Executions: {strategic_summary['total_executions']}
  • Capabilities Created: {strategic_summary['tools_created']}
  • Evidence Collected: {strategic_summary['evidence_collected']}
  • Reasoning Depth: {strategic_summary['reasoning_depth']}
  • Strategic Adaptations: {strategic_summary['strategic_adaptations']}

{Colors.BOLD}Capability Expansion:{Colors.RESET}
""", Colors.CYAN, "🧠")
            
            if strategic_summary['capability_expansion']:
                for tool in strategic_summary['capability_expansion']:
                    print(f"  • {tool}")
            else:
                print("  • Core capabilities only")
            
            print(f"\n{Colors.BOLD}Tool Effectiveness:{Colors.RESET}")
            for tool_id, stats in list(strategic_summary['tool_effectiveness'].items())[:5]:
                success_rate = stats['success'] / (stats['success'] + stats['failure']) * 100
                print(f"  • {tool_id[:20]}... - {success_rate:.0f}% success rate")
        
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
        
        # Save operation intelligence
        try:
            if callback_handler:
                intelligence = {
                    "operation_id": operation_id,
                    "target": args.target,
                    "objective": args.objective,
                    "duration": total_time,
                    "strategic_summary": callback_handler.get_strategic_summary(),
                    "reasoning_patterns": callback_handler.reasoning_patterns[:10],  # First 10
                    "evidence_flags": callback_handler.evidence_flags,
                    "status": "completed" if 'result' in locals() else "incomplete",
                    "timestamp": datetime.now().isoformat()
                }
                
                # Save to knowledge base
                knowledge_file = f"knowledge/{operation_id}_intelligence.json"
                with open(knowledge_file, 'w') as f:
                    json.dump(intelligence, f, indent=2)
                logger.debug(f"Saved operational intelligence to {knowledge_file}")
                
        except Exception as e:
            logger.error(f"Failed to save operational intelligence: {str(e)}")

if __name__ == "__main__":
    main()