# 🐳 DOCKER DEPLOYMENT GUIDE

**Complete step-by-step guide for deploying Big Data Stock Analysis System using Docker Compose**

---

## � FIX THIS FIRST - Docker Permission Error

**Nếu bạn thấy lỗi này:**

```
permission denied while trying to connect to the Docker daemon socket
```

**✅ Giải pháp (chọn 1 trong 2):**

### Option 1: Fix Permissions (RECOMMENDED - chỉ làm 1 lần)

```bash
# Add user vào docker group
sudo usermod -aG docker $USER

# Logout và login lại HOẶC chạy:
newgrp docker

# Kiểm tra:
docker ps
# Nếu không còn lỗi "permission denied" = OK!
```

### Option 2: Temporary Fix (mỗi lần phải thêm sudo)

```bash
# Thêm sudo vào mọi lệnh docker:
sudo docker build -f config/Dockerfile -t bigdata-app:latest .
sudo docker compose -f config/docker-compose.yml up -d
```

---

## 📋 TABLE OF CONTENTS

1. [Quick Start Summary](#-quick-start-summary) ⭐ **BẮT ĐẦU TỪ ĐÂY**
2. [Prerequisites](#-prerequisites)
3. [Environment Setup](#-environment-setup)
4. [Build Docker Images](#-build-docker-images)
5. [Deploy Infrastructure](#-deploy-infrastructure)
6. [Deploy Application Services](#-deploy-application-services)
7. [Verify Deployment](#-verify-deployment)
8. [Monitor System](#-monitor-system)
9. [Access Services](#-access-services)
10. [Testing Data Flow](#-testing-data-flow)
11. [Troubleshooting](#-troubleshooting)
12. [Cleanup & Teardown](#-cleanup--teardown)

---

## ⭐ QUICK START SUMMARY

**Chạy theo thứ tự này (sau khi fix Docker permissions ở trên):**

```bash
# 1. Fix Docker permissions (nếu chưa làm)
sudo usermod -aG docker $USER
newgrp docker

# 2. Cài Docker Compose v2 (nếu chưa có)
# Add Docker repository
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-compose-plugin docker-buildx-plugin

# 3. Navigate to project
cd /home/danz/Downloads/big_data

# 4. Build image
docker build -f config/Dockerfile -t bigdata-app:latest .

# 5. Start infrastructure (Kafka, HDFS, Elasticsearch)
docker compose -f config/docker-compose.yml up -d zookeeper
sleep 30
docker compose -f config/docker-compose.yml up -d kafka
sleep 60
docker compose -f config/docker-compose.yml up -d hadoop-namenode hadoop-datanode
sleep 45
docker compose -f config/docker-compose.yml up -d elasticsearch kibana
sleep 60

# 6. Start application services
docker compose -f config/docker-compose.yml up -d stock-producer
docker compose -f config/docker-compose.yml up -d spark-kafka-bridge
docker compose -f config/docker-compose.yml up -d spark-streaming-metrics spark-streaming-alerts

# 7. Check everything is running
docker compose -f config/docker-compose.yml ps

# 8. Wait 2-3 minutes, then check data
curl -X GET "http://localhost:9200/_cat/indices?v"
# Should see: stock-realtime-1m, stock-alerts-1m

# 9. Open Kibana
echo "Open browser: http://localhost:5601"
```

**Chi tiết từng bước ở các section phía dưới ↓**

---

## ✅ PREREQUISITES

### 1. Fix Docker Access (REQUIRED - làm trước tiên!)

```bash
# Test xem Docker có hoạt động không:
docker ps

# Nếu thấy "permission denied":
sudo usermod -aG docker $USER
newgrp docker
docker ps  # Test lại
```

### 2. Install Docker Compose v2 & Buildx

```bash
# Check hiện tại:
docker compose version
docker buildx version

# Nếu không có, cần add Docker repository trước:
# 1. Add Docker's GPG key
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# 2. Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 3. Install plugins
sudo apt-get update
sudo apt-get install -y docker-compose-plugin docker-buildx-plugin

# Verify:
docker compose version  # Should show v2.x.x
docker buildx version   # Should show buildx version
```

### 3. System Requirements Check

```bash
# Check Docker version
docker --version
# Expected: Docker version 20.10.x or higher

# Check available disk space (need at least 20GB)
df -h /var/lib/docker
```

### System Requirements

- **RAM**: Minimum 8GB (16GB recommended)
- **Disk**: Minimum 20GB free space
- **OS**: Linux/macOS/Windows with WSL2
- **Network**: Internet connection for pulling images and crawling data

---

## 🔧 ENVIRONMENT SETUP

### Step 1: Clone/Navigate to Project

```bash
cd /home/danz/Downloads/big_data

# Verify project structure
ls -la
# Should see: src/, deployment/, config/, requirements.txt, README.md
```

**📸 Screenshot Checkpoint 2**: Project directory structure

---

### Step 2: Review Environment Variables

```bash
# Check docker-compose configuration
cat config/docker-compose.yml | grep -A 20 "environment:"
```

**📸 Screenshot Checkpoint 3**: Environment variables displayed

---

### Step 3: Update Configuration (Optional)

Edit `config/docker-compose.yml` if needed:

```yaml
environment:
  # Kafka Configuration
  KAFKA_BROKER: "kafka:9092"
  KAFKA_TOPIC: "stocks-realtime"
  CRAWL_INTERVAL: "60" # seconds (1 minute)

  # Tickers to crawl (modify as needed)
  TICKERS: "AAPL,NVDA,TSLA,MSFT,GOOGL"

  # HDFS Configuration
  # NOTE:
  # - WebHDFS (HTTP) is on port 9870 (used by Python hdfs.InsecureClient)
  # - HDFS RPC is on port 9000 (used by Spark hdfs:// URIs)
  HDFS_HOST: "hadoop-namenode"
  HDFS_PORT: "9870"
  HDFS_BASE_PATH: "/stock-data"

  # Elasticsearch
  ELASTICSEARCH_HOST: "elasticsearch"
  ELASTICSEARCH_PORT: "9200"
```

---

## 🏗️ BUILD DOCKER IMAGES

### Step 4: Build Application Image

```bash
cd /home/danz/Downloads/big_data

# Build the main application image
docker build -f config/Dockerfile -t bigdata-app:latest .

# Nếu build thành công, bạn sẽ thấy:
# => exporting to image
# => naming to docker.io/library/bigdata-app:latest
```

**Nếu gặp lỗi:**

- `permission denied` → Quay lại [FIX THIS FIRST](#-fix-this-first---docker-permission-error)
- `docker: unknown command` → Install Compose v2: `sudo apt-get install -y docker-compose-plugin`

**Expected output:**

```
[+] Building 45.2s (12/12) FINISHED
 => [internal] load build definition
 => [internal] load .dockerignore
 => [internal] transferring context
 => CACHED [1/7] FROM docker.io/library/python:3.12-slim
 => [2/7] RUN apt-get update && apt-get install -y...
 ...
 => exporting to image
 => naming to docker.io/library/bigdata-app:latest
```

**📸 Screenshot Checkpoint 4**: Successful build output

---

### Step 5: Verify Image Created

```bash
# List Docker images
docker images | grep bigdata

# Check image size
docker images bigdata-app:latest --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
```

**📸 Screenshot Checkpoint 5**: Docker image listed

---

## 🚀 DEPLOY INFRASTRUCTURE

### One-command option (recommended)

This starts the full infrastructure stack (Kafka + HDFS + Elasticsearch + Kibana) in exactly one command.

```bash
docker compose -f config/docker-compose.yml up -d \
  zookeeper kafka \
  hadoop-namenode hadoop-datanode \
  elasticsearch kibana
```

Quick verification:

```bash
# Show container status
docker compose -f config/docker-compose.yml ps

# Kibana should respond once Elasticsearch is ready
curl -I http://localhost:5601
```

### One-command shutdown/cleanup

```bash
# Stop and remove containers + network (keeps named volumes: HDFS/Elasticsearch data)
docker compose -f config/docker-compose.yml down

# Full cleanup (also deletes named volumes: ALL persisted data will be lost)
docker compose -f config/docker-compose.yml down -v
```

Optional (aggressive) cleanup if your disk fills up:

```bash
# Removes unused images/build cache across Docker (global)
docker system prune -af
```

### Step 6: Start Zookeeper & Kafka

```bash
# Start Zookeeper first
docker compose -f config/docker-compose.yml up -d zookeeper

# Wait 30 seconds for Zookeeper to be ready
sleep 30

# Check Zookeeper logs
docker compose -f config/docker-compose.yml logs zookeeper | tail -20
```

**Expected output:**

```
zookeeper_1  | [2024-01-13 10:00:00,123] INFO binding to port 0.0.0.0/0.0.0.0:2181
zookeeper_1  | [2024-01-13 10:00:00,456] INFO Server environment:zookeeper.version=3.8.0
```

**📸 Screenshot Checkpoint 6**: Zookeeper running successfully

---

### Step 7: Start Kafka Broker

```bash
# Start Kafka
docker compose -f config/docker-compose.yml up -d kafka

# Wait 60 seconds for Kafka to be ready
sleep 60

# Check Kafka logs
docker compose -f config/docker-compose.yml logs kafka | tail -30
```

**Expected output:**

```
kafka_1  | [2024-01-13 10:01:00] INFO Kafka Server started
kafka_1  | [2024-01-13 10:01:01] INFO [KafkaServer id=1] started
```

**📸 Screenshot Checkpoint 7**: Kafka broker running

---

### Step 8: Verify Kafka Topic Creation

```bash
# List Kafka topics
docker exec -it kafka kafka-topics.sh \
  --list \
  --bootstrap-server localhost:9092
```

**Expected output:**

```
stocks-realtime
stocks-realtime-spark
```

**📸 Screenshot Checkpoint 8**: Kafka topic exists

---

### Step 9: Start HDFS

```bash
# Start HDFS namenode and datanode
docker compose -f config/docker-compose.yml up -d hadoop-namenode hadoop-datanode

# Wait 45 seconds
sleep 45

# Check HDFS status
docker exec -it hadoop-namenode hdfs dfsadmin -report
```

**Expected output:**

```
Live datanodes (1):
Name: 172.18.0.x:9866 (hdfs-datanode)
...
```

**📸 Screenshot Checkpoint 9**: HDFS cluster healthy

---

### Step 10: Start Elasticsearch

```bash
# Start Elasticsearch
docker compose -f config/docker-compose.yml up -d elasticsearch

# Wait 60 seconds
sleep 60

# Check Elasticsearch health
curl -X GET "http://localhost:9200/_cluster/health?pretty"
```

**Expected output:**

```json
{
  "cluster_name" : "docker-cluster",
  "status" : "yellow",
  "number_of_nodes" : 1,
  ...
}
```

**📸 Screenshot Checkpoint 10**: Elasticsearch running

---

### Step 11: Start Kibana (Optional)

```bash
# Start Kibana
docker compose -f config/docker-compose.yml up -d kibana

# Wait 30 seconds
sleep 30

# Check if Kibana is accessible
curl -I http://localhost:5601
```

**Expected output:**

```
HTTP/1.1 200 OK
```

**📸 Screenshot Checkpoint 11**: Kibana accessible

---

## 📡 DEPLOY APPLICATION SERVICES

### One-command option (recommended)

```bash
docker compose -f config/docker-compose.yml up -d \
  stock-producer \
  spark-kafka-bridge \
  spark-streaming-metrics \
  spark-streaming-alerts \
  hdfs-archiver
```

**Note**: Lệnh này sẽ build images nếu chưa có và start tất cả application services cùng lúc.

**Expected build time**:

- Lần đầu: ~3-5 phút (build Spark image với dependencies)
- Lần sau: ~10 giây (dùng cached image)

**Verify deployment**:

```bash
# Check all containers are running
docker compose -f config/docker-compose.yml ps

# Check Spark Streaming logs (should see "Streaming query started")
docker compose -f config/docker-compose.yml logs --tail=30 spark-streaming-metrics
docker compose -f config/docker-compose.yml logs --tail=30 spark-streaming-alerts

# Check producer is crawling
docker compose -f config/docker-compose.yml logs --tail=20 stock-producer
```

### Alternative: Deploy từng service một (Step by Step)

Nếu muốn monitor từng service khi start:

### Step 12: Start Kafka Producer (Real-time Crawling)

```bash
# Start the producer
docker compose -f config/docker-compose.yml up -d stock-producer

# Watch producer logs (Ctrl+C to exit)
docker compose -f config/docker-compose.yml logs -f stock-producer
```

**Expected output:**

```
stock-producer  | [START] Real-time crawling for 5 tickers every 60s
stock-producer  | [CRAWL] AAPL
stock-producer  | [CRAWL] NVDA
stock-producer  | [BATCH 1] 2024-01-13T10:05:00 | 5 records | 3.45s
```

**📸 Screenshot Checkpoint 12**: Producer crawling successfully

---

### Step 12B (Recommended): Start Kafka -> HDFS Archiver (near-real-time archive)

Service này sẽ đọc từ `stocks-realtime` và ghi NDJSON vào HDFS theo cấu trúc `/stock-data/YYYY-MM-DD/TICKER.json`.

```bash
docker compose -f config/docker-compose.yml up -d hdfs-archiver

# Check archiver logs
docker compose -f config/docker-compose.yml logs --tail=50 hdfs-archiver
```

---

### Step 13: Verify Data in Kafka

```bash
# Consume messages from Kafka (Ctrl+C after seeing data)
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic stocks-realtime \
  --from-beginning \
  --max-messages 5
```

**Expected output:**

```json
{"ticker":"AAPL","company":"Apple Inc.","time":"2024-01-13T10:05:00","Open":185.23,"High":185.45,"Low":185.10,"Close":185.32,"Adj Close":185.32,"Volume":12345678}
...
```

**📸 Screenshot Checkpoint 13**: Kafka messages visible

---

### Step 14: Start Kafka Bridge + Spark Streaming

```bash

# Start Kafka -> Spark bridge
docker compose -f config/docker-compose.yml up -d spark-kafka-bridge

# Start Spark Streaming jobs
docker compose -f config/docker-compose.yml up -d spark-streaming-metrics spark-streaming-alerts

# Wait 90 seconds for Spark to initialize
sleep 90

# Check Spark logs
docker compose -f config/docker-compose.yml logs spark-streaming-metrics | tail -50
docker compose -f config/docker-compose.yml logs spark-streaming-alerts | tail -50
```

**Expected output:**

```
spark-streaming-metrics  | [INFO] Kafka: kafka:9092, Topic: stocks-realtime-spark
spark-streaming-alerts   | [READY] Alerts streaming started -> ES index: stock-alerts-1m
```

**📸 Screenshot Checkpoint 14**: Spark Streaming processing data

---

## ✔️ VERIFY DEPLOYMENT

### Step 15: Check All Running Containers

```bash
# List all running containers
docker compose -f config/docker-compose.yml ps

```

**Expected output:**

```
         Name                        State     Ports
-----------------------------------------------------------
zookeeper               Up      2181/tcp
kafka                   Up      9092/tcp
hadoop-namenode         Up      9870/tcp
hadoop-datanode         Up      9864/tcp
elasticsearch           Up      9200/tcp, 9300/tcp
kibana                  Up      5601/tcp
stock-producer          Up
hdfs-archiver            Up
spark-kafka-bridge      Up
spark-streaming-metrics Up
spark-streaming-alerts  Up
```

**📸 Screenshot Checkpoint 15**: All services running

---

### Step 16: Check Elasticsearch Indices

```bash
# List Elasticsearch indices
curl -X GET "http://localhost:9200/_cat/indices?v"
```

**Expected output:**

```
health status index                uuid   pri rep docs.count docs.deleted store.size
yellow open   stock-realtime-1m    xyz123   1   1         45            0      12.5kb
yellow open   stock-alerts-1m      abc456   1   1         12            0       8.2kb
```

**📸 Screenshot Checkpoint 16**: Elasticsearch indices created

---

### Step 17: Query Real-time Data

```bash
# Query 1-minute aggregations
curl -X GET "http://localhost:9200/stock-realtime-1m/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 5,
    "sort": [{"window_start": {"order": "desc"}}]
  }'
```

**Expected output:**

```json
{
  "hits": {
    "total": { "value": 45 },
    "hits": [
      {
        "_source": {
          "ticker": "AAPL",
          "window_start": "2024-01-13T10:05:00",
          "high_1m": 185.45,
          "low_1m": 185.1,
          "close_avg_1m": 185.32
        }
      }
    ]
  }
}
```

**📸 Screenshot Checkpoint 17**: Real-time data in Elasticsearch

---

## 📊 MONITOR SYSTEM

### Step 18: Monitor Resource Usage

```bash
# Check Docker stats
docker stats --no-stream
```

**Expected output:**

```
CONTAINER           CPU %     MEM USAGE / LIMIT     MEM %
stock-producer      2.5%      512MiB / 1GiB        50%
spark-streaming-metrics  15.3%     2.1GiB / 4GiB        52.5%
elasticsearch       8.2%      1.5GiB / 2GiB        75%
kafka               5.1%      1GiB / 2GiB          50%
```

**📸 Screenshot Checkpoint 18**: Resource usage

---

### Step 19: Check Disk Usage

```bash
# Check HDFS usage
docker exec -it hadoop-namenode hdfs dfs -df -h
docker exec -it hadoop-namenode hdfs dfs -ls /stock-data
```

**Expected output:**

```
Filesystem                Size    Used   Available  Use%
hdfs://namenode:9000     50.0G   1.2G      48.8G    2%

Found 1 items
drwxr-xr-x   - root supergroup          0 2024-01-13 10:00 /stock-data/2024-01-13
```

**📸 Screenshot Checkpoint 19**: HDFS data directory

---

## 🌐 ACCESS SERVICES

### Step 20: Access Web UIs

Open these URLs in your browser:

1. **Kibana Dashboard**: http://localhost:5601
2. **Elasticsearch**: http://localhost:9200
3. **HDFS NameNode UI**: http://localhost:9870

**📸 Screenshot Checkpoint 20**:

- Kibana main page
- HDFS web UI showing cluster overview

---

### Step 21: Configure Kibana Index Pattern

1. Open Kibana: http://localhost:5601
2. Go to **Management** → **Stack Management** → **Index Patterns**
3. Click **Create index pattern**
4. Enter pattern: `stock-realtime-*`
5. Select time field: `window_start`
6. Click **Create**

**📸 Screenshot Checkpoint 21**: Kibana index pattern created

---

### Step 22: Create Kibana Visualization

1. Go to **Discover** tab
2. Select `stock-realtime-*` index
3. View real-time data streaming in

**📸 Screenshot Checkpoint 22**: Kibana showing real-time stock data

---

## 🧪 TESTING DATA FLOW

### Step 23: Test End-to-End Data Flow

```bash
# 1. Check producer is sending data
docker compose -f config/docker-compose.yml logs --tail=20 stock-producer

# 2. Verify Kafka has messages
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic stocks-realtime \
  --max-messages 2

# 3. Check Spark is processing
docker compose -f config/docker-compose.yml logs --tail=30 spark-streaming-metrics
docker compose -f config/docker-compose.yml logs --tail=30 spark-streaming-alerts

# 4. Verify data in Elasticsearch
curl -X GET "http://localhost:9200/stock-realtime-1m/_count"
```

**📸 Screenshot Checkpoint 23**: Complete data flow verified

---


---

### Step 24: Feed Dữ Liệu Lịch Sử vào HDFS (Phục vụ Batch Features)

**🎯 Mục đích**: Batch job cần dữ liệu lịch sử từ HDFS để tính toán features (MA, trend, volatility, drawdown, etc.). Archiver từ Kafka chỉ lưu dữ liệu realtime, vì vậy cần backfill dữ liệu lịch sử từ Yahoo Finance.

**Yêu cầu**: `hadoop-namenode` và `hadoop-datanode` đang chạy và healthy.

#### Option 1: Backfill dữ liệu 1 năm (RECOMMENDED)

```bash
# Crawl dữ liệu daily năm 2024 cho 3 mã chính
docker compose -f config/docker-compose.yml run --rm hdfs-archiver \
  python /app/src/utils/crawl_feed.py \
  --tickers AAPL,NVDA,TSLA \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --interval 1d
```

**Expected output:**

```
======================================================================
BACKFILL TASK
  Tickers: AAPL, NVDA, TSLA
  Date Range: 2024-01-01 to 2024-12-31
======================================================================

[CRAWL] AAPL
  ✓ /stock-data/2024-01-02/AAPL.json | +1 records (1 total)
  ✓ /stock-data/2024-01-03/AAPL.json | +1 records (1 total)
  ...
  ✓ /stock-data/2024-12-30/AAPL.json | +1 records (1 total)

[CRAWL] NVDA
  ✓ /stock-data/2024-01-02/NVDA.json | +1 records (1 total)
  ...

[CRAWL] TSLA
  ✓ /stock-data/2024-01-02/TSLA.json | +1 records (1 total)
  ...

======================================================================
BACKFILL COMPLETE
  Files Written: 753
  Files Skipped: 0 (no new data)
  Total New Records: 753
======================================================================
```

#### Option 2: Backfill nhiều năm (cho phân tích dài hạn)

```bash
# Crawl dữ liệu 5 năm (sẽ mất ~5-10 phút)
docker compose -f config/docker-compose.yml run --rm hdfs-archiver \
  python /app/src/utils/crawl_feed.py \
  --tickers AAPL,NVDA,TSLA,MSFT,GOOGL \
  --days 1825 \
  --interval 1d
```

#### Option 3: Backfill chọn khoảng thời gian cụ thể

```bash
# Crawl dữ liệu từ tháng 1 đến tháng 6 năm 2024
docker compose -f config/docker-compose.yml run --rm hdfs-archiver \
  python /app/src/utils/crawl_feed.py \
  --tickers AAPL,NVDA \
  --start 2024-01-01 \
  --end 2024-06-30 \
  --interval 1d
```

**💡 Gợi ý quan trọng**:

- **Daily interval (`--interval 1d`)**: Recommended cho backfill dài hạn. Yahoo Finance hỗ trợ dữ liệu daily cho nhiều năm.
- **Minute interval (`--interval 1m`)**: Chỉ có dữ liệu ~30 ngày gần đây từ Yahoo Finance.
- **Deduplication**: Script tự động deduplicate nên có thể chạy nhiều lần an toàn.

#### Verify dữ liệu đã được crawl

```bash
# Kiểm tra số ngày có dữ liệu
docker exec -it hadoop-namenode hdfs dfs -ls /stock-data | wc -l

# Xem chi tiết các ngày
docker exec -it hadoop-namenode hdfs dfs -ls /stock-data | tail -20

# Xem nội dung file mẫu
docker exec -it hadoop-namenode hdfs dfs -cat /stock-data/2024-01-02/AAPL.json
```

**Expected output:**

```json
{"ticker":"AAPL","company":"Apple Inc.","time":"2024-01-02T00:00:00","Open":187.15,"High":188.44,"Low":183.89,"Close":185.64,"Adj Close":184.58,"Volume":82488300}
```

**📸 Screenshot Checkpoint 24a**: Dữ liệu lịch sử đã được crawl vào HDFS

---

### Step 24b: Chạy Batch Features Job

Sau khi đã có dữ liệu trong HDFS, chạy batch job để tính toán features:

```bash
# Run batch features computation
docker compose -f config/docker-compose.yml run --rm spark-batch-features
```

**Expected output:**

```
=== [1] ĐANG LẬP KẾ HOẠCH ĐỌC DỮ LIỆU ===
=== [2] XÂY DỰNG CHUỖI TÍNH TOÁN (TRANSFORMATIONS) ===
=== [3] THỰC THI VÀ ĐẨY DỮ LIỆU (ACTIONS) ===
DONE: Đã lưu kết quả phân tán vào HDFS: hdfs://hadoop-namenode:9000/tmp/serving/batch_features
Đang đẩy dữ liệu lên Elasticsearch (Serving Layer)...
DONE: Đã đẩy dữ liệu lên Elasticsearch index: batch-features.
```

#### Verify batch features trong Elasticsearch

```bash
# Kiểm tra số lượng documents
curl -s "http://localhost:9200/batch-features/_count?pretty"

# Xem sample document
curl -s "http://localhost:9200/batch-features/_search?size=1&pretty"
```

**Expected output:**

```json
{
  "count": 501,
  ...
}
```

Sample document sẽ có các features:

- **Moving Averages**: ma50, ma100, ma200
- **Trend Analysis**: trend, trend_strength
- **Returns**: daily_return, cumulative_return, return_30d, return_90d
- **Risk Metrics**: drawdown, max_drawdown
- **Volume Features**: volume_ma20, volume_ratio
- **Volatility**: monthly_volatility
- **Market Regime**: market_regime (normal/high_vol)

#### Tạo Kibana Index Pattern cho Batch Features

1. Mở Kibana: http://localhost:5601
2. Go to **Stack Management** → **Index Patterns**
3. Click **Create index pattern**
4. Enter: `batch-features*`
5. Select time field: `time`
6. Click **Create index pattern**
7. Go to **Discover** để xem dữ liệu batch features

**📸 Screenshot Checkpoint 24b**: Batch features trong Kibana

**⚠️ Lưu ý**: Batch job cần ít nhất 20-30 records mỗi ticker để tính toán đầy đủ các features (MA200 cần 200 data points). Với ít hơn, một số features sẽ có giá trị null và bị dropna() loại bỏ.

---

### Step 25: (Optional) Schedule Batch Features CronJob

Nếu muốn batch features tự động chạy định kỳ (vd: mỗi ngày 1 lần), start batch cronjob:

```bash
docker compose -f config/docker-compose.yml up -d spark-batch-features-cron
```

Default schedule trong `docker-compose.yml` là:

```yaml
# Mỗi ngày lúc 2 giờ sáng
CRON_SCHEDULE: "0 2 * * *"
```

Verify cronjob đang chạy:

```bash
docker ps | grep batch-features-cron
```

Xem logs của cronjob:

```bash
docker logs -f spark-batch-features-cron
```

**💡 Lưu ý**: Cronjob chỉ có ích khi HDFS liên tục có dữ liệu mới (từ archiver hoặc crawl feed định kỳ). Nếu không, batch job sẽ chỉ process lại dữ liệu cũ.

**📸 Screenshot Checkpoint 25**: Batch features cronjob running

---

### Step 26: Test HDFS Archiver (Manual Run)

```bash
# Run HDFS archiver manually (takes recent Kafka data and writes to HDFS)
docker compose -f config/docker-compose.yml run --rm \
  -e KAFKA_BROKER=kafka:9092 \
  -e KAFKA_TOPIC=stocks-realtime \
  -e HDFS_HOST=hadoop-namenode \
  -e HDFS_PORT=9870 \
  -e LOOKBACK_HOURS=1 \
  python-worker \
  python -m src.consumers.kafka_consumer_hdfs_archiver
```

**Expected output:**

```
[START] Archiving data from 2024-01-13 09:00:00 to 2024-01-13 10:00:00
[CONSUME] Reading from Kafka...
  Read 120 messages...
[DONE] Read 120 messages from Kafka
[HDFS] Writing 1 dates to HDFS...
  ✓ /stock-data/2024-01-13/AAPL.json | +24 records
[COMPLETE] Wrote 5 files, 120 new records to HDFS
```

**📸 Screenshot Checkpoint 24**: HDFS archiver completed successfully

---

### Step 27: Verify HDFS Data

```bash
# List HDFS files
docker exec -it hadoop-namenode hdfs dfs -ls -R /stock-data

# Check file content
docker exec -it hadoop-namenode hdfs dfs -cat /stock-data/2024-01-13/AAPL.json | head -5
```

**Expected output:**

```
drwxr-xr-x   - root supergroup          0 2024-01-13 10:00 /stock-data/2024-01-13
-rw-r--r--   1 root supergroup       2456 2024-01-13 10:00 /stock-data/2024-01-13/AAPL.json
-rw-r--r--   1 root supergroup       2391 2024-01-13 10:00 /stock-data/2024-01-13/NVDA.json
```

**📸 Screenshot Checkpoint 25**: HDFS files created

---

## 🔧 TROUBLESHOOTING

### Common Issues & Solutions

#### Issue 1: Kafka Not Starting

```bash
# Check Zookeeper is running
docker compose -f config/docker-compose.yml logs zookeeper | grep -i error

# Restart Kafka
docker compose -f config/docker-compose.yml restart kafka

# Wait and check
sleep 30
docker compose -f config/docker-compose.yml logs kafka | tail -20
```

---

#### Issue 2: Producer Not Sending Data

```bash
# Check producer logs for errors
docker compose -f config/docker-compose.yml logs stock-producer | grep -i error

# Verify network connectivity
docker exec -it stock-producer nc -zv kafka 9092

# Restart producer
docker compose -f config/docker-compose.yml restart stock-producer
```

---

#### Issue 3: Elasticsearch Yellow Status

```bash
# This is normal for single-node cluster
# Check cluster health
curl -X GET "http://localhost:9200/_cluster/health?pretty"

# Reduce replica count (optional)
curl -X PUT "http://localhost:9200/_settings" \
  -H 'Content-Type: application/json' \
  -d '{"index": {"number_of_replicas": 0}}'
```

---

#### Issue 4: Spark Streaming Errors

```bash
# Check Spark logs
docker compose -f config/docker-compose.yml logs spark-streaming-metrics | grep -i error
docker compose -f config/docker-compose.yml logs spark-streaming-alerts | grep -i error

# Check checkpoint directories
docker exec -it spark-streaming-metrics ls -la /tmp/spark-checkpoints || true
docker exec -it spark-streaming-alerts ls -la /tmp/spark-checkpoints || true

# If a checkpoint gets corrupted, remove it and restart the affected service
docker compose -f config/docker-compose.yml stop spark-streaming-metrics
docker exec -it spark-streaming-metrics rm -rf /tmp/spark-checkpoints
docker compose -f config/docker-compose.yml start spark-streaming-metrics
```

---

#### Issue 5: HDFS SafeMode

```bash
# Check HDFS status
docker exec -it hadoop-namenode hdfs dfsadmin -safemode get

# If in safe mode, leave it
docker exec -it hadoop-namenode hdfs dfsadmin -safemode leave

# Verify
docker exec -it hadoop-namenode hdfs dfsadmin -report
```

---

## 🗑️ CLEANUP & TEARDOWN

### Step 28: View Current Resources

```bash
# List all containers
docker compose -f config/docker-compose.yml ps

# List volumes
docker volume ls | grep big_data

# Check disk usage
docker system df
```

**📸 Screenshot Checkpoint 26**: Resources before cleanup

---

### Step 29: Stop All Services

```bash
# Stop all containers (keeps data)
docker compose -f config/docker-compose.yml stop

# Verify all stopped
docker compose -f config/docker-compose.yml ps
```

**Expected output:**

```
         Name                        State
-------------------------------------------
big_data_zookeeper_1         Exit 0
big_data_kafka_1             Exit 0

...
```

**📸 Screenshot Checkpoint 27**: All services stopped

---

### Step 30: Remove Containers (Keep Data)

```bash
# Remove containers but keep volumes
docker compose -f config/docker-compose.yml down

# Verify containers removed
docker ps -a | grep big_data
```

**📸 Screenshot Checkpoint 28**: Containers removed

---

### Step 31: Complete Cleanup (Remove All Data)

```bash
# ⚠️ WARNING: This will DELETE ALL DATA!

# Remove containers and volumes
docker compose -f config/docker-compose.yml down -v

# Remove images (optional)
docker rmi bigdata-app:latest

# Clean up unused resources
docker system prune -a --volumes -f

# Verify cleanup
docker ps -a
docker volume ls
docker images
```

**Expected output:**

```
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
(empty)

VOLUME NAME
(empty)
```

**📸 Screenshot Checkpoint 29**: Complete cleanup done

---

### Step 32: Verify Disk Space Reclaimed

```bash
# Check disk usage after cleanup
df -h /var/lib/docker

# Check Docker system info
docker system df
```

**📸 Screenshot Checkpoint 30**: Disk space reclaimed

---

## 📝 DEPLOYMENT SUMMARY

### ✅ Completed Steps Checklist

- [ ] Prerequisites verified
- [ ] Environment configured
- [ ] Docker images built
- [ ] Zookeeper deployed
- [ ] Kafka deployed
- [ ] HDFS deployed
- [ ] Elasticsearch deployed
- [ ] Kibana deployed
- [ ] Kafka Producer running
- [ ] Spark Streaming running
- [ ] Spark Alerts (1m) running
- [ ] Spark Batch (features) executed
- [ ] Data flow verified
- [ ] Elasticsearch indices created
- [ ] Kibana configured
- [ ] HDFS archiver tested
- [ ] All services monitored
- [ ] Screenshots captured at each checkpoint
- [ ] System tested end-to-end
- [ ] Cleanup performed

---

## 🎯 Next Steps

After successful deployment:

1. **Configure Alerts**:

- Infra alerts: pod/container restarts, lag, disk full
- Data alerts: Elasticsearch index `stock-alerts-1m` receiving documents

2. **Optimize Resources**: Adjust memory/CPU based on load
3. **Schedule HDFS Archiver**: Add cron job for daily runs
4. **Schedule Spark Batch**: Run `src/batch_jobs/run_all.py` daily to build batch features and index `batch-features`
5. **Backup HDFS**: Implement backup strategy
6. **Scale Up**: Add more Kafka/Spark containers if needed

---

## 📞 Support

If you encounter issues:

1. Check logs: `docker compose -f config/docker-compose.yml logs [service-name]`
2. Review this guide's troubleshooting section
3. Check container health: `docker ps`
4. Verify network: `docker network ls` then `docker network inspect <project>_bigdata-network`

---

**Last Updated**: January 13, 2026  
**Version**: 1.0  
**Environment**: Docker Compose
