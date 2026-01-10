# HƯỚNG DẪN SỬ DỤNG - BIG DATA PIPELINE THỐNG NHẤT

**Real-time Stock Data Processing: Batch + Streaming Pipeline**

---

## 📋 TỔNG QUAN HỆ THỐNG

### Kiến trúc tổng quan

```
┌─────────────────┐
│  history.json   │ (Dữ liệu lịch sử)
└────────┬────────┘
         │
         v
┌─────────────────────────────────────────────────────────────┐
│                    KAFKA PRODUCER                             │
│  - Đọc history.json làm baseline                             │
│  - Sử dụng price_simulator.py để mô phỏng giá realtime      │
│  - Simulate realtime prices với volatility động              │
│  - Gửi vào topic: stocks-history                             │
│  - Schema thống nhất: ticker, company, time, OHLCV           │
└──────────────┬──────────────────────────────────────────────┘
               │
               v
       ┌───────────────┐
       │  KAFKA BROKER │
       │ stocks-history│
       └───┬───────┬───┘
           │       │
    ┌──────┘       └──────┐
    │                     │
    v                     v
┌──────────┐      ┌────────────────┐
│  HDFS    │      │ SPARK STREAMING│
│ Consumer │      │   (realtime)   │
│  (raw)   │      └───────┬────────┘
└──────────┘              │
                          v
                  ┌──────────────┐
                  │Elasticsearch │
                  │stock_realtime│
                  └──────┬───────┘
                         │
                         v
                   ┌──────────┐
                   │  KIBANA  │
                   │ Dashboard│
                   └──────────┘

┌──────────────────────────────────────┐
│   BATCH PROCESSING (python-worker)   │
│ - Đọc history.json                   │
│ - Tính batch features:               │
│   + Trend (MA50, MA100, MA200)       │
│   + Cumulative Return                │
│   + Drawdown                         │
│   + Volume Features                  │
│   + Monthly Volatility               │
│   + Market Regime                    │
│ - Ghi HDFS: /serving/batch_features  │
│ - Ghi ES: batch-features index       │
└──────────────────────────────────────┘
```

### Luồng dữ liệu thống nhất

**1. SCHEMA CHUNG (Tất cả services sử dụng)**

```json
{
  "ticker": "AAPL",
  "company": "Apple Inc.",
  "time": "2025-01-05T10:30:00Z",
  "Open": 280.5,
  "High": 282.1,
  "Low": 278.2,
  "Close": 281.0,
  "Adj Close": 281.0,
  "Volume": 45000000
}
```

**2. KAFKA TOPIC**: `stocks-history` (topic duy nhất cho cả batch và streaming)

**3. ELASTICSEARCH INDEXES**:

- `stock_realtime`: Streaming metrics (30s windows)
- `batch-features`: Batch engineered features

---

## 🚀 KHỞI ĐỘNG HỆ THỐNG

## 🚀 KHỞI ĐỘNG HỆ THỐNG

### Bước 1: Start tất cả services

```bash
cd d:\HUST\2025_1\BIGDATA\big_data
docker compose up -d
```

**Chờ 30 giây** để các services khởi động hoàn tất.

### Bước 2: Kiểm tra services đang chạy

```bash
docker compose ps
```

Phải thấy các containers:

- ✅ `zookeeper`
- ✅ `kafka`
- ✅ `hadoop-namenode`, `hadoop-datanode`
- ✅ `elasticsearch`
- ✅ `kibana`
- ✅ `python-worker`
- ✅ `spark-streaming-simple`

### Bước 3: Start Kafka Producer (gửi dữ liệu realtime)

```bash
docker exec python-worker bash -c "cd /app && nohup python kafka_producer.py > /tmp/producer.log 2>&1 &"
```

Kiểm tra Producer đang chạy:

```bash
docker exec python-worker tail -20 /tmp/producer.log
```

Phải thấy:

```
[READY] 2025-01-05 10:30:00: Starting data stream...
[BATCH 1] 2025-01-05T10:30:00Z: Sent 2 messages
[BATCH 2] 2025-01-05T10:30:30Z: Sent 2 messages
```

### Bước 4: Kiểm tra Spark Streaming đang chạy

```bash
docker logs spark-streaming-simple --tail 30
```

Phải thấy:

```
[INFO] Starting Spark Streaming Job
[INFO] Kafka: kafka:9092, Topic: stocks-history
[INFO] Elasticsearch: elasticsearch:9200, Index: stock_realtime
[INFO] Streaming query started. Writing to stock_realtime
```

### Bước 5: Chờ dữ liệu được ghi vào Elasticsearch (2-3 phút)

```bash
sleep 120
curl -s "http://localhost:9200/_cat/indices?v" | grep stock
```

Phải thấy:

```
yellow open stock_realtime ... docs.count > 0
```

---

## 🔄 CHẠY BATCH PROCESSING

### Chạy 1 lần (manual)

```bash
docker exec python-worker python /app/unified_runner.py batch
```

Output:

```
============================================================
STARTING BATCH PROCESSING
============================================================
BAT ĐẦU ĐẨY DỮ LIỆU LÊN HDFS...
DONE: Đã lưu vào HDFS tại /serving/batch_features.json
BAT ĐẦU ĐẨY DỮ LIỆU LÊN ELASTICSEARCH...
Indexed XXX documents into batch-features
DONE! HỆ THỐNG ĐÃ CẬP NHẬT CẢ HDFS VÀ ELASTICSEARCH.
✓ Batch processing completed in XX.XXs
```

### Chạy định kỳ (daemon mode)

```bash
# Chạy batch mỗi 24h + monitor system health mỗi 30 phút
docker exec -d python-worker python /app/unified_runner.py

# Hoặc chỉ monitor (không chạy batch)
docker exec -d python-worker bash -c "RUN_MODE=monitor python /app/unified_runner.py"

# Hoặc chỉ chạy batch định kỳ
docker exec -d python-worker bash -c "RUN_MODE=batch BATCH_INTERVAL_HOURS=12 python /app/unified_runner.py"
```

Kiểm tra:

```bash
docker exec python-worker python - <<'PY'
import os

def read_cmdline(pid: str) -> str:
  try:
    with open(f"/proc/{pid}/cmdline", "rb") as f:
      raw = f.read()
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
  except Exception:
    return ""

matches = []
for pid in os.listdir("/proc"):
  if pid.isdigit():
    cmd = read_cmdline(pid)
    if "unified_runner.py" in cmd:
      matches.append((pid, cmd))

if not matches:
  print("NOT_RUNNING")
else:
  for pid, cmd in sorted(matches, key=lambda x: int(x[0])):
    print(f"PID={pid} CMD={cmd}")
PY
```

---

## 📊 XEM DỮ LIỆU TRÊN KIBANA

## 📊 XEM DỮ LIỆU TRÊN KIBANA

### Bước 1: Mở Kibana

```
http://localhost:5601
```

### Bước 2: Tạo Index Patterns

#### Index Pattern 1: stock_realtime (Streaming Data)

1. Vào **Management** → **Stack Management** → **Index Patterns**
2. Click **"Create index pattern"**
3. Nhập: `stock_realtime`
4. Chọn Time field: `@timestamp` (khuyến nghị)
   - Nếu bạn không thấy `@timestamp` thì có thể chọn tạm `window_start` (nếu có)
5. Click **"Create index pattern"**

Nếu **không chọn được Time field** (không thấy `@timestamp`/`window_start` trong dropdown):

1. Kiểm tra Elasticsearch có nhận đúng kiểu `date` chưa:

```bash
curl -s "http://localhost:9200/stock_realtime/_mapping?pretty" | head -200
```

2. Nếu bạn thấy `@timestamp` đang bị map sai (ví dụ `long`), hãy reset index `stock_realtime` và tạo lại mapping chuẩn (sau đó restart Spark Streaming để bắn dữ liệu lại):

```bash
# Stop Spark để tránh ghi mapping sai lại ngay lập tức
docker compose stop spark-streaming-simple

# Xóa index cũ
curl -X DELETE "http://localhost:9200/stock_realtime"

# Tạo lại index với mapping có Time field kiểu date
curl -X PUT "http://localhost:9200/stock_realtime" ^
 -H "Content-Type: application/json" ^
 -d "{\"mappings\":{\"properties\":{\"@timestamp\":{\"type\":\"date\"},\"window_start\":{\"type\":\"date\"},\"window_end\":{\"type\":\"date\"},\"processed_time\":{\"type\":\"date\"},\"ticker\":{\"type\":\"keyword\"},\"company\":{\"type\":\"keyword\"},\"avg_price\":{\"type\":\"double\"},\"min_price\":{\"type\":\"double\"},\"max_price\":{\"type\":\"double\"},\"price_volatility\":{\"type\":\"double\"},\"total_volume\":{\"type\":\"long\"},\"trade_count\":{\"type\":\"long\"}}}}"

# Start lại Spark Streaming
docker compose start spark-streaming-simple

# Đợi 1-2 phút rồi kiểm tra lại docs
sleep 90
curl -s "http://localhost:9200/stock_realtime/_count?pretty"
```

3. Quay lại Kibana:

- Refresh trang Kibana (F5)
- Nếu đã tạo index pattern rồi: vào Index Pattern → **Refresh field list** (hoặc xóa và tạo lại)

#### Index Pattern 2: batch-features (Batch Data)

1. Click **"Create index pattern"** lần nữa
2. Nhập: `batch-features`
3. Chọn Time field: `@timestamp` (hoặc `time`)
4. Click **"Create index pattern"**

### Bước 3: Xem dữ liệu Real-time

1. Vào **Analytics** → **Discover**
2. Chọn index pattern: `stock_realtime`
3. Chọn time range: **Last 15 minutes**
4. Refresh tự động: **10 seconds**

**Các trường trong stock_realtime:**

- `window_start`, `window_end`: Thời gian window
- `ticker`, `company`: Mã cổ phiếu, tên công ty
- `avg_price`: Giá trung bình trong window
- `min_price`, `max_price`: Giá thấp/cao nhất
- `total_volume`: Tổng khối lượng giao dịch
- `trade_count`: Số lượng trades
- `price_volatility`: Độ biến động (stddev)

### Bước 4: Xem dữ liệu Batch Features

1. Chọn index pattern: `batch-features`
2. Chọn time range: **Last 7 days** hoặc **Last 30 days**

**Các trường trong batch-features:**

- `ticker`, `time`, `Open`, `High`, `Low`, `Close`, `Volume`: Dữ liệu OHLCV
- `ma50`, `ma100`, `ma200`: Moving averages
- `trend`: up/down/sideway
- `trend_strength`: Độ mạnh xu hướng
- `cumulative_return`: Tỷ suất sinh lợi tích lũy
- `drawdown`, `max_drawdown`: Sụt giảm từ đỉnh
- `volume_ma20`, `volume_ratio`: Volume metrics
- `monthly_volatility`: Volatility theo tháng
- `market_regime`: normal/high_vol

### Bước 5: Tạo Visualizations

Vào **Analytics** → **Visualize Library** → **Create visualization**

**Dashboard đề xuất:**

**1. Real-time Monitoring (stock_realtime)**

- Line chart: `avg_price` theo `window_start` (split by ticker)
- Area chart: `total_volume` theo thời gian
- Metric: Current `price_volatility`
- Gauge: `trade_count` (last 5 minutes)

**2. Batch Analysis (batch-features)**

- Line chart: `Close` price với `ma50`, `ma100`, `ma200`
- Line chart: `cumulative_return` theo ticker
- Area chart: `drawdown` (negative chart)
- Bar chart: `trend` distribution
- Heat map: `monthly_volatility` by ticker và month

---

## 🔧 QUẢN LÝ VÀ MONITORING

## 🔧 QUẢN LÝ VÀ MONITORING

### Kiểm tra logs các services

```bash
# Tất cả services
docker compose logs -f

# Kafka Producer
docker exec python-worker tail -f /tmp/producer.log

# Spark Streaming
docker logs spark-streaming-simple -f --tail 50

# Batch Processing (nếu chạy daemon)
docker exec python-worker tail -f /logs/unified_runner.log

# Elasticsearch
docker logs elasticsearch --tail 50

# Kafka
docker logs kafka --tail 50
```

### Kiểm tra health của các services

```bash
# System health check (tự động)
docker exec python-worker python /app/unified_runner.py monitor

# Elasticsearch
curl "http://localhost:9200/_cluster/health?pretty"
curl "http://localhost:9200/_cat/indices?v"

# HDFS
docker exec hadoop-namenode hdfs dfs -ls /
docker exec hadoop-namenode hdfs dfs -ls /serving
docker exec hadoop-namenode hdfs dfs -ls /user/kafka_data/stocks_history

# Kafka topics
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic stocks-history

# Kibana
curl -s "http://localhost:5601/api/status" | grep -o '"state":"[^"]*"'
```

### Restart các services

```bash
# Restart Producer
docker exec python-worker pkill -f kafka_producer.py
docker exec python-worker bash -c "cd /app && nohup python kafka_producer.py > /tmp/producer.log 2>&1 &"

# Restart Spark Streaming
docker compose restart spark-streaming-simple

# Restart Elasticsearch
docker compose restart elasticsearch

# Restart tất cả
docker compose restart
```

---

## 🛑 DỪNG VÀ RESET HỆ THỐNG

### Dừng toàn bộ hệ thống

```bash
docker compose down
```

### Reset hoàn toàn (xóa dữ liệu cũ)

```bash
# Stop tất cả
docker compose down

# Xóa volumes
docker volume rm big_data_hdfs-namenode big_data_hdfs-datanode big_data_spark-ivy-cache 2>/dev/null || true

# Xóa Spark checkpoints
docker compose up -d hadoop-namenode
sleep 15
docker exec hadoop-namenode hdfs dfs -rm -r /user/spark_checkpoints/* 2>/dev/null || true
docker compose stop hadoop-namenode

# Start lại từ đầu
docker compose down
docker compose up -d
```

### Reset chỉ Elasticsearch data

```bash
# Xóa indexes
curl -X DELETE "http://localhost:9200/stock_realtime"
curl -X DELETE "http://localhost:9200/batch-features"

# Hoặc xóa tất cả indexes
curl -X DELETE "http://localhost:9200/*"

# Restart Spark Streaming để tạo lại index
docker compose restart spark-streaming-simple
```

---

## 🔍 TROUBLESHOOTING

## 🔍 TROUBLESHOOTING

### 1. Index không xuất hiện trong Elasticsearch

**Kiểm tra Producer:**

```bash
docker exec python-worker ps aux | grep kafka_producer
docker exec python-worker tail -30 /tmp/producer.log
```

**Nếu không chạy, restart:**

```bash
docker exec python-worker bash -c "cd /app && nohup python kafka_producer.py > /tmp/producer.log 2>&1 &"
```

**Kiểm tra Kafka có nhận messages:**

```bash
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic stocks-history \
  --from-beginning \
  --max-messages 5
```

### 2. Spark Streaming có lỗi

**Xem logs chi tiết:**

```bash
docker logs spark-streaming-simple --tail 100
```

**Lỗi thường gặp:**

**a) NoSuchMethodError / Compatibility issues**

```bash
# Xóa checkpoint và restart
docker exec hadoop-namenode hdfs dfs -rm -r /user/spark_checkpoints/stock_realtime
docker compose restart spark-streaming-simple
```

**b) Elasticsearch connection refused**

```bash
# Kiểm tra ES đang chạy
curl "http://localhost:9200/_cluster/health"

# Restart ES nếu cần
docker compose restart elasticsearch
sleep 30
docker compose restart spark-streaming-simple
```

**c) Kafka connection timeout**

```bash
# Kiểm tra Kafka
docker logs kafka --tail 50

# Restart Kafka
docker compose restart zookeeper kafka
sleep 30
docker compose restart spark-streaming-simple
```

### 3. Batch Processing thất bại

**Kiểm tra lỗi:**

```bash
docker exec python-worker python /app/unified_runner.py batch
```

**Lỗi thường gặp:**

**a) HDFS connection failed**

```bash
# Kiểm tra HDFS
docker logs hadoop-namenode --tail 50
curl "http://localhost:9870"

# Restart HDFS
docker compose restart hadoop-namenode hadoop-datanode
```

**b) Elasticsearch indexing failed**

```bash
# Kiểm tra ES health
curl "http://localhost:9200/_cluster/health?pretty"

# Kiểm tra disk space
docker exec elasticsearch df -h
```

**c) Memory error (OOM)**

```bash
# Giảm batch size trong run_all.py
# Hoặc tăng memory cho python-worker trong docker-compose.yml
```

### 4. Kibana không hiển thị dữ liệu

**Kiểm tra Elasticsearch có dữ liệu:**

```bash
curl "http://localhost:9200/stock_realtime/_count?pretty"
curl "http://localhost:9200/batch-features/_count?pretty"
```

**Nếu count > 0 nhưng Kibana không thấy:**

- Refresh trang Kibana (F5)
- Kiểm tra Time Range (chọn rộng hơn: Last 24 hours)
- Xóa Index Pattern và tạo lại
- Clear browser cache

**Kiểm tra Kibana logs:**

```bash
docker logs kibana --tail 50
```

### 5. Data không update trong Kibana

**Kiểm tra thời gian:**

```bash
# So sánh thời gian hệ thống với dữ liệu
date
curl "http://localhost:9200/stock_realtime/_search?pretty" | grep window_start | head -5
```

**Nếu time mismatch:**

- Adjust time range trong Kibana
- Hoặc sync thời gian containers với host

### 6. Performance issues

**a) Streaming lag:**

```bash
# Check Spark UI
# Mở http://localhost:18080 (nếu history server được enable)
# Hoặc check logs
docker logs spark-streaming-simple | grep "Batch"
```

**b) Kafka lag:**

```bash
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --all-groups
```

**c) Elasticsearch slow:**

```bash
curl "http://localhost:9200/_cat/thread_pool?v"
curl "http://localhost:9200/_nodes/stats/indices?pretty"
```

---

## 📈 CẤU TRÚC DỮ LIỆU CHI TIẾT

### Kafka Message Schema (stocks-history topic)

```json
{
  "ticker": "AAPL",
  "company": "Apple Inc.",
  "time": "2025-01-05T10:30:00+00:00",
  "Open": 280.5,
  "High": 282.1,
  "Low": 278.2,
  "Close": 281.0,
  "Adj Close": 281.0,
  "Volume": 45123456
}
```

### Elasticsearch Index: stock_realtime

**Mapping:**

```json
{
  "window_start": "2025-01-05T10:00:00Z",
  "window_end": "2025-01-05T10:00:30Z",
  "ticker": "AAPL",
  "company": "Apple Inc.",
  "avg_price": 280.75,
  "min_price": 278.2,
  "max_price": 282.1,
  "total_volume": 135370368,
  "trade_count": 3,
  "price_volatility": 1.42,
  "processed_time": "2025-01-05T10:01:05Z"
}
```

**Giải thích:**

- `window_start/end`: 30s time window
- `avg_price`: Average Close price trong window
- `min_price`: Min Low price trong window
- `max_price`: Max High price trong window
- `total_volume`: Sum Volume trong window
- `trade_count`: Số messages trong window
- `price_volatility`: Standard deviation của Close price

### Elasticsearch Index: batch-features

**Mapping:**

```json
{
  "@timestamp": "2025-01-05T10:30:00Z",
  "ticker": "AAPL",
  "time": "2025-01-05T10:30:00Z",
  "Open": 280.5,
  "High": 282.1,
  "Low": 278.2,
  "Close": 281.0,
  "Volume": 45123456,

  "ma50": 275.3,
  "ma100": 270.45,
  "ma200": 265.8,
  "trend": "up",
  "trend_strength": 0.0234,

  "cumulative_return": 0.1523,
  "drawdown": -0.0234,
  "max_drawdown": -0.0812,

  "volume_ma20": 42000000,
  "volume_ratio": 1.074,

  "month": "2025-01",
  "monthly_volatility": 0.0245,
  "market_regime": "normal"
}
```

**Giải thích:**

- `ma50/100/200`: Moving averages (50, 100, 200 days)
- `trend`: up (ma50 > ma200), down, sideway
- `trend_strength`: (ma50 - ma200) / Close
- `cumulative_return`: Tỷ suất sinh lợi tích lũy
- `drawdown`: % sụt giảm từ đỉnh gần nhất
- `max_drawdown`: Drawdown tối đa trong lịch sử
- `volume_ma20`: Volume trung bình 20 ngày
- `volume_ratio`: Volume hiện tại / volume_ma20
- `monthly_volatility`: Volatility theo tháng
- `market_regime`: normal hoặc high_vol

---

## ⚙️ CẤU HÌNH HỆ THỐNG

### Kafka Producer (kafka_producer.py)

```python
KAFKA_TOPIC = "stocks-history"      # Topic duy nhất
UPDATE_INTERVAL = 30                # 30 giây/batch
TICKERS = ["AAPL", "NVDA"]          # Danh sách cổ phiếu
```

Thay đổi tickers:

```bash
# Trong docker-compose.yml
environment:
  - TICKERS=AAPL,NVDA,TSLA,MSFT
```

### Spark Streaming (spark_streaming_simple.py)

```python
WINDOW_DURATION = "30 seconds"      # Time window
WATERMARK_DELAY = "1 minute"        # Late data tolerance
TRIGGER_INTERVAL = "30 seconds"     # Processing trigger
```

### Batch Processing (run_all.py)

```python
# Các batch jobs được chạy:
- batch_long_term_trend()          # MA50, MA100, MA200
- batch_cumulative_return()         # Cumulative return
- batch_drawdown()                  # Drawdown, max drawdown
- batch_volume_features()           # Volume MA, ratio
- batch_monthly_volatility()        # Monthly volatility
- batch_market_regime()             # Market regime classification
```

### Unified Runner (unified_runner.py)

```bash
# Environment variables
RUN_MODE=all                        # all, batch, monitor
BATCH_INTERVAL_HOURS=24             # Batch interval

# Usage
python unified_runner.py            # Continuous mode
python unified_runner.py batch      # Run batch once
python unified_runner.py monitor    # Check health once
```

---

## 📞 TỔNG KẾT VÀ HỖ TRỢ

### Quick Commands Cheat Sheet

```bash
# Start hệ thống
docker compose up -d
docker exec python-worker bash -c "cd /app && nohup python kafka_producer.py > /tmp/producer.log 2>&1 &"

# Check status
docker compose ps
curl "http://localhost:9200/_cat/indices?v"
docker logs spark-streaming-simple --tail 20

# Run batch
docker exec python-worker python /app/unified_runner.py batch

# View logs
docker exec python-worker tail -f /tmp/producer.log
docker logs spark-streaming-simple -f

# Health check
docker exec python-worker python /app/unified_runner.py monitor

# Reset
docker compose down
docker volume prune -f
docker compose up -d
```

### Architecture Summary

```
DATA FLOW:
1. history.json → Kafka Producer → stocks-history topic
2a. stocks-history → Kafka Consumer → HDFS (raw storage)
2b. stocks-history → Spark Streaming → Elasticsearch (stock_realtime)
3. history.json → Batch Processing → HDFS + Elasticsearch (batch-features)

UNIFIED SCHEMA: ticker, company, time, Open, High, Low, Close, Adj Close, Volume
SINGLE TOPIC: stocks-history
INDEXES: stock_realtime (streaming), batch-features (batch)
```

### Ports Reference

- **9200**: Elasticsearch REST API
- **5601**: Kibana UI
- **9092**: Kafka broker
- **2181**: Zookeeper
- **9870**: HDFS NameNode UI
- **9864**: HDFS DataNode UI

### Monitoring URLs

- Kibana: http://localhost:5601
- Elasticsearch: http://localhost:9200
- HDFS: http://localhost:9870

---

**🎉 HỆ THỐNG ĐÃ ĐƯỢC THỐNG NHẤT VÀ SẴN SÀNG HOẠT ĐỘNG!**

_Dự án merge thành công batch processing và real-time streaming với schema nhất quán._
