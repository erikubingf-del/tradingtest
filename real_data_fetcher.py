"""
Real Historical Data Fetcher
Fetches actual market data from Yahoo Finance using chart API
"""

import pandas as pd
import numpy as np
import requests
import time
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Asset universe with real Yahoo Finance tickers
# Format: internal_name -> (yahoo_ticker, start_year_available, asset_class)
ASSET_MAPPING = {
    # US Equity Indices
    'SP500': ('^GSPC', 1950, 'equity'),          # S&P 500
    'NASDAQ': ('^IXIC', 1971, 'equity'),         # Nasdaq Composite
    'DOW': ('^DJI', 1985, 'equity'),             # Dow Jones
    'RUSSELL2000': ('^RUT', 1987, 'equity'),     # Russell 2000

    # International Indices
    'NIKKEI': ('^N225', 1965, 'equity'),         # Nikkei 225
    'FTSE': ('^FTSE', 1984, 'equity'),           # FTSE 100
    'DAX': ('^GDAXI', 1990, 'equity'),           # DAX
    'CAC40': ('^FCHI', 1990, 'equity'),          # CAC 40
    'HANGSENG': ('^HSI', 1986, 'equity'),        # Hang Seng
    'ASX200': ('^AXJO', 1992, 'equity'),         # ASX 200

    # Commodities (futures)
    'GOLD': ('GC=F', 1975, 'commodity'),         # Gold Futures
    'SILVER': ('SI=F', 1975, 'commodity'),       # Silver Futures
    'CRUDE': ('CL=F', 1983, 'commodity'),        # Crude Oil Futures
    'NATGAS': ('NG=F', 1990, 'commodity'),       # Natural Gas Futures
    'COPPER': ('HG=F', 1988, 'commodity'),       # Copper Futures
    'PLATINUM': ('PL=F', 1990, 'commodity'),     # Platinum Futures
    'PALLADIUM': ('PA=F', 1990, 'commodity'),    # Palladium Futures

    # Agricultural Commodities
    'CORN': ('ZC=F', 1959, 'commodity'),         # Corn Futures
    'WHEAT': ('ZW=F', 1959, 'commodity'),        # Wheat Futures
    'SOYBEANS': ('ZS=F', 1959, 'commodity'),     # Soybean Futures
    'COFFEE': ('KC=F', 1973, 'commodity'),       # Coffee Futures
    'SUGAR': ('SB=F', 1961, 'commodity'),        # Sugar Futures
    'COTTON': ('CT=F', 1959, 'commodity'),       # Cotton Futures
    'COCOA': ('CC=F', 1959, 'commodity'),        # Cocoa Futures

    # Bonds/Interest Rates
    'TBOND': ('ZB=F', 1977, 'bond'),             # 30-Year T-Bond Futures
    'TNOTE10': ('ZN=F', 1982, 'bond'),           # 10-Year T-Note Futures
    'TNOTE5': ('ZF=F', 1988, 'bond'),            # 5-Year T-Note Futures
    'TNOTE2': ('ZT=F', 1990, 'bond'),            # 2-Year T-Note Futures

    # Currencies
    'DXY': ('DX-Y.NYB', 1985, 'currency'),       # US Dollar Index
    'EURUSD': ('EURUSD=X', 1999, 'currency'),    # EUR/USD
    'GBPUSD': ('GBPUSD=X', 1990, 'currency'),    # GBP/USD
    'USDJPY': ('USDJPY=X', 1990, 'currency'),    # USD/JPY
    'AUDUSD': ('AUDUSD=X', 1990, 'currency'),    # AUD/USD
    'USDCAD': ('USDCAD=X', 1990, 'currency'),    # USD/CAD
    'USDCHF': ('USDCHF=X', 1990, 'currency'),    # USD/CHF

    # Cryptocurrencies (very limited history)
    'BTC': ('BTC-USD', 2014, 'crypto'),          # Bitcoin
    'ETH': ('ETH-USD', 2017, 'crypto'),          # Ethereum

    # Sector ETFs (limited history - mostly 1999+)
    'XLF': ('XLF', 1998, 'sector'),              # Financials
    'XLE': ('XLE', 1998, 'sector'),              # Energy
    'XLK': ('XLK', 1998, 'sector'),              # Technology
    'XLV': ('XLV', 1998, 'sector'),              # Healthcare
    'XLI': ('XLI', 1998, 'sector'),              # Industrials
    'XLP': ('XLP', 1998, 'sector'),              # Consumer Staples
    'XLY': ('XLY', 1998, 'sector'),              # Consumer Discretionary
    'XLB': ('XLB', 1998, 'sector'),              # Materials
    'XLU': ('XLU', 1998, 'sector'),              # Utilities
    'XLRE': ('XLRE', 2015, 'sector'),            # Real Estate
}

# Survivorship bias - assets that no longer exist or changed significantly
SURVIVORSHIP_NOTES = {
    'LTCM': 'Long-Term Capital Management - collapsed 1998',
    'ENRON': 'Enron - bankruptcy 2001',
    'LEHMAN': 'Lehman Brothers - bankruptcy 2008',
    'BEAR_STEARNS': 'Bear Stearns - acquired 2008',
    'WORLDCOM': 'WorldCom - bankruptcy 2002',
}


class RealDataFetcher:
    """Fetches real historical data from Yahoo Finance"""

    def __init__(self, cache_dir: str = 'data_cache'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
        })

    def _get_cache_path(self, ticker: str) -> str:
        """Get cache file path for a ticker"""
        safe_ticker = ticker.replace('^', '_').replace('=', '_').replace('.', '_').replace('-', '_')
        return os.path.join(self.cache_dir, f'{safe_ticker}.csv')

    def _fetch_yahoo_chart(self, ticker: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Fetch data from Yahoo Finance using chart API"""
        try:
            # Convert dates to timestamps
            start_ts = int(pd.Timestamp(start_date).timestamp())
            end_ts = int(pd.Timestamp(end_date).timestamp())

            # Yahoo Finance chart API
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            params = {
                'period1': start_ts,
                'period2': end_ts,
                'interval': '1d',
                'includePrePost': 'false',
                'events': 'div,split',
            }

            response = self.session.get(url, params=params, timeout=30)

            if response.status_code != 200:
                return None

            data = response.json()

            if 'chart' not in data or 'result' not in data['chart'] or not data['chart']['result']:
                return None

            result = data['chart']['result'][0]

            if 'timestamp' not in result or 'indicators' not in result:
                return None

            timestamps = result['timestamp']
            quote = result['indicators']['quote'][0]

            # Handle adjusted close
            adj_close = quote.get('close', quote.get('adjclose', []))
            if 'adjclose' in result['indicators']:
                adj_close = result['indicators']['adjclose'][0].get('adjclose', adj_close)

            df = pd.DataFrame({
                'Date': pd.to_datetime(timestamps, unit='s'),
                'Open': quote.get('open', [None] * len(timestamps)),
                'High': quote.get('high', [None] * len(timestamps)),
                'Low': quote.get('low', [None] * len(timestamps)),
                'Close': quote.get('close', [None] * len(timestamps)),
                'Adj Close': adj_close,
                'Volume': quote.get('volume', [None] * len(timestamps)),
            })

            df.set_index('Date', inplace=True)
            df = df.dropna(subset=['Close'])

            return df

        except Exception as e:
            print(f"  Error fetching {ticker}: {str(e)[:80]}")
            return None

    def fetch_asset(self, internal_name: str, start_date: str = '1980-01-01',
                    end_date: str = None, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        Fetch data for an asset by internal name
        """
        if internal_name not in ASSET_MAPPING:
            print(f"  Unknown asset: {internal_name}")
            return None

        ticker, available_from, asset_class = ASSET_MAPPING[internal_name]

        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # Adjust start date based on data availability
        requested_start = pd.Timestamp(start_date)
        available_start = pd.Timestamp(f'{available_from}-01-01')
        actual_start = max(requested_start, available_start)

        # Check cache
        cache_path = self._get_cache_path(ticker)
        if use_cache and os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                # Filter to requested date range
                df = df[actual_start.strftime('%Y-%m-%d'):end_date]
                if len(df) > 100:  # Require at least 100 days of data
                    return df
            except Exception as e:
                pass  # Will fetch fresh data

        # Fetch from Yahoo Finance
        print(f"  Fetching {internal_name} ({ticker})...", end='', flush=True)
        df = self._fetch_yahoo_chart(ticker, actual_start.strftime('%Y-%m-%d'), end_date)

        if df is not None and len(df) > 100:
            # Save to cache
            df.to_csv(cache_path)
            print(f" {len(df)} days")
            return df
        else:
            print(" FAILED")
            return None

    def fetch_all_assets(self, start_date: str = '1980-01-01',
                         end_date: str = None, use_cache: bool = True) -> Dict[str, pd.DataFrame]:
        """Fetch all assets in the universe"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        print(f"\nFetching {len(ASSET_MAPPING)} assets from {start_date} to {end_date}...")
        print("=" * 60)

        data = {}
        success_count = 0

        for name, (ticker, available_from, asset_class) in ASSET_MAPPING.items():
            df = self.fetch_asset(name, start_date, end_date, use_cache)
            if df is not None and len(df) > 100:
                data[name] = df
                success_count += 1

            # Rate limiting
            time.sleep(0.3)

        print("=" * 60)
        print(f"Successfully loaded {success_count}/{len(ASSET_MAPPING)} assets")

        return data

    def get_data_availability_report(self) -> pd.DataFrame:
        """Generate a report of data availability for all assets"""
        rows = []
        for name, (ticker, available_from, asset_class) in ASSET_MAPPING.items():
            cache_path = self._get_cache_path(ticker)

            if os.path.exists(cache_path):
                try:
                    df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                    rows.append({
                        'Asset': name,
                        'Ticker': ticker,
                        'Class': asset_class,
                        'Expected From': available_from,
                        'Actual From': df.index[0].strftime('%Y-%m-%d'),
                        'Actual To': df.index[-1].strftime('%Y-%m-%d'),
                        'Days': len(df),
                        'Years': round(len(df) / 252, 1),
                        'Status': 'OK'
                    })
                except:
                    rows.append({
                        'Asset': name, 'Ticker': ticker, 'Class': asset_class,
                        'Expected From': available_from, 'Actual From': 'N/A',
                        'Actual To': 'N/A', 'Days': 0, 'Years': 0, 'Status': 'Error'
                    })
            else:
                rows.append({
                    'Asset': name, 'Ticker': ticker, 'Class': asset_class,
                    'Expected From': available_from, 'Actual From': 'N/A',
                    'Actual To': 'N/A', 'Days': 0, 'Years': 0, 'Status': 'Not Fetched'
                })

        return pd.DataFrame(rows)


def main():
    """Test the data fetcher"""
    fetcher = RealDataFetcher()

    print("\n" + "=" * 60)
    print("REAL DATA FETCHER TEST")
    print("=" * 60)

    # Test with S&P 500
    sp500 = fetcher.fetch_asset('SP500', '1980-01-01', '2024-12-31')
    if sp500 is not None:
        print(f"\nS&P 500: {len(sp500)} days from {sp500.index[0].strftime('%Y-%m-%d')} to {sp500.index[-1].strftime('%Y-%m-%d')}")
        print(sp500.tail(3))


if __name__ == '__main__':
    main()
