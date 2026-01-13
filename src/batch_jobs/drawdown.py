"""Batch job: Drawdown analysis using PySpark"""
import sys
import os
from pyspark.sql import functions as F
from pyspark.sql.window import Window

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.standardization_local import FIELD_TICKER, FIELD_CLOSE, FIELD_TIME, FIELD_DRAWDOWN

def batch_drawdown(df):
    """
    Tính toán mức sụt giảm (Drawdown) từ đỉnh và mức sụt giảm tối đa (Max Drawdown).
    """
    # Cửa sổ từ đầu dữ liệu đến dòng hiện tại để tính giá trị cao nhất (CumMax)
    window_cummax = Window.partitionBy(FIELD_TICKER)\
                          .orderBy(FIELD_TIME)\
                          .rowsBetween(Window.unboundedPreceding, 0)
    
    #  Cửa sổ toàn bộ dữ liệu của ticker để tìm giá trị nhỏ nhất (Max Drawdown)
    window_ticker = Window.partitionBy(FIELD_TICKER)

    # Tính CumMax (Đỉnh cao nhất tính đến thời điểm hiện tại)

    df = df.withColumn("cum_max", F.max(F.col(FIELD_CLOSE)).over(window_cummax))

    # Tính Drawdown
    df = df.withColumn(FIELD_DRAWDOWN, (F.col(FIELD_CLOSE) - F.col("cum_max")) / F.col("cum_max"))

    #  Tính Max Drawdown (Giá trị nhỏ nhất của cột Drawdown cho mỗi mã)
    df = df.withColumn("max_drawdown", F.min(F.col(FIELD_DRAWDOWN)).over(window_ticker))

    # Loại bỏ cột phụ cum_max trước khi trả về
    return df.drop("cum_max")