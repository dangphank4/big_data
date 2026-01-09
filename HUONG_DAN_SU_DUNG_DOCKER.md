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
- ✅ `spark-anomaly-detection` (Price Anomaly Detection)

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

**Kiểm tra Spark Streaming (metrics aggregation):**

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

**Kiểm tra Spark Anomaly Detection (price anomalies):**

```bash
docker logs spark-anomaly-detection --tail 30
```

Phải thấy:

```
[INFO] Starting Anomaly Detection Job
[INFO] Thresholds:  ... docs.count > 0
yellow open stock_anomalies  ... docs.count >= 0
```

**Lưu ý:** Index `stock_anomalies` chỉ có documents khi phát hiện bất thường. Nếu không có anomaly thì index rỗng hoặc không tồn tại. Price change: >5.0%

- Volume spike: >3.0x
- Volatility: >3.0%
- Price gap: >2.0%
  [INFO] Anomaly detection started. Writing to stock_anomalies

````

### Bước 5: Chờ dữ liệu được ghi vào Elasticsearch (2-3 phút)

```bash
sleep 120
curl -s "http://localhost:9200/_cat/indices?v" | grep stock
````

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

1. Click **"Create index pattern"**

#### Index Pattern 3: stock_anomalies (Price Anomaly Detection)

1. Click **"Create index pattern"** lần nữa
2. Nhập: `stock_anomalies`
3. Chọn Time field: `@timestamp`
4. Click **"Create index pattern"**

**Lưu ý:** Nếu index `stock_anomalies` chưa tồn tại (chưa có anomaly nào), hãy chờ vài phút hoặc quay lại sau khi hệ thống phát hiện bất thường đầu tiên. lần nữa 2. Nhập: `batch-features` 3. Chọn Time field: `@timestamp` (hoặc `time`) 4. Click **"Create index pattern"**

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
2. Chọn time range: \*_Last 7 days_

### Bước 5: Xem dữ liệu Price Anomalies

1. Chọn index pattern: `stock_anomalies`
2. Chọn time range: **Last 15 minutes** hoặc **Last 1 hour**
3. Refresh tự động: **10 seconds**

**Các trường trong stock_anomalies:**

**Thông tin cơ bản:**

- `window_start`, `window_end`: Thời gian window phát hiện
- `ticker`, `company`: Mã cổ phiếu, tên công ty
- `avg_price`, `min_price`, `max_price`: Giá trong window
- `total_volume`, `trade_count`: Volume và số lượng trades

**Dữ liệu so sánh:**

- `historical_avg_price`: Giá trung bình lịch sử (5 windows trước)
- `hiAnomaly Alerts (stock_anomalies)\*\*

- **Alert Table**: Hiển thị anomalies gần nhất
  - Columns: ticker, window_start, anomaly_types, anomaly_severity, price_change_pct
  - Sort: By @timestamp descending
  - Filter: Last 1 hour
- **Heat Map**: Anomaly severity by ticker and time
  - X-axis: window_start
  - Y-axis: ticker
  - Color: anomaly_severity
- **Bar Chart**: Anomaly types distribution
  - X-axis: anomaly_types
  - Y-axis: Count
  - Filter: Last 24 hours
- **Line Chart**: Price change % over time (only anomalies)
  - X-axis: window_start
  - Y-axis: price_change_pct
  - Split by: ticker
  - Threshold line: 5% (anomaly threshold)
- **Gauge**: Current anomalies count
  - Metric: Count of documents
  - Time range: Last 15 minutes
  - Color ranges: 0-green, 1-5 yellow, >5 red

\*\*3. storical_avg_volume`: Volume trung bình lịch sử

- `historical_volatility`: Volatility trung bình lịch sử

**Chỉ số bất thường:**

- `price_change_p (metrics)
  docker logs spark-streaming-simple -f --tail 50

# Spark Anomaly Detection

docker logs spark-anomaly-detection volume (ví dụ: 3.5 = tăng 350%)

- `volatility_ratio`: Tỷ lệ volatility so với lịch sử
- `price_gap_pct`: % khoảng cách giữa max và min

**Cờ phát hiện:**

- `is_price_spike`: Giá tăng/giảm đột ngột >5%
- `is_volume_spike`: Volume tăng vọt >3x
- `is_high_volatility`: Volatility cao >3%
- `is_price_gap`: Khoảng cách giá lớn >2%
- `anomaly_severity`: Độ nghiêm trọng (0-4)
- `anomaly_types`: Loại bất thường (PRICE_SPIKE, VOLUME_SPIKE, HIGH_VOLATILITY, PRICE_GAP)\* hoặc **Last 30 days**

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

Kiểm tra anomaly detection có hoạt động
curl "http://localhost:9200/stock_anomalies/\_count?pretty"

#

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
docker exeSpark Anomaly Detection
docker compose restart spark-anomaly-detection

# Restart c python-worker pkill -f kafka_producer.py
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

stock_anomalies"
curl -X DELETE "http://localhost:9200/batch-features"

# Hoặc xóa tất cả indexes

curl -X DELETE "http://localhost:9200/\*"

# Restart Spark Streaming để tạo lại indexes

docker compose restart spark-streaming-simple spark-anomaly-detectioneatures"

# Hoặc xóa tất cả indexes

curl -X DELETE "http://localhost:9200/\*"

# Restart Spark Streaming để tạo lại index

docker compose restart spark-streaming-simple

````

---

## 🔍 TROUBLESHOOTING

## 🔍 TROUBLESHOOTING

### 1. Index không xuất hiện trong Elasticsearch

**Kiểm tra Producer:**

```bash
docker exec python-worker ps aux | grep kafka_producer
docker exec python-worker tail -30 /tmp/producer.log
````

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
 spark-anomaly-detection
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
curl "http://localhost:9200/stock_anomalies/_count?pretty"
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

**Lưu ý về stock_anomalies:**

- Index này chỉ có data khi phát hiện anomaly
- Nếu giá không biến động bất thường, index có thể rỗng
- Thử tăng volatility trong price_simulator.py để tạo anomalies testker logs kibana --tail 50

````

### 5. Data không update trong Kibana

**Kiểm tra thời gian:**

```bash
# So sánh thời gian hệ thống với dữ liệu
date
curl "http://localhost:9200/stock_realtime/_search?pretty" | grep window_start | head -5
````

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

### Elasticsearch Index: stock_anomalies

**Mapping:**

```json
{
  "@timestamp": "2025-01-05T10:00:00Z",
  "window_start": "2025-01-05T10:00:00Z",
  "window_end": "2025-01-05T10:00:30Z",
  "ticker": "AAPL",
  "company": "Apple Inc.",
  "avg_price": 295.5,
  "min_price": 293.2,
  "max_price": 298.1,
  "total_volume": 180000000,
  "trade_count": 3,
  "price_volatility": 2.15,
  "historical_avg_price": 280.75,
  "historical_avg_volume": 45000000,
  "historical_volatility": 0.85,
  "price_change_pct": 0.0525,
  "price_change_abs": 0.0525,
  "volume_spike_ratio": 4.0,
  "volatility_ratio": 2.53,
  "price_gap_pct": 0.0165,
  "is_price_spike_up": true,
  "is_price_spike_down": false,
  "is_volume_spike": true,
  "is_high_volatility": false,
  "is_price_gap": false,
  "anomaly_severity": 2,
  "anomaly_types": "PRICE_SPIKE_UP,VOLUME_SPIKE",
  "detected_time": "2025-01-05T10:01:08Z"
}
```

**Giải thích:**

- **Thông tin window**: window_start/end, ticker, company, giá/volume trong window
- **Historical baseline**: historical_avg_price/volume/volatility (5 windows trước)
- **Anomaly metrics**:
  - `price_change_pct`: 0.0525 = tăng **+5.25%** so với lịch sử (có dấu: +tăng/-giảm)
  - `price_change_abs`: 0.0525 = absolute value để so sánh threshold
  - `volume_spike_ratio`: 4.0 = volume gấp 4 lần trung bình
  - `volatility_ratio`: 2.53 = volatility gấp 2.53 lần thường
  - `price_gap_pct`: 0.0165 = chênh lệch max-min là 1.65%
- **Detection flags**:
  - `is_price_spike_up: true` - Phát hiện tăng giá >5%
  - `is_price_spike_down: false` - Không giảm >5%
  - `is_volume_spike: true` - Volume spike detected
  - `is_high_volatility: false` - Volatility bình thường
  - `is_price_gap: false` - Không có gap lớn
- `anomaly_severity`: 0-5 (số loại anomaly phát hiện, tối đa 5)
- `anomaly_types`: "PRICE_SPIKE_UP,VOLUME_SPIKE" (danh sách CSV)
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
docker logs spark-anomaly-detection --tail 20

# Run batch
docker exec python-worker python /app/unified_runner.py batch

# View logs
docker exec python-worker tail -f /tmp/producer.log
docker logs spark-streaming-simple -f
docker logs spark-anomaly-detection -f

# Health check
docker exec python-worker python /app/unified_runner.py monitor

# Check anomalies
curl "http://localhost:9200/stock_anomalies/_search?pretty&size=5&sort=@timestamp:desc"

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
2c. stocks-history → Spark Anomaly Detection → Elasticsearch (stock_anomalies)
3. history.json → Batch Processing → HDFS + Elasticsearch (batch-features)

UNIFIED SCHEMA: ticker, company, time, Open, High, Low, Close, Adj Close, Volume
SINGLE TOPIC: stocks-history
INDEXES:
  - stock_realtime (streaming metrics)
  - stock_anomalies (price anomaly alerts)
  - batch-features (batch features)
```

### Ports Reference

- **9200**: Elasticsearch REST API
- **5601**: Kibana UI
- **4040**: Spark UI (streaming jobs, nếu expose)

### Monitoring URLs

- Kibana: http://localhost:5601
- Elasticsearch: http://localhost:9200
- HDFS: http://localhost:9870
- Spark Streaming UI: http://localhost:4040 (nếu port-forward)

### Key Elasticsearch Queries

```bash
# Count documents per index
curl "http://localhost:9200/stock_realtime/_count?pretty"
curl "http://localhost:9200/stock_anomalies/_count?pretty"
curl "http://localhost:9200/batch-features/_count?pretty"

# Get latest anomalies
curl "http://localhost:9200/stock_anomalies/_search?pretty&size=5&sort=@timestamp:desc"

# Get anomalies for specific ticker
curl -X GET "http://localhost:9200/stock_anomalies/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "bool": {
      "must": [
        {"term": {"ticker": "AAPL"}},
        {"range": {"@timestamp": {"gte": "now-1h"}}}
      ]
    }
  },
  "sort": [{"@timestamp": "desc"}],
  "size": 10
}
'

# Get high severity anomalies only
curl -X GET "http://localhost:9200/stock_anomalies/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "range": {"anomaly_severity": {"gte": 2}}
  },
  "sort": [{"@timestamp": "desc"}],
  "size": 20
}
'
```

- Kibana: http://localhost:5601
- Elasticsearch: http://localhost:9200
- HDFS: http://localhost:9870

---

**🎉 HỆ THỐNG ĐÃ ĐƯỢC THỐNG NHẤT VÀ SẴN SÀNG HOẠT ĐỘNG!**

_Dự án merge thành công batch processing và real-time streaming với schema nhất quán._

---

## 🔔 PRICE ANOMALY DETECTION - PHÁT HIỆN BẤT THƯỜNG GIÁ

### Tổng quan

Hệ thống đã được bổ sung **Real-time Price Anomaly Detection** - một Speed Layer job chuyên phát hiện các bất thường về giá chứng khoán trong thời gian thực.

### Các loại anomaly được phát hiện

**1. PRICE_SPIKE_UP - Tăng giá đột ngột**

- **Ngưỡng**: Tăng >5% trong 30 giây (so với 5 windows trước)
- **Ví dụ**: AAPL từ $280 → $295 trong 30s (tăng +5.4%)
- **Use case**: Tin tức tích cực, insider buying, pump schemes
- **Flag**: `is_price_spike_up: true`

**2. PRICE_SPIKE_DOWN - Giảm giá đột ngột**

- **Ngưỡng**: Giảm >5% trong 30 giây (so với 5 windows trước)
- **Ví dụ**: AAPL từ $280 → $265 trong 30s (giảm -5.4%)
- **Use case**: Tin tức tiêu cực, insider selling, dump schemes
- **Flag**: `is_price_spike_down: true`

**3. VOLUME_SPIKE - Khối lượng giao dịch tăng vọt**

- **Ngưỡng**: Volume gấp >3x trung bình (5 windows trước)
- **Ví dụ**: Volume trung bình 45M → đột ngột 180M
- **Use case**: Institutional buying/selling, market events
- **Flag**: `is_volume_spike: true`

**4. HIGH_VOLATILITY - Độ biến động cao**

- **Ngưỡng**: Standard deviation >3% (so với 5 windows trước)
- **Ví dụ**: Giá dao động mạnh trong cùng một window
- **Use case**: Market uncertainty, earnings announcements
- **Flag**: `is_high_volatility: true`

**5. PRICE_GAP - Khoảng cách giá lớn**

- **Ngưỡng**: (Max - Min) / Avg > 2% trong window
- **Ví dụ**: Trong 30s, giá từ $280 → $286 → $282 (gap 2.1%)
- **Use case**: Flash crashes, liquidity issues
- **Flag**: `is_price_gap: true`

### Cách hoạt động

```
Kafka Stream → 30s Window Aggregation
    ↓
Compare với Historical Baseline (5 windows trước)
    ↓
Tính toán các chỉ số:
  - price_change_pct (% thay đổi so với lịch sử)
  - volume_spike_ratio (tỷ lệ volume/avg)
  - volatility_ratio (volatility/avg)
  - price_gap_pct (% chênh lệch max-min)
    ↓
So sánh với Thresholds
    ↓
Nếu vượt ngưỡng → Ghi vào Elasticsearch (stock_anomalies)
    ↓
Alert trên Kibana Dashboard
```

### Xem anomalies trên Kibana

**Tạo Dashboard:**

1. **Data Table - Recent Anomalies**

   - Index: `stock_anomalies`
   - Columns: ticker, window_start, anomaly_types, anomaly_severity, price_change_pct
   - Time range: Last 1 hour
   - Sort: @timestamp descending

2. **Metric - Anomaly Count**

   - Count of anomalies in last 15 minutes
   - Color thresholds: 0 (green), 1-5 (yellow), >5 (red)

3. **Bar Chart - Anomaly Types**

   - X-axis: anomaly_types
   - Y-axis: Count
   - Shows which anomaly type is most common

4. **Line Chart - Price Change Over Time**
   - X-axis: @timestamp
   - Y-axis: price_change_pct
   - Split by: ticker
   - Add threshold line at 5%

### Cấu hình Thresholds

Có thể điều chỉnh trong `spark_anomaly_detection.py`:

```python
# Thresholds hiện tại (cho 30s windows với simulated data)
PRICE_CHANGE_THRESHOLD = 0.05  # 5%
VOLUME_SPIKE_THRESHOLD = 3.0    # 3x
VOLATILITY_THRESHOLD = 0.03     # 3%
PRICE_GAP_THRESHOLD = 0.02      # 2%
```

**Tuning tips cho các loại thị trường:**

- **Thị trường biến động cao** (crypto, penny stocks):
  - Tăng thresholds: 7-10%, 5x, 5%, 3%
  - Tránh quá nhiều false positives
- **Thị trường ổn định** (blue chips, bonds):
  - Giảm thresholds: 3%, 2x, 2%, 1%
  - Detect được cả biến động nhỏ
- **Testing**:
  - Giảm thresholds để thấy nhiều anomalies hơn
  - Monitor false positive rate

**⚠️ QUAN TRỌNG: Khi crawl dữ liệu theo phút**

Khi bạn chuyển sang crawl thực tế (1 data point/phút thay vì mô phỏng 30s):

**Bước 1: Điều chỉnh Window Duration**

```python
# Trong spark_anomaly_detection.py
WINDOW_DURATION = "1 minute"  # hoặc "2 minutes"
WATERMARK_DELAY = "2 minutes"
TRIGGER_INTERVAL = "1 minute"
```

**Bước 2: Điều chỉnh Thresholds**

```python
# Cho 1-minute windows với real crawl data
PRICE_CHANGE_THRESHOLD = 0.03  # 3% (chặt hơn, data chi tiết hơn)
VOLUME_SPIKE_THRESHOLD = 2.5    # 2.5x (tùy market)
VOLATILITY_THRESHOLD = 0.02     # 2% (điều chỉnh theo reality)
PRICE_GAP_THRESHOLD = 0.015     # 1.5% (chặt hơn)
```

**Lý do điều chỉnh:**

- ✅ **Data theo phút chi tiết hơn** → Có thể detect anomaly nhỏ hơn
- ✅ **Ít aggregation** → Price change thực tế hơn
- ✅ **Tránh false positives** → Volatility intraday bình thường không trigger
- ✅ **Baseline chính xác hơn** → 5 windows = 5 phút history (đủ để compare)

**Bước 3: Test và Monitor**

```bash
# Sau khi deploy với real crawl:
# 1. Monitor số lượng anomalies
curl "http://localhost:9200/stock_anomalies/_count?pretty"

# 2. Xem anomalies sample
curl "http://localhost:9200/stock_anomalies/_search?size=10&sort=@timestamp:desc&pretty"

# 3. Check false positive rate
# Nếu quá nhiều alerts → Tăng thresholds
# Nếu miss important events → Giảm thresholds
```

**Ví dụ thực tế:**

Giả sử crawl AAPL mỗi phút, giá dao động bình thường 0.5-1%:

- Threshold 5% → Chỉ catch crash/pump thật sự
- Threshold 3% → Catch cả unusual moves
- Threshold 1% → Quá nhiều false positives

**Khuyến nghị:**

- Bắt đầu với 3% cho PRICE_CHANGE_THRESHOLD
- Monitor trong 1-2 ngày
- Điều chỉnh dựa trên kết quả thực tế

### Queries hữu ích

**Lấy 10 anomalies mới nhất:**

```bash
curl "http://localhost:9200/stock_anomalies/_search?pretty&size=10&sort=@timestamp:desc"
```

**Lấy anomalies severity cao (≥3):**

```bash
curl -X GET "http://localhost:9200/stock_anomalies/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {"range": {"anomaly_severity": {"gte": 3}}},
  "sort": [{"@timestamp": "desc"}]
}
'
```

**Lấy price spikes của AAPL trong 1 giờ qua:**

```bash
curl -X GET "http://localhost:9200/stock_anomalies/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "bool": {
      "must": [
        {"term": {"ticker": "AAPL"}},
        {"term": {"is_price_spike": true}},
        {"range": {"@timestamp": {"gte": "now-1h"}}}
      ]
    }
  }
}
'
```

### Alerting (Production)

Trong production, có thể setup alerts với:

**Elasticsearch Watcher (X-Pack):**

```json
{
  "trigger": {
    "schedule": { "interval": "1m" }
  },
  "input": {
    "search": {
      "request": {
        "indices": ["stock_anomalies"],
        "body": {
          "query": {
            "bool": {
              "must": [
                { "range": { "@timestamp": { "gte": "now-1m" } } },
                { "range": { "anomaly_severity": { "gte": 2 } } }
              ]
            }
          }
        }
      }
    }
  },
  "actions": {
    "email_admin": {
      "email": {
        "to": "admin@example.com",
        "subject": "Price Anomaly Alert",
        "body": "Detected {{ctx.payload.hits.total}} anomalies"
      }
    }
  }
}
```

**Hoặc Slack/Discord webhook:**

- Đọc anomalies từ ES mỗi phút
- Nếu severity ≥ 2 → POST đến webhook
- Hiển thị alert trên Slack channel

---

**🎉 HỆ THỐNG HOÀN CHỈNH VỚI ANOMALY DETECTION!**
