"""
HDFS ARCHIVER - BATCH CONSUMER
Reads data from Kafka and archives to HDFS daily
Designed to run as K8s CronJob (e.g., daily at 00:00)
"""

import os
import json
from datetime import datetime, timedelta
from confluent_kafka import Consumer, TopicPartition, KafkaError
from hdfs import InsecureClient

# ============================================================================
# CONFIG
# ============================================================================
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "stocks-realtime")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "hdfs-archiver")
HDFS_HOST = os.getenv("HDFS_HOST", "hdfs-namenode")
# WebHDFS runs on 9870 (9000 is HDFS RPC and will NOT work with InsecureClient)
HDFS_PORT = os.getenv("HDFS_PORT", "9870")
HDFS_BASE_PATH = os.getenv("HDFS_BASE_PATH", "/stock-data")
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "24"))


class HDFSArchiver:
    def __init__(self):
        """Initialize Kafka consumer and HDFS client"""
        self.consumer = Consumer({
            'bootstrap.servers': KAFKA_BROKER,
            'group.id': KAFKA_GROUP_ID,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False,
        })
        
        self.hdfs_client = InsecureClient(f'http://{HDFS_HOST}:{HDFS_PORT}')
        
        print(f"[INIT] HDFS Archiver", flush=True)
        print(f"  Kafka: {KAFKA_BROKER} | Topic: {KAFKA_TOPIC}", flush=True)
        print(f"  HDFS: {HDFS_HOST}:{HDFS_PORT} | Path: {HDFS_BASE_PATH}", flush=True)
    
    def get_partition_offsets(self):
        """Get current partition offsets for the topic"""
        metadata = self.consumer.list_topics(topic=KAFKA_TOPIC)
        
        if KAFKA_TOPIC not in metadata.topics:
            raise RuntimeError(f"Topic {KAFKA_TOPIC} not found")
        
        partitions = []
        for partition in metadata.topics[KAFKA_TOPIC].partitions:
            tp = TopicPartition(KAFKA_TOPIC, partition)
            partitions.append(tp)
        
        return partitions
    
    def seek_to_timestamp(self, timestamp_ms):
        """Seek to specific timestamp across all partitions"""
        partitions = self.get_partition_offsets()
        
        # Assign partitions
        self.consumer.assign(partitions)
        
        # Set timestamp for each partition
        tps_with_ts = [TopicPartition(tp.topic, tp.partition, timestamp_ms) 
                       for tp in partitions]
        
        # Get offsets for timestamp
        offsets = self.consumer.offsets_for_times(tps_with_ts)
        
        # Seek to offsets
        for tp in offsets:
            if tp.offset >= 0:
                self.consumer.seek(tp)
                print(f"  [SEEK] Partition {tp.partition} → Offset {tp.offset}", flush=True)
    
    def consume_and_archive(self):
        """Main logic: consume from Kafka and write to HDFS"""
        
        # Calculate time range (last N hours)
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=LOOKBACK_HOURS)
        
        print(f"[START] Archiving data from {start_time} to {end_time}", flush=True)
        
        # Seek to start timestamp
        start_ts_ms = int(start_time.timestamp() * 1000)
        self.seek_to_timestamp(start_ts_ms)
        
        # Data buffer organized by date and ticker
        buffer = {}  # {date: {ticker: [records]}}
        
        messages_read = 0
        end_ts_ms = int(end_time.timestamp() * 1000)
        
        print("[CONSUME] Reading from Kafka...", flush=True)
        
        while True:
            msg = self.consumer.poll(timeout=1.0)
            
            if msg is None:
                # No more messages
                if messages_read > 0:
                    break
                continue
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    break
                else:
                    print(f"[ERROR] {msg.error()}", flush=True)
                    continue
            
            # Check if message is within time range
            msg_ts = msg.timestamp()[1]
            if msg_ts > end_ts_ms:
                break
            
            try:
                # Parse message
                record = json.loads(msg.value().decode('utf-8'))
                
                # Extract date from time field
                record_time = datetime.fromisoformat(record.get('time', ''))
                date_str = record_time.strftime('%Y-%m-%d')
                ticker = record['ticker']
                
                # Add to buffer
                if date_str not in buffer:
                    buffer[date_str] = {}
                if ticker not in buffer[date_str]:
                    buffer[date_str][ticker] = []
                
                buffer[date_str][ticker].append(record)
                messages_read += 1
                
                if messages_read % 1000 == 0:
                    print(f"  Read {messages_read} messages...", flush=True)
            
            except Exception as e:
                print(f"[ERROR] Parsing message: {e}", flush=True)
                continue
        
        print(f"[DONE] Read {messages_read} messages from Kafka", flush=True)
        
        # Commit offsets
        self.consumer.commit()
        
        # Write to HDFS
        self.write_to_hdfs(buffer)
    
    def write_to_hdfs(self, buffer):
        """Write buffered data to HDFS organized by date/ticker"""
        
        print(f"[HDFS] Writing {len(buffer)} dates to HDFS...", flush=True)
        
        total_files = 0
        total_records = 0
        
        for date_str, ticker_data in buffer.items():
            for ticker, records in ticker_data.items():
                # Path: /stock-data/YYYY-MM-DD/TICKER.json
                hdfs_path = f"{HDFS_BASE_PATH}/{date_str}/{ticker}.json"
                
                try:
                    # Check if file exists
                    file_exists = False
                    try:
                        status = self.hdfs_client.status(hdfs_path)
                        file_exists = True
                    except:
                        pass
                    
                    # Read existing data if file exists
                    existing_records = []
                    if file_exists:
                        with self.hdfs_client.read(hdfs_path, encoding='utf-8') as reader:
                            for line in reader:
                                existing_records.append(json.loads(line))
                    
                    # Merge with new records (deduplicate by time)
                    existing_times = {r['time'] for r in existing_records}
                    new_records = [r for r in records if r['time'] not in existing_times]
                    
                    # Combine and sort by time
                    all_records = existing_records + new_records
                    all_records.sort(key=lambda x: x['time'])
                    
                    # Write back to HDFS
                    with self.hdfs_client.write(hdfs_path, encoding='utf-8', overwrite=True) as writer:
                        for record in all_records:
                            writer.write(json.dumps(record, ensure_ascii=False) + '\n')
                    
                    total_files += 1
                    total_records += len(new_records)
                    
                    print(f"  ✓ {hdfs_path} | +{len(new_records)} records", flush=True)
                
                except Exception as e:
                    print(f"  ✗ {hdfs_path} | Error: {e}", flush=True)
        
        print(f"[COMPLETE] Wrote {total_files} files, {total_records} new records to HDFS", flush=True)
    
    def close(self):
        """Cleanup resources"""
        self.consumer.close()


def main():
    """Main entry point"""
    archiver = HDFSArchiver()
    
    try:
        archiver.consume_and_archive()
    except KeyboardInterrupt:
        print("[INTERRUPTED] Shutting down...", flush=True)
    except Exception as e:
        print(f"[FATAL ERROR] {e}", flush=True)
        raise
    finally:
        archiver.close()


if __name__ == "__main__":
    main()
