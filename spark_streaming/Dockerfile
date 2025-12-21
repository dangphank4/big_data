# Dockerfile for Spark Streaming Jobs
FROM bitnami/spark:3.4

USER root

# Install Python dependencies
RUN pip install --no-cache-dir \
    kafka-python \
    elasticsearch \
    numpy \
    pandas

# Copy spark streaming scripts
COPY spark_streaming_technical_indicators.py /app/
COPY spark_streaming_anomaly_detection.py /app/

WORKDIR /app

# Keep container running
CMD ["tail", "-f", "/dev/null"]
