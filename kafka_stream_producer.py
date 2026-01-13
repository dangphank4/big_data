"""
KAFKA STREAM PRODUCER
Real-time Stock Data Streaming from yfinance crawler
Fetches data every minute interval
"""

import os
import sys
import json
import time
from confluent_kafka import Producer
from datetime import datetime, timedelta
from crawl_data import CrawlData

# ============================================================================
# CONFIG
# ============================================================================
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_STREAM_TOPIC", "stream_topic")
INTERVAL = os.getenv("INTERVAL", "1m")  # 1 minute interval
CRAWL_INTERVAL_SEC = int(os.getenv("CRAWL_INTERVAL_SEC", "60"))  # 60 seconds = 1 minute
TICKERS = os.getenv("TICKERS", "AAPL,NVDA").split(",")

# Docker / daemon friendly
sys.stdout = os.fdopen(sys.stdout.fileno(), "w", buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), "w", buffering=1)

# ============================================================================
# KAFKA PRODUCER CLASS
# ============================================================================
class StreamKafkaProducer:
    def __init__(self):
        self.producer = Producer({
            "bootstrap.servers": KAFKA_BROKER,
            "client.id": "stream-kafka-producer",
            "linger.ms": 10,
            "compression.type": "lz4",
        })

    @staticmethod
    def delivery_report(err, msg):
        if err:
            print(f"[ERROR] Delivery failed: {err}", flush=True)
        else:
            print(f"[SUCCESS] Message sent to {msg.topic()} [{msg.partition()}]", flush=True)

    def send(self, record: dict):
        self.producer.produce(
            topic=KAFKA_TOPIC,
            key=record["ticker"],
            value=json.dumps(record, ensure_ascii=False),
            callback=self.delivery_report
        )

    def flush(self):
        self.producer.flush()


# ============================================================================
# STREAMING LOGIC - Real-time by minute
# ============================================================================
def run_stream_producer():
    """
    Crawl data từ crawl_data theo phút (1m interval)
    và push tới Kafka stream_topic
    """
    crawler = CrawlData(interval=INTERVAL)
    producer = StreamKafkaProducer()

    print(f"[START] Stream producing {TICKERS} every {CRAWL_INTERVAL_SEC}s to topic '{KAFKA_TOPIC}'", flush=True)

    try:
        batch = 0
        while True:
            batch += 1
            start_ts = datetime.utcnow().isoformat()
            sent = 0

            # Calculate time window: last minute
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=1)

            # Crawl data for the last minute
            for record in crawler.crawl_many_stream(
                TICKERS,
                start=start_time.strftime("%Y-%m-%d %H:%M"),
                end=end_time.strftime("%Y-%m-%d %H:%M")
            ):
                # Add metadata
                record["ingest_time"] = datetime.utcnow().isoformat()
                record["source"] = "yfinance"
                record["stream_type"] = "realtime"

                producer.send(record)
                sent += 1

            producer.flush()
            print(
                f"[BATCH {batch}] {start_ts} | sent={sent} records",
                flush=True
            )

            # Wait for next minute
            time.sleep(CRAWL_INTERVAL_SEC)

    except KeyboardInterrupt:
        print("[STOP] Interrupted by user", flush=True)
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        producer.flush()
        print("[EXIT] Stream producer stopped", flush=True)


# ============================================================================
if __name__ == "__main__":
    run_stream_producer()
