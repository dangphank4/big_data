"""
SPARK STREAMING JOB: REAL-TIME ANOMALY DETECTION & RISK ALERTS
===============================================================
Mục đích: Phát hiện biến động bất thường và cảnh báo rủi ro real-time

Các loại Anomaly Detection:
1. Price Spike/Drop Detection (Biến động giá đột ngột)
2. Volume Spike Detection (Khối lượng giao dịch bất thường)
3. Volatility Breakout (Vượt ngưỡng biến động)
4. Circuit Breaker Alert (Cảnh báo tăng/giảm sàn)
5. Gap Detection (Giá mở cửa khác biệt đáng kể với giá đóng cửa hôm trước)

Góc nhìn Risk Management:
- Bảo vệ vốn khỏi biến động bất thường
- Phát hiện cơ hội trading ngắn hạn từ spike
- Cảnh báo rủi ro thanh khoản
"""

import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, window, avg, stddev, sum, count,
    lag, when, abs, max, min, lit, expr, unix_timestamp,
    to_timestamp, current_timestamp, sqrt, pow
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    TimestampType, LongType
)
from pyspark.sql.window import Window

# ============================================================================
# SCHEMA ĐỊNH NGHĨA
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
# HÀM PHÁT HIỆN ANOMALY
# ============================================================================

def detect_price_anomaly(df, std_multiplier=3.0, lookback_period=50):
    """
    Phát hiện biến động giá bất thường bằng Z-Score Method
    
    Ý nghĩa Trading:
    - Z-Score > 3: Giá tăng quá nhanh → Overbought, có thể pullback
    - Z-Score < -3: Giá giảm quá nhanh → Oversold, có thể rebound
    - |Z-Score| > 2: Biến động đáng chú ý
    
    Công thức:
    Z-Score = (Current Price - Mean Price) / Std Dev
    """
    windowSpec = Window.partitionBy("ticker").orderBy("timestamp")
    window_period = windowSpec.rowsBetween(-(lookback_period-1), 0)
    
    df_with_stats = df.withColumn(
        "price_mean",
        avg("Close").over(window_period)
    ).withColumn(
        "price_std",
        stddev("Close").over(window_period)
    ).withColumn(
        "z_score",
        (col("Close") - col("price_mean")) / col("price_std")
    ).withColumn(
        "price_anomaly_type",
        when(col("z_score") > std_multiplier, "EXTREME_SPIKE")
        .when(col("z_score") > 2, "MODERATE_SPIKE")
        .when(col("z_score") < -std_multiplier, "EXTREME_DROP")
        .when(col("z_score") < -2, "MODERATE_DROP")
        .otherwise("NORMAL")
    ).withColumn(
        "is_price_anomaly",
        when(abs(col("z_score")) > 2, True).otherwise(False)
    )
    
    return df_with_stats

def detect_volume_anomaly(df, std_multiplier=3.0, lookback_period=50):
    """
    Phát hiện khối lượng giao dịch bất thường
    
    Ý nghĩa Trading:
    - Volume Spike + Price Up: Xu hướng tăng mạnh, có confirmation
    - Volume Spike + Price Down: Bán tháo, cảnh báo nguy hiểm
    - High Volume + Price flat: Tích lũy hoặc phân phối → Breakout sắp xảy ra
    - Low Volume: Thiếu interest, xu hướng yếu
    """
    windowSpec = Window.partitionBy("ticker").orderBy("timestamp")
    window_period = windowSpec.rowsBetween(-(lookback_period-1), 0)
    
    df_with_volume_stats = df.withColumn(
        "volume_mean",
        avg("Volume").over(window_period)
    ).withColumn(
        "volume_std",
        stddev("Volume").over(window_period)
    ).withColumn(
        "volume_ratio",
        col("Volume") / col("volume_mean")
    ).withColumn(
        "volume_z_score",
        (col("Volume") - col("volume_mean")) / col("volume_std")
    ).withColumn(
        "volume_anomaly_type",
        when(col("volume_z_score") > std_multiplier, "EXTREME_VOLUME_SPIKE")
        .when(col("volume_z_score") > 2, "HIGH_VOLUME")
        .when(col("volume_z_score") < -2, "LOW_VOLUME")
        .otherwise("NORMAL_VOLUME")
    ).withColumn(
        "is_volume_anomaly",
        when(abs(col("volume_z_score")) > 2, True).otherwise(False)
    )
    
    # Phân tích Volume + Price Direction
    df_with_volume_stats = df_with_volume_stats.withColumn(
        "prev_close",
        lag("Close", 1).over(windowSpec)
    ).withColumn(
        "price_direction",
        when(col("Close") > col("prev_close"), "UP")
        .when(col("Close") < col("prev_close"), "DOWN")
        .otherwise("FLAT")
    ).withColumn(
        "volume_price_signal",
        when((col("volume_anomaly_type") == "EXTREME_VOLUME_SPIKE") & 
             (col("price_direction") == "UP"), "STRONG_BULLISH_VOLUME")
        .when((col("volume_anomaly_type") == "EXTREME_VOLUME_SPIKE") & 
              (col("price_direction") == "DOWN"), "STRONG_BEARISH_VOLUME")
        .when((col("volume_anomaly_type") == "HIGH_VOLUME") & 
              (col("price_direction") == "FLAT"), "ACCUMULATION_DISTRIBUTION")
        .otherwise("NORMAL_VOLUME_PATTERN")
    )
    
    return df_with_volume_stats

def detect_volatility_breakout(df, lookback_period=20):
    """
    Phát hiện breakout về volatility (biến động tăng đột ngột)
    
    Ý nghĩa Trading:
    - Volatility Expansion: Thị trường bắt đầu xu hướng mới
    - Volatility Contraction: Thị trường tích lũy, chuẩn bị breakout
    - Bollinger Band Squeeze: Volatility thấp nhất → Breakout sắp xảy ra
    """
    windowSpec = Window.partitionBy("ticker").orderBy("timestamp")
    window_period = windowSpec.rowsBetween(-(lookback_period-1), 0)
    
    # Tính True Range
    df_with_tr = df.withColumn(
        "prev_close",
        lag("Close", 1).over(windowSpec)
    ).withColumn(
        "TR",
        expr("""
            GREATEST(
                High - Low,
                ABS(High - prev_close),
                ABS(Low - prev_close)
            )
        """)
    )
    
    # Average True Range và volatility metrics
    df_with_volatility = df_with_tr.withColumn(
        "ATR",
        avg("TR").over(window_period)
    ).withColumn(
        "ATR_mean",
        avg("TR").over(window_period)
    ).withColumn(
        "ATR_std",
        stddev("TR").over(window_period)
    ).withColumn(
        "volatility_ratio",
        col("TR") / col("ATR_mean")
    ).withColumn(
        "volatility_percentile",
        (col("TR") - min("TR").over(window_period)) / 
        (max("TR").over(window_period) - min("TR").over(window_period))
    ).withColumn(
        "volatility_state",
        when(col("volatility_ratio") > 2.0, "EXTREME_VOLATILITY")
        .when(col("volatility_ratio") > 1.5, "HIGH_VOLATILITY")
        .when(col("volatility_ratio") < 0.5, "LOW_VOLATILITY_SQUEEZE")
        .otherwise("NORMAL_VOLATILITY")
    ).withColumn(
        "is_volatility_breakout",
        when(col("volatility_state") == "EXTREME_VOLATILITY", True).otherwise(False)
    )
    
    return df_with_volatility

def detect_circuit_breaker(df, threshold_percent=10.0):
    """
    Cảnh báo Circuit Breaker (Tăng/Giảm sàn)
    
    Ý nghĩa Trading:
    - Price change > +10%: Hitting upper limit → Cực kỳ bullish
    - Price change < -10%: Hitting lower limit → Cực kỳ bearish
    - Price change > +7%: Approaching limit → Momentum mạnh
    - Price change < -7%: Approaching limit → Selling pressure mạnh
    
    Cảnh báo Risk Management:
    - Không nên mua khi đang tăng sàn (có thể bị stuck)
    - Cân nhắc cut loss nếu giảm sàn
    """
    windowSpec = Window.partitionBy("ticker").orderBy("timestamp")
    
    df_with_circuit = df.withColumn(
        "prev_close",
        lag("Close", 1).over(windowSpec)
    ).withColumn(
        "price_change_percent",
        ((col("Close") - col("prev_close")) / col("prev_close")) * 100
    ).withColumn(
        "intraday_range_percent",
        ((col("High") - col("Low")) / col("Open")) * 100
    ).withColumn(
        "circuit_breaker_status",
        when(col("price_change_percent") >= threshold_percent, "UPPER_LIMIT_HIT")
        .when(col("price_change_percent") <= -threshold_percent, "LOWER_LIMIT_HIT")
        .when(col("price_change_percent") >= (threshold_percent * 0.7), "APPROACHING_UPPER_LIMIT")
        .when(col("price_change_percent") <= -(threshold_percent * 0.7), "APPROACHING_LOWER_LIMIT")
        .when(col("price_change_percent") >= (threshold_percent * 0.5), "STRONG_UPWARD_MOVEMENT")
        .when(col("price_change_percent") <= -(threshold_percent * 0.5), "STRONG_DOWNWARD_MOVEMENT")
        .otherwise("NORMAL_MOVEMENT")
    ).withColumn(
        "is_circuit_breaker",
        when(col("circuit_breaker_status").isin([
            "UPPER_LIMIT_HIT", "LOWER_LIMIT_HIT",
            "APPROACHING_UPPER_LIMIT", "APPROACHING_LOWER_LIMIT"
        ]), True).otherwise(False)
    )
    
    return df_with_circuit

def detect_gap(df, gap_threshold_percent=2.0):
    """
    Phát hiện Gap (Giá mở cửa khác biệt lớn với giá đóng cửa trước)
    
    Ý nghĩa Trading:
    - Gap Up: Tin tức tốt overnight → Bullish
    - Gap Down: Tin tức xấu overnight → Bearish
    - Gap Fill: Giá quay lại fill gap → Reversal pattern
    - Breakaway Gap: Gap không fill → Xu hướng mạnh tiếp tục
    """
    windowSpec = Window.partitionBy("ticker").orderBy("timestamp")
    
    df_with_gap = df.withColumn(
        "prev_close",
        lag("Close", 1).over(windowSpec)
    ).withColumn(
        "gap_percent",
        ((col("Open") - col("prev_close")) / col("prev_close")) * 100
    ).withColumn(
        "gap_type",
        when(col("gap_percent") >= gap_threshold_percent, "GAP_UP")
        .when(col("gap_percent") <= -gap_threshold_percent, "GAP_DOWN")
        .otherwise("NO_GAP")
    ).withColumn(
        "gap_size",
        abs(col("gap_percent"))
    ).withColumn(
        "is_gap",
        when(abs(col("gap_percent")) >= gap_threshold_percent, True).otherwise(False)
    )
    
    # Check if gap is filled during the day
    df_with_gap = df_with_gap.withColumn(
        "gap_filled",
        when(
            (col("gap_type") == "GAP_UP") & (col("Low") <= col("prev_close")),
            True
        ).when(
            (col("gap_type") == "GAP_DOWN") & (col("High") >= col("prev_close")),
            True
        ).otherwise(False)
    ).withColumn(
        "gap_signal",
        when((col("gap_type") == "GAP_UP") & (col("gap_filled") == False), "STRONG_BULLISH_GAP")
        .when((col("gap_type") == "GAP_DOWN") & (col("gap_filled") == False), "STRONG_BEARISH_GAP")
        .when(col("gap_filled") == True, "GAP_FILL_REVERSAL")
        .otherwise("NO_GAP_SIGNAL")
    )
    
    return df_with_gap

def generate_risk_alert(df):
    """
    Tổng hợp tất cả các anomaly và tạo risk alert level
    
    Risk Alert Levels:
    - CRITICAL: Multiple severe anomalies detected
    - HIGH: Severe anomaly in price or volume
    - MEDIUM: Moderate anomaly detected
    - LOW: Minor anomaly
    - NORMAL: No anomaly
    """
    df_with_risk = df.withColumn(
        "anomaly_count",
        (when(col("is_price_anomaly"), 1).otherwise(0) +
         when(col("is_volume_anomaly"), 1).otherwise(0) +
         when(col("is_volatility_breakout"), 1).otherwise(0) +
         when(col("is_circuit_breaker"), 1).otherwise(0) +
         when(col("is_gap"), 1).otherwise(0))
    ).withColumn(
        "risk_alert_level",
        when(col("anomaly_count") >= 3, "CRITICAL")
        .when((col("anomaly_count") == 2) | 
              col("price_anomaly_type").isin(["EXTREME_SPIKE", "EXTREME_DROP"]) |
              (col("circuit_breaker_status").isin(["UPPER_LIMIT_HIT", "LOWER_LIMIT_HIT"])),
              "HIGH")
        .when(col("anomaly_count") == 1, "MEDIUM")
        .otherwise("NORMAL")
    ).withColumn(
        "action_recommendation",
        when(
            (col("risk_alert_level") == "CRITICAL") & 
            (col("price_direction") == "DOWN"),
            "CONSIDER_STOP_LOSS_IMMEDIATELY"
        ).when(
            (col("risk_alert_level") == "CRITICAL") & 
            (col("price_direction") == "UP"),
            "CONSIDER_TAKE_PROFIT_OR_TRAILING_STOP"
        ).when(
            col("risk_alert_level") == "HIGH",
            "MONITOR_CLOSELY_REDUCE_POSITION_SIZE"
        ).when(
            col("gap_signal") == "STRONG_BULLISH_GAP",
            "POTENTIAL_ENTRY_ON_PULLBACK"
        ).when(
            col("gap_signal") == "STRONG_BEARISH_GAP",
            "AVOID_CATCHING_FALLING_KNIFE"
        ).otherwise("NORMAL_TRADING")
    )
    
    return df_with_risk

# ============================================================================
# MAIN STREAMING JOB
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("🚨 BẮT ĐẦU SPARK STREAMING: ANOMALY DETECTION & RISK ALERTS")
    print("=" * 80)
    
    # Config
    KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
    KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stock-realtime-topic")
    ES_NODES = os.getenv("ES_NODES", "elasticsearch")
    ES_PORT = os.getenv("ES_PORT", "9200")
    ES_INDEX = os.getenv("ES_INDEX", "stock_anomaly_alerts")
    CHECKPOINT_LOCATION = os.getenv(
        "CHECKPOINT_LOCATION",
        "hdfs://hadoop-namenode:8020/user/spark_checkpoints/stock_anomaly_alerts"
    )
    
    # Khởi tạo Spark
    print("\n📊 Khởi tạo SparkSession...")
    spark = SparkSession.builder \
        .appName("Stock Anomaly Detection Real-time") \
        .config("spark.es.nodes", ES_NODES) \
        .config("spark.es.port", ES_PORT) \
        .config("spark.es.nodes.wan.only", "true") \
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_LOCATION) \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    print("✅ SparkSession đã sẵn sàng")
    
    # Đọc streaming từ Kafka
    print(f"\n📡 Đọc dữ liệu từ Kafka - Topic: {KAFKA_TOPIC}")
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    # Parse JSON
    print("\n🔍 Parse dữ liệu JSON...")
    parsed_df = kafka_df \
        .select(
            col("timestamp").alias("kafka_timestamp"),
            col("value").cast(StringType())
        ) \
        .filter(col("value").isNotNull()) \
        .withColumn("data", from_json(col("value"), stock_schema)) \
        .select("kafka_timestamp", "data.*") \
        .withColumn("timestamp", to_timestamp(col("time"))) \
        .filter(col("Close").isNotNull())
    
    # Watermark
    print("\n⏰ Áp dụng Watermark...")
    watermarked_df = parsed_df.withWatermark("timestamp", "10 minutes")
    
    # Detect anomalies
    print("\n🔍 Phát hiện các anomaly...")
    print("  - Price Anomaly Detection (Z-Score)")
    df_with_price_anomaly = detect_price_anomaly(watermarked_df, std_multiplier=3.0)
    
    print("  - Volume Anomaly Detection")
    df_with_volume_anomaly = detect_volume_anomaly(df_with_price_anomaly, std_multiplier=3.0)
    
    print("  - Volatility Breakout Detection")
    df_with_volatility = detect_volatility_breakout(df_with_volume_anomaly)
    
    print("  - Circuit Breaker Detection")
    df_with_circuit = detect_circuit_breaker(df_with_volatility, threshold_percent=10.0)
    
    print("  - Gap Detection")
    df_with_gap = detect_gap(df_with_circuit, gap_threshold_percent=2.0)
    
    print("  - Risk Alert Generation")
    df_final = generate_risk_alert(df_with_gap)
    
    # Select output columns
    output_df = df_final.select(
        "timestamp",
        "ticker",
        "company",
        "Open", "High", "Low", "Close", "Volume",
        # Price Anomaly
        "z_score", "price_anomaly_type", "is_price_anomaly",
        # Volume Anomaly
        "volume_ratio", "volume_anomaly_type", "volume_price_signal", "is_volume_anomaly",
        # Volatility
        "volatility_ratio", "volatility_state", "is_volatility_breakout",
        # Circuit Breaker
        "price_change_percent", "circuit_breaker_status", "is_circuit_breaker",
        # Gap
        "gap_percent", "gap_type", "gap_filled", "gap_signal", "is_gap",
        # Risk Alert
        "anomaly_count", "risk_alert_level", "action_recommendation"
    )
    
    # Ghi vào Elasticsearch
    print(f"\n💾 Ghi kết quả vào Elasticsearch - Index: {ES_INDEX}")
    
    query = output_df.writeStream \
        .outputMode("append") \
        .format("org.elasticsearch.spark.sql") \
        .option("es.resource", ES_INDEX) \
        .option("es.nodes", ES_NODES) \
        .option("es.port", ES_PORT) \
        .option("es.nodes.wan.only", "true") \
        .option("checkpointLocation", CHECKPOINT_LOCATION) \
        .start()
    
    # Console output for CRITICAL and HIGH alerts
    console_query = output_df \
        .filter(col("risk_alert_level").isin(["CRITICAL", "HIGH"])) \
        .writeStream \
        .outputMode("append") \
        .format("console") \
        .option("truncate", "false") \
        .start()
    
    print("\n" + "=" * 80)
    print("🚨 ANOMALY DETECTION ĐANG HOẠT ĐỘNG")
    print("=" * 80)
    print("\n⚠️  CRITICAL và HIGH risk alerts sẽ được hiển thị ở console\n")
    
    query.awaitTermination()
    console_query.awaitTermination()
