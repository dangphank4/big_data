"""Batch job: Cumulative and rolling returns using PySpark"""
import sys
import os
from pyspark.sql import functions as F
from pyspark.sql.window import Window

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.standardization_local import FIELD_TICKER, FIELD_CLOSE, FIELD_TIME

def batch_cumulative_return(df):
    """
    Tính toán lợi nhuận hàng ngày, lũy kế và lợi nhuận theo chu kỳ 30/90 ngày.
    """
    # window_spec: dùng để so sánh với các dòng phía trước
    window_spec = Window.partitionBy(FIELD_TICKER).orderBy(FIELD_TIME)
    
    # window_first: dùng để lấy giá trị đầu tiên của mỗi mã chứng khoán (tính cumulative)
    window_first = Window.partitionBy(FIELD_TICKER).orderBy(FIELD_TIME).rowsBetween(Window.unboundedPreceding, 0)

    # Tính lợi nhuận hàng ngày (Daily Return)
    df = df.withColumn("prev_close", F.lag(F.col(FIELD_CLOSE), 1).over(window_spec))
    df = df.withColumn("daily_return", (F.col(FIELD_CLOSE) - F.col("prev_close")) / F.col("prev_close"))

    # Tính lợi nhuận lũy kế (Cumulative Return)
    df = df.withColumn("first_close", F.first(F.col(FIELD_CLOSE)).over(window_first))
    df = df.withColumn("cumulative_return", (F.col(FIELD_CLOSE) / F.col("first_close")) - 1)

    # Tính lợi nhuận 30 ngày (Rolling 30d Return)
    df = df.withColumn("close_30d_ago", F.lag(F.col(FIELD_CLOSE), 30).over(window_spec))
    df = df.withColumn("return_30d", (F.col(FIELD_CLOSE) - F.col("close_30d_ago")) / F.col("close_30d_ago"))

    # Tính lợi nhuận 90 ngày (Rolling 90d Return)
    df = df.withColumn("close_90d_ago", F.lag(F.col(FIELD_CLOSE), 90).over(window_spec))
    df = df.withColumn("return_90d", (F.col(FIELD_CLOSE) - F.col("close_90d_ago")) / F.col("close_90d_ago"))

    # Loại bỏ các cột phụ tạm thời trước khi trả về
    return df.drop("prev_close", "first_close", "close_30d_ago", "close_90d_ago")