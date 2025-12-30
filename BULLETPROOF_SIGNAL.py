import yfinance as yf
import pandas as pd
import sys
import shutil
import os
from datetime import datetime, timedelta

# --- 1. Bulletproof Config ---
# Clear Cache to ensure fresh data
def clear_cache():
    cache_dir = os.path.expanduser("~/.cache/py-yfinance")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print("CACHE CLEARED: ~/.cache/py-yfinance")
        except:
            print("WARNING: Could not clear cache.")

# Universe
TICKERS = {
    'BTC': 'BTC-USD', 'ETH': 'ETH-USD', 'SOL': 'SOL-USD', 'BNB': 'BNB-USD',
    'SPY': 'SPY', 'QQQ': 'QQQ', 'IWM': 'IWM',
    'XLK': 'XLK', 'XLF': 'XLF', 'XLE': 'XLE', 'XLV': 'XLV',
    'NVDA': 'NVDA', 'AAPL': 'AAPL', 'MSFT': 'MSFT', 'AMZN': 'AMZN', 'GOOGL': 'GOOGL',
    'EFA': 'EFA', 'EEM': 'EEM',
    'GLD': 'GLD', 'USO': 'USO', 'DBA': 'DBA',
    'TLT': 'TLT', 'UUP': 'UUP', 'SHV': 'SHV'
}

LOOKBACK = 120
TOP_N = 2

def get_bulletproof_signal():
    clear_cache()
    
    print(f"Signal Generation Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Downloading Fresh Data for {len(TICKERS)} Assets...")
    
    data_dict = {}
    # Download extra buffer
    start_date = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d')
    
    for name, ticker in TICKERS.items():
        try:
            df = yf.download(ticker, start=start_date, progress=False)
            if len(df) > 30:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                series = df['Close']
                series.name = name
                data_dict[name] = series
        except: pass
        
    df = pd.DataFrame(data_dict).fillna(method='ffill').dropna()
    
    # 2. Validate Freshness
    latest_date = df.index[-1]
    days_old = (datetime.now() - latest_date).days
    
    print(f"Data As Of: {latest_date.strftime('%Y-%m-%d')}")
    
    if days_old > 4: # Allow weekend + holiday buffer (3-4 days max)
        print(f"CRITICAL WARNING: Data is {days_old} days old! Signal may be STALE.")
    else:
        print("Data is FRESH.")
        
    # 3. Calculate Scores
    scores = []
    
    for col in df.columns:
        series = df[col]
        
        # SMA Filter (200 Day)
        if len(series) < 200: continue
        sma = series.rolling(200).mean().iloc[-1]
        p_now = series.iloc[-1]
        
        if p_now < sma:
             continue # Fails Trend Filter
             
        p_prev = series.iloc[-1 - LOOKBACK]
        
        # Return
        ret = (p_now - p_prev) / p_prev
        
        # Vol
        daily_rets = series.pct_change().iloc[-LOOKBACK:]
        vol = daily_rets.std()
        
        score = ret / (vol + 1e-9)
        scores.append((col, score, p_now, ret))
        
    # Rank
    scores.sort(key=lambda x: x[1], reverse=True)
    
    # Output
    print("\n--- SIGNAL REPORT ---")
    print(f"{'RANK':<5} {'ASSET':<6} {'SCORE':<8} {'RET(30d)':<10} {'PRICE':<10}")
    print("-" * 50)
    
    for i, item in enumerate(scores):
        if i < 5 or item[0] in ['GLD', 'XLF', 'SHV']: # Show Top 5 + Debug names
             rank = f"#{i+1}"
             print(f"{rank:<5} {item[0]:<6} {item[1]:<8.2f} {item[3]*100:>6.2f}%    ${item[2]:.2f}")
             
    print("-" * 50)
    
    top_score = scores[0][1]
    
    if top_score <= 0:
        print("ACTION: SELL ALL -> CASH (SHV).")
    else:
        print("ACTION: BUY TOP 2 (50% Each):")
        if scores[0][1] > 0: print(f"1. {scores[0][0]}")
        if scores[1][1] > 0: print(f"2. {scores[1][0]}")

def check_universe_audit():
    """
    Checks if today is likely the first trading day of the year (Jan 2-5).
    If so, runs the Universe Updater check to alert the user.
    """
    today = datetime.now()
    if today.month == 1 and 2 <= today.day <= 5: # Simple heuristic for first trading week
        print("\n\n" + "="*50)
        print("★ ANNUAL UNIVERSE AUDIT (First Week of January) ★")
        print("Checking if the 'Generals' have changed...")
        
# We integrate the logic from UNIVERSE_UPDATER here
        try:
            from UNIVERSE_UPDATER import get_recommended_universe
            recommended = get_recommended_universe()
            
            current_tickers = set(TICKERS.keys())
            rec_tickers = set(recommended)
            
            if current_tickers == rec_tickers:
                print(">> UNIVERSE STATUS: VERIFIED & SYNCED. (24/24 Assets Match)")
            else:
                print(">> UNIVERSE STATUS: OUT OF SYNC!")
                print(f"Current: {sorted(list(current_tickers))}")
                print(f"Recommended: {sorted(list(rec_tickers))}")
                print("ACTION: PLEASE UPDATE 'TICKERS' DICTIONARY.")
        except Exception as e:
            print(f"Could not auto-run updater: {e}")
            print(">>> Please Run: 'python3 UNIVERSE_UPDATER.py' manually.")
            
        print("="*50 + "\n")

if __name__ == "__main__":
    check_universe_audit()
    get_bulletproof_signal()
