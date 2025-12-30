import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. The User's "Verified" Universe (22 Assets) ---
TICKERS = {
    # Crypto
    'BTC': 'BTC-USD', 'ETH': 'ETH-USD', 'SOL': 'SOL-USD',
    # Indices
    'SPY': 'SPY', 'QQQ': 'QQQ', 'IWM': 'IWM',
    # Sectors
    'XLK': 'XLK', 'XLF': 'XLF', 'XLE': 'XLE', 'XLV': 'XLV',
    # Stocks
    'NVDA': 'NVDA', 'AAPL': 'AAPL', 'MSFT': 'MSFT', 'AMZN': 'AMZN',
    # International
    'EFA': 'EFA', 'EEM': 'EEM',
    # Commodities/Other
    'GLD': 'GLD', 'USO': 'USO', 'DBA': 'DBA',
    # Bonds/Cash
    'TLT': 'TLT', 'UUP': 'UUP', 'SHV': 'SHV'
}

START_DATE = '2017-11-01' # User specified "Nov 2017 - Dec 2025"
END_DATE = '2025-12-28'

# --- Config ---
LOOKBACK = 30
TOP_N = 2
FEE = 0.001

def run_strategy():
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

    # 1. Score: Return(30) / Vol(30)
    scores = pd.DataFrame(index=df.index, columns=df.columns)
    for col in df.columns:
        ret = df[col].pct_change(LOOKBACK)
        vol = df[col].pct_change().rolling(LOOKBACK).std()
        scores[col] = ret / (vol + 1e-9)
    scores = scores.fillna(0)

    # 2. Simulation
    equity = 1.0
    equity_curve = [1.0]
    
    current_holdings = [] # List of assets held
    daily_rets = df.pct_change()
    
    for i in range(len(df) - 1):
        # Decision for tomorrow (i+1)
        current_scores = scores.iloc[i]
        
        # Rank descending
        ranked = current_scores.sort_values(ascending=False)
        
        # "If highest Score <= 0: Hold CASH" -> i.e., NO LONG POSITIONS
        best_score = ranked.iloc[0]
        
        next_holdings = []
        if best_score > 0:
            # Buy TOP 2 with positive Score
            candidates = ranked[ranked > 0]
            count = min(len(candidates), TOP_N)
            if count > 0:
                next_holdings = list(candidates.index[:count])
        
        # Allocation Logic
        # 50% each if Top 2. If only 1 positive, 50% invested? Or 100%?
        # User says "Buy TOP 2... (50% each)". usually implies equal weight.
        # If only 1 qualifies, we usually do 50% in that 1, 50% Cash.
        # Or 100% in 1? Let's assume standard "1/N" sizing where N=Top_N.
        # Unallocated portion goes to Cash (SHV is in universe? No, Cash implies 0 return or SHV return).
        # Wait, SHV IS in the universe. If SHV is picked, it returns SHV.
        # If "Hold CASH" is triggered (Best <= 0), we hold SHV if available or 0.
        # Let's assume strict Cash = 0 return for simplicity, or SHV if strict "Asset".
        # User said: "If highest Score <= 0: Hold CASH".
        
        step_ret = 0.0
        
        if len(next_holdings) > 0:
            weight = 1.0 / TOP_N # 0.5
            for asset in next_holdings:
                 asset_ret = daily_rets[asset].iloc[i+1]
                 step_ret += asset_ret * weight
                 
            # If only 1 asset, step_ret is 0.5 * ret. Remaining 0.5 is Cash (0%).
        else:
            # All Cash (0%)
            step_ret = 0.0
            
        # Fees
        # Check for changes in holdings
        # Simplified Turnover: Sum of abs(NewWeight - OldWeight) / 2 * Fee?
        # Or simple check: if asset new -> fee?
        # With 2 assets, partial rotation is common (A,B -> A,C).
        # Cost = Fee * Weight for *changed* portion.
        
        # Current Weights
        curr_alloc = {a: (1.0/TOP_N) for a in current_holdings}
        next_alloc = {a: (1.0/TOP_N) for a in next_holdings}
        
        turnover = 0.0
        all_assets = set(current_holdings) | set(next_holdings)
        for a in all_assets:
            w_old = curr_alloc.get(a, 0.0)
            w_new = next_alloc.get(a, 0.0)
            turnover += abs(w_new - w_old)
            
        # Turnover is 2.0 for 100% swap. 1.0 for A,B -> A,C. 
        # Fee is applied on Trade Value. Trade Value = Turnover / 2 ?
        # No, Turnover = Buy + Sell. Fee is on total volume.
        # Volume = Turnover / 2 * PortfolioValue? 
        # Standard: Fee * turnover (sum of buys + sells? no usually just volume).
        # Let's simple approximation: Fee * Turnover / 2
        trade_cost = turnover * FEE * 0.5 # Wait, if I sell 0.5 and Buy 0.5, turnover is 1.0. I pay fee on 0.5 sell and 0.5 buy? Yes.
        # So Fee * Turnover?
        # IBKR Fee ~0.1% on Trade Value.
        # If I sell $50k (0.5), I pay 0.1%. If I buy $50k, I pay 0.1%. Total 0.1% on $100k moved? No.
        # It's Fee * Volume. Volume = Turnover.
        real_fee = turnover * FEE
        
        equity *= (1 + step_ret) - real_fee
        equity_curve.append(equity)
        current_holdings = next_holdings

    final_ret = equity_curve[-1] - 1
    days = len(equity_curve)
    cagr = ((1 + final_ret) ** (365/days)) - 1
    
    peak = pd.Series(equity_curve).cummax()
    dd = (pd.Series(equity_curve) - peak) / peak
    max_dd = dd.min()
    sharpe = (pd.Series(equity_curve).pct_change().mean() / pd.Series(equity_curve).pct_change().std()) * np.sqrt(252)

    print("-" * 60)
    print(f"STRATEGY: User 22-Asset / Top {TOP_N} / 30d")
    print(f"CAGR: {cagr*100:.2f}%")
    print(f"MAX DD: {max_dd*100:.2f}%")
    print(f"SHARPE: {sharpe:.2f}")
    print("-" * 60)

run_strategy()
