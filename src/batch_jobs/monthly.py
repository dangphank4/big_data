"""Batch job: Monthly returns and volatility using PySpark"""
import sys
import os
from pyspark.sql import functions as F
from pyspark.sql.window import Window

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.standardization_local import FIELD_TICKER, FIELD_TIME, FIELD_CLOSE, FIELD_MONTHLY_VOLATILITY

# Lợi nhuận theo tháng
def batch_monthly_return(df):
    """
    Tính lợi nhuận hàng tháng dựa trên giá đóng cửa đầu tiên và cuối cùng của tháng.
    """
    # Tạo cột tháng (định dạng yyyy-MM)
    df = df.withColumn("month", F.date_format(F.col(FIELD_TIME), "yyyy-MM"))
    
    # Định nghĩa Window để lấy giá đầu và giá cuối của mỗi tháng
    window_spec = Window.partitionBy(FIELD_TICKER, "month").orderBy(FIELD_TIME)
    
    # Lấy giá đầu tiên và giá cuối cùng trong tháng bằng Window function
    df_prices = df.withColumn("first_price", F.first(F.col(FIELD_CLOSE)).over(window_spec)) \
                  .withColumn("last_price", F.last(F.col(FIELD_CLOSE)).over(window_spec.rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)))
    
    # Gom nhóm theo tháng và lấy kết quả
    monthly = df_prices.groupBy(FIELD_TICKER, "month").agg(
        F.first("first_price").alias("first"),
        F.first("last_price").alias("last")
    )
    
    # Tính lợi nhuận: (Last - First) / First
    monthly = monthly.withColumn("monthly_return", (F.col("last") - F.col("first")) / F.col("first"))
    
    return monthly.select(FIELD_TICKER, "month", "monthly_return")

# Độ biến động theo tháng (Volatility)
def batch_monthly_volatility(df):
    """
    Tính độ biến động hàng tháng dựa trên độ lệch chuẩn của lợi nhuận hàng ngày.
    """
    # Định nghĩa Window để tính daily return
    window_ticker = Window.partitionBy(FIELD_TICKER).orderBy(FIELD_TIME)
    
    # Tính lợi nhuận hàng ngày bằng hàm lag
    df = df.withColumn("prev_close", F.lag(F.col(FIELD_CLOSE)).over(window_ticker))
    df = df.withColumn("daily_return", (F.col(FIELD_CLOSE) - F.col("prev_close")) / F.col("prev_close"))
    
    # Tạo cột tháng
    df = df.withColumn("month", F.date_format(F.col(FIELD_TIME), "yyyy-MM"))
    
    # Tính độ lệch chuẩn (stddev) theo từng tháng
    vol = df.groupBy(FIELD_TICKER, "month").agg(
        F.stddev(F.col("daily_return")).alias(FIELD_MONTHLY_VOLATILITY)
    )
    
    return vol