#!/bin/bash
# GKE Quick Deploy Script
# Usage: ./deploy-gke.sh [setup|deploy|verify|teardown]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${PROJECT_ID:-bigdata-stock-$(date +%s)}"
REGION="${REGION:-asia-southeast1}"
ZONE="${ZONE:-asia-southeast1-a}"
CLUSTER_NAME="bigdata-cluster"
REGISTRY="gcr.io/$PROJECT_ID"

echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   GKE Big Data Deployment Helper          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"

# Function: Setup GCP Project & Cluster
setup_gcp() {
    echo -e "${YELLOW}[1/5] Setting up GCP Project...${NC}"
    
    # Create project
    gcloud projects create $PROJECT_ID --name="BigData Stock System" || true
    gcloud config set project $PROJECT_ID
    
    # Enable APIs
    echo -e "${YELLOW}[2/5] Enabling required APIs...${NC}"
    gcloud services enable container.googleapis.com
    gcloud services enable compute.googleapis.com
    gcloud services enable storage-api.googleapis.com
    
    # Note: User needs to manually link billing
    echo -e "${RED}⚠️  IMPORTANT: Link billing account manually:${NC}"
    echo "gcloud beta billing projects link $PROJECT_ID --billing-account=YOUR_ACCOUNT_ID"
    echo ""
    read -p "Press enter after billing is linked..."
    
    # Create GKE cluster
    echo -e "${YELLOW}[3/5] Creating GKE cluster (this takes ~5 minutes)...${NC}"
    gcloud container clusters create $CLUSTER_NAME \
        --region=$REGION \
        --num-nodes=3 \
        --machine-type=e2-standard-4 \
        --disk-size=50GB \
        --enable-autoscaling \
        --min-nodes=3 \
        --max-nodes=6 \
        --scopes=https://www.googleapis.com/auth/cloud-platform \
        || echo "Cluster already exists"
    
    # Get credentials
    echo -e "${YELLOW}[4/5] Getting cluster credentials...${NC}"
    gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION
    
    # Verify
    echo -e "${YELLOW}[5/5] Verifying cluster...${NC}"
    kubectl get nodes
    
    echo -e "${GREEN}✅ GCP setup completed!${NC}"
}

# Function: Build and Push Images
build_images() {
    echo -e "${YELLOW}[1/3] Configuring Docker for GCR...${NC}"
    gcloud auth configure-docker
    
    echo -e "${YELLOW}[2/3] Building Docker images...${NC}"
    docker build -t $REGISTRY/stock-producer:latest -f config/Dockerfile .
    docker build -t $REGISTRY/spark-streaming:latest -f config/Dockerfile.spark .
    docker build -t $REGISTRY/spark-batch:latest -f config/Dockerfile.spark .
    
    echo -e "${YELLOW}[3/3] Pushing images to GCR...${NC}"
    docker push $REGISTRY/stock-producer:latest
    docker push $REGISTRY/spark-streaming:latest
    docker push $REGISTRY/spark-batch:latest
    
    echo -e "${GREEN}✅ Images built and pushed!${NC}"
}

# Function: Update K8s manifests
update_manifests() {
    echo -e "${YELLOW}Updating image references in K8s manifests...${NC}"
    
    # Backup originals
    mkdir -p deployment/k8s-backup
    find deployment/k8s -name "*.yaml" -type f -exec cp {} deployment/k8s-backup/ \;
    
    # Replace image names
    find deployment/k8s -name "*.yaml" -type f -exec sed -i.bak \
        "s|image: config-\([^:]*\)|image: $REGISTRY/\1:latest|g" {} \;
    
    # Remove backup files
    find deployment/k8s -name "*.bak" -delete
    
    echo -e "${GREEN}✅ Manifests updated!${NC}"
}

# Function: Deploy to K8s
deploy_k8s() {
    echo -e "${YELLOW}[1/6] Deploying Namespace & ConfigMap...${NC}"
    kubectl apply -f deployment/k8s/00-namespace/
    kubectl apply -f deployment/k8s/01-config/
    
    echo -e "${YELLOW}[2/6] Creating PersistentVolumeClaims...${NC}"
    kubectl apply -f deployment/k8s/02-storage/persistent-volumes-gke.yaml
    sleep 5
    
    echo -e "${YELLOW}[3/6] Deploying Infrastructure Services...${NC}"
    kubectl apply -f deployment/k8s/03-infrastructure/zookeeper-statefulset.yaml
    sleep 10
    kubectl wait --for=condition=ready pod -l app=zookeeper -n bigdata --timeout=300s || true
    
    kubectl apply -f deployment/k8s/03-infrastructure/kafka-statefulset.yaml
    sleep 10
    kubectl wait --for=condition=ready pod -l app=kafka -n bigdata --timeout=300s || true
    
    kubectl apply -f deployment/k8s/03-infrastructure/hdfs-statefulset.yaml
    sleep 10
    kubectl wait --for=condition=ready pod -l app=hdfs-namenode -n bigdata --timeout=300s || true
    
    kubectl apply -f deployment/k8s/03-infrastructure/elasticsearch-statefulset.yaml
    sleep 10
    kubectl wait --for=condition=ready pod -l app=elasticsearch -n bigdata --timeout=300s || true
    
    echo -e "${YELLOW}[4/6] Deploying Kibana...${NC}"
    kubectl apply -f deployment/k8s/04-applications/kibana-deployment-updated.yaml
    
    echo -e "${YELLOW}[5/6] Deploying Application Services...${NC}"
    kubectl apply -f deployment/k8s/04-applications/kafka-producer-crawl-deployment.yaml
    kubectl apply -f deployment/k8s/04-applications/spark-streaming-consumer-deployment.yaml
    kubectl apply -f deployment/k8s/04-applications/spark-alerts-deployment.yaml
    
    echo -e "${YELLOW}[6/6] Deploying CronJobs...${NC}"
    kubectl apply -f deployment/k8s/05-jobs/hdfs-archiver-cronjob.yaml
    kubectl apply -f deployment/k8s/05-jobs/spark-batch-features-cronjob.yaml
    
    echo -e "${GREEN}✅ All services deployed!${NC}"
}

# Function: Verify Deployment
verify_deployment() {
    echo -e "${YELLOW}Checking deployment status...${NC}"
    
    echo -e "\n${GREEN}=== PODS ===${NC}"
    kubectl get pods -n bigdata -o wide
    
    echo -e "\n${GREEN}=== SERVICES ===${NC}"
    kubectl get svc -n bigdata
    
    echo -e "\n${GREEN}=== PERSISTENT VOLUME CLAIMS ===${NC}"
    kubectl get pvc -n bigdata
    
    echo -e "\n${GREEN}=== CRONJOBS ===${NC}"
    kubectl get cronjobs -n bigdata
    
    echo -e "\n${YELLOW}Checking Kafka topics...${NC}"
    kubectl exec -it kafka-0 -n bigdata -- kafka-topics --list --bootstrap-server localhost:9092 || true
    
    echo -e "\n${YELLOW}Port-forwarding Kibana to localhost:5601...${NC}"
    echo -e "${GREEN}Run this in another terminal:${NC}"
    echo "kubectl port-forward svc/kibana 5601:5601 -n bigdata"
    echo ""
    echo -e "${GREEN}Then open: http://localhost:5601${NC}"
}

# Function: Teardown
teardown() {
    echo -e "${RED}⚠️  WARNING: This will delete all resources!${NC}"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        echo "Cancelled."
        exit 0
    fi
    
    echo -e "${YELLOW}[1/3] Deleting Kubernetes resources...${NC}"
    kubectl delete namespace bigdata || true
    
    echo -e "${YELLOW}[2/3] Deleting GKE cluster...${NC}"
    gcloud container clusters delete $CLUSTER_NAME --region=$REGION --quiet || true
    
    echo -e "${YELLOW}[3/3] Deleting images from GCR...${NC}"
    gcloud container images delete $REGISTRY/stock-producer:latest --quiet || true
    gcloud container images delete $REGISTRY/spark-streaming:latest --quiet || true
    gcloud container images delete $REGISTRY/spark-batch:latest --quiet || true
    
    echo -e "${GREEN}✅ Teardown completed!${NC}"
    echo -e "${YELLOW}Note: Project $PROJECT_ID still exists. Delete manually if needed:${NC}"
    echo "gcloud projects delete $PROJECT_ID"
}

# Main
case "$1" in
    setup)
        setup_gcp
        ;;
    build)
        build_images
        ;;
    update)
        update_manifests
        ;;
    deploy)
        deploy_k8s
        ;;
    verify)
        verify_deployment
        ;;
    teardown)
        teardown
        ;;
    all)
        setup_gcp
        build_images
        update_manifests
        deploy_k8s
        verify_deployment
        ;;
    *)
        echo "Usage: $0 {setup|build|update|deploy|verify|teardown|all}"
        echo ""
        echo "Commands:"
        echo "  setup     - Create GCP project and GKE cluster"
        echo "  build     - Build and push Docker images to GCR"
        echo "  update    - Update K8s manifests with GCR image references"
        echo "  deploy    - Deploy all services to GKE"
        echo "  verify    - Check deployment status"
        echo "  teardown  - Delete all resources"
        echo "  all       - Run all steps (setup → build → update → deploy → verify)"
        echo ""
        echo "Environment variables:"
        echo "  PROJECT_ID  - GCP project ID (default: bigdata-stock-TIMESTAMP)"
        echo "  REGION      - GCP region (default: asia-southeast1)"
        exit 1
        ;;
esac
