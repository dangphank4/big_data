FROM python:3.12-slim

WORKDIR /app

# Copy code
COPY kafka_producer.py kafka_consumer.py standardization_local.py unified_runner.py run_all.py /app/
COPY batch_jobs/ /app/batch_jobs/
COPY history.json /app/

# Cài dependencies
RUN pip install --no-cache-dir \
    pandas \
    numpy \
    confluent-kafka \
    hdfs \
    elasticsearch

# Tạo thư mục output
RUN mkdir -p /app/output

# Keep container running (use docker exec to run batch jobs manually)
CMD ["tail", "-f", "/dev/null"]