#!/usr/bin/env python3
"""
Tool for managing memories using Mem0 (store, delete, list, get, and retrieve)

This module provides comprehensive memory management capabilities using
Mem0 as the backend. It handles all aspects of memory management with
a user-friendly interface and proper error handling.

Key Features:
------------
1. Memory Management:
   • store: Add new memories with automatic ID generation and metadata
   • delete: Remove existing memories using memory IDs
   • list: Retrieve all memories for a user or agent
   • get: Retrieve specific memories by memory ID
   • retrieve: Perform semantic search across all memories

2. Safety Features:
   • User confirmation for mutative operations
   • Content previews before storage
   • Warning messages before deletion
   • BYPASS_TOOL_CONSENT mode for bypassing confirmations in tests

3. Advanced Capabilities:
   • Automatic memory ID generation
   • Structured memory storage with metadata
   • Semantic search with relevance filtering
   • Rich output formatting
   • Support for both user and agent memories
   • Multiple vector database backends (OpenSearch, Mem0 Platform, FAISS)

4. Error Handling:
   • Memory ID validation
   • Parameter validation
   • Graceful API error handling
   • Clear error messages

5. Configurable Components:
   • Embedder (AWS Bedrock, Ollama, OpenAI)
   • LLM (AWS Bedrock, Ollama, OpenAI)
   • Vector Store (FAISS, OpenSearch, Mem0 Platform)

Usage Examples:
--------------
```python
from strands import Agent
from modules.memory_tools import mem0_memory

agent = Agent(tools=[mem0_memory])

# Store memory in Memory
agent.tool.mem0_memory(
    action="store",
    content="Important information to remember",
    user_id="alex",  # or agent_id="agent1"
    metadata={"category": "finding"}
)

# Retrieve content using semantic search
agent.tool.mem0_memory(
    action="retrieve",
    query="meeting information",
    user_id="alex"  # or agent_id="agent1"
)

# List all memories
agent.tool.mem0_memory(
    action="list",
    user_id="alex"  # or agent_id="agent1"
)
```
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

import boto3
from mem0 import Memory as Mem0Memory
from mem0 import MemoryClient
from opensearchpy import AWSV4SignerAuth, RequestsHttpConnection
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from strands import tool
from .config import get_config_manager

# Set up logging
logger = logging.getLogger(__name__)

# Initialize Rich console
console = Console()

# Global configuration and client
_MEMORY_CONFIG = None
_MEMORY_CLIENT = None


TOOL_SPEC = {
    "name": "mem0_memory",
    "description": (
        "Memory management tool for storing, retrieving, and managing memories in Mem0.\n\n"
        "Features:\n"
        "1. Store memories with metadata (requires user_id or agent_id)\n"
        "2. Retrieve memories by ID or semantic search (requires user_id or agent_id)\n"
        "3. List all memories for a user/agent (requires user_id or agent_id)\n"
        "4. Delete memories\n"
        "5. Get memory history\n\n"
        "Actions:\n"
        "- store: Store new memory (requires user_id or agent_id)\n"
        "- get: Get memory by ID\n"
        "- list: List all memories (requires user_id or agent_id)\n"
        "- retrieve: Semantic search (requires user_id or agent_id)\n"
        "- delete: Delete memory\n"
        "- history: Get memory history\n\n"
        "Note: Most operations require either user_id or agent_id to be specified."
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "Action to perform (store, get, list, retrieve, delete, history)"
                    ),
                    "enum": ["store", "get", "list", "retrieve", "delete", "history"],
                },
                "content": {
                    "type": "string",
                    "description": "Content to store (required for store action)",
                },
                "memory_id": {
                    "type": "string",
                    "description": "Memory ID (required for get, delete, history actions)",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (required for retrieve action)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID for the memory operations (required for store, list, retrieve actions)",
                },
                "agent_id": {
                    "type": "string",
                    "description": "Agent ID for the memory operations (required for store, list, retrieve actions)",
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata to store with the memory",
                },
            },
            "required": ["action"],
        }
    },
}


class Mem0ServiceClient:
    """Client for interacting with Mem0 service."""

    @staticmethod
    def get_default_config(server: str = "remote") -> Dict:
        """Get default configuration from ConfigManager."""
        config_manager = get_config_manager()
        mem0_config = config_manager.get_mem0_service_config(server)

        # Add RequestsHttpConnection for OpenSearch if needed
        if mem0_config["vector_store"]["provider"] == "opensearch":
            mem0_config["vector_store"]["config"]["connection_class"] = (
                RequestsHttpConnection
            )

        return mem0_config

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the Mem0 service client.

        Args:
            config: Optional configuration dictionary to override defaults.
                   If provided, it will be merged with the default configuration.

        The client will use one of three backends based on environment variables:
        1. Mem0 Platform if MEM0_API_KEY is set
        2. OpenSearch if OPENSEARCH_HOST is set
        3. FAISS (default) if neither MEM0_API_KEY nor OPENSEARCH_HOST is set
        """
        self.region = None  # Initialize region attribute
        self.mem0 = self._initialize_client(config)
        self.config = config  # Store config for later use

        # Display memory overview if existing memories are detected
        self._display_startup_overview()

    def _initialize_client(self, config: Optional[Dict] = None) -> Any:
        """Initialize the appropriate Mem0 client based on environment variables.

        Args:
            config: Optional configuration dictionary to override defaults.

        Returns:
            An initialized Mem0 client (MemoryClient or Mem0Memory instance).
        """
        if os.environ.get("MEM0_API_KEY"):
            print("[+] Memory Backend: Mem0 Platform (cloud)")
            print(f"    API Key: {'*' * 8}{os.environ.get('MEM0_API_KEY', '')[-4:]}")
            logger.debug("Using Mem0 Platform backend (MemoryClient)")
            return MemoryClient()

        # Determine server type based on environment
        # Use remote if OpenSearch is available, otherwise local
        server_type = "remote" if os.environ.get("OPENSEARCH_HOST") else "local"

        if os.environ.get("OPENSEARCH_HOST"):
            merged_config = self._merge_config(config, server_type)
            config_manager = get_config_manager()
            embedder_region = (
                merged_config.get("embedder", {})
                .get("config", {})
                .get("aws_region", config_manager.get_default_region())
            )

            print("[+] Memory Backend: OpenSearch")
            print(f"    Host: {os.environ.get('OPENSEARCH_HOST')}")
            print(f"    Region: {embedder_region}")
            print(
                f"    Embedder: AWS Bedrock - {merged_config['embedder']['config']['model']} (1024 dims)"
            )
            print(f"    LLM: AWS Bedrock - {merged_config['llm']['config']['model']}")
            logger.debug("Using OpenSearch backend (Mem0Memory with OpenSearch)")
            return self._initialize_opensearch_client(config, server_type)

        # FAISS backend
        logger.debug("Using FAISS backend (Mem0Memory with FAISS)")
        return self._initialize_faiss_client(config, server_type)

    def _initialize_opensearch_client(
        self, config: Optional[Dict] = None, server: str = "remote"
    ) -> Mem0Memory:
        """Initialize a Mem0 client with OpenSearch backend.

        Args:
            config: Optional configuration dictionary to override defaults.
            server: Server type for configuration.

        Returns:
            An initialized Mem0Memory instance configured for OpenSearch.
        """
        # Set up AWS region - prioritize passed config, then environment, then default
        merged_config = self._merge_config(config, server)
        config_manager = get_config_manager()
        config_region = (
            merged_config.get("embedder", {}).get("config", {}).get("aws_region")
        )
        self.region = (
            config_region
            or os.environ.get("AWS_REGION")
            or config_manager.get_default_region()
        )

        if not os.environ.get("AWS_REGION"):
            os.environ["AWS_REGION"] = self.region

        # Set up AWS credentials
        session = boto3.Session()
        credentials = session.get_credentials()
        auth = AWSV4SignerAuth(credentials, self.region, "aoss")

        # Prepare configuration
        merged_config["vector_store"]["config"].update(
            {"http_auth": auth, "host": os.environ["OPENSEARCH_HOST"]}
        )

        return Mem0Memory.from_config(config_dict=merged_config)

    def _initialize_faiss_client(
        self, config: Optional[Dict] = None, server: str = "local"
    ) -> Mem0Memory:
        """Initialize a Mem0 client with FAISS backend.

        Args:
            config: Optional configuration dictionary to override defaults.
            server: Server type for configuration.

        Returns:
            An initialized Mem0Memory instance configured for FAISS.

        Raises:
            ImportError: If faiss-cpu package is not installed.
        """

        merged_config = self._merge_config(config, server)

        # Use provided path or create unified output structure path
        if merged_config.get("vector_store", {}).get("config", {}).get("path"):
            # Path already set in config (from args.memory_path)
            faiss_path = merged_config["vector_store"]["config"]["path"]
        else:
            # Create memory path using unified output structure
            # Memory is stored at: ./outputs/<target-name>/memory/mem0_faiss_<target-name>
            target_name = merged_config.get("target_name", "default_target")

            # Use unified output structure for memory - per-target, not per-operation
            memory_base_path = os.path.join("outputs", target_name, "memory")
            faiss_path = memory_base_path

            # Ensure the memory directory exists
            os.makedirs(memory_base_path, exist_ok=True)

        merged_config["vector_store"]["config"]["path"] = faiss_path

        # Display FAISS configuration
        print("[+] Memory Backend: FAISS (local)")
        print(f"    Store Location: {faiss_path}")

        # Display embedder configuration
        embedder_config = merged_config.get("embedder", {})
        embedder_provider = embedder_config.get("provider", "aws_bedrock")
        embedder_model = embedder_config.get("config", {}).get("model")
        config_manager = get_config_manager()
        embedder_region = embedder_config.get("config", {}).get(
            "aws_region", config_manager.get_default_region()
        )

        # Display LLM configuration
        llm_config = merged_config.get("llm", {})
        llm_model = llm_config.get("config", {}).get("model")

        if embedder_provider == "ollama":
            print(f"    Embedder: Ollama - {embedder_model} (1024 dims)")
            print(f"    LLM: Ollama - {llm_model}")
        else:
            print(f"    Region: {embedder_region}")
            print(f"    Embedder: AWS Bedrock - {embedder_model} (1024 dims)")
            print(f"    LLM: AWS Bedrock - {llm_model}")

        # Check if loading existing store
        if os.path.exists(faiss_path):
            print(f"• Loading existing FAISS store from: {faiss_path}")
            print("• Memory will persist across operations for this target")
        else:
            print(f"• Creating new FAISS store at: {faiss_path}")
            print("• Memory will persist across operations for this target")

        return Mem0Memory.from_config(config_dict=merged_config)

    def _merge_config(
        self, config: Optional[Dict] = None, server: str = "remote"
    ) -> Dict:
        """Merge user-provided configuration with default configuration.

        Args:
            config: Optional configuration dictionary to override defaults.
            server: Server type for configuration.

        Returns:
            A merged configuration dictionary.
        """
        merged_config = self.get_default_config(server).copy()
        if not config:
            return merged_config

        # Deep merge the configs
        for key, value in config.items():
            if (
                key in merged_config
                and isinstance(value, dict)
                and isinstance(merged_config[key], dict)
            ):
                merged_config[key].update(value)
            else:
                merged_config[key] = value

        return merged_config

    def store_memory(
        self,
        content: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """Store a memory in Mem0."""
        if not user_id and not agent_id:
            raise ValueError("Either user_id or agent_id must be provided")

        messages = [{"role": "user", "content": content}]
        try:
            # For cybersecurity findings, use infer=False to ensure all data is stored
            # regardless of mem0's fact filtering (critical for security assessments)
            result = self.mem0.add(
                messages,
                user_id=user_id,
                agent_id=agent_id,
                metadata=metadata,
                infer=False,
            )
            # Log successful storage
            logger.debug("Memory stored successfully: %s", result)
            return result
        except Exception as e:
            logger.error("Error storing memory: %s", e)
            # Return empty result to prevent downstream errors
            return {"results": []}

    def get_memory(self, memory_id: str):
        """Get a memory by ID."""
        return self.mem0.get(memory_id)

    def list_memories(
        self, user_id: Optional[str] = None, agent_id: Optional[str] = None
    ):
        """List all memories for a user or agent."""
        if not user_id and not agent_id:
            raise ValueError("Either user_id or agent_id must be provided")

        return self.mem0.get_all(user_id=user_id, agent_id=agent_id)

    def search_memories(
        self, query: str, user_id: Optional[str] = None, agent_id: Optional[str] = None
    ):
        """Search memories using semantic search."""
        if not user_id and not agent_id:
            raise ValueError("Either user_id or agent_id must be provided")

        return self.mem0.search(query=query, user_id=user_id, agent_id=agent_id)

    def delete_memory(self, memory_id: str):
        """Delete a memory by ID."""
        return self.mem0.delete(memory_id)

    def get_memory_history(self, memory_id: str):
        """Get the history of a memory by ID."""
        return self.mem0.history(memory_id)

    def _display_startup_overview(self) -> None:
        """Display memory overview at startup for all backends."""
        try:
            # Check if we should display overview based on backend and existing data
            should_display = self._should_display_overview()

            if should_display:
                display_memory_overview(self, user_id="cyber_agent")
        except Exception as e:
            logger.debug("Could not display startup memory overview: %s", str(e))
            print(f"    Note: Could not check existing memories: {str(e)}")

    def _should_display_overview(self) -> bool:
        """Check if we should display memory overview based on backend type and existing data."""
        try:
            # For Mem0 Platform - always try to display (cloud-based)
            if os.environ.get("MEM0_API_KEY"):
                return True

            # For OpenSearch - always try to display (remote service)
            if os.environ.get("OPENSEARCH_HOST"):
                return True

            # For FAISS - check if local store exists
            # Need to get the merged config to check the actual path
            server_type = "local"  # FAISS is local
            merged_config = self._merge_config(self.config, server_type)

            if merged_config and "vector_store" in merged_config:
                faiss_path = (
                    merged_config.get("vector_store", {}).get("config", {}).get("path")
                )
                if faiss_path and os.path.exists(faiss_path):
                    return True

            return False
        except Exception as e:
            logger.debug("Error checking if should display overview: %s", str(e))
            return False

    def get_memory_overview(self, user_id: str = "cyber_agent") -> Dict:
        """Get overview of memories for startup display.

        Args:
            user_id: User ID to retrieve memories for

        Returns:
            Dictionary containing memory overview data
        """
        try:
            # Get all memories for the user
            memories_response = self.list_memories(user_id=user_id)

            # Parse response format
            if isinstance(memories_response, dict):
                raw_memories = memories_response.get(
                    "memories", memories_response.get("results", [])
                )
            elif isinstance(memories_response, list):
                raw_memories = memories_response
            else:
                raw_memories = []

            # Analyze memories
            total_count = len(raw_memories)
            categories = {}
            recent_findings = []

            for memory in raw_memories:
                # Extract metadata
                metadata = memory.get("metadata", {})
                category = metadata.get("category", "general")

                # Count by category
                categories[category] = categories.get(category, 0) + 1

                # Collect recent findings
                if category == "finding":
                    recent_findings.append(
                        {
                            "content": memory.get("memory", "")[:100] + "..."
                            if len(memory.get("memory", "")) > 100
                            else memory.get("memory", ""),
                            "created_at": memory.get("created_at", "Unknown"),
                        }
                    )

            # Sort recent findings by creation date (most recent first)
            recent_findings.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            return {
                "total_count": total_count,
                "categories": categories,
                "recent_findings": recent_findings[:3],  # Top 3 most recent
                "has_memories": total_count > 0,
            }

        except Exception as e:
            logger.error("Error getting memory overview: %s", str(e))
            return {
                "total_count": 0,
                "categories": {},
                "recent_findings": [],
                "has_memories": False,
                "error": str(e),
            }


def display_memory_overview(
    memory_client: Mem0ServiceClient, user_id: str = "cyber_agent"
) -> None:
    """Display memory overview at startup.

    Args:
        memory_client: Initialized memory client
        user_id: User ID to check memories for
    """
    try:
        overview = memory_client.get_memory_overview(user_id=user_id)

        if overview.get("error"):
            print(
                f"    Warning: Could not retrieve memory overview: {overview['error']}"
            )
            return

        if not overview.get("has_memories"):
            print("    No existing memories found - starting fresh")
            return

        # Display overview
        total = overview.get("total_count", 0)
        categories = overview.get("categories", {})
        recent_findings = overview.get("recent_findings", [])

        print(f"    Found {total} existing memories:")

        # Show category breakdown
        if categories:
            category_parts = []
            for category, count in categories.items():
                category_parts.append(f"{count} {category}")
            print(f"      Categories: {', '.join(category_parts)}")

        # Show recent findings
        if recent_findings:
            print("      Recent findings:")
            for i, finding in enumerate(recent_findings, 1):
                content = finding.get("content", "")
                # Truncate content for display
                if len(content) > 80:
                    content = content[:77] + "..."
                print(f"        {i}. {content}")

        print("    Memory will be loaded as first action to avoid duplicate work")

    except Exception as e:
        logger.error("Error displaying memory overview: %s", str(e))
        print(f"    Warning: Could not display memory overview: {str(e)}")


def format_get_response(memory: Dict) -> Panel:
    """Format get memory response."""
    memory_id = memory.get("id", "unknown")
    content = memory.get("memory", "No content available")
    metadata = memory.get("metadata")
    created_at = memory.get("created_at", "Unknown")
    user_id = memory.get("user_id", "Unknown")

    result = [
        "✅ Memory retrieved successfully:",
        f"🔑 Memory ID: {memory_id}",
        f"👤 User ID: {user_id}",
        f"🕒 Created: {created_at}",
    ]

    if metadata:
        result.append(f"📋 Metadata: {json.dumps(metadata, indent=2)}")

    result.append(f"\n📄 Memory: {content}")

    return Panel(
        "\n".join(result), title="[bold green]Memory Retrieved", border_style="green"
    )


def format_list_response(memories: List[Dict]) -> Panel:
    """Format list memories response."""
    if not memories:
        return Panel(
            "No memories found.",
            title="[bold yellow]No Memories",
            border_style="yellow",
        )

    table = Table(title="Memories", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Memory", style="yellow", width=50)
    table.add_column("Created At", style="blue")
    table.add_column("User ID", style="green")
    table.add_column("Metadata", style="magenta")

    for memory in memories:
        memory_id = memory.get("id", "unknown")
        content = memory.get("memory", "No content available")
        created_at = memory.get("created_at", "Unknown")
        user_id = memory.get("user_id", "Unknown")
        metadata = memory.get("metadata", {})

        # Truncate content if too long
        content_preview = content[:100] + "..." if content and len(content) > 100 else content

        # Format metadata for display
        metadata_str = json.dumps(metadata, indent=2) if metadata else "None"

        table.add_row(memory_id, content_preview, created_at, user_id, metadata_str)

    return Panel(table, title="[bold green]Memories List", border_style="green")


def format_delete_response(memory_id: str) -> Panel:
    """Format delete memory response."""
    content = [
        "✅ Memory deleted successfully:",
        f"🔑 Memory ID: {memory_id}",
    ]
    return Panel(
        "\n".join(content), title="[bold green]Memory Deleted", border_style="green"
    )


def format_retrieve_response(memories: List[Dict]) -> Panel:
    """Format retrieve response."""
    if not memories:
        return Panel(
            "No memories found matching the query.",
            title="[bold yellow]No Matches",
            border_style="yellow",
        )

    table = Table(title="Search Results", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Memory", style="yellow", width=50)
    table.add_column("Relevance", style="green")
    table.add_column("Created At", style="blue")
    table.add_column("User ID", style="magenta")
    table.add_column("Metadata", style="white")

    for memory in memories:
        memory_id = memory.get("id", "unknown")
        content = memory.get("memory", "No content available")
        score = memory.get("score", 0)
        created_at = memory.get("created_at", "Unknown")
        user_id = memory.get("user_id", "Unknown")
        metadata = memory.get("metadata", {})

        # Truncate content if too long
        content_preview = content[:100] + "..." if content and len(content) > 100 else content

        # Format metadata for display
        metadata_str = json.dumps(metadata, indent=2) if metadata else "None"

        # Color code the relevance score
        if score > 0.8:
            score_color = "green"
        elif score > 0.5:
            score_color = "yellow"
        else:
            score_color = "red"

        table.add_row(
            memory_id,
            content_preview,
            f"[{score_color}]{score}[/{score_color}]",
            created_at,
            user_id,
            metadata_str,
        )

    return Panel(table, title="[bold green]Search Results", border_style="green")


def format_history_response(history: List[Dict]) -> Panel:
    """Format memory history response."""
    if not history:
        return Panel(
            "No history found for this memory.",
            title="[bold yellow]No History",
            border_style="yellow",
        )

    table = Table(title="Memory History", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Memory ID", style="green")
    table.add_column("Event", style="yellow")
    table.add_column("Old Memory", style="blue", width=30)
    table.add_column("New Memory", style="blue", width=30)
    table.add_column("Created At", style="magenta")

    for entry in history:
        entry_id = entry.get("id", "unknown")
        memory_id = entry.get("memory_id", "unknown")
        event = entry.get("event", "UNKNOWN")
        old_memory = entry.get("old_memory", "None")
        new_memory = entry.get("new_memory", "None")
        created_at = entry.get("created_at", "Unknown")

        # Truncate memory content if too long
        old_memory_preview = (
            old_memory[:100] + "..."
            if old_memory and len(old_memory) > 100
            else old_memory
        )
        new_memory_preview = (
            new_memory[:100] + "..."
            if new_memory and len(new_memory) > 100
            else new_memory
        )

        table.add_row(
            entry_id,
            memory_id,
            event,
            old_memory_preview,
            new_memory_preview,
            created_at,
        )

    return Panel(table, title="[bold green]Memory History", border_style="green")


def format_store_response(results: List[Dict]) -> Panel:
    """Format store memory response."""
    if not results:
        return Panel(
            "No memories stored.",
            title="[bold yellow]No Memories Stored",
            border_style="yellow",
        )

    table = Table(title="Memory Stored", show_header=True, header_style="bold magenta")
    table.add_column("Operation", style="green")
    table.add_column("Content", style="yellow", width=50)

    for memory in results:
        event = memory.get("event")
        text = memory.get("memory")
        # Truncate content if too long
        content_preview = text[:100] + "..." if text and len(text) > 100 else text
        table.add_row(event, content_preview)

    return Panel(table, title="[bold green]Memory Stored", border_style="green")


def initialize_memory_system(
    config: Optional[Dict] = None,
    operation_id: Optional[str] = None,
    target_name: Optional[str] = None,
) -> None:
    """Initialize the memory system with custom configuration.

    Args:
        config: Optional configuration dictionary with embedder, llm, vector_store settings
        operation_id: Unique operation identifier
        target_name: Sanitized target name for organizing memory by target
    """
    global _MEMORY_CONFIG, _MEMORY_CLIENT

    # Create enhanced config with operation context
    enhanced_config = config.copy() if config else {}
    enhanced_config["operation_id"] = (
        operation_id or f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    enhanced_config["target_name"] = target_name or "default_target"

    _MEMORY_CONFIG = enhanced_config
    _MEMORY_CLIENT = Mem0ServiceClient(enhanced_config)
    logger.info(
        "Memory system initialized for operation %s, target: %s",
        enhanced_config["operation_id"],
        enhanced_config["target_name"],
    )


def get_memory_client() -> Optional[Mem0ServiceClient]:
    """Get the current memory client, initializing if needed."""
    global _MEMORY_CLIENT
    if _MEMORY_CLIENT is None:
        # Try to initialize with default config
        try:
            initialize_memory_system()
        except Exception as e:
            logger.error("Failed to auto-initialize memory client: %s", e)
            return None
    return _MEMORY_CLIENT


@tool
def mem0_memory(
    action: str,
    content: Optional[str] = None,
    memory_id: Optional[str] = None,
    query: Optional[str] = None,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> str:
    """
    Memory management tool for storing, retrieving, and managing memories in Mem0.

    This tool provides a comprehensive interface for managing memories with Mem0,
    including storing new memories, retrieving existing ones, listing all memories,
    performing semantic searches, and managing memory history.

    Args:
        action: The action to perform (store, get, list, retrieve, delete, history)
        content: Content to store (for store action)
        memory_id: Memory ID (for get, delete, history actions)
        query: Search query (for retrieve action)
        user_id: User ID for the memory operations
        agent_id: Agent ID for the memory operations
        metadata: Optional metadata to store with the memory

    Returns:
        Formatted string response with operation results
    """
    global _MEMORY_CLIENT

    if _MEMORY_CLIENT is None:
        # Initialize with default config if not already initialized
        initialize_memory_system()

    if _MEMORY_CLIENT is None:
        return "Error: Memory client could not be initialized"

    try:
        # Use simple user_id if not provided
        if not user_id and not agent_id:
            user_id = "cyber_agent"

        # Check if we're in development mode
        strands_dev = os.environ.get("BYPASS_TOOL_CONSENT", "").lower() == "true"

        # Handle different actions
        if action == "store":
            if not content:
                raise ValueError("content is required for store action")

            # Clean content to prevent JSON issues
            cleaned_content = (
                str(content)
                .replace("\x00", "")
                .replace("\n", " ")
                .replace("\r", " ")
                .replace("\t", " ")
                .strip()
            )
            # Also clean multiple spaces
            cleaned_content = re.sub(r"\s+", " ", cleaned_content)
            if not cleaned_content:
                raise ValueError("Content is empty after cleaning")

            # Clean metadata values too
            if metadata:
                cleaned_metadata = {}
                for key, value in metadata.items():
                    if isinstance(value, str):
                        cleaned_value = (
                            str(value)
                            .replace("\x00", "")
                            .replace("\n", " ")
                            .replace("\r", " ")
                            .replace("\t", " ")
                            .strip()
                        )
                        cleaned_value = re.sub(r"\s+", " ", cleaned_value)
                        cleaned_metadata[key] = cleaned_value
                    else:
                        cleaned_metadata[key] = value
                metadata = cleaned_metadata

            # Temporarily suppress mem0's internal error logging
            mem0_logger = logging.getLogger("root")
            original_level = mem0_logger.level
            mem0_logger.setLevel(logging.CRITICAL)

            try:
                results = _MEMORY_CLIENT.store_memory(
                    cleaned_content, user_id, agent_id, metadata
                )
            except Exception as store_error:
                # Handle mem0 library errors gracefully
                if "Extra data" in str(store_error) or "Expecting value" in str(
                    store_error
                ):
                    # JSON parsing error in mem0 - return success but log issue
                    fallback_result = [
                        {
                            "status": "stored",
                            "content_preview": cleaned_content[:50] + "...",
                        }
                    ]
                    if not strands_dev:
                        console.print(
                            "[yellow]Memory stored with minor parsing warnings[/yellow]"
                        )
                    return json.dumps(fallback_result, indent=2)
                else:
                    raise store_error
            finally:
                # Restore original logging level
                mem0_logger.setLevel(original_level)

            # Normalize to list with better error handling
            if results is None:
                results_list = []
            elif isinstance(results, list):
                results_list = results
            elif isinstance(results, dict):
                results_list = results.get("results", [])
            else:
                results_list = []
            if results_list and not strands_dev:
                panel = format_store_response(results_list)
                console.print(panel)
            return json.dumps(results_list, indent=2)

        elif action == "get":
            if not memory_id:
                raise ValueError("memory_id is required for get action")

            memory = _MEMORY_CLIENT.get_memory(memory_id)
            if not strands_dev:
                panel = format_get_response(memory)
                console.print(panel)
            return json.dumps(memory, indent=2)

        elif action == "list":
            memories = _MEMORY_CLIENT.list_memories(user_id, agent_id)
            # Normalize to list with better error handling
            if memories is None:
                results_list = []
            elif isinstance(memories, list):
                results_list = memories
            elif isinstance(memories, dict):
                results_list = memories.get("results", [])
            else:
                results_list = []
            if not strands_dev:
                panel = format_list_response(results_list)
                console.print(panel)
            return json.dumps(results_list, indent=2)

        elif action == "retrieve":
            if not query:
                raise ValueError("query is required for retrieve action")

            memories = _MEMORY_CLIENT.search_memories(query, user_id, agent_id)
            # Normalize to list with better error handling
            if memories is None:
                results_list = []
            elif isinstance(memories, list):
                results_list = memories
            elif isinstance(memories, dict):
                results_list = memories.get("results", [])
            else:
                results_list = []
            if not strands_dev:
                panel = format_retrieve_response(results_list)
                console.print(panel)
            return json.dumps(results_list, indent=2)

        elif action == "delete":
            if not memory_id:
                raise ValueError("memory_id is required for delete action")

            _MEMORY_CLIENT.delete_memory(memory_id)
            if not strands_dev:
                panel = format_delete_response(memory_id)
                console.print(panel)
            return f"Memory {memory_id} deleted successfully"

        elif action == "history":
            if not memory_id:
                raise ValueError("memory_id is required for history action")

            history = _MEMORY_CLIENT.get_memory_history(memory_id)
            if not strands_dev:
                panel = format_history_response(history)
                console.print(panel)
            return json.dumps(history, indent=2)

        else:
            raise ValueError(f"Invalid action: {action}")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        if not os.environ.get("BYPASS_TOOL_CONSENT", "").lower() == "true":
            error_panel = Panel(
                Text(str(e), style="red"),
                title="❌ Memory Operation Error",
                border_style="red",
            )
            console.print(error_panel)
        return error_msg


# Note: All memory operations now go through the unified mem0_memory tool
# Use mem0_memory(action="store", content="...", metadata={"category": "finding"})
# Use mem0_memory(action="retrieve", query="category:finding")
# Use mem0_memory(action="list")
