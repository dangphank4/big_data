# 📚 TÀI LIỆU KIẾN TRÚC HỆ THỐNG BIG DATA

## 🎯 TỔNG QUAN DỰ ÁN

### Mục tiêu

Xây dựng hệ thống phân tích dữ liệu chứng khoán real-time kết hợp batch processing, triển khai trên Google Kubernetes Engine (GKE).

### Công nghệ sử dụng

- **Stream Processing**: Apache Kafka, Spark Structured Streaming
- **Batch Processing**: Python, Pandas
- **Storage**: HDFS (Hadoop), Elasticsearch
- **Visualization**: Kibana
- **Orchestration**: Kubernetes (GKE)
- **Container**: Docker

---

## 🏗️ KIẾN TRÚC LAMBDA

### Lambda Architecture Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA SOURCES                                │
│                   (Stock Market APIs)                            │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ├──────────────────┬──────────────────┐
                   │                  │                  │
                   ▼                  ▼                  ▼
          ┌────────────────┐  ┌─────────────┐  ┌────────────────┐
          │  KAFKA PRODUCER│  │ HISTORY.JSON│  │  MARKET DATA   │
          │   (Real-time)  │  │   (Batch)   │  │   (External)   │
          └────────┬───────┘  └──────┬──────┘  └────────┬───────┘
                   │                 │                   │
                   ▼                 ▼                   ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                      LAMBDA ARCHITECTURE                      │
    │                                                               │
    │  ┌─────────────────────────────────────────────────────────┐│
    │  │              BATCH LAYER (Cold Path)                    ││
    │  │  • Purpose: Historical data processing                  ││
    │  │  • Frequency: Daily (2 AM)                              ││
    │  │  • Processing: Python batch jobs                        ││
    │  │                                                          ││
    │  │  Batch Jobs:                                            ││
    │  │  ├─ batch_trend.py        (MA50, MA100, MA200)         ││
    │  │  ├─ drawdown.py           (Max drawdown)               ││
    │  │  ├─ cumulative_return.py  (Returns)                    ││
    │  │  ├─ volume_features.py    (Volume analysis)            ││
    │  │  ├─ market_regime.py      (Market state)               ││
    │  │  └─ monthly.py            (Monthly metrics)            ││
    │  │                                                          ││
    │  │  Storage: HDFS + Elasticsearch                          ││
    │  └─────────────────────────────────────────────────────────┘│
    │                                                               │
    │  ┌─────────────────────────────────────────────────────────┐│
    │  │              SPEED LAYER (Hot Path)                     ││
    │  │  • Purpose: Real-time streaming                         ││
    │  │  • Latency: < 30 seconds                                ││
    │  │  • Processing: Spark Streaming                          ││
    │  │                                                          ││
    │  │  Pipeline:                                              ││
    │  │  Kafka → Spark Streaming → Elasticsearch               ││
    │  │    │                                                    ││
    │  │    └─→ HDFS (via Kafka Consumer)                       ││
    │  │                                                          ││
    │  │  Metrics:                                               ││
    │  │  ├─ Avg price (30s window)                             ││
    │  │  ├─ Min/Max price                                       ││
    │  │  ├─ Total volume                                        ││
    │  │  ├─ Trade count                                         ││
    │  │  └─ Price volatility                                    ││
    │  └─────────────────────────────────────────────────────────┘│
    │                                                               │
    │  ┌─────────────────────────────────────────────────────────┐│
    │  │              SERVING LAYER                              ││
    │  │  • Storage: Elasticsearch (indexing & query)            ││
    │  │  • Visualization: Kibana dashboards                     ││
    │  │  • Data Lake: HDFS (long-term storage)                  ││
    │  │  • Query: Unified view of batch + streaming            ││
    │  └─────────────────────────────────────────────────────────┘│
    └───────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │    END USERS          │
                    │  • Analysts           │
                    │  • Traders            │
                    │  • Data Scientists    │
                    └───────────────────────┘
```

### Tại sao Lambda Architecture?

#### 1. **Batch Layer** giải quyết:

- **Độ chính xác cao**: Xử lý toàn bộ historical data với logic phức tạp
- **Tính toán nặng**: Moving averages 200 ngày, cumulative returns
- **Reprocessing**: Có thể tính lại khi có bug hoặc thay đổi logic
- **Cost-effective**: Chạy 1 lần/ngày, tận dụng resources khi idle

#### 2. **Speed Layer** giải quyết:

- **Độ trễ thấp**: Cảnh báo real-time, live monitoring
- **Event-driven**: Xử lý từng message khi đến
- **Immediate insights**: Phát hiện anomalies ngay lập tức
- **High throughput**: Xử lý hàng nghìn messages/giây

#### 3. **Serving Layer** merge cả hai:

- Elasticsearch index cả batch views và streaming views
- Query API thống nhất
- Balance giữa accuracy (batch) và freshness (streaming)

---

## 📊 DATA FLOW CHI TIẾT

### 1. Real-time Flow (Speed Layer)

```
┌──────────────┐
│Stock API/Feed│
└──────┬───────┘
       │
       │ Simulated by kafka_producer.py
       │ Fields: ticker, company, time, Open, High, Low, Close, Volume
       ▼
┌──────────────────┐
│ Kafka Topic      │
│ stocks-history   │
│ Retention: 7 days│
└──────┬───────────┘
       │
       ├────────────────────────┬────────────────────────┐
       │                        │                        │
       ▼                        ▼                        ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│Spark Stream  │      │Kafka Consumer│      │Other Consumer│
│              │      │(HDFS Writer) │      │  (Future)    │
└──────┬───────┘      └──────┬───────┘      └──────────────┘
       │                     │
       │ Aggregate 30s       │ Write raw to HDFS
       │ window              │ Path: /user/kafka_data/
       │                     │       stocks_history/
       ▼                     │       YYYY/MM/DD/HH/*.jsonl
┌──────────────┐             │
│Elasticsearch │◄────────────┘
│Index:        │
│stock_realtime│
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    Kibana    │
│  Dashboard   │
└──────────────┘
```

### 2. Batch Flow (Batch Layer)

```
┌──────────────────┐
│  history.json    │ (Sample historical data)
└─────────┬────────┘
          │
          │ Loaded by run_all.py
          │ Via standardization_local.load_history()
          ▼
┌──────────────────────────────────────────────────────┐
│           Batch Processing Pipeline                   │
│                                                       │
│  1. batch_trend.py                                    │
│     → MA50, MA100, MA200                              │
│     → Trend classification (up/down/sideway)          │
│     → Trend strength                                  │
│                                                       │
│  2. drawdown.py                                       │
│     → Peak price tracking                             │
│     → Max drawdown calculation                        │
│                                                       │
│  3. cumulative_return.py                              │
│     → Returns from start                              │
│     → Cumulative growth                               │
│                                                       │
│  4. volume_features.py                                │
│     → Volume MA                                       │
│     → Volume ratio                                    │
│     → Volume spikes                                   │
│                                                       │
│  5. market_regime.py                                  │
│     → Bull/Bear/Neutral classification                │
│     → Based on trend + volatility                     │
│                                                       │
│  6. monthly.py                                        │
│     → Monthly returns                                 │
│     → Monthly volatility                              │
│                                                       │
└──────────────────┬───────────────────────────────────┘
                   │
                   ├─────────────────┬─────────────────┐
                   │                 │                 │
                   ▼                 ▼                 ▼
         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
         │     HDFS     │  │Elasticsearch │  │   Kibana     │
         │/tmp/serving/ │  │Index:        │  │ Dashboard    │
         │batch_        │  │batch_        │  │ (Long-term)  │
         │features.json │  │features      │  └──────────────┘
         └──────────────┘  └──────────────┘
```

### 3. Serving Layer Query

```
User Query → Kibana → Elasticsearch
                          │
                          ├─ Index: stock_realtime*
                          │  (Last 30 seconds - 1 hour)
                          │
                          └─ Index: batch_features*
                             (Historical analysis)
```

---

## 🔧 THÀNH PHẦN HỆ THỐNG

### Infrastructure Layer (Kubernetes)

```
Namespace: bigdata
│
├─ StatefulSets (Stateful workloads)
│  ├─ zookeeper (1 replica)
│  │  └─ PVC: zookeeper-pvc (10Gi)
│  ├─ kafka (1 replica)
│  │  └─ PVC: kafka-pvc (50Gi)
│  ├─ hadoop-namenode (1 replica)
│  │  └─ PVC: hdfs-namenode-pvc (50Gi)
│  ├─ hadoop-datanode (1 replica)
│  │  └─ PVC: hdfs-datanode-pvc (100Gi)
│  └─ elasticsearch (1 replica)
│     └─ PVC: elasticsearch-pvc (50Gi)
│
├─ Deployments (Stateless workloads)
│  ├─ kibana (1 replica, HPA-ready)
│  ├─ kafka-producer (1 replica, HPA-enabled)
│  ├─ kafka-consumer (1 replica, HPA-enabled)
│  └─ spark-streaming (1 replica)
│
├─ CronJobs (Scheduled jobs)
│  └─ batch-processing (Daily 2 AM)
│
├─ Services (ClusterIP, LoadBalancer)
│  ├─ zookeeper:2181
│  ├─ kafka:9092
│  ├─ hadoop-namenode:9000,9870
│  ├─ hadoop-datanode:9864
│  ├─ elasticsearch:9200,9300
│  └─ kibana:5601 (LoadBalancer)
│
├─ ConfigMaps
│  └─ bigdata-config (Environment variables)
│
├─ HorizontalPodAutoscalers
│  ├─ kafka-producer-hpa (CPU 70%, Mem 80%)
│  └─ kafka-consumer-hpa (CPU 70%, Mem 80%)
│
└─ NetworkPolicies
   ├─ kafka-network-policy
   └─ elasticsearch-network-policy
```

### Application Layer

#### 1. **kafka_producer.py**

```python
Role: Simulate real-time stock data
Features:
  - Reads from history.json
  - Generates price movements with volatility
  - Publishes to Kafka topic: stocks-history
  - Update interval: 30 seconds (configurable)
Schema: ticker, company, time, Open, High, Low, Close, Adj Close, Volume
```

#### 2. **kafka_consumer.py**

```python
Role: Persist streaming data to HDFS
Features:
  - Consumes from Kafka
  - Batching: 100 records or 60 seconds
  - Writes to HDFS: /user/kafka_data/stocks_history/YYYY/MM/DD/HH/data_*.jsonl
  - Fault-tolerant with retries
Consumer Group: hdfs-writer-group-v1
```

#### 3. **spark_streaming_simple.py**

```python
Role: Real-time aggregation and indexing
Features:
  - Reads from Kafka (stocks-history topic)
  - 30-second tumbling window aggregations
  - Computes: avg_price, min_price, max_price, total_volume, trade_count, volatility
  - Writes to Elasticsearch index: stock_realtime
  - Checkpoint: HDFS /user/spark_checkpoints/stock_realtime_v1
Watermark: 1 minute late data tolerance
```

#### 4. **Batch Jobs** (run_all.py orchestrator)

```python
batch_trend.py:
  - MA50, MA100, MA200
  - Trend classification

drawdown.py:
  - Peak tracking
  - Max drawdown

cumulative_return.py:
  - Cumulative returns

volume_features.py:
  - Volume analysis

market_regime.py:
  - Bull/Bear/Neutral

monthly.py:
  - Monthly aggregations

Output:
  - HDFS: /tmp/serving/batch_features.json
  - Elasticsearch: batch_features index
```

#### 5. **standardization_local.py**

```python
Role: Unified schema definitions
Features:
  - Schema constants (field names)
  - PySpark schema for streaming
  - Pandas schema for batch
  - Ensures consistency across batch/streaming
```

---

## 🚀 DEPLOYMENT WORKFLOW

### Pre-deployment

```bash
1. Build Docker image
   ./scripts/build-and-push.sh

2. Create GKE cluster
   ./scripts/create-cluster.sh bigdata-cluster asia-southeast1

3. Update PROJECT_ID in manifests
   sed -i 's/PROJECT_ID/your-project-id/g' k8s/*.yaml
```

### Deployment Order

```bash
1. Namespace & ConfigMap
   kubectl apply -f k8s/namespace.yaml
   kubectl apply -f k8s/configmap.yaml

2. Storage
   kubectl apply -f k8s/persistent-volumes.yaml

3. Stateful Services (in order)
   kubectl apply -f k8s/zookeeper-statefulset.yaml
   kubectl apply -f k8s/kafka-statefulset.yaml
   kubectl apply -f k8s/hdfs-statefulset.yaml
   kubectl apply -f k8s/elasticsearch-statefulset.yaml

4. Application Services
   kubectl apply -f k8s/kibana-deployment-updated.yaml
   kubectl apply -f k8s/kafka-producer-deployment.yaml
   kubectl apply -f k8s/kafka-consumer-deployment.yaml
   kubectl apply -f k8s/spark-streaming-deployment.yaml

5. Batch Jobs
   kubectl apply -f k8s/batch-job-cronjob.yaml

6. Autoscaling & Policies
   kubectl apply -f k8s/hpa.yaml
   kubectl apply -f k8s/network-policy.yaml
```

### Automated Deployment

```bash
./scripts/deploy.sh
```

---

## 📈 PERFORMANCE & SCALABILITY

### Current Capacity

- **Kafka**: ~10,000 messages/second
- **Spark Streaming**: 4 partitions, local[*] mode
- **Elasticsearch**: Single node, ~50GB storage
- **HDFS**: 100GB total (50GB NameNode + 100GB DataNode)

### Scaling Strategies

#### Horizontal Scaling

```bash
# Scale Kafka consumers
kubectl scale deployment kafka-consumer --replicas=3 -n bigdata

# Scale producers
kubectl scale deployment kafka-producer --replicas=2 -n bigdata
```

#### Vertical Scaling

```yaml
# Increase resources
resources:
  requests:
    memory: "4Gi"
    cpu: "2000m"
  limits:
    memory: "8Gi"
    cpu: "4000m"
```

#### Cluster Scaling

```bash
# Add more nodes
gcloud container clusters resize bigdata-cluster --num-nodes=5 --zone=asia-southeast1-a
```

#### Kafka Partitioning

```bash
# Increase partitions for parallelism
kubectl exec -it kafka-0 -n bigdata -- \
  kafka-topics --alter --topic stocks-history --partitions 4 --bootstrap-server localhost:9092
```

#### Elasticsearch Scaling

```bash
# Add more ES nodes
kubectl scale statefulset elasticsearch --replicas=3 -n bigdata
```

### Performance Tuning

#### Spark

```yaml
spark.sql.shuffle.partitions: 8 # Increase for more parallelism
spark.executor.memory: 4g
spark.driver.memory: 2g
spark.streaming.kafka.maxRatePerPartition: 1000
```

#### Kafka

```yaml
KAFKA_NUM_PARTITIONS: 4
KAFKA_LOG_SEGMENT_BYTES: 1073741824 # 1GB
KAFKA_LOG_RETENTION_HOURS: 168 # 7 days
```

#### Elasticsearch

```yaml
ES_JAVA_OPTS: "-Xms2g -Xmx2g" # Increase heap
indices.memory.index_buffer_size: 20%
```

---

## 🔐 SECURITY

### Network Policies

```yaml
# Kafka: Only accept from producer, consumer, spark
# Elasticsearch: Only accept from Kibana, Spark, batch jobs
# HDFS: Only accept from consumer, spark
```

### RBAC

```yaml
# Service accounts with minimal permissions
# Batch jobs: read ConfigMaps, write to ES/HDFS
# Apps: read Secrets, write to Kafka/ES
```

### Secrets Management

```bash
# Use Google Secret Manager
gcloud secrets create kafka-password --data-file=-
```

### Workload Identity

```bash
# GKE Workload Identity to access GCP services
# No need for service account keys
```

---

## 🔍 MONITORING

### Metrics to Track

#### Application Metrics

- Kafka: Messages/sec, consumer lag
- Spark: Processing time, records/sec
- Elasticsearch: Index rate, query latency
- HDFS: Disk usage, block health

#### Infrastructure Metrics

- CPU/Memory usage per pod
- Network I/O
- Disk I/O
- PVC usage

#### Business Metrics

- Number of tickers tracked
- Data freshness (batch vs streaming)
- Query response time

### Monitoring Stack

```
Google Cloud Monitoring (default)
+ Prometheus (optional)
+ Grafana (optional)
+ Kibana (built-in)
```

### Alerts

- Pod crashes
- High CPU/Memory
- Kafka consumer lag > 1000
- HDFS disk > 80%
- Elasticsearch cluster status != green

---

## 📚 REFERENCES

### Documentation

- [GKE Docs](https://cloud.google.com/kubernetes-engine/docs)
- [Kafka Docs](https://kafka.apache.org/documentation/)
- [Spark Streaming](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)
- [Elasticsearch](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)

### Best Practices

- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [Lambda Architecture](http://lambda-architecture.net/)
- [Data Engineering](https://www.databricks.com/glossary/lambda-architecture)

---

## 🎓 LEARNING PATH

### Beginner

1. Understand Kubernetes basics
2. Learn Docker containerization
3. Study Kafka fundamentals
4. Explore Pandas for data processing

### Intermediate

5. Master Spark Structured Streaming
6. Learn HDFS architecture
7. Elasticsearch indexing strategies
8. GKE cluster management

### Advanced

9. Lambda Architecture patterns
10. Stream processing optimizations
11. Production-grade monitoring
12. CI/CD for data pipelines

---

**Last Updated**: January 2026
**Version**: 1.0.0
**Maintainer**: Big Data Team
