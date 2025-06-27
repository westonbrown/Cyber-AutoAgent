#!/usr/bin/env python3

import warnings
from datetime import datetime
from typing import Optional, Dict

from strands import tool
from .utils import Colors

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Constants for memory operations
MEMORY_CONTENT_PREVIEW_LENGTH = 100
SEARCH_RESULT_PREVIEW_LENGTH = 80
EVIDENCE_SUMMARY_PREVIEW_LENGTH = 80
MAX_EVIDENCE_DISPLAY = 10

# Global variables for evidence storage
mem0_instance = None
operation_id = None


@tool
def memory_store(
    content: str, category: str = "general", metadata: Optional[Dict] = None
) -> str:
    """Store findings and track patterns in your security assessment.

    Use this tool to document discoveries and track patterns in your testing.
    This helps you learn from attempts and recognize when to change approaches.

    Args:
        content: The finding, attempt, or insight to store
        category: Category - vulnerability, credential, finding, access, enumeration, plan, reflection
        metadata: Optional context that helps you work efficiently. Consider:
                  - patterns you're noticing in your testing
                  - why this finding matters to your objective
                  - what you learned that changes your strategy

    Returns:
        str: Success message with memory ID and preview

    Example:
        memory_store("Tested 5 XSS payloads, all filtered by input validation", "finding",
                    {"pattern": "repetitive_testing", "attempts": 5, "next_approach": "try_different_context"})
    """
    global mem0_instance, operation_id
    if mem0_instance is None:
        return "Error: Memory system not initialized"

    try:
        # Validate inputs
        if not content or not isinstance(content, str):
            return "Error: Content must be a non-empty string"

        valid_categories = [
            "vulnerability",
            "credential",
            "finding",
            "access",
            "enumeration",
            "general",
            "plan",
            "reflection",
        ]
        if category not in valid_categories:
            return f"Error: Invalid category '{category}'. Use: {', '.join(valid_categories)}"

        # Prepare metadata
        if metadata is None:
            metadata = {}
        metadata.update(
            {
                "category": category,
                "timestamp": datetime.now().isoformat(),
                "operation_id": operation_id or "unknown",
            }
        )

        # Store in memory
        result = mem0_instance.add(
            content, user_id="cyber_agent", metadata=metadata, infer=False
        )

        # Extract memory ID with proper error handling
        memory_id = "unknown"
        if isinstance(result, dict) and "results" in result and result["results"]:
            memory_id = result["results"][0].get("id", "unknown")
        elif isinstance(result, list) and result:
            memory_id = result[0].get("id", "unknown")
        elif isinstance(result, dict):
            memory_id = result.get("id", "unknown")

        preview = (
            content[:MEMORY_CONTENT_PREVIEW_LENGTH] + "..."
            if len(content) > MEMORY_CONTENT_PREVIEW_LENGTH
            else content
        )
        return f"✓ Memory stored [{category}]: {preview} (ID: {memory_id[:8]}...)"

    except ValueError as ve:
        return f"Invalid input: {ve}"
    except Exception as e:
        # Log error for debugging but return user-friendly message
        import logging

        logging.getLogger(__name__).error("Memory storage failed: %s", e, exc_info=True)
        return "Memory storage failed. Please check logs for details."


@tool
def memory_retrieve(query: str, category: Optional[str] = None, limit: int = 10) -> str:
    """Search your stored findings and patterns.

    Use this to learn from previous attempts and identify patterns in your testing.
    Particularly useful for recognizing when you're repeating approaches that haven't worked.

    Args:
        query: Search for related findings, attempts, or patterns
        category: Optional category filter (vulnerability, credential, etc.)
        limit: Maximum number of results (default: 10)

    Returns:
        str: Formatted search results
    """
    global mem0_instance
    if mem0_instance is None:
        return "Error: Memory system not initialized"

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
            filters=filters if filters else None,
        )

        if not results:
            return f"No matches found for query: {query}"

        # Format results
        output = [f"Found {len(results)} matches for '{query}':"]
        for i, r in enumerate(results, 1):
            content = r.get("memory", "")
            category = r.get("metadata", {}).get("category", "unknown")
            preview = (
                content[:SEARCH_RESULT_PREVIEW_LENGTH] + "..."
                if len(content) > SEARCH_RESULT_PREVIEW_LENGTH
                else content
            )
            output.append(f"  {i}. [{category}] {preview}")

        return "\n".join(output)

    except Exception as e:
        return f"Error searching memory: {str(e)}"


@tool
def memory_list(category: Optional[str] = None, limit: int = 50) -> dict:
    """List all stored evidence, optionally filtered by category.

    Use this tool to display a formatted summary of all collected evidence.
    Shows category breakdown and recent evidence with clean formatting.

    Args:
        category: Optional category filter ("vulnerability", "credential", "finding", etc.)
        limit: Maximum number of results to return (default: 50)

    Returns:
        Dict containing:
        - status: "success" or "error"
        - total_count: total number of evidence items
        - categories: breakdown by category with counts
        - evidence: list of evidence entries

    Note: This tool automatically displays a formatted summary to the user.

    Example:
        memory_list()  # Show all evidence
        memory_list(category="vulnerability")  # Show only vulnerabilities
    """
    global mem0_instance
    if mem0_instance is None:
        return {"error": "Memory system not initialized"}

    try:
        # Get all memories
        all_memories = mem0_instance.get_all(user_id="cyber_agent", limit=limit)

        # Handle different response formats from mem0 API
        if isinstance(all_memories, dict):
            # Extract memories from standard response formats
            all_memories = all_memories.get("memories", all_memories.get("results", []))
        elif not isinstance(all_memories, list):
            # Fallback for unexpected format
            all_memories = []

        # Filter by category if specified
        evidence = []
        for m in all_memories:
            # Ensure m is a dict
            if not isinstance(m, dict):
                continue
            if category and m.get("metadata", {}).get("category") != category:
                continue
            evidence.append(
                {
                    "id": m.get("id"),
                    "content": m.get("memory"),
                    "category": m.get("metadata", {}).get("category", "unknown"),
                    "timestamp": m.get("metadata", {}).get("timestamp"),
                    "metadata": m.get("metadata", {}),
                }
            )
    except Exception as e:
        print(
            "%sWarning: Error retrieving memories: %s%s"
            % (Colors.YELLOW, str(e), Colors.RESET)
        )
        evidence = []

    # Group by category
    categories = {}
    for e in evidence:
        cat = e["category"]
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1

    # Clean evidence summary with break lines
    print("\n%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))
    print("📋 %s%sEvidence Summary%s" % (Colors.CYAN, Colors.BOLD, Colors.RESET))
    print("%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))

    # Show category breakdown
    if categories:
        print("\nCategories:")
        for cat, count in categories.items():
            print("   • %s: %d items" % (cat, count))

    # Show recent evidence with clean formatting
    if evidence:
        print("\nRecent Evidence:")
        for i, e in enumerate(evidence[:MAX_EVIDENCE_DISPLAY]):  # Show last 10
            preview = (
                e["content"][:EVIDENCE_SUMMARY_PREVIEW_LENGTH] + "..."
                if len(e["content"]) > EVIDENCE_SUMMARY_PREVIEW_LENGTH
                else e["content"]
            )
            print(
                "\n   [%d] %s%s%s" % (i + 1, Colors.GREEN, e["category"], Colors.RESET)
            )
            print("       %s%s%s" % (Colors.DIM, preview, Colors.RESET))
            print("       %sID: %s...%s" % (Colors.BLUE, e["id"][:8], Colors.RESET))

        if len(evidence) > MAX_EVIDENCE_DISPLAY:
            print(
                "\n   %s... and %d more items%s"
                % (Colors.DIM, len(evidence) - MAX_EVIDENCE_DISPLAY, Colors.RESET)
            )
    else:
        print("\n   %sNo evidence collected yet%s" % (Colors.DIM, Colors.RESET))

    print("\n%s%s%s" % (Colors.DIM, "─" * 80, Colors.RESET))

    return {
        "status": "success",
        "total_count": len(evidence),
        "categories": categories,
        "evidence": evidence,
    }
