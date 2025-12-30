"""
UNIVERSE_UPDATER.py
-------------------
Future-Proofing the Strategy.
Run this script MONTHLY to update the "Generals" list 
based on current Market Cap rankings.

Logic:
1. Fetch Top 3 Crypto Assets (by Market Cap).
2. Fetch Top 5 Stocks (Magnificent 7 check).
3. Update DAILY_TRADING_BOT.py universe.

Requires: pip install pandas yfinance
"""

import yfinance as yf
import pandas as pd
import re

def get_top_crypto():
    # In a real scenario, use CoinGecko API.
    # For independent python, we can use a hardcoded list of candidates
    # and simply check who is biggest? Or just stick to manual logical review.
    # Verification: "Is SOL still top 5?"
    
    # Simple Heuristic: Check Volume/Cap of major candidates
    candidates = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD']
    print("Checking Top Crypto Candidates...")
    
    stats = []
    for c in candidates:
        try:
            ticker = yf.Ticker(c)
            info = ticker.info
            cap = info.get('marketCap', 0)
            stats.append((c, cap))
        except: pass
        
    stats.sort(key=lambda x: x[1], reverse=True)
    top_4 = [x[0] for x in stats[:4]]
    return top_4

def get_top_stocks():
    # Check Market Caps of big tech
    candidates = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA']
    print("Checking Top Stock Candidates...")
    
    stats = []
    for s in candidates:
        try:
            ticker = yf.Ticker(s)
            info = ticker.info
            cap = info.get('marketCap', 0)
            stats.append((s, cap))
        except: pass
        
    stats.sort(key=lambda x: x[1], reverse=True)
    top_5 = [x[0] for x in stats[:5]]
    return top_5

def get_recommended_universe():
    # 1. Get Leaders
    new_crypto = get_top_crypto()
    new_stocks = get_top_stocks()
    
    # 2. Define the 'Immutable' Core (Sectors/Indices)
    core_assets = [
        'SPY', 'QQQ', 'IWM', # Indices
        'XLK', 'XLF', 'XLE', 'XLV', # Sectors
        'EFA', 'EEM', # Global
        'GLD', 'USO', 'DBA', # Commodities
        'TLT', 'UUP', 'SHV' # Safety
    ]
    
    # 3. Construct New List
    full_list = core_assets + [x.split('-')[0] for x in new_crypto] + new_stocks
    return full_list

def update_universe():
    print("--- RUNNING UNIVERSE UPDATE ---")
    full_list = get_recommended_universe()
    print("\nSUGGESTED UNIVERSE:")
    print(full_list)
    print("\nNOTE: To safely update the bot, verify these tickers manually.")
    print("Then edit 'DAILY_TRADING_BOT.py' & 'BULLETPROOF_SIGNAL.py' TICKERS dictionary.")

if __name__ == "__main__":
    update_universe()
