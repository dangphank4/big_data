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


def write_to_hdfs(client, hdfs_path, df):
    with client.write(hdfs_path, overwrite=True) as writer:
        writer.write(
            df.to_json(
                orient="records",
                date_format="iso"
            ).encode("utf-8")
        )

def write_to_elasticsearch(df, index_name):
    es = Elasticsearch("http://elasticsearch:9200")

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
    # Load normalized historical data
    df = load_history("/app/history_all.json")

    # Batch feature engineering (RECOMPUTE ALL)
    df = batch_long_term_trend(df)
    df = batch_cumulative_return(df)
    df = batch_drawdown(df)
    df = batch_volume_features(df)

    # monthly features
    monthly_ret = batch_monthly_return(df)
    monthly_vol = batch_monthly_volatility(df)

    # merge monthly volatility back for regime detection
    df = df.merge(
        monthly_vol,
        on=["ticker", "month"],
        how="left"
    )

    df = batch_market_regime(df)

    # Ghi local
    os.makedirs("output", exist_ok=True)

    df.to_json(
        "output/batch_features.json",
        orient="records",
        indent=4,
        date_format="iso"
    )

    monthly_ret.to_json(
        "output/monthly_return.json",
        orient="records",
        indent=4
    )

    # Ghi lên HDFS (SERVING LAYER)
    hdfs_client = InsecureClient(
        "http://hadoop-namenode:9870",
        user="hdfs"
    )

    try:
        hdfs_client.makedirs("/serving")
    except Exception:
        pass

    write_to_hdfs(
        hdfs_client,
        "/serving/batch_features.json",
        df
    )

    write_to_hdfs(
        hdfs_client,
        "/serving/monthly_return.json",
        monthly_ret
    )

    print("BATCH LAYER RECOMPUTE DONE")

    write_to_elasticsearch(df, "batch-features")
    write_to_elasticsearch(monthly_ret, "monthly-return")


if __name__ == "__main__":
    main()
