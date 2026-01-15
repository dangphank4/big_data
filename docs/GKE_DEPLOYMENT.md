# ☁️ GOOGLE KUBERNETES ENGINE (GKE) DEPLOYMENT GUIDE

**Complete step-by-step guide for deploying Big Data Stock Analysis System to GKE**

> **📌 BẠN ĐÃ TẠO CLUSTER**: Guide này bắt đầu từ bước connect cluster và deploy services.

---

## 📋 TABLE OF CONTENTS

1. [System Architecture](#-system-architecture)
2. [Prerequisites](#-prerequisites)
3. [Connect to GKE Cluster](#-connect-to-gke-cluster)
4. [Understand K8s Structure](#-understand-k8s-structure)
5. [Build & Push Docker Images](#-build--push-docker-images)
6. [Deploy Infrastructure Services](#-deploy-infrastructure-services)
7. [Deploy Application Services](#-deploy-application-services)
8. [Verify Deployment](#-verify-deployment)
9. [Feed Data](#-feed-data)
10. [Access Services](#-access-services)
11. [Scaling & Optimization](#-scaling--optimization)
12. [Troubleshooting](#-troubleshooting)
13. [Complete Teardown](#-complete-teardown)

---

## 🏗️ SYSTEM ARCHITECTURE

### Big Data Stock Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    REAL-TIME DATA PIPELINE                       │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────┐    ┌───────────────┐    ┌──────────────┐
│ Yahoo Finance│───>│  Kafka   │───>│ Spark Stream  │───>│ Elasticsearch│
│   Producer   │    │ (Buffer) │    │  (Aggregate)  │    │   (Serving)  │
└──────────────┘    └──────────┘    └───────────────┘    └──────────────┘
                                                                   │
┌─────────────────────────────────────────────────────────────────┘
│
▼
┌──────────────┐    ┌──────────┐    ┌───────────────┐
│   HDFS       │◄───│ Archiver │    │    Kibana     │
│  (Storage)   │    │(Cronjob) │    │ (Dashboard)   │
└──────────────┘    └──────────┘    └───────────────┘
       │
       ▼
┌───────────────┐    ┌──────────────┐
│ Spark Batch   │───>│ Elasticsearch│
│  (Features)   │    │(batch-features)│
└───────────────┘    └──────────────┘
```

### Data Flow

1. **Real-time Stream**: Yahoo Finance → Kafka → Spark Streaming → Elasticsearch (stock-realtime-1m)
2. **Historical Batch**: Kafka → HDFS Archiver → HDFS → Spark Batch → Elasticsearch (batch-features)
3. **Alerts**: Spark Streaming → Elasticsearch (stock-alerts-1m)
4. **Visualization**: Kibana reads from Elasticsearch indices

---

## ✅ PREREQUISITES

### ✅ Đã có

- **GKE Cluster** đã tạo trên Google Cloud

### Cần chuẩn bị

- **kubectl** installed (v1.28+)
- **gcloud CLI** installed and configured
- **Docker** installed (v20.10+)
- **GCP Project** với billing enabled

### Verify Tools

```bash
# Check kubectl
kubectl version --client

# Check gcloud
gcloud version

# Check Docker
docker --version
```

---

## ☸️ CONNECT TO GKE CLUSTER

### Step 1: List Your Clusters

```bash
# List all GKE clusters in your project
gcloud container clusters list

# Expected output:
# NAME                    LOCATION       MASTER_VERSION  NODE_VERSION   NUM_NODES  STATUS
# your-cluster-name       us-central1-a  1.28.x-gke.xxx  1.28.x-gke.xxx  3         RUNNING
```

**📸 Screenshot 1**: Cluster visible

---

### Step 2: Set Environment Variables

```bash
# ⚠️ REPLACE with your actual values
export PROJECT_ID="inner-period-480016-h8"          # Your GCP Project ID
export CLUSTER_NAME="bigdata"          # Your GKE cluster name
export ZONE="asia-northeast1-c"                      # Your cluster zone (check gcloud list output)
export REGION="asia-northeast1"                      # Your cluster region
export NAMESPACE="bigdata"                       # Kubernetes namespace

# GCR (Google Container Registry) config
export GCR_HOSTNAME="gcr.io"
export IMAGE_TAG="latest"

# Verify
echo "Project: $PROJECT_ID"
echo "Cluster: $CLUSTER_NAME"
echo "Zone: $ZONE"
```

**💡 Tip**: Lưu vào file để tái sử dụng:

```bash
cat > ~/gke-env.sh << 'EOF'
export PROJECT_ID=""
export CLUSTER_NAME="bigdata"
export ZONE="asia-northeast1-c"
export REGION="asia-northeast1"
export NAMESPACE="bigdata"
export GCR_HOSTNAME="gcr.io"
export IMAGE_TAG="latest"
EOF

# Mỗi lần mở terminal mới:
source ~/gke-env.sh
```

**📸 Screenshot 2**: Environment variables set

---

### Step 3: Connect kubectl to Cluster

```bash
# Get cluster credentials
gcloud container clusters get-credentials $CLUSTER_NAME \
  --zone=$ZONE \
  --project=$PROJECT_ID

# Verify connection
kubectl cluster-info

# Expected output:
# Kubernetes control plane is running at https://xx.xxx.xxx.xxx
```

**📸 Screenshot 3**: Connected to cluster

---

### Step 4: Verify Nodes

```bash
# Check cluster nodes
kubectl get nodes -o wide

# Expected output:
# NAME                                    STATUS   ROLES    AGE   VERSION
# gke-cluster-default-xxx-abcd           Ready    <none>   10m   v1.28.x-gke.xxx
# gke-cluster-default-xxx-efgh           Ready    <none>   10m   v1.28.x-gke.xxx
# gke-cluster-default-xxx-ijkl           Ready    <none>   10m   v1.28.x-gke.xxx

# Check node resources (optional)
kubectl top nodes 2>/dev/null || echo "Metrics server not ready yet"
```

**📸 Screenshot 4**: Nodes ready

---

## 📂 UNDERSTAND K8S STRUCTURE

### Organized Folder Structure

```
deployment/k8s/
├── 00-namespace/           # Phase 0: Namespace isolation
│   └── namespace.yaml
├── 01-config/              # Phase 1: Global configuration
│   └── configmap.yaml
├── 02-storage/             # Phase 2: Persistent storage
│   ├── persistent-volumes-gke.yaml  (for GKE - USE THIS)
│   └── persistent-volumes.yaml      (for on-premise)
├── 03-infrastructure/      # Phase 3: Core services (deploy sequential!)
│   ├── zookeeper-statefulset.yaml   (1st)
│   ├── kafka-statefulset.yaml       (2nd)
│   ├── hdfs-statefulset.yaml        (3rd)
│   └── elasticsearch-statefulset.yaml (4th)
├── 04-applications/        # Phase 4: Application layer
│   ├── kafka-producer-crawl-deployment.yaml
│   ├── spark-streaming-consumer-deployment.yaml
│   ├── spark-alerts-deployment.yaml
│   ├── kafka-spark-bridge-deployment.yaml
│   └── kibana-deployment-updated.yaml
├── 05-jobs/                # Phase 5: Scheduled tasks
│   ├── hdfs-archiver-cronjob.yaml
│   ├── spark-batch-features-cronjob.yaml
│   └── hdfs-backfill-job.yaml
└── 06-networking-scaling/  # Phase 6: Optional enhancements
    ├── ingress.yaml
    ├── hpa.yaml
    ├── monitoring.yaml
    └── network-policy.yaml
```

### Deployment Order (CRITICAL!)

**Phải deploy theo thứ tự 00 → 06:**

| Phase  | Files        | Description                                  | Required    |
| ------ | ------------ | -------------------------------------------- | ----------- |
| **00** | 1 file       | Namespace isolation                          | ✅ YES      |
| **01** | 1 file       | Global env vars (Kafka, ES, tickers)         | ✅ YES      |
| **02** | 1 file (GKE) | PVCs for persistent data                     | ✅ YES      |
| **03** | 4 files      | StatefulSets - Deploy sequential with waits! | ✅ YES      |
| **04** | 5 files      | Deployments (apps can deploy parallel)       | ✅ YES      |
| **05** | 3 files      | CronJobs & batch jobs                        | ✅ YES      |
| **06** | 4 files      | Ingress, HPA, monitoring                     | ⚠️ Optional |

### Files Description

**Phase 00 - Namespace:**

- `namespace.yaml`: Creates isolated `bigdata` namespace

**Phase 01 - Configuration:**

- `configmap.yaml`: Environment variables (Kafka broker, ES hosts, stock tickers)

**Phase 02 - Storage:**

- `persistent-volumes-gke.yaml`: **USE THIS for GKE** (dynamic provisioning)
- `persistent-volumes.yaml`: For on-premise only

**Phase 03 - Infrastructure (MUST deploy sequentially):**

1. `zookeeper-statefulset.yaml`: Kafka dependency (deploy first, wait until Ready)
2. `kafka-statefulset.yaml`: Message queue (deploy after Zookeeper ready)
3. `hdfs-statefulset.yaml`: Distributed storage (namenode + datanode)
4. `elasticsearch-statefulset.yaml`: Search & analytics engine

**Phase 04 - Applications:**

- `kafka-producer-crawl-deployment.yaml`: Yahoo Finance crawler
- `kafka-spark-bridge-deployment.yaml`: Kafka consumer → Spark topic
- `spark-streaming-consumer-deployment.yaml`: Real-time metrics aggregation
- `spark-alerts-deployment.yaml`: Anomaly detection alerts
- `kibana-deployment-updated.yaml`: Visualization dashboard (optional)

**Phase 05 - Jobs:**

- `hdfs-archiver-cronjob.yaml`: Hourly backup Kafka → HDFS
- `spark-batch-features-cronjob.yaml`: Monthly batch feature computation
- `hdfs-backfill-job.yaml`: One-time historical data backfill

**Phase 06 - Networking & Scaling:**

- `ingress.yaml`: External access via LoadBalancer
- `hpa.yaml`: Horizontal Pod Autoscaler for dynamic scaling
- `monitoring.yaml`: ServiceMonitor for Prometheus (requires Prometheus Operator)
- `network-policy.yaml`: Network isolation rules

---

## 🏗️ BUILD & PUSH DOCKER IMAGES

### Step 5: Configure Docker for GCR

```bash
# Authenticate Docker with GCR
gcloud auth configure-docker

# Verify
cat ~/.docker/config.json | grep gcr.io
```

**Expected output:**

```json
{
  "credHelpers": {
    "gcr.io": "gcloud"
  }
}
```

**📸 Screenshot 5**: Docker authenticated with GCR

---

### Step 6: Build Images

```bash
cd /home/danz/Downloads/big_data

# Build application image (for producer & consumers)
docker build -f config/Dockerfile -t bigdata-app:$IMAGE_TAG .

# Build Spark image (for streaming & batch)
docker build -f config/Dockerfile.spark -t bigdata-spark:$IMAGE_TAG .

# Verify
docker images | grep bigdata
```

**Expected output:**

```
bigdata-app     latest    abc123    2 mins ago   564MB
bigdata-spark   latest    xyz789    3 mins ago   2.8GB
```

**📸 Screenshot 6**: Images built

---

### Step 7: Tag & Push to GCR

```bash
# Tag for GCR
docker tag bigdata-app:$IMAGE_TAG $GCR_HOSTNAME/$PROJECT_ID/bigdata-app:$IMAGE_TAG
docker tag bigdata-spark:$IMAGE_TAG $GCR_HOSTNAME/$PROJECT_ID/bigdata-spark:$IMAGE_TAG

# Push to GCR
docker push $GCR_HOSTNAME/$PROJECT_ID/bigdata-app:$IMAGE_TAG
docker push $GCR_HOSTNAME/$PROJECT_ID/bigdata-spark:$IMAGE_TAG

# Verify
gcloud container images list --repository=$GCR_HOSTNAME/$PROJECT_ID
```

**Expected output:**

```
NAME
gcr.io/your-project-id/bigdata-app
gcr.io/your-project-id/bigdata-spark
```

**📸 Screenshot 7**: Images in GCR

---

### Step 8: Update Deployment Manifests

```bash
cd /home/danz/Downloads/big_data

# Replace image references in all YAML files
find deployment/k8s -name "*.yaml" -type f -exec sed -i \
  "s|image: gcr.io/PROJECT_ID/|image: $GCR_HOSTNAME/$PROJECT_ID/|g" {} \;

find deployment/k8s -name "*.yaml" -type f -exec sed -i \
  "s|image: bigdata-app:latest|image: $GCR_HOSTNAME/$PROJECT_ID/bigdata-app:$IMAGE_TAG|g" {} \;

find deployment/k8s -name "*.yaml" -type f -exec sed -i \
  "s|image: bigdata-spark:latest|image: $GCR_HOSTNAME/$PROJECT_ID/bigdata-spark:$IMAGE_TAG|g" {} \;

# Verify
grep "image:" deployment/k8s/04-applications/kafka-producer-crawl-deployment.yaml
```

**Expected output:**

```yaml
image: gcr.io/your-project-id/bigdata-app:latest
```

**📸 Screenshot 8**: Manifests updated

---

## 🚀 DEPLOY INFRASTRUCTURE SERVICES

### Step 9: Deploy Namespace & ConfigMap (Phase 00-01)

```bash
# Phase 00: Create namespace
kubectl apply -f deployment/k8s/00-namespace/

# Phase 01: Apply ConfigMap
kubectl apply -f deployment/k8s/01-config/

# Verify
kubectl get namespace bigdata
kubectl get configmap -n $NAMESPACE
```

**Expected output:**

```
namespace/bigdata created

NAME             DATA   AGE
bigdata-config   15     10s
```

**📸 Screenshot 9**: Namespace & ConfigMap ready

---

### Step 10: Create Persistent Volumes (Phase 02)

```bash
# Phase 02: Apply PVCs for GKE (uses dynamic provisioning)
kubectl apply -f deployment/k8s/02-storage/persistent-volumes-gke.yaml

# Wait for PVCs to bind (10 seconds)
sleep 10

# Verify all PVCs are Bound
kubectl get pvc -n $NAMESPACE
```

**Expected output:**

```
NAME                 STATUS   VOLUME                                     CAPACITY   STORAGECLASS
elasticsearch-pvc    Bound    pvc-abc123-xxx-xxx-xxx-xxxxxxxxxxxx       30Gi       standard-rwo
hdfs-datanode-pvc    Bound    pvc-def456-xxx-xxx-xxx-xxxxxxxxxxxx       50Gi       standard-rwo
hdfs-namenode-pvc    Bound    pvc-ghi789-xxx-xxx-xxx-xxxxxxxxxxxx       20Gi       standard-rwo
kafka-pvc            Bound    pvc-jkl012-xxx-xxx-xxx-xxxxxxxxxxxx       20Gi       standard-rwo
zookeeper-pvc        Bound    pvc-mno345-xxx-xxx-xxx-xxxxxxxxxxxx       10Gi       standard-rwo
```

**📸 Screenshot 10**: All PVCs Bound

---

### Step 11: Deploy Zookeeper (Phase 03 - Step 1)

```bash
# Deploy Zookeeper FIRST (Kafka dependency)
kubectl apply -f deployment/k8s/03-infrastructure/zookeeper-statefulset.yaml

# ⏳ Wait for Zookeeper to be Ready (2 minutes)
kubectl wait --for=condition=ready pod -l app=zookeeper -n $NAMESPACE --timeout=300s

# Verify
kubectl get statefulset,pod,svc -n $NAMESPACE -l app=zookeeper
```

**Expected output:**

```
statefulset.apps/zookeeper   1/1     2m
pod/zookeeper-0              1/1     Running   0   2m
service/zookeeper            ClusterIP   10.x.x.x   2181/TCP
```

**⚠️ If pod stuck in Pending on e2-medium:**

```bash
# Reduce Zookeeper resources (small nodes)
kubectl patch statefulset zookeeper -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "100m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "256Mi"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "300m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "512Mi"}
]'

kubectl delete pod zookeeper-0 -n $NAMESPACE
```

**📸 Screenshot 11**: Zookeeper running

---

### Step 12: Deploy Kafka (Phase 03 - Step 2)

```bash
# Deploy Kafka SECOND (requires Zookeeper)
kubectl apply -f deployment/k8s/03-infrastructure/kafka-statefulset.yaml

# ⏳ Wait for Kafka to be Ready (3 minutes)
kubectl wait --for=condition=ready pod -l app=kafka -n $NAMESPACE --timeout=300s

# Verify
kubectl get statefulset,pod,svc -n $NAMESPACE -l app=kafka
```

**Expected output:**

```
statefulset.apps/kafka   1/1     3m
pod/kafka-0              1/1     Running   0   3m
service/kafka            ClusterIP   10.x.x.x   9092/TCP
```

**⚠️ If pod stuck in Pending with "Insufficient cpu":**

On **e2-medium nodes** (1 vCPU), Kafka's default 500m CPU request is too high. Reduce resources:

```bash
# Patch Kafka to reduce CPU request
kubectl patch statefulset kafka -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "100m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "512Mi"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "500m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "1Gi"}
]'

# Delete pending pod to recreate
kubectl delete pod kafka-0 -n $NAMESPACE

# Wait for pod
kubectl wait --for=condition=ready pod kafka-0 -n $NAMESPACE --timeout=300s
```

**📸 Screenshot 12**: Kafka running

---

### Step 13: Verify Kafka Topics

```bash
# List Kafka topics (should auto-create)
# NOTE: In this image the CLI is `kafka-topics` (no .sh)
kubectl exec -it kafka-0 -n $NAMESPACE -- kafka-topics \
  --list \
  --bootstrap-server localhost:9092
```

**Expected output:**

```
stocks-realtime
stocks-realtime-spark
```

**📸 Screenshot 13**: Kafka topics exist

---

### Step 14: Deploy HDFS (Phase 03 - Step 3)

```bash
# Deploy HDFS (namenode + datanode)
kubectl apply -f deployment/k8s/03-infrastructure/hdfs-statefulset.yaml

# ⏳ Wait for HDFS NameNode to be Ready (3 minutes)
kubectl wait --for=condition=ready pod -l app=hadoop-namenode -n $NAMESPACE --timeout=300s

# ⏳ Wait for HDFS DataNode to be Ready (3 minutes)
kubectl wait --for=condition=ready pod -l app=hadoop-datanode -n $NAMESPACE --timeout=300s

# Verify both namenode and datanode
kubectl get statefulset,pod,svc -n $NAMESPACE | grep hadoop
```

**Expected output:**

```
statefulset.apps/hadoop-namenode   1/1     3m
statefulset.apps/hadoop-datanode   1/1     3m
pod/hadoop-namenode-0              1/1     Running   0   3m
pod/hadoop-datanode-0              1/1     Running   0   3m
service/hadoop-namenode            ClusterIP   10.x.x.x   9870/TCP,9000/TCP
```

**⚠️ If NameNode CrashLoopBackOff with "NameNode is not formatted":**

```bash
# Scale down NameNode
kubectl scale statefulset hadoop-namenode -n $NAMESPACE --replicas=0

# Create a temporary formatter pod (uses the same PVC)
cat <<'EOF' | kubectl apply -n $NAMESPACE -f -
apiVersion: v1
kind: Pod
metadata:
  name: hdfs-namenode-format
spec:
  restartPolicy: Never
  containers:
  - name: formatter
    image: bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8
    command: ["bash","-lc","/entrypoint.sh /bin/true && HADOOP_CONF_DIR=/etc/hadoop /opt/hadoop-3.2.1/bin/hdfs namenode -format -force -nonInteractive"]
    env:
    - name: CLUSTER_NAME
      value: "bigdata-cluster"
    - name: CORE_CONF_fs_defaultFS
      value: "hdfs://hadoop-namenode:9000"
    - name: HDFS_CONF_dfs_namenode_name_dir
      value: "file:///hadoop/dfs/name"
    - name: HDFS_CONF_dfs_permissions_enabled
      value: "false"
    volumeMounts:
    - name: namenode-storage
      mountPath: /hadoop/dfs/name
  volumes:
  - name: namenode-storage
    persistentVolumeClaim:
      claimName: hdfs-namenode-pvc
EOF

# Remove formatter pod and scale up NameNode
kubectl delete pod hdfs-namenode-format -n $NAMESPACE
kubectl scale statefulset hadoop-namenode -n $NAMESPACE --replicas=1
```

**⚠️ If pods stuck in Pending on e2-medium:**

```bash
# Reduce HDFS resources for small nodes
kubectl patch statefulset hadoop-namenode -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "100m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "512Mi"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "500m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "1Gi"}
]'

kubectl patch statefulset hadoop-datanode -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "200m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "768Mi"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "800m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "1536Mi"}
]'

kubectl delete pod hadoop-namenode-0 hadoop-datanode-0 -n $NAMESPACE
```

**📸 Screenshot 14**: HDFS running

---

### Step 15: Initialize HDFS Directory

```bash
# Check HDFS cluster health
kubectl exec -it hadoop-namenode-0 -n $NAMESPACE -- hdfs dfsadmin -report

# Create base directory for stock data
kubectl exec -it hadoop-namenode-0 -n $NAMESPACE -- hdfs dfs -mkdir -p /stock-data
kubectl exec -it hadoop-namenode-0 -n $NAMESPACE -- hdfs dfs -chmod 777 /stock-data

# Verify
kubectl exec -it hadoop-namenode-0 -n $NAMESPACE -- hdfs dfs -ls /
```

**Expected output:**

```
Live datanodes (1):
Name: 10.x.x.x:9866 (hadoop-datanode-0.hadoop-datanode)

drwxrwxrwx   - root supergroup          0 2026-01-15 01:00 /stock-data
```

**📸 Screenshot 15**: HDFS initialized

---

### Step 16: Deploy Elasticsearch (Phase 03 - Step 4)

```bash
# Deploy Elasticsearch
kubectl apply -f deployment/k8s/03-infrastructure/elasticsearch-statefulset.yaml

# ⏳ Wait for Elasticsearch to be Ready (4 minutes)
kubectl wait --for=condition=ready pod -l app=elasticsearch -n $NAMESPACE --timeout=400s

# Verify
kubectl get statefulset,pod,svc -n $NAMESPACE -l app=elasticsearch
```

**Expected output:**

````
statefulset.apps/elasticsearch   1/1     4m
pod/elasticsearch-0              1/1     Running   0   4m
service/elasticsearch            ClusterIP   10.x.x.x   9200/TCP

**⚠️ If pod stuck in Pending (Insufficient cpu/memory on e2-medium):**

```bash
# Reduce ES heap + resources for small nodes
kubectl patch statefulset elasticsearch -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/env/2/value", "value": "-Xms512m -Xmx512m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "200m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "1Gi"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "500m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "1536Mi"}
]'

kubectl delete pod elasticsearch-0 -n $NAMESPACE
````

**⚠️ If Elasticsearch CrashLoop with AccessDenied on data dir:**

```bash
# Scale down ES to release PVC
kubectl scale statefulset elasticsearch -n $NAMESPACE --replicas=0

# Fix permissions on the PVC
cat <<'EOF' | kubectl apply -n $NAMESPACE -f -
apiVersion: v1
kind: Pod
metadata:
  name: elasticsearch-perms
spec:
  restartPolicy: Never
  containers:
  - name: fix-perms
    image: busybox:1.36
    command: ["sh","-c","chown -R 1000:1000 /data && chmod -R 770 /data"]
    volumeMounts:
    - name: es-data
      mountPath: /data
  volumes:
  - name: es-data
    persistentVolumeClaim:
      claimName: elasticsearch-pvc
EOF

kubectl delete pod elasticsearch-perms -n $NAMESPACE
kubectl scale statefulset elasticsearch -n $NAMESPACE --replicas=1
```

````

**📸 Screenshot 16**: Elasticsearch running

---

### Step 17: Configure Elasticsearch Index Template

```bash
# Port-forward Elasticsearch temporarily
# If 9200 is busy, use 9201:9200
kubectl port-forward svc/elasticsearch 9201:9200 -n $NAMESPACE &
PF_PID=$!
sleep 5

# Create index template for automatic timestamp mapping
curl -X PUT "http://localhost:9201/_index_template/stock-template" \
  -H 'Content-Type: application/json' \
  -d '{
    "index_patterns": ["stock-*"],
    "priority": 1,
    "template": {
      "mappings": {
        "properties": {
          "window_start": {"type": "date"},
          "window_end": {"type": "date"},
          "@timestamp": {"type": "date"},
          "month": {"type": "date", "format": "yyyy-MM"}
        }
      }
    }
  }'

# Check cluster health
curl -X GET "http://localhost:9201/_cluster/health?pretty"

# Stop port-forward
kill $PF_PID
````

**Expected output:**

```json
{"acknowledged":true}

{
  "cluster_name": "docker-cluster",
  "status": "yellow",
  "number_of_nodes": 1
}
```

**📸 Screenshot 17**: Elasticsearch configured

---

## 📡 DEPLOY APPLICATION SERVICES

### Step 18: Deploy Kafka Producer (Phase 04)

```bash
# Deploy Yahoo Finance crawler
kubectl apply -f deployment/k8s/04-applications/kafka-producer-crawl-deployment.yaml

# Wait for producer to be ready
kubectl wait --for=condition=ready pod -l app=kafka-producer -n $NAMESPACE --timeout=120s

# Check status
kubectl get deployment,pod -n $NAMESPACE -l app=kafka-producer
```

**Expected output:**

```
deployment.apps/kafka-producer   1/1     1            1           1m
pod/kafka-producer-abc123-xyz    1/1     Running     0           1m
```

**⚠️ If pod stuck in Pending on e2-medium:**

```bash
# Reduce Kafka producer resources (small nodes)
kubectl patch deployment kafka-producer-crawl -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "100m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "256Mi"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "300m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "512Mi"}
]'

kubectl delete pod -l app=kafka-producer -n $NAMESPACE
```

**📸 Screenshot 18**: Producer deployed

---

### Step 19: Verify Producer is Crawling

```bash
# Stream producer logs
kubectl logs -f -l app=kafka-producer -n $NAMESPACE --tail=30
```

**Expected output:**

```
[START] Real-time crawling for 5 tickers every 60s
[CRAWL] AAPL
[CRAWL] NVDA
[CRAWL] TSLA
[CRAWL] MSFT
[CRAWL] GOOGL
[BATCH 1] 2026-01-15T02:05:00 | 5 records | 3.2s
[WAIT] 60s until next crawl...
```

**(Press Ctrl+C to stop logs)**

**📸 Screenshot 19**: Producer crawling data

---

### Step 20: Deploy Kafka-Spark Bridge

```bash
# Deploy bridge consumer (stocks-realtime → stocks-realtime-spark)
kubectl apply -f deployment/k8s/04-applications/kafka-spark-bridge-deployment.yaml

# Wait for bridge
kubectl wait --for=condition=ready pod -l app=kafka-spark-bridge -n $NAMESPACE --timeout=180s

# Check logs
kubectl logs -l app=kafka-spark-bridge -n $NAMESPACE --tail=20
```

**Expected output:**

```
[START] Kafka Bridge Consumer
[CONSUME] stocks-realtime → [PRODUCE] stocks-realtime-spark
[READY] Bridge active
```

**📸 Screenshot 20**: Bridge deployed

---

### Step 21: Deploy Spark Streaming (Metrics)

```bash
# Deploy Spark Streaming for 2-minute window aggregations
kubectl apply -f deployment/k8s/04-applications/spark-streaming-consumer-deployment.yaml

# Wait for Spark
kubectl wait --for=condition=ready pod -l app=spark-streaming -n $NAMESPACE --timeout=180s

# Check status
kubectl get deployment,pod -n $NAMESPACE -l app=spark-streaming
```

**Expected output:**

```
deployment.apps/spark-streaming-consumer   1/1     1            1           2m
pod/spark-streaming-consumer-abc123-xyz    1/1     Running     0           2m
```

**⚠️ If pod stuck in Pending on e2-medium:**

```bash
# Reduce Spark Streaming resources (small nodes)
kubectl patch deployment spark-streaming-consumer -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "100m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "512Mi"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "300m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "1Gi"}
]'

kubectl delete pod -l app=spark-streaming -n $NAMESPACE
```

**⚠️ If readiness/liveness keeps failing:**

```bash
# Match SparkSubmit process name
kubectl patch deployment spark-streaming-consumer -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/livenessProbe/exec/command/2", "value": "SparkSubmit"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/readinessProbe/exec/command/2", "value": "SparkSubmit"}
]'

kubectl delete pod -l app=spark-streaming -n $NAMESPACE
```

**📸 Screenshot 21**: Spark Streaming deployed

---

### Step 22: Check Spark Streaming Logs

```bash
# Stream Spark logs
kubectl logs -f -l app=spark-streaming -n $NAMESPACE --tail=50
```

**Expected output:**

```
[START] Spark Streaming Consumer - Topic: stocks-realtime-spark
[SPARK] Initializing SparkSession...
[KAFKA] Reading from stocks-realtime-spark...
[READY] Streaming query started
  ✓ Metrics stream → stock-realtime-1m
[BATCH 0] Processed 12 rows, wrote to Elasticsearch
```

**(Press Ctrl+C to stop)**

**Note**: Warnings about `_doc` type are expected for ES 7.x and can be ignored.

**📸 Screenshot 22**: Spark processing data

---

### Step 23: Deploy Spark Alerts

```bash
# Deploy Spark Alerts for anomaly detection
kubectl apply -f deployment/k8s/04-applications/spark-alerts-deployment.yaml

# Wait for alerts
kubectl wait --for=condition=ready pod -l app=spark-streaming-alerts -n $NAMESPACE --timeout=180s

# Check logs
kubectl logs -l app=spark-streaming-alerts -n $NAMESPACE --tail=30
```

**Expected output:**

```
[START] Spark Streaming Alerts
[DETECT] Monitoring for price/volume anomalies...
[READY] Alerts stream → stock-alerts-1m
```

**⚠️ If pod stuck in Pending on e2-medium:**

```bash
# Reduce Spark Alerts resources (small nodes)
kubectl patch deployment spark-streaming-alerts -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "100m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "512Mi"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "300m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "1Gi"}
]'

kubectl delete pod -l app=spark-streaming-alerts -n $NAMESPACE
```

**📸 Screenshot 23**: Alerts deployed

---

### Step 24: Deploy Kibana (Optional)

```bash
# Deploy Kibana UI
kubectl apply -f deployment/k8s/04-applications/kibana-deployment-updated.yaml

# Wait for Kibana
kubectl wait --for=condition=ready pod -l app=kibana -n $NAMESPACE --timeout=180s

# Check status
kubectl get deployment,pod,svc -n $NAMESPACE -l app=kibana
```

**Expected output:**

```
deployment.apps/kibana         1/1     1            1           2m
pod/kibana-abc123-xyz          1/1     Running     0           2m
service/kibana                 LoadBalancer   34.x.x.x   <pending>   5601:30xxx/TCP
```

**⚠️ If pod stuck in Pending on e2-medium:**

```bash
# Reduce Kibana resources (small nodes)
kubectl patch deployment kibana -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "100m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "256Mi"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "300m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "512Mi"}
]'

kubectl delete pod -l app=kibana -n $NAMESPACE
```

**📸 Screenshot 24**: Kibana deployed

---

### Step 25: Deploy CronJobs (Phase 05)

```bash
# Deploy HDFS Archiver (hourly)
kubectl apply -f deployment/k8s/05-jobs/hdfs-archiver-cronjob.yaml

# Deploy Batch Features (monthly)
kubectl apply -f deployment/k8s/05-jobs/spark-batch-features-cronjob.yaml

# Verify CronJobs
kubectl get cronjob -n $NAMESPACE
```

**Expected output:**

```
NAME                      SCHEDULE       SUSPEND   ACTIVE   LAST SCHEDULE
hdfs-archiver             0 * * * *      False     0        <none>
spark-batch-features      0 0 1 * *      False     0        <none>
```

**📸 Screenshot 25**: CronJobs scheduled

---

## ✔️ VERIFY DEPLOYMENT

### Step 26: Check All Resources

```bash
# List all resources
kubectl get all -n $NAMESPACE
```

**Expected output:**

```
NAME                                          READY   STATUS    RESTARTS   AGE
pod/elasticsearch-0                           1/1     Running   0          15m
pod/hadoop-datanode-0                           1/1     Running   0          18m
pod/hadoop-namenode-0                           1/1     Running   0          18m
pod/kafka-0                                   1/1     Running   0          20m
pod/kafka-producer-crawl-xxx                  1/1     Running   0          10m
pod/kafka-spark-bridge-xxx                    1/1     Running   0          9m
pod/spark-streaming-consumer-xxx              1/1     Running   0          8m
pod/spark-streaming-alerts-xxx                1/1     Running   0          7m
pod/kibana-xxx                                1/1     Running   0          6m
pod/zookeeper-0                               1/1     Running   0          22m

NAME                        TYPE        CLUSTER-IP      PORT(S)
service/elasticsearch       ClusterIP   10.x.x.x        9200/TCP
service/hadoop-namenode     ClusterIP   10.x.x.x        9870/TCP,9000/TCP
service/kafka               ClusterIP   None            9092/TCP
service/kibana              LoadBalancer   34.x.x.x   <pending>   5601:30xxx/TCP
service/zookeeper           ClusterIP   None            2181/TCP

NAME                                       READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/kafka-producer-crawl       1/1     1            1           10m
deployment.apps/kafka-spark-bridge         1/1     1            1           9m
deployment.apps/spark-streaming-consumer   1/1     1            1           8m
deployment.apps/spark-streaming-alerts     1/1     1            1           7m
deployment.apps/kibana                     1/1     1            1           6m

NAME                            READY   AGE
statefulset.apps/elasticsearch  1/1     15m
statefulset.apps/hadoop-datanode  1/1     18m
statefulset.apps/hadoop-namenode  1/1     18m
statefulset.apps/kafka          1/1     20m
statefulset.apps/zookeeper      1/1     22m

NAME                             SCHEDULE       SUSPEND   ACTIVE
cronjob.batch/hdfs-archiver      0 * * * *      False     0
cronjob.batch/spark-batch-features  0 0 1 * *   False     0
```

**📸 Screenshot 26**: All resources running

---

### Step 27: Verify Data in Elasticsearch

```bash
# Port-forward Elasticsearch
# If 9200 is busy, use 9201:9200
kubectl port-forward svc/elasticsearch 9201:9200 -n $NAMESPACE &
PF_PID=$!
sleep 5

# Check indices
curl -X GET "http://localhost:9201/_cat/indices?v"

# Count documents in stock-realtime-1m
curl -X GET "http://localhost:9201/stock-realtime-1m/_count"

# Count documents in stock-alerts-1m
curl -X GET "http://localhost:9201/stock-alerts-1m/_count"

# Query recent data
curl -X GET "http://localhost:9201/stock-realtime-1m/_search?size=3&sort=window_start:desc&pretty" \
  -H 'Content-Type: application/json' \
  -d '{"_source": ["ticker", "window_start", "avg_price", "total_volume"]}'

# Stop port-forward
kill $PF_PID
```

**Expected output:**

```
health status index              uuid   pri rep docs.count
yellow open   stock-realtime-1m  xyz123   1   1         45
yellow open   stock-alerts-1m    abc456   1   1         12

{"count":45}
{"count":12}  # alerts có thể = 0 nếu chưa có biến động bất thường
```

**📸 Screenshot 27**: Data in Elasticsearch

---

## 📊 FEED DATA

### Option 1: Wait for Real-time Data (Recommended)

Producer tự động crawl mỗi 60 giây. Chờ 5-10 phút để data flow hoàn chỉnh.

```bash
# Monitor producer
kubectl logs -f -l app=kafka-producer -n $NAMESPACE

# Monitor Spark Streaming
kubectl logs -f -l app=spark-streaming -n $NAMESPACE --tail=50
```

---

### Option 2: Manual HDFS Archiver Trigger

```bash
# Trigger archiver manually để backup Kafka → HDFS
kubectl create job --from=cronjob/hdfs-archiver manual-archive-$(date +%s) -n $NAMESPACE

# Wait for completion
kubectl wait --for=condition=complete job -l job-name --timeout=300s -n $NAMESPACE

# Check logs
ARCHIVE_POD=$(kubectl get pods -n $NAMESPACE -l job-name --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
kubectl logs $ARCHIVE_POD -n $NAMESPACE

# Verify HDFS
kubectl exec -it hadoop-namenode-0 -n $NAMESPACE -- hdfs dfs -ls -R /stock-data
```

**Expected output:**

```
[START] Archiving data...
[HDFS] Wrote 120 records to /stock-data/2026-01-15/
```

---

### Option 3: Historical Backfill

```bash
# One-time backfill từ Yahoo Finance → HDFS
kubectl apply -f deployment/k8s/05-jobs/hdfs-backfill-job.yaml

# Monitor backfill
kubectl logs -f job/hdfs-historical-backfill -n $NAMESPACE

# Verify
kubectl exec -it hadoop-namenode-0 -n $NAMESPACE -- hdfs dfs -ls -R /stock-data
```

---

### Option 4: Manual Batch Features

```bash
# Trigger batch features job (HDFS → Elasticsearch)
kubectl create job --from=cronjob/spark-batch-features manual-batch-$(date +%s) -n $NAMESPACE

# Monitor
kubectl wait --for=condition=complete job -l job-name --timeout=600s -n $NAMESPACE

# Check logs
BATCH_POD=$(kubectl get pods -n $NAMESPACE -l job-name --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
kubectl logs $BATCH_POD -n $NAMESPACE

# Verify batch-features index
kubectl port-forward svc/elasticsearch 9200:9200 -n $NAMESPACE &
sleep 3
curl -X GET "http://localhost:9200/batch-features/_count"
pkill -f "port-forward.*elasticsearch"
```

**📸 Screenshot 28**: Data feeding complete

---

## 🌐 ACCESS SERVICES

### Step 28: Port-Forward Kibana

```bash
# Forward Kibana to localhost
# If 5601 is busy, use 5602:5601
kubectl port-forward svc/kibana 5601:5601 -n $NAMESPACE

# Access: http://localhost:5601
```

**In Kibana UI:**

1. Go to **Management** → **Stack Management** → **Index Patterns**
2. Create index pattern: **stock-realtime-1m\***
   - Time field: **window_start**
3. Create index pattern: **stock-alerts-1m\***
   - Time field: **window_start**
4. Create index pattern: **batch-features\***
   - Time field: **month**
5. Go to **Discover** to view data

**📸 Screenshot 29**: Kibana accessible

---

### Step 29: Other Services (Optional)

```bash
# Port-forward Elasticsearch
# If 9200 is busy, use 9201:9200
kubectl port-forward svc/elasticsearch 9200:9200 -n $NAMESPACE &

# Port-forward HDFS NameNode UI
# If 9870 is busy, use 9871:9870
kubectl port-forward svc/hadoop-namenode 9870:9870 -n $NAMESPACE &

# List port-forwards
ps aux | grep "kubectl port-forward"
```

**Access URLs:**

- Elasticsearch: http://localhost:9200
- HDFS NameNode: http://localhost:9870

---

## 📈 SCALING & OPTIMIZATION

### Enable HPA (Phase 06 - Optional)

```bash
# Apply HPA
kubectl apply -f deployment/k8s/06-networking-scaling/hpa.yaml

# Check HPA
kubectl get hpa -n $NAMESPACE
```

**Note**: If `TARGETS` show `<unknown>`, install Metrics Server or wait for it to become ready.

---

### Scale Kafka

```bash
# Scale Kafka to 3 brokers
kubectl scale statefulset kafka --replicas=3 -n $NAMESPACE
kubectl wait --for=condition=ready pod -l app=kafka -n $NAMESPACE --timeout=300s
```

**Note**: On e2-medium nodes, scaling may fail due to CPU/memory limits. Use larger nodes or keep 1 broker.

---

### Enable Ingress (Optional)

```bash
# Apply ingress for external access
kubectl apply -f deployment/k8s/06-networking-scaling/ingress.yaml

# Wait for external IP (5-10 minutes)
kubectl get ingress -n $NAMESPACE -w
```

**Note**: `kubernetes.io/ingress.class` is deprecated. If needed, switch to `spec.ingressClassName` and ensure an Ingress controller is installed.

**Expected output:**

```
NAME              CLASS    ADDRESS         PORTS   AGE
bigdata-ingress   <none>   35.xxx.xxx.xxx  80      10m
```

---

## 🔧 TROUBLESHOOTING

### Pod Stuck in Pending

```bash
kubectl describe pod <pod-name> -n $NAMESPACE
kubectl top nodes
```

**Common causes:**

- Insufficient CPU/memory quota
- PVC not bound
- Node affinity issues

**Solutions:**

**Option 1: Reduce Resource Requests (Quick Fix for e2-medium)**

If using **e2-medium nodes** (1 vCPU), reduce Kafka/Zookeeper/HDFS/Elasticsearch/Spark/Kibana resource requests:

```bash
# Example: Reduce Kafka resources
kubectl patch statefulset kafka -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "100m"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "512Mi"}
]'

# Delete pod to recreate
kubectl delete pod <pod-name> -n $NAMESPACE
```

**Option 2: Upgrade Node Machine Type (Production)**

```bash
# Create new node pool with e2-standard-2 (2 vCPU, 8GB RAM)
gcloud container node-pools create standard-pool \
  --cluster=$CLUSTER_NAME \
  --zone=$ZONE \
  --machine-type=e2-standard-2 \
  --num-nodes=3 \
  --disk-size=50

# Cordon old nodes
for node in $(kubectl get nodes -l cloud.google.com/gke-nodepool=default-pool -o name); do
  kubectl cordon $node
done

# Delete old StatefulSets (will reschedule on new nodes)
kubectl delete statefulset --all -n $NAMESPACE --cascade=orphan
kubectl delete pod --all -n $NAMESPACE

# Reapply infrastructure
kubectl apply -f deployment/k8s/03-infrastructure/

# Delete old node pool
gcloud container node-pools delete default-pool --cluster=$CLUSTER_NAME --zone=$ZONE --quiet
```

**Option 3: Increase Cluster Size**

```bash
# Add more nodes to spread load
gcloud container clusters resize $CLUSTER_NAME --num-nodes=5 --zone=$ZONE
```

---

### Image Pull Errors

```bash
gcloud container images list-tags $GCR_HOSTNAME/$PROJECT_ID/bigdata-app

# Grant GKE access
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/storage.objectViewer
```

---

### No Data in Elasticsearch

```bash
# Check producer
kubectl logs -l app=kafka-producer -n $NAMESPACE --tail=50

# Check Kafka messages
kubectl exec -it kafka-0 -n $NAMESPACE -- \
  kafka-console-consumer \
    --bootstrap-server localhost:9092 \
    --topic stocks-realtime-spark \
    --from-beginning \
    --max-messages 5

# Check Spark
kubectl logs -l app=spark-streaming -n $NAMESPACE --tail=50
```

**If Spark pod keeps restarting due to probes:**

```bash
# Fix probes to match SparkSubmit process name
kubectl patch deployment spark-streaming-consumer -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/livenessProbe/exec/command/2", "value": "SparkSubmit"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/readinessProbe/exec/command/2", "value": "SparkSubmit"}
]'

kubectl delete pod -l app=spark-streaming -n $NAMESPACE
```

---

### Kibana: “No available fields”

**Nguyên nhân phổ biến:**

- Index có **0 documents** (Spark chưa đẩy dữ liệu vào ES)
- Time filter trong Kibana đang lọc sai khoảng thời gian
- Index pattern chưa refresh field list
- Mapping chưa tạo đúng kiểu `date`

**Kiểm tra nhanh:**

```bash
# 1) Đếm document
kubectl port-forward svc/elasticsearch 9201:9200 -n $NAMESPACE &
sleep 3
curl -X GET "http://localhost:9201/stock-alerts-1m/_count"

# 2) Xem mapping
curl -X GET "http://localhost:9201/stock-alerts-1m/_mapping?pretty"

pkill -f "port-forward.*elasticsearch"
```

**Khắc phục:**

1. **Nếu count = 0** → kiểm tra Spark Alerts log:

```bash
kubectl logs -l app=spark-streaming-alerts -n $NAMESPACE --tail=50
```

**Gợi ý**: Alert chỉ xuất hiện khi biến động đủ lớn. Có thể hạ ngưỡng tạm thời để kiểm thử:

```bash
kubectl patch deployment spark-streaming-alerts -n $NAMESPACE --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/env/5/value", "value": "0.0001"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/env/6/value", "value": "0.0001"}
]'
kubectl delete pod -l app=spark-streaming-alerts -n $NAMESPACE
```

Hoặc tạo 1 bản ghi test thủ công để Kibana có field:

```bash
kubectl port-forward svc/elasticsearch 9201:9200 -n $NAMESPACE &
sleep 3
curl -X POST "http://localhost:9201/stock-alerts-1m/_doc" \
  -H 'Content-Type: application/json' \
  -d '{"ticker":"TEST","window_start":"2026-01-15T08:30:00Z","window_end":"2026-01-15T08:31:00Z","return_pct_1m":0.02,"range_pct_1m":0.03,"alert_reason":"manual_test","direction":"up","alert_score":1.0,"@timestamp":"2026-01-15T08:30:30Z"}'
pkill -f "port-forward.*elasticsearch"
```

2. **Nếu có dữ liệu** → vào Kibana **Index Patterns** → chọn pattern → **Refresh field list**.
3. Kiểm tra **Time filter** trong Discover (Last 15 minutes → Last 24 hours).
4. Nếu mapping không có `window_start` hoặc sai kiểu date, tạo lại index template.

---

### Kafka Topics Missing

```bash
# List topics
kubectl exec -it kafka-0 -n $NAMESPACE -- \
  kafka-topics --list --bootstrap-server localhost:9092

# Create manually if needed
kubectl exec -it kafka-0 -n $NAMESPACE -- \
  kafka-topics \
    --create \
    --topic stocks-realtime \
    --bootstrap-server localhost:9092 \
    --partitions 1 \
    --replication-factor 1
```

---

### HDFS SafeMode

```bash
# Check status
kubectl exec -it hadoop-namenode-0 -n $NAMESPACE -- hdfs dfsadmin -safemode get

# Leave safe mode
kubectl exec -it hadoop-namenode-0 -n $NAMESPACE -- hdfs dfsadmin -safemode leave
```

---

### Elasticsearch Yellow Health

```bash
# Normal for single-node ES, reduce replicas
kubectl port-forward svc/elasticsearch 9201:9200 -n $NAMESPACE &
sleep 3
curl -X PUT "http://localhost:9201/_settings" \
  -H 'Content-Type: application/json' \
  -d '{"index": {"number_of_replicas": 0}}'
pkill -f "port-forward.*elasticsearch"
```

---

## 🗑️ COMPLETE TEARDOWN

### Delete Applications

```bash
# Delete all applications
kubectl delete deployment --all -n $NAMESPACE
kubectl delete statefulset --all -n $NAMESPACE
kubectl delete cronjob --all -n $NAMESPACE
kubectl delete job --all -n $NAMESPACE

# Wait for pods to terminate
kubectl wait --for=delete pod --all -n $NAMESPACE --timeout=300s
```

---

### Delete Data (⚠️ Permanent!)

```bash
# Delete PVCs (deletes all data)
kubectl delete pvc --all -n $NAMESPACE

# Verify
kubectl get pvc -n $NAMESPACE
```

---

### Delete Namespace

```bash
# Delete namespace (deletes all resources)
kubectl delete namespace $NAMESPACE

# Verify
kubectl get namespaces
```

---

### Delete GKE Cluster (Optional)

```bash
# ⚠️ WARNING: Deletes entire cluster
gcloud container clusters delete $CLUSTER_NAME --zone=$ZONE --quiet

# Verify
gcloud container clusters list
```

---

### Delete Container Images

```bash
# Delete images from GCR
gcloud container images delete $GCR_HOSTNAME/$PROJECT_ID/bigdata-app:latest --quiet
gcloud container images delete $GCR_HOSTNAME/$PROJECT_ID/bigdata-spark:latest --quiet

# Verify
gcloud container images list --repository=$GCR_HOSTNAME/$PROJECT_ID
```

---

## 📝 DEPLOYMENT CHECKLIST

- [ ] Cluster connected
- [ ] Environment variables set
- [ ] Images built & pushed to GCR
- [ ] Namespace created (00)
- [ ] ConfigMap applied (01)
- [ ] PVCs bound (02)
- [ ] Zookeeper running (03)
- [ ] Kafka running & topics exist (03)
- [ ] HDFS running & initialized (03)
- [ ] Elasticsearch running (03)
- [ ] Producer crawling data (04)
- [ ] Kafka-Spark bridge running (04)
- [ ] Spark Streaming processing (04)
- [ ] Spark Alerts deployed (04)
- [ ] Kibana accessible (04)
- [ ] CronJobs scheduled (05)
- [ ] Data in Elasticsearch
- [ ] HPA enabled (06 - optional)
- [ ] Ingress configured (06 - optional)

---

## 💡 IMPORTANT NOTES

### Window Duration Configuration

**⚠️ Critical**: Spark Streaming uses **2-minute windows** by default:

- Producer sends 5 tickers every 60 seconds
- Window needs >= 2 batches to aggregate properly
- If you see empty batches, increase `WINDOW_DURATION` in deployment YAML

**To change window duration:**

```yaml
# In spark-streaming-consumer-deployment.yaml
env:
  - name: WINDOW_DURATION
    value: "2 minutes" # Change this
  - name: WATERMARK_DELAY
    value: "3 minutes"
```

### Data Volume = 0

If Yahoo Finance returns `Volume: 0.0`, đây là normal cho after-market hours hoặc market closed. Data vẫn được process nhưng volume metrics sẽ = 0.

### Storage Classes

GKE sử dụng dynamic provisioning:

- `standard-rwo`: Standard Persistent Disk (default)
- `premium-rwo`: SSD Persistent Disk (faster)

File `persistent-volumes-gke.yaml` đã configure đúng cho GKE.

---

**Last Updated**: January 15, 2026  
**Version**: 2.0 (Refactored with organized folder structure)  
**Deployment Method**: Phased deployment (00 → 06)  
**Window Duration**: 2 minutes (configurable)
