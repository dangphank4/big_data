"""
KAFKA PRODUCER: STOCK MARKET DATA STREAMING
============================================
Gửi dữ liệu cổ phiếu real-time vào Kafka topic

Features:
- Load historical data để simulate realtime
- Continuous streaming với timestamp update
- Random price fluctuations để simulate market
- Support multiple tickers
"""

from confluent_kafka import Producer
import json
import time
import random
from datetime import datetime, timedelta
import os

# ============================================================================
# CONFIGURATION
# ============================================================================

# Kafka Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stock-realtime-topic")  

# Streaming Configuration
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "30"))  # seconds

# Tickers to monitor
TICKERS = os.getenv("TICKERS", "AAPL,NVDA").split(",")

# ============================================================================
# KAFKA PRODUCER SETUP
# ============================================================================

conf = {
    "bootstrap.servers": KAFKA_BROKER,
    "client.id": "stock-producer",
    "compression.type": "lz4",  # Compression để giảm bandwidth
    "linger.ms": 10,  # Batch messages
}

producer = Producer(conf)

def delivery_report(err, msg):
    """Callback khi message được gửi thành công hoặc fail"""
    if err:
        print(f" Delivery failed: {err}")
    else:
        print(f" Sent to {msg.topic()} [{msg.partition()}] @ {msg.offset()}")

# ============================================================================
# DATA SIMULATION FUNCTIONS
# ============================================================================

def load_latest_prices():
    """Load giá gần nhất từ history để làm base"""
    try:
        with open("history_all.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Lấy giá gần nhất của mỗi ticker
        latest_prices = {}
        for record in data:
            ticker = record["ticker"]
            if ticker in TICKERS:
                if ticker not in latest_prices:
                    latest_prices[ticker] = record
                else:
                    # Update nếu có ngày mới hơn
                    if record["time"] > latest_prices[ticker]["time"]:
                        latest_prices[ticker] = record
        
        print(f" Loaded latest prices for {len(latest_prices)} tickers")
        return latest_prices
    
    except FileNotFoundError:
        print(" history_all.json not found, using default prices")
        # Default prices nếu không có file
        return {
            "AAPL": {"Close": 180.0, "Volume": 50000000},
            "NVDA": {"Close": 500.0, "Volume": 40000000},
        }

def simulate_realtime_price(base_price, volatility=0.02):
    """
    Simulate biến động giá real-time
    
    Args:
        base_price: Giá hiện tại
        volatility: Mức độ biến động (default 2%)
    
    Returns:
        dict with Open, High, Low, Close prices
    """
    # Random walk: giá có thể lên hoặc xuống
    price_change_pct = random.uniform(-volatility, volatility)
    
    open_price = base_price
    close_price = base_price * (1 + price_change_pct)
    
    # High/Low based on volatility
    high_price = max(open_price, close_price) * (1 + random.uniform(0, volatility/2))
    low_price = min(open_price, close_price) * (1 - random.uniform(0, volatility/2))
    
    return {
        "Open": round(open_price, 2),
        "High": round(high_price, 2),
        "Low": round(low_price, 2),
        "Close": round(close_price, 2)
    }

def simulate_volume(base_volume, volatility=0.3):
    """Simulate volume với biến động"""
    volume_change = random.uniform(-volatility, volatility)
    new_volume = base_volume * (1 + volume_change)
    return int(max(1000000, new_volume))  # Min 1M volume

# ============================================================================
# STREAMING MODES
# ============================================================================

def stream_realtime_mode():
    """
    Real-time Stock Data Streaming
    ==============================
    Liên tục generate dữ liệu cổ phiếu mới với timestamp hiện tại
    để feed vào Spark Streaming jobs (Technical Indicators & Anomaly Detection)
    """
    print("\n" + "="*80)
    print(" STARTING REAL-TIME STREAMING MODE")
    print("="*80)
    print(f" Kafka Broker: {KAFKA_BROKER}")
    print(f" Topic: {KAFKA_TOPIC}")
    print(f" Update Interval: {UPDATE_INTERVAL}s")
    print(f" Tickers: {', '.join(TICKERS)}")
    print("="*80 + "\n")
    
    # Load base prices
    latest_prices = load_latest_prices()
    
    # Current state for each ticker
    current_state = {}
    for ticker in TICKERS:
        if ticker in latest_prices:
            current_state[ticker] = {
                "company": latest_prices[ticker].get("company", f"{ticker} Corp"),
                "last_close": latest_prices[ticker]["Close"],
                "base_volume": latest_prices[ticker]["Volume"]
            }
        else:
            # Default nếu không có trong history
            current_state[ticker] = {
                "company": f"{ticker} Corp",
                "last_close": 100.0,
                "base_volume": 10000000
            }
    
    print(" Starting prices:")
    for ticker, state in current_state.items():
        print(f"  {ticker}: ${state['last_close']:.2f}")
    print()
    
    # Streaming loop
    message_count = 0
    try:
        while True:
            timestamp = datetime.now().isoformat()
            
            for ticker in TICKERS:
                state = current_state[ticker]
                
                # Simulate new prices based on last close
                prices = simulate_realtime_price(state["last_close"], volatility=0.02)
                volume = simulate_volume(state["base_volume"], volatility=0.3)
                
                # Create message
                message = {
                    "ticker": ticker,
                    "company": state["company"],
                    "time": timestamp,
                    "Open": prices["Open"],
                    "High": prices["High"],
                    "Low": prices["Low"],
                    "Close": prices["Close"],
                    "Volume": volume
                }
                
                # Send to Kafka
                producer.produce(
                    KAFKA_TOPIC,
                    key=ticker.encode('utf-8'),  # Partition by ticker
                    value=json.dumps(message).encode('utf-8'),
                    callback=delivery_report
                )
                producer.poll(0)
                
                # Update state
                state["last_close"] = prices["Close"]
                
                message_count += 1
                
                # Display
                price_change = ((prices["Close"] - prices["Open"]) / prices["Open"]) * 100
                arrow = "🟢" if price_change >= 0 else "🔴"
                print(f"{arrow} {ticker:6s} | ${prices['Close']:8.2f} | {price_change:+6.2f}% | Vol: {volume:,}")
            
            print(f"\n Batch #{message_count//len(TICKERS)} sent. Waiting {UPDATE_INTERVAL}s...\n")
            producer.flush()
            time.sleep(UPDATE_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\n Interrupted by user")
    finally:
        producer.flush()
        print(f"\n Sent total {message_count} messages")
        print(" Producer stopped")

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Start real-time streaming để Spark Streaming xử lý"""
    stream_realtime_mode()

if __name__ == "__main__":
    main()
