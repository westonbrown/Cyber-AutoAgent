#!/usr/bin/env python3
"""
List available benchmarks and their status
"""

import json
import subprocess
import sys

def load_endpoints():
    """Load benchmark endpoints from JSON file"""
    try:
        with open("../ctf_endpoints_internal.json", 'r') as f:
            data = json.load(f)
            return data.get('ctf_challenges', [])
    except Exception as e:
        print(f"❌ Error loading endpoints: {e}")
        return []

def check_benchmark_status(service_name, namespace="benchmark-harness"):
    """Check if benchmark service is running"""
    try:
        cmd = ["kubectl", "get", "service", service_name, "-n", namespace, "--no-headers"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def main():
    print("📋 Available Benchmarks")
    print("=" * 50)
    
    endpoints = load_endpoints()
    if not endpoints:
        print("❌ No benchmarks found")
        sys.exit(1)
    
    running_count = 0
    total_count = len(endpoints)
    
    for challenge in endpoints:
        benchmark_id = challenge.get('benchmark_id', 'Unknown')
        name = challenge.get('name', 'Unknown')
        service_name = challenge.get('service_name', '')
        internal_endpoint = challenge.get('internal_endpoint', '')
        tags = challenge.get('tags', [])
        level = challenge.get('level', 'Unknown')
        
        # Check if service is running
        is_running = check_benchmark_status(service_name) if service_name else False
        status_icon = "✅" if is_running else "❌"
        
        if is_running:
            running_count += 1
        
        print(f"{status_icon} {benchmark_id}")
        print(f"   Name: {name}")
        print(f"   Level: {level}")
        print(f"   Tags: {', '.join(tags)}")
        print(f"   Endpoint: {internal_endpoint}")
        if service_name:
            print(f"   Service: {service_name}")
        print()
    
    print("=" * 50)
    print(f"📊 Summary: {running_count}/{total_count} benchmarks running")
    
    if running_count == 0:
        print("\n⚠️ No benchmarks are currently running!")
        print("Run 'make deploy-benchmarks' to deploy them.")
        sys.exit(1)
    elif running_count < total_count:
        print(f"\n⚠️ {total_count - running_count} benchmarks are not running")
    else:
        print("\n🎉 All benchmarks are running!")

if __name__ == "__main__":
    main()