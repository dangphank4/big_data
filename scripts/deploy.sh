#!/bin/bash
# ==============================================================================
# SCRIPT TRIỂN KHAI TỰ ĐỘNG HỆ THỐNG BIG DATA LÊN GKE
# ==============================================================================

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

# ==============================================================================
# COLORS
# ==============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ==============================================================================
# FUNCTIONS
# ==============================================================================

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

wait_for_pods() {
    local label=$1
    local namespace=$2
    local timeout=${3:-600}
    
    log_info "Waiting for pods with label app=$label to be ready..."
    kubectl wait --for=condition=ready pod \
        -l app=$label \
        -n $namespace \
        --timeout=${timeout}s 2>&1 | grep -v "no matching resources" || true
    
    # Check if pods exist and are ready
    local ready_pods=$(kubectl get pods -n $namespace -l app=$label --no-headers 2>/dev/null | grep -c "Running" || echo "0")
    if [ "$ready_pods" -gt 0 ]; then
        log_success "Pods with label app=$label are ready"
    else
        log_warning "No pods found with label app=$label (might be StatefulSet or CronJob)"
    fi
}

wait_for_statefulset() {
    local name=$1
    local namespace=$2
    
    log_info "Waiting for StatefulSet $name to be ready..."
    kubectl rollout status statefulset/$name -n $namespace --timeout=10m
    log_success "StatefulSet $name is ready"
}

check_prerequisites() {
    log_step "CHECKING PREREQUISITES"
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl first."
        exit 1
    fi
    log_success "kubectl found: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"
    
    # Check gcloud
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud not found. Please install Google Cloud SDK first."
        exit 1
    fi
    log_success "gcloud found: $(gcloud version | head -n1)"
    
    # Check connection to cluster
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Please run 'gcloud container clusters get-credentials' first."
        exit 1
    fi
    log_success "Connected to cluster: $(kubectl config current-context)"
    
    # Check Docker images exist
    local project_id=$(gcloud config get-value project)
    log_info "Checking if Docker images exist in project: $project_id"
    
    if gcloud container images list --repository=gcr.io/$project_id 2>/dev/null | grep -q "bigdata-python-worker"; then
        log_success "Docker image found in GCR"
    else
        log_warning "Docker image not found in GCR. Please build and push first:"
        echo "  ./scripts/build-and-push.sh"
        read -p "Do you want to continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# ==============================================================================
# MAIN DEPLOYMENT FLOW
# ==============================================================================

main() {
    log_step "🚀 BIG DATA SYSTEM DEPLOYMENT TO GKE"
    
    # Variables
    NAMESPACE="bigdata"
    
    # Check prerequisites
    check_prerequisites
    
    # Step 1: Create Namespace
    log_step "📦 STEP 1: CREATING NAMESPACE"
    kubectl apply -f k8s/namespace.yaml
    kubectl config set-context --current --namespace=${NAMESPACE}
    log_success "Namespace created and set as default"
    
    # Step 2: Create ConfigMap
    log_step "⚙️  STEP 2: CREATING CONFIGMAP"
    kubectl apply -f k8s/configmap.yaml
    log_success "ConfigMap created"
    
    # Show ConfigMap
    log_info "ConfigMap contents:"
    kubectl get configmap bigdata-config -n ${NAMESPACE} -o yaml | grep -A 30 "data:"
    
    # Step 3: Create Persistent Volumes
    log_step "💾 STEP 3: CREATING PERSISTENT VOLUMES"
    kubectl apply -f k8s/persistent-volumes.yaml
    
    log_info "Waiting for PVCs to be bound..."
    sleep 15
    kubectl get pvc -n ${NAMESPACE}
    
    local unbound=$(kubectl get pvc -n ${NAMESPACE} --no-headers | grep -c "Pending" || echo "0")
    if [ "$unbound" -gt 0 ]; then
        log_warning "$unbound PVCs are still pending. This might be normal if cluster is provisioning disks."
    fi
    log_success "Persistent Volumes created"
    
    # Step 4: Deploy StatefulSets
    log_step "🗄️  STEP 4: DEPLOYING STATEFULSETS"
    
    # 4.1 Zookeeper
    log_info "Deploying Zookeeper..."
    kubectl apply -f k8s/zookeeper-statefulset.yaml
    wait_for_statefulset "zookeeper" ${NAMESPACE}
    
    # 4.2 Kafka
    log_info "Deploying Kafka..."
    kubectl apply -f k8s/kafka-statefulset.yaml
    wait_for_statefulset "kafka" ${NAMESPACE}
    
    # Verify Kafka is ready
    log_info "Verifying Kafka health..."
    sleep 10
    kubectl exec -it kafka-0 -n ${NAMESPACE} -- \
        kafka-topics --bootstrap-server localhost:9092 --list 2>&1 | head -5 || true
    
    # 4.3 HDFS NameNode
    log_info "Deploying HDFS NameNode..."
    kubectl apply -f k8s/hdfs-statefulset.yaml
    sleep 20  # Wait for NameNode to initialize
    kubectl wait --for=condition=ready pod -l app=hadoop-namenode -n ${NAMESPACE} --timeout=600s || true
    log_success "HDFS NameNode deployed"
    
    # 4.4 Elasticsearch
    log_info "Deploying Elasticsearch..."
    kubectl apply -f k8s/elasticsearch-statefulset.yaml
    wait_for_statefulset "elasticsearch" ${NAMESPACE}
    
    # Verify Elasticsearch health
    log_info "Verifying Elasticsearch health..."
    sleep 10
    kubectl exec -it elasticsearch-0 -n ${NAMESPACE} -- \
        curl -s -X GET "localhost:9200/_cluster/health?pretty" | grep status || true
    
    log_success "All StatefulSets deployed"
    
    # Step 5: Deploy Deployments
    log_step "🚢 STEP 5: DEPLOYING APPLICATIONS"
    
    # 5.1 Kibana
    log_info "Deploying Kibana..."
    kubectl apply -f k8s/kibana-deployment-updated.yaml
    wait_for_pods "kibana" ${NAMESPACE}
    
    # 5.2 Kafka Producer
    log_info "Deploying Kafka Producer..."
    kubectl apply -f k8s/kafka-producer-deployment.yaml
    wait_for_pods "kafka-producer" ${NAMESPACE}
    
    # 5.3 Kafka Consumer
    log_info "Deploying Kafka Consumer..."
    kubectl apply -f k8s/kafka-consumer-deployment.yaml
    wait_for_pods "kafka-consumer" ${NAMESPACE}
    
    # 5.4 Spark Streaming
    log_info "Deploying Spark Streaming..."
    kubectl apply -f k8s/spark-streaming-deployment.yaml
    wait_for_pods "spark-streaming" ${NAMESPACE}
    
    log_success "All applications deployed"
    
    # Step 6: Deploy CronJobs
    log_step "⏰ STEP 6: DEPLOYING BATCH JOBS"
    kubectl apply -f k8s/batch-job-cronjob.yaml
    log_success "Batch jobs configured"
    
    log_info "CronJob schedule:"
    kubectl get cronjob -n ${NAMESPACE}
    
    # Step 7: Deploy HPA
    log_step "📈 STEP 7: DEPLOYING HORIZONTAL POD AUTOSCALERS"
    kubectl apply -f k8s/hpa.yaml
    log_success "HPA configured"
    
    kubectl get hpa -n ${NAMESPACE}
    
    # Step 8: Deploy Network Policies
    log_step "🔒 STEP 8: DEPLOYING NETWORK POLICIES"
    kubectl apply -f k8s/network-policy.yaml
    log_success "Network policies applied"
    
    # Step 9: Deploy Ingress (Optional)
    log_step "🌐 STEP 9: INGRESS (OPTIONAL)"
    log_warning "Ingress is not deployed by default. To deploy:"
    log_info "  1. Reserve static IP: gcloud compute addresses create bigdata-static-ip --global"
    log_info "  2. Update domain in k8s/ingress.yaml"
    log_info "  3. Deploy: kubectl apply -f k8s/ingress.yaml"
    
    # Final status
    log_step "✅ DEPLOYMENT COMPLETED!"
    
    echo ""
    log_info "📊 DEPLOYMENT STATUS:"
    kubectl get all -n ${NAMESPACE}
    
    echo ""
    log_info "💾 PERSISTENT VOLUMES:"
    kubectl get pvc -n ${NAMESPACE}
    
    echo ""
    log_step "🎯 NEXT STEPS"
    echo ""
    echo "1️⃣  Check pod logs:"
    echo "   kubectl logs -f deployment/kafka-producer -n bigdata"
    echo ""
    echo "2️⃣  Access Kibana:"
    echo "   kubectl port-forward svc/kibana 5601:5601 -n bigdata"
    echo "   Then open: http://localhost:5601"
    echo ""
    echo "3️⃣  Access HDFS UI:"
    echo "   kubectl port-forward svc/hadoop-namenode 9870:9870 -n bigdata"
    echo "   Then open: http://localhost:9870"
    echo ""
    echo "4️⃣  Run manual batch job:"
    echo "   kubectl create job --from=cronjob/batch-processing batch-manual-1 -n bigdata"
    echo ""
    echo "5️⃣  Check Kafka topics:"
    echo "   kubectl exec -it kafka-0 -n bigdata -- kafka-topics --list --bootstrap-server localhost:9092"
    echo ""
    echo "6️⃣  Monitor with:"
    echo "   watch kubectl get pods -n bigdata"
    echo ""
    log_success "Deployment successful! 🎉"
}

# ==============================================================================
# RUN
# ==============================================================================

main "$@"
