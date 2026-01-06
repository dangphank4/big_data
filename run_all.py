from standardization_local import load_history

from batch_jobs.batch_trend import batch_long_term_trend
from batch_jobs.drawdown import batch_drawdown
from batch_jobs.cumulative_return import batch_cumulative_return
from batch_jobs.volume_features import batch_volume_features
from batch_jobs.market_regime import batch_market_regime
from batch_jobs.monthly import (
    batch_monthly_return,
    batch_monthly_volatility
)

from elasticsearch import Elasticsearch, helpers
from hdfs import InsecureClient
import os
# Fix
import gc
# Fix


def write_to_hdfs(client, hdfs_path, df):
    """Write DataFrame to HDFS as JSON"""
    try:
        # Reset index to avoid complex index serialization issues
        df_to_write = df.reset_index(drop=True).copy()
        
        # Convert problematic types to strings
        for col in df_to_write.columns:
            if df_to_write[col].dtype == 'object' or str(df_to_write[col].dtype).startswith('period'):
                df_to_write[col] = df_to_write[col].astype(str)
        
        json_data = df_to_write.to_json(orient="records", date_format="iso")
        
        with client.write(hdfs_path, overwrite=True) as writer:
            writer.write(json_data.encode("utf-8"))
            
    except Exception as e:
        raise Exception(f"Failed to write to HDFS: {e}")

def write_to_elasticsearch(df, index_name):
    # Use environment variable or default to elasticsearch service
    es_host = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
    es_port = os.getenv("ELASTICSEARCH_PORT", "9200")
    es = Elasticsearch(
        [f"http://{es_host}:{es_port}"],
        # Force client to work with older server versions
        headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=7"}
    )

    actions = []
    for _, row in df.iterrows():
        doc = row.to_dict()

        if "date" in doc:
            doc["@timestamp"] = doc["date"]

        actions.append({
            "_index": index_name,
            "_source": doc
        })

    helpers.bulk(es, actions)
    print(f"Indexed {len(actions)} documents into {index_name}")

def main():
    # Load dữ liệu lịch sử
    df = load_history("history.json")

    # Ép kiểu để tiết kiệm RAM
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = df[col].astype("float32")

    # Tính toán Batch Features
    df = batch_long_term_trend(df)
    df = batch_cumulative_return(df)
    df = batch_drawdown(df)
    df = batch_volume_features(df)

    # Xử lý dữ liệu theo tháng
    monthly_vol = batch_monthly_volatility(df.copy())
    df["month"] = df["time"].dt.to_period("M")
    df = df.merge(monthly_vol, on=["ticker", "month"], how="left")
    df = batch_market_regime(df)
    
    #  Xóa rác bộ nhớ
    gc.collect()

    # HDFS lưu trữ toàn bộ dữ liệu (kể cả những dòng có NaN để làm lịch sử đầy đủ)
    print("BAT ĐẦU ĐẨY DỮ LIỆU LÊN HDFS...")
    hdfs_client = InsecureClient("http://hadoop-namenode:9870", user="root")
    try:
        hdfs_client.makedirs("/tmp/serving")
        write_to_hdfs(hdfs_client, "/tmp/serving/batch_features.json", df)
        print("DONE: Đã lưu vào HDFS tại /tmp/serving/batch_features.json")
    except Exception as e:
        print(f"LỖI HDFS: {e}")

    #  Chỉ lấy dữ liệu sạch (không NaN) để đẩy lên ES vẽ biểu đồ
    df_clean = df.dropna().copy()
    
    # Chuyển sang String để ES hiểu được
    df_to_es = df_clean.copy()
    df_to_es["month"] = df_to_es["month"].astype(str)
    df_to_es["time"] = df_to_es["time"].astype(str)

    print("BAT ĐẦU ĐẨY DỮ LIỆU LÊN ELASTICSEARCH...")
    write_to_elasticsearch(df_to_es, "batch-features")
    
    print("DONE! HỆ THỐNG ĐÃ CẬP NHẬT CẢ HDFS VÀ ELASTICSEARCH.")

if __name__ == "__main__":
    main()