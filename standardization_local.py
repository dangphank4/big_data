"""
UNIFIED DATA STANDARDIZATION MODULE
Shared schema and utilities for batch and streaming pipelines
"""

import json

# Optional PySpark import - only needed for Spark streaming
try:
    from pyspark.sql.types import (
        StructType, StructField, StringType, 
        DoubleType, IntegerType
    )
    HAS_PYSPARK = True
except ImportError:
    HAS_PYSPARK = False
    StructType = StructField = StringType = DoubleType = IntegerType = None

# Optional pandas import - only needed for batch processing
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None  # Set to None if not available

# ============================================================================
# FIELD NAME CONSTANTS - Use these in all batch jobs!
# ============================================================================
# To ensure consistency, always reference these constants instead of 
# hardcoding field names

# Core fields
FIELD_TICKER = "ticker"
FIELD_COMPANY = "company"
FIELD_TIME = "time"
FIELD_OPEN = "Open"
FIELD_HIGH = "High"
FIELD_LOW = "Low"
FIELD_CLOSE = "Close"
FIELD_ADJ_CLOSE = "Adj Close"
FIELD_VOLUME = "Volume"

# Derived fields (computed by batch jobs)
FIELD_MA_50 = "ma50"
FIELD_MA_100 = "ma100"
FIELD_MA_200 = "ma200"
FIELD_TREND = "trend"
FIELD_DRAWDOWN = "drawdown"
FIELD_MONTHLY_VOLATILITY = "monthly_volatility"

# ============================================================================
# UNIFIED SCHEMA - Single Source of Truth
# ============================================================================
# Field names that MUST be used across all services:
# - Kafka Producer
# - Kafka Consumer  
# - Spark Streaming
# - Batch Processing
# - Elasticsearch indexing

STOCK_FIELDS = [
    "ticker",      # Stock symbol (e.g., "AAPL")
    "company",     # Company name (e.g., "Apple Inc.")
    "time",        # Timestamp (ISO 8601 format)
    "Open",        # Opening price
    "High",        # Highest price
    "Low",         # Lowest price
    "Close",       # Closing price
    "Adj Close",   # Adjusted closing price (optional)
    "Volume"       # Trading volume
]

# PySpark Schema for Streaming
def get_spark_schema():
    """
    Returns PySpark StructType schema for stock data
    Used by: Spark Streaming jobs
    
    Note: This function requires PySpark. If PySpark is not available,
          an ImportError will be raised.
    """
    if not HAS_PYSPARK:
        raise ImportError(
            "pyspark is required for get_spark_schema(). "
            "This function is only available in Spark environments. "
            "Install pyspark with: pip install pyspark"
        )
    
    return StructType([
        StructField("ticker", StringType(), False),
        StructField("company", StringType(), True),
        StructField("time", StringType(), False),
        StructField("Open", DoubleType(), False),
        StructField("High", DoubleType(), False),
        StructField("Low", DoubleType(), False),
        StructField("Close", DoubleType(), False),
        StructField("Adj Close", DoubleType(), True),
        StructField("Volume", IntegerType(), False)
    ])

# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

def load_history(json_file="history.json", include_company=False):
    """
    Load historical stock data from JSON file
    
    Args:
        json_file: Path to history JSON file
        include_company: If True, include 'company' field in output
        
    Returns:
        pandas.DataFrame with standardized schema
        
    Used by: Batch processing pipeline
    
    Note: This function requires pandas. If pandas is not available,
          an ImportError will be raised.
    """
    if not HAS_PANDAS:
        raise ImportError(
            "pandas is required for load_history(). "
            "This function is only available in batch processing environments. "
            "Install pandas with: pip install pandas"
        )
    
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    df = pd.DataFrame(data)
    
    # Standardize datetime
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values(["ticker", "time"])

    # Select standard fields
    fields = ["ticker", "time", "Open", "High", "Low", "Close", "Volume"]
    if include_company and "company" in df.columns:
        fields.insert(1, "company")
    
    df = df[fields]

    return df

def validate_schema(data_dict):
    """
    Validate if data dict contains all required fields
    
    Args:
        data_dict: Dictionary to validate
        
    Returns:
        tuple: (is_valid, missing_fields)
        
    Used by: Data quality checks
    """
    required_fields = ["ticker", "time", "Open", "High", "Low", "Close", "Volume"]
    missing = [f for f in required_fields if f not in data_dict]
    return (len(missing) == 0, missing)

def standardize_message(raw_message):
    """
    Standardize a raw message to unified schema
    Ensures field names and types are correct
    
    Args:
        raw_message: Dict with raw data
        
    Returns:
        Dict with standardized fields
        
    Used by: Kafka consumers, data validation
    """
    standardized = {}
    
    # Required string fields
    for field in ["ticker", "time"]:
        standardized[field] = str(raw_message.get(field, ""))
    
    # Optional string field
    if "company" in raw_message:
        standardized["company"] = str(raw_message["company"])
    
    # Required numeric fields (OHLCV)
    for field in ["Open", "High", "Low", "Close", "Volume"]:
        value = raw_message.get(field, 0)
        if field == "Volume":
            standardized[field] = int(value)
        else:
            standardized[field] = float(value)
    
    # Optional Adj Close
    if "Adj Close" in raw_message:
        standardized["Adj Close"] = float(raw_message["Adj Close"])
    
    return standardized