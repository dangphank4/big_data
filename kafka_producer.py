#!/usr/bin/env python3
"""
KAFKA PRODUCER DAEMON - Chạy background được
"""

from confluent_kafka import Producer
import json
import time
import random
from datetime import datetime
import os
import sys

# Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stock-realtime-topic")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "30"))
TICKERS = os.getenv("TICKERS", "AAPL,NVDA").split(",")

# Unbuffered output for daemon mode
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

# Kafka Producer
conf = {
    "bootstrap.servers": KAFKA_BROKER,
    "client.id": "stock-producer-daemon",
    "compression.type": "lz4",
    "linger.ms": 10,
}
producer = Producer(conf)

# Simple callback - no verbose output
def delivery_report(err, msg):
    if err:
        print(f"[ERROR] {datetime.now()}: {err}", flush=True)

def load_latest_prices():
    """Load initial prices"""
    try:
        with open("/app/history_all.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        latest_prices = {}
        for record in data:
            ticker = record["ticker"]
            if ticker in TICKERS:
                if ticker not in latest_prices or record["time"] > latest_prices[ticker]["time"]:
                    latest_prices[ticker] = record
        
        print(f"[INFO] {datetime.now()}: Loaded {len(latest_prices)} tickers", flush=True)
        return latest_prices
    except Exception as e:
        print(f"[ERROR] {datetime.now()}: Cannot load history - {e}", flush=True)
        return {}

def simulate_price_update(last_close):
    """Simulate price movement"""
    change_percent = random.uniform(-2, 2)
    new_price = last_close * (1 + change_percent / 100)
    return round(new_price, 2)

def main():
    print(f"[START] {datetime.now()}: Producer starting...", flush=True)
    print(f"[CONFIG] Broker={KAFKA_BROKER}, Topic={KAFKA_TOPIC}, Interval={UPDATE_INTERVAL}s", flush=True)
    
    # Load initial data
    latest_prices = load_latest_prices()
    if not latest_prices:
        print("[ERROR] No initial data, using defaults", flush=True)
        latest_prices = {
            "AAPL": {"ticker": "AAPL", "company": "Apple Inc.", "Close": 280.0},
            "NVDA": {"ticker": "NVDA", "company": "NVIDIA Corporation", "Close": 185.0}
        }
    
    # Initialize state
    state = {ticker: {"last_close": latest_prices[ticker]["Close"]} for ticker in TICKERS}
    batch_count = 0
    
    print(f"[READY] {datetime.now()}: Starting data stream...", flush=True)
    
    try:
        while True:
            batch_count += 1
            timestamp = datetime.now()
            
            for ticker in TICKERS:
                # Simulate prices
                new_close = simulate_price_update(state[ticker]["last_close"])
                new_open = state[ticker]["last_close"]
                new_high = max(new_close, new_open) * random.uniform(1.0, 1.02)
                new_low = min(new_close, new_open) * random.uniform(0.98, 1.0)
                volume = random.randint(10_000_000, 200_000_000)
                
                # Create message
                message = {
                    "ticker": ticker,
                    "company": latest_prices[ticker].get("company", ticker),
                    "time": timestamp.isoformat(),
                    "Open": round(new_open, 2),
                    "High": round(new_high, 2),
                    "Low": round(new_low, 2),
                    "Close": round(new_close, 2),
                    "Volume": volume
                }
                
                # Send to Kafka
                producer.produce(
                    KAFKA_TOPIC,
                    value=json.dumps(message),
                    callback=delivery_report
                )
                
                # Update state
                state[ticker]["last_close"] = new_close
            
            producer.flush()
            print(f"[BATCH] {datetime.now()}: #{batch_count} sent ({len(TICKERS)} messages)", flush=True)
            time.sleep(UPDATE_INTERVAL)
    
    except KeyboardInterrupt:
        print(f"\n[STOP] {datetime.now()}: Interrupted by user", flush=True)
    except Exception as e:
        print(f"\n[ERROR] {datetime.now()}: {e}", flush=True)
    finally:
        producer.flush()
        print(f"[EXIT] {datetime.now()}: Producer stopped (sent {batch_count} batches)", flush=True)

if __name__ == "__main__":
    main()
