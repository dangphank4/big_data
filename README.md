# Big Data Real-Time Stock Analysis Pipeline

## 📊 Tổng Quan

Pipeline phân tích cổ phiếu real-time sử dụng:

- **Kafka** - Message streaming
- **Spark Streaming** - Xử lý real-time
- **Elasticsearch** - Lưu trữ dữ liệu
- **Kibana** - Visualization
- **HDFS** - Checkpoint storage

## 🚀 Quick Start

### 1. Khởi động hệ thống

```bash
docker compose up -d
sleep 30

# Start Producer
docker exec python-worker bash -c "cd /app && nohup python kafka_producer.py > /tmp/producer.log 2>&1 &"

# Đợi 2 phút và kiểm tra
sleep 120
curl -s "http://localhost:9200/_cat/indices?v" | grep stock
```

### 2. Mở Kibana

```
http://localhost:5601
```

Tạo Index Pattern: `stock_realtime` với time field `@timestamp` (khuyến nghị). Nếu bạn muốn dùng cửa sổ thời gian, có thể chọn `window_start`.

## 📖 Tài Liệu Chi Tiết

- **[HUONG_DAN_SU_DUNG_DOCKER.md](HUONG_DAN_SU_DUNG_DOCKER.md)** - Hướng dẫn chạy với Docker Compose
- **[GKE_DEPLOYMENT_GUIDE.md](GKE_DEPLOYMENT_GUIDE.md)** - Hướng dẫn deploy lên Google Kubernetes Engine
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Kiến trúc hệ thống chi tiết

## 📦 Module Structure

### Price Simulator Module (`price_simulator.py`)

Module độc lập để mô phỏng giá chứng khoán với volatility động và drift:

**Các hàm chính:**

- `initialize_ticker_state(ticker, base_close)` - Khởi tạo trạng thái ban đầu
- `simulate_next_bar(state)` - Mô phỏng giá tiếp theo
- `generate_ohlc_data(state, vol)` - Tạo dữ liệu OHLC
- `generate_volume(vol, change_percent)` - Tạo volume tương quan với volatility

**Đặc điểm:**

- Stateful simulation với volatility mean-reversion
- Heavy-tailed distribution cho shock events
- Occasional jump events (tin tức bất ngờ)
- Realistic intrabar high/low range

### Kafka Producer (`kafka_producer.py`)

Producer sử dụng `price_simulator` để stream dữ liệu realtime:

- Import từ `price_simulator`: `initialize_ticker_state`, `simulate_next_bar`, `generate_volume`
- Đọc baseline từ `history.json`
- Stream mỗi 30 giây (configurable)

## 📖 Tài Liệu Chi Tiết (Legacy)

Xem file: **[HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md)** (nếu có)

## 🛑 Dừng & Reset

```bash
docker compose down
docker volume rm big_data_es_data big_data_kafka_data 2>/dev/null || true
```

## 📁 Cấu Trúc

```
├── docker-compose.yml              # Định nghĩa services
├── kafka_producer.py               # Producer gửi dữ liệu
├── price_simulator.py              # Module mô phỏng giá chứng khoán
├── kafka_consumer.py               # Consumer lưu dữ liệu vào HDFS
├── spark_streaming/
│   ├── spark_streaming_simple.py              # Job chính
│   ├── spark_streaming_technical_indicators.py # Technical analysis
│   └── spark_streaming_anomaly_detection.py   # Anomaly detection
└── HUONG_DAN_SU_DUNG_DOCKER.md    # Hướng dẫn đầy đủ
```

## ✅ Kiểm Tra Hệ Thống

```bash
# Services
docker compose ps

# Producer logs
docker exec python-worker tail -10 /tmp/producer.log

# Spark logs
docker logs spark-streaming-simple --tail 20

# Elasticsearch
curl "http://localhost:9200/_cat/indices?v" | grep stock
```
