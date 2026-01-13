FROM python:3.11-slim-bookworm

# Cài đặt Java 17 và procps
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    procps \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Thiết lập JAVA_HOME (đường dẫn chuẩn trên Debian Bookworm)
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

WORKDIR /app

# 2. Thiết lập biến môi trường JAVA_HOME
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# 3. Copy file requirements (Đảm bảo bạn đã thêm 'pyspark' vào file này)
COPY requirements.txt /app/

# 4. Cài đặt dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# 5. Copy toàn bộ code
COPY kafka_producer.py kafka_consumer.py price_simulator.py standardization_local.py unified_runner.py run_all.py /app/
COPY batch_jobs/ /app/batch_jobs/
COPY history.json /app/

# 6. Tạo thư mục output
RUN mkdir -p /app/output

# Giữ container chạy ngầm
CMD ["tail", "-f", "/dev/null"]