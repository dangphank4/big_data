"""
KAFKA PRODUCER - REAL-TIME CRAWLING MODE
Crawls stock data every minute and streams to Kafka
Single source of truth for all downstream consumers
"""

import os
import sys
import json
import time
from confluent_kafka import Producer
from datetime import datetime, timedelta
from ..utils.crawl_data import CrawlData

# ============================================================================
# CONFIG
# ============================================================================
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stocks-realtime")
CRAWL_INTERVAL = int(os.getenv("CRAWL_INTERVAL", "60"))  # seconds (1 minute)
TICKERS = os.getenv("TICKERS", "AAPL,NVDA,TSLA,MSFT,GOOGL").split(",")

# Unbuffered output for Docker
sys.stdout = os.fdopen(sys.stdout.fileno(), "w", buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), "w", buffering=1)


# ============================================================================
# KAFKA PRODUCER
# ============================================================================
class StockProducerCrawl:
    def __init__(self):
        self.producer = Producer({
            "bootstrap.servers": KAFKA_BROKER,
            "client.id": "stock-crawl-producer",
            "linger.ms": 10,
            "compression.type": "lz4",
        })
        self.crawler = CrawlData(interval="1m")  # Minute bars

    def send(self, record: dict):
        """Send record to Kafka"""
        self.producer.produce(
            topic=KAFKA_TOPIC,
            key=record["ticker"],
            value=json.dumps(record, ensure_ascii=False),
            callback=lambda err, msg: print(f"[ERROR] {err}", flush=True) if err else None
        )

    def flush(self):
        """Flush pending messages"""
        self.producer.flush()

    def crawl_and_stream(self):
        """Main loop: crawl real data every minute and stream to Kafka"""
        print(f"[START] Real-time crawling for {len(TICKERS)} tickers every {CRAWL_INTERVAL}s", flush=True)
        
        batch_count = 0
        while True:
            try:
                batch_count += 1
                start_time = datetime.now()
                
                # Calculate time range for last minute
                end = datetime.now()
                start = end - timedelta(minutes=2)  # Get last 2 minutes to ensure data
                
                records_sent = 0
                for ticker in TICKERS:
                    try:
                        # Crawl minute data
                        records = self.crawler.crawl_ticker(
                            ticker=ticker,
                            start=start.strftime("%Y-%m-%d %H:%M"),
                            end=end.strftime("%Y-%m-%d %H:%M")
                        )
                        
                        # Send to Kafka
                        for record in records:
                            self.send(record)
                            records_sent += 1
                        
                    except Exception as e:
                        print(f"[ERROR] {ticker}: {e}", flush=True)
                        continue
                
                self.flush()
                
                elapsed = (datetime.now() - start_time).total_seconds()
                print(
                    f"[BATCH {batch_count}] {datetime.now().isoformat()} | "
                    f"{records_sent} records | {elapsed:.2f}s",
                    flush=True
                )
                
                # Sleep until next interval
                sleep_time = max(0, CRAWL_INTERVAL - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                print("[STOP] Shutting down...", flush=True)
                break
            except Exception as e:
                print(f"[ERROR] Main loop: {e}", flush=True)
                time.sleep(10)  # Wait before retry


# ============================================================================
# MAIN
# ============================================================================
def main():
    producer = StockProducerCrawl()
    producer.crawl_and_stream()


if __name__ == "__main__":
    main()
