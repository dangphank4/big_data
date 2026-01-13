# ☁️ GOOGLE KUBERNETES ENGINE (GKE) DEPLOYMENT GUIDE

**Complete step-by-step guide for deploying Big Data Stock Analysis System to GKE**

---

## 📋 TABLE OF CONTENTS

1. [Prerequisites](#-prerequisites)
2. [GCP Project Setup](#-gcp-project-setup)
3. [Install Required Tools](#-install-required-tools)
4. [Configure GCP Environment](#-configure-gcp-environment)
5. [Create GKE Cluster](#-create-gke-cluster)
6. [Build & Push Docker Images](#-build--push-docker-images)
7. [Deploy Infrastructure Services](#-deploy-infrastructure-services)
8. [Deploy Application Services](#-deploy-application-services)
9. [Verify Deployment](#-verify-deployment)
10. [Configure Monitoring](#-configure-monitoring)
11. [Access Services](#-access-services)
12. [Test Data Flow](#-test-data-flow)
13. [Scaling & Optimization](#-scaling--optimization)
14. [Troubleshooting](#-troubleshooting)
15. [Complete Teardown](#-complete-teardown)

---

## ✅ PREREQUISITES

### Required Accounts & Permissions

- **GCP Account** with billing enabled
- **IAM Roles Required**:
  - `roles/container.admin` (GKE Admin)
  - `roles/storage.admin` (GCR access)
  - `roles/compute.admin` (Compute resources)
  - `roles/iam.serviceAccountAdmin` (Service accounts)

### Local Tools Verification

```bash
# Check kubectl
kubectl version --client
# Expected: Client Version: v1.28.0 or higher

# Check gcloud
gcloud version
# Expected: Google Cloud SDK 450.0.0 or higher

# Check Docker
docker --version
# Expected: Docker version 20.10.x or higher

# Check git
git --version
```

**📸 Screenshot Checkpoint 1**: All tools installed and versions displayed

---

### System Requirements

- **Local Machine**: 4GB+ RAM, 10GB+ disk
- **GCP Quota**:
  - 16+ vCPUs in region
  - 64GB+ RAM
  - 500GB+ disk
- **Cost Estimate**: ~$400-600/month for production

---

## 🏗️ GCP PROJECT SETUP

### Step 1: Create GCP Project

```bash
# Set project name
export PROJECT_ID="bigdata-stock-$(date +%s)"
export PROJECT_NAME="BigData Stock Analysis"

# Create project
gcloud projects create $PROJECT_ID --name="$PROJECT_NAME"

# Set as current project
gcloud config set project $PROJECT_ID

# Verify
gcloud config list project
```

**Expected output:**

```
Created [https://cloudresourcemanager.googleapis.com/v1/projects/bigdata-stock-1234567890].
[core]
project = bigdata-stock-1234567890
```

**📸 Screenshot Checkpoint 2**: GCP project created

---

### Step 2: Enable Required APIs

```bash
# Enable APIs
gcloud services enable \
  container.googleapis.com \
  containerregistry.googleapis.com \
  compute.googleapis.com \
  storage-api.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com

# Wait for APIs to be enabled (30 seconds)
sleep 30

# Verify enabled services
gcloud services list --enabled | grep -E 'container|compute|storage|logging|monitoring'
```

**Expected output:**

```
container.googleapis.com        Kubernetes Engine API
compute.googleapis.com          Compute Engine API
storage-api.googleapis.com      Google Cloud Storage JSON API
...
```

**📸 Screenshot Checkpoint 3**: APIs enabled

---

### Step 3: Link Billing Account

```bash
# List billing accounts
gcloud billing accounts list

# Set billing account (replace with your account ID)
export BILLING_ACCOUNT_ID="01AB2C-34DE56-78FG90"
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT_ID

# Verify billing enabled
gcloud billing projects describe $PROJECT_ID
```

**Expected output:**

```
billingAccountName: billingAccounts/01AB2C-34DE56-78FG90
billingEnabled: true
```

**📸 Screenshot Checkpoint 4**: Billing linked

---

## 🛠️ INSTALL REQUIRED TOOLS

### Step 4: Configure kubectl

```bash
# Install gke-gcloud-auth-plugin (if not installed)
gcloud components install gke-gcloud-auth-plugin

# Verify installation
gke-gcloud-auth-plugin --version
```

**📸 Screenshot Checkpoint 5**: kubectl configured

---

### Step 5: Set Environment Variables

```bash
# Project configuration
export PROJECT_ID=$(gcloud config get-value project)
export REGION="us-central1"
export ZONE="us-central1-a"
export CLUSTER_NAME="bigdata-stock-cluster"
export NAMESPACE="bigdata"

# GCR configuration
export GCR_HOSTNAME="gcr.io"
export IMAGE_TAG="v1.0.0"

# Save to file for later use
cat > /tmp/gke-env.sh <<EOF
export PROJECT_ID="$PROJECT_ID"
export REGION="$REGION"
export ZONE="$ZONE"
export CLUSTER_NAME="$CLUSTER_NAME"
export NAMESPACE="$NAMESPACE"
export GCR_HOSTNAME="$GCR_HOSTNAME"
export IMAGE_TAG="$IMAGE_TAG"
EOF

# Verify
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Cluster: $CLUSTER_NAME"
```

**📸 Screenshot Checkpoint 6**: Environment variables set

---

## ☸️ CREATE GKE CLUSTER

### Step 6: Create GKE Cluster

```bash
# Create cluster (this takes 5-10 minutes)
gcloud container clusters create $CLUSTER_NAME \
  --zone=$ZONE \
  --num-nodes=4 \
  --machine-type=n1-standard-4 \
  --disk-size=100GB \
  --disk-type=pd-standard \
  --enable-autoscaling \
  --min-nodes=3 \
  --max-nodes=8 \
  --enable-autorepair \
  --enable-autoupgrade \
  --addons=HorizontalPodAutoscaling,HttpLoadBalancing,GcePersistentDiskCsiDriver \
  --enable-stackdriver-kubernetes \
  --logging=SYSTEM,WORKLOAD \
  --monitoring=SYSTEM

# This will take several minutes...
```

**Expected output:**

```
Creating cluster bigdata-stock-cluster in us-central1-a...done.
Created [https://container.googleapis.com/v1/projects/bigdata-stock-1234567890/zones/us-central1-a/clusters/bigdata-stock-cluster].
kubeconfig entry generated for bigdata-stock-cluster.
NAME                    LOCATION       MASTER_VERSION  NODE_VERSION   NUM_NODES  STATUS
bigdata-stock-cluster   us-central1-a  1.28.5-gke.1217 1.28.5-gke.1217  4         RUNNING
```

**📸 Screenshot Checkpoint 7**: GKE cluster created

---

### Step 7: Connect to Cluster

```bash
# Get cluster credentials
gcloud container clusters get-credentials $CLUSTER_NAME --zone=$ZONE

# Verify connection
kubectl cluster-info

# Check nodes
kubectl get nodes
```

**Expected output:**

```
Kubernetes control plane is running at https://35.xxx.xxx.xxx

NAME                                    STATUS   ROLES    AGE   VERSION
gke-bigdata-stock-default-xxx-abcd      Ready    <none>   2m    v1.28.5-gke.1217
gke-bigdata-stock-default-xxx-efgh      Ready    <none>   2m    v1.28.5-gke.1217
gke-bigdata-stock-default-xxx-ijkl      Ready    <none>   2m    v1.28.5-gke.1217
gke-bigdata-stock-default-xxx-mnop      Ready    <none>   2m    v1.28.5-gke.1217
```

**📸 Screenshot Checkpoint 8**: Connected to cluster

---

### Step 8: Create Namespace

```bash
# Apply namespace
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/namespace.yaml

# Verify
kubectl get namespaces

# Set default namespace
kubectl config set-context --current --namespace=$NAMESPACE
```

**Expected output:**

```
namespace/bigdata created

NAME              STATUS   AGE
bigdata           Active   5s
default           Active   10m
kube-system       Active   10m
```

**📸 Screenshot Checkpoint 9**: Namespace created

---

## 🏗️ BUILD & PUSH DOCKER IMAGES

### Step 9: Configure Docker for GCR

```bash
# Configure Docker authentication
gcloud auth configure-docker

# Verify
cat ~/.docker/config.json | grep gcr.io
```

**Expected output:**

```
  "credHelpers": {
    "gcr.io": "gcloud",
    ...
  }
```

**📸 Screenshot Checkpoint 10**: Docker configured for GCR

---

### Step 10: Build Application Image

```bash
cd /home/danz/Downloads/big_data

# Build image
docker build -f config/Dockerfile -t bigdata-app:$IMAGE_TAG .

# Tag for GCR
docker tag bigdata-app:$IMAGE_TAG $GCR_HOSTNAME/$PROJECT_ID/bigdata-app:$IMAGE_TAG
docker tag bigdata-app:$IMAGE_TAG $GCR_HOSTNAME/$PROJECT_ID/bigdata-app:latest

# Verify
docker images | grep bigdata-app
```

**Expected output:**

```
bigdata-app                                    v1.0.0    abc123def456   2 minutes ago   1.2GB
gcr.io/bigdata-stock-1234567890/bigdata-app   v1.0.0    abc123def456   2 minutes ago   1.2GB
gcr.io/bigdata-stock-1234567890/bigdata-app   latest    abc123def456   2 minutes ago   1.2GB
```

**📸 Screenshot Checkpoint 11**: Image built and tagged

---

### Step 11: Push to GCR

```bash
# Push images to GCR
docker push $GCR_HOSTNAME/$PROJECT_ID/bigdata-app:$IMAGE_TAG
docker push $GCR_HOSTNAME/$PROJECT_ID/bigdata-app:latest

# Verify in GCR
gcloud container images list --repository=$GCR_HOSTNAME/$PROJECT_ID
```

**Expected output:**

```
NAME
gcr.io/bigdata-stock-1234567890/bigdata-app

# List tags
gcloud container images list-tags $GCR_HOSTNAME/$PROJECT_ID/bigdata-app

DIGEST        TAGS          TIMESTAMP
sha256:abc... v1.0.0,latest 2024-01-13T10:00:00
```

**📸 Screenshot Checkpoint 12**: Images pushed to GCR

---

## 🚀 DEPLOY INFRASTRUCTURE SERVICES

### Step 12: Create Persistent Volumes

```bash
# Apply PV and PVC
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/persistent-volumes.yaml

# Wait 10 seconds
sleep 10

# Verify
kubectl get pv,pvc -n $NAMESPACE
```

**Expected output:**

```
NAME                        CAPACITY   STATUS   CLAIM
persistentvolume/hdfs-pv    100Gi      Bound    bigdata/hdfs-pvc
persistentvolume/kafka-pv   50Gi       Bound    bigdata/kafka-pvc
persistentvolume/zoo-pv     10Gi       Bound    bigdata/zookeeper-pvc

NAME                              STATUS   VOLUME      CAPACITY
persistentvolumeclaim/hdfs-pvc    Bound    hdfs-pv     100Gi
persistentvolumeclaim/kafka-pvc   Bound    kafka-pv    50Gi
...
```

**📸 Screenshot Checkpoint 13**: Persistent volumes created

---

### Step 13: Apply ConfigMap

```bash
# Update ConfigMap with GCR image
sed -i "s|bigdata-app:latest|$GCR_HOSTNAME/$PROJECT_ID/bigdata-app:latest|g" \
  /home/danz/Downloads/big_data/deployment/k8s/configmap.yaml

# Apply ConfigMap
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/configmap.yaml

# Verify
kubectl get configmap -n $NAMESPACE
kubectl describe configmap bigdata-config -n $NAMESPACE
```

**Expected output:**

```
NAME             DATA   AGE
bigdata-config   15     10s

Data
====
KAFKA_BROKER:
----
kafka:9092
KAFKA_TOPIC:
----
stocks-realtime
...
```

**📸 Screenshot Checkpoint 14**: ConfigMap applied

---

### Step 14: Deploy Zookeeper

```bash
# Apply Zookeeper StatefulSet
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/zookeeper-statefulset.yaml

# Wait for Zookeeper to be ready (2 minutes)
kubectl wait --for=condition=ready pod -l app=zookeeper -n $NAMESPACE --timeout=300s

# Check status
kubectl get statefulset,pod -n $NAMESPACE -l app=zookeeper
```

**Expected output:**

```
NAME                         READY   AGE
statefulset.apps/zookeeper   1/1     2m

NAME              READY   STATUS    RESTARTS   AGE
pod/zookeeper-0   1/1     Running   0          2m
```

**📸 Screenshot Checkpoint 15**: Zookeeper running

---

### Step 15: Deploy Kafka

```bash
# Apply Kafka StatefulSet
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/kafka-statefulset.yaml

# Wait for Kafka to be ready (3 minutes)
kubectl wait --for=condition=ready pod -l app=kafka -n $NAMESPACE --timeout=300s

# Check status
kubectl get statefulset,pod,svc -n $NAMESPACE -l app=kafka
```

**Expected output:**

```
NAME                     READY   AGE
statefulset.apps/kafka   1/1     3m

NAME          READY   STATUS    RESTARTS   AGE
pod/kafka-0   1/1     Running   0          3m

NAME            TYPE        CLUSTER-IP    PORT(S)
service/kafka   ClusterIP   10.x.x.x      9092/TCP
```

**📸 Screenshot Checkpoint 16**: Kafka running

---

### Step 16: Verify Kafka Topic

```bash
# Check Kafka logs
kubectl logs kafka-0 -n $NAMESPACE | tail -30

# List topics
kubectl exec -it kafka-0 -n $NAMESPACE -- kafka-topics.sh \
  --list \
  --bootstrap-server localhost:9092
```

**Expected output:**

```
stocks-realtime
stocks-realtime-spark
```

**📸 Screenshot Checkpoint 17**: Kafka topic exists

---

### Step 17: Deploy HDFS

```bash
# Apply HDFS StatefulSet
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/hdfs-statefulset.yaml

# Wait for HDFS to be ready (3 minutes)
kubectl wait --for=condition=ready pod -l app=hdfs-namenode -n $NAMESPACE --timeout=300s

# Check status
kubectl get statefulset,pod,svc -n $NAMESPACE | grep hdfs
```

**Expected output:**

```
statefulset.apps/hdfs-namenode   1/1     3m
statefulset.apps/hdfs-datanode   1/1     3m

pod/hdfs-namenode-0   1/1     Running   0   3m
pod/hdfs-datanode-0   1/1     Running   0   3m

service/hdfs-namenode   ClusterIP   10.x.x.x   9870/TCP,9000/TCP
service/hdfs-datanode   ClusterIP   10.x.x.x   9866/TCP
```

**📸 Screenshot Checkpoint 18**: HDFS running

---

### Step 18: Verify HDFS Cluster

```bash
# Check HDFS status
kubectl exec -it hdfs-namenode-0 -n $NAMESPACE -- hdfs dfsadmin -report

# Create base directory
kubectl exec -it hdfs-namenode-0 -n $NAMESPACE -- hdfs dfs -mkdir -p /stock-data
kubectl exec -it hdfs-namenode-0 -n $NAMESPACE -- hdfs dfs -chmod 777 /stock-data

# Verify
kubectl exec -it hdfs-namenode-0 -n $NAMESPACE -- hdfs dfs -ls /
```

**Expected output:**

```
Live datanodes (1):
Name: 10.x.x.x:9866 (hdfs-datanode-0.hdfs-datanode)
...

Found 1 items
drwxrwxrwx   - root supergroup          0 2024-01-13 10:00 /stock-data
```

**📸 Screenshot Checkpoint 19**: HDFS cluster healthy

---

### Step 18B (Optional): Backfill Dữ Liệu Lịch Sử vào HDFS (phục vụ Batch)

Mặc định, CronJob `hdfs-archiver` chỉ lấy dữ liệu gần đây (vd: 24h). Nếu batch của bạn cần dữ liệu từ rất lâu về trước, hãy chạy Job backfill này 1 lần để nạp dữ liệu lịch sử vào HDFS (`/stock-data`).

Lưu ý: dữ liệu theo phút (`1m`) từ yfinance thường bị giới hạn lịch sử gần đây; backfill “rất lâu” nên dùng `1d`.

```bash
# Apply one-time backfill job (edit tickers/days in YAML if needed)
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/hdfs-backfill-job.yaml

# Follow logs
kubectl logs -n $NAMESPACE -f job/hdfs-historical-backfill

# Verify HDFS data appears
kubectl exec -it hdfs-namenode-0 -n $NAMESPACE -- hdfs dfs -ls /stock-data | tail -20
```

---

### Step 19: Deploy Elasticsearch

```bash
# Apply Elasticsearch StatefulSet
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/elasticsearch-statefulset.yaml

# Wait for Elasticsearch to be ready (4 minutes)
kubectl wait --for=condition=ready pod -l app=elasticsearch -n $NAMESPACE --timeout=400s

# Check status
kubectl get statefulset,pod,svc -n $NAMESPACE -l app=elasticsearch
```

**Expected output:**

```
NAME                             READY   AGE
statefulset.apps/elasticsearch   1/1     4m

NAME                  READY   STATUS    RESTARTS   AGE
pod/elasticsearch-0   1/1     Running   0          4m

NAME                    TYPE        CLUSTER-IP    PORT(S)
service/elasticsearch   ClusterIP   10.x.x.x      9200/TCP
```

**📸 Screenshot Checkpoint 20**: Elasticsearch running

---

### Step 20: Verify Elasticsearch

```bash
# Port-forward to access Elasticsearch
kubectl port-forward svc/elasticsearch 9200:9200 -n $NAMESPACE &
PF_PID=$!

# Wait 5 seconds
sleep 5

# Check Elasticsearch health
curl -X GET "http://localhost:9200/_cluster/health?pretty"

# Kill port-forward
kill $PF_PID
```

**Expected output:**

```json
{
  "cluster_name": "docker-cluster",
  "status": "yellow",
  "number_of_nodes": 1,
  "active_primary_shards": 0
}
```

**📸 Screenshot Checkpoint 21**: Elasticsearch healthy

---

## 📡 DEPLOY APPLICATION SERVICES

### Step 21: Update Deployment Manifests with GCR Image

```bash
# Update all app manifests that use the placeholder PROJECT_ID
for file in \
  /home/danz/Downloads/big_data/deployment/k8s/*-deployment.yaml \
  /home/danz/Downloads/big_data/deployment/k8s/*-cronjob.yaml \
  /home/danz/Downloads/big_data/deployment/k8s/*-job.yaml
do
  # Some files may not exist depending on your repo version
  [ -f "$file" ] || continue
  sed -i "s|gcr.io/PROJECT_ID/bigdata-app:latest|$GCR_HOSTNAME/$PROJECT_ID/bigdata-app:latest|g" "$file"
  sed -i "s|gcr.io/PROJECT_ID/bigdata-spark:latest|$GCR_HOSTNAME/$PROJECT_ID/bigdata-spark:latest|g" "$file"
done

# Verify changes
grep "image:" /home/danz/Downloads/big_data/deployment/k8s/kafka-producer-crawl-deployment.yaml
```

**Expected output:**

```yaml
image: gcr.io/bigdata-stock-1234567890/bigdata-app:latest
```

**📸 Screenshot Checkpoint 22**: Deployment manifests updated

---

### Step 22: Deploy Kafka Producer (Real-time Crawler)

```bash
# Apply producer deployment
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/kafka-producer-crawl-deployment.yaml

# Wait for producer to be ready
kubectl wait --for=condition=ready pod -l app=kafka-producer -n $NAMESPACE --timeout=120s

# Check status
kubectl get deployment,pod -n $NAMESPACE -l app=kafka-producer
```

**Expected output:**

```
NAME                             READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/kafka-producer   1/1     1            1           1m

NAME                                  READY   STATUS    RESTARTS   AGE
pod/kafka-producer-abc123-xyz456      1/1     Running   0          1m
```

**📸 Screenshot Checkpoint 23**: Kafka producer deployed

---

### Step 23: Check Producer Logs

```bash
# Get producer pod name
PRODUCER_POD=$(kubectl get pod -n $NAMESPACE -l app=kafka-producer -o jsonpath='{.items[0].metadata.name}')

# Stream logs (Ctrl+C to stop)
kubectl logs -f $PRODUCER_POD -n $NAMESPACE
```

**Expected output:**

```
[START] Real-time crawling for 5 tickers every 60s
[CRAWL] AAPL
[CRAWL] NVDA
[CRAWL] TSLA
[CRAWL] MSFT
[CRAWL] GOOGL
[BATCH 1] 2024-01-13T10:05:00 | 5 records | 3.45s
[WAIT] 60s until next crawl...
```

**📸 Screenshot Checkpoint 24**: Producer crawling data

---

### Step 24: Deploy Kafka Bridge + Spark Streaming

```bash
# 1) Kafka -> Spark bridge (stocks-realtime -> stocks-realtime-spark)
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/kafka-spark-bridge-deployment.yaml

# 2) Spark Streaming (metrics)
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/spark-streaming-consumer-deployment.yaml

# 3) Spark Streaming (alerts)
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/spark-alerts-deployment.yaml

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=kafka-spark-bridge -n $NAMESPACE --timeout=180s
kubectl wait --for=condition=ready pod -l app=spark-streaming -n $NAMESPACE --timeout=180s
kubectl wait --for=condition=ready pod -l app=spark-streaming-alerts -n $NAMESPACE --timeout=180s

# Check status
kubectl get deployment,pod -n $NAMESPACE -l app=kafka-spark-bridge
kubectl get deployment,pod -n $NAMESPACE -l app=spark-streaming
kubectl get deployment,pod -n $NAMESPACE -l app=spark-streaming-alerts
```

**Expected output:**

```
NAME                                  READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/kafka-spark-bridge     1/1     1            1           1m
deployment.apps/spark-streaming-consumer 1/1   1            1           1m
deployment.apps/spark-streaming-alerts 1/1     1            1           1m
```

**📸 Screenshot Checkpoint 25**: Spark Streaming deployed

---

### Step 25: Check Spark Logs

```bash
# Get Spark pods
SPARK_METRICS_POD=$(kubectl get pod -n $NAMESPACE -l app=spark-streaming -o jsonpath='{.items[0].metadata.name}')
SPARK_ALERTS_POD=$(kubectl get pod -n $NAMESPACE -l app=spark-streaming-alerts -o jsonpath='{.items[0].metadata.name}')

# Stream logs (metrics)
kubectl logs -f $SPARK_METRICS_POD -n $NAMESPACE | tail -50

# Stream logs (alerts)
kubectl logs -f $SPARK_ALERTS_POD -n $NAMESPACE | tail -50
```

**Expected output:**

```
[START] Spark Streaming Consumer - Topic: stocks-realtime-spark
[SPARK] Initializing SparkSession...
[SPARK] Reading from Kafka...
[READY] Streaming queries started
  ✓ metrics stream → stock-realtime-1m
  ✓ alerts stream  → stock-alerts-1m
```

**📸 Screenshot Checkpoint 26**: Spark Streaming processing data

---

### Step 26: Deploy HDFS Archiver CronJob

```bash
# Apply CronJob
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/hdfs-archiver-cronjob.yaml

# Verify CronJob created
kubectl get cronjob -n $NAMESPACE
```

**Expected output:**

```
NAME            SCHEDULE     SUSPEND   ACTIVE   LAST SCHEDULE   AGE
hdfs-archiver   0 0 * * *    False     0        <none>          30s
```

**📸 Screenshot Checkpoint 27**: CronJob scheduled

---

### Step 27: Manually Trigger HDFS Archiver

```bash
# Create a manual job from CronJob
kubectl create job --from=cronjob/hdfs-archiver manual-archive-$(date +%s) -n $NAMESPACE

# Wait for job to complete
kubectl wait --for=condition=complete job -l job-name --timeout=300s -n $NAMESPACE

# Check job status
kubectl get jobs -n $NAMESPACE

# Get job pod name and check logs
ARCHIVE_POD=$(kubectl get pods -n $NAMESPACE -l job-name --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
kubectl logs $ARCHIVE_POD -n $NAMESPACE
```

**Expected output:**

```
NAME                          COMPLETIONS   DURATION   AGE
manual-archive-1234567890     1/1           45s        1m

[START] Archiving data from 2024-01-13 09:00:00 to 2024-01-13 10:00:00
[CONSUME] Reading from Kafka...
[DONE] Read 120 messages from Kafka
[HDFS] Writing 1 dates to HDFS...
[COMPLETE] Wrote 5 files, 120 new records to HDFS
```

**📸 Screenshot Checkpoint 28**: HDFS archiver completed

---

## ✔️ VERIFY DEPLOYMENT

### Step 28: Check All Resources

```bash
# List all resources in namespace
kubectl get all -n $NAMESPACE
```

**Expected output:**

```
NAME                                  READY   STATUS    RESTARTS   AGE
pod/elasticsearch-0                   1/1     Running   0          15m
pod/hdfs-datanode-0                   1/1     Running   0          18m
pod/hdfs-namenode-0                   1/1     Running   0          18m
pod/kafka-0                           1/1     Running   0          20m
pod/kafka-producer-abc123-xyz456      1/1     Running   0          10m
pod/spark-streaming-abc123-xyz456     1/1     Running   0          8m
pod/zookeeper-0                       1/1     Running   0          22m

NAME                        TYPE        CLUSTER-IP      PORT(S)
service/elasticsearch       ClusterIP   10.x.x.x        9200/TCP
service/hdfs-namenode       ClusterIP   10.x.x.x        9870/TCP,9000/TCP
service/kafka               ClusterIP   10.x.x.x        9092/TCP
service/zookeeper           ClusterIP   10.x.x.x        2181/TCP

NAME                              READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/kafka-producer    1/1     1            1           10m
deployment.apps/spark-streaming   1/1     1            1           8m

NAME                            READY   AGE
statefulset.apps/elasticsearch  1/1     15m
statefulset.apps/hdfs-datanode  1/1     18m
statefulset.apps/hdfs-namenode  1/1     18m
statefulset.apps/kafka          1/1     20m
statefulset.apps/zookeeper      1/1     22m

NAME                      SCHEDULE     SUSPEND   ACTIVE   LAST SCHEDULE   AGE
cronjob.batch/hdfs-archiver   0 0 * * *    False     0        5m              15m
```

**📸 Screenshot Checkpoint 29**: All resources running

---

### Step 29: Verify Data in Elasticsearch

```bash
# Port-forward Elasticsearch
kubectl port-forward svc/elasticsearch 9200:9200 -n $NAMESPACE &
PF_PID=$!
sleep 5

# Check indices
curl -X GET "http://localhost:9200/_cat/indices?v"

# Check data count
curl -X GET "http://localhost:9200/stock-realtime-1m/_count"

# Query recent data
curl -X GET "http://localhost:9200/stock-realtime-1m/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 5,
    "sort": [{"window_start": {"order": "desc"}}]
  }'

# Kill port-forward
kill $PF_PID
```

**Expected output:**

```
health status index              uuid   pri rep docs.count
yellow open   stock-realtime-1m  xyz123   1   1         45
yellow open   stock-alerts-1m    abc456   1   1         12

{"count":45,"_shards":{"total":1,"successful":1,"skipped":0,"failed":0}}
```

**📸 Screenshot Checkpoint 30**: Data in Elasticsearch

---

### Step 30: Verify Data in HDFS

```bash
# List HDFS files
kubectl exec -it hdfs-namenode-0 -n $NAMESPACE -- hdfs dfs -ls -R /stock-data

# Check file content
kubectl exec -it hdfs-namenode-0 -n $NAMESPACE -- \
  hdfs dfs -cat /stock-data/$(date +%Y-%m-%d)/AAPL.json | head -5
```

**Expected output:**

```
drwxrwxrwx   - root supergroup          0 2024-01-13 10:00 /stock-data/2024-01-13
-rw-r--r--   1 root supergroup       2456 2024-01-13 10:00 /stock-data/2024-01-13/AAPL.json
-rw-r--r--   1 root supergroup       2391 2024-01-13 10:00 /stock-data/2024-01-13/NVDA.json
...

{"ticker":"AAPL","company":"Apple Inc.","time":"2024-01-13T10:05:00",...}
```

**📸 Screenshot Checkpoint 31**: Data in HDFS

---

## 📊 CONFIGURE MONITORING

### Step 31 (Optional): Enable ServiceMonitor/PodMonitor

```bash
# NOTE: monitoring.yaml defines ServiceMonitor/PodMonitor resources.
# These require Prometheus Operator CRDs to be installed in the cluster.

# Check CRDs
kubectl get crd servicemonitors.monitoring.coreos.com podmonitors.monitoring.coreos.com

# If CRDs exist, apply monitoring configuration
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/monitoring.yaml
```

**📸 Screenshot Checkpoint 32**: Monitoring resources applied

---

### Step 32: Access Cloud Monitoring

```bash
# View GKE dashboard
gcloud container clusters describe $CLUSTER_NAME \
  --zone=$ZONE \
  --format="value(monitoringConfig)"

# Open Cloud Monitoring in browser
echo "https://console.cloud.google.com/monitoring/dashboards?project=$PROJECT_ID"
```

**📸 Screenshot Checkpoint 33**: Cloud Monitoring dashboard

---

### Step 33: Check Pod Metrics

```bash
# Get resource usage
kubectl top nodes
kubectl top pods -n $NAMESPACE
```

**Expected output:**

```
NAME                                    CPU(cores)   MEMORY(bytes)
gke-bigdata-stock-default-xxx-abcd      245m         2456Mi
...

NAME                                  CPU(cores)   MEMORY(bytes)
elasticsearch-0                       150m         1500Mi
kafka-producer-abc123-xyz456          50m          256Mi
spark-streaming-abc123-xyz456         200m         1024Mi
...
```

**📸 Screenshot Checkpoint 34**: Resource usage

---

## 🌐 ACCESS SERVICES

### Step 34: Deploy Ingress (Optional)

```bash
# Apply ingress configuration
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/ingress.yaml

# Wait for external IP (this may take 5-10 minutes)
kubectl get ingress -n $NAMESPACE -w
```

**Expected output:**

```
NAME              CLASS    HOSTS   ADDRESS         PORTS   AGE
bigdata-ingress   <none>   *       35.xxx.xxx.xxx  80      10m
```

**📸 Screenshot Checkpoint 35**: Ingress created with external IP

---

### Step 35: Port-Forward for Local Access

```bash
# Forward Elasticsearch
kubectl port-forward svc/elasticsearch 9200:9200 -n $NAMESPACE &

# Forward HDFS NameNode UI
kubectl port-forward svc/hdfs-namenode 9870:9870 -n $NAMESPACE &

# List port-forwards
ps aux | grep "kubectl port-forward"
```

**Access URLs:**

- Elasticsearch: http://localhost:9200
- HDFS NameNode UI: http://localhost:9870

**📸 Screenshot Checkpoint 36**: Services accessible locally

---

## 🧪 TEST DATA FLOW

### Step 36: End-to-End Data Flow Test

```bash
# 1. Check producer is sending data
kubectl logs -l app=kafka-producer -n $NAMESPACE --tail=20

# 2. Verify Kafka messages
kubectl exec -it kafka-0 -n $NAMESPACE -- \
  kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 \
    --topic stocks-realtime \
    --from-beginning \
    --max-messages 5

# 3. Check Spark is processing
kubectl logs -l app=spark-streaming -n $NAMESPACE --tail=30

# 4. Verify Elasticsearch data
kubectl port-forward svc/elasticsearch 9200:9200 -n $NAMESPACE &
sleep 5
curl -X GET "http://localhost:9200/stock-realtime-1m/_count"
pkill -f "port-forward.*elasticsearch"
```

**📸 Screenshot Checkpoint 37**: Complete data flow verified

---

### Step 37: Load Testing

```bash
# Check current throughput
kubectl logs -l app=kafka-producer -n $NAMESPACE --tail=50 | grep "BATCH"

# Monitor Kafka lag
kubectl exec -it kafka-0 -n $NAMESPACE -- \
  kafka-consumer-groups.sh \
    --bootstrap-server localhost:9092 \
    --describe \
    --group spark-streaming-group
```

**Expected output:**

```
GROUP                TOPIC            PARTITION  CURRENT-OFFSET  LAG
spark-streaming-group stocks-realtime  0          1234            0
```

**📸 Screenshot Checkpoint 38**: No consumer lag

---

## 📈 SCALING & OPTIMIZATION

### Step 38: Enable Horizontal Pod Autoscaling

```bash
# Apply HPA configuration
kubectl apply -f /home/danz/Downloads/big_data/deployment/k8s/hpa.yaml

# Check HPA status
kubectl get hpa -n $NAMESPACE
```

**Expected output:**

```
NAME              REFERENCE                    TARGETS         MINPODS   MAXPODS   REPLICAS
kafka-producer    Deployment/kafka-producer    cpu: 25%/80%    1         3         1
spark-streaming   Deployment/spark-streaming   cpu: 30%/80%    1         5         1
```

**📸 Screenshot Checkpoint 39**: HPA configured

---

### Step 39: Scale Kafka Brokers

```bash
# Scale Kafka to 3 brokers
kubectl scale statefulset kafka --replicas=3 -n $NAMESPACE

# Wait for new brokers
kubectl wait --for=condition=ready pod -l app=kafka -n $NAMESPACE --timeout=300s

# Verify
kubectl get statefulset,pod -n $NAMESPACE -l app=kafka
```

**Expected output:**

```
NAME                     READY   AGE
statefulset.apps/kafka   3/3     30m

NAME          READY   STATUS    RESTARTS   AGE
pod/kafka-0   1/1     Running   0          30m
pod/kafka-1   1/1     Running   0          5m
pod/kafka-2   1/1     Running   0          5m
```

**📸 Screenshot Checkpoint 40**: Kafka scaled to 3 brokers

---

### Step 40: Increase HDFS Capacity

```bash
# Scale HDFS datanodes to 3
kubectl scale statefulset hdfs-datanode --replicas=3 -n $NAMESPACE

# Wait for new datanodes
kubectl wait --for=condition=ready pod -l app=hdfs-datanode -n $NAMESPACE --timeout=300s

# Verify HDFS cluster
kubectl exec -it hdfs-namenode-0 -n $NAMESPACE -- hdfs dfsadmin -report
```

**Expected output:**

```
Live datanodes (3):
Name: 10.x.x.x:9866 (hdfs-datanode-0)
Name: 10.x.x.x:9866 (hdfs-datanode-1)
Name: 10.x.x.x:9866 (hdfs-datanode-2)
```

**📸 Screenshot Checkpoint 41**: HDFS scaled to 3 datanodes

---

## 🔧 TROUBLESHOOTING

### Common Issues

#### Issue 1: Pod Stuck in Pending

```bash
# Check pod events
kubectl describe pod <pod-name> -n $NAMESPACE

# Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# If quota exceeded, add nodes to cluster
gcloud container clusters resize $CLUSTER_NAME \
  --num-nodes=5 \
  --zone=$ZONE
```

---

#### Issue 2: Image Pull Errors

```bash
# Check image exists in GCR
gcloud container images list-tags $GCR_HOSTNAME/$PROJECT_ID/bigdata-app

# Grant GKE access to GCR
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/storage.objectViewer

# Re-create pod
kubectl delete pod <pod-name> -n $NAMESPACE
```

---

#### Issue 3: Kafka Connection Errors

```bash
# Check Kafka service
kubectl get svc kafka -n $NAMESPACE

# Check Kafka logs
kubectl logs kafka-0 -n $NAMESPACE | grep -i error

# Verify Zookeeper
kubectl exec -it kafka-0 -n $NAMESPACE -- \
  zookeeper-shell.sh zookeeper:2181 ls /brokers/ids
```

---

#### Issue 4: HDFS SafeMode

```bash
# Check HDFS status
kubectl exec -it hdfs-namenode-0 -n $NAMESPACE -- hdfs dfsadmin -safemode get

# Leave safe mode (if stuck)
kubectl exec -it hdfs-namenode-0 -n $NAMESPACE -- hdfs dfsadmin -safemode leave

# Format namenode (ONLY if corrupted, DELETES ALL DATA)
kubectl exec -it hdfs-namenode-0 -n $NAMESPACE -- hdfs namenode -format
```

---

#### Issue 5: Elasticsearch Yellow Health

```bash
# This is normal for single-node ES
# Check cluster health
kubectl exec -it elasticsearch-0 -n $NAMESPACE -- \
  curl -X GET "localhost:9200/_cluster/health?pretty"

# Reduce replicas (single-node cluster)
kubectl exec -it elasticsearch-0 -n $NAMESPACE -- \
  curl -X PUT "localhost:9200/_settings" \
    -H 'Content-Type: application/json' \
    -d '{"index": {"number_of_replicas": 0}}'
```

---

## 🗑️ COMPLETE TEARDOWN

### Step 41: View Current Resources Before Cleanup

```bash
# List all resources
kubectl get all -n $NAMESPACE

# List persistent volumes
kubectl get pv,pvc -n $NAMESPACE

# Check GKE cluster
gcloud container clusters list --filter="name:$CLUSTER_NAME"

# Check GCR images
gcloud container images list --repository=$GCR_HOSTNAME/$PROJECT_ID
```

**📸 Screenshot Checkpoint 42**: Resources before teardown

---

### Step 42: Delete Application Resources

```bash
# Delete deployments and StatefulSets
kubectl delete deployment --all -n $NAMESPACE
kubectl delete statefulset --all -n $NAMESPACE
kubectl delete cronjob --all -n $NAMESPACE
kubectl delete job --all -n $NAMESPACE

# Wait for pods to terminate
kubectl wait --for=delete pod --all -n $NAMESPACE --timeout=300s

# Verify
kubectl get all -n $NAMESPACE
```

**Expected output:**

```
No resources found in bigdata namespace.
```

**📸 Screenshot Checkpoint 43**: Application resources deleted

---

### Step 43: Delete Persistent Data

```bash
# ⚠️ WARNING: This deletes ALL data!

# Delete PVCs (this will delete PVs)
kubectl delete pvc --all -n $NAMESPACE

# Verify
kubectl get pv,pvc
```

**Expected output:**

```
No resources found
```

**📸 Screenshot Checkpoint 44**: Persistent data deleted

---

### Step 44: Delete Namespace

```bash
# Delete namespace (deletes all resources in it)
kubectl delete namespace $NAMESPACE

# Verify
kubectl get namespaces
```

**📸 Screenshot Checkpoint 45**: Namespace deleted

---

### Step 45: Delete GKE Cluster

```bash
# ⚠️ WARNING: This deletes the entire cluster!

# Delete cluster (takes 5-10 minutes)
gcloud container clusters delete $CLUSTER_NAME \
  --zone=$ZONE \
  --quiet

# Verify
gcloud container clusters list
```

**Expected output:**

```
Listed 0 items.
```

**📸 Screenshot Checkpoint 46**: GKE cluster deleted

---

### Step 46: Delete Container Images

```bash
# List all images
gcloud container images list --repository=$GCR_HOSTNAME/$PROJECT_ID

# Delete images
gcloud container images delete $GCR_HOSTNAME/$PROJECT_ID/bigdata-app:latest --quiet
gcloud container images delete $GCR_HOSTNAME/$PROJECT_ID/bigdata-app:$IMAGE_TAG --quiet

# Verify
gcloud container images list --repository=$GCR_HOSTNAME/$PROJECT_ID
```

**Expected output:**

```
Listed 0 items.
```

**📸 Screenshot Checkpoint 47**: Container images deleted

---

### Step 47: Delete GCP Project (Optional)

```bash
# ⚠️ WARNING: This deletes the ENTIRE project!

# Delete project
gcloud projects delete $PROJECT_ID --quiet

# Verify
gcloud projects list --filter="projectId:$PROJECT_ID"
```

**Expected output:**

```
Listed 0 items.
```

**📸 Screenshot Checkpoint 48**: GCP project deleted

---

### Step 48: Verify Complete Cleanup

```bash
# Check no resources remain
gcloud container clusters list
gcloud compute disks list
gcloud compute instances list
gcloud container images list

# Check billing
echo "Check billing console: https://console.cloud.google.com/billing"
echo "Ensure no ongoing charges"
```

**📸 Screenshot Checkpoint 49**: No resources remain

---

### Step 49: Clean Local Configuration

```bash
# Remove kubectl context
kubectl config get-contexts
kubectl config delete-context gke_${PROJECT_ID}_${ZONE}_${CLUSTER_NAME}

# Remove gcloud config
gcloud config configurations list
gcloud config unset project

# Remove environment file
rm -f /tmp/gke-env.sh

# Verify
kubectl config get-contexts
gcloud config list
```

**📸 Screenshot Checkpoint 50**: Local config cleaned

---

## 💰 COST ESTIMATION

### Monthly Cost Breakdown

| Resource           | Type          | Quantity | Monthly Cost    |
| ------------------ | ------------- | -------- | --------------- |
| GKE Cluster        | n1-standard-4 | 4 nodes  | ~$480           |
| Persistent Disk    | SSD           | 260GB    | ~$45            |
| Load Balancer      | HTTP(S)       | 1        | ~$18            |
| Container Registry | Storage       | 5GB      | ~$0.25          |
| Cloud Logging      | Data          | 50GB     | ~$2.50          |
| Cloud Monitoring   | -             | -        | Free tier       |
| **TOTAL**          |               |          | **~$545/month** |

### Cost Optimization Tips

1. **Use Preemptible VMs**: Save 60-80% on compute costs
2. **Right-size nodes**: Use n1-standard-2 for dev (halves cost)
3. **Enable autoscaling**: Scale to zero during off-hours
4. **Use regional disks**: Standard PD instead of SSD saves 50%
5. **Delete unused images**: Clean GCR regularly
6. **Use committed use**: 1-year commit saves 37%

---

## 📝 DEPLOYMENT CHECKLIST

### ✅ Pre-Deployment

- [ ] GCP project created
- [ ] Billing enabled
- [ ] APIs enabled
- [ ] Tools installed (gcloud, kubectl, docker)
- [ ] Environment variables set

### ✅ Cluster Setup

- [ ] GKE cluster created
- [ ] kubectl configured
- [ ] Namespace created
- [ ] Persistent volumes created
- [ ] ConfigMap applied

### ✅ Infrastructure Deployment

- [ ] Zookeeper deployed and running
- [ ] Kafka deployed and running
- [ ] Kafka topic created
- [ ] HDFS deployed and running
- [ ] HDFS base directory created
- [ ] Elasticsearch deployed and running

### ✅ Application Deployment

- [ ] Images built and pushed to GCR
- [ ] Kafka Producer deployed
- [ ] Producer crawling data
- [ ] Spark Streaming deployed
- [ ] Spark processing data
- [ ] Spark Alerts deployed (index `stock-alerts-1m`)
- [ ] HDFS Archiver CronJob created
- [ ] Spark Batch Features CronJob created

### ✅ Verification

- [ ] All pods running
- [ ] Data in Kafka
- [ ] Data in Elasticsearch
- [ ] Alerts in Elasticsearch (`stock-alerts-1m`)
- [ ] Data in HDFS
- [ ] Monitoring configured
- [ ] Ingress configured (if needed)
- [ ] HPA enabled

### ✅ Production Readiness

- [ ] Resource limits set
- [ ] Alerts configured
- [ ] Backup strategy defined
- [ ] Scaling tested
- [ ] Documentation complete
- [ ] Team trained

### ✅ Teardown

- [ ] Application deleted
- [ ] Data backed up (if needed)
- [ ] PVCs deleted
- [ ] Namespace deleted
- [ ] GKE cluster deleted
- [ ] GCR images deleted
- [ ] GCP project deleted (optional)
- [ ] No ongoing charges verified

---

## 🎯 NEXT STEPS

After successful GKE deployment:

1. **Set up CI/CD**:

   - GitHub Actions for automated builds
   - GitOps with ArgoCD or Flux
   - Automated testing in staging

2. **Enhance Monitoring**:

   - Custom Grafana dashboards
   - PagerDuty/Opsgenie integration
   - SLO/SLI tracking

3. **Implement Security**:

   - Network policies
   - Pod security policies
   - Secrets management (Secret Manager)
   - Workload Identity

4. **Optimize Costs**:

   - Preemptible nodes
   - Cluster autoscaling
   - Resource quotas
   - Committed use discounts

5. **Disaster Recovery**:
   - Regular HDFS backups
   - Kafka replication
   - Multi-region setup
   - Runbooks for incidents

---

## 📞 SUPPORT

### GKE Documentation

- https://cloud.google.com/kubernetes-engine/docs
- https://kubernetes.io/docs/home/

### Troubleshooting

- GKE Logs: `gcloud logging read`
- Cloud Console: https://console.cloud.google.com
- Support: https://cloud.google.com/support

### Community

- GKE GitHub: https://github.com/GoogleCloudPlatform/kubernetes-engine-samples
- Stack Overflow: Tag `google-kubernetes-engine`

---

**Last Updated**: January 13, 2024  
**Version**: 1.0  
**Environment**: Google Kubernetes Engine (GKE)  
**Region**: us-central1
