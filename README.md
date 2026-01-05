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

Tạo Index Pattern: `stock_realtime` với time field `window_start`

## 📖 Tài Liệu Chi Tiết

Xem file: **[HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md)**

## 🛑 Dừng & Reset

```bash
docker compose down
docker volume rm big_data_es_data big_data_kafka_data 2>/dev/null || true
```

## 📁 Cấu Trúc

```
├── docker-compose.yml              # Định nghĩa services
├── kafka_producer.py               # Producer gửi dữ liệu
├── spark_streaming/
│   ├── spark_streaming_simple.py              # Job chính
│   ├── spark_streaming_technical_indicators.py # Technical analysis
│   └── spark_streaming_anomaly_detection.py   # Anomaly detection
└── HUONG_DAN_SU_DUNG.md           # Hướng dẫn đầy đủ
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
