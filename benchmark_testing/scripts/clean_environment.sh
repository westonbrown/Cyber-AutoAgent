#!/bin/bash
# clean_environment.sh
# Script to clean up Docker resources and prepare for fresh test runs

set -e

echo "===== CAA Test Harness - Environment Cleanup ====="
echo "Cleaning up Docker resources and preparing for fresh test runs..."

# Function to display usage information
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -a, --all       Remove all Docker resources (containers, images, volumes, networks)"
    echo "  -c, --containers Remove only stopped containers"
    echo "  -i, --images    Remove dangling images"
    echo "  -v, --volumes   Remove unused volumes"
    echo "  -r, --results   Clean results directory (keeps directory structure)"
    echo "  -h, --help      Display this help message"
    echo
    echo "If no options are specified, only stopped containers are removed."
}

# Parse command-line options
CLEAN_CONTAINERS=false
CLEAN_IMAGES=false
CLEAN_VOLUMES=false
CLEAN_RESULTS=false
CLEAN_ALL=false

if [ $# -eq 0 ]; then
    CLEAN_CONTAINERS=true
else
    while [ $# -gt 0 ]; do
        case "$1" in
            -a|--all)
                CLEAN_ALL=true
                CLEAN_CONTAINERS=true
                CLEAN_IMAGES=true
                CLEAN_VOLUMES=true
                CLEAN_RESULTS=true
                ;;
            -c|--containers)
                CLEAN_CONTAINERS=true
                ;;
            -i|--images)
                CLEAN_IMAGES=true
                ;;
            -v|--volumes)
                CLEAN_VOLUMES=true
                ;;
            -r|--results)
                CLEAN_RESULTS=true
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
        shift
    done
fi

# Stop all running containers
if [ "$CLEAN_CONTAINERS" = true ] || [ "$CLEAN_ALL" = true ]; then
    echo "[1/5] Stopping all running benchmark containers..."
    
    # Find all docker-compose files in the benchmarks directory
    BENCHMARK_DIR=~/cyber-autoagent-test/validation-benchmarks/benchmarks
    for BENCHMARK in "$BENCHMARK_DIR"/XBEN-*; do
        if [ -d "$BENCHMARK" ] && [ -f "$BENCHMARK/docker-compose.yml" ]; then
            echo "  - Stopping containers for $(basename "$BENCHMARK")..."
            (cd "$BENCHMARK" && docker-compose down) || echo "  - Failed to stop containers for $(basename "$BENCHMARK")"
        fi
    done
    
    # Remove any other stopped containers
    echo "  - Removing any remaining stopped containers..."
    docker container prune -f
    echo "  - Containers cleaned up."
fi

# Clean up dangling and unused images
if [ "$CLEAN_IMAGES" = true ] || [ "$CLEAN_ALL" = true ]; then
    echo "[2/5] Removing dangling Docker images..."
    docker image prune -f
    
    if [ "$CLEAN_ALL" = true ]; then
        echo "  - Removing all unused Docker images..."
        docker image prune -a -f
    fi
    echo "  - Images cleaned up."
fi

# Clean up volumes
if [ "$CLEAN_VOLUMES" = true ] || [ "$CLEAN_ALL" = true ]; then
    echo "[3/5] Cleaning up Docker volumes..."
    docker volume prune -f
    echo "  - Volumes cleaned up."
fi

# Clean up networks
if [ "$CLEAN_ALL" = true ]; then
    echo "[4/5] Cleaning up Docker networks..."
    docker network prune -f
    echo "  - Networks cleaned up."
fi

# Clean up results directory
if [ "$CLEAN_RESULTS" = true ] || [ "$CLEAN_ALL" = true ]; then
    echo "[5/5] Cleaning results directory..."
    RESULTS_DIR=~/cyber-autoagent-test/results
    if [ -d "$RESULTS_DIR" ]; then
        rm -f "$RESULTS_DIR"/*.json
        rm -f "$RESULTS_DIR"/*.log
        echo "  - Results directory cleaned."
    else
        echo "  - Results directory not found, skipping."
    fi
fi

echo "===== Environment cleanup complete! ====="
if [ "$CLEAN_ALL" = true ]; then
    echo "All Docker resources and results have been cleaned."
    echo "The system is ready for fresh benchmark testing."
else
    echo "Selected resources have been cleaned."
    echo "Use './clean_environment.sh --all' for a complete cleanup."
fi