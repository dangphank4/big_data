"""
UNIFIED PIPELINE RUNNER
Combines Batch Processing + Real-time Monitoring
Run from python-worker container
"""

import os
import sys
import time
import subprocess
from datetime import datetime
import logging

# ============================================================================
# LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("unified-runner")

# ============================================================================
# CONFIGURATION
# ============================================================================
RUN_MODE = os.getenv("RUN_MODE", "all")  # all, batch, monitor
BATCH_INTERVAL_HOURS = int(os.getenv("BATCH_INTERVAL_HOURS", "24"))

# ============================================================================
# BATCH PROCESSING
# ============================================================================
def run_batch_processing():
    """
    Run batch feature engineering pipeline
    - Loads history.json
    - Computes batch features (trend, drawdown, volatility, etc.)
    - Writes to HDFS and Elasticsearch
    """
    log.info("=" * 60)
    log.info("STARTING BATCH PROCESSING")
    log.info("=" * 60)
    
    try:
        # Import and run batch pipeline
        from run_all import main as batch_main
        
        start_time = time.time()
        batch_main()
        elapsed = time.time() - start_time
        
        log.info(f"✓ Batch processing completed in {elapsed:.2f}s")
        return True
        
    except Exception as e:
        log.error(f"✗ Batch processing failed: {e}", exc_info=True)
        return False

# ============================================================================
# MONITORING
# ============================================================================
def check_kafka_producer():
    """Check if Kafka producer is running"""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        return "kafka_producer.py" in result.stdout
    except Exception as e:
        log.warning(f"Could not check producer: {e}")
        return False

def check_elasticsearch_health():
    """Check Elasticsearch health"""
    try:
        import requests
        response = requests.get("http://elasticsearch:9200/_cluster/health", timeout=5)
        data = response.json()
        return data.get("status") in ["green", "yellow"]
    except Exception as e:
        log.warning(f"Elasticsearch health check failed: {e}")
        return False

def check_hdfs_health():
    """Check HDFS health"""
    try:
        from hdfs import InsecureClient
        client = InsecureClient("http://hadoop-namenode:9870", user="hdfs")
        client.status("/")
        return True
    except Exception as e:
        log.warning(f"HDFS health check failed: {e}")
        return False

def monitor_system():
    """Monitor system health"""
    log.info("=" * 60)
    log.info("SYSTEM HEALTH CHECK")
    log.info("=" * 60)
    
    checks = {
        "Kafka Producer": check_kafka_producer(),
        "Elasticsearch": check_elasticsearch_health(),
        "HDFS": check_hdfs_health()
    }
    
    for name, status in checks.items():
        icon = "✓" if status else "✗"
        log.info(f"{icon} {name}: {'OK' if status else 'FAIL'}")
    
    all_ok = all(checks.values())
    if not all_ok:
        log.warning("⚠ Some services are not healthy!")
    
    return all_ok

# ============================================================================
# MAIN LOOP
# ============================================================================
def run_unified_pipeline():
    """Main unified pipeline"""
    
    log.info("=" * 60)
    log.info("UNIFIED PIPELINE RUNNER")
    log.info(f"Mode: {RUN_MODE}")
    log.info(f"Batch Interval: {BATCH_INTERVAL_HOURS}h")
    log.info("=" * 60)
    
    last_batch_time = 0
    
    while True:
        try:
            current_time = time.time()
            
            # Monitor system health
            if RUN_MODE in ["all", "monitor"]:
                monitor_system()
            
            # Run batch processing
            if RUN_MODE in ["all", "batch"]:
                hours_since_last_batch = (current_time - last_batch_time) / 3600
                
                if hours_since_last_batch >= BATCH_INTERVAL_HOURS:
                    success = run_batch_processing()
                    if success:
                        last_batch_time = current_time
                    else:
                        log.warning("Batch processing failed, will retry next cycle")
                else:
                    remaining = BATCH_INTERVAL_HOURS - hours_since_last_batch
                    log.info(f"Next batch in {remaining:.1f}h")
            
            # Sleep between checks
            sleep_minutes = 5 if RUN_MODE == "monitor" else 30
            log.info(f"Sleeping {sleep_minutes} minutes...")
            time.sleep(sleep_minutes * 60)
            
        except KeyboardInterrupt:
            log.info("Interrupted by user, shutting down...")
            break
        except Exception as e:
            log.error(f"Error in main loop: {e}", exc_info=True)
            log.info("Retrying in 1 minute...")
            time.sleep(60)

# ============================================================================
# ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "batch":
            # Run batch once and exit
            success = run_batch_processing()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "monitor":
            # Run monitor once and exit
            success = monitor_system()
            sys.exit(0 if success else 1)
    
    # Run continuous unified pipeline
    run_unified_pipeline()
