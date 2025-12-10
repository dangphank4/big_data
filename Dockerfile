# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy mã Python
COPY kafka_producer.py kafka_consumer.py history_all.json /app/

# Cài packages cần thiết
RUN pip install --no-cache-dir confluent-kafka hdfs

# Mặc định chỉ chạy bash, sẽ override khi chạy container
CMD ["bash"]
