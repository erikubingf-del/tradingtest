import yfinance as yf
import pandas as pd
import numpy as np

# --- Configuration ---
TICKERS = {
    'S&P 500': 'SPY',
    'Nasdaq': 'QQQ',
    'Gold': 'GC=F',
    'Oil': 'CL=F',
    'Bitcoin': 'BTC-USD'
}

START_DATE = '2015-01-01'
END_DATE = '2025-12-28'
TARGET_VOL = 0.20

def run_strategy(df):
    # Data Clean
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df.columns = [c.lower() for c in df.columns]
    
    # 1. Volatility Sizing
    df['ret'] = df['close'].pct_change()
    df['vol'] = df['ret'].rolling(20).std() * np.sqrt(252)
    df['vol'] = df['vol'].fillna(0.20) # Default to 20%
    
    # Logic: Size = Target / Vol
    df['size'] = TARGET_VOL / df['vol']
    df['size'] = df['size'].clip(upper=2.0) # Cap leverage at 2x
    
    # 2. Donchian Trend
    df['high_20'] = df['high'].rolling(20).max().shift(1)
    df['low_10'] = df['low'].rolling(10).min().shift(1)
    
    # 3. Signals
    signals = []
    in_trade = False
    
    closes = df['close'].values
    highs = df['high'].values
    high_20 = df['high_20'].values
    low_10 = df['low_10'].values
    
    for i in range(len(df)):
        if i < 25: 
            signals.append(0)
            continue
            
        c = closes[i]
        h = highs[i]
        entry = high_20[i]
        exit_val = low_10[i]
        
        if np.isnan(entry):
            signals.append(0)
            continue
            
        sig = 0
        if not in_trade:
            if c > entry:
                in_trade = True
                sig = 1
        else:
            if c < exit_val:
                in_trade = False
                sig = 0
            else:
                sig = 1 # Hold
        
        signals.append(sig)

    df['signal'] = signals
    
    # 4. Returns
    df['strat_ret'] = df['ret'] * df['size'].shift(1) * df['signal'].shift(1)
    df['cum_ret'] = (1 + df['strat_ret']).cumprod()
    
    total = df['cum_ret'].iloc[-1] - 1
    days = (df.index[-1] - df.index[0]).days
    cagr = ((1 + total) ** (365/days)) - 1
    
    peak = df['cum_ret'].cummax()
    dd = (df['cum_ret'] - peak) / peak
    max_dd = dd.min()
    avg_size = df[df['signal']==1]['size'].mean()
    
    return cagr*100, max_dd*100, avg_size

# --- Exec ---
print(f"{'ASSET':<15} {'CAGR %':<10} {'MAX DD %':<10} {'AVG SIZE':<10} {'STATUS'}")
print("-" * 65)

for name, ticker in TICKERS.items():
    try:
        data = yf.download(ticker, start=START_DATE, end=END_DATE, interval='1d', progress=False)
        if len(data) < 100: continue
        
        cagr, dd, size = run_strategy(data)
        
        status = "✅ STABLE" if abs(dd) < 35 else "⚠️ VOLATILE"
        print(f"{name:<15} {cagr:>6.2f}% {dd:>8.2f}% {size:>8.2f}x  {status}")
        
    except Exception as e:
        print(f"{name} ERR: {e}")
