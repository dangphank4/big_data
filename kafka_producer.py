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
    """Simulate next close price.

    Goal: produce more natural/chaotic movements than a fixed +/-2% uniform.
    - time-varying volatility (regimes)
    - heavy-tailed shocks
    - occasional jumps (news-like moves)
    """
    raise NotImplementedError("simulate_price_update is replaced by per-ticker stateful simulation")


def clamp(value, low, high):
    return max(low, min(high, value))


def simulate_next_bar(state):
    """Stateful price simulation.

    state keys:
      - last_close: float
      - vol: float (% std dev per step)
      - drift: float (% mean per step)
    """
    last_close = float(state["last_close"])

    # Volatility mean-reversion with random walk (keeps things lively but bounded)
    vol = float(state.get("vol", 1.2))
    drift = float(state.get("drift", 0.0))

    target_vol = 1.2
    vol = vol + 0.15 * (target_vol - vol) + random.gauss(0.0, 0.15)
    vol = clamp(vol, 0.2, 6.0)

    # Small drift that slowly wanders
    drift = drift + random.gauss(0.0, 0.01)
    drift = clamp(drift, -0.08, 0.08)

    # Heavy-tailed shock via mixture distribution
    base_move = random.gauss(0.0, vol)
    if random.random() < 0.12:
        base_move += random.gauss(0.0, vol * 2.5)

    # Occasional jump (news event)
    jump = 0.0
    if random.random() < 0.04:
        jump = random.gauss(0.0, vol * 4.0)

    change_percent = drift + base_move + jump
    change_percent = clamp(change_percent, -18.0, 18.0)

    new_close = last_close * (1.0 + change_percent / 100.0)
    new_close = max(new_close, 0.01)

    state["vol"] = vol
    state["drift"] = drift
    state["last_close"] = float(round(new_close, 2))
    return state["last_close"], change_percent, vol

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
    
    # Initialize state (per-ticker volatility/drift so each ticker behaves differently)
    state = {}
    for ticker in TICKERS:
        base_close = float(latest_prices[ticker]["Close"])
        state[ticker] = {
            "last_close": base_close,
            # Different initial vol by ticker; later evolves dynamically
            "vol": clamp(random.uniform(0.8, 1.8) * (1.2 if ticker == "NVDA" else 1.0), 0.2, 6.0),
            "drift": random.uniform(-0.02, 0.02),
        }
    batch_count = 0
    
    print(f"[READY] {datetime.now()}: Starting data stream...", flush=True)
    
    try:
        while True:
            batch_count += 1
            timestamp = datetime.now()
            
            for ticker in TICKERS:
                # Simulate prices (stateful + chaotic)
                new_open = state[ticker]["last_close"]
                new_close, change_percent, vol = simulate_next_bar(state[ticker])

                # Intrabar range tied to volatility (creates more realistic high/low spread)
                range_pct = abs(random.gauss(0.0, vol * 0.35)) / 100.0
                base_high = max(new_close, new_open)
                base_low = min(new_close, new_open)
                new_high = base_high * (1.0 + range_pct)
                new_low = base_low * (1.0 - range_pct)
                new_low = max(new_low, 0.01)

                # Volume loosely correlated with volatility and move size
                move_mag = abs(change_percent)
                volume_base = random.randint(8_000_000, 120_000_000)
                volume_boost = int(volume_base * (0.3 * (vol / 1.2) + 0.15 * (move_mag / 2.0)))
                volume = int(clamp(volume_base + volume_boost, 1_000_000, 300_000_000))
                
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
                    key=ticker,
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
