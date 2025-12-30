"""
Utility to fetch adjusted OHLCV data to CSV for the robust backtester.

Usage (examples):
    python -m robust_backtester.download_data --tickers SPY QQQ IWM GLD TLT UUP --start 1980-01-01
    python -m robust_backtester.download_data --tickers ES=F NQ=F CL=F GC=F SI=F ZC=F ZS=F ZW=F DX-Y.NYB --start 1980-01-01

Notes:
- Uses yfinance; adjust tickers as needed for your data vendor.
- Saves to ./data/{TICKER}.csv with columns: Date,Open,High,Low,Close,Volume
- For futures/FX continuous series, yfinance tickers are imperfect; replace paths with your own high-quality continuous data if available.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf


def fetch_and_save(ticker: str, start: str, end: str | None, outdir: Path) -> Path:
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError(f"No data returned for {ticker}")
    df = df.rename(columns=str.title)  # Open, High, Low, Close, Volume, Adj Close
    df = df[["Open", "High", "Low", "Close", "Volume"]].reset_index()
    df = df.rename(columns={"Date": "Date"})
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / f"{ticker.replace('=','_').replace('^','')}.csv"
    df.to_csv(out_path, index=False)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Download adjusted OHLCV CSVs via yfinance")
    parser.add_argument("--tickers", nargs="+", required=True, help="List of tickers")
    parser.add_argument("--start", required=True, help="Start date, e.g. 1980-01-01")
    parser.add_argument("--end", default=None, help="End date (optional)")
    parser.add_argument("--outdir", default="data", help="Output directory")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    for t in args.tickers:
        path = fetch_and_save(t, args.start, args.end, outdir)
        print(f"Saved {t} -> {path}")


if __name__ == "__main__":
    main()
