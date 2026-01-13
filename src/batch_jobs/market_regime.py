"""Batch job: Market regime classification using PySpark"""
import sys
import os
from pyspark.sql import functions as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.standardization_local import FIELD_MA_50, FIELD_MA_200, FIELD_MONTHLY_VOLATILITY

def batch_market_regime(df):
    """
    Phân loại trạng thái thị trường dựa trên các đường MA và độ biến động.
    """
    df = df.withColumn("market_regime", 
        F.when(
            (F.col(FIELD_MA_50) > F.col(FIELD_MA_200)) & 
            (F.col(FIELD_MONTHLY_VOLATILITY) < 0.02), 
            "bull"
        )
        .when(
            (F.col(FIELD_MA_50) < F.col(FIELD_MA_200)) & 
            (F.col(FIELD_MONTHLY_VOLATILITY) > 0.03), 
            "bear"
        )
        .when(
            F.col(FIELD_MONTHLY_VOLATILITY) > 0.05, 
            "high_vol"
        )
        .otherwise("normal")
    )

    return df