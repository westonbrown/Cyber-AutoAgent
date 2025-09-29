#!/bin/bash
# Build all benchmark containers for the new simplified harness

set -e

# Configuration
ECR_REGISTRY="123456789999.dkr.ecr.us-east-1.amazonaws.com"  # Update with your account ID
AWS_REGION="us-east-1"
IMAGE_TAG="latest"
PLATFORM="linux/amd64"

# Generate all benchmark IDs from 001 to 104
ALL_BENCHMARKS=()
for i in {1..104}; do
    benchmark_id=$(printf "XBEN-%03d-24" $i)
    ALL_BENCHMARKS+=("$benchmark_id")
done

echo "=== Building all 104 benchmark containers ==="

# Ensure ECR login
echo "Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Create repositories if they don't exist
echo "Ensuring ECR repositories exist..."
aws ecr create-repository --repository-name benchmark-harness/xben-databases --region $AWS_REGION 2>/dev/null || true
aws ecr create-repository --repository-name benchmark-harness/xben-web-apps --region $AWS_REGION 2>/dev/null || true
aws ecr create-repository --repository-name benchmark-harness/xben-services --region $AWS_REGION 2>/dev/null || true
aws ecr create-repository --repository-name benchmark-harness/caa-agent --region $AWS_REGION 2>/dev/null || true
aws ecr create-repository --repository-name benchmark-harness/caa-agent --region $AWS_REGION 2>/dev/null || true

# Function to get flag for a benchmark from all-flag-secrets.yaml
get_benchmark_flag() {
    local benchmark_id=$1
    local flag_secret_name=$(echo "${benchmark_id}" | tr '[:upper:]' '[:lower:]')"-flag"
    
    # Find the secret block and extract the base64 encoded flag
    # The structure is: data: -> flag: -> ... -> name: secret_name
    local encoded_flag=$(awk -v name="$flag_secret_name" '
        /^data:/ { getline; if(/^  flag:/) flag_value=$2; next }
        /^  name: / && $2 == name && flag_value { print flag_value; flag_value="" }
    ' ./all-flag-secrets.yaml)
    
    if [[ -n "$encoded_flag" ]]; then
        # Decode the base64 flag
        echo "$encoded_flag" | base64 -d
    else
        echo "flag{placeholder-$benchmark_id}"
    fi
}

# Function to build containers for a benchmark
build_benchmark() {
    local benchmark_id=$1
    echo "=== Building $benchmark_id ==="
    
    local benchmark_dir="./containers/$benchmark_id"
    if [[ ! -d "$benchmark_dir" ]]; then
        echo "Directory $benchmark_dir not found, skipping..."
        return 1
    fi
    
    # Find all component directories
    for component_dir in "$benchmark_dir"/*; do
        if [[ -d "$component_dir" ]]; then
            local component=$(basename "$component_dir")
            
            # Check if Dockerfile exists
            if [[ -f "$component_dir/Dockerfile" ]]; then
                echo "Building $benchmark_id - $component..."
                
                # Determine ECR repository name based on component type
                local ecr_repo=""
                case $component in
                    db|mysql|postgres|mongodb)
                        ecr_repo="benchmark-harness/xben-databases"
                        ;;
                    *service*|*router*|haproxy|mitmproxy|nginx)
                        ecr_repo="benchmark-harness/xben-services"
                        ;;
                    *)
                        ecr_repo="benchmark-harness/xben-web-apps"
                        ;;
                esac
                
                local image_name="${ECR_REGISTRY}/${ecr_repo}:${benchmark_id}-${component}-${IMAGE_TAG}"
                
                # Get the flag for this benchmark
                local flag=$(get_benchmark_flag "$benchmark_id")
                echo "Using flag: $flag"
                
                # Build and push with flag as build argument
                if docker build --platform $PLATFORM --build-arg FLAG="$flag" -t $image_name $component_dir/; then
                    echo "Pushing $image_name..."
                    docker push $image_name
                    echo "✓ Successfully built and pushed $benchmark_id-$component"
                else
                    echo "✗ Failed to build $benchmark_id-$component"
                fi
            else
                echo "No Dockerfile found in $component_dir, skipping..."
            fi
        fi
    done
}

# Build each benchmark
echo "Building all ${#ALL_BENCHMARKS[@]} benchmarks..."
for benchmark in "${ALL_BENCHMARKS[@]}"; do
    build_benchmark "$benchmark"
    echo ""
done

echo "=== Build process complete ==="
echo "Built containers for all 104 benchmarks"
echo "Images are available in ECR repositories:"
echo "  - $ECR_REGISTRY/benchmark-harness/xben-web-apps"
echo "  - $ECR_REGISTRY/benchmark-harness/xben-databases"  
echo "  - $ECR_REGISTRY/benchmark-harness/xben-services"