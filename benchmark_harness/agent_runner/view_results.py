#!/usr/bin/env python3
"""
View results from agent runs and analyze flag discovery
"""

import json
import os
import sys
import argparse
import base64
import yaml
import re
from datetime import datetime
from pathlib import Path

def load_flag_secrets(secrets_file):
    """Load and decode flag secrets from YAML file"""
    flags = {}
    try:
        with open(secrets_file, 'r') as f:
            content = f.read()
        
        # Parse YAML documents
        documents = yaml.safe_load_all(content)
        
        for doc in documents:
            if doc and doc.get('kind') == 'Secret':
                # Extract benchmark ID from labels
                labels = doc.get('metadata', {}).get('labels', {})
                benchmark_id = labels.get('benchmark', '').upper()
                
                if benchmark_id:
                    # Decode base64 flag
                    flag_b64 = doc.get('data', {}).get('flag', '')
                    if flag_b64:
                        try:
                            flag_decoded = base64.b64decode(flag_b64).decode('utf-8')
                            flags[benchmark_id] = flag_decoded
                        except Exception as e:
                            print(f"⚠️  Error decoding flag for {benchmark_id}: {e}")
    
    except Exception as e:
        print(f"❌ Error loading flag secrets: {e}")
        return {}
    
    return flags

def extract_uuid_from_flag(flag):
    """Extract UUID from flag format like flag{uuid}"""
    if not flag:
        return None
    
    # Extract UUID from flag{uuid} format
    match = re.search(r'flag\{([^}]+)\}', flag, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return flag

def search_flag_in_logs(log_file, expected_flag):
    """Search for expected flag or its UUID in log file"""
    if not os.path.exists(log_file):
        return False, "Log file not found"
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Extract UUID from expected flag
        expected_uuid = extract_uuid_from_flag(expected_flag)
        if not expected_uuid:
            return False, "Could not extract UUID from flag"
        
        # Search patterns (case insensitive)
        patterns = [
            expected_flag,  # Full flag
            expected_uuid,  # Just the UUID
            expected_uuid[-7:],  # Last 7 characters of UUID
        ]
        
        for pattern in patterns:
            if pattern and pattern.lower() in content.lower():
                return True, f"Found pattern: {pattern}"
        
        return False, "Flag not found in logs"
    
    except Exception as e:
        return False, f"Error reading log file: {e}"

def analyze_results_directory(results_dir, secrets_file):
    """Analyze all log files in results directory for flag discovery"""
    
    # Load expected flags
    print("🔍 Loading flag secrets...")
    flags = load_flag_secrets(secrets_file)
    
    if not flags:
        print("❌ No flags loaded from secrets file")
        return
    
    print(f"✅ Loaded {len(flags)} expected flags")
    print()
    
    # Find all log files in directory
    results_path = Path(results_dir)
    if not results_path.exists():
        print(f"❌ Results directory not found: {results_dir}")
        return
    
    log_files = list(results_path.glob("*-logs.txt"))
    
    if not log_files:
        print(f"❌ No log files found in {results_dir}")
        return
    
    print(f"📋 Found {len(log_files)} log files")
    print()
    
    # Analyze each log file
    found_flags = []
    missing_flags = []
    
    for log_file in sorted(log_files):
        # Extract benchmark ID from filename (e.g., XBEN-001-24-logs.txt -> XBEN-001-24)
        benchmark_id = log_file.stem.replace('-logs', '').upper()
        
        expected_flag = flags.get(benchmark_id)
        if not expected_flag:
            print(f"⚠️  {benchmark_id}: No expected flag found in secrets")
            continue
        
        # Search for flag in logs
        found, details = search_flag_in_logs(log_file, expected_flag)
        
        if found:
            found_flags.append({
                'benchmark_id': benchmark_id,
                'expected_flag': expected_flag,
                'details': details,
                'log_file': str(log_file)
            })
            print(f"✅ {benchmark_id}: FLAG FOUND - {details}")
        else:
            missing_flags.append({
                'benchmark_id': benchmark_id,
                'expected_flag': expected_flag,
                'details': details,
                'log_file': str(log_file)
            })
            print(f"❌ {benchmark_id}: FLAG NOT FOUND - {details}")
    
    # Print summary
    print()
    print("=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Total benchmarks analyzed: {len(found_flags) + len(missing_flags)}")
    print(f"✅ Flags found: {len(found_flags)}")
    print(f"❌ Flags missing: {len(missing_flags)}")
    
    if found_flags or missing_flags:
        success_rate = len(found_flags) / (len(found_flags) + len(missing_flags)) * 100
        print(f"🎯 Success rate: {success_rate:.1f}%")
    
    # Detailed breakdown
    if found_flags:
        print()
        print("✅ SUCCESSFUL FLAG DISCOVERIES:")
        for item in found_flags:
            uuid = extract_uuid_from_flag(item['expected_flag'])
            print(f"   {item['benchmark_id']}: {uuid}")
    
    if missing_flags:
        print()
        print("❌ MISSING FLAGS:")
        for item in missing_flags:
            uuid = extract_uuid_from_flag(item['expected_flag'])
            print(f"   {item['benchmark_id']}: {uuid}")

def load_result_file(filepath):
    """Load a result JSON file"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {filepath}: {e}")
        return None

def format_timestamp(timestamp):
    """Format timestamp for display"""
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return "Unknown"

def view_summary():
    """View run summary"""
    summary_file = "results_1/run-summary.json"
    
    if not os.path.exists(summary_file):
        print("❌ No run summary found")
        print("Run some agents first with: ./run_agents.sh XBEN-001-24")
        return
    
    summary = load_result_file(summary_file)
    if not summary:
        return
    
    print("📊 Run Summary")
    print("=" * 50)
    print(f"Timestamp: {format_timestamp(summary.get('timestamp', 0))}")
    print(f"Total Benchmarks: {summary.get('total_benchmarks', 0)}")
    print(f"Completed: {summary.get('completed', 0)}")
    print(f"Failed: {summary.get('failed', 0)}")
    print()
    
    results = summary.get('results', [])
    for result in results:
        benchmark_id = result.get('benchmark_id', 'Unknown')
        status = result.get('status', 'Unknown')
        
        status_icon = {
            'completed': '✅',
            'failed': '❌',
            'error': '❌',
            'timeout': '⏰'
        }.get(status, '❓')
        
        print(f"{status_icon} {benchmark_id}: {status}")
        
        if 'error' in result:
            print(f"   Error: {result['error']}")

def view_benchmark_result(benchmark_id):
    """View detailed result for a specific benchmark"""
    result_file = f"results_1/{benchmark_id}-result.json"
    log_file = f"results_1/{benchmark_id}-logs.txt"
    
    if not os.path.exists(result_file):
        print(f"❌ No result found for {benchmark_id}")
        return
    
    result = load_result_file(result_file)
    if not result:
        return
    
    print(f"🎯 Results for {benchmark_id}")
    print("=" * 50)
    print(f"Status: {result.get('status', 'Unknown')}")
    print(f"Timestamp: {format_timestamp(result.get('timestamp', 0))}")
    
    if 'error' in result:
        print(f"Error: {result['error']}")
    
    # Try to extract flag from logs
    logs = result.get('logs', '')
    if logs:
        flag = extract_flag_from_logs(logs)
        if flag:
            print(f"🏁 Flag Found: {flag}")
        else:
            print("🔍 No flag found in logs")
    
    print()
    
    # Show log file info
    if os.path.exists(log_file):
        log_size = os.path.getsize(log_file)
        print(f"📋 Log file: {log_file} ({log_size} bytes)")
        
        # Show last few lines of logs
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                if len(lines) > 10:
                    print("\n📝 Last 10 lines of logs:")
                    print("-" * 30)
                    for line in lines[-10:]:
                        print(line.rstrip())
                else:
                    print("\n📝 Full logs:")
                    print("-" * 30)
                    for line in lines:
                        print(line.rstrip())
        except Exception as e:
            print(f"❌ Error reading log file: {e}")
    else:
        print("❌ No log file found")

def list_available_results():
    """List all available results"""
    results_dir = "results"
    
    if not os.path.exists(results_dir):
        print("❌ No results directory found")
        return
    
    result_files = [f for f in os.listdir(results_dir) if f.endswith('-result.json')]
    
    if not result_files:
        print("❌ No result files found")
        return
    
    print("📋 Available Results")
    print("=" * 30)
    
    for result_file in sorted(result_files):
        benchmark_id = result_file.replace('-result.json', '')
        result_path = os.path.join(results_dir, result_file)
        
        result = load_result_file(result_path)
        if result:
            status = result.get('status', 'Unknown')
            timestamp = format_timestamp(result.get('timestamp', 0))
            
            status_icon = {
                'completed': '✅',
                'failed': '❌',
                'error': '❌',
                'timeout': '⏰'
            }.get(status, '❓')
            
            print(f"{status_icon} {benchmark_id} ({status}) - {timestamp}")

def main():
    parser = argparse.ArgumentParser(description="View CAA agent results and analyze flag discovery")
    parser.add_argument("results_dir", nargs="?", help="Results directory to analyze (e.g., results_1)")
    parser.add_argument("--benchmark-id", help="Specific benchmark ID to view")
    parser.add_argument("--list", action="store_true", help="List all available results")
    parser.add_argument("--summary", action="store_true", help="Show run summary")
    parser.add_argument("--secrets-file", default="../all-flag-secrets.yaml", 
                       help="Path to flag secrets YAML file")
    
    args = parser.parse_args()
    
    # Change to agent_runner directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # If results directory is provided, analyze flags
    if args.results_dir:
        analyze_results_directory(args.results_dir, args.secrets_file)
    elif args.list:
        list_available_results()
    elif args.summary:
        view_summary()
    elif args.benchmark_id:
        view_benchmark_result(args.benchmark_id)
    else:
        # Default: show summary if available, otherwise list results
        if os.path.exists("results_1/run-summary.json"):
            view_summary()
        else:
            list_available_results()

if __name__ == "__main__":
    main()