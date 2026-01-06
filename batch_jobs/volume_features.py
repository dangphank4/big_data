"""Batch job: Volume features and liquidity analysis"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from standardization_local import FIELD_TICKER, FIELD_VOLUME

# Đo thanh khoản và giao dịch bất thường của cổ phiếu

def batch_volume_features(df):
    df = df.copy()

    df["volume_ma20"] = df.groupby(FIELD_TICKER)[FIELD_VOLUME].transform(
        lambda x: x.rolling(20).mean()
    )

    df["volume_ratio"] = df[FIELD_VOLUME] / df["volume_ma20"]

    return df
