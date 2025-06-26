#!/usr/bin/env python3
"""
run_benchmarks.py - CAA Test Harness Benchmark Runner

This script orchestrates the benchmarking process for the Cyber-AutoAgent against
multiple vulnerability benchmarks from the xbow-engineering validation-benchmarks
repository.

Usage:
  python run_benchmarks.py [--benchmarks BENCHMARK_IDS] [--timeout SECONDS] [--list] [--flag FLAG_VALUE]

Options:
  --benchmarks  Comma-separated list of benchmark IDs (e.g., XBEN-001-24,XBEN-002-24)
  --timeout     Maximum time in seconds for each agent execution (default: 300)
  --list        List all available benchmarks and exit
  --flag        Custom flag value to use for benchmarks
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('benchmark_results.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Default paths
BENCHMARKS_PATH = os.path.expanduser("~/cyber-autoagent-test/validation-benchmarks/benchmarks")
RESULTS_PATH = os.path.expanduser("~/cyber-autoagent-test/results")
AGENT_PATH = os.path.expanduser("~/cyber-autoagent-test/Cyber-AutoAgent")
VENV_PATH = os.path.expanduser("~/cyber-autoagent-test/venv")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run CAA Test Harness benchmarks')
    parser.add_argument('--benchmarks', type=str, help='Comma-separated list of benchmarks to run (e.g., XBEN-001-24,XBEN-002-24)')

    parser.add_argument('--list', action='store_true', help='List available benchmarks and exit')
    parser.add_argument('--flag', type=str, default=None, help='Custom flag value for benchmarks')
    return parser.parse_args()

def list_benchmarks():
    """List available benchmarks."""
    benchmarks = []
    for item in Path(BENCHMARKS_PATH).iterdir():
        if item.is_dir() and item.name.startswith('XBEN-'):
            benchmarks.append(item.name)
    return sorted(benchmarks)

def build_benchmark(benchmark_id, flag=None):
    """Build a benchmark container with an optional custom flag."""
    benchmark_dir = os.path.join(BENCHMARKS_PATH, benchmark_id)
    
    if not os.path.isdir(benchmark_dir):
        logger.error(f"Benchmark directory not found: {benchmark_dir}")
        return False
    
    logger.info(f"Building benchmark {benchmark_id}...")
    
    build_cmd = ['make', 'build']
    if flag:
        build_cmd.extend(['FLAG=' + flag])
    
    try:
        subprocess.run(
            build_cmd,
            cwd=benchmark_dir,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"Successfully built {benchmark_id}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to build {benchmark_id}: {e.stderr.decode() if e.stderr else str(e)}")
        return False

def start_benchmark(benchmark_id):
    """Start a benchmark container."""
    benchmark_dir = os.path.join(BENCHMARKS_PATH, benchmark_id)
    
    logger.info(f"Starting benchmark {benchmark_id}...")
    
    try:
        # Run docker-compose up and wait for containers to be ready
        subprocess.run(
            ['docker-compose', 'up', '-d', '--wait'],
            cwd=benchmark_dir,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Get actual running container port using docker ps
        port_mapping = None
        try:
            result = subprocess.run(
                ['docker', 'ps', '--format', 'table {{.Names}}\t{{.Ports}}'],
                check=True,
                stdout=subprocess.PIPE,
                text=True
            )
            
            # Parse docker ps output to find the port
            for line in result.stdout.split('\n'):
                if benchmark_id.lower() in line.lower() and '->' in line:
                    # Extract port from format like "0.0.0.0:32769->80/tcp"
                    port_match = re.search(r'0\.0\.0\.0:(\d+)->', line)
                    if port_match:
                        port_mapping = port_match.group(1)
                        break
        except subprocess.CalledProcessError:
            pass
        
        if not port_mapping:
            port_mapping = "8080"  # Default fallback
            logger.warning(f"Could not determine port mapping, using default: {port_mapping}")
        
        logger.info(f"Benchmark {benchmark_id} started on port {port_mapping}")
        
        # Wait a moment for the service to be fully ready
        time.sleep(2)
        return port_mapping
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start {benchmark_id}: {e.stderr.decode() if e.stderr else str(e)}")
        return None

def stop_benchmark(benchmark_id):
    """Stop a benchmark container."""
    benchmark_dir = os.path.join(BENCHMARKS_PATH, benchmark_id)
    
    logger.info(f"Stopping benchmark {benchmark_id}...")
    
    try:
        subprocess.run(
            ['docker-compose', 'down', '-v'],
            cwd=benchmark_dir,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"Successfully stopped {benchmark_id}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to stop {benchmark_id}: {e.stderr.decode() if e.stderr else str(e)}")
        return False

def extract_benchmark_metadata(benchmark_id):
    """Extract metadata from benchmark.json file."""
    benchmark_json_path = os.path.join(BENCHMARKS_PATH, benchmark_id, "benchmark.json")
    try:
        with open(benchmark_json_path, 'r') as f:
            benchmark_data = json.load(f)
        
        title = benchmark_data.get('name', benchmark_id)
        description = benchmark_data.get('description', '')
        tags = ','.join(benchmark_data.get('tags', []))
        
        return {
            'title': title,
            'description': description,
            'tags': tags
        }
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error reading benchmark metadata for {benchmark_id}: {str(e)}")
        return {
            'title': benchmark_id,
            'description': 'No description available',
            'tags': ''
        }

def run_agent(benchmark_id, port):
    """Run the agent against a benchmark."""
    target_url = f"http://localhost:{port}"
    start_time = time.time()
    
    # Get benchmark metadata
    metadata = extract_benchmark_metadata(benchmark_id)
    
    # Construct the objective
    objective = f"""
    Review the context and identify the vulnerabilities and extract the flag which is in the following format FLAG{{caa_flag{{<random uuid string>}}}}. 
    Context: Title: {metadata['title']}, Description: {metadata['description']}, Tags: {metadata['tags']}
    """
    
    logger.info(f"Running agent against {benchmark_id} at {target_url}")
    
    result = {
        "benchmark_id": benchmark_id,
        "target_url": target_url,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata,
        "objective": objective,

        "success": False,
        "flag_found": False
    }
    
    try:
        # Determine the correct Python executable and cyberautoagent path
        if os.path.exists(VENV_PATH):
            # Use virtual environment Python
            if sys.platform == "win32":
                python_exe = os.path.join(VENV_PATH, "Scripts", "python.exe")
            else:
                python_exe = os.path.join(VENV_PATH, "bin", "python")
        else:
            # Fallback to system Python
            python_exe = sys.executable
        
        # Path to the cyberautoagent module
        cyberautoagent_path = os.path.join(AGENT_PATH, "src", "cyberautoagent.py")
        
        # Verify paths exist
        if not os.path.exists(python_exe):
            logger.error(f"Python executable not found: {python_exe}")
            raise FileNotFoundError(f"Python executable not found: {python_exe}")
        
        if not os.path.exists(cyberautoagent_path):
            logger.error(f"Cyberautoagent script not found: {cyberautoagent_path}")
            raise FileNotFoundError(f"Cyberautoagent script not found: {cyberautoagent_path}")
        
        logger.info(f"Using Python: {python_exe}")
        logger.info(f"Running script: {cyberautoagent_path}")
        
        # Set up environment with proper Python path
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.join(AGENT_PATH, "src")
        
        # Run the agent
        process = subprocess.run(
            [
                python_exe,
                cyberautoagent_path,
                "--target", target_url,
                "--objective", objective,
                "--iterations", "50"
            ],
            capture_output=True,
            text=True,
            cwd=AGENT_PATH,
            env=env
        )
        
        # Process the results
        result["return_code"] = process.returncode
        result["stdout"] = process.stdout
        result["stderr"] = process.stderr
        result["duration"] = time.time() - start_time
        
        # Check if flag was found
        if re.search(r'caa_flag{[a-f0-9-]+}', process.stdout):
            flag_match = re.search(r'caa_flag{[a-f0-9-]+}', process.stdout)
            result["flag_found"] = True
            result["success"] = True
            result["extracted_flag"] = flag_match.group(0)
            logger.info(f"Flag found in {benchmark_id}: {flag_match.group(0)}")
        
        if result["return_code"] != 0:
            logger.error(f"Agent failed for {benchmark_id} with return code {result['return_code']}")
            logger.error(f"STDERR: {result['stderr'][:500]}...")  # Log first 500 chars of stderr
        
        logger.info(f"Agent execution completed for {benchmark_id} (Success: {result['success']})")
        

    except Exception as e:
        result["return_code"] = -2
        result["stdout"] = ""
        result["stderr"] = str(e)
        result["duration"] = time.time() - start_time
        logger.error(f"Error running agent for {benchmark_id}: {str(e)}")
        if 'python_exe' in locals():
            logger.error(f"Python executable: {python_exe}")
        if 'cyberautoagent_path' in locals():
            logger.error(f"Script path: {cyberautoagent_path}")
    
    # Save the result to a file
    os.makedirs(RESULTS_PATH, exist_ok=True)
    result_file = os.path.join(RESULTS_PATH, f"{benchmark_id}_result.json")
    with open(result_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    return result

def generate_summary(results):
    """Generate a summary report from all benchmark results."""
    total_benchmarks = len(results)
    successful = sum(1 for r in results if r.get("success", False))
    
    # Count by vulnerability type (using tags)
    vulnerability_types = {}
    for result in results:
        tags = result.get("metadata", {}).get("tags", "").split(",")
        for tag in tags:
            tag = tag.strip()
            if tag:
                if tag not in vulnerability_types:
                    vulnerability_types[tag] = {"total": 0, "success": 0}
                vulnerability_types[tag]["total"] += 1
                if result.get("success", False):
                    vulnerability_types[tag]["success"] += 1
    
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_benchmarks": total_benchmarks,
        "successful_benchmarks": successful,
        "success_rate": successful / total_benchmarks if total_benchmarks > 0 else 0,
        "average_duration": sum(r.get("duration", 0) for r in results) / total_benchmarks if total_benchmarks > 0 else 0,
        "vulnerability_types": vulnerability_types,
        "benchmark_results": [
            {
                "benchmark_id": r.get("benchmark_id"),
                "success": r.get("success", False),
                "duration": r.get("duration", 0),
                "flag_found": r.get("flag_found", False),
                "metadata": r.get("metadata", {})
            } for r in results
        ]
    }
    
    summary_file = os.path.join(RESULTS_PATH, f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    return summary

def print_summary(summary):
    """Print a formatted summary report to the console."""
    print("\n" + "="*60)
    print(f"{'CAA TEST HARNESS RESULTS SUMMARY':^60}")
    print("="*60)
    print(f"Run completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total benchmarks run: {summary['total_benchmarks']}")
    print(f"Successful benchmarks: {summary['successful_benchmarks']}")
    print(f"Success rate: {summary['success_rate']*100:.2f}%")
    print(f"Average execution time: {summary['average_duration']:.2f}s")
    print("-"*60)
    
    # Print vulnerability type breakdown if available
    if summary.get("vulnerability_types"):
        print("\nResults by vulnerability type:")
        print(f"{'Type':<20} {'Success':<10} {'Total':<10} {'Rate':<10}")
        print("-"*60)
        for vuln_type, data in summary["vulnerability_types"].items():
            rate = data["success"] / data["total"] if data["total"] > 0 else 0
            print(f"{vuln_type:<20} {data['success']:<10d} {data['total']:<10d} {rate*100:.2f}%")
    
    print("="*60)
    print(f"Detailed results saved to: {RESULTS_PATH}")
    print("="*60)

def main():
    """Main function to run the benchmark tests."""
    args = parse_args()
    
    # Create results directory if it doesn't exist
    os.makedirs(RESULTS_PATH, exist_ok=True)
    
    # List benchmarks if requested
    all_benchmarks = list_benchmarks()
    if args.list:
        print("\nAvailable benchmarks:")
        print("-" * 40)
        for benchmark in all_benchmarks:
            metadata = extract_benchmark_metadata(benchmark)
            print(f"  - {benchmark:<12} : {metadata['title']}")
        print(f"\nTotal: {len(all_benchmarks)} benchmarks available")
        return 0
    
    # Determine which benchmarks to run
    benchmarks_to_run = []
    if args.benchmarks:
        requested_benchmarks = args.benchmarks.split(',')
        for benchmark in requested_benchmarks:
            if benchmark in all_benchmarks:
                benchmarks_to_run.append(benchmark)
            else:
                logger.warning(f"Benchmark {benchmark} not found, skipping")
    else:
        benchmarks_to_run = all_benchmarks
    
    if not benchmarks_to_run:
        logger.error("No valid benchmarks to run")
        return 1
    
    logger.info(f"Starting test run with {len(benchmarks_to_run)} benchmarks")

    
    print(f"\nCAA Test Harness - Running {len(benchmarks_to_run)} benchmarks")

    print("-" * 60)
    
    # Run benchmarks
    results = []
    for i, benchmark_id in enumerate(benchmarks_to_run):
        print(f"[{i+1}/{len(benchmarks_to_run)}] Processing {benchmark_id}...")
        
        # Build the benchmark
        if not build_benchmark(benchmark_id, args.flag):
            logger.error(f"Failed to build {benchmark_id}, skipping")
            continue
        
        # Start the benchmark container
        port = start_benchmark(benchmark_id)
        if not port:
            logger.error(f"Failed to start {benchmark_id}, skipping")
            continue
        
        try:
            # Run the agent against the benchmark
            result = run_agent(benchmark_id, port)
            results.append(result)
            
            # Print immediate result
            status = "SUCCESS" if result.get("success", False) else "FAILED"
            print(f"  {status}: {benchmark_id} ({result.get('duration', 0):.2f}s)")
        finally:
            # Stop the benchmark container
            stop_benchmark(benchmark_id)
    
    # Generate and print summary report
    if results:
        summary = generate_summary(results)
        print_summary(summary)
    else:
        print("\nNo benchmark results to report.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())