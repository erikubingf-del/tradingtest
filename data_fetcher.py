"""
Data Fetching Module for Trend Following Backtester

Handles fetching historical data from multiple sources:
- Yahoo Finance (primary)
- Crypto exchanges via CCXT (for extended crypto history)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import yfinance as yf
from tqdm import tqdm
import warnings
import time

warnings.filterwarnings('ignore')


class DataFetcher:
    """
    Multi-source data fetcher with caching and error handling.
    """

    def __init__(self, cache_dir: str = "./data_cache"):
        self.cache_dir = cache_dir
        self.data_cache: Dict[str, pd.DataFrame] = {}
        self.failed_tickers: List[str] = []

    def fetch_single(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data for a single ticker.

        Args:
            ticker: The ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval: Data interval (1d, 1wk, 1mo)

        Returns:
            DataFrame with OHLCV data or None if failed
        """
        cache_key = f"{ticker}_{start_date}_{end_date}_{interval}"

        if cache_key in self.data_cache:
            return self.data_cache[cache_key]

        try:
            # Use yfinance to fetch data
            df = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                interval=interval,
                progress=False,
                auto_adjust=True  # Use adjusted prices
            )

            if df.empty:
                self.failed_tickers.append(ticker)
                return None

            # Standardize column names
            df.columns = [col.lower() if isinstance(col, str) else col[0].lower() for col in df.columns]

            # Ensure we have required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    # Try to find it in multi-level columns
                    for c in df.columns:
                        if col in str(c).lower():
                            df[col] = df[c]
                            break

            # Add ticker identifier
            df['ticker'] = ticker

            # Cache the data
            self.data_cache[cache_key] = df

            return df

        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            self.failed_tickers.append(ticker)
            return None

    def fetch_multiple(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        interval: str = "1d",
        show_progress: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple tickers.

        Returns:
            Dictionary mapping ticker to DataFrame
        """
        data = {}
        iterator = tqdm(tickers, desc="Fetching data") if show_progress else tickers

        for ticker in iterator:
            df = self.fetch_single(ticker, start_date, end_date, interval)
            if df is not None and not df.empty:
                data[ticker] = df
            time.sleep(0.1)  # Rate limiting

        return data

    def fetch_universe(
        self,
        universe: Dict[str, List[Tuple[str, str]]],
        start_date: str,
        end_date: str
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for entire asset universe.
        """
        all_tickers = []
        for category, assets in universe.items():
            for ticker, name in assets:
                all_tickers.append(ticker)

        return self.fetch_multiple(all_tickers, start_date, end_date)

    def get_aligned_data(
        self,
        data: Dict[str, pd.DataFrame],
        min_history_days: int = 252
    ) -> pd.DataFrame:
        """
        Align all tickers to common dates and return a multi-column DataFrame.

        Args:
            data: Dictionary of ticker -> DataFrame
            min_history_days: Minimum days of history required

        Returns:
            DataFrame with MultiIndex columns (ticker, field)
        """
        if not data:
            return pd.DataFrame()

        # Find common date range
        all_dates = None
        valid_tickers = []

        for ticker, df in data.items():
            if len(df) >= min_history_days:
                if all_dates is None:
                    all_dates = set(df.index)
                else:
                    all_dates = all_dates.intersection(set(df.index))
                valid_tickers.append(ticker)

        if not all_dates:
            return pd.DataFrame()

        common_dates = sorted(list(all_dates))

        # Build aligned DataFrame
        aligned_data = {}
        for ticker in valid_tickers:
            df = data[ticker]
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    aligned_data[(ticker, col)] = df.loc[common_dates, col]

        result = pd.DataFrame(aligned_data, index=common_dates)
        result.columns = pd.MultiIndex.from_tuples(result.columns)

        return result

    def calculate_returns(
        self,
        data: Dict[str, pd.DataFrame],
        price_col: str = 'close'
    ) -> pd.DataFrame:
        """
        Calculate returns for all tickers.

        Returns:
            DataFrame with daily returns for each ticker
        """
        returns = {}
        for ticker, df in data.items():
            if price_col in df.columns:
                returns[ticker] = df[price_col].pct_change()

        return pd.DataFrame(returns)


class CryptoDataFetcher:
    """
    Specialized fetcher for cryptocurrency data.
    Uses yfinance for simplicity but can be extended to CCXT.
    """

    def __init__(self):
        self.cache: Dict[str, pd.DataFrame] = {}

    def fetch_crypto(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        Fetch crypto data. Symbol should be like 'BTC-USD'.
        """
        try:
            df = yf.download(
                symbol,
                start=start_date,
                end=end_date,
                progress=False
            )

            if df.empty:
                return None

            df.columns = [col.lower() if isinstance(col, str) else col[0].lower() for col in df.columns]
            df['ticker'] = symbol

            return df

        except Exception as e:
            print(f"Error fetching crypto {symbol}: {e}")
            return None


def get_historical_data_summary(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Generate summary of available data for each ticker.
    """
    summary = []
    for ticker, df in data.items():
        if df is not None and not df.empty:
            summary.append({
                'ticker': ticker,
                'start_date': df.index.min(),
                'end_date': df.index.max(),
                'days': len(df),
                'years': len(df) / 252,
                'missing_pct': df['close'].isna().sum() / len(df) * 100 if 'close' in df.columns else 0
            })

    return pd.DataFrame(summary).sort_values('start_date')


def validate_data_quality(df: pd.DataFrame) -> Dict:
    """
    Validate data quality for a single ticker.
    """
    if df is None or df.empty:
        return {'valid': False, 'reason': 'Empty data'}

    issues = []

    # Check for missing values
    missing_pct = df.isna().sum() / len(df)
    if missing_pct.max() > 0.05:
        issues.append(f"High missing values: {missing_pct.max():.1%}")

    # Check for price anomalies
    if 'close' in df.columns:
        returns = df['close'].pct_change()
        extreme_moves = (returns.abs() > 0.5).sum()
        if extreme_moves > 0:
            issues.append(f"{extreme_moves} extreme daily moves (>50%)")

    # Check for stale data
    if 'close' in df.columns:
        unchanged = (df['close'].diff() == 0).sum()
        if unchanged / len(df) > 0.1:
            issues.append(f"Stale data: {unchanged / len(df):.1%} unchanged days")

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'days': len(df),
        'start': df.index.min() if len(df) > 0 else None,
        'end': df.index.max() if len(df) > 0 else None
    }


if __name__ == "__main__":
    # Test the data fetcher
    fetcher = DataFetcher()

    # Test single ticker
    print("Testing single ticker fetch...")
    spy_data = fetcher.fetch_single("SPY", "2020-01-01", "2024-01-01")
    if spy_data is not None:
        print(f"SPY data: {len(spy_data)} days from {spy_data.index.min()} to {spy_data.index.max()}")

    # Test multiple tickers
    print("\nTesting multiple ticker fetch...")
    test_tickers = ["SPY", "QQQ", "GLD", "TLT", "BTC-USD"]
    multi_data = fetcher.fetch_multiple(test_tickers, "2020-01-01", "2024-01-01")
    print(f"Successfully fetched {len(multi_data)} tickers")

    # Show data summary
    summary = get_historical_data_summary(multi_data)
    print("\nData Summary:")
    print(summary.to_string())
