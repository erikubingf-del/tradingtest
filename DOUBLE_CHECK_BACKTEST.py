import yfinance as yf
import pandas as pd
import numpy as np
import shutil
import os
import sys

# --- CONFIG ---
TICKERS = {
    'BTC': 'BTC-USD', 'ETH': 'ETH-USD', 'SOL': 'SOL-USD',
    'SPY': 'SPY', 'QQQ': 'QQQ', 'IWM': 'IWM',
    'XLK': 'XLK', 'XLF': 'XLF', 'XLE': 'XLE', 'XLV': 'XLV',
    'NVDA': 'NVDA', 'AAPL': 'AAPL', 'MSFT': 'MSFT', 'AMZN': 'AMZN',
    'EFA': 'EFA', 'EEM': 'EEM',
    'GLD': 'GLD', 'USO': 'USO', 'DBA': 'DBA',
    'TLT': 'TLT', 'UUP': 'UUP', 'SHV': 'SHV'
}
LOOKBACK = 30
TOP_N = 2
FRICTION = 0.002 # 0.1% Fee + 0.1% Slippage (Conservative)

def clear_cache():
    cache_dir = os.path.expanduser("~/.cache/py-yfinance")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print("CACHE CLEARED.")
        except: pass

def run_rigorous_backtest():
    clear_cache()
    print("Downloading Fresh Data (Open/High/Low/Close)...")
    
    data_close = {}
    data_open = {}
    
    # We need OPEN and CLOSE for realistic execution
    # Signal at Close(i) -> Trade at Open(i+1)
    
    for name, ticker in TICKERS.items():
        try:
            df = yf.download(ticker, start='2017-09-01', progress=False)
            if len(df) > 100:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                
                # Close for Sig
                c = df['Close']
                c.name = name
                data_close[name] = c
                
                # Open for Execution
                o = df['Open']
                o.name = name
                data_open[name] = o
        except: pass

    df_close = pd.DataFrame(data_close).fillna(method='ffill').dropna()
    df_open = pd.DataFrame(data_open).fillna(method='ffill').dropna()
    
    # Align Check
    common_index = df_close.index.intersection(df_open.index)
    df_close = df_close.loc[common_index]
    df_open = df_open.loc[common_index]
    
    print(f"Data Aligned: {len(df_close)} days.")

    # 1. Scores (on CLOSE)
    scores = pd.DataFrame(index=df_close.index, columns=df_close.columns)
    for col in df_close.columns:
        ret = df_close[col].pct_change(LOOKBACK)
        vol = df_close[col].pct_change().rolling(LOOKBACK).std()
        scores[col] = ret / (vol + 1e-9)
    scores = scores.fillna(0)

    # 2. Simulation (Gap Execution)
    equity = 1.0
    equity_curve = []
    current_holdings = []
    
    # We trade from LOOKBACK to End
    # Decision at Close[i]. Execution at Open[i+1].
    # Holding period: Open[i+1] to Open[i+2] basically? 
    # Or Open[i+1] to Close[i+1]? 
    # Standard: Decide Close[i]. Enter Open[i+1]. Hold until Close[i+1] (for daily rebal) OR Hold until Open[i+2].
    # Simplest Realistic: Invest at Open[i+1]. Value changes by (Open[i+2] / Open[i+1]).
    # This captures the full day-to-day move including next gap.
    
    # Let's track Portfolio Value at OPEN.
    
    print(f"{'DATE':<12} {'HOLDING 1':<10} {'HOLDING 2':<10} {'VALUE':<10}")
    print("-" * 50)
    
    for i in range(LOOKBACK, len(df_close) - 1):
        date = df_close.index[i]
        next_open_date = df_close.index[i+1]
        
        # 1. GENERATE SIGNAL at Close[i]
        row_scores = scores.iloc[i]
        ranked = row_scores.sort_values(ascending=False)
        top_score = ranked.iloc[0]
        
        target_holdings = []
        if top_score > 0:
            cands = ranked[ranked > 0]
            count = min(len(cands), TOP_N)
            if count > 0:
                target_holdings = list(cands.index[:count])
                
        # 2. EXECUTION at Open[i+1]
        # Calculate return from Previous Execution (Open[i]) to Current Execution (Open[i+1])
        # Only if we held something.
        
        # But wait, we need to track "What we held from Open[i] to Open[i+1]"
        # current_holdings is what we decided at Close[i-1] to hold starting Open[i].
        
        step_ret = 0.0
        if len(current_holdings) > 0:
            weight = 1.0 / TOP_N
            for asset in current_holdings:
                # Return = (Open[i+1] - Open[i]) / Open[i]
                p_open_now = df_open[asset].iloc[i+1]
                p_open_prev = df_open[asset].iloc[i]
                
                r = (p_open_now - p_open_prev) / p_open_prev
                step_ret += r * weight
        
        # 3. APPLY FRICTION
        # Did we change holdings?
        # Target vs Current
        # Turnover calculation
        turnover = 0.0
        # Simple Check: Any change?
        # Real logic: Total Turnover
        curr_set = set(current_holdings)
        targ_set = set(target_holdings)
        
        # If I held A,B. Now A,C. I sold B, Bought C. Turnover 50%.
        # Friction applied on Turnover portion.
        # If I hold nothing (Cash). Buy A,B. Turnover 100%.
        
        # Change calculation
        changes = len(curr_set.symmetric_difference(targ_set))
        # Total slots = 2 * TOP_N (Buy + Sell sides max)
        # Simplify: If holdings changed, apply Friction to the *changed portion*.
        # Fraction Changed = changes / (2 * TOP_N) ? No.
        # If A,B -> A,C. 1 sell, 1 buy. 2 ops. Portfolio size 2. 50% rotated.
        # Friction * 0.5.
        
        if len(target_holdings) == 0 and len(current_holdings) == 0:
            fraction_rotated = 0.0
        else:
            # Approx logic
            fraction_rotated = 0.0
            if curr_set != targ_set:
                # Conservative: Look at set diff
                diff = len(curr_set.symmetric_difference(targ_set))
                # Max diff is 4 (A,B -> C,D). 2 sells, 2 buys. 100% rotation.
                # If diff is 2 (A,B -> A,C). 1 sell, 1 buy. 50% rotation.
                fraction_rotated = diff / (2 * TOP_N)
                
        cost = fraction_rotated * FRICTION
        
        # Update Equity
        equity *= (1 + step_ret) * (1 - cost)
        equity_curve.append(equity)
        
        # Log
        if i % 100 == 0:
            h1 = target_holdings[0] if len(target_holdings)>0 else "CASH"
            h2 = target_holdings[1] if len(target_holdings)>1 else ""
            print(f"{next_open_date.strftime('%Y-%m-%d'):<12} {h1:<10} {h2:<10} {equity:.2f}x")
            
        # Update state for next loop
        current_holdings = target_holdings

    # Final Stats
    final_ret = equity_curve[-1] - 1
    days = len(equity_curve)
    cagr = ((1 + final_ret) ** (365/days)) - 1
    
    # Drawdown Calculation (Percentage)
    eq_series = pd.Series(equity_curve, index=df_close.index[LOOKBACK+1:]) 
    # Align index length: loop i from LOOKBACK to len-1. 
    # eq_curve has len = len(df_close) - 1 - LOOKBACK.
    
    peak = eq_series.cummax()
    drawdown = (eq_series - peak) / peak
    max_dd = drawdown.min()

    # Yearly Returns
    print("\n--- YEARLY PERFORMANCE ---")
    print(f"{'YEAR':<6} {'RETURN':<10}")
    print("-" * 20)
    
    # Resample to Yearly
    yearly = eq_series.resample('Y').last()
    yearly_ret = yearly.pct_change()
    # First year return: yearly[0] / 1.0 - 1
    yearly_ret.iloc[0] = yearly.iloc[0] / 1.0 - 1
    
    for date, ret in yearly_ret.items():
        print(f"{date.year:<6} {ret*100:>8.2f}%")
    print("-" * 20)

    print("-" * 60)
    print(f"RIGOROUS BACKTEST (Open-to-Open Execution + 0.2% Friction)")
    print(f"CAGR: {cagr*100:.2f}%")
    print(f"MAX DD: {max_dd*100:.2f}%")
    print(f"TOTAL RETURN: {equity_curve[-1]:.2f}x")

    
    # Sharpe Ratio (Daily)
    daily_rets_strat = eq_series.pct_change().dropna()
    sharpe = (daily_rets_strat.mean() / daily_rets_strat.std()) * np.sqrt(252)
    print(f"SHARPE RATIO: {sharpe:.2f}")

    if cagr > 0.30:
        print("VERDICT: PASSED (>30%)")
    else:
        print("VERDICT: FAILED")
    print("-" * 60)

if __name__ == "__main__":
    run_rigorous_backtest()
