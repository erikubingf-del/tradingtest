import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. The 21-Asset "Super Universe" ---
TICKERS = {
    # Crypto (Direct)
    'Bitcoin': 'BTC-USD',
    'Ethereum': 'ETH-USD',
    'Coinbase (Sol Proxy)': 'COIN',
    
    # Indices
    'S&P 500': 'SPY',
    'Nasdaq': 'QQQ',
    'Russell 2000': 'IWM',
    
    # Sector ETFs
    'Tech': 'XLK',
    'Finance': 'XLF',
    'Energy': 'XLE',
    'Healthcare': 'XLV',
    
    # Stocks
    'NVIDIA': 'NVDA',
    'Apple': 'AAPL',
    'Microsoft': 'MSFT',
    'Amazon': 'AMZN',
    
    # International
    'Developed': 'EFA',
    'Emerging': 'EEM',
    
    # Commodities
    'Gold': 'GLD',
    'Oil': 'USO',
    'Agriculture': 'DBA',
    
    # Bonds/Cash
    'Treasury': 'TLT',
    'Dollar': 'UUP'
}

START_DATE = '2015-01-01'
END_DATE = '2025-12-28'

# --- Configuration ---
TOP_N = 3 # Hold Top 3
LOOKBACK = 45 # 45 Day Momentum (User Specification)
REBALANCE_FEE = 0.001 # 0.1%

def analyze_strategy():
    print(f"Downloading {len(TICKERS)} Assets...")
    data_dict = {}
    for name, ticker in TICKERS.items():
        try:
            df = yf.download(ticker, start=START_DATE, end=END_DATE, interval='1d', progress=False)
            if len(df) > 100:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                series = df['Close']
                series.name = name
                data_dict[name] = series
        except: pass
            
    df = pd.DataFrame(data_dict).fillna(method='ffill').dropna()
    print(f"Data Aligned: {len(df)} days. Assets: {len(df.columns)}")

    # 1. Momentum Score (Return / Vol)
    # User Spec: Lookback 45
    scores = pd.DataFrame(index=df.index, columns=df.columns)
    for col in df.columns:
        ret = df[col].pct_change(LOOKBACK)
        vol = df[col].pct_change().rolling(LOOKBACK).std()
        scores[col] = ret / (vol + 1e-9)
    scores = scores.fillna(0)

    # 2. Simulation
    equity = 1.0
    equity_curve = [1.0]
    
    # Track Holdings (Set of names)
    current_holdings = set()
    daily_rets = df.pct_change()
    
    for i in range(len(df) - 1):
        # Decision for tomorrow (i+1) based on today (i)
        current_scores = scores.iloc[i]
        
        # Rank: Sort descending
        ranked = current_scores.sort_values(ascending=False)
        
        # Select Top N (Score > 0)
        valid_candidates = ranked[ranked > 0]
        
        next_holdings = []
        if len(valid_candidates) >= TOP_N:
             next_holdings = list(valid_candidates.index[:TOP_N])
        elif len(valid_candidates) > 0:
             # If less than 3 valid, hold what is valid, rest Cash
             next_holdings = list(valid_candidates.index)
        else:
             next_holdings = [] # All Cash
             
        # Convert to Set for comparison
        next_set = set(next_holdings)
        
        # Calc Return
        # Equal Weight Logic: 1/3 each
        # If holding 2 assets, 1/3 each, 1/3 cash? Or 1/2? 
        # User said "Top 3 assets (33% each)". Implies 33% cash if no asset.
        
        step_ret = 0.0
        
        count = len(next_holdings)
        if count > 0:
            avg_ret = 0.0
            for asset in next_holdings:
                 asset_ret = daily_rets[asset].iloc[i+1]
                 avg_ret += asset_ret
            # Return is (Sum of Asset Returns) / 3 (Fixed 33% Allocation)
            # Implies 100% invested only if 3 assets.
            # If 2 assets -> 66% invested.
            step_ret = avg_ret / TOP_N 
        else:
            step_ret = 0.0 # 100% Cash
            
        # Fees: Apply fee for any NEW asset entered
        # Turnover calculation
        # Simplified: If asset in next but not current -> Fee
        fee_hit = 0.0
        for asset in next_set:
            if asset not in current_holdings:
                fee_hit += REBALANCE_FEE * (1.0/TOP_N) # Fee on that slice
                
        # Net
        equity *= (1 + step_ret) - fee_hit
        equity_curve.append(equity)
        current_holdings = next_set

    final_ret = equity_curve[-1] - 1
    days = len(equity_curve)
    cagr = ((1 + final_ret) ** (365/days)) - 1
    
    peak = pd.Series(equity_curve).cummax()
    dd = (pd.Series(equity_curve) - peak) / peak
    max_dd = dd.min()
    
    print("-" * 60)
    print(f"STRATEGY: 21 Assets / Top {TOP_N} / Lookback {LOOKBACK}")
    print(f"CAGR: {cagr*100:.2f}%")
    print(f"MAX DD: {max_dd*100:.2f}%")
    print(f"TOTAL RETURN: {equity_curve[-1]:.2f}x")
    print("-" * 60)

analyze_strategy()
