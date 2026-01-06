"""Batch job: Long-term trend analysis"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from standardization_local import (
    FIELD_TICKER, FIELD_CLOSE, 
    FIELD_MA_50, FIELD_MA_100, FIELD_MA_200, FIELD_TREND
)

# Xu hướng giá
# Trend = up/down/sideway

#ma50 - ma200 + strength (long term)
def batch_long_term_trend(df):
    df = df.copy()

    for w in [50, 100, 200]:
        df[f"ma{w}"] = df.groupby(FIELD_TICKER)[FIELD_CLOSE].transform(
            lambda x: x.rolling(w).mean()
        )

    df[FIELD_TREND] = "sideway"
    df.loc[df[FIELD_MA_50] > df[FIELD_MA_200], FIELD_TREND] = "up"
    df.loc[df[FIELD_MA_50] < df[FIELD_MA_200], FIELD_TREND] = "down"

    df["trend_strength"] = (df[FIELD_MA_50] - df[FIELD_MA_200]) / df[FIELD_CLOSE]

    return df
