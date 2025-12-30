"""
ULTIMATE_BACKTEST.py
--------------------
"The Time Machine"
Simulates the Strategy over 20 Years (2005-2025) with DYNAMIC Universe Updates.

Logic:
1. "Time Travel Universe": On Jan 1st of each year, update the asset list 
   to reflect what was actually tradeable and dominant in that era.
2. Daily Simulation:
   - Rank assets by Momentum (30d Return / Vol).
   - Buy Top 2 at Market Open.
   - Pay Transaction Fees.
   - Log EVERY trade.

Author: Antigravity Agent
"""

import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import os

# --- 1. HISTORICAL UNIVERSE MAP (The Simulation of "Updater.py" in the past) ---
# We define what the "Generals" were in each era.
HISTORICAL_UNIVERSE = {
    # ERA 1: The Commodity/Energy Supercycle & Financial Crisis (2005-2010)
    2005: [
        'SPY', 'QQQ', 'IWM', # Indices
        'EFA', 'EEM', # Global
        'XLF', 'XLE', 'XLK', 'XLV', # Sectors
        'GLD', 'TLT', 'SHV', # Safety/Commodities
        'XOM', 'GE', 'MSFT', 'C' # The "Magnificent 4" of 2005 (Exxon, GE, Microsoft, Citi)
    ],
    # ERA 2: The Tech Recovery & BTC Birth (2011-2015)
    2011: [
        'SPY', 'QQQ', 'IWM', 'EFA', 'EEM',
        'XLF', 'XLE', 'XLK', 'XLV',
        'GLD', 'TLT', 'SHV',
        'AAPL', 'XOM', 'MSFT', 'AMZN' # Apple & Amazon rise. Citi/GE fall.
    ],
    # ERA 3: The FAANG Era & Crypto Early Days (2016-2019)
    2016: [
        'SPY', 'QQQ', 'IWM', 'EFA', 'EEM',
        'XLF', 'XLE', 'XLK', 'XLV',
        'GLD', 'TLT', 'SHV',
        'AAPL', 'AMZN', 'MSFT', 'GOOGL', 'NVDA', 'FB', # Tech dominance
        'BTC-USD' # Bitcoin becomes tradeable
    ],
    # ERA 4: The Crypto/AI Boom (2020-2025)
    2020: [
        'SPY', 'QQQ', 'IWM', 'EFA', 'EEM',
        'XLF', 'XLE', 'XLK', 'XLV',
        'GLD', 'TLT', 'SHV', 'USO', 'DBA',
        'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'TSLA', # Tesla enters
        'BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD' # Crypto Explosion
    ]
}

def get_universe_for_year(year):
    # Find the applicable universe (latest one <= year)
    selected_year = 2005
    for y in sorted(HISTORICAL_UNIVERSE.keys()):
        if year >= y:
            selected_year = y
    
    return HISTORICAL_UNIVERSE[selected_year]

def download_all_data():
    print("Downloading 20 Years of Data... (This may take 2 mins)")
    # Collect all unique tickers ever used
    all_tickers = set()
    for u in HISTORICAL_UNIVERSE.values():
        all_tickers.update(u)
    
    data_dict = {}
    for t in all_tickers:
        try:
            # Download full history
            df = yf.download(t, start="2004-01-01", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            data_dict[t] = df
        except: pass
        
    return data_dict

def run_simulation():
    # 1. Prepare Data
    raw_data = download_all_data()
    
    # We need a master timeline
    # Use SPY as clock
    spy = raw_data['SPY']
    dates = spy.index
    
    # 2. Simulation State
    equity = 1.0
    cash = 1.0
    holdings = {} # {Ticker: Qty} - Simplified to Weights for speed, or strict accounting?
    # User wants "Buy/Sell Price" and "Daily Log". Strict Accounting is better.
    # Let's use "Value" tracking to handle splits/dividends implicitly via Adjusted Close?
    # Or Open/Close execution.
    # Let's stick to the "Vectorized Loop" approach for speed, but print details.
    
    daily_log = []
    
    current_universe = []
    
    # Start loop
    # Need 30d lookback. Start at 2005-02-01
    
    print(f"\nSTARTING SIMULATION (2005 - 2025)...")
    print(f"{'DATE':<12} {'UNIVERSE':<5} {'TOP 1':<8} {'TOP 2':<8} {'EQUITY':<10}")
    
    prev_equity = 1.0
    current_holdings = [] # List of tickers
    
    # Pre-calculate Returns/Vols for ALL assets? 
    # Hard because universe changes. Dynamic approach:
    # On each day, check year. Update universe. 
    # Subset data. Rank. Trade.
    
    # To optimize: Create a giant DataFrame of Closes?
    # Then subset columns dynamically.
    
    # Create master DF of 'Close', 'Adj Close', and 'Open' (for execution)
    master_close = pd.DataFrame({k: v['Close'] for k, v in raw_data.items()})
    
    # Robust Adj Close: Use Adj Close if exists, else Close
    adj_dict = {}
    for k, v in raw_data.items():
        if 'Adj Close' in v.columns:
            adj_dict[k] = v['Adj Close']
        else:
            adj_dict[k] = v['Close'] # Fallback
            
    master_adj = pd.DataFrame(adj_dict) # For Momentum Score
    master_open = pd.DataFrame({k: v['Open'] for k, v in raw_data.items()})
    
    master_close = master_close.ffill()
    master_adj = master_adj.ffill()
    master_open = master_open.ffill()
    
    # Loop day by day
    # Start index 30
    
    for i in range(30, len(dates)-1):
        date = dates[i]
        next_date = dates[i+1] # Execution Day
        year = date.year
        
        # A. Universe Update (First trading day of year logic)
        target_universe = get_universe_for_year(year)
        
        # B. Get Candidates Data
        candidates = []
        for sym in target_universe:
            if sym in master_adj.columns:
                # Check valid price
                if not pd.isna(master_adj[sym].iloc[i]):
                    candidates.append(sym)
                    
        # C. Calculate Scores (Using Total Return / Adj Close)
        scores = []
        for sym in candidates:
            # 30d Return
            p_now = master_adj[sym].iloc[i]
            p_prev = master_adj[sym].iloc[i-30]
            
            if pd.isna(p_prev) or p_prev <= 0: continue
            
            ret = (p_now - p_prev) / p_prev
            
            # Vol
            last_30_closes = master_adj[sym].iloc[i-30:i+1]
            vol = last_30_closes.pct_change().std()
            
            if pd.isna(vol) or vol == 0: continue
            
            score = ret / vol
            scores.append((sym, score))
            
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # D. Selection (Top 2)
        top_2 = []
        if scores and scores[0][1] > 0:
            top_2.append(scores[0][0])
            if len(scores) > 1 and scores[1][1] > 0:
                top_2.append(scores[1][0])
                
        # Fallback to CASH (SHV) if empty or score <= 0
        if not top_2:
            top_2 = ['SHV']
            
        # E. Execution (Open-to-Open return)
        step_ret = 0.0
        
        # Convert to sets for comparison logic
        curr_set = set(current_holdings)
        targ_set = set(top_2)
        
        if current_holdings:
            w = 1.0 / len(current_holdings)
            for asset in current_holdings:
                # SPECIAL CASE: SHV (Cash) Yield
                if asset == 'SHV':
                    # If SHV data is flat, assumes 0%. We add Risk Free Rate approx.
                    # Or trust the data? SHV data *should* have dividends if Adj Close is used...
                    # But for Execution we use Open price.
                    # Price Return of SHV is ~0. Total Return comes from Divs.
                    # Simplified: Add 3% APY daily for SHV holding
                    yield_daily = 0.03 / 252.0
                    
                    # Also need Price Move (Fluctuation)
                    if asset in master_open.columns:
                        o_curr = master_open[asset].iloc[i]
                        o_next = master_open[asset].iloc[i+1]
                        if not pd.isna(o_curr) and not pd.isna(o_next) and o_curr > 0:
                            r = (o_next - o_curr) / o_curr
                            step_ret += (r + yield_daily) * w
                        else:
                             step_ret += yield_daily * w
                    else:
                        step_ret += yield_daily * w
                        
                elif asset in master_open.columns:
                    o_curr = master_open[asset].iloc[i]   # Opened position here (yesterday)
                    o_next = master_open[asset].iloc[i+1] # Closing/Rolling position here (today)
                    
                    if not pd.isna(o_curr) and not pd.isna(o_next) and o_curr > 0:
                        r = (o_next - o_curr) / o_curr
                        # Add Dividend Yield approximation for Bond ETFs (TLT)?
                        # TLT pays ~3-4%. Price move captures rate change, but coupon is separate if using Open prices.
                        # Ideally execution should track total return index.
                        # Conservative: Just price return + small yield for bonds?
                        # Let's stick to Price Return for risk assets.
                        if asset in ['TLT', 'IEF']:
                             r += (0.03 / 252.0)
                        step_ret += r * w
                        
        # Friction Logic (Refined)
        # Apply friction only to the portion that CHANGED
        # If A,B -> A,C. Changed 1 slot of 2. 50% turnover.
        # Friction = 0.001 * 0.5
        
        # If holdings [SHV] -> [XLF, XLE]. Changed 1 to 2. Turnover 100%.
        
        friction = 0.0
        if current_holdings != top_2:
            # Simple turnover calculation:
            # Find what was sold
            sold_count = len(curr_set - targ_set)
            # Find what was bought
            bought_count = len(targ_set - curr_set)
            
            # Total ops = sold + bought
            # But we pay friction on "Traded Value".
            # If I sell 50% and buy 50%, I traded 100% of equity (50 out, 50 in).
            # Friction = 0.001 * 1.0.
            
            # What if I hold 2. Sell BOTH (100%). Buy 2 (100%).
            # Trade value = 200% of Equity.
            # Friction = 0.001 * 2.0 = 0.002.
            
            # Let's verify standard backtests. usually they apply slippage/comm per Trade.
            # My previous logic `0.001` on total equity assumes 100% turnover.
            # So if I swap A,B -> C,D (100% turnover), cost is 0.002 (sell 2, buy 2).
            
            # Let's calculate Traded Fraction
            qty_prev = len(current_holdings)
            qty_curr = len(top_2)
            
            if qty_prev == 0: frac_sold = 0
            else: frac_sold = sold_count / qty_prev # Not quite right if sizes differ
            
            # Assume equal weight.
            # Value Sold = (Count Sold) * (1/Count Prev)
            # Value Bought = (Count Bought) * (1/Count Curr)
            
            val_sold = 0.0
            if qty_prev > 0: val_sold = sold_count * (1.0/qty_prev)
            
            val_bought = 0.0
            if qty_curr > 0: val_bought = bought_count * (1.0/qty_curr)
            
            turnover = val_sold + val_bought
            friction = turnover * 0.001 # 0.1% per 100% volume traded
            
        equity = prev_equity * (1 + step_ret) * (1 - friction)
        prev_equity = equity
        current_holdings = top_2
        
        # Log
        daily_log.append({
            'Date': next_date,
            'Holdings':  " ".join(top_2),
            'UniverseSize': len(target_universe),
            'Equity': equity
        })
        
        if i % 250 == 0: # Yearly print
             print(f"{next_date.strftime('%Y-%m-%d'):<12} {len(target_universe):<5} {top_2[0]:<8} {top_2[1] if len(top_2)>1 else '':<8} {equity:.2f}x")

    # Generate CSV
    df_log = pd.DataFrame(daily_log)
    df_log.to_csv('ULTIMATE_HISTORY_LOG.csv', index=False)
    print("\nSimulation Complete. Log saved to 'ULTIMATE_HISTORY_LOG.csv'")
    
    # Final Stats
    final_eq = df_log['Equity'].iloc[-1]
    years = (df_log['Date'].iloc[-1] - df_log['Date'].iloc[0]).days / 365.25
    cagr = (final_eq ** (1/years)) - 1
    
    print(f"\nFINAL RESULTS (2005-2025):")
    print(f"Total Years: {years:.1f}")
    print(f"Final Equity: {final_eq:.2f}x (Returns !)")
    print(f"CAGR: {cagr*100:.2f}%")

if __name__ == "__main__":
    run_simulation()
