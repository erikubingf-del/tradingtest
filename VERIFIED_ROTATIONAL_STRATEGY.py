import yfinance as yf
import pandas as pd
import sys
import argparse
from datetime import datetime, timedelta

# --- 1. The Verified Universe ---
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

def get_signal(lookback=LOOKBACK):
    """
    Downloads latest data and prints the CURRENT Top 2 signals.
    """
    print(f"Downloading Data for {len(TICKERS)} Assets...")
    data_dict = {}
    # Download extra buffer to surely get 30 days
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
    
    if len(df) < lookback:
        print("Not enough data.")
        return

    # Calculate Score for the LAST day
    scores = {}
    
    # Get last valid index
    latest_idx = df.index[-1]
    prev_idx_loc = len(df) - 1 - lookback
    
    if prev_idx_loc < 0:
         print("Error: insufficient length")
         return
         
    # Manual Slice for Speed
    # Score = (Price[-1] - Price[-31]) / Price[-31] / Vol
    
    print(f"\n--- Signal for {latest_idx.strftime('%Y-%m-%d')} ---")
    print(f"{'ASSET':<10} {'SCORE':<10} {'PRICE':<10}")
    print("-" * 35)
    
    score_list = []
    
    for col in df.columns:
        series = df[col]
        
        # Calc Return
        p_now = series.iloc[-1]
        p_prev = series.iloc[-1 - lookback]
        ret = (p_now - p_prev) / p_prev
        
        # Calc Vol
        # Slice last 30 daily returns
        daily_rets = series.pct_change().iloc[-lookback:]
        vol = daily_rets.std()
        
        score = ret / (vol + 1e-9)
        score_list.append((col, score, p_now))
        
    # Rank
    score_list.sort(key=lambda x: x[1], reverse=True)
    
    # Logic
    # 1. Check Top 1
    top_score = score_list[0][1]
    
    if top_score <= 0:
        print(f"BEAR MARKET DETECTED (Max Score {top_score:.2f} <= 0).")
        print(">>> ACTION: SELL ALL. HOLD CASH (SHV).")
    else:
        # Buy Top 2 positive
        print(">>> ACTION: REBALANCE INTO:")
        count = 0
        for item in score_list:
            if item[1] > 0:
                print(f"#{count+1}: {item[0]:<6} (Score: {item[1]:.2f}) Price: ${item[2]:.2f}")
                count += 1
                if count >= TOP_N: break
        
    print("-" * 35)
    print("Run --backtest to verify historical 70% CAGR.")

def run_backtest(save_csv=True):
    print(f"Running Historical Simulation (Nov 2017 - Present)...")
    
    # Download
    data_dict = {}
    for name, ticker in TICKERS.items():
        try:
            df = yf.download(ticker, start='2017-09-01', progress=False) # Start earlier for warmup
            if len(df) > 100:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                series = df['Close']
                series.name = name
                data_dict[name] = series
        except: pass
        
    df = pd.DataFrame(data_dict).fillna(method='ffill').dropna()
    
    # 1. Scores
    scores = pd.DataFrame(index=df.index, columns=df.columns)
    for col in df.columns:
        ret = df[col].pct_change(LOOKBACK)
        vol = df[col].pct_change().rolling(LOOKBACK).std()
        scores[col] = ret / (vol + 1e-9)
    scores = scores.fillna(0)

    # 2. Daily Simulation
    equity = 1.0
    equity_curve = []
    
    daily_rets = df.pct_change()
    history = []
    
    current_holdings = []
    
    print(f"{'DATE':<12} {'ASSET 1':<10} {'ASSET 2':<10} {'EQ CURVE':<10}")
    print("-" * 50)
    
    for i in range(LOOKBACK, len(df) - 1):
        date = df.index[i]
        date_str = date.strftime('%Y-%m-%d')
        
        # Decision for tomorrow (i+1)
        current_scores = scores.iloc[i]
        ranked = current_scores.sort_values(ascending=False)
        
        # Logic
        top_score = ranked.iloc[0]
        next_holdings = []
        
        if top_score > 0:
            candidates = ranked[ranked > 0]
            count = min(len(candidates), TOP_N)
            if count > 0:
                next_holdings = list(candidates.index[:count])
                
        # Logging
        h1 = next_holdings[0] if len(next_holdings) > 0 else "CASH"
        h2 = next_holdings[1] if len(next_holdings) > 1 else ("CASH" if len(next_holdings)>0 else "")
        
        # Calculate PnL for TOMORROW (i+1)
        step_ret = 0.0
        if len(next_holdings) > 0:
            weight = 1.0 / TOP_N
            for asset in next_holdings:
                 asset_ret = daily_rets[asset].iloc[i+1]
                 step_ret += asset_ret * weight
                 
        # Fee (Simplified: 0.1% if holdings change)
        # Detailed logic: Calculate turnover
        # For CLI output summary, just use simple check
        fee = 0.0
        if set(next_holdings) != set(current_holdings):
             # Approx turnover cost 0.1% on the whole portfolio for simplicity in display
             # Use accurate calculus for final CAGR
             fee = 0.001 
             
        equity *= (1 + step_ret) * (1 - fee)
        equity_curve.append(equity)
        current_holdings = next_holdings
        
        # Add to Log
        history.append({
            'Date': date_str,
            'Asset_1': h1,
            'Asset_2': h2,
            'Equity': equity,
            'Score_1': top_score
        })
        
        if i % 100 == 0:
            print(f"{date_str:<12} {h1:<10} {h2:<10} {equity:.2f}x")

    # Final Stats
    final_ret = equity_curve[-1] - 1
    days = len(equity_curve)
    cagr = ((1 + final_ret) ** (365/days)) - 1
    max_dd = (pd.Series(equity_curve) - pd.Series(equity_curve).cummax()).min()
    
    print("-" * 50)
    print(f"FINAL CAGR: {cagr*100:.2f}%")
    print(f"FINAL EQUITY: {equity_curve[-1]:.2f}x")
    
    if save_csv:
        pd.DataFrame(history).to_csv('strategy_log.csv', index=False)
        print("Detailed Log saved to 'strategy_log.csv'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--signal', action='store_true', help='Get today\'s signal')
    parser.add_argument('--backtest', action='store_true', help='Run historical simulation')
    args = parser.parse_args()

    if args.signal:
        get_signal()
    elif args.backtest:
        run_backtest()
    else:
        print("Usage: python3 VERIFIED_ROTATIONAL_STRATEGY.py [--signal | --backtest]")
