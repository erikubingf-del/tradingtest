import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. The Survival Universe ---
TICKERS = {
    'Bitcoin': 'BTC-USD',
    'Ethereum': 'ETH-USD',
    'Nasdaq': 'QQQ',
    'S&P 500': 'SPY',
    'Gold': 'GC=F',
    'Oil': 'CL=F',
    'CashProxy': 'SHV' 
}

START_DATE = '2015-01-01'
END_DATE = '2025-12-28'

def run_rotational_strategy():
    # 1. Download & Align
    data_dict = {}
    
    print("Downloading Data...")
    for name, ticker in TICKERS.items():
        try:
            df = yf.download(ticker, start=START_DATE, end=END_DATE, interval='1d', progress=False)
            if len(df) > 100:
                # Handle MultiIndex
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                
                # Use Close
                series = df['Close']
                series.name = name
                data_dict[name] = series
        except Exception as e:
            print(f"Failed {name}: {e}")
            
    if not data_dict:
        print("No Data Found.")
        return 0, 0
        
    # Align to DataFrame (Outer join to keep all days, then ffill)
    df = pd.DataFrame(data_dict)
    df = df.fillna(method='ffill').dropna() # Drop initial NaNs
    
    print(f"Data Aligned: {len(df)} days.")
    
    # 2. Strategy Logic: Rotational Momentum
    # Score = 20d Return / 20d Volatility
    scores = pd.DataFrame(index=df.index, columns=df.columns)
    
    for col in df.columns:
        ret_20 = df[col].pct_change(20)
        vol_20 = df[col].pct_change().rolling(20).std()
        
        # Avoid div by zero
        scores[col] = ret_20 / (vol_20 + 1e-9)
        
    scores = scores.fillna(0)
    
    # Simulation
    daily_rets = df.pct_change()
    
    portfolio_value = 1.0
    equity_curve = [1.0]
    
    # Track which asset we are in
    current_asset = None
    transaction_cost = 0.001 # 0.1% Fee per trade (Buy + Sell spread avg)
    
    for i in range(len(df) - 1):
        # Decision for tomorrow (i+1) based on today (i)
        current_scores = scores.iloc[i]
        
        # Pick Top 1 with Score > 0
        valid_scores = current_scores[current_scores > 0]
        
        next_asset = None
        if len(valid_scores) == 0:
            next_asset = "CASH"
        else:
            next_asset = valid_scores.idxmax()
            
        # Calc Return
        step_ret = 0.0
        if next_asset == "CASH":
            step_ret = 0.0 # Treasury yield could be added here
        else:
            step_ret = daily_rets[next_asset].iloc[i+1]
            
        # Apply Fee if Rotation occurred
        fee = 0.0
        if next_asset != current_asset:
            fee = transaction_cost
            
        # Net Multiplier
        portfolio_value *= (1 + step_ret) * (1 - fee)
        
        equity_curve.append(portfolio_value)
        current_asset = next_asset
        
    equity_curve = pd.Series(equity_curve, index=df.index)
    
    # Stats
    total_ret = equity_curve.iloc[-1] - 1
    days = (equity_curve.index[-1] - equity_curve.index[0]).days
    cagr = ((1 + total_ret) ** (365/days)) - 1
    
    peak = equity_curve.cummax()
    dd = (equity_curve - peak) / peak
    max_dd = dd.min()
    
    return cagr * 100, max_dd * 100

# --- Exec ---
print(f"{'STRATEGY':<25} {'CAGR %':<10} {'MAX DD %':<10}")
print("-" * 60)

cagr, dd = run_rotational_strategy()
print(f"{'ROTATIONAL GLOBAL':<25} {cagr:>6.2f}% {dd:>8.2f}%")
print("-" * 60)
