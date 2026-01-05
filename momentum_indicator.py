# Động lượng
# Indicator: RSI14 (quá mua/quá bán), MACD (động lượng xu hướng), momentum (close-close)

def compute_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1+rs))
    return rsi

def batch_momentum(df):
    df = df.copy()

    df["rsi14"] = df.groupby("ticker")["Close"].transform(
        lambda x: compute_rsi(x, 14)
    )

    df["momentum_10"] = df.groupby("ticker")["Close"].transform(
        lambda x: x - x.shift(10)
    )

    return df[["ticker", "time", "rsi14", "momentum_10"]]