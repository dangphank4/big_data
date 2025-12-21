"""
SPARK STREAMING JOB: SIMPLE REAL-TIME STOCK DATA PROCESSING
===========================================================
Version đơn giản: Chỉ stream dữ liệu cơ bản vào Elasticsearch
Phù hợp với Structured Streaming limitations
"""

import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, window, avg, stddev, sum, count,
    min, max, lit, expr, unix_timestamp,
    to_timestamp, current_timestamp, round as spark_round
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    TimestampType
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
    
    # Tính toán các metrics cơ bản sử dụng time window aggregation
    windowed_df = stock_df \
        .withWatermark("timestamp", "1 minute") \
        .groupBy(
            window(col("timestamp"), "30 seconds"),
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
        current_timestamp().alias("processed_time")
    )
    
    # Ghi vào Elasticsearch using foreachBatch (compatible with ES 7.17 + Spark 3.5)
    print("💾 Bắt đầu streaming vào Elasticsearch...")
    
    def write_to_es(batch_df, batch_id):
        if batch_df.count() > 0:
            print(f"\n📦 Processing batch {batch_id} with {batch_df.count()} records")
            batch_df.write \
                .format("org.elasticsearch.spark.sql") \
                .option("es.resource", ES_INDEX) \
                .option("es.nodes", ES_NODES) \
                .option("es.port", ES_PORT) \
                .option("es.nodes.wan.only", "true") \
                .option("es.batch.size.entries", "100") \
                .option("es.write.operation", "index") \
                .mode("append") \
                .save()
            print(f"✅ Batch {batch_id} written to Elasticsearch")
    
    query = output_df.writeStream \
        .outputMode("append") \
        .foreachBatch(write_to_es) \
        .option("checkpointLocation", CHECKPOINT_LOCATION) \
        .start()
    
    # Console output
    console_query = output_df.writeStream \
        .outputMode("append") \
        .format("console") \
        .option("truncate", "false") \
        .start()
    
    print("\n" + "=" * 80)
    print("✅ STREAMING JOB ĐANG CHẠY (ForeachBatch mode)")
    print("=" * 80)
    print(f"📊 Dữ liệu được ghi vào: {ES_INDEX}")
    print("📈 Window: 30 giây, Watermark: 1 phút\n")
    
    query.awaitTermination()
