import pandas as pd
import yfinance as yf
from datetime import datetime
from typing import List, Dict, Iterable


class CrawlData:
    """
    Crawl stock data from yfinance and return flat JSON records
    """

    def __init__(self, interval: str = "1d"):
        self.interval = interval

    @staticmethod
    def _parse_datetime(dt):
        """
        Hỗ trợ:
        - YYYY-MM-DD
        - YYYY-MM-DD HH:MM
        """
        if isinstance(dt, str):
            try:
                return datetime.strptime(dt, "%Y-%m-%d %H:%M")
            except ValueError:
                return datetime.strptime(dt, "%Y-%m-%d")
        return dt

    @staticmethod
    def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
        """
        Chuẩn hoá dataframe:
        - Bỏ MultiIndex
        - index → string
        - NaN → None
        """
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.index = df.index.astype(str)
        df = df.where(pd.notnull(df), None)
        return df

    @staticmethod
    def _df_to_flat_records(
        df: pd.DataFrame,
        ticker: str,
        company: str
    ) -> List[Dict]:
        """
        DataFrame → flat JSON records
        """
        records = []

        for t, row in df.iterrows():
            rec = {
                "ticker": ticker,
                "company": company,
                "time": t
            }
            rec.update(row.to_dict())
            records.append(rec)

        return records

    def crawl_ticker(
        self,
        ticker: str,
        start=None,
        end=None,
        latest_only: bool = False
    ) -> List[Dict]:
        """
        Crawl 1 mã cổ phiếu
        - interval=1m → dùng period=1d
        - latest_only=True → chỉ lấy candle mới nhất (Kafka)
        """

        tk = yf.Ticker(ticker)
        company = tk.info.get("longName")

        if self.interval == "1m":
            df = yf.download(
                ticker,
                interval="1m",
                period="1d",
                auto_adjust=False,
                progress=False
            )
        else:
            start = self._parse_datetime(start)
            end = self._parse_datetime(end)

            df = yf.download(
                ticker,
                interval=self.interval,
                start=start,
                end=end,
                auto_adjust=False,
                progress=False
            )

        if df.empty:
            return []

        df = self._normalize_df(df)

        if latest_only:
            df = df.tail(1)

        return self._df_to_flat_records(df, ticker, company)

    def crawl_many(
        self,
        tickers: Iterable[str],
        start=None,
        end=None
    ) -> List[Dict]:
        """
        Crawl nhiều mã – trả về list records
        """
        all_records = []

        for ticker in tickers:
            print(f"[CRAWL] {ticker}")
            records = self.crawl_ticker(ticker, start, end)
            all_records.extend(records)

        return all_records

    def crawl_many_stream(
        self,
        tickers: Iterable[str],
        start=None,
        end=None
    ):
        """
        Generator version – dùng cho Kafka streaming
        """
        for ticker in tickers:
            print(f"[CRAWL-STREAM] {ticker}")
            for record in self.crawl_ticker(ticker, start, end):
                yield record