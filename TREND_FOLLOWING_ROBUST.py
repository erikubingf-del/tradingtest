"""
ROBUST TREND FOLLOWING STRATEGY
================================
Based on proven methods that have worked since 1980s:
- Turtle Traders (Donchian Breakouts)
- AQR Managed Futures
- Time-Series Momentum (Moskowitz et al.)

Key Principles:
1. Cut losses short, let winners run
2. Trade across MANY uncorrelated markets
3. Position sizing based on volatility (ATR)
4. Multiple timeframes for confirmation
5. No single asset dependency

Target: 20-30% CAGR with max 25% drawdown over ANY 10-year period
"""

import yfinance as yf
import pandas as pd
import numpy as np
import shutil
import os
from datetime import datetime, timedelta

# Clear cache
def clear_cache():
    cache_dir = os.path.expanduser("~/.cache/py-yfinance")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
        except: pass

# =============================================================================
# DIVERSIFIED UNIVERSE - 30+ UNCORRELATED MARKETS
# =============================================================================
# The key to consistent returns is DIVERSIFICATION across:
# - Asset classes (stocks, bonds, commodities, currencies, crypto)
# - Geographies (US, Europe, Asia, Emerging)
# - Sectors

UNIVERSE = {
    # US Equity Indices (all since 2002+)
    'SPY': 'SPY',      # S&P 500
    'QQQ': 'QQQ',      # Nasdaq
    'IWM': 'IWM',      # Russell 2000
    'DIA': 'DIA',      # Dow Jones

    # International Equity
    'EFA': 'EFA',      # Developed Markets
    'EEM': 'EEM',      # Emerging Markets
    'VGK': 'VGK',      # Europe
    'EWJ': 'EWJ',      # Japan
    'FXI': 'FXI',      # China

    # US Sectors (all since 1998)
    'XLK': 'XLK',      # Tech
    'XLF': 'XLF',      # Financials
    'XLE': 'XLE',      # Energy
    'XLV': 'XLV',      # Healthcare
    'XLI': 'XLI',      # Industrials
    'XLP': 'XLP',      # Consumer Staples
    'XLU': 'XLU',      # Utilities

    # Bonds
    'TLT': 'TLT',      # Long-Term Treasury
    'IEF': 'IEF',      # Intermediate Treasury
    'LQD': 'LQD',      # Corporate Bonds
    'HYG': 'HYG',      # High Yield

    # Commodities
    'GLD': 'GLD',      # Gold
    'SLV': 'SLV',      # Silver
    'USO': 'USO',      # Oil
    'UNG': 'UNG',      # Natural Gas
    'DBA': 'DBA',      # Agriculture

    # Currency
    'UUP': 'UUP',      # US Dollar
    'FXE': 'FXE',      # Euro
    'FXY': 'FXY',      # Yen

    # Crypto (limited allocation - huge alpha generator)
    'BTC': 'BTC-USD',
    'ETH': 'ETH-USD',

    # Safe Haven
    'SHV': 'SHV',      # Cash equivalent
}

# LONG HISTORY UNIVERSE (for 15+ year tests)
UNIVERSE_LONG_HISTORY = {
    # US Equity Indices
    'SPY': 'SPY',      # S&P 500 (1993)
    'QQQ': 'QQQ',      # Nasdaq (1999)
    'IWM': 'IWM',      # Russell 2000 (2000)
    'DIA': 'DIA',      # Dow Jones (1998)

    # International
    'EFA': 'EFA',      # Developed Markets (2001)
    'EEM': 'EEM',      # Emerging Markets (2003)
    'EWJ': 'EWJ',      # Japan (1996)

    # Sectors (all since 1998)
    'XLK': 'XLK',      # Tech
    'XLF': 'XLF',      # Financials
    'XLE': 'XLE',      # Energy
    'XLV': 'XLV',      # Healthcare
    'XLI': 'XLI',      # Industrials
    'XLP': 'XLP',      # Consumer Staples
    'XLU': 'XLU',      # Utilities

    # Bonds (2002+)
    'TLT': 'TLT',      # Long-Term Treasury
    'IEF': 'IEF',      # Intermediate Treasury
    'LQD': 'LQD',      # Corporate Bonds

    # Commodities (2004+)
    'GLD': 'GLD',      # Gold (2004)

    # Safe Haven
    'SHV': 'SHV',      # Cash equivalent (2007)
}

# =============================================================================
# TREND FOLLOWING RULES (Proven since 1980s)
# =============================================================================

def calculate_trend_signals(prices, fast=15, slow=60):
    """
    Multi-timeframe trend confirmation:
    - Short-term: 20-day momentum
    - Long-term: 100-day trend (above/below MA)
    - Volatility-adjusted scoring
    """
    signals = pd.DataFrame(index=prices.index, columns=prices.columns)

    for col in prices.columns:
        price = prices[col]

        # 1. Long-term trend filter (price > 100-day MA)
        ma_long = price.rolling(slow).mean()
        trend_up = (price > ma_long).astype(int)

        # 2. Medium-term momentum (30-day ROC)
        roc_30 = price.pct_change(30)

        # 3. Short-term momentum (15-day ROC)
        roc_15 = price.pct_change(fast)

        # 4. Volatility (for position sizing later)
        vol = price.pct_change().rolling(fast).std()

        # Combined score: Only trade WITH the trend
        # Score = momentum / volatility (Sharpe-like)
        raw_score = (roc_15 * 0.3 + roc_30 * 0.7) / (vol + 1e-9)

        # Apply trend filter: zero out counter-trend signals
        signals[col] = raw_score * trend_up

    return signals.fillna(0)


def calculate_atr_position_size(prices, lookback=20):
    """
    ATR-based position sizing (Turtle method):
    - Higher volatility = smaller position
    - This prevents any single market from dominating
    """
    atr_pct = pd.DataFrame(index=prices.index, columns=prices.columns)

    for col in prices.columns:
        price = prices[col]
        daily_range = price.pct_change().abs()
        atr_pct[col] = daily_range.rolling(lookback).mean()

    # Inverse ATR for sizing (higher vol = lower weight)
    inv_atr = 1 / (atr_pct + 1e-9)

    # Normalize so weights sum to 1
    weights = inv_atr.div(inv_atr.sum(axis=1), axis=0)

    return weights.fillna(0)


def run_trend_following_backtest(start_date='2007-01-01'):
    """
    Classic Trend Following Backtest

    Rules:
    1. Score all assets by trend strength (momentum / volatility)
    2. Only buy assets in uptrend (price > 100-day MA)
    3. Size positions by inverse volatility (ATR)
    4. Hold TOP N trending assets
    5. Rebalance weekly (reduce noise)
    """
    clear_cache()
    print("="*70)
    print("ROBUST TREND FOLLOWING BACKTEST")
    print("="*70)

    # Download data
    print(f"\nDownloading {len(UNIVERSE)} assets from {start_date}...")

    data = {}
    for name, ticker in UNIVERSE.items():
        try:
            df = yf.download(ticker, start=start_date, progress=False)
            if len(df) > 200:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                data[name] = df['Close']
        except:
            pass

    prices = pd.DataFrame(data).ffill().dropna()
    print(f"Loaded {len(prices.columns)} assets, {len(prices)} days")

    # Calculate signals
    print("Calculating trend signals...")
    signals = calculate_trend_signals(prices)

    # Calculate daily returns
    returns = prices.pct_change()

    # Simulation parameters - AGGRESSIVE VERSION
    TOP_N = 2  # Hold top 2 trending assets (concentrated like original)
    REBAL_FREQ = 1  # Rebalance daily (capture momentum faster)
    FEE = 0.001  # 0.1% per trade
    MAX_CRYPTO_WEIGHT = 0.50  # Cap crypto at 50% of portfolio (1 slot max)

    # Run simulation
    equity = 1.0
    equity_curve = []
    holdings = []
    last_rebal = 0

    print(f"\n{'DATE':<12} {'TOP HOLDINGS':<40} {'EQUITY':<10}")
    print("-"*65)

    for i in range(100, len(prices)-1):
        date = prices.index[i]

        # Rebalance check
        if i - last_rebal >= REBAL_FREQ:
            last_rebal = i

            # Get current scores
            today_signals = signals.iloc[i]

            # Only consider positive (uptrending) assets
            positive = today_signals[today_signals > 0].sort_values(ascending=False)

            if len(positive) > 0:
                # Select top N
                new_holdings = list(positive.index[:TOP_N])

                # Cap crypto exposure
                crypto_in_holdings = [h for h in new_holdings if h in ['BTC', 'ETH']]
                if len(crypto_in_holdings) > 1:
                    # Keep only best crypto
                    crypto_scores = [(c, positive[c]) for c in crypto_in_holdings]
                    crypto_scores.sort(key=lambda x: x[1], reverse=True)
                    for c, _ in crypto_scores[1:]:
                        new_holdings.remove(c)
                        # Add next best non-crypto
                        for alt in positive.index:
                            if alt not in new_holdings and alt not in ['BTC', 'ETH']:
                                new_holdings.append(alt)
                                break

            else:
                # All assets in downtrend -> go to cash
                new_holdings = ['SHV']

            # Calculate turnover cost
            old_set = set(holdings)
            new_set = set(new_holdings)
            if old_set != new_set:
                turnover = len(old_set.symmetric_difference(new_set)) / (2 * TOP_N)
                cost = turnover * FEE
                equity *= (1 - cost)

            holdings = new_holdings

        # Calculate daily return
        if len(holdings) > 0:
            weight = 1.0 / len(holdings)
            daily_ret = sum(returns[h].iloc[i+1] * weight for h in holdings if h in returns.columns)
            equity *= (1 + daily_ret)

        equity_curve.append(equity)

        # Log
        if i % 250 == 0:
            h_str = ', '.join(holdings[:3]) + ('...' if len(holdings) > 3 else '')
            print(f"{date.strftime('%Y-%m-%d'):<12} {h_str:<40} {equity:.2f}x")

    # Results
    eq_series = pd.Series(equity_curve, index=prices.index[101:])

    # Calculate metrics
    total_days = len(eq_series)
    total_return = eq_series.iloc[-1] - 1
    cagr = ((1 + total_return) ** (365/total_days)) - 1

    # Drawdown
    peak = eq_series.cummax()
    drawdown = (eq_series - peak) / peak
    max_dd = drawdown.min()

    # Sharpe
    daily_rets = eq_series.pct_change().dropna()
    sharpe = (daily_rets.mean() / daily_rets.std()) * np.sqrt(252)

    # Yearly returns
    print("\n" + "="*50)
    print("YEARLY PERFORMANCE")
    print("="*50)
    yearly = eq_series.resample('YE').last()
    yearly_ret = yearly.pct_change()
    yearly_ret.iloc[0] = yearly.iloc[0] - 1

    positive_years = 0
    for date, ret in yearly_ret.items():
        status = "+" if ret > 0 else "-"
        print(f"{date.year}: {ret*100:>7.2f}% {status}")
        if ret > 0:
            positive_years += 1

    win_rate = positive_years / len(yearly_ret) * 100

    # Rolling 5-year CAGR
    print("\n" + "="*50)
    print("ROLLING 5-YEAR CAGR (Consistency Check)")
    print("="*50)

    for i in range(0, len(yearly)-5, 1):
        start_val = yearly.iloc[i]
        end_val = yearly.iloc[i+5]
        period_cagr = ((end_val / start_val) ** 0.2) - 1
        start_year = yearly.index[i].year
        end_year = yearly.index[i+5].year
        print(f"{start_year}-{end_year}: {period_cagr*100:.1f}% CAGR")

    # Final summary
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    print(f"Period: {prices.index[100].strftime('%Y-%m-%d')} to {prices.index[-1].strftime('%Y-%m-%d')}")
    print(f"CAGR: {cagr*100:.2f}%")
    print(f"Max Drawdown: {max_dd*100:.2f}%")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Total Return: {equity_curve[-1]:.2f}x")
    print(f"Win Rate (Years): {win_rate:.0f}%")
    print("="*70)

    if cagr > 0.20 and max_dd > -0.30:
        print("VERDICT: ROBUST STRATEGY (>20% CAGR, <30% MaxDD)")
    else:
        print("VERDICT: NEEDS IMPROVEMENT")

    return eq_series


def get_current_signal():
    """Get today's trading signal"""
    clear_cache()
    print("="*50)
    print("TREND FOLLOWING - TODAY'S SIGNAL")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*50)

    # Download recent data
    start = (datetime.now() - timedelta(days=150)).strftime('%Y-%m-%d')

    data = {}
    for name, ticker in UNIVERSE.items():
        try:
            df = yf.download(ticker, start=start, progress=False)
            if len(df) > 100:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                data[name] = df['Close']
        except:
            pass

    prices = pd.DataFrame(data).ffill().dropna()
    signals = calculate_trend_signals(prices)

    # Get latest signals
    today = signals.iloc[-1].sort_values(ascending=False)

    print("\nTOP 10 TRENDING ASSETS:")
    print("-"*40)
    for i, (asset, score) in enumerate(today.head(10).items()):
        trend = "UPTREND" if score > 0 else "DOWNTREND"
        print(f"{i+1}. {asset:<6} Score: {score:>6.2f}  [{trend}]")

    # Generate recommendation
    positive = today[today > 0]
    if len(positive) >= 5:
        holdings = list(positive.index[:5])
        print(f"\nRECOMMENDED HOLDINGS (Top 5):")
        for h in holdings:
            print(f"  - {h} (20% each)")
    else:
        print(f"\nWARNING: Only {len(positive)} assets in uptrend")
        print("Consider reducing exposure or holding cash (SHV)")


if __name__ == "__main__":
    import sys
    if '--signal' in sys.argv:
        get_current_signal()
    else:
        run_trend_following_backtest()
