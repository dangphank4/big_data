"""Batch job: Long-term trend analysis using PySpark"""
import sys
import os
from pyspark.sql import functions as F
from pyspark.sql.window import Window

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from standardization_local import (
    FIELD_TICKER, FIELD_CLOSE, FIELD_TIME,
    FIELD_MA_50, FIELD_MA_100, FIELD_MA_200, FIELD_TREND
)

def batch_long_term_trend(df):
    """
    Sử dụng PySpark Window để tính toán MA50, 100, 200 và phân loại xu hướng.
    """
    # Định nghĩa Window: Chia theo mã (Ticker) và sắp xếp theo thời gian
    window_ma50 = Window.partitionBy(FIELD_TICKER).orderBy(FIELD_TIME).rowsBetween(-49, 0)
    window_ma100 = Window.partitionBy(FIELD_TICKER).orderBy(FIELD_TIME).rowsBetween(-99, 0)
    window_ma200 = Window.partitionBy(FIELD_TICKER).orderBy(FIELD_TIME).rowsBetween(-199, 0)

    # Tính các đường trung bình động (MA)
    df = df.withColumn(FIELD_MA_50, F.avg(F.col(FIELD_CLOSE)).over(window_ma50))
    df = df.withColumn(FIELD_MA_100, F.avg(F.col(FIELD_CLOSE)).over(window_ma100))
    df = df.withColumn(FIELD_MA_200, F.avg(F.col(FIELD_CLOSE)).over(window_ma200))

    # Phân loại xu hướng (Trend)
    df = df.withColumn(FIELD_TREND, 
        F.when(F.col(FIELD_MA_50) > F.col(FIELD_MA_200), "up")
         .when(F.col(FIELD_MA_50) < F.col(FIELD_MA_200), "down")
         .otherwise("sideway")
    )

    # Tính sức mạnh xu hướng
    df = df.withColumn("trend_strength", 
        (F.col(FIELD_MA_50) - F.col(FIELD_MA_200)) / F.col(FIELD_CLOSE)
    )

    return df