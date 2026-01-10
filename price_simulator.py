"""
PRICE SIMULATOR MODULE
Stateful stock price simulation with realistic volatility and drift
"""

import random


def clamp(value, low, high):
    """Clamp value between low and high bounds."""
    return max(low, min(high, value))


def simulate_next_bar(state):
    """Stateful price simulation with realistic market behavior.

    Args:
        state (dict): Ticker state containing:
            - last_close: float (previous close price)
            - vol: float (% std dev per step)
            - drift: float (% mean per step)

    Returns:
        tuple: (new_close, change_percent, vol)
    """
    last_close = float(state["last_close"])

    # Volatility mean-reversion with random walk
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

    # Update state
    state["vol"] = vol
    state["drift"] = drift
    state["last_close"] = float(round(new_close, 2))
    
    return state["last_close"], change_percent, vol


def initialize_ticker_state(ticker, base_close):
    """Initialize simulation state for a ticker.

    Args:
        ticker (str): Ticker symbol
        base_close (float): Initial close price

    Returns:
        dict: Initial state with last_close, vol, and drift
    """
    return {
        "last_close": base_close,
        "vol": clamp(
            random.uniform(0.8, 1.8) * (1.2 if ticker == "NVDA" else 1.0),
            0.2,
            6.0
        ),
        "drift": random.uniform(-0.02, 0.02),
    }


def generate_ohlc_data(state, vol):
    """Generate OHLC data based on simulation results.

    Args:
        state (dict): Current ticker state
        vol (float): Current volatility

    Returns:
        dict: OHLC data with keys: open, high, low, close
    """
    new_open = state["last_close"]
    new_close, change_percent, _ = simulate_next_bar(state)

    # Intrabar range tied to volatility
    range_pct = abs(random.gauss(0.0, vol * 0.35)) / 100.0
    base_high = max(new_close, new_open)
    base_low = min(new_close, new_open)
    new_high = base_high * (1.0 + range_pct)
    new_low = base_low * (1.0 - range_pct)
    new_low = max(new_low, 0.01)

    return {
        "open": round(new_open, 2),
        "high": round(new_high, 2),
        "low": round(new_low, 2),
        "close": round(new_close, 2),
        "change_percent": change_percent
    }


def generate_volume(vol, change_percent):
    """Generate realistic volume based on volatility and price movement.

    Args:
        vol (float): Current volatility
        change_percent (float): Price change percentage

    Returns:
        int: Simulated volume
    """
    move_mag = abs(change_percent)
    volume_base = random.randint(8_000_000, 120_000_000)
    volume_boost = int(volume_base * (0.3 * (vol / 1.2) + 0.15 * (move_mag / 2.0)))
    volume = int(clamp(volume_base + volume_boost, 1_000_000, 300_000_000))
    return volume
