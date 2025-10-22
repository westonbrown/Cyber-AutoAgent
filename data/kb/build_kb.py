#!/usr/bin/env python3
"""
Knowledge Base Index Builder

Generates FAISS vector index from KB content files for semantic search.
Uses the same embedding model as configured for the main system.

Usage:
    python data/kb/build_kb.py

Requirements:
    - KB content files in data/kb/content/*.jsonl
    - AWS credentials configured (for Bedrock embeddings)
    - faiss-cpu package installed

Output:
    - data/kb/index/embeddings.faiss - FAISS index file
    - Updates manifest.json with build metadata
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_kb_content(content_dir: Path) -> List[Dict[str, Any]]:
    """Load all KB entries from JSONL files.

    Args:
        content_dir: Directory containing JSONL files

    Returns:
        List of KB entry dictionaries
    """
    entries = []
    for jsonl_file in content_dir.glob("*.jsonl"):
        logger.info(f"Loading {jsonl_file.name}...")
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing line {line_num} in {jsonl_file.name}: {e}")

    logger.info(f"Loaded {len(entries)} total entries")
    return entries


def generate_embeddings(entries: List[Dict[str, Any]]) -> List[List[float]]:
    """Generate embeddings for KB entries.

    Args:
        entries: List of KB entries

    Returns:
        List of embedding vectors
    """
    from modules.config.manager import get_config_manager

    config_manager = get_config_manager()
    embedding_config = config_manager.get_embedding_config("bedrock")

    logger.info(f"Using embedding model: {embedding_config.model_id}")
    logger.info(f"Generating embeddings for {len(entries)} entries...")

    # For now, this is a placeholder
    # In a full implementation, we would:
    # 1. Use boto3 to call Bedrock embeddings API
    # 2. Batch the entries for efficiency
    # 3. Handle rate limiting and retries

    # TODO: Implement actual embedding generation
    logger.warning("Embedding generation not yet implemented")
    logger.warning("FAISS index will not be created - KB will use text search fallback")

    return []


def build_faiss_index(embeddings: List[List[float]], index_path: Path) -> None:
    """Build and save FAISS index from embeddings.

    Args:
        embeddings: List of embedding vectors
        index_path: Path to save FAISS index
    """
    if not embeddings:
        logger.warning("No embeddings provided - skipping FAISS index creation")
        return

    try:
        import faiss
        import numpy as np

        # Convert to numpy array
        embeddings_array = np.array(embeddings).astype('float32')
        dimension = embeddings_array.shape[1]

        logger.info(f"Building FAISS index with {len(embeddings)} vectors of dimension {dimension}")

        # Create FAISS index (using flat L2 for simplicity)
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_array)

        # Save index
        index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(index_path))

        logger.info(f"FAISS index saved to {index_path}")

    except ImportError:
        logger.error("faiss-cpu package not installed. Install with: pip install faiss-cpu")
        raise
    except Exception as e:
        logger.error(f"Error building FAISS index: {e}")
        raise


def update_manifest(manifest_path: Path, entry_count: int, has_index: bool) -> None:
    """Update manifest with build metadata.

    Args:
        manifest_path: Path to manifest.json
        entry_count: Number of KB entries
        has_index: Whether FAISS index was created
    """
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {}

    # Update build metadata
    manifest["last_build"] = datetime.now().isoformat()
    manifest["entry_count"] = entry_count
    manifest["has_faiss_index"] = has_index

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Updated manifest: {entry_count} entries, index={has_index}")


def main():
    """Main build process."""
    logger.info("Starting KB index build...")

    # Get paths
    kb_dir = Path(__file__).parent
    content_dir = kb_dir / "content"
    index_path = kb_dir / "index" / "embeddings.faiss"
    manifest_path = kb_dir / "manifest.json"

    # Check content directory exists
    if not content_dir.exists():
        logger.error(f"Content directory not found: {content_dir}")
        sys.exit(1)

    # Load KB content
    entries = load_kb_content(content_dir)
    if not entries:
        logger.error("No KB entries loaded")
        sys.exit(1)

    # Generate embeddings
    embeddings = generate_embeddings(entries)

    # Build FAISS index
    has_index = False
    if embeddings:
        build_faiss_index(embeddings, index_path)
        has_index = True
    else:
        logger.info("Skipping FAISS index creation - text search will be used")

    # Update manifest
    update_manifest(manifest_path, len(entries), has_index)

    logger.info("KB build complete!")
    logger.info(f"  Entries: {len(entries)}")
    logger.info(f"  FAISS index: {'created' if has_index else 'not created (using text search)'}")


if __name__ == "__main__":
    main()
