"""
KAFKA PRODUCER DAEMON
Real-time Stock Data Simulator
Schema compatible with history.json
"""

from confluent_kafka import Producer
import json
import time
import random
from datetime import datetime
import os
import sys

# ============================================================================
# CONFIGURATION
# ============================================================================
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stocks-history")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "30"))  # seconds
TICKERS = os.getenv("TICKERS", "AAPL,NVDA").split(",")

# Unbuffered stdout/stderr (daemon & Docker friendly)
sys.stdout = os.fdopen(sys.stdout.fileno(), "w", buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), "w", buffering=1)

# ============================================================================
# KAFKA PRODUCER
# ============================================================================
producer = Producer({
    "bootstrap.servers": KAFKA_BROKER,
    "client.id": "stock-producer-daemon",
    "compression.type": "lz4",
    "linger.ms": 10
})

def delivery_report(err, msg):
    if err:
        print(f"[ERROR] Delivery failed: {err}", flush=True)

# ============================================================================
# LOAD HISTORY
# ============================================================================
def load_latest_prices():
    """
    Load latest record per ticker from history.json
    """
    try:
        with open("history.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        latest = {}

        for record in data:
            ticker = record["ticker"]
            if ticker not in TICKERS:
                continue

            record_time = datetime.fromisoformat(record["time"])
            if (
                ticker not in latest
                or record_time > datetime.fromisoformat(latest[ticker]["time"])
            ):
                latest[ticker] = record

        print(f"[INFO] Loaded history for {len(latest)} tickers", flush=True)
        return latest

    except FileNotFoundError:
        print("[WARN] history.json not found – using defaults", flush=True)
        return {}

# ============================================================================
# SIMULATION
# ============================================================================
def simulate_realtime_price(base_price, volatility=0.02):
    pct = random.uniform(-volatility, volatility)

    open_p = base_price
    close_p = base_price * (1 + pct)
    high_p = max(open_p, close_p) * random.uniform(1.0, 1.01)
    low_p = min(open_p, close_p) * random.uniform(0.99, 1.0)

    return {
        "Open": round(open_p, 2),
        "High": round(high_p, 2),
        "Low": round(low_p, 2),
        "Close": round(close_p, 2),
    }

# ============================================================================
# STREAMING
# ============================================================================
def stream_realtime_mode():
    print("=" * 80)
    print(" STARTING REAL-TIME STOCK KAFKA PRODUCER")
    print("=" * 80)
    print(f"Broker  : {KAFKA_BROKER}")
    print(f"Topic   : {KAFKA_TOPIC}")
    print(f"Interval: {UPDATE_INTERVAL}s")
    print(f"Tickers : {TICKERS}")
    print("=" * 80, flush=True)

    latest_prices = load_latest_prices()

    # Fallback defaults
    for t in TICKERS:
        latest_prices.setdefault(t, {
            "ticker": t,
            "company": t,
            "Close": random.uniform(100, 500)
        })

    state = {t: latest_prices[t]["Close"] for t in TICKERS}
    batch = 0

    try:
        while True:
            batch += 1
            timestamp = datetime.now().astimezone().isoformat()

            for ticker in TICKERS:
                price = simulate_realtime_price(state[ticker])

                message = {
                    "ticker": ticker,
                    "company": latest_prices[ticker].get("company", ticker),
                    "time": timestamp,
                    "Open": price["Open"],
                    "High": price["High"],
                    "Low": price["Low"],
                    "Close": price["Close"],
                    "Adj Close": price["Close"],
                    "Volume": int(random.randint(100_000, 5_000_000))
                }

                producer.produce(
                    KAFKA_TOPIC,
                    value=json.dumps(message),
                    callback=delivery_report
                )

                state[ticker] = price["Close"]

            producer.flush()
            print(f"[BATCH {batch}] Sent {len(TICKERS)} messages", flush=True)
            time.sleep(UPDATE_INTERVAL)

    except KeyboardInterrupt:
        print("[STOP] Interrupted by user", flush=True)
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
    finally:
        producer.flush()
        print("[EXIT] Producer stopped", flush=True)

# ============================================================================
if __name__ == "__main__":
    stream_realtime_mode()
