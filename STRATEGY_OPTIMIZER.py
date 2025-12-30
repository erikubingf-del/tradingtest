"""
STRATEGY_OPTIMIZER.py
---------------------
Diagnosing the "Lost Decade" (2005-2015).
Searching for parameters that deliver CONSISTENCY (Trend Following).

Tests:
1. Lookback Periods: 30, 60, 90, 120, 200 days.
2. Trend Filter: Price > SMA 200?
3. Volatility Weighting: Inverse Volatility?

Goal: Maximize Sharpe Ratio and Stability over the full 20 years.
"""

import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. HISTORICAL UNIVERSE (Same as Ultimate) ---
# We assume the universe creation logic is sound, just the *selection* logic is noisy.
HISTORICAL_UNIVERSE = {
    2005: ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM', 'XLF', 'XLE', 'XLK', 'XLV', 'GLD', 'TLT', 'SHV', 'XOM', 'GE', 'MSFT', 'C'],
    2011: ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM', 'XLF', 'XLE', 'XLK', 'XLV', 'GLD', 'TLT', 'SHV', 'AAPL', 'XOM', 'MSFT', 'AMZN'],
    2016: ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM', 'XLF', 'XLE', 'XLK', 'XLV', 'GLD', 'TLT', 'SHV', 'AAPL', 'AMZN', 'MSFT', 'GOOGL', 'NVDA', 'FB', 'BTC-USD'],
    2020: ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM', 'XLF', 'XLE', 'XLK', 'XLV', 'GLD', 'TLT', 'SHV', 'USO', 'DBA', 'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'TSLA', 'BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD']
}

def get_universe_for_year(year):
    selected = 2005
    for y in sorted(HISTORICAL_UNIVERSE.keys()):
        if year >= y: selected = y
    return HISTORICAL_UNIVERSE[selected]

def run_test(lookback_days, use_sma_filter=False):
    print(f"\n--- TESTING LOOKBACK: {lookback_days} DAYS (SMA Filter: {use_sma_filter}) ---")
    
    # Load Data (Assuming previously downloaded cache or re-download)
    # Ideally reuse data to be fast.
    # For standalone, let's download just the core needed to prove the point.
    
    # We need a master ticker list
    all_tickers = set()
    for u in HISTORICAL_UNIVERSE.values(): all_tickers.update(u)
    
    # Download
    print("Loading Data...")
    raw_data = {}
    for t in all_tickers:
        try:
            df = yf.download(t, start="2004-01-01", progress=False)
            # Fix MultiIndex
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
            raw_data[t] = df
        except: pass
        
    master_adj = pd.DataFrame({k: v.get('Adj Close', v['Close']) for k, v in raw_data.items()}).ffill()
    master_close = pd.DataFrame({k: v['Close'] for k, v in raw_data.items()}).ffill()
    
    # Run Sim
    dates = master_adj.index
    equity = 1.0
    
    # Stats Tracking
    start_equity_2005 = 1.0
    equity_2015 = 1.0
    
    prev_eq = 1.0
    top_2 = ['SHV']
    
    # Start loop
    start_idx = max(lookback_days, 200) # Need enough data
    
    for i in range(start_idx, len(dates)-1):
        date = dates[i]
        next_date = dates[i+1]
        
        # Capture 2015 checkpoint
        if date.year == 2015 and dates[i-1].year == 2014:
            equity_2015 = prev_eq
            
        universe = get_universe_for_year(date.year)
        
        candidates = []
        for sym in universe:
            if sym in master_adj.columns and not pd.isna(master_adj[sym].iloc[i]):
                # SMA Filter check
                if use_sma_filter:
                    sma_200 = master_close[sym].iloc[i-200:i].mean()
                    price = master_close[sym].iloc[i]
                    if price < sma_200: continue
                    
                candidates.append(sym)
                
        scores = []
        for sym in candidates:
            # Score = Return(Lookback) / Vol(Lookback)
            p_now = master_adj[sym].iloc[i]
            p_prev = master_adj[sym].iloc[i-lookback_days]
            
            if pd.isna(p_prev) or p_prev==0: continue
            ret = (p_now - p_prev) / p_prev
            
            # Vol
            vol = master_adj[sym].iloc[i-lookback_days:i].pct_change().std()
            if pd.isna(vol) or vol==0: continue
            
            score = ret / (vol + 1e-9)
            scores.append((sym, score))
            
        scores.sort(key=lambda x: x[1], reverse=True)
        
        target = []
        if scores and scores[0][1] > 0:
            target.append(scores[0][0])
            if len(scores) > 1 and scores[1][1] > 0:
                target.append(scores[1][0])
                
        if not target: target = ['SHV']
        
        # Execution (Approx for speed: Close-to-Close of Next Day)
        # Accurate: Open-to-Open
        # For Optimization speed, let's use Adj Close pct_change of next day
        
        step_ret = 0.0
        w = 1.0 / len(target)
        for sym in target:
            if sym in master_adj.columns:
                r = master_adj[sym].pct_change().iloc[i+1] # Returns for tomorrow
                if pd.isna(r): r = 0.0
                if sym == 'SHV': r += (0.03/252) # Yield
                step_ret += r * w
                
        equity = prev_eq * (1 + step_ret)
        prev_eq = equity
        
    print(f"Final Equity: {equity:.2f}x")
    print(f"2005-2015 Return: {equity_2015:.2f}x")
    print(f"2015-2025 Return: {equity/equity_2015:.2f}x")
    
if __name__ == "__main__":
    # Test 3 variations
    run_test(30, False) # Baseline
    run_test(120, True) # Trend Following (6 Months + SMA200)
    run_test(90, True) # Hybrid
