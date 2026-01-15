"""
SPARK STRUCTURED STREAMING - STOCK REALTIME METRICS
Unified schema with batch processing pipeline
Uses utils.standardization_local for schema consistency
"""

import os
import sys
import time

# Add parent directory to path so we can import from src/utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, window, avg, min, max, sum, count,
    stddev, current_timestamp, to_timestamp, date_format, concat_ws, coalesce
)

# Import unified schema from standardization module
from utils.standardization_local import get_spark_schema, STOCK_FIELDS

# ============================================================================
# CONFIGURATION
# ============================================================================
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stocks-realtime-spark")

ES_NODES = os.getenv("ES_NODES", os.getenv("ELASTICSEARCH_HOST", "elasticsearch"))
ES_PORT = os.getenv("ES_PORT", os.getenv("ELASTICSEARCH_PORT", "9200"))

# This job is meant to create the "metrics" index for Kibana.
ES_INDEX = os.getenv("ES_INDEX", "stock-realtime-1m")

# Use local checkpoint by default (works in Docker/K8s). Override if you want HDFS.
CHECKPOINT_LOCATION = os.getenv(
    "CHECKPOINT_LOCATION",
    "/tmp/spark-checkpoints/stock-realtime-1m",
)

WINDOW_DURATION = os.getenv("WINDOW_DURATION", "1 minute")
WATERMARK_DELAY = os.getenv("WATERMARK_DELAY", "2 minutes")
TRIGGER_INTERVAL = os.getenv("TRIGGER_INTERVAL", "30 seconds")

# ============================================================================
# SPARK SESSION
# ============================================================================
def create_spark_session():
    """Create Spark session with Kafka and Elasticsearch dependencies"""
    return SparkSession.builder \
        .appName("StockRealtimeStreaming") \
        .config("spark.jars.packages", 
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.3,"
                "org.elasticsearch:elasticsearch-spark-30_2.12:7.17.16") \
        .config("spark.sql.shuffle.partitions", "4") \
        .config("spark.sql.streaming.minBatchesToRetain", "2") \
        .config("spark.streaming.stopGracefullyOnShutdown", "true") \
        .getOrCreate()

# ============================================================================
# STREAMING PIPELINE
# ============================================================================
def run_streaming():
    """Main streaming pipeline"""
    
    print(f"[INFO] Starting Spark Streaming Job")
    print(f"[INFO] Kafka: {KAFKA_BROKER}, Topic: {KAFKA_TOPIC}")
    print(f"[INFO] Elasticsearch: {ES_NODES}:{ES_PORT}, Index: {ES_INDEX}")
    print(f"[INFO] Checkpoint: {CHECKPOINT_LOCATION}")
    print(f"[INFO] Using unified schema from utils.standardization_local")
    print(f"[INFO] Schema fields: {', '.join(STOCK_FIELDS)}")
    
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    # Get unified schema from standardization module
    stock_schema = get_spark_schema()
    
    # Read from Kafka
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    # Parse JSON with unified schema
    parsed_df = kafka_df.select(
        from_json(col("value").cast("string"), stock_schema).alias("data")
    ).select("data.*")
    
    # Convert time to timestamp
    parsed_df = (
        parsed_df
        .withColumn(
            "source_time",
            coalesce(
                to_timestamp(col("time"), "yyyy-MM-dd HH:mm:ssXXX"),
                to_timestamp(col("time")),
            ),
        )
        # Use processing time for windowing so append mode can emit regularly.
        .withColumn("event_time", current_timestamp())
    )
    
    # Apply watermark
    watermarked_df = parsed_df.withWatermark("event_time", WATERMARK_DELAY)
    
    # Time window aggregation
    windowed_df = watermarked_df.groupBy(
        window(col("event_time"), WINDOW_DURATION),
        col("ticker"),
        col("company")
    ).agg(
        avg("Close").alias("avg_price"),
        min("Low").alias("min_price"),
        max("High").alias("max_price"),
        sum("Volume").alias("total_volume"),
        count("*").alias("trade_count"),
        stddev("Close").alias("price_volatility"),
        max("source_time").alias("source_time"),
    )
    
    # Format output - Keep @timestamp as actual timestamp type for Kibana recognition
    output_df = windowed_df.select(
        col("window.start").alias("@timestamp"),  # Keep as TIMESTAMP for Kibana time field
        col("window.start").alias("window_start"),  # Also keep as timestamp type
        col("window.end").alias("window_end"),      # Also keep as timestamp type
        col("ticker"),
        col("company"),
        col("avg_price"),
        col("min_price"),
        col("max_price"),
        col("total_volume"),
        col("trade_count"),
        col("price_volatility"),
        col("source_time"),
        current_timestamp().alias("processed_time"),  # Keep as timestamp type
        concat_ws("_", col("ticker"), date_format(col("window.start"), "yyyyMMddHHmm")).alias("doc_id"),
    )
    
    # Start streaming with retry to avoid cold-start races (topic not created yet)
    startup_retry_seconds = int(os.getenv("STARTUP_RETRY_SECONDS", "5"))
    startup_max_retries = int(os.getenv("STARTUP_MAX_RETRIES", "60"))

    last_error = None
    for attempt in range(1, startup_max_retries + 1):
        try:
            query = output_df.writeStream \
                .outputMode("append") \
                .format("org.elasticsearch.spark.sql") \
                .option("es.nodes", ES_NODES) \
                .option("es.port", ES_PORT) \
                .option("es.resource", f"{ES_INDEX}/_doc") \
                .option("es.mapping.id", "doc_id") \
                .option("checkpointLocation", CHECKPOINT_LOCATION) \
                .trigger(processingTime=TRIGGER_INTERVAL) \
                .start()
            break
        except Exception as e:
            last_error = e
            msg = str(e)
            if "UnknownTopicOrPartitionException" in msg or "UnknownTopicOrPartition" in msg:
                print(
                    f"[WARN] Kafka topic not ready yet (attempt {attempt}/{startup_max_retries}). "
                    f"Retrying in {startup_retry_seconds}s..."
                )
                time.sleep(startup_retry_seconds)
                continue
            raise
    else:
        raise RuntimeError(
            f"Failed to start streaming after {startup_max_retries} attempts; last error: {last_error}"
        )
    
    print(f"[INFO] Streaming query started. Writing to {ES_INDEX}")
    print(f"[INFO] Query ID: {query.id}")
    
    # Wait for termination
    query.awaitTermination()

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    try:
        run_streaming()
    except KeyboardInterrupt:
        print("\n[INFO] Streaming job interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Streaming job failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)