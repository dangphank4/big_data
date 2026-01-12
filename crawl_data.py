import os
import json
import pandas as pd
import yfinance as yf
from datetime import datetime


def df_to_flat_json(df: pd.DataFrame, ticker: str, company: str):
    records = []

    df2 = df.copy()

    # Nếu cột là MultiIndex (Open, High + ticker)
    if isinstance(df2.columns, pd.MultiIndex):
        df2.columns = df2.columns.get_level_values(0)

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


def save_all_flat_history(
    tickers,
    json_file="history.json",
    interval="15m",
    start=None,
    end=None
):
    # ---- parse datetime ----
    # Hỗ trợ cả định dạng "%Y-%m-%d" (ngày) và "%Y-%m-%d %H:%M" (ngày giờ phút)
    if isinstance(start, str):
        try:
            start = datetime.strptime(start, "%Y-%m-%d %H:%M")
        except ValueError:
            start = datetime.strptime(start, "%Y-%m-%d")
    
    if isinstance(end, str):
        try:
            end = datetime.strptime(end, "%Y-%m-%d %H:%M")
        except ValueError:
            end = datetime.strptime(end, "%Y-%m-%d")

    # =====================================================
    # Load 1 file duy nhất và update history FLAT JSON
    # =====================================================

    # Load file cũ (nếu có)
    # ---- load old data ----
    if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
            all_records = json.load(f)
    else:
        all_records = []

    df_all = pd.DataFrame(all_records) if all_records else pd.DataFrame(
        columns=["ticker", "company", "time"]
    )

    updated_records = []

    for ticker in tickers:
        print(f"\n=== {ticker} ===")

        tk = yf.Ticker(ticker)
        company = tk.info.get("longName")

        df_old = df_all[df_all["ticker"] == ticker]

        # ---- download data ----
        new_df = yf.download(
            ticker,
            interval=interval,
            start=start,
            end=end,
            auto_adjust=False,
            progress=False
        )

        if new_df.empty:
            print(f"[{ticker}] No new data")
            if not df_old.empty:
                updated_records.extend(df_old.to_dict(orient="records"))
            continue

        new_records = df_to_flat_json(new_df, ticker, company)

        if not df_old.empty:
            updated_records.extend(df_old.to_dict(orient="records"))

        updated_records.extend(new_records)

    # ---- sort & save ----
        # ---- deduplicate, sort & save ----
    # Loại bỏ bản ghi trùng theo khóa (ticker, time). Giữ bản ghi mới nhất nếu có trùng.
    if updated_records:
        df_updated = pd.DataFrame(updated_records)
        df_updated = df_updated.drop_duplicates(subset=["ticker", "time"], keep="last")
        updated_records = df_updated.sort_values(by=["ticker", "time"]).to_dict(orient="records")
    else:
        updated_records = []

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(updated_records, f, indent=4, ensure_ascii=False)

    print("\nĐÃ LƯU HISTORY THEO KHOẢNG NGÀY + GIỜ")
    return updated_records

if __name__ == "__main__":
    # Ví dụ: Lưu theo ngày
    save_all_flat_history(
        tickers=["AAPL", "NVDA"], 
        json_file="history.json",
        interval="15m",    #1d, 1h, 1m tuy chon     
        start="2026-01-05",    
        end="2026-01-10"
    )
    #1m	~7 ngày gần nhất
    #5m–60m	~60 ngày gần nhất
    #1d	Không giới hạn