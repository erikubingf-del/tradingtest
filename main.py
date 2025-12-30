#!/usr/bin/env python3
"""
Trend Following Backtesting System - Main Entry Point

This system implements proven trend-following strategies based on:
- AQR "A Century of Evidence on Trend-Following Investing"
- Turtle Trading Rules (Richard Dennis)
- Dual Momentum (Gary Antonacci)
- Time Series Momentum (Moskowitz, Ooi, Pedersen 2012)

Goal: Achieve 20% CAGR over 10-year periods by:
1. Scanning 50+ diversified assets
2. Entering with 2-5% positions in trending assets
3. Scaling up as trends prove themselves
4. Strict exit rules to cut losers quickly
5. Letting winners run with trailing stops

Usage:
    python main.py --strategy combined --start 2010-01-01 --end 2024-01-01
    python main.py --optimize --strategy turtle
    python main.py --monte-carlo --simulations 1000
"""

import argparse
import sys
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from tqdm import tqdm
import warnings

warnings.filterwarnings('ignore')

from config import (
    BacktestConfig, ASSET_UNIVERSE, FUTURES_PROXIES,
    get_full_universe, CORRELATION_GROUPS
)
from data_fetcher import DataFetcher, get_historical_data_summary
from backtester import Backtester, print_results, MonteCarloSimulator
from indicators import calculate_all_indicators
from strategies import TrendScanner


def fetch_data(
    start_date: str,
    end_date: str,
    asset_classes: List[str] = None,
    use_futures: bool = False
) -> Dict[str, pd.DataFrame]:
    """
    Fetch data for backtesting.

    Args:
        start_date: Start date
        end_date: End date
        asset_classes: List of asset classes to include
        use_futures: Use futures proxies for longer history

    Returns:
        Dictionary of ticker -> DataFrame
    """
    fetcher = DataFetcher()

    if use_futures:
        # Use futures proxies for historical data
        tickers = list(FUTURES_PROXIES.keys())
    else:
        if asset_classes:
            tickers = []
            for ac in asset_classes:
                if ac in ASSET_UNIVERSE:
                    for ticker, name in ASSET_UNIVERSE[ac]:
                        tickers.append(ticker)
        else:
            tickers = get_full_universe()

    print(f"Fetching data for {len(tickers)} assets...")
    data = fetcher.fetch_multiple(tickers, start_date, end_date)

    # Show summary
    summary = get_historical_data_summary(data)
    print(f"\nSuccessfully fetched {len(data)} assets")
    if len(summary) > 0:
        print(f"Date range: {summary['start_date'].min()} to {summary['end_date'].max()}")
        print(f"Average history: {summary['years'].mean():.1f} years")

    return data


def run_single_backtest(
    data: Dict[str, pd.DataFrame],
    strategy: str = "combined",
    start_date: str = "2010-01-01",
    end_date: str = "2024-01-01",
    initial_capital: float = 100000,
    target_cagr: float = 0.20
) -> Dict:
    """
    Run a single backtest with specified parameters.
    """
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        target_cagr=target_cagr,
        strategy=strategy
    )

    bt = Backtester(config, strategy_name=strategy)
    results = bt.run(data, start_date, end_date)

    return results, bt


def run_decade_analysis(
    data: Dict[str, pd.DataFrame],
    strategy: str = "combined",
    start_year: int = 1990,
    end_year: int = 2024
) -> pd.DataFrame:
    """
    Run backtests for each decade to validate 20% CAGR target.
    """
    results = []

    # Test overlapping 10-year periods
    for decade_start in range(start_year, end_year - 9, 5):
        decade_end = decade_start + 10

        try:
            metrics, bt = run_single_backtest(
                data,
                strategy=strategy,
                start_date=f"{decade_start}-01-01",
                end_date=f"{decade_end}-01-01"
            )

            results.append({
                'period': f"{decade_start}-{decade_end}",
                'start_year': decade_start,
                'end_year': decade_end,
                'cagr': metrics['cagr'],
                'sharpe': metrics['sharpe_ratio'],
                'max_dd': metrics['max_drawdown'],
                'trades': metrics['total_trades'],
                'win_rate': metrics['win_rate'],
                'meets_target': metrics['cagr'] >= 0.20
            })

            print(f"{decade_start}-{decade_end}: CAGR={metrics['cagr']:.2%}, "
                  f"Sharpe={metrics['sharpe_ratio']:.2f}, "
                  f"MaxDD={metrics['max_drawdown']:.2%}")

        except Exception as e:
            print(f"Error for {decade_start}-{decade_end}: {e}")
            continue

    return pd.DataFrame(results)


def run_parameter_optimization(
    data: Dict[str, pd.DataFrame],
    strategy: str = "combined",
    start_date: str = "2010-01-01",
    end_date: str = "2024-01-01"
) -> pd.DataFrame:
    """
    Run parameter optimization to find best settings.
    """
    print("\nRunning parameter optimization...")

    param_grid = {
        'momentum_lookback': [3, 6, 12],
        'initial_position': [0.02, 0.03, 0.05],
        'max_position': [0.08, 0.10, 0.15],
        'atr_stop': [1.5, 2.0, 2.5, 3.0]
    }

    results = []
    total = (len(param_grid['momentum_lookback']) *
             len(param_grid['initial_position']) *
             len(param_grid['max_position']) *
             len(param_grid['atr_stop']))

    pbar = tqdm(total=total, desc="Optimizing")

    for mom_lb in param_grid['momentum_lookback']:
        for init_pos in param_grid['initial_position']:
            for max_pos in param_grid['max_position']:
                for atr_stop in param_grid['atr_stop']:
                    try:
                        config = BacktestConfig(
                            start_date=start_date,
                            end_date=end_date,
                            initial_capital=100000
                        )
                        config.momentum.lookback_months = mom_lb
                        config.risk.initial_position_pct = init_pos
                        config.risk.max_position_pct = max_pos
                        config.turtle.stop_atr_multiple = atr_stop

                        bt = Backtester(config, strategy_name=strategy)
                        metrics = bt.run(data, start_date, end_date, show_progress=False)

                        results.append({
                            'momentum_lookback': mom_lb,
                            'initial_position': init_pos,
                            'max_position': max_pos,
                            'atr_stop': atr_stop,
                            'cagr': metrics['cagr'],
                            'sharpe': metrics['sharpe_ratio'],
                            'max_dd': metrics['max_drawdown'],
                            'calmar': metrics['calmar_ratio'],
                            'win_rate': metrics['win_rate']
                        })

                    except Exception:
                        pass

                    pbar.update(1)

    pbar.close()

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('sharpe', ascending=False)

    return results_df


def run_walk_forward(
    data: Dict[str, pd.DataFrame],
    strategy: str = "combined",
    train_years: int = 5,
    test_years: int = 1,
    start_year: int = 2010,
    end_year: int = 2024
) -> pd.DataFrame:
    """
    Walk-forward optimization for robustness testing.
    """
    print("\nRunning walk-forward analysis...")

    results = []

    for year in range(start_year + train_years, end_year - test_years + 1):
        train_start = f"{year - train_years}-01-01"
        train_end = f"{year}-01-01"
        test_start = f"{year}-01-01"
        test_end = f"{year + test_years}-01-01"

        try:
            # Train period
            train_metrics, _ = run_single_backtest(
                data, strategy, train_start, train_end
            )

            # Test period (out of sample)
            test_metrics, _ = run_single_backtest(
                data, strategy, test_start, test_end
            )

            results.append({
                'train_period': f"{year - train_years}-{year}",
                'test_period': f"{year}-{year + test_years}",
                'train_cagr': train_metrics['cagr'],
                'test_cagr': test_metrics['cagr'],
                'train_sharpe': train_metrics['sharpe_ratio'],
                'test_sharpe': test_metrics['sharpe_ratio'],
                'degradation': train_metrics['cagr'] - test_metrics['cagr']
            })

            print(f"Train {year - train_years}-{year}: {train_metrics['cagr']:.2%} | "
                  f"Test {year}-{year + test_years}: {test_metrics['cagr']:.2%}")

        except Exception as e:
            print(f"Error for period ending {year}: {e}")

    return pd.DataFrame(results)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Trend Following Backtesting System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --strategy combined
  python main.py --strategy turtle --start 2015-01-01 --end 2024-01-01
  python main.py --optimize
  python main.py --decade-analysis
  python main.py --walk-forward
  python main.py --monte-carlo --simulations 500
        """
    )

    parser.add_argument(
        "--strategy",
        choices=["turtle", "momentum", "dual_momentum", "combined"],
        default="combined",
        help="Strategy to use (default: combined)"
    )

    parser.add_argument(
        "--start",
        default="2010-01-01",
        help="Start date (YYYY-MM-DD)"
    )

    parser.add_argument(
        "--end",
        default="2024-12-01",
        help="End date (YYYY-MM-DD)"
    )

    parser.add_argument(
        "--capital",
        type=float,
        default=100000,
        help="Initial capital (default: 100000)"
    )

    parser.add_argument(
        "--assets",
        nargs="+",
        choices=list(ASSET_UNIVERSE.keys()),
        help="Asset classes to include"
    )

    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Run parameter optimization"
    )

    parser.add_argument(
        "--decade-analysis",
        action="store_true",
        help="Run decade-by-decade CAGR analysis"
    )

    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help="Run walk-forward analysis"
    )

    parser.add_argument(
        "--monte-carlo",
        action="store_true",
        help="Run Monte Carlo simulation"
    )

    parser.add_argument(
        "--simulations",
        type=int,
        default=500,
        help="Number of Monte Carlo simulations"
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test with limited assets"
    )

    args = parser.parse_args()

    print("="*60)
    print("TREND FOLLOWING BACKTESTING SYSTEM")
    print("="*60)
    print(f"\nStrategy: {args.strategy}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Initial Capital: ${args.capital:,.0f}")
    print(f"Target CAGR: 20%")
    print()

    # Fetch data
    if args.quick:
        # Quick test with core ETFs only
        quick_tickers = ["SPY", "QQQ", "EFA", "EEM", "GLD", "TLT", "USO"]
        fetcher = DataFetcher()
        data = fetcher.fetch_multiple(quick_tickers, args.start, args.end)
    else:
        data = fetch_data(args.start, args.end, args.assets)

    if not data:
        print("Error: No data fetched. Exiting.")
        sys.exit(1)

    # Run analysis based on arguments
    if args.optimize:
        results_df = run_parameter_optimization(
            data, args.strategy, args.start, args.end
        )
        print("\nTop 10 Parameter Combinations:")
        print(results_df.head(10).to_string())

        # Save results
        results_df.to_csv("optimization_results.csv", index=False)
        print("\nResults saved to optimization_results.csv")

    elif args.decade_analysis:
        results_df = run_decade_analysis(data, args.strategy)
        print("\nDecade Analysis Summary:")
        print(results_df.to_string())

        # Calculate percentage meeting target
        if len(results_df) > 0:
            pct_meeting = results_df['meets_target'].mean() * 100
            print(f"\n{pct_meeting:.0f}% of periods met 20% CAGR target")

    elif args.walk_forward:
        results_df = run_walk_forward(data, args.strategy)
        print("\nWalk-Forward Analysis Summary:")
        print(results_df.to_string())

        # Calculate average degradation
        if len(results_df) > 0:
            avg_degradation = results_df['degradation'].mean()
            print(f"\nAverage performance degradation: {avg_degradation:.2%}")

    elif args.monte_carlo:
        print(f"\nRunning {args.simulations} Monte Carlo simulations...")

        config = BacktestConfig(
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.capital
        )
        bt = Backtester(config, strategy_name=args.strategy)

        mc = MonteCarloSimulator(bt, n_simulations=args.simulations)
        mc_results = mc.run_bootstrap(data)

        print("\nMonte Carlo Results:")
        print(f"  CAGR (median):     {mc_results['cagr'].median():.2%}")
        print(f"  CAGR (5th pct):    {mc_results['cagr'].quantile(0.05):.2%}")
        print(f"  CAGR (95th pct):   {mc_results['cagr'].quantile(0.95):.2%}")
        print(f"  Prob CAGR > 20%:   {(mc_results['cagr'] > 0.20).mean():.1%}")

        mc_results.to_csv("monte_carlo_results.csv", index=False)
        print("\nResults saved to monte_carlo_results.csv")

    else:
        # Standard backtest
        metrics, bt = run_single_backtest(
            data,
            strategy=args.strategy,
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.capital
        )

        print_results(metrics)

        # Show annual returns
        print("\nAnnual Returns:")
        annual = bt.get_annual_returns()
        for year, ret in annual.items():
            marker = "✓" if ret >= 0.20 else ""
            print(f"  {year}: {ret:>7.2%} {marker}")

        # Show decade analysis
        decade_df = bt.get_decade_cagr()
        if len(decade_df) > 0:
            print("\n10-Year Rolling CAGR:")
            for _, row in decade_df.iterrows():
                marker = "✓" if row['meets_target'] else "✗"
                print(f"  {row['period']}: {row['cagr']:.2%} {marker}")

        # Recommendations
        print("\n" + "="*60)
        print("RECOMMENDATIONS")
        print("="*60)

        if metrics['cagr'] >= 0.20:
            print("✓ Strategy meets 20% CAGR target!")
        else:
            gap = 0.20 - metrics['cagr']
            print(f"✗ Strategy is {gap:.2%} below 20% CAGR target")
            print("\nSuggestions to improve:")
            if metrics['win_rate'] < 0.45:
                print("  - Improve entry filters (tighter trend confirmation)")
            if abs(metrics['max_drawdown']) > 0.25:
                print("  - Reduce position sizes or tighten stops")
            if metrics['profit_factor'] < 2.0:
                print("  - Let winners run longer (wider trailing stops)")
            print("  - Consider adding more uncorrelated assets")
            print("  - Run parameter optimization: python main.py --optimize")


if __name__ == "__main__":
    main()
