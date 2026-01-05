import json
import time
import logging
import signal
from datetime import datetime

from confluent_kafka import Consumer, KafkaException
from hdfs import InsecureClient
from hdfs.util import HdfsError

# LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - PID:%(process)d - %(message)s'
)
log = logging.getLogger(__name__)

# CONFIG
KAFKA_BROKER_URL = "kafka:9092"
KAFKA_TOPIC = 'stocks-history'
KAFKA_GROUP_ID = 'hdfs-writer-group-final-v1'

HDFS_URL = "http://hadoop-namenode:9870"
HDFS_USER = 'root'
HDFS_BASE_PATH = '/user/kafka_data/real_estate_by_date'

BATCH_SIZE = 100
BATCH_INTERVAL_SECONDS = 60

hdfs_client = None
consumer = None
hdfs_ready = False


# GHI FILE MỚI VÀO HDFS THEO NGÀY
def write_data_to_new_hdfs_file(current_hdfs_client, base_path, batch_data):
    global hdfs_ready, hdfs_client

    if not batch_data:
        log.info("BATCH EMPTY → Không ghi.")
        return True

    try:
        now = datetime.now()
        date_path = now.strftime('%Y/%m/%d')
        target_dir = f"{base_path}/{date_path}"

        filename = f"data_{now.strftime('%H%M%S%f')}.jsonl"
        full_path = f"{target_dir}/{filename}"

        current_hdfs_client.makedirs(target_dir)

        data_string = "\n".join(json.dumps(r, ensure_ascii=False) for r in batch_data)

        with current_hdfs_client.write(full_path, encoding="utf-8") as w:
            w.write(data_string)

        log.info(f"WRITE SUCCESS: {len(batch_data)} records → {full_path}")
        return True

    except Exception as e:
        log.error(f"HDFS ERROR: {e}", exc_info=True)
        hdfs_ready = False
        hdfs_client = None
        return False


# VÒNG LẶP CONSUME
def consume_and_write():
    global consumer, hdfs_client, hdfs_ready

    batch = []
    last_write = time.time()

    log.info("Consumer READY → Listening Kafka...")

    while True:
        msg = consumer.poll(1.0)

        if msg is None:
            continue

        if msg.error():
            log.error(f"Kafka error: {msg.error()}")
            continue

        try:
            record = json.loads(msg.value().decode("utf-8"))
        except Exception:
            log.error("JSON decode error")
            continue

        batch.append(record)

        now = time.time()

        if len(batch) >= BATCH_SIZE or (now - last_write >= BATCH_INTERVAL_SECONDS):
            ok = write_data_to_new_hdfs_file(hdfs_client, HDFS_BASE_PATH, batch)
            if ok:
                batch = []
                last_write = now
            else:
                log.error("WRITE FAIL → Exit session")
                return


# =========================================================
# MAIN LOOP – AUTO RETRY
# =========================================================
if __name__ == "__main__":
    retry_delay = 10

    while True:
        # HDFS CONNECT
        try:
            hdfs_client = InsecureClient(HDFS_URL, user=HDFS_USER)
            hdfs_client.makedirs(HDFS_BASE_PATH)
            hdfs_ready = True
            log.info("HDFS CONNECTED")
        except Exception as e:
            log.error(f"Cannot connect HDFS: {e}")
            time.sleep(retry_delay)
            continue

        # KAFKA CONNECT
        settings = {
            "bootstrap.servers": KAFKA_BROKER_URL,
            "group.id": KAFKA_GROUP_ID,
            "auto.offset.reset": "earliest"
        }

        try:
            consumer = Consumer(settings)
            consumer.subscribe([KAFKA_TOPIC])
            log.info("Kafka CONNECTED")
        except KafkaException as e:
            log.error(f"Cannot connect Kafka: {e}")
            time.sleep(retry_delay)
            continue

        # START SESSION
        try:
            consume_and_write()
        except Exception as e:
            log.error("Fatal consumer error", exc_info=True)

        consumer.close()
        log.warning("Restarting session...")
        time.sleep(retry_delay)