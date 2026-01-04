"""
SPARK STREAMING JOB: REAL-TIME TECHNICAL INDICATORS FOR STOCK TRADING
===============================================================
Mục đích: Tính toán các chỉ báo kỹ thuật real-time từ dữ liệu cổ phiếu streaming
Chỉ báo: RSI, MACD, Moving Averages (SMA, EMA), Bollinger Bands, ATR

Góc nhìn Trader: Các chỉ báo này giúp xác định:
- Điểm mua/bán (RSI overbought/oversold)
- Xu hướng thị trường (Moving Averages crossover)
- Biến động và rủi ro (Bollinger Bands, ATR)
- Momentum (MACD)
"""

import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, window, avg, stddev, sum, count,
    lag, when, abs, max, min, lit, expr, unix_timestamp,
    to_timestamp, current_timestamp
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    TimestampType, LongType
)
from pyspark.sql.window import Window

# ============================================================================
# SCHEMA ĐỊNH NGHĨA
# ============================================================================

# Schema cho dữ liệu cổ phiếu từ Kafka
stock_schema = StructType([
    StructField("ticker", StringType(), True),
    StructField("company", StringType(), True),
    StructField("time", StringType(), True),  # Sẽ convert sang timestamp
    StructField("Open", DoubleType(), True),
    StructField("High", DoubleType(), True),
    StructField("Low", DoubleType(), True),
    StructField("Close", DoubleType(), True),
    StructField("Volume", DoubleType(), True)
])

# ============================================================================
# HÀM TÍNH TOÁN CHỈ BÁO KỸ THUẬT
# ============================================================================

def calculate_moving_averages(df, periods=[5, 10, 20, 50]):
    """
    Tính Moving Averages (SMA & EMA)
    
    Ý nghĩa Trading:
    - SMA 5/10: Xu hướng ngắn hạn (day trading)
    - SMA 20: Xu hướng trung hạn (swing trading)
    - SMA 50: Xu hướng dài hạn (position trading)
    - Golden Cross: SMA50 cắt lên SMA200 → Tín hiệu mua mạnh
    - Death Cross: SMA50 cắt xuống SMA200 → Tín hiệu bán mạnh
    """
    result_df = df
    
    for period in periods:
        # Window spec cho từng ticker
        windowSpec = Window.partitionBy("ticker").orderBy("timestamp").rowsBetween(-(period-1), 0)
        
        # Simple Moving Average
        result_df = result_df.withColumn(
            f"SMA_{period}",
            avg("Close").over(windowSpec)
        )
        
        # Exponential Moving Average (EMA)
        # EMA = Close * multiplier + EMA(previous) * (1 - multiplier)
        # multiplier = 2 / (period + 1)
        multiplier = 2.0 / (period + 1)
        
        # Tính EMA đơn giản (có thể tối ưu hơn với state store)
        result_df = result_df.withColumn(
            f"EMA_{period}",
            avg("Close").over(windowSpec)  # Simplified version
        )
    
    return result_df

def calculate_rsi(df, period=14):
    """
    Tính RSI (Relative Strength Index)
    
    Ý nghĩa Trading:
    - RSI > 70: Overbought (quá mua) → Cân nhắc bán
    - RSI < 30: Oversold (quá bán) → Cân nhắc mua
    - RSI 50: Vùng trung lập
    - Divergence: Giá tạo đỉnh mới nhưng RSI không → Tín hiệu đảo chiều
    
    Công thức:
    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain / Average Loss
    """
    windowSpec = Window.partitionBy("ticker").orderBy("timestamp")
    
    # Tính price change
    df_with_change = df.withColumn(
        "price_change",
        col("Close") - lag("Close", 1).over(windowSpec)
    )
    
    # Tách gain và loss
    df_with_change = df_with_change.withColumn(
        "gain",
        when(col("price_change") > 0, col("price_change")).otherwise(0)
    ).withColumn(
        "loss",
        when(col("price_change") < 0, abs(col("price_change"))).otherwise(0)
    )
    
    # Tính average gain và loss trong period
    windowSpec_period = Window.partitionBy("ticker").orderBy("timestamp").rowsBetween(-(period-1), 0)
    
    df_with_rs = df_with_change.withColumn(
        "avg_gain",
        avg("gain").over(windowSpec_period)
    ).withColumn(
        "avg_loss",
        avg("loss").over(windowSpec_period)
    )
    
    # Tính RSI
    df_with_rsi = df_with_rs.withColumn(
        "RS",
        when(col("avg_loss") != 0, col("avg_gain") / col("avg_loss")).otherwise(100)
    ).withColumn(
        "RSI",
        100 - (100 / (1 + col("RS")))
    ).withColumn(
        "RSI_signal",
        when(col("RSI") > 70, "OVERBOUGHT")
        .when(col("RSI") < 30, "OVERSOLD")
        .otherwise("NEUTRAL")
    )
    
    return df_with_rsi

def calculate_macd(df, fast=12, slow=26, signal=9):
    """
    Tính MACD (Moving Average Convergence Divergence)
    
    Ý nghĩa Trading:
    - MACD Line cắt lên Signal Line → Tín hiệu mua (Bullish)
    - MACD Line cắt xuống Signal Line → Tín hiệu bán (Bearish)
    - Histogram > 0: Xu hướng tăng mạnh lên
    - Histogram < 0: Xu hướng giảm mạnh lên
    
    Công thức:
    MACD Line = EMA(12) - EMA(26)
    Signal Line = EMA(9) of MACD Line
    Histogram = MACD Line - Signal Line
    """
    windowSpec = Window.partitionBy("ticker").orderBy("timestamp")
    
    # Tính EMA fast và slow
    window_fast = windowSpec.rowsBetween(-(fast-1), 0)
    window_slow = windowSpec.rowsBetween(-(slow-1), 0)
    
    df_with_ema = df.withColumn(
        "EMA_fast",
        avg("Close").over(window_fast)
    ).withColumn(
        "EMA_slow",
        avg("Close").over(window_slow)
    )
    
    # MACD Line
    df_with_macd = df_with_ema.withColumn(
        "MACD_line",
        col("EMA_fast") - col("EMA_slow")
    )
    
    # Signal Line (EMA of MACD)
    window_signal = windowSpec.rowsBetween(-(signal-1), 0)
    df_with_signal = df_with_macd.withColumn(
        "MACD_signal",
        avg("MACD_line").over(window_signal)
    )
    
    # Histogram và Trading Signal
    df_final = df_with_signal.withColumn(
        "MACD_histogram",
        col("MACD_line") - col("MACD_signal")
    ).withColumn(
        "MACD_crossover",
        when(
            (col("MACD_line") > col("MACD_signal")) & 
            (lag("MACD_line", 1).over(windowSpec) <= lag("MACD_signal", 1).over(windowSpec)),
            "BULLISH_CROSSOVER"
        ).when(
            (col("MACD_line") < col("MACD_signal")) & 
            (lag("MACD_line", 1).over(windowSpec) >= lag("MACD_signal", 1).over(windowSpec)),
            "BEARISH_CROSSOVER"
        ).otherwise("NO_SIGNAL")
    )
    
    return df_final

def calculate_bollinger_bands(df, period=20, std_dev=2):
    """
    Tính Bollinger Bands
    
    Ý nghĩa Trading:
    - Giá chạm Upper Band: Overbought → Cân nhắc bán
    - Giá chạm Lower Band: Oversold → Cân nhắc mua
    - Bandwidth hẹp: Consolidation (tích lũy) → Sắp breakout
    - Bandwidth rộng: Volatility cao → Xu hướng mạnh
    - Price breaks Upper Band: Strong bullish → Tiếp tục uptrend
    - Price breaks Lower Band: Strong bearish → Tiếp tục downtrend
    """
    windowSpec = Window.partitionBy("ticker").orderBy("timestamp").rowsBetween(-(period-1), 0)
    
    df_with_bands = df.withColumn(
        "BB_middle",
        avg("Close").over(windowSpec)
    ).withColumn(
        "BB_std",
        stddev("Close").over(windowSpec)
    ).withColumn(
        "BB_upper",
        col("BB_middle") + (col("BB_std") * std_dev)
    ).withColumn(
        "BB_lower",
        col("BB_middle") - (col("BB_std") * std_dev)
    ).withColumn(
        "BB_width",
        col("BB_upper") - col("BB_lower")
    ).withColumn(
        "BB_position",
        (col("Close") - col("BB_lower")) / (col("BB_upper") - col("BB_lower"))
    ).withColumn(
        "BB_signal",
        when(col("Close") >= col("BB_upper"), "UPPER_TOUCH")
        .when(col("Close") <= col("BB_lower"), "LOWER_TOUCH")
        .when(col("BB_position") > 0.8, "NEAR_UPPER")
        .when(col("BB_position") < 0.2, "NEAR_LOWER")
        .otherwise("MIDDLE_RANGE")
    )
    
    return df_with_bands

def calculate_atr(df, period=14):
    """
    Tính ATR (Average True Range)
    
    Ý nghĩa Trading:
    - Đo lường volatility (biến động)
    - ATR cao: Thị trường biến động mạnh → Rủi ro cao, dừng lỗ rộng hơn
    - ATR thấp: Thị trường ít biến động → Rủi ro thấp, dừng lỗ hẹp hơn
    - Sử dụng cho Stop Loss: Stop Loss = Entry Price ± (ATR × multiplier)
    """
    windowSpec = Window.partitionBy("ticker").orderBy("timestamp")
    
    # Tính True Range
    df_with_prev = df.withColumn(
        "prev_close",
        lag("Close", 1).over(windowSpec)
    )
    
    df_with_tr = df_with_prev.withColumn(
        "TR",
        expr("""
            GREATEST(
                High - Low,
                ABS(High - prev_close),
                ABS(Low - prev_close)
            )
        """)
    )
    
    # Average True Range
    window_period = windowSpec.rowsBetween(-(period-1), 0)
    df_with_atr = df_with_tr.withColumn(
        "ATR",
        avg("TR").over(window_period)
    ).withColumn(
        "ATR_percent",
        (col("ATR") / col("Close")) * 100
    ).withColumn(
        "volatility_level",
        when(col("ATR_percent") > 3, "HIGH_VOLATILITY")
        .when(col("ATR_percent") > 1.5, "MODERATE_VOLATILITY")
        .otherwise("LOW_VOLATILITY")
    )
    
    return df_with_atr

def generate_trading_signals(df):
    """
    Tổng hợp các tín hiệu trading từ nhiều chỉ báo
    
    Chiến lược Multi-Indicator Confirmation:
    - STRONG BUY: RSI < 30 + MACD Bullish + Price near BB Lower
    - BUY: 2/3 indicators bullish
    - STRONG SELL: RSI > 70 + MACD Bearish + Price near BB Upper
    - SELL: 2/3 indicators bearish
    - HOLD: Mixed signals
    """
    df_with_signals = df.withColumn(
        "bullish_count",
        (when(col("RSI") < 30, 1).otherwise(0) +
         when(col("MACD_crossover") == "BULLISH_CROSSOVER", 1).otherwise(0) +
         when(col("BB_signal").isin(["LOWER_TOUCH", "NEAR_LOWER"]), 1).otherwise(0))
    ).withColumn(
        "bearish_count",
        (when(col("RSI") > 70, 1).otherwise(0) +
         when(col("MACD_crossover") == "BEARISH_CROSSOVER", 1).otherwise(0) +
         when(col("BB_signal").isin(["UPPER_TOUCH", "NEAR_UPPER"]), 1).otherwise(0))
    ).withColumn(
        "overall_signal",
        when(col("bullish_count") >= 3, "STRONG_BUY")
        .when(col("bullish_count") == 2, "BUY")
        .when(col("bearish_count") >= 3, "STRONG_SELL")
        .when(col("bearish_count") == 2, "SELL")
        .otherwise("HOLD")
    ).withColumn(
        "signal_strength",
        when(col("overall_signal").isin(["STRONG_BUY", "STRONG_SELL"]), 
             (col("bullish_count") + col("bearish_count")) / 3.0)
        .otherwise(0.5)
    )
    
    return df_with_signals

# ============================================================================
# MAIN STREAMING JOB
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("🚀 BẮT ĐẦU SPARK STREAMING: TECHNICAL INDICATORS REAL-TIME")
    print("=" * 80)
    
    # Lấy config từ environment variables
    KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
    KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stock-realtime-topic")
    ES_NODES = os.getenv("ES_NODES", "elasticsearch")
    ES_PORT = os.getenv("ES_PORT", "9200")
    ES_INDEX = os.getenv("ES_INDEX", "stock_technical_indicators")
    CHECKPOINT_LOCATION = os.getenv(
        "CHECKPOINT_LOCATION",
        "hdfs://hadoop-namenode:8020/user/spark_checkpoints/stock_technical_indicators"
    )
    
    # Khởi tạo Spark Session
    print("\n📊 Khởi tạo SparkSession...")
    spark = SparkSession.builder \
        .appName("Stock Technical Indicators Real-time") \
        .config("spark.es.nodes", ES_NODES) \
        .config("spark.es.port", ES_PORT) \
        .config("spark.es.nodes.wan.only", "true") \
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_LOCATION) \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    print("✅ SparkSession đã sẵn sàng")
    
    # Đọc streaming data từ Kafka
    print(f"\n📡 Đọc dữ liệu từ Kafka - Broker: {KAFKA_BROKER}, Topic: {KAFKA_TOPIC}")
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "earliest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    # Parse JSON data
    print("\n🔍 Parse dữ liệu JSON từ Kafka...")
    parsed_df = kafka_df \
        .select(
            col("value").cast(StringType())
        ) \
        .filter(col("value").isNotNull()) \
        .withColumn("data", from_json(col("value"), stock_schema)) \
        .select("data.*") \
        .withColumn("timestamp", to_timestamp(col("time"))) \
        .filter(col("Close").isNotNull())
    
    # Thêm watermark để xử lý late data
    print("\n⏰ Áp dụng Watermark (10 phút)...")
    watermarked_df = parsed_df.withWatermark("timestamp", "10 minutes")
    
    # Tính các chỉ báo kỹ thuật
    print("\n📈 Tính toán các chỉ báo kỹ thuật...")
    print("  - Moving Averages (SMA 5, 10, 20, 50)")
    df_with_ma = calculate_moving_averages(watermarked_df, periods=[5, 10, 20, 50])
    
    print("  - RSI (Relative Strength Index)")
    df_with_rsi = calculate_rsi(df_with_ma, period=14)
    
    print("  - MACD (Moving Average Convergence Divergence)")
    df_with_macd = calculate_macd(df_with_rsi, fast=12, slow=26, signal=9)
    
    print("  - Bollinger Bands")
    df_with_bb = calculate_bollinger_bands(df_with_macd, period=20, std_dev=2)
    
    print("  - ATR (Average True Range)")
    df_with_atr = calculate_atr(df_with_bb, period=14)
    
    print("  - Tổng hợp Trading Signals")
    df_final = generate_trading_signals(df_with_atr)
    
    # Chọn các cột quan trọng để lưu
    output_df = df_final.select(
        "timestamp",
        "ticker",
        "company",
        "Open", "High", "Low", "Close", "Volume",
        # Moving Averages
        "SMA_5", "SMA_10", "SMA_20", "SMA_50",
        # RSI
        "RSI", "RSI_signal",
        # MACD
        "MACD_line", "MACD_signal", "MACD_histogram", "MACD_crossover",
        # Bollinger Bands
        "BB_upper", "BB_middle", "BB_lower", "BB_width", "BB_position", "BB_signal",
        # ATR
        "ATR", "ATR_percent", "volatility_level",
        # Trading Signals
        "bullish_count", "bearish_count", "overall_signal", "signal_strength"
    )
    
    # Ghi kết quả vào Elasticsearch using foreachBatch (compatible with ES 7.17 + Spark 3.5)
    print(f"\n💾 Ghi kết quả vào Elasticsearch - Index: {ES_INDEX}")
    
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
    
    # Console output for monitoring (optional)
    console_query = output_df \
        .filter(col("overall_signal").isin(["STRONG_BUY", "STRONG_SELL", "BUY", "SELL"])) \
        .writeStream \
        .outputMode("append") \
        .format("console") \
        .option("truncate", "false") \
        .start()
    
    print("\n" + "=" * 80)
    print("✅ STREAMING JOB ĐANG CHẠY (ForeachBatch mode) - Monitoring trading signals...")
    print("=" * 80)
    print("\n📊 Các tín hiệu STRONG_BUY/STRONG_SELL sẽ được hiển thị ở console\n")
    
    # Chờ streaming job
    query.awaitTermination()
    console_query.awaitTermination()
