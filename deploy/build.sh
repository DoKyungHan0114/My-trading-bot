#!/bin/bash
# Build and push TQQQ Trading Bot image to Artifact Registry
# Usage: ./deploy/build.sh [tag]

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-short-term-trade}"
REGION="${GCE_REGION:-us-central1}"
AR_REPO="tqqq"
IMAGE_NAME="bot"
TAG="${1:-latest}"

IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}"

echo "=== Building TQQQ Trading Bot Image ==="
echo "Project: ${PROJECT_ID}"
echo "Image: ${IMAGE_URL}:${TAG}"
echo ""

# Ensure we're in project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

# Configure Docker for Artifact Registry
echo "Configuring Docker authentication..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Build image
echo "Building image..."
docker build -f deploy/Dockerfile.bot -t ${IMAGE_URL}:${TAG} .

# Also tag as latest if building a specific version
if [ "${TAG}" != "latest" ]; then
    docker tag ${IMAGE_URL}:${TAG} ${IMAGE_URL}:latest
fi

# Push image
echo "Pushing image..."
docker push ${IMAGE_URL}:${TAG}

if [ "${TAG}" != "latest" ]; then
    docker push ${IMAGE_URL}:latest
fi

echo ""
echo "=== Build Complete ==="
echo "Image: ${IMAGE_URL}:${TAG}"
echo ""
echo "To deploy to GCE:"
echo "  gcloud compute ssh tqqq-trading-bot --zone=us-central1-a -- sudo tqqq-update"
echo ""
echo "Or with specific tag:"
echo "  IMAGE_TAG=${TAG} ./deploy/gce_setup.sh"
