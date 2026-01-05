# Phân loại thị trường, cổ phiếu

def batch_market_regime(df):
    df = df.copy()

    df["market_regime"] = "sideway"

    df.loc[
        (df["ma50"] > df["ma200"]) & (df["monthly_volatility"] < 0.02),
        "market_regime"
    ] = "bull"

    df.loc[df["ma50"] < df["ma200"], "market_regime"] = "bear"

    return df
