import json
import time
import logging
import signal
import sys
from datetime import datetime

from confluent_kafka import Consumer, KafkaException
from hdfs import InsecureClient

# ============================================================================
# LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - PID:%(process)d - %(message)s"
)
log = logging.getLogger("kafka-hdfs-consumer")

# ============================================================================
# CONFIG
# ============================================================================
KAFKA_BROKER_URL = "kafka:9092"
KAFKA_TOPIC = "stocks-history"
KAFKA_GROUP_ID = "hdfs-writer-group-v1"

HDFS_URL = "http://hadoop-namenode:9870"
HDFS_USER = "root"
HDFS_BASE_PATH = "/user/kafka_data/stocks_history"

BATCH_SIZE = 100
BATCH_INTERVAL_SECONDS = 60
POLL_TIMEOUT = 1.0
RETRY_DELAY = 10

# ============================================================================
# GLOBAL STATE
# ============================================================================
running = True
consumer = None
hdfs_client = None

# ============================================================================
# SIGNAL HANDLING
# ============================================================================
def shutdown_handler(signum, frame):
    global running
    log.warning(f"Received signal {signum} → shutting down gracefully")
    running = False

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# ============================================================================
# HDFS WRITE
# ============================================================================
def write_batch_to_hdfs(client, base_path, records):
    if not records:
        return True

    try:
        now = datetime.now()
        path = now.strftime("%Y/%m/%d/%H")
        target_dir = f"{base_path}/{path}"

        filename = f"data_{now.strftime('%H%M%S%f')}.jsonl"
        full_path = f"{target_dir}/{filename}"

        client.makedirs(target_dir)

        payload = "\n".join(
            json.dumps(r, ensure_ascii=False) for r in records
        )

        with client.write(full_path, encoding="utf-8") as writer:
            writer.write(payload)

        log.info(f"HDFS WRITE OK: {len(records)} records → {full_path}")
        return True

    except Exception as e:
        log.error("HDFS WRITE FAILED", exc_info=True)
        return False

# ============================================================================
# CONSUME LOOP
# ============================================================================
def consume_loop():
    global consumer, hdfs_client

    batch = []
    last_flush = time.time()

    log.info("Consumer started")

    while running:
        msg = consumer.poll(POLL_TIMEOUT)

        if msg is None:
            time.sleep(0.1)
            continue

        if msg.error():
            log.error(f"Kafka error: {msg.error()}")
            continue

        try:
            record = json.loads(msg.value().decode("utf-8"))
        except Exception:
            log.error("Invalid JSON message")
            continue

        batch.append(record)
        now = time.time()

        if (
            len(batch) >= BATCH_SIZE
            or now - last_flush >= BATCH_INTERVAL_SECONDS
        ):
            ok = write_batch_to_hdfs(hdfs_client, HDFS_BASE_PATH, batch)
            if ok:
                consumer.commit(asynchronous=False)
                batch.clear()
                last_flush = now
            else:
                raise RuntimeError("HDFS write failed")

    # FLUSH LAST BATCH
    if batch:
        log.info("Flushing remaining batch before exit")
        if write_batch_to_hdfs(hdfs_client, HDFS_BASE_PATH, batch):
            consumer.commit(asynchronous=False)

# ============================================================================
# MAIN – AUTO RESTART
# ============================================================================
if __name__ == "__main__":
    while True:
        try:
            # HDFS CONNECT
            hdfs_client = InsecureClient(HDFS_URL, user=HDFS_USER)
            hdfs_client.makedirs(HDFS_BASE_PATH)
            log.info("HDFS CONNECTED")

            # KAFKA CONNECT
            consumer = Consumer({
                "bootstrap.servers": KAFKA_BROKER_URL,
                "group.id": KAFKA_GROUP_ID,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False
            })

            consumer.subscribe([KAFKA_TOPIC])
            log.info("Kafka CONNECTED")

            consume_loop()

        except Exception:
            log.error("SESSION ERROR", exc_info=True)

        finally:
            try:
                if consumer:
                    consumer.close()
            except Exception:
                pass

            if not running:
                log.info("Consumer shutdown completed")
                sys.exit(0)

            log.warning(f"Restarting session in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
