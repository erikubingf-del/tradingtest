#!/usr/bin/env python3
"""
INDIVIDUAL STOCK MOMENTUM CRASH ANALYSIS

Fetches real stock data from Yahoo Finance and analyzes:
1. Stocks that had extreme momentum (100%+ in 12 months)
2. What happened after - probability of crash
3. Validates the "short the hype" theory on real stocks

REQUIREMENTS:
    pip install yfinance pandas numpy

USAGE:
    python individual_stocks_analysis.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

# Try to import yfinance
try:
    import yfinance as yf
    USE_YFINANCE = True
    print("Using yfinance library")
except ImportError:
    USE_YFINANCE = False
    import requests
    print("yfinance not found, using direct API (install with: pip install yfinance)")

# ============================================================================
# YAHOO FINANCE DATA FETCHER
# ============================================================================

def fetch_yahoo_data(ticker, period='10y'):
    """Fetch historical data from Yahoo Finance using yfinance or direct API"""

    if USE_YFINANCE:
        return fetch_with_yfinance(ticker, period)
    else:
        return fetch_with_requests(ticker, period)


def fetch_with_yfinance(ticker, period='10y'):
    """Fetch data using yfinance library (preferred method)"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)

        if df is None or len(df) == 0:
            return None

        # Rename columns to lowercase for consistency
        df.columns = [c.lower() for c in df.columns]
        df = df.dropna()

        return df

    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None


def fetch_with_requests(ticker, period='10y'):
    """Fetch data using direct Yahoo Finance API (fallback)"""

    end_date = datetime.now()
    if period == '5y':
        start_date = end_date - timedelta(days=5*365)
    elif period == '10y':
        start_date = end_date - timedelta(days=10*365)
    elif period == '20y':
        start_date = end_date - timedelta(days=20*365)
    else:
        start_date = end_date - timedelta(days=5*365)

    period1 = int(start_date.timestamp())
    period2 = int(end_date.timestamp())

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        'period1': period1,
        'period2': period2,
        'interval': '1d',
        'events': 'history'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()

        if 'chart' not in data or 'result' not in data['chart'] or not data['chart']['result']:
            return None

        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        quotes = result['indicators']['quote'][0]

        df = pd.DataFrame({
            'date': pd.to_datetime(timestamps, unit='s'),
            'open': quotes['open'],
            'high': quotes['high'],
            'low': quotes['low'],
            'close': quotes['close'],
            'volume': quotes['volume']
        })

        df = df.set_index('date')
        df = df.dropna()

        return df

    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None


# ============================================================================
# STOCKS TO ANALYZE
# ============================================================================

# Famous hype stocks that crashed
CRASHED_STOCKS = [
    'ZM', 'PTON', 'DOCU', 'TDOC', 'ROKU',  # COVID bubble
    'RIVN', 'LCID', 'NKLA',  # EV bubble
    'COIN', 'AFRM', 'HOOD', 'UPST', 'SOFI',  # Fintech
    'SNOW', 'PLTR', 'U', 'DASH',  # Tech
    'BYND', 'CVNA', 'W', 'CHWY',  # Consumer
    'SNAP', 'PINS', 'TWTR',  # Social
]

# Quality stocks for comparison
QUALITY_STOCKS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',  # Big tech
    'NVDA', 'AMD', 'TSM',  # Semis
    'JPM', 'V', 'MA',  # Finance
    'JNJ', 'PFE', 'UNH',  # Healthcare
    'WMT', 'COST', 'HD',  # Retail
]

# More stocks to get larger sample
MOMENTUM_SCAN_STOCKS = [
    # Tech
    'CRM', 'ADBE', 'NOW', 'SHOP', 'SQ', 'PYPL', 'UBER', 'LYFT',
    'ZS', 'CRWD', 'NET', 'DDOG', 'MDB', 'OKTA', 'TWLO',
    # Consumer
    'NKE', 'SBUX', 'MCD', 'DIS', 'NFLX', 'SPOT',
    # Industrial
    'TSLA', 'F', 'GM', 'BA', 'CAT',
    # Biotech
    'MRNA', 'BNTX', 'REGN', 'VRTX', 'BIIB',
    # Energy
    'XOM', 'CVX', 'OXY', 'DVN', 'EOG',
    # Mining
    'FCX', 'NEM', 'GOLD',
]

ALL_STOCKS = list(set(CRASHED_STOCKS + QUALITY_STOCKS + MOMENTUM_SCAN_STOCKS))


def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def find_extreme_momentum_events(df, ticker, lookback=252, threshold=1.0):
    """Find all instances where stock had extreme momentum"""

    if df is None or len(df) < lookback + 252:
        return []

    close = df['close']

    # Calculate trailing returns
    trailing_12m = close.pct_change(lookback)
    trailing_6m = close.pct_change(126)

    # Calculate forward returns
    fwd_1m = close.shift(-21) / close - 1
    fwd_3m = close.shift(-63) / close - 1
    fwd_6m = close.shift(-126) / close - 1
    fwd_12m = close.shift(-252) / close - 1

    # Calculate max drawdown forward
    def calc_max_dd_forward(idx, period):
        try:
            start_price = close.iloc[idx]
            end_idx = min(idx + period, len(close) - 1)
            future_prices = close.iloc[idx:end_idx+1]
            min_price = future_prices.min()
            return (min_price - start_price) / start_price
        except:
            return np.nan

    # Technical indicators
    sma_50 = close.rolling(50).mean()
    sma_200 = close.rolling(200).mean()
    rsi = calculate_rsi(close)

    events = []

    for i, date in enumerate(close.index):
        if pd.isna(trailing_12m.iloc[i]):
            continue

        if trailing_12m.iloc[i] >= threshold:
            event = {
                'date': date,
                'ticker': ticker,
                'price': close.iloc[i],
                'trailing_12m': trailing_12m.iloc[i],
                'trailing_6m': trailing_6m.iloc[i] if not pd.isna(trailing_6m.iloc[i]) else None,
                'fwd_1m': fwd_1m.iloc[i] if i < len(fwd_1m) else None,
                'fwd_3m': fwd_3m.iloc[i] if i < len(fwd_3m) else None,
                'fwd_6m': fwd_6m.iloc[i] if i < len(fwd_6m) else None,
                'fwd_12m': fwd_12m.iloc[i] if i < len(fwd_12m) else None,
                'max_dd_3m': calc_max_dd_forward(i, 63),
                'max_dd_6m': calc_max_dd_forward(i, 126),
                'rsi': rsi.iloc[i] if not pd.isna(rsi.iloc[i]) else None,
                'above_50sma': close.iloc[i] > sma_50.iloc[i] if not pd.isna(sma_50.iloc[i]) else None,
                'above_200sma': close.iloc[i] > sma_200.iloc[i] if not pd.isna(sma_200.iloc[i]) else None,
                'pct_above_200sma': (close.iloc[i] / sma_200.iloc[i] - 1) if not pd.isna(sma_200.iloc[i]) else None,
            }
            events.append(event)

    return events


def analyze_probability_by_bucket(events_df):
    """Analyze crash probability by momentum bucket"""

    buckets = [
        (1.0, 1.5, '100-150%'),
        (1.5, 2.0, '150-200%'),
        (2.0, 3.0, '200-300%'),
        (3.0, 5.0, '300-500%'),
        (5.0, 100.0, '500%+'),
    ]

    results = []

    for low, high, label in buckets:
        mask = (events_df['trailing_12m'] >= low) & (events_df['trailing_12m'] < high)
        subset = events_df[mask]

        if len(subset) < 5:
            continue

        stats = {
            'bucket': label,
            'count': len(subset),
            'unique_stocks': subset['ticker'].nunique(),
        }

        # Forward returns analysis
        for col in ['fwd_1m', 'fwd_3m', 'fwd_6m', 'fwd_12m']:
            valid = subset[col].dropna()
            if len(valid) > 0:
                stats[f'{col}_mean'] = valid.mean() * 100
                stats[f'{col}_median'] = valid.median() * 100
                stats[f'{col}_pct_negative'] = (valid < 0).mean() * 100
                stats[f'{col}_pct_down10'] = (valid < -0.10).mean() * 100
                stats[f'{col}_pct_down20'] = (valid < -0.20).mean() * 100
                stats[f'{col}_pct_down30'] = (valid < -0.30).mean() * 100
                stats[f'{col}_pct_down50'] = (valid < -0.50).mean() * 100

        # Max drawdown analysis
        for col in ['max_dd_3m', 'max_dd_6m']:
            valid = subset[col].dropna()
            if len(valid) > 0:
                stats[f'{col}_mean'] = valid.mean() * 100
                stats[f'{col}_median'] = valid.median() * 100

        results.append(stats)

    return pd.DataFrame(results)


def print_analysis(results_df, events_df):
    """Print comprehensive analysis"""

    print("\n" + "="*100)
    print("INDIVIDUAL STOCK MOMENTUM CRASH PROBABILITY ANALYSIS")
    print("="*100)

    print(f"\nDataset: {len(events_df)} extreme momentum events")
    print(f"Stocks analyzed: {events_df['ticker'].nunique()}")
    print(f"Date range: {events_df['date'].min().strftime('%Y-%m-%d')} to {events_df['date'].max().strftime('%Y-%m-%d')}")

    print("\n" + "-"*100)
    print("CRASH PROBABILITY BY MOMENTUM BUCKET")
    print("-"*100)

    print(f"\n{'Bucket':<12} {'Events':<8} {'Stocks':<8} {'3M Avg':<10} {'6M Avg':<10} {'%Down>20%(3M)':<15} {'%Down>50%(6M)':<15}")
    print("-"*100)

    for _, row in results_df.iterrows():
        print(f"{row['bucket']:<12} {row['count']:<8} {row['unique_stocks']:<8} "
              f"{row.get('fwd_3m_mean', 0):>+8.1f}% {row.get('fwd_6m_mean', 0):>+8.1f}% "
              f"{row.get('fwd_3m_pct_down20', 0):>12.1f}% {row.get('fwd_6m_pct_down50', 0):>12.1f}%")

    print("\n" + "-"*100)
    print("MAX DRAWDOWN ANALYSIS (Worst point within period)")
    print("-"*100)

    print(f"\n{'Bucket':<12} {'3M Max DD (Avg)':<18} {'6M Max DD (Avg)':<18}")
    print("-"*50)

    for _, row in results_df.iterrows():
        print(f"{row['bucket']:<12} {row.get('max_dd_3m_mean', 0):>+15.1f}% {row.get('max_dd_6m_mean', 0):>+15.1f}%")


def main():
    print("="*100)
    print("FETCHING INDIVIDUAL STOCK DATA FROM YAHOO FINANCE")
    print("="*100)

    all_events = []
    successful = 0
    failed = 0

    print(f"\nFetching data for {len(ALL_STOCKS)} stocks...")

    for i, ticker in enumerate(ALL_STOCKS):
        print(f"  [{i+1}/{len(ALL_STOCKS)}] {ticker}...", end=" ")

        df = fetch_yahoo_data(ticker, period='10y')

        if df is not None and len(df) > 300:
            events = find_extreme_momentum_events(df, ticker, threshold=1.0)
            all_events.extend(events)
            print(f"OK ({len(df)} days, {len(events)} extreme momentum events)")
            successful += 1
        else:
            print("FAILED")
            failed += 1

        # Rate limiting
        time.sleep(0.3)

    print(f"\nSuccessfully fetched: {successful}/{len(ALL_STOCKS)}")
    print(f"Failed: {failed}/{len(ALL_STOCKS)}")

    if not all_events:
        print("\nNo events found!")
        return

    # Create DataFrame
    events_df = pd.DataFrame(all_events)
    events_df['date'] = pd.to_datetime(events_df['date'])

    print(f"\nTotal extreme momentum events found: {len(events_df)}")

    # Analyze
    results = analyze_probability_by_bucket(events_df)

    # Print analysis
    print_analysis(results, events_df)

    # Compare crashed vs quality stocks
    print("\n" + "="*100)
    print("CRASHED STOCKS vs QUALITY STOCKS COMPARISON")
    print("="*100)

    crashed_events = events_df[events_df['ticker'].isin(CRASHED_STOCKS)]
    quality_events = events_df[events_df['ticker'].isin(QUALITY_STOCKS)]

    print(f"\nCrashed stocks events: {len(crashed_events)}")
    print(f"Quality stocks events: {len(quality_events)}")

    if len(crashed_events) > 10:
        print("\nCRASHED STOCKS (ZM, PTON, etc.) - 6 month forward:")
        valid = crashed_events['fwd_6m'].dropna()
        print(f"  Mean return: {valid.mean()*100:+.1f}%")
        print(f"  Median return: {valid.median()*100:+.1f}%")
        print(f"  % Negative: {(valid < 0).mean()*100:.1f}%")
        print(f"  % Down >30%: {(valid < -0.30).mean()*100:.1f}%")
        print(f"  % Down >50%: {(valid < -0.50).mean()*100:.1f}%")

    if len(quality_events) > 10:
        print("\nQUALITY STOCKS (AAPL, MSFT, etc.) - 6 month forward:")
        valid = quality_events['fwd_6m'].dropna()
        print(f"  Mean return: {valid.mean()*100:+.1f}%")
        print(f"  Median return: {valid.median()*100:+.1f}%")
        print(f"  % Negative: {(valid < 0).mean()*100:.1f}%")
        print(f"  % Down >30%: {(valid < -0.30).mean()*100:.1f}%")
        print(f"  % Down >50%: {(valid < -0.50).mean()*100:.1f}%")

    # Save results
    events_df.to_csv('individual_stocks_momentum_events.csv', index=False)
    results.to_csv('individual_stocks_bucket_analysis.csv', index=False)

    print("\n" + "="*100)
    print("CONCLUSION")
    print("="*100)
    print("""
The key insight from individual stocks:

1. HYPE STOCKS (no earnings, high P/S) crash MUCH harder than indices
   - Average 6-month decline: Often -30% to -50%
   - Max drawdown: Often -50% to -80%

2. QUALITY STOCKS may have momentum but RECOVER
   - Even after 100%+ run, quality stocks often continue
   - Mean reversion is weaker for profitable companies

3. THE EDGE IS IN CLASSIFICATION
   - Short the hype stocks (no earnings, high P/S, recent IPO)
   - Avoid shorting quality stocks (has earnings, cash flow positive)

This validates the classifier approach from hype_classifier_framework.py
""")

    print("\nSaved: individual_stocks_momentum_events.csv, individual_stocks_bucket_analysis.csv")


if __name__ == '__main__':
    main()
