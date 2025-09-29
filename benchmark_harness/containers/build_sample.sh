#!/bin/bash
# Sample build script to test the approach with a few benchmarks

set -e

# Configuration
ECR_REGISTRY="980989823532.dkr.ecr.us-east-1.amazonaws.com"
AWS_REGION="us-east-1"
IMAGE_TAG="latest"
PLATFORM="linux/amd64"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Sample XBOW Benchmark Build ===${NC}"
echo -e "${BLUE}ECR Registry: $ECR_REGISTRY${NC}"
echo -e "${BLUE}Platform: $PLATFORM${NC}"
echo ""

# Function to ensure ECR login
ensure_ecr_login() {
    echo -e "${YELLOW}Ensuring ECR login...${NC}"
    if aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY; then
        echo -e "${GREEN}✓ ECR login successful${NC}"
    else
        echo -e "${RED}✗ ECR login failed${NC}"
        exit 1
    fi
}

# Function to create ECR repository if it doesn't exist
ensure_ecr_repo() {
    local repo_name=$1
    echo -e "${YELLOW}Checking ECR repository: $repo_name${NC}"
    
    if aws ecr describe-repositories --repository-names "$repo_name" --region $AWS_REGION >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Repository $repo_name exists${NC}"
    else
        echo -e "${YELLOW}Creating ECR repository: $repo_name${NC}"
        if aws ecr create-repository --repository-name "$repo_name" --region $AWS_REGION >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Repository $repo_name created${NC}"
        else
            echo -e "${RED}✗ Failed to create repository $repo_name${NC}"
            return 1
        fi
    fi
}

# Function to get flag for a benchmark
get_benchmark_flag() {
    local benchmark_id=$1
    local flag_file="validation-benchmarks/benchmarks/${benchmark_id}/.env"
    
    if [[ -f "$flag_file" ]]; then
        grep "FLAG=" "$flag_file" | cut -d'"' -f2
    else
        echo "flag{placeholder-${benchmark_id}}"
    fi
}

# Function to check if component needs flag injection
needs_flag_injection() {
    local build_path=$1
    if [[ -f "$build_path/Dockerfile" ]]; then
        grep -q "ARG FLAG" "$build_path/Dockerfile"
    else
        false
    fi
}

# Function to build and push image
build_and_push() {
    local benchmark_id=$1
    local component=$2
    local build_path=$3
    local needs_flag=$4
    
    echo -e "${YELLOW}Building ${benchmark_id} - ${component}...${NC}"
    
    # Determine ECR repository name based on component type
    local ecr_repo=""
    case $component in
        db|mysql|postgres|mongodb)
            ecr_repo="eks-benchmark-harness/xben-databases"
            ;;
        *)
            ecr_repo="eks-benchmark-harness/xben-web-apps"
            ;;
    esac
    
    # Ensure ECR repository exists
    if ! ensure_ecr_repo "$ecr_repo"; then
        echo -e "${RED}✗ Failed to ensure ECR repository${NC}"
        return 1
    fi
    
    local image_name="${ECR_REGISTRY}/${ecr_repo}:${benchmark_id}-${component}-${IMAGE_TAG}"
    
    # Build command with platform specification
    local build_cmd="docker build --platform $PLATFORM"
    
    # Add flag if needed
    if [[ "$needs_flag" == "true" ]]; then
        local flag=$(get_benchmark_flag "$benchmark_id")
        build_cmd="$build_cmd --build-arg FLAG=\"$flag\""
        echo -e "${GREEN}  Using flag: $flag${NC}"
    fi
    
    build_cmd="$build_cmd -t $image_name $build_path"
    
    echo -e "${BLUE}  Build command: $build_cmd${NC}"
    
    # Execute build
    if eval $build_cmd; then
        echo -e "${GREEN}  ✓ Build successful${NC}"
        
        # Push to ECR
        echo -e "${YELLOW}  Pushing to ECR...${NC}"
        if docker push "$image_name"; then
            echo -e "${GREEN}  ✓ Push successful${NC}"
            return 0
        else
            echo -e "${RED}  ✗ Push failed${NC}"
            return 1
        fi
    else
        echo -e "${RED}  ✗ Build failed${NC}"
        return 1
    fi
}

# Main execution
main() {
    # Ensure ECR login first
    ensure_ecr_login
    
    # Sample benchmarks to test (avoiding problematic ones)
    local sample_benchmarks=("XBEN-005-24" "XBEN-006-24")
    
    local build_count=0
    local success_count=0
    local failed_builds=()
    
    for benchmark_id in "${sample_benchmarks[@]}"; do
        local benchmark_dir="benchmark_harness/containers/$benchmark_id"
        
        if [[ -d "$benchmark_dir" ]]; then
            echo -e "${BLUE}=== Processing $benchmark_id ===${NC}"
            
            # Find all component directories
            for component_dir in "$benchmark_dir"/*; do
                if [[ -d "$component_dir" ]]; then
                    local component=$(basename "$component_dir")
                    
                    # Check if Dockerfile exists
                    if [[ -f "$component_dir/Dockerfile" ]]; then
                        build_count=$((build_count + 1))
                        
                        # Check if this component needs flag injection
                        local flag_needed="false"
                        if needs_flag_injection "$component_dir"; then
                            flag_needed="true"
                        fi
                        
                        # Build and push
                        if build_and_push "$benchmark_id" "$component" "$component_dir" "$flag_needed"; then
                            success_count=$((success_count + 1))
                        else
                            failed_builds+=("${benchmark_id}-${component}")
                        fi
                    else
                        echo -e "${YELLOW}  Skipping $component (no Dockerfile)${NC}"
                    fi
                fi
            done
            echo ""
        else
            echo -e "${RED}Directory not found: $benchmark_dir${NC}"
        fi
    done
    
    # Summary
    echo -e "${BLUE}=== Build Summary ===${NC}"
    echo -e "${GREEN}Successful builds: $success_count${NC}"
    echo -e "${RED}Failed builds: $((build_count - success_count))${NC}"
    echo -e "${BLUE}Total builds attempted: $build_count${NC}"
    
    if [[ ${#failed_builds[@]} -gt 0 ]]; then
        echo -e "${RED}Failed builds:${NC}"
        for failed in "${failed_builds[@]}"; do
            echo -e "${RED}  - $failed${NC}"
        done
    else
        echo -e "${GREEN}All sample builds completed successfully!${NC}"
    fi
}

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI is required but not installed${NC}"
    exit 1
fi

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is required but not installed${NC}"
    exit 1
fi

# Run main function
main "$@"