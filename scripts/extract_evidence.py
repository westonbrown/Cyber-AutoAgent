#!/usr/bin/env python3
"""
Evidence extraction script for Cyber-AutoAgent investigations.
This script attempts to access and display stored evidence from a completed operation.
"""

import sys
import sqlite3
import pickle
import argparse
import glob
from pathlib import Path


def extract_evidence_from_folder(evidence_folder):
    """Extract evidence from the specified evidence folder."""

    evidence_path = Path(evidence_folder)
    if not evidence_path.exists():
        print(f"❌ Evidence folder not found: {evidence_folder}")
        return None

    print(f"🔍 Examining evidence folder: {evidence_folder}")
    print("=" * 80)

    # Check SQLite database
    history_db = evidence_path / "history.db"
    if history_db.exists():
        print(f"📊 History Database: {history_db}")
        try:
            conn = sqlite3.connect(str(history_db))
            cursor = conn.cursor()

            # Get table info
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print(f"   Tables: {[t[0] for t in tables]}")

            # Check history table
            cursor.execute("SELECT COUNT(*) FROM history;")
            count = cursor.fetchone()[0]
            print(f"   History records: {count}")

            if count > 0:
                cursor.execute("SELECT * FROM history LIMIT 10;")
                records = cursor.fetchall()
                print("   Recent history entries:")
                for i, record in enumerate(records):
                    print(f"     {i + 1}. {record}")

            conn.close()
        except Exception as e:
            print(f"   ❌ Error reading database: {e}")

    # Check pickle file
    pickle_file = evidence_path / "mem0.pkl"
    if pickle_file.exists():
        print(f"\n🗂️  Memory Pickle: {pickle_file}")
        try:
            with open(pickle_file, "rb") as f:
                data = pickle.load(f)
            print(f"   Type: {type(data)}")
            print(f"   Content: {data}")
            print(f"   Size: {pickle_file.stat().st_size} bytes")
        except Exception as e:
            print(f"   ❌ Error reading pickle: {e}")

    # Check FAISS file
    faiss_file = evidence_path / "mem0.faiss"
    if faiss_file.exists():
        print(f"\n🧮 FAISS Vector Store: {faiss_file}")
        print(f"   Size: {faiss_file.stat().st_size} bytes")

        # Try to load with FAISS if available
        try:
            import faiss

            index = faiss.read_index(str(faiss_file))
            print(f"   Vector dimensions: {index.d}")
            print(f"   Total vectors: {index.ntotal}")
        except ImportError:
            print("   ⚠️  FAISS not available - cannot read vector data")
        except Exception as e:
            print(f"   ❌ Error reading FAISS index: {e}")

    print("=" * 80)

    return {
        "folder": evidence_folder,
        "history_db": history_db.exists(),
        "pickle_file": pickle_file.exists(),
        "faiss_file": faiss_file.exists(),
    }


def try_mem0_access(evidence_folder):
    """Try to access evidence using mem0 library directly."""

    print("\n🧠 Attempting to access mem0 memory system...")
    print("=" * 80)

    try:
        # Add the src directory to path
        src_path = Path(__file__).parent / "src"
        sys.path.insert(0, str(src_path))

        from mem0 import Memory

        # Configure mem0 to use the evidence folder
        config = {
            "vector_store": {
                "provider": "faiss",
                "config": {"collection_name": "mem0", "path": str(evidence_folder)},
            }
        }

        # Initialize memory instance
        memory = Memory.from_config(config)

        # Try to get all memories
        memories = memory.get_all(user_id="cyber_agent")

        print(f"📋 Retrieved {len(memories) if memories else 0} memory entries")

        if memories:
            print("\n🔍 Memory Entries:")
            for i, mem in enumerate(memories):
                print(f"\n   [{i + 1}] Memory ID: {mem.get('id', 'unknown')}")
                print(f"       Content: {mem.get('memory', 'No content')[:200]}...")
                print(
                    f"       Category: {mem.get('metadata', {}).get('category', 'unknown')}"
                )
                print(
                    f"       Timestamp: {mem.get('metadata', {}).get('timestamp', 'unknown')}"
                )
        else:
            print("   ❌ No memories found")

        return memories

    except ImportError as e:
        print(f"   ⚠️  mem0 library not available: {e}")
        return None
    except Exception as e:
        print(f"   ❌ Error accessing mem0: {e}")
        return None


def find_evidence_folders(base_path="/app/evidence"):
    """Find all evidence folders in the base path."""
    base_path = Path(base_path)
    if not base_path.exists():
        # Fallback to current directory
        base_path = Path(".")

    evidence_patterns = ["evidence_*", "evidence_OP_*"]
    evidence_folders = []

    for pattern in evidence_patterns:
        evidence_folders.extend(glob.glob(str(base_path / pattern)))

    return sorted(evidence_folders)


def main():
    """Main function to extract evidence."""

    parser = argparse.ArgumentParser(
        description="Extract and display evidence from Cyber-AutoAgent operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python extract_evidence.py                           # List all evidence folders
    python extract_evidence.py --folder evidence_OP_123 # Examine specific folder
    python extract_evidence.py --latest                 # Examine latest evidence
        """,
    )
    parser.add_argument("--folder", "-f", help="Specific evidence folder to examine")
    parser.add_argument(
        "--latest", "-l", action="store_true", help="Examine the latest evidence folder"
    )
    parser.add_argument(
        "--list", action="store_true", help="List all available evidence folders"
    )
    parser.add_argument(
        "--base-path",
        "-b",
        default="/app/evidence",
        help="Base path to search for evidence folders (default: /app/evidence)",
    )

    args = parser.parse_args()

    print("🕵️ Cyber-AutoAgent Evidence Extraction Tool")
    print("=" * 80)

    # Find evidence folders
    evidence_folders = find_evidence_folders(args.base_path)

    if not evidence_folders:
        print(f"❌ No evidence folders found in {args.base_path}")
        # Try current directory as fallback
        evidence_folders = find_evidence_folders(".")
        if evidence_folders:
            print("📁 Found evidence folders in current directory:")
            for folder in evidence_folders:
                print(f"   - {folder}")
        return

    # Handle list option
    if args.list:
        print(f"📁 Available evidence folders in {args.base_path}:")
        for i, folder in enumerate(evidence_folders, 1):
            folder_name = Path(folder).name
            print(f"   {i}. {folder_name}")
        return

    # Determine which folder to examine
    if args.folder:
        evidence_folder = args.folder
        if not Path(evidence_folder).is_absolute():
            evidence_folder = str(Path(args.base_path) / evidence_folder)
    elif args.latest:
        evidence_folder = evidence_folders[-1] if evidence_folders else None
    else:
        if len(evidence_folders) == 1:
            evidence_folder = evidence_folders[0]
        else:
            print(f"📁 Found {len(evidence_folders)} evidence folders:")
            for i, folder in enumerate(evidence_folders, 1):
                folder_name = Path(folder).name
                print(f"   {i}. {folder_name}")
            print(
                "\nUse --folder <name> to examine a specific folder or --latest for the most recent"
            )
            return

    if not evidence_folder:
        print("❌ No evidence folder specified")
        return

    # Extract basic file information
    file_info = extract_evidence_from_folder(evidence_folder)

    if not file_info:
        return

    # Try to access mem0 system
    memories = try_mem0_access(evidence_folder)

    # Generate summary
    folder_name = Path(evidence_folder).name
    operation_id = folder_name.replace("evidence_", "").replace("_", "-")

    print("\n📄 INVESTIGATION SUMMARY")
    print("=" * 80)
    print(f"Operation ID: {operation_id}")
    print(f"Evidence Folder: {evidence_folder}")

    if memories:
        print(f"✅ Successfully retrieved {len(memories)} evidence items")

        # Categorize memories
        categories = {}
        for mem in memories:
            category = mem.get("metadata", {}).get("category", "uncategorized")
            categories[category] = categories.get(category, 0) + 1

        print("\n📊 Evidence Categories:")
        for category, count in categories.items():
            print(f"   - {category}: {count} items")

    else:
        print(
            "⚠️  No evidence retrieved - possible memory system issue or empty evidence store"
        )


if __name__ == "__main__":
    main()
