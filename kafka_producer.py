"""
KAFKA PRODUCER
Stock Data Streaming from yfinance crawler
Flat JSON schema (compatible with history.json)
"""

import os
import sys
import json
import time
from confluent_kafka import Producer
from datetime import datetime
from crawl_data import CrawlData

# ============================================================================
# CONFIG
# ============================================================================
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stocks-history")
INTERVAL = os.getenv("INTERVAL", "1d")
CRAWL_INTERVAL_SEC = int(os.getenv("CRAWL_INTERVAL_SEC", "3600"))  # daemon mode
TICKERS = os.getenv("TICKERS", "AAPL,NVDA").split(",")

CRAWL_START = os.getenv("CRAWL_START", "2023-01-01")
CRAWL_END = os.getenv("CRAWL_END", "2026-01-01")

# Docker / daemon friendly
sys.stdout = os.fdopen(sys.stdout.fileno(), "w", buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), "w", buffering=1)

# ============================================================================
# KAFKA PRODUCER CLASS
# ============================================================================
class StockKafkaProducer:
    def __init__(self):
        self.producer = Producer({
            "bootstrap.servers": KAFKA_BROKER,
            "client.id": "stock-kafka-producer",
            "linger.ms": 10,
            "compression.type": "lz4",
        })

    @staticmethod
    def delivery_report(err, msg):
        if err:
            print(f"[ERROR] Delivery failed: {err}", flush=True)

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
# STREAMING LOGIC
# ============================================================================
def run_streaming_daemon():
    """
    Crawl data định kỳ và push Kafka
    """
    crawler = CrawlData(interval=INTERVAL)
    producer = StockKafkaProducer()

    print(f"[START] Streaming {TICKERS} every {CRAWL_INTERVAL_SEC}s", flush=True)

    try:
        batch = 0
        while True:
            batch += 1
            start_ts = datetime.utcnow().isoformat()
            sent = 0

            for record in crawler.crawl_many_stream(TICKERS, start=CRAWL_START,end=CRAWL_END):
                # metadata (rất nên có)
                record["ingest_time"] = datetime.utcnow().isoformat()
                record["source"] = "yfinance"

                producer.send(record)
                sent += 1

            producer.flush()
            print(
                f"[BATCH {batch}] {start_ts} | sent={sent}",
                flush=True
            )

            time.sleep(CRAWL_INTERVAL_SEC)

    except KeyboardInterrupt:
        print("[STOP] Interrupted by user", flush=True)
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
    finally:
        producer.flush()
        print("[EXIT] Producer stopped", flush=True)


# ============================================================================
if __name__ == "__main__":
    run_streaming_daemon()
