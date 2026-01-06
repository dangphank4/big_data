FROM python:3.12-slim

WORKDIR /app

# Copy dependency manifest first for better layer caching
COPY requirements.txt /app/

# Copy code
COPY kafka_producer.py kafka_consumer.py standardization_local.py unified_runner.py run_all.py /app/
COPY batch_jobs/ /app/batch_jobs/
COPY history.json /app/

# Install dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Tạo thư mục output
RUN mkdir -p /app/output

# Keep container running (use docker exec to run batch jobs manually)
CMD ["tail", "-f", "/dev/null"]