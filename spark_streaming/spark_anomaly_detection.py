"""
SPARK STRUCTURED STREAMING - PRICE ANOMALY DETECTION
Real-time detection of abnormal price movements in stock data
Uses statistical methods appropriate for financial data
"""

import os
import sys
import time

# Add parent directory to path to import standardization_local
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, window, avg, min, max, sum, count,
    stddev, current_timestamp, to_timestamp, abs as spark_abs,
    when, lit, expr
)
from pyspark.sql.window import Window

# Import unified schema from standardization module
from standardization_local import get_spark_schema, STOCK_FIELDS

# ============================================================================
# CONFIGURATION
# ============================================================================
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stocks-history")
ES_NODES = os.getenv("ES_NODES", "elasticsearch")
ES_PORT = os.getenv("ES_PORT", "9200")
ES_INDEX = os.getenv("ES_INDEX_ANOMALY", "stock_anomalies")
CHECKPOINT_LOCATION = os.getenv("CHECKPOINT_LOCATION_ANOMALY", "hdfs://hadoop-namenode:9000/user/spark_checkpoints/stock_anomaly")

WINDOW_DURATION = "30 seconds"
WATERMARK_DELAY = "1 minute"
TRIGGER_INTERVAL = "30 seconds"

# Anomaly Detection Thresholds (tuned for stock market)
# NOTE: These thresholds are calibrated for 30-second windows with simulated data
# 
# FOR REAL-TIME CRAWL (1 data point per minute):
# - Adjust window to match data frequency: WINDOW_DURATION = "1 minute" or "2 minutes"
# - For 1-minute windows, consider adjusting thresholds:
#   * PRICE_CHANGE_THRESHOLD = 0.03-0.04 (3-4%, tighter since more data points)
#   * VOLUME_SPIKE_THRESHOLD = 2.5-3.0 (similar, volume patterns stable)
#   * VOLATILITY_THRESHOLD = 0.02-0.03 (2-3%, adjust based on market)
#   * PRICE_GAP_THRESHOLD = 0.015-0.02 (1.5-2%, tighter for minute data)
#
# REASON: With minute-level crawl:
# - More granular data → can detect smaller anomalies
# - Less aggregation → price changes more realistic
# - Need to avoid false positives from normal intraday volatility
PRICE_CHANGE_THRESHOLD = 0.05  # 5% price change in 30s = suspicious
VOLUME_SPIKE_THRESHOLD = 3.0    # 3x average volume = spike
VOLATILITY_THRESHOLD = 0.03     # 3% volatility in 30s = high
PRICE_GAP_THRESHOLD = 0.02      # 2% gap between trades = suspicious

# ============================================================================
# SPARK SESSION
# ============================================================================
def create_spark_session():
    """Create Spark session with Kafka and Elasticsearch dependencies"""
    return SparkSession.builder \
        .appName("StockAnomalyDetection") \
        .config("spark.jars.packages", 
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.3,"
                "org.elasticsearch:elasticsearch-spark-30_2.12:7.17.16") \
        .config("spark.sql.shuffle.partitions", "4") \
        .config("spark.sql.streaming.minBatchesToRetain", "2") \
        .config("spark.streaming.stopGracefullyOnShutdown", "true") \
        .getOrCreate()

# ============================================================================
# ANOMALY DETECTION LOGIC
# ============================================================================
def detect_anomalies(windowed_df):
    """
    Detect various types of anomalies in stock data:
    1. Price Spike Up: Sudden large price increase (>threshold)
    2. Price Spike Down: Sudden large price decrease (>threshold)
    3. Volume Spike: Unusually high trading volume (>3x avg)
    4. High Volatility: High price variance within window
    5. Price Gap: Large gap between max and min prices
    
    Notes:
    - Uses rolling window of last 5 windows for baseline
    - Thresholds are tuned for 30s-60s windows
    - For different frequencies, adjust thresholds accordingly
    """
    
    # Define window for historical comparison (last 5 windows per ticker)
    ticker_window = Window.partitionBy("ticker").orderBy("window_start").rowsBetween(-5, -1)
    
    # Calculate historical averages
    df_with_history = windowed_df.withColumn(
        "historical_avg_price",
        avg("avg_price").over(ticker_window)
    ).withColumn(
        "historical_avg_volume",
        avg("total_volume").over(ticker_window)
    ).withColumn(
        "historical_volatility",
        avg("price_volatility").over(ticker_window)
    )
    
    # Calculate anomaly indicators
    anomaly_df = df_with_history.withColumn(
        # 1. Price change percentage (with direction)
        "price_change_pct",
        when(col("historical_avg_price").isNotNull(),
             (col("avg_price") - col("historical_avg_price")) / col("historical_avg_price")
        ).otherwise(0.0)
    ).withColumn(
        # 1a. Absolute price change (for threshold comparison)
        "price_change_abs",
        spark_abs(col("price_change_pct"))
    ).withColumn(
        # 2. Volume spike ratio
        "volume_spike_ratio",
        when(col("historical_avg_volume").isNotNull() & (col("historical_avg_volume") > 0),
             col("total_volume") / col("historical_avg_volume")
        ).otherwise(1.0)
    ).withColumn(
        # 3. Volatility ratio
        "volatility_ratio",
        when(col("historical_volatility").isNotNull() & (col("historical_volatility") > 0),
             col("price_volatility") / col("historical_volatility")
        ).otherwise(1.0)
    ).withColumn(
        # 4. Price gap (difference between max and min relative to avg)
        "price_gap_pct",
        (col("max_price") - col("min_price")) / col("avg_price")
    )
    
    # Detect anomalies based on thresholds
    anomaly_df = anomaly_df.withColumn(
        # Price spike detection (separate up/down)
        "is_price_spike_up",
        col("price_change_pct") > PRICE_CHANGE_THRESHOLD
    ).withColumn(
        "is_price_spike_down",
        col("price_change_pct") < -PRICE_CHANGE_THRESHOLD
    ).withColumn(
        "is_price_spike",
        col("is_price_spike_up") | col("is_price_spike_down")
    ).withColumn(
        "is_volume_spike",
        col("volume_spike_ratio") > VOLUME_SPIKE_THRESHOLD
    ).withColumn(
        "is_high_volatility",
        col("price_volatility") > VOLATILITY_THRESHOLD
    ).withColumn(
        "is_price_gap",
        col("price_gap_pct") > PRICE_GAP_THRESHOLD
    ).withColumn(
        # Overall anomaly flag (any anomaly detected)
        "is_anomaly",
        col("is_price_spike") | col("is_volume_spike") | 
        col("is_high_volatility") | col("is_price_gap")
    ).withColumn(
        # Anomaly severity (0-4, number of anomaly types detected)
        "anomaly_severity",
        (col("is_price_spike").cast("int") + 
         col("is_volume_spike").cast("int") + 
         col("is_high_volatility").cast("int") + 
         col("is_price_gap").cast("int"))
    ).withColumn(
        # Anomaly types (comma-separated list with direction)
        "anomaly_types",
        expr("""
            concat_ws(',',
                if(is_price_spike_up, 'PRICE_SPIKE_UP', null),
                if(is_price_spike_down, 'PRICE_SPIKE_DOWN', null),
                if(is_volume_spike, 'VOLUME_SPIKE', null),
                if(is_high_volatility, 'HIGH_VOLATILITY', null),
                if(is_price_gap, 'PRICE_GAP', null)
            )
        """)
    )
    
    # Filter only anomalies
    anomalies_only = anomaly_df.filter(col("is_anomaly") == True)
    
    return anomalies_only

# ============================================================================
# STREAMING PIPELINE
# ============================================================================
def run_anomaly_detection():
    """Main anomaly detection streaming pipeline"""
    
    print(f"[INFO] Starting Anomaly Detection Job")
    print(f"[INFO] Kafka: {KAFKA_BROKER}, Topic: {KAFKA_TOPIC}")
    print(f"[INFO] Elasticsearch: {ES_NODES}:{ES_PORT}, Index: {ES_INDEX}")
    print(f"[INFO] Checkpoint: {CHECKPOINT_LOCATION}")
    print(f"[INFO] Thresholds:")
    print(f"  - Price change: >{PRICE_CHANGE_THRESHOLD*100}%")
    print(f"  - Volume spike: >{VOLUME_SPIKE_THRESHOLD}x")
    print(f"  - Volatility: >{VOLATILITY_THRESHOLD*100}%")
    print(f"  - Price gap: >{PRICE_GAP_THRESHOLD*100}%")
    
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
    parsed_df = parsed_df.withColumn(
        "event_time", 
        to_timestamp(col("time"))
    )
    
    # Apply watermark
    watermarked_df = parsed_df.withWatermark("event_time", WATERMARK_DELAY)
    
    # Time window aggregation (same as regular streaming)
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
        stddev("Close").alias("price_volatility")
    ).withColumn(
        "window_start",
        col("window.start")
    ).withColumn(
        "window_end",
        col("window.end")
    ).drop("window")
    
    # Detect anomalies
    anomalies_df = detect_anomalies(windowed_df)
    
    # Format output for Elasticsearch
    output_df = anomalies_df.select(
        col("window_start").alias("@timestamp"),  # Kibana time field
        col("window_start"),
        col("window_end"),
        col("ticker"),
        col("company"),
        col("avg_price"),
        col("min_price"),
        col("price_change_abs"),
        col("volume_spike_ratio"),
        col("volatility_ratio"),
        col("price_gap_pct"),
        col("is_price_spike"),
        col("is_price_spike_up"),
        col("is_price_spike_downty"),
        col("historical_avg_price"),
        col("historical_avg_volume"),
        col("historical_volatility"),
        col("price_change_pct"),
        col("volume_spike_ratio"),
        col("volatility_ratio"),
        col("price_gap_pct"),
        col("is_price_spike"),
        col("is_volume_spike"),
        col("is_high_volatility"),
        col("is_price_gap"),
        col("anomaly_severity"),
        col("anomaly_types"),
        current_timestamp().alias("detected_time")
    )
    
    # Start streaming with retry
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
                .option("es.resource", ES_INDEX) \
                .option("es.nodes.wan.only", "true") \
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
    
    print(f"[INFO] Anomaly detection started. Writing to {ES_INDEX}")
    print(f"[INFO] Query ID: {query.id}")
    
    # Wait for termination
    query.awaitTermination()

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    try:
        run_anomaly_detection()
    except KeyboardInterrupt:
        print("\n[INFO] Anomaly detection interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Anomaly detection failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
