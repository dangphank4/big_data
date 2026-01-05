import json
import pandas as pd

def load_history(json_file="history_all.json"):
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    df = pd.DataFrame(data)

    df["time"] = pd.to_datetime(df["time"])
    df= df.sort_values(["ticker", "time"])

    df = df[["ticker", "time", "Open", "High", "Low", "Close", "Volume" ]]

    return df