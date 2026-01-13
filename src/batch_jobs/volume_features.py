"""Batch job: Volume features and liquidity analysis using PySpark"""
import sys
import os
from pyspark.sql import functions as F
from pyspark.sql.window import Window

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.standardization_local import FIELD_TICKER, FIELD_VOLUME, FIELD_TIME

def batch_volume_features(df):
    """
    Tính toán trung bình động khối lượng (Volume MA20) và tỷ lệ khối lượng (Volume Ratio).
    """
    # Định nghĩa Window: Phân vùng theo mã cổ phiếu và sắp xếp theo thời gian
    window_volume = Window.partitionBy(FIELD_TICKER).orderBy(FIELD_TIME).rowsBetween(-19, 0)

    # Tính Volume MA20 (Trung bình động khối lượng 20 phiên)
    df = df.withColumn("volume_ma20", F.avg(F.col(FIELD_VOLUME)).over(window_volume))

    # Tính Volume Ratio (Tỷ lệ khối lượng hiện tại so với trung bình)
    df = df.withColumn("volume_ratio", F.col(FIELD_VOLUME) / F.col("volume_ma20"))

    return df