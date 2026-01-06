"""Batch job: Monthly returns and volatility"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from standardization_local import FIELD_TICKER, FIELD_TIME, FIELD_CLOSE, FIELD_MONTHLY_VOLATILITY

# Lợi nhuận theo tháng
def batch_monthly_return(df):
    df = df.copy()
    df["month"] = df[FIELD_TIME].dt.to_period("M")

    monthly = (
        df.groupby([FIELD_TICKER, "month"])[FIELD_CLOSE]
        .agg(["first", "last"])
        .reset_index()
    )

    monthly["monthly_return"] = (
        monthly["last"] - monthly["first"]
    ) / monthly["first"]

    return monthly[[FIELD_TICKER, "month", "monthly_return"]]

#Khối lượng giao dịch theo tháng (volatility)
def batch_monthly_volatility(df):
    df = df.copy()
    df[FIELD_TIME] = pd.to_datetime(df[FIELD_TIME]) 
    df["month"] = df[FIELD_TIME].dt.to_period("M")

    df["daily_return"] = df.groupby(FIELD_TICKER)[FIELD_CLOSE].pct_change()

    vol = (
        df.groupby([FIELD_TICKER, "month"])["daily_return"]
        .std()
        .reset_index()
        .rename(columns={"daily_return": FIELD_MONTHLY_VOLATILITY})
    )

    return vol

