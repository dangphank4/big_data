"""Batch job: Cumulative and rolling returns"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from standardization_local import FIELD_TICKER, FIELD_CLOSE

# Cumulative return + Rolling return: Lợi nhuận theo nhóm ngày (đo hiệu suất sinh lời)
# Return = (Close(t) - Close(t-1))/Close(t-1)


def batch_cumulative_return(df):
    df = df.copy()

    # hàng ngày
    df["daily_return"] = df.groupby(FIELD_TICKER)[FIELD_CLOSE].pct_change()

    # từ ngày đầu -> hiện tại
    df["cumulative_return"] = df.groupby(FIELD_TICKER)["daily_return"].transform(
        lambda x: (1 + x).cumprod() - 1
    )

    # 30 ngày
    df["return_30d"] = df.groupby(FIELD_TICKER)[FIELD_CLOSE].transform(
        lambda x: x.pct_change(30)
    )

    # 90 ngày
    df["return_90d"] = df.groupby(FIELD_TICKER)[FIELD_CLOSE].transform(
        lambda x: x.pct_change(90)
    )

    return df
