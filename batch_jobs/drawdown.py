# Drawdown + Max drawdown: Mức sụt giảm giá trị cổ phiếu tối đa tính từ đỉnh
def compute_drawdown(close):
    cum_max = close.cummax()
    drawdown = (close - cum_max) / cum_max
    return drawdown

def batch_drawdown(df):
    df = df.copy()

    df["drawdown"] = df.groupby("ticker")["Close"].transform(
        compute_drawdown
    )

    df["max_drawdown"] = df.groupby("ticker")["drawdown"].transform(
        "min"
    )

    return df
