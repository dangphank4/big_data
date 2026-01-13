"""Spark Structured Streaming (simple) + 1-minute abnormal-move alerts.

Flow:
Kafka (minute bars) -> Spark Streaming -> Elasticsearch (for Kibana)

Alert definition (default):
- Compute 1-minute OHLCV per ticker (using event-time window)
- Raise alert when absolute 1-minute return exceeds a threshold

-> alert sẽ xuất hiện khi giá tăng/giảm ≥ 1% hoặc biên độ dao động ≥ 1.5% trong 1 phút.
"""

import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.functions import from_json, col, window
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType


# ============================================================================
# CONFIG
# ============================================================================
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stocks-realtime-spark")

ES_NODES = os.getenv("ES_NODES", os.getenv("ELASTICSEARCH_HOST", "elasticsearch"))
ES_PORT = os.getenv("ES_PORT", os.getenv("ELASTICSEARCH_PORT", "9200"))
ES_ALERT_INDEX = os.getenv("ES_ALERT_INDEX", "stock-alerts-1m")

CHECKPOINT_LOCATION = os.getenv(
    "CHECKPOINT_LOCATION",
    os.getenv("CHECKPOINT_DIR", "/tmp/spark-streaming-simple-checkpoint"),
)

ALERT_RETURN_PCT_THRESHOLD = float(os.getenv("ALERT_RETURN_PCT_THRESHOLD", "0.01"))  # 1%
ALERT_RANGE_PCT_THRESHOLD = float(os.getenv("ALERT_RANGE_PCT_THRESHOLD", "0.015"))   # 1.5%


SCHEMA = StructType([
    StructField("ticker", StringType(), True),
    StructField("company", StringType(), True),
    StructField("time", StringType(), True),
    StructField("Open", DoubleType(), True),
    StructField("High", DoubleType(), True),
    StructField("Low", DoubleType(), True),
    StructField("Close", DoubleType(), True),
    StructField("Adj Close", DoubleType(), True),
    StructField("Volume", LongType(), True),
])


def main():
    spark = (
        SparkSession.builder
        .appName("SparkStreamingSimpleWithAlerts")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.streaming.stopGracefullyOnShutdown", "true")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    print(f"[START] spark_streaming_simple | topic={KAFKA_TOPIC} | es={ES_NODES}:{ES_PORT}", flush=True)
    print(
        f"[ALERT] return>={ALERT_RETURN_PCT_THRESHOLD:.4f} or range>={ALERT_RANGE_PCT_THRESHOLD:.4f}",
        flush=True,
    )

    df_raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BROKER)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "latest")
        .load()
    )

    df = (
        df_raw.select(from_json(col("value").cast("string"), SCHEMA).alias("data"))
        .select("data.*")
        .withColumn("timestamp", F.to_timestamp("time"))
        .where(F.col("ticker").isNotNull() & F.col("timestamp").isNotNull())
    )

    # 1-minute OHLCV per ticker (event-time window)
    # Use min/max(struct(ts, value)) to get deterministic open/close within window.
    df_1m = (
        df.withWatermark("timestamp", "2 minutes")
        .groupBy(window(col("timestamp"), "1 minute"), col("ticker"))
        .agg(
            F.min(F.struct(col("timestamp").alias("ts"), col("Open").alias("open"))).alias("open_struct"),
            F.max(F.struct(col("timestamp").alias("ts"), col("Close").alias("close"))).alias("close_struct"),
            F.max(col("High")).alias("high_1m"),
            F.min(col("Low")).alias("low_1m"),
            F.sum(col("Volume")).alias("volume_sum_1m"),
        )
        .select(
            col("ticker"),
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("open_struct.open").alias("open_1m"),
            col("close_struct.close").alias("close_1m"),
            col("high_1m"),
            col("low_1m"),
            col("volume_sum_1m"),
        )
        .withColumn(
            "return_pct_1m",
            F.when(col("open_1m") > 0, (col("close_1m") - col("open_1m")) / col("open_1m")).otherwise(F.lit(None)),
        )
        .withColumn(
            "range_pct_1m",
            F.when(col("open_1m") > 0, (col("high_1m") - col("low_1m")) / col("open_1m")).otherwise(F.lit(None)),
        )
    )

    df_alerts = (
        df_1m
        .withColumn(
            "alert_reason",
            F.when(F.abs(col("return_pct_1m")) >= F.lit(ALERT_RETURN_PCT_THRESHOLD), F.lit("return_pct"))
             .when(col("range_pct_1m") >= F.lit(ALERT_RANGE_PCT_THRESHOLD), F.lit("range_pct"))
             .otherwise(F.lit(None)),
        )
        .where(col("alert_reason").isNotNull())
        .withColumn(
            "direction",
            F.when(col("return_pct_1m") >= 0, F.lit("up")).otherwise(F.lit("down")),
        )
        .withColumn(
            "alert_score",
            F.when(col("alert_reason") == "return_pct", F.abs(col("return_pct_1m"))).otherwise(col("range_pct_1m")),
        )
        .withColumn(
            "doc_id",
            F.concat_ws(
                "_",
                col("ticker"),
                F.date_format(col("window_start"), "yyyyMMddHHmm"),
                col("alert_reason"),
                col("direction"),
            ),
        )
    )

    query_alerts = (
        df_alerts.writeStream
        .outputMode("append")
        .format("org.elasticsearch.spark.sql")
        .option("es.nodes", ES_NODES)
        .option("es.port", ES_PORT)
        .option("es.resource", f"{ES_ALERT_INDEX}/doc")
        .option("es.mapping.id", "doc_id")
        .option("es.write.operation", "index")
        .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/alerts")
        .start()
    )

    # Optional: console preview
    _ = (
        df_alerts.select(
            "ticker",
            "window_start",
            "open_1m",
            "close_1m",
            "return_pct_1m",
            "range_pct_1m",
            "alert_reason",
            "direction",
            "alert_score",
        )
        .writeStream
        .outputMode("append")
        .format("console")
        .option("truncate", "false")
        .option("numRows", "10")
        .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/console")
        .start()
    )

    print(f"[READY] Alerts streaming started -> ES index: {ES_ALERT_INDEX}", flush=True)
    query_alerts.awaitTermination()


if __name__ == "__main__":
    main()