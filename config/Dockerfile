FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (Java for Spark, procps for debugging)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    procps \
    netcat-openbsd \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME for Spark
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

# Copy requirements and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY src/ /app/src/

# Create output directory
RUN mkdir -p /app/output

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Default command (can be overridden in K8s)
CMD ["python", "-m", "src.producers.kafka_producer"]