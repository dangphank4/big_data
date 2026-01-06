"""Batch job: Market regime classification"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from standardization_local import FIELD_MA_50, FIELD_MA_200, FIELD_MONTHLY_VOLATILITY

# Phân loại thị trường, cổ phiếu

def batch_market_regime(df):
    df = df.copy()

    df["market_regime"] = "normal"

    df.loc[
        (df[FIELD_MA_50] > df[FIELD_MA_200]) & (df[FIELD_MONTHLY_VOLATILITY] < 0.02),
        "market_regime"
    ] = "bull"

    df.loc[
        (df[FIELD_MA_50] < df[FIELD_MA_200]) & (df[FIELD_MONTHLY_VOLATILITY] > 0.03),
        "market_regime"
    ] = "bear"
    
    df.loc[
        df[FIELD_MONTHLY_VOLATILITY] > 0.05,
        "market_regime"
    ] = "high_vol"

    return df
