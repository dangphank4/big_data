# Xu hướng giá
# Trend = up/down/sideway

# ma20 - ma50
# def batch_trend(df):
#     df = df.copy()

#     df["ma20"] = df.groupby("ticker")["Close"].transform(
#         lambda x: x.rolling(20).mean()
#     )

#     df["ma50"] = df.groupby("ticker")["Close"].transform(
#         lambda x: x.rolling(50).mean()
#     )

#     df["trend"] = "sideway"
#     df.loc[df["ma20"] > df["ma50"], "trend"] = "up"
#     df.loc[df["ma20"] < df["ma50"], "trend"] = "down"

#     return df[["ticker", "time", "ma20", "ma50", "trend"]]

#ma50 - ma200 + strength (long term)
def batch_long_term_trend(df):
    df = df.copy()

    for w in [50, 100, 200]:
        df[f"ma{w}"] = df.groupby("ticker")["Close"].transform(
            lambda x: x.rolling(w).mean()
        )

    df["trend"] = "sideway"
    df.loc[df["ma50"] > df["ma200"], "trend"] = "up"
    df.loc[df["ma50"] < df["ma200"], "trend"] = "down"

    df["trend_strength"] = (df["ma50"] - df["ma200"]) / df["Close"]

    return df
