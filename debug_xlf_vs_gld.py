import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# Debug: Specific Comparison
TICKERS = {'XLF': 'XLF', 'GLD': 'GLD', 'SHV': 'SHV'}
LOOKBACK = 30

print(f"DEBUG: Comparing XLF vs GLD for Date: {datetime.now().strftime('%Y-%m-%d')}")

# Download
start_date = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d')
data = yf.download(list(TICKERS.values()), start=start_date, progress=False)['Close']
data = data.fillna(method='ffill').dropna()

print(f"\n{'ASSET':<6} {'PRICE -30d':<12} {'PRICE NOW':<12} {'RETURN %':<10} {'VOL %':<10} {'SCORE':<10}")
print("-" * 70)

for ticker in TICKERS:
    try:
        series = data[ticker]
        if len(series) < LOOKBACK: continue
            
        p_now = series.iloc[-1]
        p_prev = series.iloc[-1 - LOOKBACK]
        
        # Exact Calculation
        ret = (p_now - p_prev) / p_prev
        
        daily_rets = series.pct_change().iloc[-LOOKBACK:]
        vol = daily_rets.std()
        
        score = ret / (vol + 1e-9)
        
        print(f"{ticker:<6} {p_prev:<12.2f} {p_now:<12.2f} {ret*100:>8.2f}% {vol*100:>8.2f}% {score:>8.2f}")
    except Exception as e:
        print(f"Error {ticker}: {e}")

print("-" * 70)
print("Note: Differences can arise from Dividend Adjustments (yfinance vs others) or exact '30 day' count (Trading Days vs Calendar Days).")
print("My script uses 30 TRADING DAYS (Bars) for calculation.")
