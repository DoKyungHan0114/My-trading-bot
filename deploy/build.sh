#!/bin/bash
# Build and push TQQQ Trading Bot image using Cloud Build
# Usage: ./deploy/build.sh [tag]

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-short-term-trade}"
REGION="${GCE_REGION:-us-central1}"
AR_REPO="tqqq"
IMAGE_NAME="bot"
TAG="${1:-latest}"

IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}"

echo "=== Building TQQQ Trading Bot Image (Cloud Build) ==="
echo "Project: ${PROJECT_ID}"
echo "Image: ${IMAGE_URL}:${TAG}"
echo ""

# Ensure we're in project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

# Enable Cloud Build API
echo "Enabling Cloud Build API..."
gcloud services enable cloudbuild.googleapis.com --project="${PROJECT_ID}"

# Create Artifact Registry repo if not exists
echo "Setting up Artifact Registry..."
gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="TQQQ Trading Bot images" \
    --project="${PROJECT_ID}" 2>/dev/null || echo "Repository already exists"

# Build using Cloud Build
echo "Building with Cloud Build..."
gcloud builds submit \
    --config=cloudbuild.yaml \
    --substitutions=_IMAGE_URL="${IMAGE_URL}:${TAG}" \
    --project="${PROJECT_ID}" \
    --gcs-log-dir="gs://${PROJECT_ID}_cloudbuild/logs" \
    -q \
    .

# Also tag as latest if building specific version
if [ "${TAG}" != "latest" ]; then
    echo "Tagging as latest..."
    gcloud artifacts docker tags add \
        "${IMAGE_URL}:${TAG}" \
        "${IMAGE_URL}:latest" \
        --project="${PROJECT_ID}"
fi

echo ""
echo "=== Build Complete ==="
echo "Image: ${IMAGE_URL}:${TAG}"
echo ""
echo "To deploy to GCE:"
echo "  gcloud compute ssh tqqq-trading-bot --zone=us-central1-a -- sudo tqqq-update"
