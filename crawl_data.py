import os
import json
import pandas as pd
import yfinance as yf
from datetime import datetime


# =====================================================
# Convert DataFrame → danh sách JSON FLAT (ĐÚNG FORMAT)
# =====================================================
def df_to_flat_json(df: pd.DataFrame, ticker: str, company: str):
    records = []

    df2 = df.copy()

    # Nếu MultiIndex (Close, High... + ticker) → chỉ lấy level 0
    if isinstance(df2.columns, pd.MultiIndex):
        df2.columns = df2.columns.get_level_values(0)

    # Giờ df2.columns = ["Open", "High", "Low", "Close", "Volume"]

    df2.index = df2.index.astype(str)
    df2 = df2.where(pd.notnull(df2), None)

    for t, row in df2.iterrows():
        rec = {
            "ticker": ticker,
            "company": company,
            "time": t
        }
        rec.update(row.to_dict())
        records.append(rec)

    return records



# =====================================================
# Load 1 file duy nhất và update history FLAT JSON
# =====================================================
def save_all_flat_history(tickers, json_file="history_all.json", start="2025-04-01"):

    # Load file cũ (nếu có)
    if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
            all_records = json.load(f)
    else:
        all_records = []

    df_all = pd.DataFrame(all_records) if all_records else pd.DataFrame(columns=["ticker", "company", "time"])

    updated_records = []

    for ticker in tickers:
        print(f"\n=== {ticker} ===")

        tk = yf.Ticker(ticker)
        company = tk.info.get("longName")

        # Dữ liệu cũ cho ticker này
        df_old = df_all[df_all["ticker"] == ticker]

        if df_old.empty:
            print(f"[{ticker}] Chưa có dữ liệu → tải từ đầu...")
            last_date = start
        else:
            df_old = df_old.sort_values("time")
            last_date = df_old["time"].max()
            print(f"[{ticker}] Cập nhật từ ngày {last_date}...")

        # Download new part
        new_df = yf.download(ticker, start=last_date)

        if new_df.empty and not df_old.empty:
            print(f"[{ticker}] Không có dữ liệu mới.")
            updated_records.extend(df_old.to_dict(orient="records"))
            continue

        # Convert new DF thành JSON flat đúng format
        new_records = df_to_flat_json(new_df, ticker, company)

        # Merge
        if not df_old.empty:
            updated_records.extend(df_old.to_dict(orient="records"))

        updated_records.extend(new_records)

    # Sắp xếp theo ticker + time
    updated_records = sorted(updated_records, key=lambda x: (x["ticker"], x["time"]))

    # Ghi file
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(updated_records, f, indent=4, ensure_ascii=False)

    print(f"\nĐÃ LƯU HISTORY: {json_file}")
    return updated_records


# =====================================================
# REALTIME FLAT JSON (ĐÚNG FORMAT NHƯ HISTORY)
# =====================================================
def save_realtime_flat(tickers, json_file="realtime_all.json"):
    realtime = []

    for t in tickers:
        tk = yf.Ticker(t)
        info = tk.fast_info
        company = tk.info.get("longName")

        rec = {
            "ticker": t,
            "company": company,
            "time": datetime.now().isoformat(),
            "Open": info.get("open"),
            "High": info.get("day_high"),
            "Low": info.get("day_low"),
            "Close": info.get("last_price"),
            "Volume": info.get("volume"),
        }

        realtime.append(rec)

    # Append file
    if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
            old = json.load(f)
        realtime = old + realtime

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(realtime, f, indent=4, ensure_ascii=False)

    print(f"ĐÃ LƯU REALTIME: {json_file}")
    return realtime


# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    tickers = ["AAPL", "NVDA"]

    print("==== UPDATE HISTORY ====")
    save_all_flat_history(tickers)

    print("\n==== UPDATE REALTIME ====")
    save_realtime_flat(tickers)
