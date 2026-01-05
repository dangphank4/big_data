"""
SPARK STREAMING JOB: SIMPLE REAL-TIME STOCK DATA PROCESSING
===========================================================
Version đơn giản: Chỉ stream dữ liệu cơ bản vào Elasticsearch
Phù hợp với Structured Streaming limitations
"""

import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg,
    col,
    concat_ws,
    count,
    current_timestamp,
    date_format,
    from_json,
    max,
    min,
    round as spark_round,
    stddev,
    sum,
    to_timestamp,
    window,
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
)

# ============================================================================
# CẤU HÌNH
# ============================================================================

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stock-realtime-topic")
ES_NODES = os.getenv("ES_NODES", "elasticsearch")
ES_PORT = os.getenv("ES_PORT", "9200")
ES_INDEX = os.getenv("ES_INDEX", "stock_realtime")
CHECKPOINT_LOCATION = os.getenv("CHECKPOINT_LOCATION", "hdfs://hadoop-namenode:9000/user/spark_checkpoints/stock_realtime")

# Streaming behavior
WATERMARK_DELAY = os.getenv("WATERMARK_DELAY", "1 minute")
WINDOW_DURATION = os.getenv("WINDOW_DURATION", "1 minute")
ENABLE_CONSOLE_SINK = os.getenv("ENABLE_CONSOLE_SINK", "false").lower() in ("1", "true", "yes")
CONSOLE_CHECKPOINT_LOCATION = os.getenv(
    "CONSOLE_CHECKPOINT_LOCATION",
    CHECKPOINT_LOCATION.rstrip("/") + "_console",
)

# ============================================================================
# SCHEMA
# ============================================================================

stock_schema = StructType([
    StructField("ticker", StringType(), True),
    StructField("company", StringType(), True),
    StructField("time", StringType(), True),
    StructField("Open", DoubleType(), True),
    StructField("High", DoubleType(), True),
    StructField("Low", DoubleType(), True),
    StructField("Close", DoubleType(), True),
    StructField("Volume", DoubleType(), True)
])

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("🚀 SPARK STREAMING: SIMPLE STOCK DATA")
    print("=" * 80)
    
    # Tạo Spark Session
    spark = SparkSession.builder \
        .appName("SimpleStockStreaming") \
        .config("spark.sql.streaming.schemaInference", "false") \
        .config("spark.sql.shuffle.partitions", "4") \
        .config("spark.sql.session.timeZone", "UTC") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print(f"\n📡 Kết nối Kafka: {KAFKA_BROKER}")
    print(f"📋 Topic: {KAFKA_TOPIC}")
    print(f"💾 Elasticsearch: {ES_NODES}:{ES_PORT}")
    print(f"📊 Index: {ES_INDEX}\n")
    
    # Đọc từ Kafka (earliest để đọc tất cả messages)
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "earliest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    # Parse JSON
    stock_df = kafka_df.select(
        from_json(col("value").cast("string"), stock_schema).alias("data")
    ).select("data.*")
    
    # Convert ISO timestamp string to timestamp
    stock_df = stock_df.withColumn(
        "timestamp",
        to_timestamp(col("time"))  # Auto-parse ISO 8601 format
    )

    # Basic validation to avoid bad records breaking aggregations
    stock_df = stock_df.filter(
        col("ticker").isNotNull()
        & col("timestamp").isNotNull()
        & col("Close").isNotNull()
    )
    
    # Tính toán các metrics cơ bản sử dụng time window aggregation
    windowed_df = stock_df \
        .withWatermark("timestamp", WATERMARK_DELAY) \
        .groupBy(
            window(col("timestamp"), WINDOW_DURATION),
            col("ticker"),
            col("company")
        ) \
        .agg(
            avg("Close").alias("avg_price"),
            min("Close").alias("min_price"),
            max("Close").alias("max_price"),
            sum("Volume").alias("total_volume"),
            count("*").alias("trade_count"),
            stddev("Close").alias("price_volatility")
        )
    
    # Format lại dữ liệu
    output_df = windowed_df.select(
        col("window.start").alias("window_start"),
        col("window.end").alias("window_end"),
        col("ticker"),
        col("company"),
        spark_round(col("avg_price"), 2).alias("avg_price"),
        spark_round(col("min_price"), 2).alias("min_price"),
        spark_round(col("max_price"), 2).alias("max_price"),
        col("total_volume").cast("long"),
        col("trade_count"),
        spark_round(col("price_volatility"), 2).alias("price_volatility"),
        current_timestamp().alias("processed_time"),
        # Deterministic ES document id to make writes idempotent (no duplicates on restart/replay)
        concat_ws(
            ":",
            col("ticker"),
            date_format(col("window.start"), "yyyyMMddHHmm"),
        ).alias("doc_id"),
    )
    
    # Ghi vào Elasticsearch using foreachBatch (compatible with ES 7.17 + Spark 3.5)
    print("💾 Bắt đầu streaming vào Elasticsearch...")
    
    def write_to_es(batch_df, batch_id):
        if batch_df.take(1):
            record_count = batch_df.count()
            print(f"\n📦 Processing batch {batch_id} with {record_count} records")
            batch_df.write \
                .format("org.elasticsearch.spark.sql") \
                .option("es.resource", ES_INDEX) \
                .option("es.nodes", ES_NODES) \
                .option("es.port", ES_PORT) \
                .option("es.nodes.wan.only", "true") \
                .option("es.batch.size.entries", "100") \
                .option("es.write.operation", "index") \
                .option("es.mapping.id", "doc_id") \
                .mode("append") \
                .save()
            print(f"✅ Batch {batch_id} written to Elasticsearch")
    
    query = output_df.writeStream \
        .outputMode("update") \
        .foreachBatch(write_to_es) \
        .option("checkpointLocation", CHECKPOINT_LOCATION) \
        .start()

    if ENABLE_CONSOLE_SINK:
        output_df.writeStream \
            .outputMode("update") \
            .format("console") \
            .option("truncate", "false") \
            .option("checkpointLocation", CONSOLE_CHECKPOINT_LOCATION) \
            .start()
    
    print("\n" + "=" * 80)
    print("✅ STREAMING JOB ĐANG CHẠY (ForeachBatch mode)")
    print("=" * 80)
    print(f"📊 Dữ liệu được ghi vào: {ES_INDEX}")
    print(f"📈 Window: {WINDOW_DURATION}, Watermark: {WATERMARK_DELAY}\n")
    
    query.awaitTermination()
