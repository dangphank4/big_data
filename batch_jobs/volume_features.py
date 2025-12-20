# Đo thanh khoản và giao dịch bất thường của cổ phiếu

def batch_volume_features(df):
    df = df.copy()

    df["vol_ma20"] = df.groupby("ticker")["Volume"].transform(
        lambda x: x.rolling(20).mean()
    )

    df["volume_spike"] = df["Volume"] / df["vol_ma20"]

    return df
