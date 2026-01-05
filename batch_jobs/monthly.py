# Lợi nhuận theo tháng
def batch_monthly_return(df):
    df = df.copy()
    df["month"] = df["time"].dt.to_period("M")

    monthly = (
        df.groupby(["ticker", "month"])["Close"]
        .agg(["first", "last"])
        .reset_index()
    )

    monthly["monthly_return"] = (
        monthly["last"] - monthly["first"]
    ) / monthly["first"]

    return monthly[["ticker", "month", "monthly_return"]]

#Khối lượng giao dịch theo tháng
def batch_monthly_volatility(df):
    df = df.copy()
    df["month"] = df["time"].dt.to_period("M")

    df["daily_return"] = df.groupby("ticker")["Close"].pct_change()

    vol = (
        df.groupby(["ticker", "month"])["daily_return"]
        .std()
        .reset_index()
        .rename(columns={"daily_return": "monthly_volatility"})
    )

    return vol

