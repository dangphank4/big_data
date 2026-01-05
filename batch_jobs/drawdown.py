"""Batch job: Drawdown analysis"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from standardization_local import FIELD_TICKER, FIELD_CLOSE, FIELD_DRAWDOWN

# Drawdown + Max drawdown: Mức sụt giảm giá trị cổ phiếu tối đa tính từ đỉnh
def compute_drawdown(close):
    cum_max = close.cummax()
    drawdown = (close - cum_max) / cum_max
    return drawdown

def batch_drawdown(df):
    df = df.copy()

    df[FIELD_DRAWDOWN] = df.groupby(FIELD_TICKER)[FIELD_CLOSE].transform(
        compute_drawdown
    )

    df["max_drawdown"] = df.groupby(FIELD_TICKER)[FIELD_DRAWDOWN].transform(
        "min"
    )

    return df
