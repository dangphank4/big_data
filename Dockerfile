FROM python:3.12-slim

# ===============================
# METADATA
# ===============================
LABEL maintainer="bigdata-stack"
LABEL description="Kafka Producer / Consumer / Stock Crawler"

# ===============================
# WORKDIR
# ===============================
WORKDIR /app

# ===============================
# SYSTEM DEPENDENCIES
# (required by confluent-kafka)
# ===============================
RUN apt-get update && apt-get install -y \
    gcc \
    librdkafka-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ===============================
# PYTHON DEPENDENCIES
# ===============================
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ===============================
# APPLICATION CODE
# ===============================
COPY crawl_data.py .
COPY kafka_producer.py .
COPY kafka_consumer.py .
COPY price_simulator.py .

# ===============================
# ENVIRONMENT
# ===============================
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ===============================
# DEFAULT CMD
# Giữ container sống để docker exec / override bằng compose
# ===============================
CMD ["sleep", "infinity"]
