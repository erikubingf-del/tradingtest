"""
GLOBAL ROTATIONAL STRATEGY - EXPANDED UNIVERSE
Interactive Brokers Implementation

Optimized for 30%+ CAGR with diversified asset classes
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# EXPANDED ASSET UNIVERSE (20+ Assets)
# =============================================================================

# CORE UNIVERSE - Balanced across asset classes
EXPANDED_UNIVERSE = {
    # CRYPTO (High Momentum Potential) - 3 assets
    'BTC-USD': 'Bitcoin',
    'ETH-USD': 'Ethereum',
    'SOL-USD': 'Solana',

    # US EQUITY INDICES - 3 assets
    'SPY': 'S&P 500',
    'QQQ': 'Nasdaq 100',
    'IWM': 'Russell 2000',

    # SECTOR ETFS (High Growth) - 4 assets
    'XLK': 'Technology',
    'XLF': 'Financials',
    'XLE': 'Energy',
    'XLV': 'Healthcare',

    # INDIVIDUAL STOCKS (Momentum Leaders) - 4 assets
    'NVDA': 'NVIDIA',
    'AAPL': 'Apple',
    'MSFT': 'Microsoft',
    'AMZN': 'Amazon',

    # INTERNATIONAL - 2 assets
    'EFA': 'Developed Markets',
    'EEM': 'Emerging Markets',

    # COMMODITIES - 3 assets
    'GLD': 'Gold',
    'USO': 'Oil',
    'DBA': 'Agriculture',

    # BONDS/SAFE HAVEN - 2 assets
    'TLT': 'Long-Term Treasury',
    'UUP': 'US Dollar',
}

# ALTERNATIVE: Smaller focused universe for higher concentration
FOCUSED_UNIVERSE = {
    # Crypto (2)
    'BTC-USD': 'Bitcoin',
    'ETH-USD': 'Ethereum',

    # Tech Leaders (4)
    'QQQ': 'Nasdaq 100',
    'NVDA': 'NVIDIA',
    'MSFT': 'Microsoft',
    'AAPL': 'Apple',

    # Safe Haven (3)
    'GLD': 'Gold',
    'TLT': 'Long-Term Treasury',
    'UUP': 'US Dollar',

    # Energy (1)
    'USO': 'Oil',

    # International (1)
    'EEM': 'Emerging Markets',
}


def download_data(symbols, start_date, end_date):
    """Download historical data for all symbols"""
    print(f"Downloading data for {len(symbols)} assets...")

    all_data = {}
    for symbol in symbols:
        try:
            df = yf.download(symbol, start=start_date, end=end_date, progress=False)
            if len(df) > 100:
                # Handle both old and new yfinance column formats
                if isinstance(df.columns, pd.MultiIndex):
                    all_data[symbol] = df['Close'][symbol]
                elif 'Adj Close' in df.columns:
                    all_data[symbol] = df['Adj Close']
                else:
                    all_data[symbol] = df['Close']
                print(f"  ✓ {symbol}: {len(df)} days")
            else:
                print(f"  ✗ {symbol}: Insufficient data ({len(df)} days)")
        except Exception as e:
            print(f"  ✗ {symbol}: Error - {e}")

    prices = pd.DataFrame(all_data)
    prices = prices.dropna(how='all')
    print(f"\nTotal trading days: {len(prices)}")
    print(f"Assets with full data: {len(prices.columns)}")

    return prices


def calculate_momentum_score(prices, lookback=30):
    """Calculate risk-adjusted momentum score"""
    returns = prices.pct_change(lookback)
    volatility = prices.pct_change().rolling(lookback).std()

    # Risk-adjusted momentum (Sharpe-like)
    score = returns / (volatility + 1e-9)
    return score


def backtest_global_rotational(prices, lookback=30, rebalance_days=1,
                                top_n=1, use_regime_filter=True):
    """
    Backtest Global Rotational Strategy

    Parameters:
    - lookback: Days for momentum calculation
    - rebalance_days: How often to rebalance (1=daily, 5=weekly, 21=monthly)
    - top_n: Number of top assets to hold (1 = pure rotation)
    - use_regime_filter: If True, go to cash when all momentums negative
    """

    # Calculate momentum scores
    scores = calculate_momentum_score(prices, lookback)

    # Initialize
    portfolio_value = [100.0]
    positions = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    current_holdings = None
    last_rebalance = None

    # Track statistics
    trades = 0
    cash_days = 0

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
            # Get today's scores
            today_scores = scores.iloc[i-1].dropna()

            if len(today_scores) == 0:
                continue

            # Regime filter: Check if ANY asset has positive momentum
            if use_regime_filter:
                positive_assets = (today_scores > 0).sum()
                if positive_assets == 0:
                    # Go to cash
                    new_holdings = None
                    cash_days += 1
                else:
                    # Rank and select top N with positive momentum only
                    positive_scores = today_scores[today_scores > 0]
                    ranked = positive_scores.sort_values(ascending=False)
                    new_holdings = list(ranked.head(top_n).index)
            else:
                # No regime filter - always hold top N
                ranked = today_scores.sort_values(ascending=False)
                new_holdings = list(ranked.head(top_n).index)

            # Count trades
            if new_holdings != current_holdings:
                trades += 1
                current_holdings = new_holdings

            last_rebalance = date

        # Calculate returns
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
            # In cash
            portfolio_value.append(portfolio_value[-1])

    # Create results series
    results = pd.Series(portfolio_value[1:], index=prices.index[lookback+1:])

    # Calculate metrics
    total_return = (results.iloc[-1] / results.iloc[0]) - 1
    years = len(results) / 252
    cagr = (results.iloc[-1] / results.iloc[0]) ** (1/years) - 1

    # Drawdown
    rolling_max = results.cummax()
    drawdown = (results - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    # Sharpe
    daily_returns = results.pct_change().dropna()
    sharpe = np.sqrt(252) * daily_returns.mean() / daily_returns.std()

    return {
        'cagr': cagr * 100,
        'max_drawdown': max_drawdown * 100,
        'total_return': total_return * 100,
        'sharpe': sharpe,
        'trades': trades,
        'cash_days': cash_days,
        'years': years,
        'results': results
    }


def optimize_parameters(prices):
    """Test different parameter combinations"""

    print("\n" + "="*70)
    print("PARAMETER OPTIMIZATION")
    print("="*70)

    results = []

    # Parameter grid
    lookbacks = [20, 30, 45, 60]
    rebalance_options = [1, 3, 5, 10, 21]  # Daily, 3-day, Weekly, Bi-weekly, Monthly
    top_n_options = [1, 2, 3]

    for lookback in lookbacks:
        for rebalance in rebalance_options:
            for top_n in top_n_options:
                r = backtest_global_rotational(
                    prices,
                    lookback=lookback,
                    rebalance_days=rebalance,
                    top_n=top_n,
                    use_regime_filter=True
                )

                results.append({
                    'lookback': lookback,
                    'rebalance': rebalance,
                    'top_n': top_n,
                    'cagr': r['cagr'],
                    'max_dd': r['max_drawdown'],
                    'sharpe': r['sharpe'],
                    'trades': r['trades']
                })

    df = pd.DataFrame(results)

    # Sort by CAGR
    df_sorted = df.sort_values('cagr', ascending=False)

    print("\nTOP 10 CONFIGURATIONS BY CAGR:")
    print("-" * 70)
    print(f"{'Lookback':>8} {'Rebal':>6} {'Top_N':>6} {'CAGR':>8} {'MaxDD':>8} {'Sharpe':>8} {'Trades':>7}")
    print("-" * 70)

    for i, row in df_sorted.head(10).iterrows():
        print(f"{row['lookback']:>8} {row['rebalance']:>6} {row['top_n']:>6} "
              f"{row['cagr']:>7.1f}% {row['max_dd']:>7.1f}% {row['sharpe']:>8.2f} {row['trades']:>7}")

    # Best risk-adjusted (highest Sharpe)
    best_sharpe = df.loc[df['sharpe'].idxmax()]
    print(f"\nBEST RISK-ADJUSTED (Sharpe): Lookback={best_sharpe['lookback']}, "
          f"Rebalance={best_sharpe['rebalance']}, Top_N={best_sharpe['top_n']}")
    print(f"  CAGR: {best_sharpe['cagr']:.1f}%, MaxDD: {best_sharpe['max_dd']:.1f}%, "
          f"Sharpe: {best_sharpe['sharpe']:.2f}")

    return df_sorted


def main():
    """Main execution"""

    print("="*70)
    print("GLOBAL ROTATIONAL STRATEGY - INTERACTIVE BROKERS")
    print("Expanded Universe Testing")
    print("="*70)

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*7)  # 7 years

    # Test both universes
    for universe_name, universe in [
        ("EXPANDED (21 assets)", EXPANDED_UNIVERSE),
        ("FOCUSED (11 assets)", FOCUSED_UNIVERSE)
    ]:
        print(f"\n\n{'#'*70}")
        print(f"TESTING: {universe_name}")
        print(f"{'#'*70}")

        # Download data
        prices = download_data(list(universe.keys()), start_date, end_date)

        if len(prices.columns) < 5:
            print("ERROR: Not enough assets with valid data")
            continue

        # Optimize parameters
        optimization_results = optimize_parameters(prices)

        # Run best configuration
        best = optimization_results.iloc[0]
        print(f"\n\n{'='*70}")
        print(f"FINAL RESULTS - BEST CONFIGURATION")
        print(f"{'='*70}")

        final_result = backtest_global_rotational(
            prices,
            lookback=int(best['lookback']),
            rebalance_days=int(best['rebalance']),
            top_n=int(best['top_n']),
            use_regime_filter=True
        )

        print(f"""
OPTIMAL CONFIGURATION FOR {universe_name}:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lookback Period: {int(best['lookback'])} days
Rebalance Frequency: Every {int(best['rebalance'])} day(s)
Top N Holdings: {int(best['top_n'])} asset(s)

PERFORMANCE METRICS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAGR: {final_result['cagr']:.2f}%
Max Drawdown: {final_result['max_drawdown']:.2f}%
Sharpe Ratio: {final_result['sharpe']:.2f}
Total Return: {final_result['total_return']:.2f}%
Years Tested: {final_result['years']:.1f}
Total Trades: {final_result['trades']}
Days in Cash: {final_result['cash_days']}
""")

    print("\n" + "="*70)
    print("INTERACTIVE BROKERS IMPLEMENTATION NOTES:")
    print("="*70)
    print("""
1. API SETUP:
   - Install: pip install ib_insync
   - Enable API in TWS/Gateway (port 7497 for paper, 7496 for live)

2. DAILY ROUTINE:
   - Run ranking calculation after market close
   - Execute rebalance orders at market open

3. POSITION SIZING:
   - 100% in top asset (or 50% each if top_n=2)
   - Use limit orders to minimize slippage

4. TAX EFFICIENCY (US):
   - Consider using ISA/401k for frequent trading
   - Track cost basis for each rotation

5. CRYPTO NOTE:
   - IBKR offers BTC/ETH directly
   - Alternatively use BITO (Bitcoin ETF) for easier execution
""")


if __name__ == "__main__":
    main()
