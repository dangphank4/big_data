"""
KAFKA PRODUCER DAEMON
Real-time Stock Data Streaming
Schema compatible with history.json
"""

from confluent_kafka import Producer
import json
import time
import random
from datetime import datetime
import os
import sys
from price_simulator import initialize_ticker_state, simulate_next_bar, generate_volume

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
# MAIN EXECUTION
# ============================================================================
def stream_realtime_mode():
    """Main function to run the Kafka producer in streaming mode."""
    latest_prices = load_latest_prices()
    if not latest_prices:
        print("[ERROR] No initial data, using defaults", flush=True)
        latest_prices = {
            "AAPL": {"ticker": "AAPL", "company": "Apple Inc.", "Close": 280.0},
            "NVDA": {"ticker": "NVDA", "company": "NVIDIA Corporation", "Close": 185.0}
        }
    
    # Initialize simulation state per ticker
    state = {}
    for ticker in TICKERS:
        base_close = float(latest_prices[ticker]["Close"])
        state[ticker] = initialize_ticker_state(ticker, base_close)
    
    print(f"[READY] {datetime.now()}: Starting data stream...", flush=True)
    
    try:
        batch = 0  # Initialize batch counter
        while True:
            batch += 1
            timestamp = datetime.now().astimezone().isoformat()

            for ticker in TICKERS:
                # Simulate next bar using price simulator
                new_open = state[ticker]["last_close"]
                new_close, change_percent, vol = simulate_next_bar(state[ticker])

                # Calculate high/low based on volatility
                range_pct = abs(random.gauss(0.0, vol * 0.35)) / 100.0
                base_high = max(new_close, new_open)
                base_low = min(new_close, new_open)
                new_high = base_high * (1.0 + range_pct)
                new_low = base_low * (1.0 - range_pct)
                new_low = max(new_low, 0.01)
                
                # Generate volume correlated with volatility
                volume = generate_volume(vol, change_percent)
                
                # Create message - UNIFIED SCHEMA
                message = {
                    "ticker": ticker,
                    "company": latest_prices[ticker].get("company", ticker),
                    "time": timestamp,
                    "Open": round(new_open, 2),
                    "High": round(new_high, 2),
                    "Low": round(new_low, 2),
                    "Close": round(new_close, 2),
                    "Adj Close": round(new_close, 2),
                    "Volume": volume
                }

                producer.produce(
                    KAFKA_TOPIC,
                    key=ticker,
                    value=json.dumps(message),
                    callback=delivery_report
                )

            producer.flush()
            print(f"[BATCH {batch}] {timestamp}: Sent {len(TICKERS)} messages", flush=True)
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
