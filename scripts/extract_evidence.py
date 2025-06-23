#!/usr/bin/env python3
"""
Evidence extraction script for Cyber-AutoAgent investigations.
This script attempts to access and display stored evidence from a completed operation.
"""

import os
import sys
import sqlite3
import pickle
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
                    print(f"     {i+1}. {record}")
            
            conn.close()
        except Exception as e:
            print(f"   ❌ Error reading database: {e}")
    
    # Check pickle file
    pickle_file = evidence_path / "mem0.pkl"
    if pickle_file.exists():
        print(f"\n🗂️  Memory Pickle: {pickle_file}")
        try:
            with open(pickle_file, 'rb') as f:
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
        'folder': evidence_folder,
        'history_db': history_db.exists(),
        'pickle_file': pickle_file.exists(),
        'faiss_file': faiss_file.exists()
    }

def try_mem0_access(evidence_folder):
    """Try to access evidence using mem0 library directly."""
    
    print(f"\n🧠 Attempting to access mem0 memory system...")
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
                "config": {
                    "collection_name": "mem0",
                    "path": str(evidence_folder)
                }
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
                print(f"\n   [{i+1}] Memory ID: {mem.get('id', 'unknown')}")
                print(f"       Content: {mem.get('memory', 'No content')[:200]}...")
                print(f"       Category: {mem.get('metadata', {}).get('category', 'unknown')}")
                print(f"       Timestamp: {mem.get('metadata', {}).get('timestamp', 'unknown')}")
        else:
            print("   ❌ No memories found")
        
        return memories
        
    except ImportError as e:
        print(f"   ⚠️  mem0 library not available: {e}")
        return None
    except Exception as e:
        print(f"   ❌ Error accessing mem0: {e}")
        return None

def main():
    """Main function to extract evidence."""
    
    # Look for the specific evidence folder
    evidence_folder = "/Users/konradsemsch/Projects/private/Cyber-AutoAgent/evidence_OP_20250623_172144"
    
    print("🕵️ Cyber-AutoAgent Evidence Extraction Tool")
    print("=" * 80)
    
    # Extract basic file information
    file_info = extract_evidence_from_folder(evidence_folder)
    
    if not file_info:
        return
    
    # Try to access mem0 system
    memories = try_mem0_access(evidence_folder)
    
    # Summary
    print(f"\n📄 INVESTIGATION SUMMARY")
    print("=" * 80)
    print(f"Operation ID: OP-20250623-172144")
    print(f"Target: http://testphp.vulnweb.com")
    print(f"Objective: Identify and demonstrate exploitable vulnerabilities")
    print(f"Duration: ~10 minutes (based on logs)")
    print(f"Evidence Folder: {evidence_folder}")
    print(f"Status: Investigation completed but evidence retrieval shows disconnect")
    
    if memories:
        print(f"✅ Successfully retrieved {len(memories)} evidence items")
    else:
        print("⚠️  No evidence retrieved - possible memory system issue")
        print("   The logs show 'Evidence Collected: 3 items' but retrieval returns 0")
        print("   This suggests evidence was collected but not properly stored/accessible")

if __name__ == "__main__":
    main()