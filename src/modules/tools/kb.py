#!/usr/bin/env python3
"""
Tool for retrieving domain knowledge from preloaded knowledge base.

This module provides read-only access to curated security domain knowledge
including CVEs, threat actors, TTPs, and payload patterns. Unlike operation
memory (dynamic, per-target evidence), this KB is static, cross-target reference
knowledge bundled with releases.

Key Features:
-----------
1. Offline Access:
   • Prebuilt embeddings and FAISS index
   • No runtime HTTP calls for knowledge retrieval
   • Deterministic results across operations

2. Domain Coverage:
   • CVE patterns and exploitation notes
   • Threat actor profiles and TTPs
   • Payload templates (XSS, SSTI, SQLi, etc.)
   • MITRE ATT&CK mapped techniques

3. Usage:
   • Semantic search via retrieve_kb(query, filters, max_results)
   • Optional filtering by domain, category, tags
   • Returns concise passages (200-400 tokens each)

4. Distinction from Operation Memory:
   • Operation Memory: Per-target, dynamic, written during ops
   • KB: Cross-target, static, read-only curated knowledge

Usage:
-----
- Query KB: retrieve_kb("blind XSS detection techniques")
- Filter by domain: retrieve_kb("SSTI Twig2 payloads", filters={"domain": "web"})
- Filter by tags: retrieve_kb("APT28 TTPs", filters={"tactic": "credential_access"})
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from strands import tool

logger = logging.getLogger(__name__)

# Global KB client
_KB_CLIENT = None


def _get_kb_config() -> Dict[str, Any]:
    """Get KB configuration from environment and config manager.

    Returns:
        Configuration dictionary with KB settings
    """
    from modules.config.manager import get_config_manager

    config_manager = get_config_manager()

    # Get base directory for KB data
    kb_base_dir = os.getenv("CYBER_KB_BASE_DIR", "data/kb")

    # Check if KB is enabled
    kb_enabled = os.getenv("CYBER_KB_ENABLED", "true").lower() == "true"

    # Get max results limit
    max_results = int(os.getenv("CYBER_KB_MAX_RESULTS", "3"))

    # Get KB version
    kb_version = os.getenv("CYBER_KB_VERSION", "v0.1.0")

    # Build paths
    content_dir = os.path.join(kb_base_dir, "content")
    index_path = os.path.join(kb_base_dir, "index", "embeddings.faiss")
    manifest_path = os.path.join(kb_base_dir, "manifest.json")

    return {
        "enabled": kb_enabled,
        "max_results": max_results,
        "version": kb_version,
        "base_dir": kb_base_dir,
        "content_dir": content_dir,
        "index_path": index_path,
        "manifest_path": manifest_path,
        "embedding_config": config_manager.get_embedding_config("bedrock"),
    }


class KnowledgeBaseClient:
    """Client for querying the preloaded knowledge base.

    Provides semantic search over curated security domain knowledge using
    FAISS for local vector similarity search. The KB is read-only and
    preloaded during initialization.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the KB client.

        Args:
            config: Optional configuration override
        """
        self.config = config or _get_kb_config()
        self.kb_data: List[Dict[str, Any]] = []
        self.faiss_index = None
        self.embedder = None

        # Load KB data and index
        self._load_kb()

    def _load_kb(self) -> None:
        """Load KB content and FAISS index from disk."""
        if not self.config["enabled"]:
            logger.info("KB disabled - skipping initialization")
            return

        # Check if KB directory exists
        if not os.path.exists(self.config["content_dir"]):
            logger.warning("KB content directory not found: %s", self.config["content_dir"])
            logger.info("KB will be initialized with empty data")
            return

        # Load content files
        content_dir = Path(self.config["content_dir"])
        for content_file in content_dir.glob("*.jsonl"):
            try:
                with open(content_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            entry = json.loads(line)
                            self.kb_data.append(entry)
            except Exception as e:
                logger.error("Error loading KB file %s: %s", content_file, e)

        logger.info("Loaded %d KB entries from %s", len(self.kb_data), content_dir)

        # Load FAISS index if it exists
        index_path = Path(self.config["index_path"])
        if index_path.exists():
            try:
                import faiss
                self.faiss_index = faiss.read_index(str(index_path))
                logger.info("Loaded FAISS index from %s", index_path)
            except Exception as e:
                logger.warning("Could not load FAISS index: %s", e)
                logger.info("Will use fallback text search")

    def retrieve(
        self,
        query: str,
        filters: Optional[Dict[str, str]] = None,
        max_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Retrieve KB entries matching the query.

        Args:
            query: Search query string
            filters: Optional filters (domain, category, tags, etc.)
            max_results: Maximum number of results to return

        Returns:
            List of matching KB entries
        """
        if not self.config["enabled"]:
            return []

        if not self.kb_data:
            logger.warning("KB is empty - no entries loaded")
            return []

        # Cap max_results to configured limit
        max_results = min(max_results, self.config["max_results"])

        # If FAISS index is available, use semantic search
        if self.faiss_index is not None:
            results = self._semantic_search(query, filters, max_results)
        else:
            # Fallback to text-based search
            results = self._text_search(query, filters, max_results)

        return results

    def _semantic_search(
        self,
        query: str,
        filters: Optional[Dict[str, str]],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Perform semantic search using FAISS index.

        Args:
            query: Search query string
            filters: Optional metadata filters
            max_results: Maximum results to return

        Returns:
            List of matching entries sorted by relevance
        """
        # TODO: Implement semantic search with embeddings
        # For now, fall back to text search
        logger.debug("Semantic search not yet implemented, using text search")
        return self._text_search(query, filters, max_results)

    def _text_search(
        self,
        query: str,
        filters: Optional[Dict[str, str]],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Perform text-based search over KB entries.

        Args:
            query: Search query string
            filters: Optional metadata filters
            max_results: Maximum results to return

        Returns:
            List of matching entries
        """
        query_lower = query.lower()
        matches = []

        for entry in self.kb_data:
            # Apply filters first
            if filters:
                match_filters = True
                for key, value in filters.items():
                    if key == "tags":
                        # Special handling for tags (list field)
                        entry_tags = entry.get("tags", [])
                        if value not in entry_tags:
                            match_filters = False
                            break
                    else:
                        # Other fields
                        if str(entry.get(key, "")).lower() != value.lower():
                            match_filters = False
                            break

                if not match_filters:
                    continue

            # Check if query matches content, tags, or category
            content = entry.get("content", "").lower()
            tags = " ".join(entry.get("tags", [])).lower()
            category = entry.get("category", "").lower()

            if (query_lower in content or
                query_lower in tags or
                query_lower in category):
                matches.append(entry)

            if len(matches) >= max_results:
                break

        return matches


def get_kb_client() -> Optional[KnowledgeBaseClient]:
    """Get or initialize the global KB client.

    Returns:
        KB client instance or None if disabled
    """
    global _KB_CLIENT

    if _KB_CLIENT is None:
        config = _get_kb_config()
        if config["enabled"]:
            _KB_CLIENT = KnowledgeBaseClient(config)

    return _KB_CLIENT


@tool
def retrieve_kb(
    query: str,
    filters: Optional[Dict[str, str]] = None,
    max_results: int = 3
) -> str:
    """
    Retrieve domain knowledge from preloaded knowledge base.

    Returns concise passages about CVEs, TTPs, payloads, or exploitation
    patterns. This KB is read-only, offline, and separate from operation
    memory.

    Examples:
        retrieve_kb("blind XSS detection techniques")
        retrieve_kb("SSTI Twig2 payloads", filters={"domain": "web"})
        retrieve_kb("APT28 TTPs", filters={"tactic": "credential_access"})

    Args:
        query: Search query for KB content
        filters: Optional filters (domain, category, cve, tactic, tags)
        max_results: Maximum results to return (default: 3, capped by config)

    Returns:
        JSON string with matching KB entries or error message
    """
    try:
        client = get_kb_client()

        if client is None:
            return json.dumps({
                "status": "disabled",
                "message": "Knowledge base is disabled. Enable with CYBER_KB_ENABLED=true"
            })

        # Retrieve matching entries
        results = client.retrieve(query, filters, max_results)

        if not results:
            return json.dumps({
                "status": "no_results",
                "message": f"No KB entries found matching query: {query}",
                "query": query,
                "filters": filters
            })

        # Format results
        formatted_results = []
        for entry in results:
            formatted_results.append({
                "id": entry.get("id", "unknown"),
                "domain": entry.get("domain", "general"),
                "category": entry.get("category", "unknown"),
                "content": entry.get("content", ""),
                "tags": entry.get("tags", []),
                "source": entry.get("source", "")
            })

        return json.dumps({
            "status": "success",
            "count": len(formatted_results),
            "query": query,
            "filters": filters,
            "results": formatted_results
        }, indent=2)

    except Exception as e:
        error_msg = f"KB retrieval error: {str(e)}"
        logger.error(error_msg)
        return json.dumps({
            "status": "error",
            "message": error_msg
        })
