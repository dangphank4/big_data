# Cumulative return + Rolling return: Lợi nhuận theo nhóm ngày (đo hiệu suất sinh lời)
# Return = (Close(t) - Close(t-1))/Close(t-1)


def batch_cumulative_return(df):
    df = df.copy()

    # hàng ngày
    df["daily_return"] = df.groupby("ticker")["Close"].pct_change()

    # từ ngày đầu -> hiện tại
    # df["cum_return"] = (
    #     1 + df.groupby("ticker")["daily_return"]
    # ).cumprod() - 1

# Fix
    df["cum_return"] = df.groupby("ticker")["daily_return"].transform(lambda x: (1 + x).cumprod() - 1)
# Fix
    # 30 ngày
    df["return_30d"] = df.groupby("ticker")["Close"].transform(
        lambda x: x.pct_change(30)
    )

    # 90 ngày
    df["return_90d"] = df.groupby("ticker")["Close"].transform(
        lambda x: x.pct_change(90)
    )

    return df
