import os
import sys


# Ensure the src/ directory is importable when this file is executed directly via spark-submit.
_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from batch_jobs.batch_trend import batch_long_term_trend
from batch_jobs.drawdown import batch_drawdown
from batch_jobs.cumulative_return import batch_cumulative_return
from batch_jobs.volume_features import batch_volume_features
from batch_jobs.market_regime import batch_market_regime
from batch_jobs.monthly import batch_monthly_volatility


# ============================================================================
# CONFIG (align with Kafka -> HDFS archiver output)
# ============================================================================
# Kafka -> HDFS Archiver writes NDJSON files under:
#   hdfs://hadoop-namenode:9000/stock-data/YYYY-MM-DD/TICKER.json
HDFS_INPUT_PATH = os.getenv(
    "HDFS_INPUT_PATH",
    "hdfs://hadoop-namenode:9000/stock-data",
)

# Batch features output (Serving layer source-of-truth on HDFS)
HDFS_OUTPUT_PATH = os.getenv(
    "HDFS_OUTPUT_PATH",
    "hdfs://hadoop-namenode:9000/tmp/serving/batch_features",
)

# Elasticsearch (for Kibana)
ES_NODES = os.getenv("ES_NODES", os.getenv("ELASTICSEARCH_HOST", "elasticsearch"))
ES_PORT = os.getenv("ES_PORT", os.getenv("ELASTICSEARCH_PORT", "9200"))
ES_INDEX_BATCH = os.getenv("ES_INDEX_BATCH", "batch-features")


def main():
    spark = (
        SparkSession.builder
        .appName("BigData_Stock_Batch")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )

    print("=== [1] ĐANG LẬP KẾ HOẠCH ĐỌC DỮ LIỆU ===", flush=True)
    df = (
        spark.read
        .option("recursiveFileLookup", "true")
        .json(HDFS_INPUT_PATH)
    )

    if "time" in df.columns:
        df = df.withColumn("time", F.to_timestamp("time"))

    for col_name in ["Open", "High", "Low", "Close", "Volume"]:
        if col_name in df.columns:
            df = df.withColumn(col_name, F.col(col_name).cast("float"))

    print("=== [2] XÂY DỰNG CHUỖI TÍNH TOÁN (TRANSFORMATIONS) ===", flush=True)
    df = batch_long_term_trend(df)
    df = batch_cumulative_return(df)
    df = batch_drawdown(df)
    df = batch_volume_features(df)

    df = df.withColumn("month", F.date_format(F.col("time"), "yyyy-MM"))
    monthly_vol = batch_monthly_volatility(df)
    df = df.join(monthly_vol, on=["ticker", "month"], how="left")
    df = batch_market_regime(df)

    print("=== [3] THỰC THI VÀ ĐẨY DỮ LIỆU (ACTIONS) ===", flush=True)

    try:
        df.write.mode("overwrite").json(HDFS_OUTPUT_PATH)
        print(f"DONE: Đã lưu kết quả phân tán vào HDFS: {HDFS_OUTPUT_PATH}", flush=True)
    except Exception as e:
        print(f"LỖI HDFS: {e}", flush=True)

    df_clean = df.dropna()
    print("Đang đẩy dữ liệu lên Elasticsearch (Serving Layer)...", flush=True)

    df_es = df_clean.withColumn(
        "doc_id",
        F.concat_ws(
            "_",
            F.col("ticker"),
            F.date_format(F.col("time"), "yyyyMMddHHmmss"),
        ),
    )

    (
        df_es.write
        .format("org.elasticsearch.spark.sql")
        .option("es.nodes", ES_NODES)
        .option("es.port", ES_PORT)
        .option("es.resource", f"{ES_INDEX_BATCH}/doc")
        .option("es.mapping.id", "doc_id")
        .option("es.write.operation", "index")
        .mode("append")
        .save()
    )

    print(f"DONE: Đã đẩy dữ liệu lên Elasticsearch index: {ES_INDEX_BATCH}.", flush=True)
    spark.stop()


if __name__ == "__main__":
    main()
