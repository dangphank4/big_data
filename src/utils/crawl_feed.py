"""
CRAWL FEED - HISTORICAL DATA BACKFILL UTILITY
Crawls historical stock data and writes directly to HDFS
Bypasses Kafka - for one-time backfill operations
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from hdfs import InsecureClient

try:
    # Preferred when executed as a module: python -m src.utils.crawl_feed
    from .crawl_data import CrawlData
except Exception:
    # Fallback when executed as a file: python src/utils/crawl_feed.py
    from crawl_data import CrawlData

# ============================================================================
# CONFIG
# ============================================================================
HDFS_HOST = os.getenv("HDFS_HOST", "hadoop-namenode")
# WebHDFS runs on 9870 (9000 is HDFS RPC and will NOT work with InsecureClient)
HDFS_PORT = os.getenv("HDFS_PORT", "9870")
HDFS_BASE_PATH = os.getenv("HDFS_BASE_PATH", "/stock-data")
DEFAULT_INTERVAL = os.getenv("HISTORICAL_INTERVAL", "1d")


class HistoricalBackfiller:
    """Backfill historical data directly to HDFS"""
    
    def __init__(self, interval: str = DEFAULT_INTERVAL):
        self.hdfs_client = InsecureClient(f'http://{HDFS_HOST}:{HDFS_PORT}')
        # Note: yfinance minute intervals (e.g., 1m) are typically limited to recent history.
        # For long backfills, prefer daily (1d) or hourly (1h) depending on availability.
        self.crawler = CrawlData(interval=interval)
        
        print(f"[INIT] Historical Backfiller", flush=True)
        print(f"  HDFS: {HDFS_HOST}:{HDFS_PORT} | Path: {HDFS_BASE_PATH}", flush=True)
    
    def check_existing_data(self, ticker, date_str):
        """Check if data already exists for ticker/date"""
        hdfs_path = f"{HDFS_BASE_PATH}/{date_str}/{ticker}.json"
        
        try:
            status = self.hdfs_client.status(hdfs_path)
            return True, hdfs_path
        except:
            return False, hdfs_path
    
    def read_existing_records(self, hdfs_path):
        """Read existing records from HDFS"""
        try:
            records = []
            with self.hdfs_client.read(hdfs_path, encoding='utf-8') as reader:
                for line in reader:
                    records.append(json.loads(line))
            return records
        except:
            return []
    
    def write_to_hdfs(self, ticker, date_str, records):
        """Write records to HDFS with deduplication"""
        hdfs_path = f"{HDFS_BASE_PATH}/{date_str}/{ticker}.json"
        
        try:
            # Read existing data
            existing_records = self.read_existing_records(hdfs_path)
            
            # Deduplicate by time
            existing_times = {r['time'] for r in existing_records}
            new_records = [r for r in records if r['time'] not in existing_times]
            
            if not new_records:
                print(f"  ⊘ {hdfs_path} | No new data (skipped)", flush=True)
                return 0
            
            # Merge and sort
            all_records = existing_records + new_records
            all_records.sort(key=lambda x: x['time'])
            
            # Ensure directory exists
            dir_path = f"{HDFS_BASE_PATH}/{date_str}"
            try:
                self.hdfs_client.makedirs(dir_path)
            except:
                pass
            
            # Write to HDFS
            with self.hdfs_client.write(hdfs_path, encoding='utf-8', overwrite=True) as writer:
                for record in all_records:
                    writer.write(json.dumps(record, ensure_ascii=False) + '\n')
            
            print(f"  ✓ {hdfs_path} | +{len(new_records)} records ({len(all_records)} total)", flush=True)
            return len(new_records)
        
        except Exception as e:
            print(f"  ✗ {hdfs_path} | Error: {e}", flush=True)
            return 0
    
    def backfill(self, tickers, start_date, end_date):
        """Backfill historical data for given tickers and date range"""
        
        print(f"\n{'='*70}")
        print(f"BACKFILL TASK")
        print(f"  Tickers: {', '.join(tickers)}")
        print(f"  Date Range: {start_date} to {end_date}")
        print(f"{'='*70}\n")
        
        total_records = 0
        total_files = 0
        skipped_files = 0
        
        for ticker in tickers:
            print(f"[CRAWL] {ticker}", flush=True)
            
            try:
                # Crawl historical data
                records = self.crawler.crawl_ticker(
                    ticker=ticker,
                    start=start_date,
                    end=end_date
                )
                
                if not records:
                    print(f"  ⚠ No data returned for {ticker}", flush=True)
                    continue
                
                # Group records by date
                records_by_date = {}
                for record in records:
                    try:
                        record_time = datetime.fromisoformat(record['time'])
                        date_str = record_time.strftime('%Y-%m-%d')
                        
                        if date_str not in records_by_date:
                            records_by_date[date_str] = []
                        records_by_date[date_str].append(record)
                    except Exception as e:
                        print(f"  ⚠ Invalid time format: {record.get('time')}", flush=True)
                        continue
                
                # Write each date
                for date_str, date_records in sorted(records_by_date.items()):
                    exists, _ = self.check_existing_data(ticker, date_str)
                    
                    written = self.write_to_hdfs(ticker, date_str, date_records)
                    
                    if written > 0:
                        total_files += 1
                        total_records += written
                    else:
                        skipped_files += 1
            
            except Exception as e:
                print(f"  ✗ Error crawling {ticker}: {e}", flush=True)
                continue
        
        print(f"\n{'='*70}")
        print(f"BACKFILL COMPLETE")
        print(f"  Files Written: {total_files}")
        print(f"  Files Skipped: {skipped_files} (no new data)")
        print(f"  Total New Records: {total_records}")
        print(f"{'='*70}\n")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Backfill historical stock data to HDFS',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backfill last 30 days for AAPL and NVDA
  python crawl_feed.py --tickers AAPL,NVDA --days 30
  
  # Backfill specific date range
  python crawl_feed.py --tickers TSLA,MSFT --start 2024-01-01 --end 2024-12-31
  
  # Backfill all default tickers for last year
  python crawl_feed.py --days 365
        """
    )
    
    parser.add_argument(
        '--tickers',
        type=str,
        default='AAPL,NVDA,TSLA,MSFT,GOOGL',
        help='Comma-separated ticker symbols (default: AAPL,NVDA,TSLA,MSFT,GOOGL)'
    )
    
    parser.add_argument(
        '--start',
        type=str,
        help='Start date (YYYY-MM-DD). Mutually exclusive with --days'
    )
    
    parser.add_argument(
        '--end',
        type=str,
        help='End date (YYYY-MM-DD). Defaults to today'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        help='Number of days to backfill from end date (alternative to --start)'
    )

    parser.add_argument(
        '--interval',
        type=str,
        default=DEFAULT_INTERVAL,
        help='yfinance interval for historical crawl (default: 1d). Examples: 1d, 1h, 1m (limited).'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    
    # Parse tickers
    tickers = [t.strip() for t in args.tickers.split(',')]
    
    # Calculate date range
    if args.end:
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    if args.days:
        if args.start:
            print("Error: Cannot specify both --start and --days")
            return 1
        start_date = end_date - timedelta(days=args.days)
    elif args.start:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
    else:
        print("Error: Must specify either --start or --days")
        return 1
    
    # Format dates
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Run backfill
    backfiller = HistoricalBackfiller(interval=args.interval)
    backfiller.backfill(tickers, start_date_str, end_date_str)
    
    return 0


if __name__ == "__main__":
    exit(main())
