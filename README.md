# BigData Stock Analysis System

**Real-time Stock Market Data Pipeline - Production Ready**

## 🚀 Quick Start

See detailed step-by-step guides:

- **[Docker Deployment Guide](docs/DOCKER_DEPLOYMENT.md)** - Local testing with Docker Compose
- **[GKE Deployment Guide](docs/GKE_DEPLOYMENT.md)** - Production deployment on Google Kubernetes Engine

## 📁 Project Structure

```
big_data/
├── docs/                          # Complete deployment guides
│   ├── DOCKER_DEPLOYMENT.md       # Step-by-step Docker guide (30 steps)
│   └── GKE_DEPLOYMENT.md          # Step-by-step GKE guide (50 steps)
├── src/                           # Source code
│   ├── producers/
│   │   └── kafka_producer.py      # Real-time crawler (yfinance, 60s interval)
│   ├── consumers/
│   │   ├── kafka_consumer_spark_streaming.py    # Kafka -> Spark bridge (topic fan-out)
│   │   └── kafka_consumer_hdfs_archiver.py      # HDFS archiver (daily CronJob)
│   ├── streaming/
│   │   ├── spark_streaming_simple.py           # Metrics stream -> ES: stock-realtime-1m
│   │   └── spark_streaming_alert.py            # Alerts stream  -> ES: stock-alerts-1m
│   ├── batch_jobs/
│   │   └── run_all.py                          # Spark batch entrypoint (features)
│   └── utils/
│       ├── crawl_data.py          # Yahoo Finance API wrapper
│       ├── crawl_feed.py          # Historical backfill utility
│       └── standardization_local.py  # Schema definitions
├── config/
│   ├── docker-compose.yml         # Local deployment orchestration
│   ├── Dockerfile                 # Application image
│   └── Dockerfile.production      # Production-optimized image
├── deployment/
│   ├── k8s/                       # Kubernetes manifests (15 files)
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   ├── kafka-producer-crawl-deployment.yaml
│   │   ├── spark-streaming-consumer-deployment.yaml
│   │   ├── hdfs-archiver-cronjob.yaml
│   │   ├── kafka-statefulset.yaml
│   │   ├── hdfs-statefulset.yaml
│   │   ├── elasticsearch-statefulset.yaml
│   │   └── ... (infrastructure manifests)
│   └── scripts/
│       ├── build-and-push.sh      # Build & push to GCR
│       ├── create-cluster.sh      # Create GKE cluster
│       ├── deploy.sh              # Deploy to K8s
│       └── cleanup.sh             # Cleanup resources
└── requirements.txt               # Python dependencies
```

## 📊 Architecture

### Real-time Data Pipeline (Lambda Architecture)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HOT PATH (Real-time)                          │
│                                                                       │
│  yfinance API                                                         │
│      │                                                                │
│      ▼                                                                │
│  kafka_producer.py ──► Kafka Topic: stocks-realtime                  │
│  (60s interval)              │                                        │
│                              ├──► kafka_consumer_spark_streaming.py  │
│                              │    • bridge -> Kafka: stocks-realtime-spark │
│                              │                                        │
│                              ├──► spark_streaming_simple.py          │
│                              │    • metrics aggregation (1m)         │
│                              │    ▼                                   │
│                              │    Elasticsearch: stock-realtime-1m   │
│                              │                                        │
│                              ├──► spark_streaming_alert.py           │
│                              │    • alerts detection (1m)            │
│                              │    ▼                                   │
│                              │    Elasticsearch: stock-alerts-1m     │
│                              │                                        │
│                              └──► [Kafka Buffer: 7 days retention]   │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                        COLD PATH (Batch)                              │
│                                                                        │
│  kafka_consumer_hdfs_archiver.py                                      │
│  (CronJob: Daily 00:00 UTC)                                           │
│      • Reads last 24h from Kafka                                      │
│      • Deduplication                                                  │
│      ▼                                                                 │
│  HDFS: /stock-data/YYYY-MM-DD/TICKER.json                            │
│                                                                        │
│  crawl_feed.py (Backfill Utility)                                     │
│      • Historical data (bypasses Kafka)                               │
│      • Direct to HDFS                                                 │
│      • Command: --days 30 or --start/--end                           │
└───────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                        SERVING LAYER                                  │
│                                                                        │
│  Elasticsearch ◄─── Query real-time data (last hours/days)           │
│  HDFS          ◄─── Query historical data (months/years)             │
│  Kibana        ◄─── Visualization & dashboards                        │
└───────────────────────────────────────────────────────────────────────┘
```

### Key Features

- ✅ **Real-time Crawling**: yfinance API every 60 seconds (minute bars)
- ✅ **Hot Storage**: Elasticsearch for real-time queries (hours/days)
- ✅ **Cold Storage**: HDFS for long-term archival (months/years)
- ✅ **Kafka Buffer**: 7-day retention for replay and recovery
- ✅ **Deduplication**: Both consumers handle duplicates
- ✅ **Scalability**: Kubernetes-ready with HPA
- ✅ **Production Ready**: Comprehensive deployment guides

## 📦 Services

| Service       | Port | Purpose                 |
| ------------- | ---- | ----------------------- |
| Zookeeper     | 2181 | Kafka coordination      |
| Kafka         | 9092 | Message broker          |
| HDFS NameNode | 9870 | HDFS management UI      |
| HDFS DataNode | 9866 | HDFS data storage       |
| Elasticsearch | 9200 | Real-time data indexing |
| Kibana        | 5601 | Data visualization      |

## 🔧 Development

### Environment Variables

```bash
# Kafka Configuration
KAFKA_BROKER=kafka:9092
KAFKA_TOPIC=stocks-realtime
CRAWL_INTERVAL=60  # seconds

# Stock Tickers (comma-separated)
TICKERS=AAPL,NVDA,TSLA,MSFT,GOOGL

# HDFS Configuration
HDFS_HOST=hdfs-namenode
HDFS_PORT=9000
HDFS_BASE_PATH=/stock-data

# Elasticsearch Configuration
ELASTICSEARCH_HOST=elasticsearch
ELASTICSEARCH_PORT=9200
```

### Running Individual Components

```bash
# Run producer (real-time crawling)
docker run --rm --network bigdata_default \
  -e KAFKA_BROKER=kafka:9092 \
  -e TICKERS=AAPL,NVDA \
  bigdata-app:latest python -m src.producers.kafka_producer

# Run Kafka -> Spark bridge
docker run --rm --network bigdata_default \
  -e KAFKA_BROKER=kafka:9092 \
  -e INPUT_TOPIC=stocks-realtime \
  -e SPARK_TOPIC=stocks-realtime-spark \
  bigdata-app:latest python -m src.consumers.kafka_consumer_spark_streaming

# Run Spark Streaming metrics job
docker run --rm --network bigdata_default \
  -e KAFKA_BROKER=kafka:9092 \
  -e ELASTICSEARCH_HOST=elasticsearch \
  bigdata-app:latest \
  spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.3 \

  # Metrics stream (stock-realtime-1m)
  /app/src/streaming/spark_streaming_simple.py

# Run Spark Streaming alerts job
docker run --rm --network bigdata_default \
  -e KAFKA_BROKER=kafka:9092 \
  -e ELASTICSEARCH_HOST=elasticsearch \
  bigdata-app:latest \
  spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.3 \

  # Alerts stream (stock-alerts-1m)
  /app/src/streaming/spark_streaming_alert.py

# Run HDFS archiver manually
docker run --rm --network bigdata_default \
  -e KAFKA_BROKER=kafka:9092 \
  -e HDFS_HOST=hdfs-namenode \
  bigdata-app:latest python -m src.consumers.kafka_consumer_hdfs_archiver

# Backfill historical data
docker run --rm --network bigdata_default \
  -e HDFS_HOST=hdfs-namenode \
  bigdata-app:latest python -m src.utils.crawl_feed --days 30
```

## 📊 Data Schema

### Kafka Message Format (JSON)

```json
{
  "ticker": "AAPL",
  "company": "Apple Inc.",
  "time": "2024-01-13T10:05:00",
  "Open": 185.23,
  "High": 185.45,
  "Low": 185.1,
  "Close": 185.32,
  "Adj Close": 185.32,
  "Volume": 12345678
}
```

### Elasticsearch Indices

- **stock-realtime-1m**: 1-minute metrics aggregation
- **stock-alerts-1m**: 1-minute alerts stream

### HDFS Structure

```
/stock-data/
├── 2024-01-13/
│   ├── AAPL.json     # All AAPL records for the day
│   ├── NVDA.json     # All NVDA records for the day
│   └── TSLA.json     # All TSLA records for the day
├── 2024-01-14/
│   └── ...
└── 2024-01-15/
    └── ...
```

## 🚀 Deployment

### Docker (Local Testing)

Follow [docs/DOCKER_DEPLOYMENT.md](docs/DOCKER_DEPLOYMENT.md) for complete step-by-step guide.

Quick start:

```bash
# Build image
docker build -f config/Dockerfile -t bigdata-app:latest .

# Start infrastructure
docker-compose -f config/docker-compose.yml up -d zookeeper kafka hadoop-namenode hadoop-datanode elasticsearch kibana

# Start application
docker-compose -f config/docker-compose.yml up -d stock-producer spark-kafka-bridge spark-streaming-metrics spark-streaming-alerts
```

### Kubernetes (Production)

Follow [docs/GKE_DEPLOYMENT.md](docs/GKE_DEPLOYMENT.md) for complete GKE deployment.

Quick start:

```bash
# Create GKE cluster
gcloud container clusters create bigdata-cluster \
  --zone=us-central1-a \
  --num-nodes=4 \
  --machine-type=n1-standard-4

# Build and push to GCR
docker build -f config/Dockerfile -t gcr.io/PROJECT_ID/bigdata-app:latest .
docker push gcr.io/PROJECT_ID/bigdata-app:latest

# Deploy
kubectl apply -f deployment/k8s/namespace.yaml
kubectl apply -f deployment/k8s/configmap.yaml
kubectl apply -f deployment/k8s/
```

## 🧪 Testing

### Verify Data Flow

```bash
# 1. Check producer logs
kubectl logs -l app=kafka-producer -n bigdata --tail=50

# 2. Check Kafka messages
kubectl exec -it kafka-0 -n bigdata -- \
  kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 \
    --topic stocks-realtime \
    --max-messages 5

# 3. Check Elasticsearch data
curl http://localhost:9200/stock-realtime-1m/_count

# 4. Check HDFS data
kubectl exec -it hdfs-namenode-0 -n bigdata -- \
  hdfs dfs -ls /stock-data/$(date +%Y-%m-%d)
```

## 📈 Monitoring

### Metrics

- **Producer**: Records sent per minute, crawl latency
- **Spark Streaming**: Processing rate, checkpoint age
- **Elasticsearch**: Index size, query latency
- **HDFS**: Storage usage, replication status

### Logs

```bash
# Docker
docker-compose -f config/docker-compose.yml logs -f [service-name]

# Kubernetes
kubectl logs -f -l app=[app-name] -n bigdata
kubectl logs -f [pod-name] -n bigdata --tail=100
```

## 🛠️ Troubleshooting

Common issues and solutions are documented in:

- [docs/DOCKER_DEPLOYMENT.md#troubleshooting](docs/DOCKER_DEPLOYMENT.md#troubleshooting)
- [docs/GKE_DEPLOYMENT.md#troubleshooting](docs/GKE_DEPLOYMENT.md#troubleshooting)

## 📚 Resources

- **Apache Kafka**: https://kafka.apache.org/
- **Apache Spark**: https://spark.apache.org/
- **Apache HDFS**: https://hadoop.apache.org/
- **Elasticsearch**: https://www.elastic.co/
- **yfinance API**: https://pypi.org/project/yfinance/
- **GKE Documentation**: https://cloud.google.com/kubernetes-engine/docs

## 📝 License

This project is for educational and research purposes.

## 👥 Contributors

Big Data Stock Analysis Team

---

**Last Updated**: January 13, 2024  
**Version**: 2.0 (Real-time Crawling Architecture)

| Kafka | 9092 | Message broker |
| Zookeeper | 2181 | Kafka coordination |
| Elasticsearch | 9200 | Data storage & search |
| Kibana | 5601 | Visualization UI |
| HDFS NameNode | 9870 | Hadoop UI |
| HDFS DataNode | 9864 | Data storage |

## 🔍 Monitoring

```bash
# Check Elasticsearch indices
curl "http://localhost:9200/_cat/indices?v"

# Query real-time data
curl "http://localhost:9200/stock_realtime/_search?size=5&pretty"

# Query anomalies
curl "http://localhost:9200/stock_anomalies/_search?size=5&pretty"

# Check Spark logs
docker logs spark-streaming-simple
docker logs spark-anomaly-detection
```

## 📖 Documentation

- **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Docker Guide**: [docs/HUONG_DAN_SU_DUNG_DOCKER.md](docs/HUONG_DAN_SU_DUNG_DOCKER.md)
- **GKE Deployment**: [docs/GKE_DEPLOYMENT_GUIDE.md](docs/GKE_DEPLOYMENT_GUIDE.md)

## 🛠️ Technical Stack

- **Streaming**: Apache Kafka 7.9.1, Spark 3.4.3
- **Storage**: Hadoop HDFS 3.2.1, Elasticsearch 7.17.16
- **Visualization**: Kibana 7.17.16
- **Orchestration**: Docker Compose, Kubernetes
- **Language**: Python 3.12, PySpark

## 📝 License

Internal project - All rights reserved

---

**Version**: 2.0.0 | **Last Updated**: January 2026
