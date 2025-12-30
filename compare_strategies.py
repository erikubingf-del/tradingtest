"""
HEAD-TO-HEAD COMPARISON:
1. "Global Rotational Momentum" (7 assets, Top 1, 20-day) - Other AI's spec
2. "Expanded Universe" (21 assets, Top 3, 45-day) - Our optimized version

Fair comparison with identical backtest framework.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# STRATEGY 1: Other AI's Exact Specification
# =============================================================================
STRATEGY_1_UNIVERSE = {
    'BTC-USD': 'Bitcoin',
    'ETH-USD': 'Ethereum',
    'SPY': 'S&P 500',
    'QQQ': 'Nasdaq 100',
    'GLD': 'Gold',
    'USO': 'Crude Oil',
    'SHV': 'Cash/Treasury',  # Their explicit cash asset
}

STRATEGY_1_CONFIG = {
    'name': 'Other AI: 7 Assets, Top 1, 20-day',
    'lookback': 20,
    'top_n': 1,
    'rebalance_days': 1,
    'fee_per_trade': 0.001,  # 0.1%
    'use_regime_filter': True,
    'cash_asset': 'SHV',
}

# =============================================================================
# STRATEGY 2: Our Expanded Universe
# =============================================================================
STRATEGY_2_UNIVERSE = {
    'BTC-USD': 'Bitcoin',
    'ETH-USD': 'Ethereum',
    'SOL-USD': 'Solana',
    'SPY': 'S&P 500',
    'QQQ': 'Nasdaq 100',
    'IWM': 'Russell 2000',
    'XLK': 'Technology',
    'XLF': 'Financials',
    'XLE': 'Energy',
    'XLV': 'Healthcare',
    'NVDA': 'NVIDIA',
    'AAPL': 'Apple',
    'MSFT': 'Microsoft',
    'AMZN': 'Amazon',
    'EFA': 'Developed Markets',
    'EEM': 'Emerging Markets',
    'GLD': 'Gold',
    'USO': 'Oil',
    'DBA': 'Agriculture',
    'TLT': 'Long Treasury',
    'UUP': 'US Dollar',
}

STRATEGY_2_CONFIG = {
    'name': 'Ours: 21 Assets, Top 3, 45-day',
    'lookback': 45,
    'top_n': 3,
    'rebalance_days': 1,
    'fee_per_trade': 0.001,  # 0.1%
    'use_regime_filter': True,
    'cash_asset': None,  # Go to cash when all negative
}


def download_data(symbols, start_date, end_date):
    """Download historical data for all symbols"""
    all_data = {}
    for symbol in symbols:
        try:
            df = yf.download(symbol, start=start_date, end=end_date, progress=False)
            if len(df) > 100:
                if isinstance(df.columns, pd.MultiIndex):
                    all_data[symbol] = df['Close'][symbol]
                elif 'Adj Close' in df.columns:
                    all_data[symbol] = df['Adj Close']
                else:
                    all_data[symbol] = df['Close']
        except:
            pass

    prices = pd.DataFrame(all_data)
    prices = prices.dropna(how='all')
    return prices


def calculate_momentum_score(prices, lookback=20):
    """
    Exact formula from Other AI:
    Score = Return(20 days) / Volatility(20 days)
    """
    returns = prices.pct_change(lookback)
    volatility = prices.pct_change().rolling(lookback).std()
    score = returns / (volatility + 1e-9)
    return score


def backtest_rotational(prices, config, universe):
    """
    Backtest rotational strategy with exact rules.
    """
    lookback = config['lookback']
    top_n = config['top_n']
    rebalance_days = config['rebalance_days']
    fee = config['fee_per_trade']
    use_regime_filter = config['use_regime_filter']
    cash_asset = config['cash_asset']

    # Calculate momentum scores
    scores = calculate_momentum_score(prices, lookback)

    # Initialize
    portfolio_value = [100.0]
    current_holdings = None
    last_rebalance = None

    # Track statistics
    trades = 0
    cash_days = 0
    holding_history = []

    for i in range(lookback + 1, len(prices)):
        date = prices.index[i]
        prev_date = prices.index[i-1]

        # Check if rebalance day
        should_rebalance = False
        if last_rebalance is None:
            should_rebalance = True
        elif (date - last_rebalance).days >= rebalance_days:
            should_rebalance = True

        if should_rebalance:
            # Get today's scores (using previous day to avoid lookahead)
            today_scores = scores.iloc[i-1].dropna()

            if len(today_scores) == 0:
                continue

            # Rank assets
            ranked = today_scores.sort_values(ascending=False)

            # Apply regime filter
            if use_regime_filter:
                # Check if highest score is negative
                if ranked.iloc[0] <= 0:
                    # Go to cash
                    if cash_asset and cash_asset in prices.columns:
                        new_holdings = [cash_asset]
                    else:
                        new_holdings = None  # Pure cash
                    cash_days += 1
                else:
                    # Select top N with positive momentum
                    positive = ranked[ranked > 0]
                    new_holdings = list(positive.head(top_n).index)

                    # Exclude cash asset from momentum selection (it's a safety net)
                    if cash_asset and cash_asset in new_holdings:
                        new_holdings = [h for h in new_holdings if h != cash_asset]
                        if not new_holdings:
                            new_holdings = [cash_asset]
            else:
                new_holdings = list(ranked.head(top_n).index)

            # Count trades and apply fees
            if new_holdings != current_holdings:
                if current_holdings is not None:
                    # Fee for selling old positions
                    num_sells = len([h for h in current_holdings if h not in (new_holdings or [])])
                    # Fee for buying new positions
                    num_buys = len([h for h in (new_holdings or []) if h not in current_holdings])
                    total_fee = (num_sells + num_buys) * fee
                    portfolio_value[-1] *= (1 - total_fee)
                trades += 1
                current_holdings = new_holdings

            last_rebalance = date
            holding_history.append((date, current_holdings))

        # Calculate daily return
        if current_holdings is not None and len(current_holdings) > 0:
            daily_returns = []
            for asset in current_holdings:
                if asset in prices.columns:
                    ret = (prices[asset].iloc[i] / prices[asset].iloc[i-1]) - 1
                    if not np.isnan(ret):
                        daily_returns.append(ret)

            if daily_returns:
                avg_return = np.mean(daily_returns)
                portfolio_value.append(portfolio_value[-1] * (1 + avg_return))
            else:
                portfolio_value.append(portfolio_value[-1])
        else:
            # Pure cash - no return
            portfolio_value.append(portfolio_value[-1])

    # Create results series
    results = pd.Series(portfolio_value[1:], index=prices.index[lookback+1:])

    # Calculate metrics
    years = len(results) / 252
    cagr = (results.iloc[-1] / results.iloc[0]) ** (1/years) - 1

    # Drawdown
    rolling_max = results.cummax()
    drawdown = (results - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    # Sharpe
    daily_returns = results.pct_change().dropna()
    sharpe = np.sqrt(252) * daily_returns.mean() / daily_returns.std()

    # Sortino
    negative_returns = daily_returns[daily_returns < 0]
    sortino = np.sqrt(252) * daily_returns.mean() / negative_returns.std() if len(negative_returns) > 0 else 0

    return {
        'cagr': cagr * 100,
        'max_drawdown': max_drawdown * 100,
        'total_return': (results.iloc[-1] / results.iloc[0] - 1) * 100,
        'sharpe': sharpe,
        'sortino': sortino,
        'trades': trades,
        'cash_days': cash_days,
        'years': years,
        'results': results,
        'final_value': results.iloc[-1],
        'holding_history': holding_history
    }


def main():
    print("="*80)
    print("HEAD-TO-HEAD STRATEGY COMPARISON")
    print("="*80)

    # Date range: Nov 2017 to Dec 2025 (ETH data starts Nov 2017)
    # Also test 2015-2025 without ETH
    start_date = '2017-11-10'  # ETH data starts here
    end_date = '2025-12-28'

    print(f"\nTest Period: {start_date} to {end_date}")
    print(f"Fee: 0.1% per trade")

    # Download data for both universes
    all_symbols = set(STRATEGY_1_UNIVERSE.keys()) | set(STRATEGY_2_UNIVERSE.keys())
    print(f"\nDownloading data for {len(all_symbols)} unique assets...")

    prices = download_data(list(all_symbols), start_date, end_date)
    print(f"Total trading days: {len(prices)}")
    print(f"Assets with data: {len(prices.columns)}")

    # Check which assets have data
    print("\nAsset Data Availability:")
    for symbol in sorted(all_symbols):
        if symbol in prices.columns:
            first_date = prices[symbol].first_valid_index()
            print(f"  ✓ {symbol}: from {first_date.strftime('%Y-%m-%d')}")
        else:
            print(f"  ✗ {symbol}: NO DATA")

    # ==========================================================================
    # STRATEGY 1: Other AI's Specification
    # ==========================================================================
    print("\n" + "="*80)
    print("STRATEGY 1: Other AI's Specification")
    print("="*80)
    print(f"Universe: {list(STRATEGY_1_UNIVERSE.keys())}")
    print(f"Lookback: {STRATEGY_1_CONFIG['lookback']} days")
    print(f"Holdings: Top {STRATEGY_1_CONFIG['top_n']}")
    print(f"Cash Asset: {STRATEGY_1_CONFIG['cash_asset']}")

    # Filter prices to only include Strategy 1 assets
    prices_1 = prices[[s for s in STRATEGY_1_UNIVERSE.keys() if s in prices.columns]]
    result_1 = backtest_rotational(prices_1, STRATEGY_1_CONFIG, STRATEGY_1_UNIVERSE)

    print(f"\nResults:")
    print(f"  CAGR: {result_1['cagr']:.2f}%")
    print(f"  Max Drawdown: {result_1['max_drawdown']:.2f}%")
    print(f"  Sharpe Ratio: {result_1['sharpe']:.2f}")
    print(f"  Total Return: {result_1['total_return']:.2f}%")
    print(f"  Final Value: ${result_1['final_value']:.2f} (from $100)")
    print(f"  Total Trades: {result_1['trades']}")
    print(f"  Days in Cash: {result_1['cash_days']}")

    # ==========================================================================
    # STRATEGY 2: Our Expanded Universe
    # ==========================================================================
    print("\n" + "="*80)
    print("STRATEGY 2: Our Expanded Universe")
    print("="*80)
    print(f"Universe: {len(STRATEGY_2_UNIVERSE)} assets")
    print(f"Lookback: {STRATEGY_2_CONFIG['lookback']} days")
    print(f"Holdings: Top {STRATEGY_2_CONFIG['top_n']}")

    # Filter prices to only include Strategy 2 assets
    prices_2 = prices[[s for s in STRATEGY_2_UNIVERSE.keys() if s in prices.columns]]
    result_2 = backtest_rotational(prices_2, STRATEGY_2_CONFIG, STRATEGY_2_UNIVERSE)

    print(f"\nResults:")
    print(f"  CAGR: {result_2['cagr']:.2f}%")
    print(f"  Max Drawdown: {result_2['max_drawdown']:.2f}%")
    print(f"  Sharpe Ratio: {result_2['sharpe']:.2f}")
    print(f"  Total Return: {result_2['total_return']:.2f}%")
    print(f"  Final Value: ${result_2['final_value']:.2f} (from $100)")
    print(f"  Total Trades: {result_2['trades']}")
    print(f"  Days in Cash: {result_2['cash_days']}")

    # ==========================================================================
    # HEAD-TO-HEAD COMPARISON
    # ==========================================================================
    print("\n" + "="*80)
    print("HEAD-TO-HEAD COMPARISON")
    print("="*80)

    print(f"""
┌─────────────────────────────┬────────────────────────┬────────────────────────┐
│ Metric                      │ Other AI (7 assets)    │ Ours (21 assets)       │
├─────────────────────────────┼────────────────────────┼────────────────────────┤
│ CAGR                        │ {result_1['cagr']:>20.2f}% │ {result_2['cagr']:>20.2f}% │
│ Max Drawdown                │ {result_1['max_drawdown']:>20.2f}% │ {result_2['max_drawdown']:>20.2f}% │
│ Sharpe Ratio                │ {result_1['sharpe']:>21.2f} │ {result_2['sharpe']:>21.2f} │
│ Sortino Ratio               │ {result_1['sortino']:>21.2f} │ {result_2['sortino']:>21.2f} │
│ Total Return                │ {result_1['total_return']:>20.2f}% │ {result_2['total_return']:>20.2f}% │
│ Final Value ($100 start)    │ ${result_1['final_value']:>19.2f} │ ${result_2['final_value']:>19.2f} │
│ Total Trades                │ {result_1['trades']:>21} │ {result_2['trades']:>21} │
│ Days in Cash                │ {result_1['cash_days']:>21} │ {result_2['cash_days']:>21} │
└─────────────────────────────┴────────────────────────┴────────────────────────┘
""")

    # Determine winner
    print("WINNER BY METRIC:")
    print(f"  CAGR: {'Other AI ✓' if result_1['cagr'] > result_2['cagr'] else 'Ours ✓'}")
    print(f"  Max Drawdown: {'Other AI ✓' if abs(result_1['max_drawdown']) < abs(result_2['max_drawdown']) else 'Ours ✓'}")
    print(f"  Sharpe: {'Other AI ✓' if result_1['sharpe'] > result_2['sharpe'] else 'Ours ✓'}")
    print(f"  Risk-Adjusted (CAGR/DD): {'Other AI ✓' if result_1['cagr']/abs(result_1['max_drawdown']) > result_2['cagr']/abs(result_2['max_drawdown']) else 'Ours ✓'}")

    # ==========================================================================
    # ALSO TEST: Their spec with OUR parameters (21 assets, 45-day)
    # ==========================================================================
    print("\n" + "="*80)
    print("BONUS: Other AI's 7 Assets with OUR 45-day lookback")
    print("="*80)

    config_hybrid = {
        'name': 'Hybrid: 7 Assets, Top 1, 45-day',
        'lookback': 45,
        'top_n': 1,
        'rebalance_days': 1,
        'fee_per_trade': 0.001,
        'use_regime_filter': True,
        'cash_asset': 'SHV',
    }

    result_hybrid = backtest_rotational(prices_1, config_hybrid, STRATEGY_1_UNIVERSE)
    print(f"CAGR: {result_hybrid['cagr']:.2f}%")
    print(f"Max Drawdown: {result_hybrid['max_drawdown']:.2f}%")
    print(f"Sharpe: {result_hybrid['sharpe']:.2f}")

    # ==========================================================================
    # ALSO TEST: Our assets with THEIR parameters (Top 1, 20-day)
    # ==========================================================================
    print("\n" + "="*80)
    print("BONUS: Our 21 Assets with THEIR 20-day lookback, Top 1")
    print("="*80)

    config_hybrid2 = {
        'name': 'Hybrid: 21 Assets, Top 1, 20-day',
        'lookback': 20,
        'top_n': 1,
        'rebalance_days': 1,
        'fee_per_trade': 0.001,
        'use_regime_filter': True,
        'cash_asset': None,
    }

    result_hybrid2 = backtest_rotational(prices_2, config_hybrid2, STRATEGY_2_UNIVERSE)
    print(f"CAGR: {result_hybrid2['cagr']:.2f}%")
    print(f"Max Drawdown: {result_hybrid2['max_drawdown']:.2f}%")
    print(f"Sharpe: {result_hybrid2['sharpe']:.2f}")

    print("\n" + "="*80)
    print("FINAL VERDICT")
    print("="*80)

    all_results = [
        (f"Other AI (7, Top1, 20d)", result_1),
        (f"Ours (21, Top3, 45d)", result_2),
        (f"Hybrid (7, Top1, 45d)", result_hybrid),
        (f"Hybrid (21, Top1, 20d)", result_hybrid2),
    ]

    # Sort by CAGR
    all_results.sort(key=lambda x: x[1]['cagr'], reverse=True)

    print("\nRANKED BY CAGR:")
    for i, (name, r) in enumerate(all_results, 1):
        print(f"  {i}. {name}: {r['cagr']:.2f}% CAGR, {r['max_drawdown']:.2f}% MaxDD, {r['sharpe']:.2f} Sharpe")


if __name__ == "__main__":
    main()
