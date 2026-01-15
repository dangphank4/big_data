"""
UNIFIED DATA STANDARDIZATION MODULE
Shared schema constants and validation utilities
"""

import json

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


def get_spark_schema():
    """Return a PySpark StructType for the unified stock schema.

    This is used by Spark streaming jobs that parse Kafka JSON messages.
    Importing PySpark is intentionally done inside the function so that
    non-Spark environments (e.g., IDEs without pyspark installed) can still
    import this module.
    """

    try:
        from pyspark.sql.types import (
            StructType,
            StructField,
            StringType,
            DoubleType,
        )
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "PySpark is required to build the Spark schema. "
            "Run this inside a Spark runtime/container."
        ) from e

    return StructType(
        [
            StructField(FIELD_TICKER, StringType(), True),
            StructField(FIELD_COMPANY, StringType(), True),
            StructField(FIELD_TIME, StringType(), True),
            StructField(FIELD_OPEN, DoubleType(), True),
            StructField(FIELD_HIGH, DoubleType(), True),
            StructField(FIELD_LOW, DoubleType(), True),
            StructField(FIELD_CLOSE, DoubleType(), True),
            StructField(FIELD_ADJ_CLOSE, DoubleType(), True),
            StructField(FIELD_VOLUME, DoubleType(), True),
        ]
    )


# ============================================================================
# DATA VALIDATION FUNCTIONS
# ============================================================================

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