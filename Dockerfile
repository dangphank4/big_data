FROM python:3.12-slim

WORKDIR /app

# Copy code
COPY kafka_producer.py kafka_consumer.py /app/
COPY batch_jobs/ /app/batch/
COPY history.json /app/data/
# Copy mã Python
COPY kafka_producer.py kafka_consumer.py history.json /app/

# Cài dependencies
RUN pip install --no-cache-dir \
    pandas \
    numpy \
    confluent-kafka \
    hdfs \
    elasticsearch

# Tạo thư mục output
RUN mkdir -p /app/output

CMD ["python", "batch/run_all.py"]