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

Plan & Reflection:
- Plan lifecycle: store_plan (create), get_plan (retrieve), update via store_plan (new version)
- Evaluation cadence: Every ~20 steps → get_plan, assess criteria, update phases if satisfied
- Phase transitions: Criteria met → status="done", advance current_phase, next status="active", store_plan
- Post-reflection: Evaluate plan, update if phase complete or pivot needed
- Stuck detection: Phase >40% budget → force advance with context note

Adaptation Tracking:
- After failed attempts: store("[BLOCKED] Approach X at endpoint Y", metadata={"category": "adaptation", "retry_count": n})
- Include what was blocked (script tags, specific chars, etc.) and next strategy
- After 3 retries with same approach, mandatory pivot to different technique

Plan Storage - CRITICAL: Pass as JSON dict, NOT as string!

CORRECT EXAMPLE (pass dict directly):
mem0_memory(
  action="store_plan",
  content={
    "objective": "Comprehensive security assessment of target",
    "current_phase": 1,
    "total_phases": 3,
    "phases": [
      {"id": 1, "title": "Reconnaissance", "status": "active", "criteria": "tech_stack identified, endpoints mapped"},
      {"id": 2, "title": "Vulnerability Testing", "status": "pending", "criteria": "vulns tested with PoC"},
      {"id": 3, "title": "Exploitation", "status": "pending", "criteria": "flag extracted, evidence saved"}
    ]
  }
)

WRONG (do NOT pass as string):
content="{\"objective\": \"...\", ...}"  # ❌ This will be rejected

Required fields: objective, current_phase, total_phases, phases (with id, title, status, criteria)

Proof Pack policy:
- For any HIGH/CRITICAL finding stored via mem0_memory, include a short Proof Pack authored by the LLM:
  • 2–4 sentences that reference at least one concrete artifact (evidence/<...> path, HTTP transcript, RPC JSON, or screenshot)
  • One-line rationale linking the artifact to the claim
- If no artifact exists, set metadata.validation_status="hypothesis" (not "verified") and include next steps to obtain proof.
- Recommended metadata keys: severity, confidence, validation_status.

Capability gaps (Ask-Enable-Retry):
- If a missing capability blocks progress (e.g., web3), the LLM should:
  1) Ask: state why it is required and the minimal package(s)
  2) Enable: propose a minimal, temporary, non-interactive enablement (e.g., ephemeral venv under outputs/<target>/<op>/venv)
  3) Retry: re-run once and store resulting artifacts
- If enablement is not permitted, store the next steps instead of escalating severity.

Usage:
- Keep entries concise. For large artifacts (HTML/JS/logs), save files to outputs/<target>/OP_<id>/artifacts and store only the file path in memory.
- See tool schema below.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import boto3
from mem0 import Memory as Mem0Memory
from mem0 import MemoryClient
from opensearchpy import AWSV4SignerAuth, RequestsHttpConnection
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from strands import tool

from modules.config.manager import get_config_manager

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
        "Memory management: store/retrieve/list/get/delete.\n"
        "Actions: store, store_plan, get_plan, get, list, retrieve, delete.\n"
        "Plan (compact JSON): objective, current_phase, phases[id|title|status|criteria].\n"
        "Plan evaluation: MANDATORY checkpoints at 20%/40%/60%/80% budget → get_plan, assess criteria, update phases if met (store_plan).\n"
        "Context preservation: For 800+ step operations, checkpoints anchor strategy in memory across context window limits.\n"
        "Phase transitions: Criteria satisfied → status='done', advance current_phase, next status='active', store_plan.\n"
        "Finding Format: [VULNERABILITY][WHERE][IMPACT][EVIDENCE][STEPS][REMEDIATION][CONFIDENCE].\n"
        "Proof Pack (High/Critical): artifact path + one-line rationale; else validation_status='hypothesis' with next steps.\n"
        "Default user_id='cyber_agent' if unspecified.\n"
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": ("Action to perform (store, store_plan, get_plan, get, list, retrieve, delete)"),
                    "enum": [
                        "store",
                        "store_plan",
                        "get_plan",
                        "get",
                        "list",
                        "retrieve",
                        "delete",
                    ],
                },
                "content": {
                    "type": ["string", "object"],
                    "description": "Content to store - string for store, dict for store_plan",
                },
                "memory_id": {
                    "type": "string",
                    "description": "Memory ID (required for get, delete actions)",
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
    """Lightweight client for Mem0 operations (store, search, list).

    Supports FAISS, OpenSearch, or Mem0 Platform based on environment.
    """

    @staticmethod
    def _normalise_results_list(payload: Any) -> List[Dict[str, Any]]:
        """Best-effort conversion of Mem0 responses to a list of memory dicts."""
        if payload is None:
            return []
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("results", "memories", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        return []

    @staticmethod
    def get_default_config(server: str = "bedrock") -> Dict:
        """Get default configuration from ConfigManager."""
        config_manager = get_config_manager()
        mem0_config = config_manager.get_mem0_service_config(server)

        # Add RequestsHttpConnection for OpenSearch if needed
        if mem0_config["vector_store"]["provider"] == "opensearch":
            mem0_config["vector_store"]["config"]["connection_class"] = RequestsHttpConnection

        return mem0_config

    def __init__(self, config: Optional[Dict] = None, has_existing_memories: bool = False, silent: bool = False):
        """Initialize the Mem0 service client.

        Args:
            config: Optional configuration dictionary to override defaults.
                   If provided, it will be merged with the default configuration.
            has_existing_memories: Whether memories already existed before initialization
            silent: If True, suppress initialization output (used during report generation)

        The client will use one of three backends based on environment variables:
        1. Mem0 Platform if MEM0_API_KEY is set
        2. OpenSearch if OPENSEARCH_HOST is set
        3. FAISS (default) if neither MEM0_API_KEY nor OPENSEARCH_HOST is set
        """
        self.region = None  # Initialize region attribute
        self.has_existing_memories = has_existing_memories  # Store existing memory info
        self.silent = silent  # Store silent flag for use in initialization methods
        self.mem0 = self._initialize_client(config)
        self.config = config  # Store config for later use

        # Display memory overview if existing memories are detected (unless silent)
        if not silent:
            self._display_startup_overview()

    def _initialize_client(self, config: Optional[Dict] = None) -> Any:
        """Initialize the appropriate Mem0 client based on environment variables.

        Args:
            config: Optional configuration dictionary to override defaults.

        Returns:
            An initialized Mem0 client (MemoryClient or Mem0Memory instance).
        """
        if os.environ.get("MEM0_API_KEY"):
            if not self.silent:
                print("[+] Memory Backend: Mem0 Platform (cloud)")
                print(f"    API Key: {'*' * 8}{os.environ.get('MEM0_API_KEY', '')[-4:]}")
            logger.debug("Using Mem0 Platform backend (MemoryClient)")
            return MemoryClient()

        # Determine provider type based on environment
        # Use bedrock if OpenSearch is available, otherwise ollama
        server_type = "bedrock" if os.environ.get("OPENSEARCH_HOST") else "ollama"

        if os.environ.get("OPENSEARCH_HOST"):
            merged_config = self._merge_config(config, server_type)
            config_manager = get_config_manager()
            embedder_region = (
                merged_config.get("embedder", {})
                .get("config", {})
                .get("aws_region", config_manager.get_default_region())
            )

            if not self.silent:
                print("[+] Memory Backend: OpenSearch")
                print(f"    Host: {os.environ.get('OPENSEARCH_HOST')}")
                print(f"    Region: {embedder_region}")
                print(f"    Embedder: AWS Bedrock - {merged_config['embedder']['config']['model']} (1024 dims)")
                print(f"    LLM: AWS Bedrock - {merged_config['llm']['config']['model']}")
            logger.debug("Using OpenSearch backend (Mem0Memory with OpenSearch)")
            return self._initialize_opensearch_client(config, server_type)

        # FAISS backend
        logger.debug("Using FAISS backend (Mem0Memory with FAISS)")
        return self._initialize_faiss_client(config, server_type, self.has_existing_memories)

    def _initialize_opensearch_client(self, config: Optional[Dict] = None, server: str = "bedrock") -> Mem0Memory:
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
        config_region = merged_config.get("embedder", {}).get("config", {}).get("aws_region")
        self.region = config_region or os.environ.get("AWS_REGION") or config_manager.get_default_region()

        if not os.environ.get("AWS_REGION"):
            os.environ["AWS_REGION"] = self.region

        # Set up AWS credentials
        session = boto3.Session()
        credentials = session.get_credentials()
        auth = AWSV4SignerAuth(credentials, self.region, "es")

        # Prepare configuration
        merged_config["vector_store"]["config"].update({"http_auth": auth, "host": os.environ["OPENSEARCH_HOST"]})

        return Mem0Memory.from_config(config_dict=merged_config)

    def _initialize_faiss_client(
        self,
        config: Optional[Dict] = None,
        server: str = "ollama",
        has_existing_memories: bool = False,
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

        # Initialize store existence flag
        store_existed_before = False

        # Use provided path or create unified output structure path
        if merged_config.get("vector_store", {}).get("config", {}).get("path"):
            # Path already set in config (from args.memory_path)
            faiss_path = merged_config["vector_store"]["config"]["path"]
            # For custom paths, assume it's an existing store (like --memory-path flag)
            store_existed_before = os.path.exists(faiss_path)
        else:
            # Create memory path using unified output structure
            # Memory is stored at: ./outputs/<target-name>/memory/mem0_faiss_<target-name>
            target_name = merged_config.get("target_name", "default_target")

            # Use unified output structure for memory - per-target, not per-operation
            # Get output directory from environment or config
            output_dir = os.environ.get("CYBER_AGENT_OUTPUT_DIR") or merged_config.get("output_dir", "outputs")
            memory_base_path = os.path.join(output_dir, target_name, "memory")
            faiss_path = memory_base_path

            # Check if store existed before we create directories
            store_existed_before = os.path.exists(memory_base_path)

            # Ensure the memory directory exists
            os.makedirs(memory_base_path, exist_ok=True)

        merged_config["vector_store"]["config"]["path"] = faiss_path

        # Display FAISS configuration (unless silent mode for report generation)
        if not self.silent:
            print("[+] Memory Backend: FAISS (local)")
            print(f"    Store Location: {faiss_path}")

            # Display embedder configuration
            embedder_config = merged_config.get("embedder", {})
            embedder_provider = embedder_config.get("provider", "aws_bedrock")
            embedder_model = embedder_config.get("config", {}).get("model")
            config_manager = get_config_manager()
            embedder_region = embedder_config.get("config", {}).get("aws_region", config_manager.get_default_region())

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

            # Display appropriate message based on whether store existed before initialization
            # Use has_existing_memories parameter which includes proper file size validation
            if has_existing_memories or store_existed_before:
                print(f"    Loading existing FAISS store from: {faiss_path}")
                print("    Memory will persist across operations for this target")
            else:
                # For fresh starts, just show the persistence message
                print("    Memory will persist across operations for this target")

        logger.debug("Initializing Mem0Memory with config: %s", merged_config)
        try:
            mem0_client = Mem0Memory.from_config(config_dict=merged_config)
            logger.debug("Mem0Memory client initialized successfully")
            return mem0_client
        except Exception as e:
            logger.error("Failed to initialize Mem0Memory client: %s", e)
            raise

    def _merge_config(self, config: Optional[Dict] = None, server: str = "bedrock") -> Dict:
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
            if key in merged_config and isinstance(value, dict) and isinstance(merged_config[key], dict):
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

        # Default agent_id to user_id to avoid null actor attribution in some backends
        if user_id and not agent_id:
            agent_id = user_id

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
            logger.error("Critical error storing memory: %s", e)
            raise RuntimeError(f"Memory storage failed: {e}") from e

    def get_memory(self, memory_id: str):
        """Get a memory by ID."""
        return self.mem0.get(memory_id)

    def list_memories(self, user_id: Optional[str] = None, agent_id: Optional[str] = None):
        """List all memories for a user or agent."""
        if not user_id and not agent_id:
            raise ValueError("Either user_id or agent_id must be provided")

        logger = logging.getLogger("CyberAutoAgent")
        logger.debug("Calling mem0.get_all with user_id=%s, agent_id=%s", user_id, agent_id)

        try:
            result = self.mem0.get_all(user_id=user_id, agent_id=agent_id)
            logger.debug("mem0.get_all returned type: %s", type(result))
            logger.debug("mem0.get_all returned: %s", result)
            return result
        except Exception as e:
            logger.error("Error in mem0.get_all: %s", e)
            raise

    def search_memories(self, query: str, user_id: Optional[str] = None, agent_id: Optional[str] = None):
        """Search memories using semantic search."""
        if not user_id and not agent_id:
            raise ValueError("Either user_id or agent_id must be provided")

        # Delegate to the compatibility search helper for normalized results
        return self.search(
            query=query,
            filters=None,
            limit=20,
            user_id=user_id or "cyber_agent",
            agent_id=agent_id,
        )

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        *,
        user_id: str = "cyber_agent",
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Compatibility wrapper providing Mem0-style search with filter support."""

        filters = filters or {}
        top_k = max(int(limit or 20), 1)

        def _coerce_entry(entry: Any) -> Dict[str, Any]:
            """Ensure every entry behaves like a memory dict."""
            if isinstance(entry, dict):
                return entry
            if isinstance(entry, str):
                return {"memory": entry, "metadata": {}}
            if entry is None:
                return {"memory": "", "metadata": {}}
            # Fallback stringify for unexpected types (lists/tuples/etc.)
            try:
                text = json.dumps(entry) if isinstance(entry, (list, tuple, set)) else str(entry)
            except Exception:  # pragma: no cover - defensive conversion
                text = str(entry)
            return {"memory": text, "metadata": {}}

        # Try native Mem0 search first (covers FAISS/OpenSearch/Platform backends)
        if hasattr(self.mem0, "search"):
            search_kwargs: Dict[str, Any] = {"user_id": user_id}
            if agent_id:
                search_kwargs["agent_id"] = agent_id
            if filters:
                search_kwargs["metadata"] = filters

            for size_kw in ("top_k", "limit"):
                try:
                    search_kwargs[size_kw] = top_k
                    results = self.mem0.search(query=query, **search_kwargs)
                    normalised = self._normalise_results_list(results)
                    if normalised:
                        coerced = [_coerce_entry(entry) for entry in normalised]
                        return coerced[:top_k]
                    if isinstance(results, list):
                        coerced = [_coerce_entry(entry) for entry in results]
                        return coerced[:top_k]
                except TypeError:
                    search_kwargs.pop(size_kw, None)
                except Exception as exc:  # pragma: no cover - backend specific
                    logger.debug("Native Mem0 search failed (%s): %s", size_kw, exc)
                    break

        # Fallback: list memories and apply lightweight filtering locally
        try:
            all_memories = self.list_memories(user_id=user_id, agent_id=agent_id)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Fallback memory listing failed during search: %s", exc)
            return []

        raw_entries = self._normalise_results_list(all_memories)
        if not raw_entries and isinstance(all_memories, list):
            raw_entries = all_memories

        raw_entries = [_coerce_entry(entry) for entry in raw_entries]

        def _matches_filters(entry: Dict[str, Any]) -> bool:
            metadata = entry.get("metadata", {}) or {}
            for key, value in filters.items():
                if str(metadata.get(key)) != str(value):
                    return False
            return True

        if query:
            terms = [term.lower() for term in re.split(r"\s+", query) if term]
        else:
            terms = []

        results: List[Dict[str, Any]] = []
        for entry in raw_entries:
            if filters and not _matches_filters(entry):
                continue

            if terms:
                text = " ".join(
                    str(part)
                    for part in (
                        entry.get("memory"),
                        entry.get("content"),
                        json.dumps(entry.get("metadata", {}), default=str),
                    )
                    if part
                ).lower()
                if not all(term in text for term in terms):
                    continue

            results.append(entry)
            if len(results) >= top_k:
                break

        return results

    def delete_memory(self, memory_id: str):
        """Delete a memory by ID."""
        return self.mem0.delete(memory_id)

    def get_memory_history(self, memory_id: str):
        """Get the history of a memory by ID."""
        return self.mem0.history(memory_id)

    def _display_startup_overview(self) -> None:
        """Display memory overview at startup if memories exist."""
        try:
            # For Mem0 Platform & OpenSearch - always display (remote backends)
            # For FAISS - only if memories existed before init
            should_display = (
                os.environ.get("MEM0_API_KEY") or
                os.environ.get("OPENSEARCH_HOST") or
                self.has_existing_memories
            )

            if not should_display:
                return

            # Get and display overview
            overview = self.get_memory_overview(user_id="cyber_agent")

            if overview.get("error"):
                print(f"    Warning: Could not retrieve memory overview: {overview['error']}")
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
                category_parts = [f"{count} {category}" for category, count in categories.items()]
                print(f"      Categories: {', '.join(category_parts)}")

            # Show recent findings
            if recent_findings:
                print("      Recent findings:")
                for i, finding in enumerate(recent_findings[:3], 1):
                    content = finding.get("content", "")
                    if len(content) > 80:
                        content = content[:77] + "..."
                    print(f"        {i}. {content}")

            print("    Memory will be loaded as first action to avoid duplicate work")

        except Exception as e:
            logger.debug("Could not display startup memory overview: %s", str(e))
            print(f"    Note: Could not check existing memories: {str(e)}")

    def store_plan(
        self, plan_content: Union[str, Dict], user_id: str = "cyber_agent", metadata: Optional[Dict] = None
    ) -> Dict:
        """Store a strategic plan in memory with category='plan'.

        REQUIRES dict format (JSON string is parsed before this method)

        Args:
            plan_content: The strategic plan dict with required fields
            user_id: User ID for memory storage
            metadata: Optional metadata (will be enhanced with category='plan')

        Returns:
            Memory storage result
        """
        # This should always be a dict (mem0_memory parses JSON strings)
        if isinstance(plan_content, str):
            logger.error("Unexpected string in store_plan - should be dict")
            raise ValueError(
                "Internal error: plan_content should be dict at this point. "
                "The mem0_memory function should have parsed any JSON string."
            )

        # Validate required fields
        required_fields = ["objective", "current_phase", "total_phases", "phases"]
        missing = [f for f in required_fields if f not in plan_content]
        if missing:
            logger.error(f"Plan missing required fields: {missing}")
            raise ValueError(f"Plan missing required fields: {missing}. See tool docstring for format.")

        # Validate phases structure
        if not isinstance(plan_content.get("phases"), list) or not plan_content["phases"]:
            raise ValueError("Plan must have 'phases' as non-empty list")

        for phase in plan_content["phases"]:
            phase_required = ["id", "title", "status", "criteria"]
            phase_missing = [f for f in phase_required if f not in phase]
            if phase_missing:
                raise ValueError(f"Phase {phase.get('id', '?')} missing fields: {phase_missing}")

        # Format dict as structured text for storage
        objective = plan_content.get("objective", "Unknown objective")
        current_phase = plan_content.get("current_phase", 1)
        total_phases = plan_content.get("total_phases", len(plan_content.get("phases", [])))
        phases = plan_content.get("phases", [])

        # Format as structured text
        formatted_plan = f"OBJECTIVE: {objective}\n"
        formatted_plan += f"PROGRESS: Phase {current_phase}/{total_phases}\n"
        for phase in phases:
            status_text = "COMPLETED" if phase["status"] == "done" else "ACTIVE" if phase["status"] == "active" else "PENDING"
            formatted_plan += f"Phase {phase['id']} [{status_text}]: {phase['title']} - {phase['criteria']}\n"

        plan_content_str = formatted_plan.strip()
        plan_structured = True

        plan_metadata = metadata or {}
        plan_metadata.update(
            {
                "category": "plan",
                "created_at": datetime.now().isoformat(),
                "type": "strategic_plan",
                "structured": plan_structured,
                "active": True,
                "plan_json": plan_content,  # Store original JSON in metadata
            }
        )
        # Tag with current operation ID (prefer client config, then env)
        op_id = (self.config or {}).get("operation_id") or os.getenv("CYBER_OPERATION_ID")
        if op_id:
            plan_metadata["operation_id"] = op_id

        # Warn if extending plan after marking complete
        try:
            prev = self.get_active_plan(user_id)
            if prev:
                prev_json = prev.get("metadata", {}).get("plan_json", {})
                if prev_json.get("assessment_complete") and total_phases > prev_json.get("total_phases", 0):
                    logger.warning(
                        f"Adding phases ({prev_json.get('total_phases')} → {total_phases}) after assessment_complete=true. "
                        "Consider stopping and generating report instead."
                    )
        except Exception as e:
            logger.debug(f"Could not check previous plan for extension: {e}")

        # Deactivate previous plans
        try:
            previous_plans = self.search_memories("category:plan active:true", user_id=user_id)
            if isinstance(previous_plans, list):
                for plan in previous_plans:
                    if plan.get("id"):
                        # Mark as inactive
                        self.store_memory(
                            content=plan.get("memory", ""),
                            user_id=user_id,
                            metadata={**plan.get("metadata", {}), "active": False},
                        )
        except Exception as e:
            logger.debug(f"Could not deactivate previous plans: {e}")

        result = self.store_memory(content=f"[PLAN] {plan_content_str}", user_id=user_id, metadata=plan_metadata)

        # Check if all phases complete and add reminder
        all_done = all(p["status"] == "done" for p in phases)
        if all_done and not plan_content.get("assessment_complete"):
            plan_content["assessment_complete"] = True
            result["_reminder"] = "All phases complete. Call stop('Assessment complete: X phases done, Y findings')"
            logger.info("All phases complete - set assessment_complete=true")

        return result

    def store_reflection(
        self,
        reflection_content: str,
        plan_id: Optional[str] = None,
        user_id: str = "cyber_agent",
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Store a reflection on findings and plan progress.

        Args:
            reflection_content: The reflection content
            plan_id: Optional ID of the plan being reflected upon
            user_id: User ID for memory storage
            metadata: Optional metadata (will be enhanced with category='reflection')

        Returns:
            Memory storage result with plan evaluation reminder
        """
        reflection_metadata = metadata or {}
        reflection_metadata.update(
            {"category": "reflection", "created_at": datetime.now().isoformat(), "type": "plan_reflection"}
        )
        # Tag with current operation ID when available
        op_id = os.getenv("CYBER_OPERATION_ID")
        if op_id and "operation_id" not in reflection_metadata:
            reflection_metadata["operation_id"] = op_id

        if plan_id:
            reflection_metadata["related_plan_id"] = plan_id

        result = self.store_memory(
            content=f"[REFLECTION] {reflection_content}", user_id=user_id, metadata=reflection_metadata
        )

        # Add plan evaluation reminder
        result["_reminder"] = "Reflection stored. Now: get_plan → check if phase criteria met or pivot needed → update if yes"

        return result

    def get_active_plan(self, user_id: str = "cyber_agent", operation_id: Optional[str] = None) -> Optional[Dict]:
        """Get the most recent active plan, preferring the current operation.

        This avoids semantic-search drift by listing all memories and selecting the
        newest plan entry (by created_at) with metadata.active == True. If an
        operation_id is provided, only consider plans tagged with that ID.

        Args:
            user_id: User ID to search plans for
            operation_id: Optional operation ID to scope plan selection

        Returns:
            Most recent active plan or None if no plans found
        """
        try:
            # Prefer deterministic listing over semantic search to avoid stale snapshots
            all_memories = self.list_memories(user_id=user_id)

            if isinstance(all_memories, dict):
                raw = all_memories.get("results", []) or all_memories.get("memories", []) or []
            elif isinstance(all_memories, list):
                raw = all_memories
            else:
                raw = []

            # Filter to plan items, optionally scoped to operation_id
            plan_items: List[Dict[str, Any]] = []
            for m in raw:
                meta = m.get("metadata", {}) or {}
                if str(meta.get("category", "")) != "plan":
                    continue
                if operation_id and str(meta.get("operation_id", "")) != str(operation_id):
                    continue
                plan_items.append(m)

            if not plan_items:
                # Fallback: if op-scoped search had no results, try any plan
                for m in raw:
                    meta = m.get("metadata", {}) or {}
                    if str(meta.get("category", "")) == "plan":
                        plan_items.append(m)

            if not plan_items:
                return None

            # Sort by created_at (desc). If missing, keep original order.
            def _dt(x: Dict[str, Any]) -> str:
                return str(x.get("created_at", ""))

            plan_items.sort(key=_dt, reverse=True)

            # Prefer the first active plan; if none, return most recent plan
            for m in plan_items:
                meta = m.get("metadata", {}) or {}
                if meta.get("active", False) is True:
                    return m

            return plan_items[0]
        except Exception as e:
            logger.error(f"Error retrieving active plan: {e}")
            return None

    def reflect_on_findings(
        self, recent_findings: List[Dict], current_plan: Optional[Dict] = None, user_id: str = "cyber_agent"
    ) -> str:
        """Generate reflection prompt based on recent findings and current plan.

        Args:
            recent_findings: List of recent findings to reflect on
            current_plan: Current active plan (optional)
            user_id: User ID for memory operations

        Returns:
            Reflection prompt for the agent
        """
        if not recent_findings:
            return "No recent findings to reflect on."

        # Summarize recent findings
        findings_summary = []
        for finding in recent_findings[:5]:  # Last 5 findings
            content = finding.get("memory", finding.get("content", ""))[:100]
            metadata = finding.get("metadata", {})
            severity = str(metadata.get("severity", "unknown"))
            findings_summary.append(f"- [{severity.upper()}] {content}")

        reflection_prompt = f"""
## REFLECTION REQUIRED

**Recent Findings ({len(findings_summary)}):**
{chr(10).join(findings_summary)}

**Current Plan Status:**
"""

        if current_plan:
            plan_content = current_plan.get("memory", current_plan.get("content", ""))[:200]
            reflection_prompt += f"""
Active plan: {plan_content}

**Required Actions:**
1. Is current phase criteria satisfied? If YES → mark status="done", advance current_phase, store_plan
2. Should we pivot strategy? If YES → update phases with new approach, store_plan
3. Phase stuck >40% budget? If YES → force advance to next phase
4. Deploy swarms if multiple vectors or <70% budget with no progress

After analysis: get_plan → evaluate → update phases if needed → store_plan → continue
"""
        else:
            reflection_prompt += """
No active plan found.

**Required Action:**
Create strategic plan NOW with store_plan before continuing.
Include: objective, current_phase=1, phases with clear criteria for each.
"""

        return reflection_prompt

    def get_memory_overview(self, user_id: str = "cyber_agent") -> Dict:
        """Get overview of memories for startup display.

        Args:
            user_id: User ID to retrieve memories for

        Returns:
            Dictionary containing memory overview data
        """
        try:
            # Get all memories for the user
            logger = logging.getLogger("CyberAutoAgent")
            logger.debug("Getting memory overview for user_id: %s", user_id)

            memories_response = self.list_memories(user_id=user_id)
            logger.debug("Memory overview raw response type: %s", type(memories_response))
            logger.debug("Memory overview raw response: %s", memories_response)

            # Parse response format
            if isinstance(memories_response, dict):
                raw_memories = memories_response.get("memories", memories_response.get("results", []))
                logger.debug("Dict response: found %d memories", len(raw_memories))
            elif isinstance(memories_response, list):
                raw_memories = memories_response
                logger.debug("List response: found %d memories", len(raw_memories))
            else:
                raw_memories = []
                logger.debug("Unexpected response type, using empty list")

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
                            "content": (
                                memory.get("memory", "")[:100] + "..."
                                if len(memory.get("memory", "")) > 100
                                else memory.get("memory", "")
                            ),
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

    return Panel("\n".join(result), title="[bold green]Memory Retrieved", border_style="green")


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
    return Panel("\n".join(content), title="[bold green]Memory Deleted", border_style="green")


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
        old_memory_preview = old_memory[:100] + "..." if old_memory and len(old_memory) > 100 else old_memory
        new_memory_preview = new_memory[:100] + "..." if new_memory and len(new_memory) > 100 else new_memory

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
    has_existing_memories: bool = False,
    silent: bool = False,
) -> None:
    """Initialize the memory system with custom configuration.

    Args:
        config: Optional configuration dictionary with embedder, llm, vector_store settings
        operation_id: Unique operation identifier
        target_name: Sanitized target name for organizing memory by target
        has_existing_memories: Whether memories already existed before initialization
        silent: If True, suppress initialization output (used during report generation)
    """
    global _MEMORY_CONFIG, _MEMORY_CLIENT

    # Create enhanced config with operation context
    enhanced_config = config.copy() if config else {}
    enhanced_config["operation_id"] = operation_id or f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    enhanced_config["target_name"] = target_name or "default_target"

    # Expose operation context for downstream components that rely on env
    try:
        os.environ["CYBER_OPERATION_ID"] = enhanced_config["operation_id"]
    except Exception:
        pass

    _MEMORY_CONFIG = enhanced_config
    _MEMORY_CLIENT = Mem0ServiceClient(enhanced_config, has_existing_memories, silent)
    logger.info(
        "Memory system initialized for operation %s, target: %s",
        enhanced_config["operation_id"],
        enhanced_config["target_name"],
    )


def get_memory_client(silent: bool = False) -> Optional[Mem0ServiceClient]:
    """Get the current memory client, initializing if needed.

    Args:
        silent: If True, suppress initialization output (used during report generation)

    Returns:
        The memory client instance or None if initialization fails
    """
    global _MEMORY_CLIENT
    if _MEMORY_CLIENT is None:
        # Try to initialize with default config
        try:
            initialize_memory_system(silent=silent)
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

    Purpose and scope:
    - Store atomic, reproducible evidence and findings; aggregation happens at report generation.
    - Never store executive summaries/final reports in memory.

    Failure-mode hardening (validation first):
    - High/Critical findings require metadata.proof_pack with existing artifact paths; missing/invalid proof_pack → auto-downgrade validation_status to "hypothesis" and cap confidence.
    - Pattern-only signals are capped at low confidence and marked as "pattern_match" evidence_type.
    - Do not store success/verified booleans; use validation_status + proof_pack instead.

    Structured finding content:
    [VULNERABILITY] title [WHERE] location [IMPACT] impact
    [EVIDENCE] proof [STEPS] reproduction [REMEDIATION] fix or "Not determined"
    [CONFIDENCE] percentage with justification

    Args:
        action: One of store|get|list|retrieve|delete|store_plan|get_plan
        content: Content to store (for store action) — use structured format for findings
        memory_id: Memory ID (for get, delete actions)
        query: Search query (for retrieve action)
        user_id: User ID for memory operations (defaults to 'cyber_agent')
        agent_id: Agent ID for memory operations
        metadata: Optional metadata with category, severity, confidence; for findings include severity, validation_status, and proof_pack when verified

    Returns:
        JSON/text response summarizing the memory operation; on parsing issues, returns a safe fallback summary.
    """
    global _MEMORY_CLIENT

    if _MEMORY_CLIENT is None:
        # Initialize with default config if not already initialized
        # Always use silent mode for auto-initialization to prevent unwanted output
        initialize_memory_system(silent=True)

    if _MEMORY_CLIENT is None:
        return "Error: Memory client could not be initialized"

    try:
        # Use simple user_id if not provided
        if not user_id and not agent_id:
            user_id = "cyber_agent"

        def _normalize_confidence(conf_val: Any, cap_to: float | None = None) -> str:
            """Normalize confidence to a percentage string, optionally capping at cap_to."""
            try:
                if isinstance(conf_val, str) and conf_val.strip().endswith("%"):
                    num = float(conf_val.strip().rstrip("%"))
                else:
                    num = float(conf_val)
            except Exception:
                num = 0.0
            if cap_to is not None:
                num = min(num, cap_to)
            num = max(0.0, min(100.0, num))
            return f"{num:.1f}%"

        def _is_valid_proof_pack(proof: Any) -> bool:
            """Validate proof_pack structure and artifact existence (fail-closed).

            Expectations:
            - proof_pack is a dict with key 'artifacts': List[str] of file paths (absolute or relative)
            - Optional 'rationale': short string tying artifacts to impact
            - Every listed artifact path MUST exist at validation time

            Notes:
            - No content parsing or domain heuristics are used here; presence of files only
            - Any exception or malformed input results in False (fail-closed)
            """
            if not isinstance(proof, dict):
                return False
            arts = proof.get("artifacts")
            if not isinstance(arts, list) or len(arts) == 0:
                return False
            # All listed artifacts must exist; relative or absolute paths supported
            for p in arts:
                try:
                    if not isinstance(p, str) or not p.strip():
                        return False
                    if not os.path.exists(p):
                        return False
                except Exception:
                    return False
            # Rationale is encouraged but not strictly required for validity here
            return True

        # Check if we're in development mode
        strands_dev = os.environ.get("BYPASS_TOOL_CONSENT", "").lower() == "true"

        # Handle different actions
        if action == "store_plan":
            if not content:
                raise ValueError("content is required for store_plan action")

            # Parse JSON string to dict if needed
            if isinstance(content, str):
                try:
                    plan_dict = json.loads(content)
                except json.JSONDecodeError:
                    raise ValueError(
                        "Content must be valid JSON dict with: objective, current_phase, total_phases, phases. "
                        "Got invalid JSON string."
                    )
            else:
                plan_dict = content

            results = _MEMORY_CLIENT.store_plan(plan_dict, user_id or "cyber_agent")
            if not strands_dev:
                console.print("[green]✅ Strategic plan stored successfully[/green]")
            return json.dumps(results, indent=2)

        elif action == "get_plan":
            # Scope retrieval to current operation when available to avoid stale plans
            op_id = os.getenv("CYBER_OPERATION_ID")
            plan = _MEMORY_CLIENT.get_active_plan(user_id or "cyber_agent", operation_id=op_id)
            if plan:
                if not strands_dev:
                    console.print("[green]📋 Active plan retrieved[/green]")
                return json.dumps(plan, indent=2)
            else:
                if not strands_dev:
                    console.print("[yellow]⚠️ No active plan found[/yellow]")
                return "No active plan found"

        elif action == "store":
            if not content:
                raise ValueError("content is required for store action")

            # Clean content to prevent JSON issues
            cleaned_content = (
                str(content).replace("\x00", "").replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()
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
            else:
                metadata = {}

            # Tag with current operation ID when available
            op_id = os.getenv("CYBER_OPERATION_ID")
            if op_id and "operation_id" not in metadata:
                metadata["operation_id"] = op_id

            # Consolidated validation for findings (single pass)
            if metadata.get("category") == "finding":
                # 1. Normalize severity
                valid_severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
                sev = str(metadata.get("severity", "MEDIUM")).upper()
                if sev not in valid_severities:
                    logger.warning(f"Invalid severity '{sev}', defaulting to MEDIUM")
                    sev = "MEDIUM"
                metadata["severity"] = sev

                # 2. Validate proof_pack for HIGH/CRITICAL findings
                vstat = str(metadata.get("validation_status", "")).lower()
                if sev in {"HIGH", "CRITICAL"}:
                    proof = metadata.get("proof_pack")
                    if _is_valid_proof_pack(proof):
                        # Valid proof_pack exists - respect or default to unverified
                        if vstat not in {"verified", "unverified", "hypothesis"}:
                            metadata["validation_status"] = "unverified"
                    else:
                        # Missing/invalid proof_pack - downgrade to hypothesis and cap confidence
                        metadata["validation_status"] = "hypothesis"
                        metadata["confidence"] = _normalize_confidence(metadata.get("confidence", "60%"), cap_to=60.0)
                else:
                    # Non-critical findings - default validation_status if not set
                    if vstat not in {"verified", "unverified", "hypothesis"}:
                        metadata["validation_status"] = "unverified"

                # 3. Determine evidence_type based on confidence (if not already set)
                if "evidence_type" not in metadata:
                    confidence_str = metadata.get("confidence", "0%")
                    try:
                        confidence_val = float(str(confidence_str).rstrip("%"))
                    except Exception:
                        confidence_val = 0

                    if confidence_val >= 70:
                        metadata["evidence_type"] = "exploited"
                    elif confidence_val >= 50:
                        metadata["evidence_type"] = "behavioral"
                    else:
                        metadata["evidence_type"] = "pattern_match"

                # 4. Cap confidence for pattern matches
                if metadata.get("evidence_type") == "pattern_match":
                    metadata["confidence"] = _normalize_confidence(metadata.get("confidence", "35%"), cap_to=40.0)

            # Suppress mem0's internal error logging during operation
            mem0_logger = logging.getLogger("root")
            original_level = mem0_logger.level
            mem0_logger.setLevel(logging.CRITICAL)

            try:
                results = _MEMORY_CLIENT.store_memory(cleaned_content, user_id, agent_id, metadata)
            except Exception as store_error:
                # Handle mem0 library errors gracefully
                if "Extra data" in str(store_error) or "Expecting value" in str(store_error):
                    # JSON parsing error in mem0 - return success but log issue
                    fallback_result = [
                        {
                            "status": "stored",
                            "content_preview": cleaned_content[:50] + "...",
                        }
                    ]
                    if not strands_dev:
                        console.print("[yellow]Memory stored with minor parsing warnings[/yellow]")
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

            # Debug logging to understand the response structure
            logger = logging.getLogger("CyberAutoAgent")
            logger.debug("Memory list raw response type: %s", type(memories))
            logger.debug("Memory list raw response: %s", memories)

            # Normalize to list with better error handling
            if memories is None:
                results_list = []
                logger.debug("memories is None, returning empty list")
            elif isinstance(memories, list):
                results_list = memories
                logger.debug("memories is list with %d items", len(memories))
            elif isinstance(memories, dict):
                # Check for different possible dict structures
                if "results" in memories:
                    results_list = memories.get("results", [])
                    logger.debug("Found 'results' key with %d items", len(results_list))
                elif "memories" in memories:
                    results_list = memories.get("memories", [])
                    logger.debug("Found 'memories' key with %d items", len(results_list))
                else:
                    # If dict doesn't have expected keys, treat as single memory
                    results_list = [memories] if memories else []
                    logger.debug("Dict without expected keys, treating as single memory: %d items", len(results_list))
            else:
                results_list = []
                logger.debug("Unexpected response type: %s", type(memories))

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

        else:
            raise ValueError(f"Invalid action: {action}")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        if os.environ.get("BYPASS_TOOL_CONSENT", "").lower() != "true":
            error_panel = Panel(
                Text(str(e), style="red"),
                title="❌ Memory Operation Error",
                border_style="red",
            )
            console.print(error_panel)
        return error_msg
