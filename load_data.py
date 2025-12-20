from hdfs import InsecureClient
import json
import pandas as pd

def load_history(
    hdfs_url="http://hadoop-namenode:9870",
    hdfs_path="/data/stock/history_all.json",
    user="hdfs"
):
    client = InsecureClient(hdfs_url, user=user)

    with client.read(hdfs_path) as reader:
        data = json.load(reader)

    df = pd.DataFrame(data)

    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values(["ticker", "time"])

    df = df[["ticker", "time", "Open", "High", "Low", "Close", "Volume"]]
    return df
