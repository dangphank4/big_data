#!/bin/bash
# ==============================================================================
# CREATE GKE CLUSTER
# ==============================================================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# ==============================================================================
# CONFIGURATION
# ==============================================================================

PROJECT_ID=$(gcloud config get-value project)
CLUSTER_NAME=${1:-"bigdata-cluster"}
REGION=${2:-"asia-southeast1"}
ZONE="${REGION}-a"
MACHINE_TYPE="n1-standard-4"
NUM_NODES=3
MIN_NODES=3
MAX_NODES=10
CLUSTER_TYPE=${3:-"standard"}  # standard, preemptible, autopilot

log_info "Configuration:"
echo "  Project: $PROJECT_ID"
echo "  Cluster: $CLUSTER_NAME"
echo "  Region: $REGION"
echo "  Zone: $ZONE"
echo "  Type: $CLUSTER_TYPE"
echo ""

read -p "Continue with these settings? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# ==============================================================================
# CREATE CLUSTER
# ==============================================================================

if [ "$CLUSTER_TYPE" == "autopilot" ]; then
    log_info "Creating Autopilot cluster (serverless)..."
    
    gcloud container clusters create-auto ${CLUSTER_NAME} \
        --region=${REGION} \
        --release-channel=regular \
        --project=${PROJECT_ID}
    
elif [ "$CLUSTER_TYPE" == "preemptible" ]; then
    log_info "Creating cluster with preemptible nodes (60-70% cheaper)..."
    
    gcloud container clusters create ${CLUSTER_NAME} \
        --zone=${ZONE} \
        --machine-type=${MACHINE_TYPE} \
        --num-nodes=${NUM_NODES} \
        --preemptible \
        --disk-size=50 \
        --disk-type=pd-standard \
        --enable-autoscaling \
        --min-nodes=2 \
        --max-nodes=5 \
        --enable-autorepair \
        --no-enable-autoupgrade \
        --project=${PROJECT_ID}
    
else
    log_info "Creating standard production cluster..."
    
    gcloud container clusters create ${CLUSTER_NAME} \
        --zone=${ZONE} \
        --machine-type=${MACHINE_TYPE} \
        --num-nodes=${NUM_NODES} \
        --enable-autoscaling \
        --min-nodes=${MIN_NODES} \
        --max-nodes=${MAX_NODES} \
        --enable-autorepair \
        --enable-autoupgrade \
        --disk-size=100 \
        --disk-type=pd-ssd \
        --enable-ip-alias \
        --network="default" \
        --subnetwork="default" \
        --enable-stackdriver-kubernetes \
        --addons=HorizontalPodAutoscaling,HttpLoadBalancing,GcePersistentDiskCsiDriver \
        --workload-pool=${PROJECT_ID}.svc.id.goog \
        --enable-shielded-nodes \
        --release-channel=regular \
        --project=${PROJECT_ID}
fi

log_success "Cluster created!"

# ==============================================================================
# GET CREDENTIALS
# ==============================================================================

log_info "Getting cluster credentials..."

if [ "$CLUSTER_TYPE" == "autopilot" ]; then
    gcloud container clusters get-credentials ${CLUSTER_NAME} --region=${REGION}
else
    gcloud container clusters get-credentials ${CLUSTER_NAME} --zone=${ZONE}
fi

# ==============================================================================
# VERIFY
# ==============================================================================

log_info "Verifying cluster..."
kubectl cluster-info
echo ""
kubectl get nodes
echo ""

log_success "Cluster is ready!"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Build and push Docker image:"
echo "   ./scripts/build-and-push.sh"
echo ""
echo "2. Update PROJECT_ID in K8s files:"
echo "   sed -i 's/PROJECT_ID/${PROJECT_ID}/g' k8s/*.yaml"
echo ""
echo "3. Deploy the system:"
echo "   ./scripts/deploy.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
