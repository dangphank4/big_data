#!/bin/bash
# ==============================================================================
# BUILD AND PUSH DOCKER IMAGE TO GOOGLE CONTAINER REGISTRY
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Get GCP project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    log_error "GCP project not set. Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

log_info "Using GCP Project: $PROJECT_ID"

# Image configuration
IMAGE_NAME="bigdata-python-worker"
IMAGE_TAG=${1:-"v1.0.0"}  # Use first argument or default
FULL_IMAGE_NAME="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${IMAGE_TAG}"
LATEST_IMAGE_NAME="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"

log_info "Image: $FULL_IMAGE_NAME"

# ==============================================================================
# BUILD
# ==============================================================================

log_info "Building Docker image..."
docker build -t ${FULL_IMAGE_NAME} -f Dockerfile .

if [ $? -eq 0 ]; then
    log_success "Docker build successful"
else
    log_error "Docker build failed"
    exit 1
fi

# Tag as latest
docker tag ${FULL_IMAGE_NAME} ${LATEST_IMAGE_NAME}

# ==============================================================================
# TEST
# ==============================================================================

log_info "Testing image..."

# Test Python
docker run --rm ${FULL_IMAGE_NAME} python --version
if [ $? -ne 0 ]; then
    log_error "Python test failed"
    exit 1
fi

# Test dependencies
log_info "Checking dependencies..."
docker run --rm ${FULL_IMAGE_NAME} pip list | grep -E "confluent-kafka|pandas|hdfs|elasticsearch"

log_success "Image tests passed"

# ==============================================================================
# PUSH
# ==============================================================================

log_info "Pushing image to GCR..."

# Configure Docker to use gcloud
gcloud auth configure-docker gcr.io --quiet

# Push with version tag
docker push ${FULL_IMAGE_NAME}
if [ $? -eq 0 ]; then
    log_success "Pushed ${FULL_IMAGE_NAME}"
else
    log_error "Push failed"
    exit 1
fi

# Push latest tag
docker push ${LATEST_IMAGE_NAME}
if [ $? -eq 0 ]; then
    log_success "Pushed ${LATEST_IMAGE_NAME}"
else
    log_error "Push latest tag failed"
    exit 1
fi

# ==============================================================================
# VERIFY
# ==============================================================================

log_info "Verifying image in GCR..."
gcloud container images describe ${FULL_IMAGE_NAME}

log_success "Image successfully built and pushed!"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Image Details:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Name: ${FULL_IMAGE_NAME}"
echo "Latest: ${LATEST_IMAGE_NAME}"
echo ""
echo "🔧 Update K8s deployments:"
echo "   sed -i 's|PROJECT_ID|${PROJECT_ID}|g' k8s/*.yaml"
echo ""
echo "🚀 Deploy to GKE:"
echo "   ./scripts/deploy.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
