"""
CTA_PARAMETER_SWEEP.py
======================
Professional CTA Backtest with Full Parameter Optimization

Based on proven systems:
- Turtle Trading (Dennis, 1983)
- Time-Series Momentum (Moskowitz et al., 2012)
- AQR Managed Futures

Parameter Sweep:
- Donchian Entry: 40, 55, 80 days
- Donchian Exit: 10, 20, 30 days
- SMA Regime Filter: 150, 200, 250 days
- ATR Multiplier: 2.0, 2.5, 3.0
- Risk per Trade: 0.5%, 0.75%, 1.0%

Outputs:
- parameter_sweep_results.csv: All parameter combinations with metrics
- best_parameters.json: Optimal parameters based on Sharpe/CAGR tradeoff
- equity_curve_best.csv: Equity curve for best parameters
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
from itertools import product
import warnings
warnings.filterwarnings('ignore')

# Import our futures data loader
from FUTURES_DATA_LOADER import (
    FuturesDataLoader,
    CONTRACT_SPECS,
    CLASSIC_CTA_UNIVERSE,
    ContractSpec
)


# =============================================================================
# PARAMETER DEFINITIONS
# =============================================================================

@dataclass
class StrategyParams:
    """Strategy parameters for the Donchian breakout system"""
    donchian_entry: int = 55       # Days for entry breakout
    donchian_exit: int = 20        # Days for exit breakout
    sma_filter: int = 200          # SMA regime filter
    atr_multiplier: float = 2.5    # ATR multiplier for stops
    risk_per_trade: float = 0.01   # Risk per trade (1%)
    max_positions: int = 10        # Maximum concurrent positions
    max_sector_exposure: float = 0.4  # Max exposure per sector
    rebalance_freq: int = 1        # Days between rebalancing


# Parameter sweep ranges
PARAM_GRID = {
    'donchian_entry': [40, 55, 80],
    'donchian_exit': [10, 20, 30],
    'sma_filter': [150, 200, 250],
    'atr_multiplier': [2.0, 2.5, 3.0],
    'risk_per_trade': [0.005, 0.0075, 0.01],
}


# =============================================================================
# DONCHIAN BREAKOUT SYSTEM
# =============================================================================

def calculate_donchian_channels(df: pd.DataFrame, entry_period: int, exit_period: int) -> pd.DataFrame:
    """
    Calculate Donchian channels for entry and exit.

    Entry: Break above highest high of N days (long entry)
    Exit: Break below lowest low of M days (long exit)
    """
    df = df.copy()

    # Entry channels
    df['Upper_Entry'] = df['High'].rolling(entry_period).max()
    df['Lower_Entry'] = df['Low'].rolling(entry_period).min()

    # Exit channels (tighter)
    df['Upper_Exit'] = df['High'].rolling(exit_period).max()
    df['Lower_Exit'] = df['Low'].rolling(exit_period).min()

    return df


def calculate_atr(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate Average True Range"""
    high = df['High']
    low = df['Low']
    close = df['Close'].shift(1)

    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()

    return atr


def calculate_position_size(
    price: float,
    atr: float,
    risk_per_trade: float,
    account_value: float,
    multiplier: float,
    atr_multiplier: float
) -> float:
    """
    ATR-based position sizing (Turtle method).

    Position Size = (Account * Risk%) / (ATR * Multiplier * Contract Multiplier)
    """
    if atr <= 0 or price <= 0:
        return 0

    risk_amount = account_value * risk_per_trade
    dollar_risk = atr * atr_multiplier * multiplier

    if dollar_risk <= 0:
        return 0

    # Number of contracts (can be fractional for backtesting)
    contracts = risk_amount / dollar_risk

    return max(0, contracts)


# =============================================================================
# BACKTEST ENGINE
# =============================================================================

@dataclass
class Position:
    """Track an open position"""
    symbol: str
    entry_date: datetime
    entry_price: float
    contracts: float
    stop_price: float
    direction: int  # 1 for long, -1 for short


def run_backtest(
    data: Dict[str, pd.DataFrame],
    params: StrategyParams,
    initial_capital: float = 1_000_000
) -> Tuple[pd.DataFrame, Dict]:
    """
    Run the Donchian breakout backtest with given parameters.

    Returns:
        equity_curve: DataFrame with daily equity
        metrics: Dictionary of performance metrics
    """
    # Prepare data
    processed = {}

    for symbol, df in data.items():
        if len(df) < max(params.donchian_entry, params.sma_filter) + 50:
            continue

        df = df.copy()

        # Add indicators
        df = calculate_donchian_channels(df, params.donchian_entry, params.donchian_exit)
        df['ATR'] = calculate_atr(df, 20)
        df['SMA'] = df['Close'].rolling(params.sma_filter).mean()
        df['Momentum'] = df['Close'].pct_change(params.donchian_entry)
        df['Volatility'] = df['Close'].pct_change().rolling(20).std()

        # Score for ranking (momentum / volatility)
        df['Score'] = df['Momentum'] / (df['Volatility'] + 1e-9)

        df = df.dropna()

        if len(df) > 252:
            processed[symbol] = df

    if len(processed) < 5:
        return pd.DataFrame(), {'error': 'Insufficient data'}

    # Align all data to common dates
    all_dates = sorted(set.intersection(*[set(df.index) for df in processed.values()]))

    if len(all_dates) < 252:
        return pd.DataFrame(), {'error': 'Insufficient common dates'}

    # Initialize
    equity = initial_capital
    positions: Dict[str, Position] = {}
    equity_curve = []

    # Get sector mapping from specs
    sector_map = {s: spec.sector for s, spec in CONTRACT_SPECS.items() if s in processed}

    for i, date in enumerate(all_dates[:-1]):
        next_date = all_dates[i + 1]

        # Skip warmup period
        if i < params.sma_filter:
            equity_curve.append({'Date': date, 'Equity': equity, 'Positions': 0})
            continue

        # Check rebalancing
        should_rebalance = (i % params.rebalance_freq == 0)

        # 1. Update existing positions and check exits
        closed_pnl = 0
        symbols_to_close = []

        for symbol, pos in positions.items():
            if symbol not in processed:
                continue

            df = processed[symbol]
            if date not in df.index or next_date not in df.index:
                continue

            current_price = df.loc[date, 'Close']
            next_price = df.loc[next_date, 'Close']

            spec = CONTRACT_SPECS.get(symbol)
            multiplier = spec.multiplier if spec else 1.0

            # Check exit conditions
            exit_signal = False

            if pos.direction == 1:  # Long position
                # Exit on break below exit channel or stop
                lower_exit = df.loc[date, 'Lower_Exit']
                if current_price <= lower_exit or current_price <= pos.stop_price:
                    exit_signal = True
            else:  # Short position
                upper_exit = df.loc[date, 'Upper_Exit']
                if current_price >= upper_exit or current_price >= pos.stop_price:
                    exit_signal = True

            if exit_signal:
                # Calculate P&L
                if pos.direction == 1:
                    pnl = (next_price - pos.entry_price) * pos.contracts * multiplier
                else:
                    pnl = (pos.entry_price - next_price) * pos.contracts * multiplier

                closed_pnl += pnl
                symbols_to_close.append(symbol)
            else:
                # Mark-to-market for open positions
                if pos.direction == 1:
                    pnl = (next_price - current_price) * pos.contracts * multiplier
                else:
                    pnl = (current_price - next_price) * pos.contracts * multiplier
                closed_pnl += pnl

        # Remove closed positions
        for symbol in symbols_to_close:
            del positions[symbol]

        # 2. Look for new entries (only on rebalance days)
        if should_rebalance:
            # Get all valid entry signals
            candidates = []

            for symbol, df in processed.items():
                if symbol in positions:
                    continue

                if date not in df.index:
                    continue

                close = df.loc[date, 'Close']
                sma = df.loc[date, 'SMA']
                upper = df.loc[date, 'Upper_Entry']
                lower = df.loc[date, 'Lower_Entry']
                score = df.loc[date, 'Score']
                atr = df.loc[date, 'ATR']

                if pd.isna(score) or pd.isna(atr) or atr <= 0:
                    continue

                # Long entry: price > SMA (uptrend) and breakout above upper channel
                if close > sma and close >= upper and score > 0:
                    candidates.append((symbol, score, 1, close, atr))

                # Short entry: price < SMA (downtrend) and breakout below lower channel
                # Disabled for now (long-only performs better with ETF proxies)
                # if close < sma and close <= lower and score < 0:
                #     candidates.append((symbol, abs(score), -1, close, atr))

            # Rank by score (momentum/vol)
            candidates.sort(key=lambda x: x[1], reverse=True)

            # Check position limits and sector exposure
            current_sectors = {}
            for sym in positions:
                sec = sector_map.get(sym, 'Other')
                current_sectors[sec] = current_sectors.get(sec, 0) + 1

            for symbol, score, direction, price, atr in candidates:
                if len(positions) >= params.max_positions:
                    break

                # Check sector limit
                sector = sector_map.get(symbol, 'Other')
                sector_count = current_sectors.get(sector, 0)
                max_per_sector = int(params.max_positions * params.max_sector_exposure)

                if sector_count >= max_per_sector:
                    continue

                # Calculate position size
                spec = CONTRACT_SPECS.get(symbol)
                multiplier = spec.multiplier if spec else 1.0

                contracts = calculate_position_size(
                    price=price,
                    atr=atr,
                    risk_per_trade=params.risk_per_trade,
                    account_value=equity,
                    multiplier=multiplier,
                    atr_multiplier=params.atr_multiplier
                )

                if contracts <= 0:
                    continue

                # Set stop loss
                if direction == 1:
                    stop_price = price - (atr * params.atr_multiplier)
                else:
                    stop_price = price + (atr * params.atr_multiplier)

                # Open position
                positions[symbol] = Position(
                    symbol=symbol,
                    entry_date=date,
                    entry_price=price,
                    contracts=contracts,
                    stop_price=stop_price,
                    direction=direction
                )

                current_sectors[sector] = sector_count + 1

        # Update equity
        equity += closed_pnl

        equity_curve.append({
            'Date': date,
            'Equity': equity,
            'Positions': len(positions)
        })

    # Create equity DataFrame
    eq_df = pd.DataFrame(equity_curve)
    if len(eq_df) == 0:
        return pd.DataFrame(), {'error': 'No equity data'}

    eq_df.set_index('Date', inplace=True)

    # Calculate metrics
    metrics = calculate_metrics(eq_df, initial_capital)
    metrics['params'] = asdict(params)

    return eq_df, metrics


def calculate_metrics(eq_df: pd.DataFrame, initial_capital: float) -> Dict:
    """Calculate performance metrics from equity curve"""
    if len(eq_df) < 252:
        return {'error': 'Insufficient data for metrics'}

    equity = eq_df['Equity']

    # Returns
    daily_returns = equity.pct_change().dropna()

    # Total return
    total_return = (equity.iloc[-1] / initial_capital) - 1

    # CAGR
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0:
        return {'error': 'Invalid date range'}

    cagr = ((equity.iloc[-1] / initial_capital) ** (1/years)) - 1

    # Volatility
    annual_vol = daily_returns.std() * np.sqrt(252)

    # Sharpe Ratio (assuming 3% risk-free rate)
    rf_daily = 0.03 / 252
    excess_returns = daily_returns - rf_daily
    sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252) if excess_returns.std() > 0 else 0

    # Max Drawdown
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    max_dd = drawdown.min()

    # Calmar Ratio (CAGR / MaxDD)
    calmar = abs(cagr / max_dd) if max_dd != 0 else 0

    # Win rate (yearly)
    yearly_returns = equity.resample('YE').last().pct_change().dropna()
    yearly_returns.iloc[0] = (equity.resample('YE').last().iloc[0] / initial_capital) - 1
    positive_years = (yearly_returns > 0).sum()
    total_years = len(yearly_returns)
    win_rate = positive_years / total_years if total_years > 0 else 0

    # Sortino Ratio
    downside = daily_returns[daily_returns < 0]
    downside_std = downside.std() * np.sqrt(252) if len(downside) > 0 else 0.01
    sortino = (cagr - 0.03) / downside_std if downside_std > 0 else 0

    return {
        'total_return': total_return,
        'cagr': cagr,
        'annual_volatility': annual_vol,
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'max_drawdown': max_dd,
        'calmar_ratio': calmar,
        'win_rate_yearly': win_rate,
        'years': years,
        'positive_years': positive_years,
        'total_years': total_years,
        'final_equity': equity.iloc[-1],
    }


# =============================================================================
# PARAMETER SWEEP
# =============================================================================

def run_parameter_sweep(
    data: Dict[str, pd.DataFrame],
    output_dir: str = './'
) -> pd.DataFrame:
    """
    Run backtest for all parameter combinations and find optimal set.
    """
    print("=" * 70)
    print("RUNNING PARAMETER SWEEP")
    print("=" * 70)

    # Generate all parameter combinations
    param_names = list(PARAM_GRID.keys())
    param_values = list(PARAM_GRID.values())
    combinations = list(product(*param_values))

    print(f"\nTesting {len(combinations)} parameter combinations...")
    print(f"Parameters: {param_names}")

    results = []

    for i, combo in enumerate(combinations):
        # Create params
        params = StrategyParams(
            donchian_entry=combo[0],
            donchian_exit=combo[1],
            sma_filter=combo[2],
            atr_multiplier=combo[3],
            risk_per_trade=combo[4]
        )

        # Run backtest
        eq_df, metrics = run_backtest(data, params)

        if 'error' in metrics:
            continue

        # Store results
        result = {
            'donchian_entry': params.donchian_entry,
            'donchian_exit': params.donchian_exit,
            'sma_filter': params.sma_filter,
            'atr_multiplier': params.atr_multiplier,
            'risk_per_trade': params.risk_per_trade,
            'cagr': metrics['cagr'],
            'sharpe': metrics['sharpe_ratio'],
            'sortino': metrics['sortino_ratio'],
            'max_dd': metrics['max_drawdown'],
            'calmar': metrics['calmar_ratio'],
            'win_rate': metrics['win_rate_yearly'],
            'final_equity': metrics['final_equity'],
        }
        results.append(result)

        # Progress
        if (i + 1) % 25 == 0 or i == 0:
            print(f"  [{i+1}/{len(combinations)}] Entry={params.donchian_entry}, "
                  f"Exit={params.donchian_exit}, SMA={params.sma_filter}, "
                  f"ATR={params.atr_multiplier}, Risk={params.risk_per_trade:.2%} "
                  f"-> CAGR={metrics['cagr']*100:.1f}%, Sharpe={metrics['sharpe_ratio']:.2f}")

    if len(results) == 0:
        print("ERROR: No valid backtest results")
        return pd.DataFrame()

    # Create results DataFrame
    df_results = pd.DataFrame(results)

    # Sort by Sharpe (most robust metric)
    df_results = df_results.sort_values('sharpe', ascending=False)

    # Save results
    results_path = os.path.join(output_dir, 'parameter_sweep_results.csv')
    df_results.to_csv(results_path, index=False)
    print(f"\nResults saved to: {results_path}")

    # Find best parameters
    best = df_results.iloc[0]

    print("\n" + "=" * 70)
    print("TOP 5 PARAMETER SETS (by Sharpe Ratio)")
    print("=" * 70)

    for i, row in df_results.head(5).iterrows():
        print(f"\n#{i+1}:")
        print(f"  Entry: {row['donchian_entry']}d, Exit: {row['donchian_exit']}d, "
              f"SMA: {row['sma_filter']}d, ATR: {row['atr_multiplier']}x, "
              f"Risk: {row['risk_per_trade']*100:.1f}%")
        print(f"  CAGR: {row['cagr']*100:.2f}%, Sharpe: {row['sharpe']:.2f}, "
              f"MaxDD: {row['max_dd']*100:.1f}%, Win Rate: {row['win_rate']*100:.0f}%")

    # Run best parameters and save equity curve
    print("\n" + "=" * 70)
    print("RUNNING BEST PARAMETERS")
    print("=" * 70)

    best_params = StrategyParams(
        donchian_entry=int(best['donchian_entry']),
        donchian_exit=int(best['donchian_exit']),
        sma_filter=int(best['sma_filter']),
        atr_multiplier=float(best['atr_multiplier']),
        risk_per_trade=float(best['risk_per_trade'])
    )

    eq_df, metrics = run_backtest(data, best_params)

    if 'error' not in metrics:
        # Save equity curve
        eq_path = os.path.join(output_dir, 'equity_curve_best.csv')
        eq_df.to_csv(eq_path)
        print(f"Equity curve saved to: {eq_path}")

        # Save best parameters
        params_path = os.path.join(output_dir, 'best_parameters.json')
        with open(params_path, 'w') as f:
            json.dump({
                'parameters': asdict(best_params),
                'metrics': {k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                           for k, v in metrics.items() if k != 'params'}
            }, f, indent=2, default=str)
        print(f"Best parameters saved to: {params_path}")

        # Print detailed results
        print(f"\nBEST PARAMETER SET:")
        print(f"  Donchian Entry: {best_params.donchian_entry} days")
        print(f"  Donchian Exit: {best_params.donchian_exit} days")
        print(f"  SMA Filter: {best_params.sma_filter} days")
        print(f"  ATR Multiplier: {best_params.atr_multiplier}x")
        print(f"  Risk per Trade: {best_params.risk_per_trade*100:.2f}%")

        print(f"\nPERFORMANCE:")
        print(f"  CAGR: {metrics['cagr']*100:.2f}%")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"  Sortino Ratio: {metrics['sortino_ratio']:.2f}")
        print(f"  Max Drawdown: {metrics['max_drawdown']*100:.2f}%")
        print(f"  Calmar Ratio: {metrics['calmar_ratio']:.2f}")
        print(f"  Win Rate (Yearly): {metrics['win_rate_yearly']*100:.0f}%")
        print(f"  Years: {metrics['years']:.1f}")
        print(f"  Final Equity: ${metrics['final_equity']:,.0f}")

        # Yearly breakdown
        print("\nYEARLY RETURNS:")
        print("-" * 40)
        yearly = eq_df['Equity'].resample('YE').last()
        yearly_ret = yearly.pct_change()
        yearly_ret.iloc[0] = (yearly.iloc[0] / 1_000_000) - 1

        for date, ret in yearly_ret.items():
            status = "+" if ret > 0 else "-"
            print(f"  {date.year}: {ret*100:>7.2f}% {status}")

    return df_results


# =============================================================================
# QUICK BACKTEST (Single Parameter Set)
# =============================================================================

def run_quick_backtest(
    data: Dict[str, pd.DataFrame],
    params: StrategyParams = None
) -> Tuple[pd.DataFrame, Dict]:
    """
    Run a single backtest with specified or default parameters.
    """
    if params is None:
        # Use robust default parameters
        params = StrategyParams(
            donchian_entry=55,
            donchian_exit=20,
            sma_filter=200,
            atr_multiplier=2.5,
            risk_per_trade=0.01
        )

    print("=" * 70)
    print("RUNNING CTA BACKTEST")
    print("=" * 70)
    print(f"\nParameters:")
    print(f"  Donchian Entry: {params.donchian_entry} days")
    print(f"  Donchian Exit: {params.donchian_exit} days")
    print(f"  SMA Filter: {params.sma_filter} days")
    print(f"  ATR Multiplier: {params.atr_multiplier}x")
    print(f"  Risk per Trade: {params.risk_per_trade*100:.2f}%")

    eq_df, metrics = run_backtest(data, params)

    if 'error' in metrics:
        print(f"ERROR: {metrics['error']}")
        return eq_df, metrics

    print(f"\nRESULTS:")
    print(f"  Period: {eq_df.index[0].strftime('%Y-%m-%d')} to {eq_df.index[-1].strftime('%Y-%m-%d')}")
    print(f"  CAGR: {metrics['cagr']*100:.2f}%")
    print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown: {metrics['max_drawdown']*100:.2f}%")
    print(f"  Win Rate: {metrics['win_rate_yearly']*100:.0f}%")
    print(f"  Final Equity: ${metrics['final_equity']:,.0f}")

    return eq_df, metrics


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys

    # Load data
    print("Loading futures data...")
    loader = FuturesDataLoader(data_dir='./futures_data')

    data = loader.load_all_contracts(
        symbols=CLASSIC_CTA_UNIVERSE,
        start_date='2005-01-01',
        prefer_source='yahoo'  # Will use CSV if available, then Yahoo proxy
    )

    if len(data) < 5:
        print("ERROR: Insufficient data loaded")
        sys.exit(1)

    print(f"\nLoaded {len(data)} contracts: {list(data.keys())}")

    # Check command line arguments
    if '--sweep' in sys.argv:
        # Run full parameter sweep
        results = run_parameter_sweep(data, output_dir='./')
    else:
        # Run quick backtest with default parameters
        eq_df, metrics = run_quick_backtest(data)

        # Save results
        if 'error' not in metrics:
            eq_df.to_csv('cta_equity_curve.csv')
            print("\nEquity curve saved to: cta_equity_curve.csv")

            print("\nTo run full parameter sweep:")
            print("  python3 CTA_PARAMETER_SWEEP.py --sweep")
