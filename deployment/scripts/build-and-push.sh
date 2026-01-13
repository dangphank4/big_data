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

IMAGE_TAG=${1:-"v1.0.0"}  # Use first argument or default

# Image configuration
IMAGE_NAME_APP="bigdata-app"
IMAGE_NAME_SPARK="bigdata-spark"

APP_IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME_APP}:${IMAGE_TAG}"
APP_IMAGE_LATEST="gcr.io/${PROJECT_ID}/${IMAGE_NAME_APP}:latest"

SPARK_IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME_SPARK}:${IMAGE_TAG}"
SPARK_IMAGE_LATEST="gcr.io/${PROJECT_ID}/${IMAGE_NAME_SPARK}:latest"

log_info "Images:"
log_info "  App:   $APP_IMAGE"
log_info "  Spark: $SPARK_IMAGE"

# ==============================================================================
# BUILD
# ==============================================================================

log_info "Building Docker images..."

docker build -t ${APP_IMAGE} -f config/Dockerfile .

docker build -t ${SPARK_IMAGE} -f config/Dockerfile.spark .

log_success "Docker builds successful"

# Tag as latest
docker tag ${APP_IMAGE} ${APP_IMAGE_LATEST}
docker tag ${SPARK_IMAGE} ${SPARK_IMAGE_LATEST}

# ==============================================================================
# TEST
# ==============================================================================

log_info "Testing images..."

# Test Python
docker run --rm ${APP_IMAGE} python --version
if [ $? -ne 0 ]; then
    log_error "Python test failed"
    exit 1
fi

# Test dependencies
log_info "Checking app dependencies..."
docker run --rm ${APP_IMAGE} pip list | grep -E "confluent-kafka|pandas|hdfs|elasticsearch"

log_info "Checking spark image has spark-submit..."
docker run --rm ${SPARK_IMAGE} /opt/spark/bin/spark-submit --version | head -n 3

log_success "Image tests passed"

# ==============================================================================
# PUSH
# ==============================================================================

log_info "Pushing images to GCR..."

# Configure Docker to use gcloud
gcloud auth configure-docker gcr.io --quiet

for img in ${APP_IMAGE} ${APP_IMAGE_LATEST} ${SPARK_IMAGE} ${SPARK_IMAGE_LATEST}; do
  docker push ${img}
  if [ $? -eq 0 ]; then
      log_success "Pushed ${img}"
  else
      log_error "Push failed: ${img}"
      exit 1
  fi
done

# ==============================================================================
# VERIFY
# ==============================================================================

log_info "Verifying images in GCR..."
gcloud container images describe ${APP_IMAGE}
gcloud container images describe ${SPARK_IMAGE}

log_success "Images successfully built and pushed!"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Image Details:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "App:   ${APP_IMAGE}"
echo "App (latest):   ${APP_IMAGE_LATEST}"
echo "Spark: ${SPARK_IMAGE}"
echo "Spark (latest): ${SPARK_IMAGE_LATEST}"
echo ""
echo "🔧 Update K8s deployments:"
echo "   sed -i 's|PROJECT_ID|${PROJECT_ID}|g' k8s/*.yaml"
echo ""
echo "🚀 Deploy to GKE:"
echo "   ./scripts/deploy.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
