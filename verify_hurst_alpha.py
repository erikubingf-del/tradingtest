import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. The "Energy" Universe ---
# "Paid in Energy" -> We trade the sources of Energy and Compute.
TICKERS = {
    'Bitcoin (Digital Energy)': 'BTC-USD',
    'Oil (Physical Energy)': 'CL=F',
    'Nasdaq (Compute/AI)': 'QQQ',
    'NVIDIA (The Engine)': 'NVDA' 
}

START_DATE = '2015-01-01'
END_DATE = '2025-12-28'

# --- 2. Advanced Technique: Fractal Geometry (Hurst Exponent) ---
def get_hurst_exponent(time_series, max_lag=20):
    """
    Returns the Hurst Exponent of the time series vector ts.
    H < 0.5 = Mean Reverting (Kill Trade)
    H = 0.5 = Random Walk (Kill Trade)
    H > 0.5 = Trending (Persistent) -> TRADE
    """
    lags = range(2, max_lag)
    tau = [np.sqrt(np.std(np.subtract(time_series[lag:], time_series[:-lag]))) for lag in lags]
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    return poly[0] * 2.0

def run_advanced_strategy(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df.columns = [c.lower() for c in df.columns]

    # Pre-calc Indicators
    df['ret'] = df['close'].pct_change()
    
    # 1. Regime Filter: Hurst Exponent (Rolling)
    # This is computationally expensive, so we use a simplified rolling window approach
    # We calculate it over a lookback window (e.g. 100 days) to determine current regime
    
    hurst_values = []
    closes = df['close'].values
    lookback = 100
    
    for i in range(len(df)):
        if i < lookback:
            hurst_values.append(0.5) # Default neutral
            continue
            
        # Get slice
        slice_ts = closes[i-lookback:i]
        
        # Simplified R/S Analysis approximation for speed in loop
        # Or standard Rescaled Range for robustness
        # Using variance ratio logic relative to simple lag
        
        # Fast Proxy for Hurst: Variance Ratio Test logic
        # If Var(2*lag) / Var(lag) scales with 2^(2H)
        # We'll use a standard Hurst func implementation within reason
        
        try:
            # Calculate actual Hurst for this window
            # Using simple lag difference logic
            lags = [2, 10]
            variances = []
            for lag in lags:
                # diff = slice_ts[lag:] - slice_ts[:-lag] 
                # Faster:
                diff = np.diff(slice_ts[::lag]) # Decimated diff for speed proxy
                if len(diff) < 2:
                    variances.append(0)
                else:
                    variances.append(np.var(diff))
            
            if variances[0] > 0 and variances[1] > 0:
                # H = 0.5 * log(Var(t*lag)/Var(lag)) / log(t) ? 
                # Standard relationship: Var(tau) ~ tau^(2H)
                # log(Var) = 2H * log(tau) + C
                # Slope = 2H
                # H = Slope / 2
                x = np.log(lags)
                y = np.log(variances)
                slope = (y[1]-y[0]) / (x[1]-x[0])
                h = slope / 2.0
            else:
                h = 0.5
                
            hurst_values.append(h)
        except:
            hurst_values.append(0.5)
            
    df['hurst'] = hurst_values
    
    # 2. Trend Signal: Exponential Trend
    df['ema_short'] = df['close'].ewm(span=20).mean()
    df['ema_long'] = df['close'].ewm(span=50).mean()
    
    signals = []
    
    for i in range(len(df)):
        if i < lookback: 
            signals.append(0)
            continue
            
        h_val = df['hurst'].iloc[i]
        c = df['close'].iloc[i]
        ema = df['ema_long'].iloc[i]
        
        # THE ADVANCED LOGIC:
        # Only trade if Market Memory (Hurst) proves Structure (> 0.55)
        # AND Price confirms Momentum
        if h_val > 0.55 and c > ema:
            signals.append(1) # Long
        else:
            signals.append(0) # Cash (Exit Non-Profit structure instantly)
            
    df['signal'] = signals
    
    # Returns
    df['strat_ret'] = df['ret'] * df['signal'].shift(1)
    df['cum_ret'] = (1 + df['strat_ret']).cumprod()
    
    total = df['cum_ret'].iloc[-1] - 1
    days = (df.index[-1] - df.index[0]).days
    cagr = ((1 + total) ** (365/days)) - 1
    
    peak = df['cum_ret'].cummax()
    dd = (df['cum_ret'] - peak) / peak
    max_dd = dd.min()
    
    return cagr * 100, max_dd * 100

# --- Exec ---
print(f"{'ASSET (ENERGY)':<25} {'CAGR %':<10} {'MAX DD %':<10} {'RESULT'}")
print("-" * 60)

avg_cagr = 0
count = 0

for name, ticker in TICKERS.items():
    try:
        data = yf.download(ticker, start=START_DATE, end=END_DATE, interval='1d', progress=False)
        if len(data) < 200: continue
        
        cagr, dd = run_advanced_strategy(data)
        
        print(f"{name:<25} {cagr:>6.2f}% {dd:>8.2f}%")
        avg_cagr += cagr
        count += 1
    except Exception as e:
        print(e)
        
print("-" * 60)
if count > 0:
    print(f"{'PORTFOLIO AVERAGE':<25} {avg_cagr/count:>6.2f}%")
