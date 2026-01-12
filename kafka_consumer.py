"""
KAFKA CONSUMER → HDFS WRITER
Consumes flat stock JSON records and writes to HDFS (JSONL)
"""

import json
import time
import logging
import signal
import sys
from datetime import datetime
from typing import List

from confluent_kafka import Consumer
from hdfs import InsecureClient

# ============================================================================
# LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | PID:%(process)d | %(message)s"
)
log = logging.getLogger("kafka-hdfs-consumer")

# ============================================================================
# CONFIG
# ============================================================================
KAFKA_BROKER = "kafka:9092"
KAFKA_TOPIC = "stocks-history"
KAFKA_GROUP_ID = "hdfs-writer-v1"

HDFS_URL = "http://hadoop-namenode:9870"
HDFS_USER = "root"
HDFS_BASE_PATH = "/data/stock/history"

POLL_TIMEOUT = 1.0
BATCH_SIZE = 200
BATCH_INTERVAL_SEC = 60
RETRY_DELAY = 10

# ============================================================================
running = True
consumer = None
hdfs_client = None


# ============================================================================
# SIGNAL HANDLING
# ============================================================================
def shutdown_handler(signum, frame):
    global running
    log.warning(f"Signal {signum} received → shutdown requested")
    running = False


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# ============================================================================
# HDFS WRITE
# ============================================================================
def write_batch_to_hdfs(
    client: InsecureClient,
    base_path: str,
    records: List[dict]
) -> bool:
    if not records:
        return True

    try:
        now = datetime.utcnow()

        # Partitioned path: date=YYYY-MM-DD/hour=HH
        dir_path = (
            f"{base_path}/"
            f"date={now.strftime('%Y-%m-%d')}/"
            f"hour={now.strftime('%H')}"
        )

        filename = f"part-{now.strftime('%Y%m%d%H%M%S%f')}.jsonl"
        full_path = f"{dir_path}/{filename}"

        client.makedirs(dir_path)

        payload = "\n".join(
            json.dumps(r, ensure_ascii=False) for r in records
        )

        with client.write(full_path, encoding="utf-8") as writer:
            writer.write(payload)

        log.info(f"HDFS WRITE OK | {len(records)} records → {full_path}")
        return True

    except Exception:
        log.exception("HDFS WRITE FAILED")
        return False


# ============================================================================
# CONSUME LOOP
# ============================================================================
def consume_loop():
    global consumer, hdfs_client

    buffer = []
    last_flush = time.time()

    log.info("Consume loop started")

    while running:
        msg = consumer.poll(POLL_TIMEOUT)

        if msg is None:
            time.sleep(0.05)
            continue

        if msg.error():
            log.error(f"Kafka error: {msg.error()}")
            continue

        try:
            record = json.loads(msg.value().decode("utf-8"))
        except Exception:
            log.error("Invalid JSON message – skipped")
            continue

        buffer.append(record)
        now = time.time()

        if (
            len(buffer) >= BATCH_SIZE
            or now - last_flush >= BATCH_INTERVAL_SEC
        ):
            if write_batch_to_hdfs(hdfs_client, HDFS_BASE_PATH, buffer):
                consumer.commit(asynchronous=False)
                buffer.clear()
                last_flush = now
            else:
                raise RuntimeError("HDFS write failed")

    # graceful shutdown flush
    if buffer:
        log.info("Flushing remaining messages before shutdown")
        if write_batch_to_hdfs(hdfs_client, HDFS_BASE_PATH, buffer):
            consumer.commit(asynchronous=False)


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    while True:
        try:
            # HDFS
            hdfs_client = InsecureClient(HDFS_URL, user=HDFS_USER)
            hdfs_client.makedirs(HDFS_BASE_PATH)
            log.info("HDFS connected")

            # Kafka
            consumer = Consumer({
                "bootstrap.servers": KAFKA_BROKER,
                "group.id": KAFKA_GROUP_ID,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False
            })

            consumer.subscribe([KAFKA_TOPIC])
            log.info("Kafka connected – start consuming")

            consume_loop()

        except Exception:
            log.exception("Consumer session error")

        finally:
            try:
                if consumer:
                    consumer.close()
            except Exception:
                pass

            if not running:
                log.info("Consumer shutdown completed")
                sys.exit(0)

            log.warning(f"Restarting in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
