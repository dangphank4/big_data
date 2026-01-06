# 🚀 HƯỚNG DẪN TRIỂN KHAI HỆ THỐNG BIG DATA LÊN GOOGLE KUBERNETES ENGINE (GKE)

## 📋 MỤC LỤC

1. [Tổng quan hệ thống](#tổng-quan-hệ-thống)
2. [Kiến trúc Lambda Architecture](#kiến-trúc-lambda-architecture)
3. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
4. [Chuẩn bị môi trường](#chuẩn-bị-môi-trường)
5. [Build và Push Docker Images](#build-và-push-docker-images)
6. [Tạo GKE Cluster](#tạo-gke-cluster)
7. [Triển khai hệ thống](#triển-khai-hệ-thống)
8. [Kiểm tra và Giám sát](#kiểm-tra-và-giám-sát)
9. [Troubleshooting](#troubleshooting)
10. [Tối ưu hóa chi phí](#tối-ưu-hóa-chi-phí)
11. [Bảo mật Production](#bảo-mật-production)

---

## 📊 TỔNG QUAN HỆ THỐNG

### Mô tả dự án

Hệ thống phân tích dữ liệu chứng khoán real-time và batch processing sử dụng Lambda Architecture.

### Các thành phần chính:

#### 1. **Batch Layer** (Cold Path)

- **Mục đích**: Xử lý dữ liệu lịch sử, tính toán các chỉ số kỹ thuật phức tạp
- **Công nghệ**: Python + Pandas + Batch Jobs
- **Storage**: HDFS + Elasticsearch
- **Tần suất**: Chạy hàng ngày (2h sáng)
- **Batch Jobs**:
  - `batch_trend.py`: Phân tích xu hướng dài hạn (MA50, MA100, MA200)
  - `drawdown.py`: Tính toán độ sụt giảm tối đa
  - `cumulative_return.py`: Tính lợi nhuận tích lũy
  - `volume_features.py`: Phân tích khối lượng giao dịch
  - `market_regime.py`: Phát hiện chế độ thị trường
  - `monthly.py`: Tính toán chỉ số theo tháng

#### 2. **Speed Layer** (Hot Path)

- **Mục đích**: Xử lý dữ liệu streaming real-time
- **Luồng dữ liệu**:
  ```
  Kafka Producer → Kafka → Spark Streaming → Elasticsearch
                     ↓
                 Kafka Consumer → HDFS
  ```
- **Công nghệ**: Apache Kafka, Spark Structured Streaming
- **Độ trễ**: < 30 giây
- **Metrics real-time**:
  - Giá trung bình theo cửa sổ thời gian
  - Khối lượng giao dịch tổng hợp
  - Độ biến động giá (volatility)
  - Min/Max giá trong cửa sổ

#### 3. **Serving Layer**

- **Visualization**: Kibana
- **Query Engine**: Elasticsearch
- **Data Lake**: HDFS (Hadoop)

### Kiến trúc triển khai:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Google Cloud Platform                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                 Google Kubernetes Engine (GKE)            │  │
│  │                                                           │  │
│  │  ┌──────────────┐      ┌──────────────┐                 │  │
│  │  │   Zookeeper  │◄─────┤    Kafka     │                 │  │
│  │  │ (StatefulSet)│      │ (StatefulSet)│                 │  │
│  │  └──────────────┘      └──────┬───────┘                 │  │
│  │                               │                          │  │
│  │  ┌──────────────┐      ┌──────▼───────┐                 │  │
│  │  │Kafka Producer├─────►│Kafka Consumer│                 │  │
│  │  │ (Deployment) │      │ (Deployment) │                 │  │
│  │  └──────────────┘      └──────┬───────┘                 │  │
│  │                               │                          │  │
│  │  ┌──────────────┐      ┌──────▼───────┐                 │  │
│  │  │    Spark     │      │     HDFS     │                 │  │
│  │  │  Streaming   ├─────►│  NameNode    │                 │  │
│  │  │ (Deployment) │      │  DataNode    │                 │  │
│  │  └──────┬───────┘      │(StatefulSets)│                 │  │
│  │         │              └──────────────┘                 │  │
│  │         │                                               │  │
│  │  ┌──────▼───────┐      ┌──────────────┐                 │  │
│  │  │Elasticsearch │◄─────┤    Kibana    │                 │  │
│  │  │(StatefulSet) │      │ (Deployment) │                 │  │
│  │  └──────────────┘      └──────────────┘                 │  │
│  │         ▲                                               │  │
│  │         │                                               │  │
│  │  ┌──────┴───────┐                                       │  │
│  │  │Batch Jobs    │                                       │  │
│  │  │  (CronJob)   │                                       │  │
│  │  └──────────────┘                                       │  │
│  │                                                           │  │
│  │  Persistent Volumes: GCE Persistent Disks               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Load Balancer → Ingress → Services                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 KIẾN TRÚC LAMBDA ARCHITECTURE

### Tại sao sử dụng Lambda Architecture?

#### Batch Layer (Cold Path)

**Ưu điểm:**

- Xử lý toàn bộ dữ liệu lịch sử với độ chính xác cao
- Tính toán các chỉ số phức tạp không thể làm real-time
- Chi phí xử lý thấp (chỉ chạy 1 lần/ngày)
- Fault-tolerant: Có thể recompute nếu lỗi

**Use cases:**

- Moving averages dài hạn (MA200)
- Cumulative returns toàn bộ lịch sử
- Market regime detection
- Monthly aggregations

#### Speed Layer (Hot Path)

**Ưu điểm:**

- Độ trễ thấp (< 30 giây)
- Real-time monitoring
- Immediate insights
- Event-driven processing

**Use cases:**

- Real-time price monitoring
- Volume spikes detection
- Price volatility alerts
- Live trading signals

#### Serving Layer

**Vai trò:**

- Merge batch views + real-time views
- Cung cấp unified query interface
- Balance between accuracy (batch) and latency (streaming)

### So sánh với các kiến trúc khác:

| Tiêu chí     | Lambda     | Kappa         | Batch-only        |
| ------------ | ---------- | ------------- | ----------------- |
| Độ phức tạp  | Cao        | Trung bình    | Thấp              |
| Real-time    | ✅ Tốt     | ✅ Tốt        | ❌ Không          |
| Độ chính xác | ✅ Cao     | ⚠️ Phụ thuộc  | ✅ Cao            |
| Chi phí      | Trung bình | Cao           | Thấp              |
| Use case     | Cần cả 2   | Chỉ streaming | Analytics offline |

**Kết luận**: Lambda Architecture phù hợp với dự án này vì:

1. Cần real-time monitoring (Speed Layer)
2. Cần tính toán chính xác dữ liệu lịch sử (Batch Layer)
3. Cần balance giữa latency và accuracy

---

## ✅ YÊU CẦU HỆ THỐNG

### Local Development Machine

- **OS**: Windows/Linux/macOS
- **RAM**: Tối thiểu 8GB, khuyến nghị 16GB
- **Storage**: 20GB trống
- **Software**:
  - Docker Desktop (hoặc Docker Engine)
  - Google Cloud SDK (gcloud CLI)
  - kubectl
  - Git

### Google Cloud Platform

- **GCP Account** với billing enabled
- **Project ID** đã tạo sẵn
- **APIs cần enable**:
  - Kubernetes Engine API
  - Container Registry API (hoặc Artifact Registry API)
  - Compute Engine API
  - Cloud Build API (optional, để CI/CD)

### GKE Cluster Specs (Khuyến nghị cho Production)

- **Node Pool**:
  - Machine type: `n1-standard-4` (4 vCPU, 15GB RAM)
  - Số nodes: 3-5 nodes
  - Auto-scaling: enabled (min: 3, max: 10)
- **Disk**:
  - Boot disk: 100GB SSD
  - Persistent volumes: SSD persistent disks
- **Network**: VPC-native cluster với IP aliasing
- **Region**: Chọn gần nhất (ví dụ: `asia-southeast1` cho Việt Nam)

### Ước tính chi phí (US Regions)

- **GKE Cluster**: ~$200-400/tháng (3-5 nodes n1-standard-4)
- **Persistent Disks**: ~$20-50/tháng (250GB total)
- **Load Balancer**: ~$18/tháng
- **Network egress**: Biến đổi
- **Tổng ước tính**: $250-500/tháng

> 💡 **Tip**: Sử dụng Preemptible VMs để giảm 60-70% chi phí cho môi trường dev/test

---

## 🔧 CHUẨN BỊ MÔI TRƯỜNG

### Bước 1: Cài đặt công cụ cần thiết

#### 1.1. Google Cloud SDK

```bash
# Linux/macOS
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Windows: Download từ
# https://cloud.google.com/sdk/docs/install

# Verify
gcloud version
```

#### 1.2. Kubectl

```bash
# Install qua gcloud
gcloud components install kubectl

# Hoặc cài standalone
# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# macOS
brew install kubectl

# Windows
choco install kubernetes-cli

# Verify
kubectl version --client
```

#### 1.3. Docker

```bash
# Verify Docker
docker --version
docker-compose --version
```

### Bước 2: Cấu hình GCP Project

```bash
# Login to GCP
gcloud auth login

# Set project (Thay YOUR_PROJECT_ID)
export PROJECT_ID="your-bigdata-project-123"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable container.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Configure Docker to use gcloud as credential helper
gcloud auth configure-docker
gcloud auth configure-docker gcr.io

# Verify
gcloud config list
```

### Bước 3: Chuẩn bị source code

```bash
# Clone repository (nếu từ Git)
git clone <your-repo-url>
cd big_data

# Hoặc nếu đã có local
cd /path/to/big_data

# Verify structure
ls -la
# Phải thấy: Dockerfile, docker-compose.yml, k8s/, batch_jobs/, etc.
```

---

## 🐳 BUILD VÀ PUSH DOCKER IMAGES

### Bước 1: Build Python Worker Image

```bash
# Set variables
export PROJECT_ID="your-bigdata-project-123"  # THAY ĐỔI
export IMAGE_NAME="bigdata-python-worker"
export IMAGE_TAG="v1.0.0"
export FULL_IMAGE_NAME="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${IMAGE_TAG}"

# Build image
docker build -t ${FULL_IMAGE_NAME} -f Dockerfile .

# Test image locally (optional)
docker run --rm ${FULL_IMAGE_NAME} python --version
docker run --rm ${FULL_IMAGE_NAME} pip list

# Push to Google Container Registry
docker push ${FULL_IMAGE_NAME}

# Tag as latest
docker tag ${FULL_IMAGE_NAME} gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest
docker push gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest

# Verify
gcloud container images list --repository=gcr.io/${PROJECT_ID}
gcloud container images describe ${FULL_IMAGE_NAME}
```

### Bước 2: Tạo ConfigMap cho Spark code

Spark Streaming cần mount source code vào container. Ta sẽ tạo ConfigMap:

```bash
# Tạo ConfigMap từ file
kubectl create configmap spark-app-code \
  --from-file=spark_streaming/spark_streaming_simple.py \
  --from-file=standardization_local.py \
  --namespace=bigdata \
  --dry-run=client -o yaml > k8s/spark-code-configmap.yaml

# Hoặc thủ công tạo file (xem phần sau)
```

### Bước 3: Update image name trong K8s manifests

```bash
# Replace PROJECT_ID trong tất cả deployment files
cd k8s
sed -i "s/PROJECT_ID/${PROJECT_ID}/g" kafka-producer-deployment.yaml
sed -i "s/PROJECT_ID/${PROJECT_ID}/g" kafka-consumer-deployment.yaml
sed -i "s/PROJECT_ID/${PROJECT_ID}/g" batch-job-cronjob.yaml

# Verify
grep "gcr.io" *.yaml
```

---

## ☸️ TẠO GKE CLUSTER

### Phương án 1: Standard Cluster (Khuyến nghị cho Production)

```bash
# Set variables
export CLUSTER_NAME="bigdata-cluster"
export REGION="asia-southeast1"  # Hoặc us-central1, europe-west1
export ZONE="${REGION}-a"
export MACHINE_TYPE="n1-standard-4"
export NUM_NODES=3
export MIN_NODES=3
export MAX_NODES=10

# Create GKE cluster
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
  --release-channel=regular

# Tạo cluster mất ~5-10 phút
```

### Phương án 2: Preemptible Nodes (Dev/Test - Tiết kiệm 60-70%)

```bash
gcloud container clusters create ${CLUSTER_NAME}-dev \
  --zone=${ZONE} \
  --machine-type=n1-standard-4 \
  --num-nodes=3 \
  --preemptible \
  --disk-size=50 \
  --disk-type=pd-standard \
  --enable-autoscaling \
  --min-nodes=2 \
  --max-nodes=5 \
  --no-enable-autoupgrade
```

### Phương án 3: Autopilot Cluster (Serverless K8s)

```bash
# GKE Autopilot - Google quản lý toàn bộ infrastructure
gcloud container clusters create-auto ${CLUSTER_NAME}-autopilot \
  --region=${REGION} \
  --release-channel=regular

# Ưu điểm: Không cần quản lý nodes, auto-scaling tốt hơn
# Nhược điểm: Một số features bị hạn chế (StatefulSets phức tạp)
```

### Sau khi tạo cluster

```bash
# Get credentials
gcloud container clusters get-credentials ${CLUSTER_NAME} --zone=${ZONE}

# Verify connection
kubectl cluster-info
kubectl get nodes
kubectl get namespaces

# Expected output: 3 nodes READY
```

### Tạo Static IP cho Ingress (Optional)

```bash
# Reserve static IP
gcloud compute addresses create bigdata-static-ip \
  --global \
  --ip-version IPV4

# Get IP address
gcloud compute addresses describe bigdata-static-ip --global

# Note down the IP address - Sẽ dùng cho DNS và Ingress
```

---

## 🚀 TRIỂN KHAI HỆ THỐNG

### Thứ tự triển khai (QUAN TRỌNG!)

Phải tuân thủ thứ tự sau để tránh dependency issues:

```
1. Namespace & ConfigMap
2. Persistent Volumes
3. StatefulSets (Zookeeper → Kafka → HDFS → Elasticsearch)
4. Deployments (Kibana → Python workers → Spark)
5. Jobs & CronJobs
6. Ingress & Services
7. HPA & Network Policies
```

### Script triển khai tự động

Tạo file `deploy.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Starting Big Data System Deployment to GKE..."

# Variables
NAMESPACE="bigdata"
KUBECTL="kubectl"

# Function to wait for pods
wait_for_pods() {
  local label=$1
  local count=$2
  local namespace=$3

  echo "⏳ Waiting for $label pods to be ready..."
  ${KUBECTL} wait --for=condition=ready pod \
    -l app=$label \
    -n $namespace \
    --timeout=600s || true
}

# Function to check statefulset
wait_for_statefulset() {
  local name=$1
  local namespace=$2

  echo "⏳ Waiting for StatefulSet $name..."
  ${KUBECTL} rollout status statefulset/$name -n $namespace --timeout=10m
}

# Step 1: Create Namespace
echo "📦 Step 1: Creating namespace..."
${KUBECTL} apply -f k8s/namespace.yaml
${KUBECTL} config set-context --current --namespace=${NAMESPACE}

# Step 2: Create ConfigMap
echo "⚙️  Step 2: Creating ConfigMap..."
${KUBECTL} apply -f k8s/configmap.yaml

# Step 3: Create Persistent Volumes
echo "💾 Step 3: Creating Persistent Volumes..."
${KUBECTL} apply -f k8s/persistent-volumes.yaml

# Wait for PVCs to be bound
echo "⏳ Waiting for PVCs..."
sleep 10
${KUBECTL} get pvc -n ${NAMESPACE}

# Step 4: Deploy StatefulSets (in order)
echo "🗄️  Step 4: Deploying StatefulSets..."

echo "  → Deploying Zookeeper..."
${KUBECTL} apply -f k8s/zookeeper-statefulset.yaml
wait_for_statefulset "zookeeper" ${NAMESPACE}

echo "  → Deploying Kafka..."
${KUBECTL} apply -f k8s/kafka-statefulset.yaml
wait_for_statefulset "kafka" ${NAMESPACE}

echo "  → Deploying HDFS NameNode..."
${KUBECTL} apply -f k8s/hdfs-statefulset.yaml
sleep 20  # Wait for NameNode to initialize
${KUBECTL} wait --for=condition=ready pod -l app=hadoop-namenode -n ${NAMESPACE} --timeout=300s

echo "  → Deploying Elasticsearch..."
${KUBECTL} apply -f k8s/elasticsearch-statefulset.yaml
wait_for_statefulset "elasticsearch" ${NAMESPACE}

# Step 5: Deploy Deployments
echo "🚢 Step 5: Deploying Applications..."

echo "  → Deploying Kibana..."
${KUBECTL} apply -f k8s/kibana-deployment-updated.yaml
wait_for_pods "kibana" 1 ${NAMESPACE}

echo "  → Deploying Kafka Producer..."
${KUBECTL} apply -f k8s/kafka-producer-deployment.yaml
wait_for_pods "kafka-producer" 1 ${NAMESPACE}

echo "  → Deploying Kafka Consumer..."
${KUBECTL} apply -f k8s/kafka-consumer-deployment.yaml
wait_for_pods "kafka-consumer" 1 ${NAMESPACE}

echo "  → Deploying Spark Streaming..."
${KUBECTL} apply -f k8s/spark-streaming-deployment.yaml
wait_for_pods "spark-streaming" 1 ${NAMESPACE}

# Step 6: Deploy CronJobs
echo "⏰ Step 6: Deploying Batch Jobs..."
${KUBECTL} apply -f k8s/batch-job-cronjob.yaml

# Step 7: Deploy HPA
echo "📈 Step 7: Deploying Horizontal Pod Autoscalers..."
${KUBECTL} apply -f k8s/hpa.yaml

# Step 8: Deploy Network Policies
echo "🔒 Step 8: Deploying Network Policies..."
${KUBECTL} apply -f k8s/network-policy.yaml

# Step 9: Deploy Ingress (if using)
echo "🌐 Step 9: Deploying Ingress..."
# ${KUBECTL} apply -f k8s/ingress.yaml  # Uncomment if using

echo ""
echo "✅ Deployment completed!"
echo ""
echo "📊 Checking deployment status..."
${KUBECTL} get all -n ${NAMESPACE}
echo ""
echo "💾 Persistent Volumes:"
${KUBECTL} get pvc -n ${NAMESPACE}
echo ""
echo "🎯 Next steps:"
echo "  1. Check logs: kubectl logs -f <pod-name> -n bigdata"
echo "  2. Access Kibana: kubectl port-forward svc/kibana 5601:5601 -n bigdata"
echo "  3. Access HDFS UI: kubectl port-forward svc/hadoop-namenode 9870:9870 -n bigdata"
echo "  4. Run manual batch job: kubectl create job --from=cronjob/batch-processing batch-manual-1 -n bigdata"
```

### Triển khai

```bash
# Make executable
chmod +x deploy.sh

# Run deployment
./deploy.sh

# Monitor deployment
watch kubectl get pods -n bigdata
```

### Triển khai thủ công (từng bước)

Nếu muốn kiểm soát chi tiết:

```bash
# 1. Namespace
kubectl apply -f k8s/namespace.yaml
kubectl config set-context --current --namespace=bigdata

# 2. ConfigMap
kubectl apply -f k8s/configmap.yaml

# 3. PVCs
kubectl apply -f k8s/persistent-volumes.yaml
kubectl get pvc

# 4. Zookeeper
kubectl apply -f k8s/zookeeper-statefulset.yaml
kubectl rollout status statefulset/zookeeper

# 5. Kafka
kubectl apply -f k8s/kafka-statefulset.yaml
kubectl rollout status statefulset/kafka

# 6. HDFS
kubectl apply -f k8s/hdfs-statefulset.yaml
kubectl rollout status statefulset/hadoop-namenode
kubectl rollout status statefulset/hadoop-datanode

# 7. Elasticsearch
kubectl apply -f k8s/elasticsearch-statefulset.yaml
kubectl rollout status statefulset/elasticsearch

# 8. Kibana
kubectl apply -f k8s/kibana-deployment-updated.yaml
kubectl rollout status deployment/kibana

# 9. Kafka Producer
kubectl apply -f k8s/kafka-producer-deployment.yaml

# 10. Kafka Consumer
kubectl apply -f k8s/kafka-consumer-deployment.yaml

# 11. Spark Streaming
kubectl apply -f k8s/spark-streaming-deployment.yaml

# 12. Batch Jobs
kubectl apply -f k8s/batch-job-cronjob.yaml

# 13. HPA
kubectl apply -f k8s/hpa.yaml

# 14. Network Policies
kubectl apply -f k8s/network-policy.yaml
```

---

## 🔍 KIỂM TRA VÀ GIÁM SÁT

### 1. Kiểm tra trạng thái pods

```bash
# All pods
kubectl get pods -n bigdata

# Wide view (includes nodes)
kubectl get pods -n bigdata -o wide

# Watch mode
watch kubectl get pods -n bigdata

# Expected: All pods STATUS = Running
```

### 2. Kiểm tra logs

```bash
# Kafka Producer logs
kubectl logs -f deployment/kafka-producer -n bigdata

# Kafka Consumer logs
kubectl logs -f deployment/kafka-consumer -n bigdata

# Spark Streaming logs
kubectl logs -f deployment/spark-streaming -n bigdata

# Batch job logs (latest)
kubectl logs job/batch-processing-manual -n bigdata

# Multiple pods
kubectl logs -l app=kafka-producer -n bigdata --tail=100
```

### 3. Access các UI

#### 3.1. Kibana (Visualization)

```bash
# Port forward
kubectl port-forward svc/kibana 5601:5601 -n bigdata

# Open browser: http://localhost:5601

# Tạo Index Pattern:
# 1. Go to Management → Stack Management → Index Patterns
# 2. Create index pattern: stock_realtime*
# 3. Time field: @timestamp
# 4. Create visualizations and dashboards
```

#### 3.2. HDFS NameNode UI

```bash
# Port forward
kubectl port-forward svc/hadoop-namenode 9870:9870 -n bigdata

# Open browser: http://localhost:9870
# Check: Datanodes, file system, blocks
```

#### 3.3. Elasticsearch API

```bash
# Port forward
kubectl port-forward svc/elasticsearch 9200:9200 -n bigdata

# Check cluster health
curl http://localhost:9200/_cluster/health?pretty

# List indices
curl http://localhost:9200/_cat/indices?v

# Query data
curl -X GET "http://localhost:9200/stock_realtime/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match_all": {}
  },
  "size": 10,
  "sort": [{"@timestamp": "desc"}]
}'
```

### 4. Kiểm tra Kafka

```bash
# Exec into Kafka pod
kubectl exec -it kafka-0 -n bigdata -- bash

# List topics
kafka-topics --list --bootstrap-server localhost:9092

# Describe topic
kafka-topics --describe --topic stocks-history --bootstrap-server localhost:9092

# Consume messages (test)
kafka-console-consumer --topic stocks-history \
  --bootstrap-server localhost:9092 \
  --from-beginning \
  --max-messages 10

# Check consumer groups
kafka-consumer-groups --list --bootstrap-server localhost:9092

# Describe consumer group
kafka-consumer-groups --describe --group hdfs-writer-group-v1 --bootstrap-server localhost:9092
```

### 5. Kiểm tra HDFS

```bash
# Exec into NameNode
kubectl exec -it hadoop-namenode-0 -n bigdata -- bash

# List files
hdfs dfs -ls /
hdfs dfs -ls /user/kafka_data/stocks_history/
hdfs dfs -ls /user/spark_checkpoints/

# Check disk usage
hdfs dfs -du -h /user/

# Check file content
hdfs dfs -cat /tmp/serving/batch_features.json | head -n 10

# File system check
hdfs fsck / -files -blocks
```

### 6. Chạy batch job thủ công

```bash
# Create job from cronjob
kubectl create job --from=cronjob/batch-processing batch-manual-test -n bigdata

# Watch job
kubectl get jobs -n bigdata -w

# Check logs
kubectl logs job/batch-manual-test -n bigdata

# Delete completed job
kubectl delete job batch-manual-test -n bigdata
```

### 7. Monitoring với kubectl top

```bash
# Node resources
kubectl top nodes

# Pod resources
kubectl top pods -n bigdata

# Specific pod
kubectl top pod kafka-0 -n bigdata --containers
```

### 8. Check HPA status

```bash
# HPA status
kubectl get hpa -n bigdata

# Describe HPA
kubectl describe hpa kafka-producer-hpa -n bigdata

# Expected: Current replicas scaling based on CPU/Memory
```

---

## 🛠️ TROUBLESHOOTING

### 1. Pod không start (Pending)

```bash
# Check pod events
kubectl describe pod <pod-name> -n bigdata

# Common issues:
# - Insufficient resources: Scale cluster
# - PVC not bound: Check PVC status
# - Image pull error: Check image name và registry auth
```

**Solution - Insufficient resources:**

```bash
# Scale cluster
gcloud container clusters resize ${CLUSTER_NAME} \
  --num-nodes=5 \
  --zone=${ZONE}
```

**Solution - PVC not bound:**

```bash
# Check PVC
kubectl get pvc -n bigdata

# Describe PVC
kubectl describe pvc hdfs-namenode-pvc -n bigdata

# Check StorageClass
kubectl get storageclass

# Delete and recreate PVC if needed
kubectl delete pvc hdfs-namenode-pvc -n bigdata
kubectl apply -f k8s/persistent-volumes.yaml
```

### 2. Kafka connection timeout

```bash
# Check Zookeeper first
kubectl logs zookeeper-0 -n bigdata

# Check Kafka logs
kubectl logs kafka-0 -n bigdata | grep -i error

# Check service
kubectl get svc kafka -n bigdata

# Test connection from another pod
kubectl run -it --rm debug --image=busybox --restart=Never -n bigdata -- sh
# Inside pod:
telnet kafka 9092
```

**Solution:**

```bash
# Restart Kafka
kubectl rollout restart statefulset/kafka -n bigdata

# Check Kafka topics are created
kubectl exec -it kafka-0 -n bigdata -- \
  kafka-topics --list --bootstrap-server localhost:9092
```

### 3. HDFS NameNode not ready

```bash
# Check NameNode logs
kubectl logs hadoop-namenode-0 -n bigdata | tail -50

# Common issue: Safe mode
# Exec into pod
kubectl exec -it hadoop-namenode-0 -n bigdata -- bash

# Check safe mode
hdfs dfsadmin -safemode get

# Leave safe mode (if stuck)
hdfs dfsadmin -safemode leave

# Format NameNode (DANGER - deletes all data!)
# hdfs namenode -format
```

### 4. Elasticsearch không healthy

```bash
# Check logs
kubectl logs elasticsearch-0 -n bigdata | tail -100

# Common: vm.max_map_count too low
# Solution: Already handled by initContainer in StatefulSet

# Check cluster health
kubectl exec -it elasticsearch-0 -n bigdata -- \
  curl -X GET "localhost:9200/_cluster/health?pretty"

# Check nodes
kubectl exec -it elasticsearch-0 -n bigdata -- \
  curl -X GET "localhost:9200/_cat/nodes?v"
```

### 5. Spark Streaming job failing

```bash
# Check Spark logs
kubectl logs deployment/spark-streaming -n bigdata | grep -i error

# Common issues:
# - Kafka topic not exist: Wait for Kafka to fully start
# - Elasticsearch connection failed: Check ES health
# - Checkpoint directory: Check HDFS

# Restart Spark
kubectl rollout restart deployment/spark-streaming -n bigdata

# Delete checkpoint (if corrupted)
kubectl exec -it hadoop-namenode-0 -n bigdata -- \
  hdfs dfs -rm -r /user/spark_checkpoints/stock_realtime_v1
```

### 6. Image pull errors

```bash
# Describe pod
kubectl describe pod <pod-name> -n bigdata | grep -i image

# Common: Wrong image name or no permission

# Solution 1: Check image exists
gcloud container images list --repository=gcr.io/${PROJECT_ID}

# Solution 2: Create Image Pull Secret (if using private registry)
kubectl create secret docker-registry gcr-json-key \
  --docker-server=gcr.io \
  --docker-username=_json_key \
  --docker-password="$(cat ~/key.json)" \
  --docker-email=user@example.com \
  -n bigdata

# Add to deployment:
# spec:
#   imagePullSecrets:
#   - name: gcr-json-key
```

### 7. OOMKilled (Out of Memory)

```bash
# Check pod
kubectl describe pod <pod-name> -n bigdata | grep -i oom

# Solution: Increase memory limits
# Edit deployment
kubectl edit deployment <deployment-name> -n bigdata

# Update resources:
# resources:
#   limits:
#     memory: "4Gi"  # Increase
#   requests:
#     memory: "2Gi"  # Increase
```

### 8. CrashLoopBackOff

```bash
# Check logs
kubectl logs <pod-name> -n bigdata --previous

# Common: Application error or missing dependencies

# Debug by running shell
kubectl run -it debug --image=gcr.io/${PROJECT_ID}/bigdata-python-worker:latest \
  --restart=Never -n bigdata -- /bin/bash

# Inside container, test commands
python /app/kafka_producer.py
```

---

## 💰 TỐI ƯU HÓA CHI PHÍ

### 1. Sử dụng Preemptible Nodes cho Dev/Test

```bash
# Create node pool with preemptible nodes
gcloud container node-pools create preemptible-pool \
  --cluster=${CLUSTER_NAME} \
  --zone=${ZONE} \
  --machine-type=n1-standard-4 \
  --num-nodes=2 \
  --preemptible \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=5

# Add taint to run only non-critical workloads
kubectl taint nodes -l cloud.google.com/gke-preemptible=true preemptible=true:NoSchedule

# Add toleration in deployments
# spec:
#   template:
#     spec:
#       tolerations:
#       - key: "preemptible"
#         operator: "Equal"
#         value: "true"
#         effect: "NoSchedule"
```

### 2. Auto-scaling Pods

```bash
# Check HPA
kubectl get hpa -n bigdata

# Manual scale (if needed)
kubectl scale deployment kafka-producer --replicas=3 -n bigdata

# Scale to zero for non-essential (dev)
kubectl scale deployment kafka-producer --replicas=0 -n bigdata
```

### 3. Storage optimization

```bash
# Use pd-standard instead of pd-ssd for non-critical data
# Edit PVC:
# storageClassName: standard  # Instead of standard-rwo (SSD)

# Set retention policies
# Kafka: KAFKA_LOG_RETENTION_HOURS=168 (7 days)
# Elasticsearch: ILM policies to delete old indices

# Delete old indices
kubectl exec -it elasticsearch-0 -n bigdata -- \
  curl -X DELETE "localhost:9200/stock_realtime-2024.01.*"
```

### 4. Resource Requests/Limits

Tối ưu requests để Kubernetes pack pods hiệu quả hơn:

```yaml
# Before:
resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"
  limits:
    memory: "4Gi"
    cpu: "2000m"

# After (right-size based on actual usage):
resources:
  requests:
    memory: "512Mi"  # Actual usage: 300Mi
    cpu: "250m"      # Actual usage: 150m
  limits:
    memory: "1Gi"
    cpu: "500m"
```

### 5. Schedule workloads

```bash
# Stop non-essential services at night (dev environment)
# Use CronJob to scale down/up

# scale-down.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: scale-down-nightly
spec:
  schedule: "0 22 * * *"  # 10 PM
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: scaler
          containers:
          - name: kubectl
            image: bitnami/kubectl
            command:
            - /bin/sh
            - -c
            - |
              kubectl scale deployment kafka-producer --replicas=0 -n bigdata
              kubectl scale deployment kafka-consumer --replicas=0 -n bigdata
          restartPolicy: OnFailure
```

### 6. Cluster auto-shutdown (dev)

```bash
# Delete cluster when not in use
gcloud container clusters delete ${CLUSTER_NAME} --zone=${ZONE} --quiet

# Recreate later (nhanh với scripts)
./deploy.sh
```

---

## 🔐 BẢO MẬT PRODUCTION

### 1. Network Policies

```bash
# Already applied in deployment
kubectl get networkpolicies -n bigdata

# Test: Should not be able to access Kafka from outside namespace
kubectl run test --image=busybox --rm -it -- sh
# Should timeout: telnet kafka.bigdata.svc.cluster.local 9092
```

### 2. RBAC (Role-Based Access Control)

```bash
# Create service account for batch jobs
kubectl create sa batch-job-sa -n bigdata

# Create role
kubectl create role batch-job-role \
  --verb=get,list,watch \
  --resource=configmaps,secrets \
  -n bigdata

# Bind role
kubectl create rolebinding batch-job-binding \
  --role=batch-job-role \
  --serviceaccount=bigdata:batch-job-sa \
  -n bigdata

# Use in CronJob:
# spec:
#   template:
#     spec:
#       serviceAccountName: batch-job-sa
```

### 3. Secrets Management

```bash
# Create secret for sensitive data
kubectl create secret generic bigdata-secrets \
  --from-literal=es-password=yourpassword \
  --from-literal=kafka-sasl-password=yourpassword \
  -n bigdata

# Use in pods:
# env:
# - name: ES_PASSWORD
#   valueFrom:
#     secretKeyRef:
#       name: bigdata-secrets
#       key: es-password

# Hoặc sử dụng Google Secret Manager (khuyến nghị)
gcloud secrets create es-password --data-file=- <<< "your-password"

# Grant access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member=serviceAccount:${PROJECT_ID}.svc.id.goog[bigdata/default] \
  --role=roles/secretmanager.secretAccessor
```

### 4. Enable Workload Identity

```bash
# Already enabled during cluster creation (--workload-pool)

# Create GCP Service Account
gcloud iam service-accounts create bigdata-gke-sa \
  --display-name="Big Data GKE Service Account"

# Grant permissions
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member=serviceAccount:bigdata-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --role=roles/storage.objectViewer

# Bind to K8s SA
gcloud iam service-accounts add-iam-policy-binding \
  bigdata-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="serviceAccount:${PROJECT_ID}.svc.id.goog[bigdata/default]"

# Annotate K8s SA
kubectl annotate serviceaccount default \
  iam.gke.io/gcp-service-account=bigdata-gke-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  -n bigdata
```

### 5. Enable Binary Authorization (Optional)

```bash
# Enforce only signed images can run
gcloud container clusters update ${CLUSTER_NAME} \
  --enable-binauthz \
  --zone=${ZONE}

# Create policy (attestation required)
# Requires setting up Attestors and CI/CD pipeline
```

### 6. Private GKE Cluster

```bash
# For production, use private cluster
gcloud container clusters create ${CLUSTER_NAME}-private \
  --enable-private-nodes \
  --enable-private-endpoint \
  --master-ipv4-cidr=172.16.0.0/28 \
  --enable-ip-alias \
  --zone=${ZONE}

# Access via Bastion host or Cloud Shell
```

---

## 📊 MONITORING & LOGGING

### 1. Cloud Logging (Stackdriver)

```bash
# Logs automatically sent to Cloud Logging

# View logs in console:
# https://console.cloud.google.com/logs

# Filter by resource:
# resource.type="k8s_container"
# resource.labels.cluster_name="${CLUSTER_NAME}"
# resource.labels.namespace_name="bigdata"

# Export logs to BigQuery for analysis
gcloud logging sinks create bigdata-logs-sink \
  bigquery.googleapis.com/projects/${PROJECT_ID}/datasets/bigdata_logs \
  --log-filter='resource.type="k8s_container" AND resource.labels.namespace_name="bigdata"'
```

### 2. Cloud Monitoring (Metrics)

```bash
# Auto-enabled with --enable-stackdriver-kubernetes

# View dashboards:
# https://console.cloud.google.com/monitoring

# Create custom metrics from Elasticsearch
# Use Prometheus exporter
```

### 3. Install Prometheus & Grafana (Optional)

```bash
# Add Prometheus Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus Operator
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace

# Access Grafana
kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring
# Username: admin
# Password: prom-operator

# Import dashboards:
# - Kubernetes Cluster Monitoring (ID: 7249)
# - Kafka Overview (ID: 7589)
# - Elasticsearch (ID: 2322)
```

### 4. Alerting

```bash
# Cloud Monitoring Alerting Policies
# Go to: https://console.cloud.google.com/monitoring/alerting

# Example alert: High CPU usage
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="High CPU Usage" \
  --condition-display-name="CPU > 80%" \
  --condition-threshold-value=0.8 \
  --condition-threshold-duration=300s \
  --condition-metric-kind=GAUGE \
  --condition-metric-type=kubernetes.io/container/cpu/core_usage_time \
  --condition-aggregation-alignment-period=60s \
  --condition-aggregation-per-series-aligner=ALIGN_RATE
```

---

## 🧪 TESTING

### Unit Tests

```bash
# Test locally before deploying
python -m pytest tests/ -v

# Test Kafka producer
python kafka_producer.py &
sleep 30
pkill -f kafka_producer.py

# Test batch jobs
python run_all.py
```

### Integration Tests

```bash
# Create test namespace
kubectl create namespace bigdata-test

# Deploy to test namespace
kubectl apply -f k8s/ -n bigdata-test

# Run tests
kubectl run test-runner --image=python:3.12 --rm -it -n bigdata-test -- sh

# Clean up
kubectl delete namespace bigdata-test
```

---

## 📚 BEST PRACTICES

### 1. Deployment Strategy

- **Blue/Green Deployment**: Maintain zero downtime
- **Canary Deployment**: Gradually roll out changes
- **Rolling Update**: Default, good for most cases

### 2. Resource Management

- Always set resource requests/limits
- Use HPA for auto-scaling
- Monitor actual usage and adjust

### 3. Data Management

- Regular backups of persistent volumes
- Test restore procedures
- Use snapshots for HDFS/Elasticsearch

### 4. Security

- Network Policies for pod-to-pod communication
- RBAC for access control
- Secrets for sensitive data
- Private cluster for production

### 5. Monitoring

- Enable Cloud Logging/Monitoring
- Set up alerting
- Regular health checks
- Performance profiling

---

## 🔄 CI/CD PIPELINE (Bonus)

### Google Cloud Build

Tạo `cloudbuild.yaml`:

```yaml
steps:
  # Build Docker image
  - name: "gcr.io/cloud-builders/docker"
    args:
      [
        "build",
        "-t",
        "gcr.io/$PROJECT_ID/bigdata-python-worker:$COMMIT_SHA",
        ".",
      ]

  # Push to GCR
  - name: "gcr.io/cloud-builders/docker"
    args: ["push", "gcr.io/$PROJECT_ID/bigdata-python-worker:$COMMIT_SHA"]

  # Update K8s deployment
  - name: "gcr.io/cloud-builders/kubectl"
    args:
      - "set"
      - "image"
      - "deployment/kafka-producer"
      - "kafka-producer=gcr.io/$PROJECT_ID/bigdata-python-worker:$COMMIT_SHA"
      - "-n"
      - "bigdata"
    env:
      - "CLOUDSDK_COMPUTE_ZONE=asia-southeast1-a"
      - "CLOUDSDK_CONTAINER_CLUSTER=bigdata-cluster"

images:
  - "gcr.io/$PROJECT_ID/bigdata-python-worker:$COMMIT_SHA"
```

Trigger build:

```bash
# Submit build
gcloud builds submit --config cloudbuild.yaml

# Create trigger from GitHub
gcloud builds triggers create github \
  --repo-name=big_data \
  --repo-owner=your-username \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

---

## 📞 HỖ TRỢ

### Tài liệu tham khảo

- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [Kubernetes Official Docs](https://kubernetes.io/docs/)
- [Apache Kafka](https://kafka.apache.org/documentation/)
- [Apache Spark](https://spark.apache.org/docs/latest/)
- [Elasticsearch](https://www.elastic.co/guide/index.html)

### Commands cheat sheet

```bash
# Quick status check
kubectl get all -n bigdata

# Logs
kubectl logs -f <pod-name> -n bigdata

# Describe
kubectl describe pod <pod-name> -n bigdata

# Exec
kubectl exec -it <pod-name> -n bigdata -- bash

# Port forward
kubectl port-forward svc/<service-name> <local-port>:<remote-port> -n bigdata

# Scale
kubectl scale deployment <name> --replicas=<count> -n bigdata

# Delete
kubectl delete pod <pod-name> -n bigdata

# Restart
kubectl rollout restart deployment/<name> -n bigdata
```

---

## ✅ CHECKLIST TRIỂN KHAI

- [ ] Cài đặt gcloud, kubectl, docker
- [ ] Tạo GCP project và enable APIs
- [ ] Build và push Docker images
- [ ] Tạo GKE cluster
- [ ] Update ConfigMap với thông tin đúng
- [ ] Update image names trong deployments
- [ ] Deploy Namespace
- [ ] Deploy ConfigMap
- [ ] Deploy PVCs
- [ ] Deploy StatefulSets (Zookeeper → Kafka → HDFS → ES)
- [ ] Deploy Deployments
- [ ] Deploy CronJobs
- [ ] Deploy HPA
- [ ] Deploy Network Policies
- [ ] Test Kafka producer/consumer
- [ ] Test Spark streaming
- [ ] Test batch jobs
- [ ] Access Kibana và tạo dashboards
- [ ] Set up monitoring và alerting
- [ ] Configure backups
- [ ] Document architecture và runbooks

---

**🎉 HOÀN THÀNH!**

Hệ thống Big Data của bạn đã sẵn sàng trên Google Kubernetes Engine!

**Liên hệ**: Nếu có vấn đề, check Troubleshooting section hoặc xem logs.
