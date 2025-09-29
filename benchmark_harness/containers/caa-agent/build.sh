#!/bin/bash
set -e

# Build script for CAA Agent container

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

IMAGE_NAME="caa-agent"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-}"

echo "Building CAA Agent container..."
echo "Project root: $PROJECT_ROOT"
echo "Script directory: $SCRIPT_DIR"

# Build the image
if [ -n "$REGISTRY" ]; then
    FULL_IMAGE_NAME="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
else
    FULL_IMAGE_NAME="$IMAGE_NAME:$IMAGE_TAG"
fi

echo "Building image: $FULL_IMAGE_NAME"

docker build \
    --platform linux/amd64 \
    -t "$FULL_IMAGE_NAME" \
    "$SCRIPT_DIR"

echo "✅ Successfully built $FULL_IMAGE_NAME"

# Test the image
echo "🧪 Testing the image..."
docker run --rm "$FULL_IMAGE_NAME" --help

echo "✅ CAA Agent container built and tested successfully!"