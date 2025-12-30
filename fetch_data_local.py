"""
Run this script on your local machine to fetch real historical data.
Then upload the generated CSV files back to the Claude environment.

Requirements:
    pip install yfinance pandas

Usage:
    python fetch_data_local.py
"""

import pandas as pd
import os
import time

try:
    import yfinance as yf
except ImportError:
    print("Installing yfinance...")
    os.system("pip install yfinance pandas")
    import yfinance as yf

# Asset mapping: internal_name -> (yahoo_ticker, asset_class)
ASSETS = {
    # Equity Indices
    'SP500': '^GSPC',
    'NASDAQ': '^IXIC',
    'DOW': '^DJI',
    'RUSSELL2000': '^RUT',
    'NIKKEI': '^N225',
    'FTSE': '^FTSE',
    'DAX': '^GDAXI',
    'HANGSENG': '^HSI',

    # Commodities
    'GOLD': 'GC=F',
    'SILVER': 'SI=F',
    'CRUDE': 'CL=F',
    'NATGAS': 'NG=F',
    'COPPER': 'HG=F',
    'PLATINUM': 'PL=F',

    # Agricultural
    'CORN': 'ZC=F',
    'WHEAT': 'ZW=F',
    'SOYBEANS': 'ZS=F',
    'COFFEE': 'KC=F',
    'SUGAR': 'SB=F',
    'COTTON': 'CT=F',

    # Bonds
    'TBOND': 'ZB=F',
    'TNOTE10': 'ZN=F',

    # Currencies
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'DXY': 'DX-Y.NYB',

    # Crypto (limited history)
    'BTC': 'BTC-USD',
    'ETH': 'ETH-USD',

    # Sector ETFs
    'XLF': 'XLF',
    'XLE': 'XLE',
    'XLK': 'XLK',
    'XLV': 'XLV',
}

def fetch_all_data():
    """Fetch all assets and save to CSV"""

    os.makedirs('historical_data', exist_ok=True)

    print("=" * 60)
    print("FETCHING REAL HISTORICAL DATA")
    print("=" * 60)

    results = []

    for name, ticker in ASSETS.items():
        print(f"Fetching {name} ({ticker})...", end=' ', flush=True)

        try:
            data = yf.download(ticker, start='1980-01-01', end='2024-12-31',
                              progress=False, auto_adjust=True)

            if len(data) > 100:
                # Save to CSV
                filepath = f'historical_data/{name}.csv'
                data.to_csv(filepath)

                print(f"OK - {len(data)} days ({data.index[0].strftime('%Y-%m-%d')} to {data.index[-1].strftime('%Y-%m-%d')})")
                results.append({
                    'Asset': name,
                    'Ticker': ticker,
                    'Days': len(data),
                    'From': data.index[0].strftime('%Y-%m-%d'),
                    'To': data.index[-1].strftime('%Y-%m-%d'),
                    'Status': 'OK'
                })
            else:
                print("FAILED - insufficient data")
                results.append({'Asset': name, 'Ticker': ticker, 'Days': 0, 'Status': 'Failed'})

        except Exception as e:
            print(f"ERROR - {str(e)[:40]}")
            results.append({'Asset': name, 'Ticker': ticker, 'Days': 0, 'Status': 'Error'})

        time.sleep(0.5)  # Rate limiting

    # Save summary
    summary = pd.DataFrame(results)
    summary.to_csv('historical_data/data_summary.csv', index=False)

    print("\n" + "=" * 60)
    print(f"SUCCESS: {len([r for r in results if r['Status']=='OK'])}/{len(ASSETS)} assets")
    print("=" * 60)
    print("\nFiles saved to: historical_data/")
    print("Upload this folder to Claude environment to continue.")

if __name__ == '__main__':
    fetch_all_data()
