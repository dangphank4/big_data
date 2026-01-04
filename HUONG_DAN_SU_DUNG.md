# HƯỚNG DẪN SỬ DỤNG PIPELINE REAL-TIME STOCK DATA

**Big Data Project - Kafka → Spark Streaming → Elasticsearch → Kibana**

---

## 📋 TỔNG QUAN HỆ THỐNG

Pipeline xử lý dữ liệu cổ phiếu real-time với Spark Streaming:

1. **stock_realtime** - Tính toán metrics cơ bản theo time window (✅ Đang chạy)
   - Aggregation theo window 30 giây
   - Metrics: avg_price, min_price, max_price, total_volume, trade_count, price_volatility

**Lưu ý:** Technical Indicators và Anomaly Detection jobs không tương thích với Spark Structured Streaming vì yêu cầu row-based window functions (RSI, MACD, v.v.). Các chỉ báo này phù hợp hơn cho batch processing.

---

## 🚀 KHỞI ĐỘNG HỆ THỐNG

### Bước 1: Start tất cả services

```bash
cd /home/danz/Downloads/big_data
docker compose up -d
```

**Chờ 30 giây** để các services khởi động hoàn tất.

### Bước 2: Kiểm tra services đang chạy

```bash
docker compose ps
```

Phải thấy các containers: `elasticsearch`, `kibana`, `kafka`, `hadoop-namenode`, `spark-streaming-simple`, `python-worker`

### Bước 3: Start Kafka Producer (gửi dữ liệu cổ phiếu)

```bash
docker exec python-worker bash -c "cd /app && nohup python kafka_producer.py > /tmp/producer.log 2>&1 &"
```

Kiểm tra Producer đang chạy:

```bash
docker exec python-worker tail -10 /tmp/producer.log
```

Phải thấy: `[BATCH] 2025-xx-xx xx:xx:xx: #N sent (2 messages)`

### Bước 4: Đợi dữ liệu được ghi vào Elasticsearch (2-3 phút)

```bash
# Kiểm tra sau 2 phút
sleep 120
curl -s -X GET "http://localhost:9200/_cat/indices?v" | grep stock
```

Phải thấy index `stock_realtime` với docs.count > 0

---

## 📊 XEM DỮ LIỆU TRÊN KIBANA

### Bước 1: Mở Kibana

```
http://localhost:5601
```

### Bước 2: Tạo Index Pattern

1. Vào **Management** → **Stack Management** → **Index Patterns**
2. Click **"Create index pattern"**
3. Nhập: `stock_realtime`
4. Chọn Time field: `window_start`
5. Click **"Create index pattern"**

### Bước 3: Xem dữ liệu Real-time

1. Vào **Analytics** → **Discover**
2. Chọn index pattern: `stock_realtime`
3. Chọn time range: **Last 15 minutes**
4. Refresh tự động: **10 seconds**

### Bước 4: Tạo Visualization (tùy chọn)

Vào **Analytics** → **Visualize Library** → **Create visualization**

**Gợi ý visualizations:**

- Line chart: `avg_price` theo thời gian
- Bar chart: `total_volume` theo ticker
- Metric: `price_volatility` hiện tại

---

## 🔧 QUẢN LÝ SPARK STREAMING JOB

### Kiểm tra logs của Spark Streaming

```bash
# Job chính (simple metrics) - Đang chạy
docker logs spark-streaming-simple --tail 50
```

**Index được tạo:** `stock_realtime`

**Lưu ý về Technical Indicators và Anomaly Detection:**
Hai jobs này (`spark_streaming_technical_indicators.py` và `spark_streaming_anomaly_detection.py`) sử dụng row-based window functions để tính RSI, MACD, Bollinger Bands, ATR - các tính năng này **không được hỗ trợ trong Spark Structured Streaming**.

Spark Structured Streaming chỉ hỗ trợ time-based window aggregation. Để sử dụng các chỉ báo kỹ thuật này, cần chuyển sang **Batch Processing** hoặc dùng các thư viện bên ngoài.

---

## 🛑 DỪNG VÀ KHỞI ĐỘNG LẠI TỪ ĐẦU

### Dừng toàn bộ hệ thống

```bash
cd /home/danz/Downloads/big_data
docker compose down
```

### Xóa dữ liệu cũ (reset hoàn toàn)

```bash
# Xóa Elasticsearch data
docker volume rm big_data_es_data 2>/dev/null || true

# Xóa Kafka data
docker volume rm big_data_kafka_data 2>/dev/null || true

# Xóa HDFS checkpoints
docker compose up -d hadoop-namenode
sleep 10
docker exec hadoop-namenode hdfs dfs -rm -r /user/spark_checkpoints/* 2>/dev/null || true
docker compose stop hadoop-namenode
```

### Khởi động lại từ đầu

```bash
docker compose up -d
sleep 30

# Start Producer
docker exec python-worker bash -c "cd /app && nohup python kafka_producer.py > /tmp/producer.log 2>&1 &"

# Đợi 2-3 phút rồi kiểm tra
sleep 120
curl -s -X GET "http://localhost:9200/_cat/indices?v" | grep stock
```

---

## 🔍 TROUBLESHOOTING

### 1. Index không xuất hiện trong Elasticsearch

**Kiểm tra Producer:**

```bash
docker exec python-worker ps aux | grep kafka_producer
docker exec python-worker tail -20 /tmp/producer.log
```

**Nếu không chạy, restart:**

```bash
docker exec python-worker bash -c "cd /app && nohup python kafka_producer.py > /tmp/producer.log 2>&1 &"
```

### 2. Spark Streaming có lỗi

**Xem logs:**

```bash
docker logs spark-streaming-simple --tail 100
```

**Nếu có lỗi NoSuchMethodError hoặc checkpoint issues:**

```bash
# Xóa checkpoint
docker exec hadoop-namenode hdfs dfs -rm -r /user/spark_checkpoints/stock_realtime

# Restart Spark
docker compose restart spark-streaming-simple
```

### 3. Kibana không hiển thị dữ liệu

**Kiểm tra Elasticsearch có dữ liệu:**

```bash
curl -X GET "http://localhost:9200/stock_realtime/_count?pretty"
```

**Nếu count > 0 nhưng Kibana không thấy:**

- Refresh trang Kibana (F5)
- Kiểm tra Time Range (phải chọn Last 15 minutes hoặc rộng hơn)
- Xóa Index Pattern và tạo lại

### 4. Kafka không nhận messages

**Kiểm tra Kafka topic:**

```bash
docker exec python-worker python -c "
from confluent_kafka import Consumer
import time

conf = {'bootstrap.servers': 'kafka:9092', 'group.id': 'test', 'auto.offset.reset': 'latest'}
consumer = Consumer(conf)
consumer.subscribe(['stock-realtime-topic'])

print('Waiting 10 seconds...')
for _ in range(10):
    msg = consumer.poll(1.0)
    if msg and not msg.error():
        print(f'Message: {msg.value().decode()[:100]}')

consumer.close()
"
```

---

## 📈 CẤU TRÚC DỮ LIỆU

### Index: stock_realtime

```json
{
  "window_start": "2025-12-21T06:00:00Z",
  "window_end": "2025-12-21T06:00:30Z",
  "ticker": "AAPL",
  "company": "Apple Inc.",
  "avg_price": 280.5,
  "min_price": 278.2,
  "max_price": 282.1,
  "total_volume": 45000000,
  "trade_count": 15,
  "price_volatility": 1.25,
  "processed_time": "2025-12-21T06:01:05Z"
}
```

**Giải thích các trường:**

- `window_start/end`: Time window 30 giây
- `avg_price`: Giá trung bình trong window
- `min_price/max_price`: Giá thấp nhất/cao nhất
- `total_volume`: Tổng khối lượng giao dịch
- `trade_count`: Số lượng trades trong window
- `price_volatility`: Độ biến động giá (standard deviation)

---

## ⚙️ CẤU HÌNH

### Producer Settings (kafka_producer.py)

- `UPDATE_INTERVAL`: 30 giây (thời gian gửi batch)
- `TICKERS`: AAPL, NVDA (thêm ticker trong docker-compose.yml)

### Spark Streaming Settings

- Window: 30 giây
- Watermark: 1 phút
- Trigger: 30 giây

### Elasticsearch Settings

- Version: 7.17.16
- No security (development mode)
- Single node

---

## 📞 HỖ TRỢ

**Xem logs chi tiết:**

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f spark-streaming-simple
docker compose logs -f kafka
docker compose logs -f elasticsearch
```

**Check Elasticsearch health:**

```bash
curl -X GET "http://localhost:9200/_cluster/health?pretty"
```

**Check Kibana status:**

```bash
curl -s "http://localhost:5601/api/status" | jq '.status.overall.state'
```

---

**🎉 Pipeline đã sẵn sàng hoạt động!**
