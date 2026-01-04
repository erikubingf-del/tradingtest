#!/usr/bin/env python3
"""
SIGNAL AGE CHECKER: How long has this stock been signaling?
============================================================

Checks when a stock FIRST triggered the entry criteria.
Helps you know if it's a fresh signal or an old one.

Usage:
    python signal_age.py TICKER [TICKER2 ...]
    python signal_age.py CLSK SMCI
    python signal_age.py --all  # Check all current signals
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import warnings
warnings.filterwarnings('ignore')

def check_signal_age(ticker):
    """
    Check when a stock first triggered the signal criteria.
    Returns the first signal date and how many days ago.
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period='14mo')

        if len(df) < 252:
            return None, None, "Insufficient data"

        df = df.reset_index()
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)

        # Calculate indicators for each day
        df['high_52w'] = df['Close'].rolling(252).max()
        df['pct_from_high'] = (df['Close'] - df['high_52w']) / df['high_52w']
        df['mom_12m'] = df['Close'].pct_change(252)

        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Check criteria for each day
        df['signal'] = (
            (df['mom_12m'] >= 1.0) &  # 100% momentum
            (df['pct_from_high'] <= -0.50) &  # 50% drop
            (df['rsi'] < 60)  # RSI < 60
        )

        # Find first signal date
        signals = df[df['signal'] == True]

        if len(signals) == 0:
            return None, None, "No signal (criteria not met)"

        first_signal_date = signals['Date'].iloc[0]
        last_signal_date = signals['Date'].iloc[-1]
        current_price = df['Close'].iloc[-1]

        # Is it currently signaling?
        is_current = df['signal'].iloc[-1]

        # Days since first signal
        days_since_first = (datetime.now() - first_signal_date).days

        # Get price at first signal
        first_signal_price = signals['Close'].iloc[0]
        price_change = (current_price / first_signal_price - 1) * 100

        # Count consecutive signal days (current streak)
        streak = 0
        for i in range(len(df) - 1, -1, -1):
            if df['signal'].iloc[i]:
                streak += 1
            else:
                break

        return {
            'ticker': ticker,
            'first_signal_date': first_signal_date.strftime('%Y-%m-%d'),
            'days_since_first': days_since_first,
            'first_signal_price': first_signal_price,
            'current_price': current_price,
            'price_change_pct': price_change,
            'is_current_signal': is_current,
            'current_streak_days': streak,
            'total_signal_days': len(signals),
            'current_mom': df['mom_12m'].iloc[-1] * 100,
            'current_drop': df['pct_from_high'].iloc[-1] * 100,
            'current_rsi': df['rsi'].iloc[-1],
        }, None

    except Exception as e:
        return None, str(e)


def main():
    if len(sys.argv) < 2:
        print("Usage: python signal_age.py TICKER [TICKER2 ...]")
        print("       python signal_age.py --all")
        sys.exit(1)

    # Get tickers to check
    if sys.argv[1] == '--all':
        # Run sniper scan first to get current signals
        print("Scanning for current signals...")
        from sniper_scanner_v2 import ALL_STOCKS, scan_stock
        tickers = []
        for t in ALL_STOCKS:
            result = scan_stock(t)
            if result:
                tickers.append(t)
        print(f"Found {len(tickers)} current signals\n")
    else:
        tickers = [t.upper() for t in sys.argv[1:]]

    if not tickers:
        print("No tickers to check.")
        sys.exit(0)

    print("="*80)
    print("SIGNAL AGE ANALYSIS")
    print("="*80)
    print(f"Checking {len(tickers)} ticker(s): {', '.join(tickers)}\n")

    results = []
    for ticker in tickers:
        print(f"Analyzing {ticker}...")
        result, error = check_signal_age(ticker)

        if error:
            print(f"  ERROR: {error}\n")
            continue

        if result is None:
            print(f"  No signal found\n")
            continue

        results.append(result)

    if not results:
        print("No results to display.")
        sys.exit(0)

    # Display results
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)

    for r in results:
        status = "🟢 ACTIVE" if r['is_current_signal'] else "🔴 EXPIRED"
        freshness = "🆕 FRESH!" if r['days_since_first'] <= 5 else "⚠️  OLD" if r['days_since_first'] > 14 else "📅 RECENT"

        print(f"""
┌─────────────────────────────────────────────────────────────────────
│ {r['ticker']} - {status} {freshness}
├─────────────────────────────────────────────────────────────────────
│ First Signal:     {r['first_signal_date']} ({r['days_since_first']} days ago)
│ Current Streak:   {r['current_streak_days']} consecutive days
│ Total Signal Days: {r['total_signal_days']} days
│
│ Price at Signal:  ${r['first_signal_price']:.2f}
│ Current Price:    ${r['current_price']:.2f} ({r['price_change_pct']:+.1f}% since signal)
│
│ Current Stats:
│   Momentum:       {r['current_mom']:+.0f}%
│   From High:      {r['current_drop']:.0f}%
│   RSI:            {r['current_rsi']:.0f}
└─────────────────────────────────────────────────────────────────────""")

    # Summary recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    for r in results:
        ticker = r['ticker']
        days = r['days_since_first']
        price_chg = r['price_change_pct']

        if not r['is_current_signal']:
            print(f"\n{ticker}: ❌ SKIP - Signal expired (criteria no longer met)")
        elif days <= 3:
            print(f"\n{ticker}: ✅ ENTER - Fresh signal ({days} days old)")
        elif days <= 7:
            print(f"\n{ticker}: ✅ ENTER - Recent signal ({days} days old), still good")
        elif days <= 14 and price_chg < 10:
            print(f"\n{ticker}: ⚠️  CAUTION - Signal is {days} days old, price {price_chg:+.0f}% since")
            print(f"          Consider entering but you missed the ideal entry")
        else:
            print(f"\n{ticker}: ❌ SKIP - Signal too old ({days} days) or price moved too much ({price_chg:+.0f}%)")
            print(f"          Wait for next fresh signal on this stock")

    print("\n" + "="*80)
    print("ENTRY RULES")
    print("="*80)
    print("""
    ✅ ENTER if:
       - Signal is ≤7 days old
       - Price hasn't moved more than +10% since first signal

    ⚠️  CAUTION if:
       - Signal is 8-14 days old
       - You may have missed some of the move

    ❌ SKIP if:
       - Signal is >14 days old
       - Price has moved >10% since signal
       - Signal has expired (criteria no longer met)

    The backtest enters on DAY 1 of the signal.
    Entering late reduces expected returns.
    """)


if __name__ == "__main__":
    main()
