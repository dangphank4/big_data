import os
import sys
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from batch_jobs.batch_trend import batch_long_term_trend
from batch_jobs.drawdown import batch_drawdown
from batch_jobs.cumulative_return import batch_cumulative_return
from batch_jobs.volume_features import batch_volume_features
from batch_jobs.market_regime import batch_market_regime
from batch_jobs.monthly import batch_monthly_volatility

def main():
    #Khởi tạo SparkSession
    spark = SparkSession.builder \
        .appName("BigData_Stock_Batch") \
        .config("spark.sql.session.timeZone", "UTC") \
        .getOrCreate()

    print("=== [1] ĐANG LẬP KẾ HOẠCH ĐỌC DỮ LIỆU ===")
    # Đọc history.json. Spark chưa đọc ngay, nó chỉ kiểm tra cấu trúc file (Lazy Evaluation)
    df_batch = spark.read.json("hdfs://hadoop-namenode:9000/tmp/serving/batch_features")

    # Chuẩn hóa cột thời gian và ép kiểu (Spark tự tối ưu hóa kiểu số)
    if "time" in df.columns:
        df = df.withColumn("time", F.to_timestamp("time"))
    
    for col_name in ["Open", "High", "Low", "Close", "Volume"]:
        if col_name in df.columns:
            df = df.withColumn(col_name, F.col(col_name).cast("float"))

    print("=== [2] XÂY DỰNG CHUỖI TÍNH TOÁN (TRANSFORMATIONS) ===")
    # DataFrame cũ không mất đi, mỗi hàm tạo ra một "phiên bản" mới có thêm cột
    df = batch_long_term_trend(df)
    df = batch_cumulative_return(df)
    df = batch_drawdown(df)
    df = batch_volume_features(df)

    # Xử lý logic hàng tháng bằng Join phân tán
    # Tạo cột month dùng chung
    df = df.withColumn("month", F.date_format(F.col("time"), "yyyy-MM"))
    
    # Tính Volatility (một nhánh tính toán riêng)
    monthly_vol = batch_monthly_volatility(df)
    
    # Gộp lại bằng Join
    df = df.join(monthly_vol, on=["ticker", "month"], how="left")
    
    # Phân loại thị trường sau khi đã có đủ các cột đặc trưng
    df = batch_market_regime(df)

    print("=== [3] THỰC THI VÀ ĐẨY DỮ LIỆU (ACTIONS) ===")
    
    # Đẩy lên HDFS - Lúc này Spark mới thực sự chạy MapReduce để tính toán
    hdfs_path = "hdfs://hadoop-namenode:9000/tmp/serving/batch_features"
    try:
        # Ghi đè (overwrite) kết quả vào HDFS dưới dạng JSON phân tán
        df.write.mode("overwrite").json(hdfs_path)
        print(f"DONE: Đã lưu kết quả phân tán vào HDFS: {hdfs_path}")
    except Exception as e:
        print(f"LỖI HDFS: {e}")

    # Đẩy lên Elasticsearch (Serving Layer)
    # Lấy dữ liệu sạch (không NaN)
    df_clean = df.dropna()

    print("Đang chuẩn bị dữ liệu cho Elasticsearch...")
    pdf = df_clean.toPandas() 
    
    from elasticsearch import Elasticsearch, helpers
    es = Elasticsearch([f"http://{os.getenv('ELASTICSEARCH_HOST', 'elasticsearch')}:9200"])
    
    actions = [
        {
            "_index": "batch-features",
            "_source": {k: (str(v) if "month" in k or "time" in k else v) for k, v in row.items()}
        }
        for _, row in pdf.iterrows()
    ]
    
    helpers.bulk(es, actions)
    print(f"DONE: Đã đẩy {len(actions)} bản ghi lên Elasticsearch.")

    spark.stop()

if __name__ == "__main__":
    main()