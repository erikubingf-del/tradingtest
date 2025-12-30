import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. The Survival Universe ---
TICKERS = {
    'Bitcoin': 'BTC-USD',
    'Ethereum': 'ETH-USD',
    'Nasdaq (Growth)': 'QQQ',
    'S&P 500 (Stability)': 'SPY',
    'Gold (Safety)': 'GC=F',
    'Oil (Resource)': 'CL=F',
    'Cash (Treasury)': 'SHV' 
}

START_DATE = '2015-01-01'
END_DATE = '2025-12-28'

def analyze_strategy():
    # 1. Download
    print("Downloading Data for Investigation...")
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
    print(f"Data Loaded: {len(df)} days.")

    # 2. Logic: Momentum Score
    scores = pd.DataFrame(index=df.index, columns=df.columns)
    for col in df.columns:
        ret_20 = df[col].pct_change(20)
        vol_20 = df[col].pct_change().rolling(20).std()
        scores[col] = ret_20 / (vol_20 + 1e-9)
    scores = scores.fillna(0)

    # 3. Simulation with Trade Log
    current_asset = "CASH"
    equity = 1.0
    equity_curve = []
    trade_log = []
    
    daily_rets = df.pct_change()
    
    print("-" * 80)
    print(f"{'DATE':<12} {'FROM':<15} {'TO':<15} {'REASON (New Score)'}")
    print("-" * 80)
    
    for i in range(len(df) - 1):
        date = df.index[i].strftime('%Y-%m-%d')
        
        # Decision
        valid_scores = scores.iloc[i][scores.iloc[i] > 0]
        next_asset = "Cash (Treasury)" # Default safety
        
        if len(valid_scores) > 0:
            next_asset = valid_scores.idxmax()
            best_score = valid_scores.max()
        else:
            best_score = 0.0
            
        # Switch Logic
        if next_asset != current_asset:
            # Log the Trade
            print(f"{date:<12} {str(current_asset):<15} {str(next_asset):<15} Score: {best_score:.2f}")
            trade_log.append({
                'Date': date,
                'From': current_asset,
                'To': next_asset,
                'Score': best_score,
                'Equity': equity
            })
            
        # PnL
        ret = 0.0
        if next_asset != "Cash (Treasury)" and next_asset != "CASH":
            ret = daily_rets[next_asset].iloc[i+1]
        
        # 0.1% Fee on Switch
        fee = 0.001 if next_asset != current_asset else 0.0
        
        equity *= (1 + ret) * (1 - fee)
        equity_curve.append(equity)
        current_asset = next_asset

    final_ret = equity_curve[-1] - 1
    days = len(equity_curve)
    cagr = ((1 + final_ret) ** (365/days)) - 1
    
    print("-" * 80)
    print(f"FINAL CAGR: {cagr*100:.2f}%")
    print(f"FINAL EQUITY: {equity_curve[-1]:.2f}x")

# Run
analyze_strategy()
