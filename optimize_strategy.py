"""
Parameter Optimization for Trend-Following Strategy
Find optimal balance between CAGR and Max Drawdown
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass
import itertools


@dataclass
class Position:
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: float
    leverage: float = 1.0
    highest_price: float = 0.0
    days_profitable: int = 0


class FastBacktester:
    """Optimized backtester for parameter search"""

    def __init__(self, data: Dict[str, pd.DataFrame], initial_capital: float = 100000):
        self.data = data
        self.initial_capital = initial_capital
        self.all_dates = self._get_all_trading_dates()

    def _get_all_trading_dates(self):
        all_dates = set()
        for df in self.data.values():
            all_dates.update(df.index.tolist())
        return pd.DatetimeIndex(sorted(all_dates))

    def run(self, params: dict) -> dict:
        """Run backtest with given parameters"""
        capital = self.initial_capital
        positions = {}
        equity_curve = []
        peak_equity = self.initial_capital
        max_dd = 0

        start_dt = pd.Timestamp('1980-01-01')
        end_dt = pd.Timestamp('2024-12-31')
        trading_dates = [d for d in self.all_dates if start_dt <= d <= end_dt]

        for i, date in enumerate(trading_dates):
            if i < 252:
                continue

            # Process exits
            to_close = []
            for ticker, pos in list(positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue

                row = self.data[ticker].loc[date]
                price = row['Close']

                if price > pos.highest_price:
                    pos.highest_price = price

                pnl_pct = (price - pos.entry_price) / pos.entry_price

                # Track profitable days
                if pnl_pct > 0:
                    pos.days_profitable += 1

                # Update leverage based on profit and days
                if pos.days_profitable >= params['lev_confirm_days'] and pnl_pct >= params['lev_min_profit']:
                    pos.leverage = params['max_leverage']

                # Exit conditions
                should_exit = False
                # Stop loss
                if pnl_pct * pos.leverage <= params['stop_loss']:
                    should_exit = True
                # Trailing stop
                elif pos.highest_price > 0:
                    pullback = (pos.highest_price - price) / pos.highest_price
                    trail_mult = params['trail_lev'] if pos.leverage > 1 else params['trail_base']
                    atr = row.get('ATR', 0)
                    if not pd.isna(atr) and atr > 0:
                        if price < pos.highest_price - trail_mult * atr:
                            should_exit = True
                    elif pullback > params['exit_pullback']:
                        should_exit = True
                # Momentum reversal
                mom_1m = row.get('Mom_1m', 0)
                if not pd.isna(mom_1m) and mom_1m < params['mom_exit']:
                    should_exit = True

                # Deleverage triggers
                if pos.leverage > 1:
                    if pullback > params['delev_pullback']:
                        pos.leverage = 1.0
                    sma50 = row.get('SMA50')
                    if not pd.isna(sma50) and price < sma50:
                        pos.leverage = 1.0

                if should_exit:
                    to_close.append((ticker, price))

            for ticker, price in to_close:
                pos = positions[ticker]
                pnl = (price - pos.entry_price) * pos.shares * pos.leverage
                capital += pos.shares * pos.entry_price + pnl
                del positions[ticker]

            # New entries
            if len(positions) < params['max_positions']:
                for ticker in self.data:
                    if ticker in positions:
                        continue
                    if ticker not in self.data or date not in self.data[ticker].index:
                        continue

                    row = self.data[ticker].loc[date]

                    # Entry conditions
                    mom_12m = row.get('Mom_12m', 0)
                    mom_6m = row.get('Mom_6m', 0)
                    mom_3m = row.get('Mom_3m', 0)
                    mom_1m = row.get('Mom_1m', 0)
                    sma50 = row.get('SMA50')
                    sma200 = row.get('SMA200')

                    if pd.isna(mom_12m) or pd.isna(sma50) or pd.isna(sma200):
                        continue

                    score = 0
                    if mom_12m > params['entry_mom_12m']:
                        score += 1
                    if not pd.isna(mom_6m) and mom_6m > params['entry_mom_6m']:
                        score += 1
                    if not pd.isna(mom_3m) and mom_3m > params['entry_mom_3m']:
                        score += 1
                    if not pd.isna(mom_1m) and mom_1m > params['entry_mom_1m']:
                        score += 1

                    if score < params['min_score']:
                        continue
                    if row['Close'] < sma50 or sma50 < sma200:
                        continue

                    price = row['Close']
                    pos_value = capital * params['position_size']
                    shares = pos_value / price

                    positions[ticker] = Position(
                        ticker=ticker,
                        entry_date=date,
                        entry_price=price,
                        shares=shares,
                        leverage=1.0,
                        highest_price=price,
                        days_profitable=0
                    )
                    capital -= pos_value

                    if len(positions) >= params['max_positions']:
                        break

            # Portfolio value
            portfolio = capital
            for ticker, pos in positions.items():
                if ticker in self.data and date in self.data[ticker].index:
                    price = self.data[ticker].loc[date, 'Close']
                    upnl = (price - pos.entry_price) * pos.shares * pos.leverage
                    portfolio += pos.shares * pos.entry_price + upnl

            if portfolio > peak_equity:
                peak_equity = portfolio
            dd = (portfolio - peak_equity) / peak_equity
            if dd < max_dd:
                max_dd = dd

            equity_curve.append(portfolio)

        if len(equity_curve) < 100:
            return {'cagr': 0, 'max_dd': -1, 'calmar': 0}

        final = equity_curve[-1]
        years = len(equity_curve) / 252
        cagr = (final / self.initial_capital) ** (1/years) - 1 if years > 0 else 0
        calmar = abs(cagr / max_dd) if max_dd != 0 else 0

        return {
            'cagr': cagr,
            'max_dd': max_dd,
            'calmar': calmar,
            'final': final
        }


def load_data(data_dir='historical_data'):
    """Load and prepare all data"""
    data = {}
    for filename in os.listdir(data_dir):
        if filename.endswith('.csv') and filename != 'data_summary.csv':
            ticker = filename.replace('.csv', '')
            filepath = os.path.join(data_dir, filename)
            try:
                df = pd.read_csv(filepath, header=[0, 1, 2])
                df.columns = [col[0] for col in df.columns]
                df = df.rename(columns={df.columns[0]: 'Date'})
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.dropna(subset=['Date'])
                df.set_index('Date', inplace=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                if 'Close' in df.columns and len(df) > 252:
                    # Calculate indicators
                    df['SMA50'] = df['Close'].rolling(50).mean()
                    df['SMA200'] = df['Close'].rolling(200).mean()
                    df['Mom_12m'] = df['Close'].pct_change(252)
                    df['Mom_6m'] = df['Close'].pct_change(126)
                    df['Mom_3m'] = df['Close'].pct_change(63)
                    df['Mom_1m'] = df['Close'].pct_change(21)
                    df['TR'] = np.maximum(df['High'] - df['Low'],
                                          np.maximum(abs(df['High'] - df['Close'].shift(1)),
                                                    abs(df['Low'] - df['Close'].shift(1))))
                    df['ATR'] = df['TR'].rolling(14).mean()
                    data[ticker] = df
            except:
                pass
    return data


def run_optimization():
    print("Loading data...")
    data = load_data()
    print(f"Loaded {len(data)} assets")

    bt = FastBacktester(data)

    # Parameter grid
    param_grid = {
        'entry_mom_12m': [0.08, 0.12, 0.15],
        'entry_mom_6m': [0.04, 0.06, 0.08],
        'entry_mom_3m': [0.02, 0.03, 0.04],
        'entry_mom_1m': [0.01, 0.02],
        'min_score': [2, 3],
        'max_leverage': [1.5, 2.0, 2.5],
        'lev_confirm_days': [5, 10, 15],
        'lev_min_profit': [0.02, 0.03, 0.05],
        'stop_loss': [-0.03, -0.04, -0.05],
        'trail_base': [2.0, 2.5],
        'trail_lev': [1.0, 1.5],
        'exit_pullback': [0.04, 0.05, 0.06],
        'delev_pullback': [0.015, 0.02],
        'mom_exit': [-0.03, -0.05],
        'position_size': [0.05, 0.06, 0.07],
        'max_positions': [10, 12, 15],
    }

    # Generate combinations (limited for speed)
    keys = list(param_grid.keys())
    combinations = list(itertools.product(*param_grid.values()))

    print(f"Total combinations: {len(combinations)}")
    print("Running optimization (sampling 500 combinations)...")

    # Sample for speed
    np.random.seed(42)
    if len(combinations) > 500:
        indices = np.random.choice(len(combinations), 500, replace=False)
        combinations = [combinations[i] for i in indices]

    results = []
    best_calmar = 0
    best_params = None
    best_result = None

    for i, combo in enumerate(combinations):
        params = dict(zip(keys, combo))

        result = bt.run(params)

        # Target: CAGR > 15% AND Max DD > -50%
        if result['cagr'] > 0.15 and result['max_dd'] > -0.50:
            results.append({**params, **result})

            if result['calmar'] > best_calmar:
                best_calmar = result['calmar']
                best_params = params
                best_result = result

        if (i + 1) % 50 == 0:
            print(f"  Tested {i+1}/{len(combinations)}...")
            if best_result:
                print(f"    Best so far: CAGR={best_result['cagr']*100:.1f}%, DD={best_result['max_dd']*100:.1f}%, Calmar={best_result['calmar']:.2f}")

    print("\n" + "=" * 70)
    print("OPTIMIZATION RESULTS")
    print("=" * 70)

    if best_result:
        print(f"\nBest Result (Calmar Ratio):")
        print(f"  CAGR:         {best_result['cagr']*100:.2f}%")
        print(f"  Max Drawdown: {best_result['max_dd']*100:.2f}%")
        print(f"  Calmar Ratio: {best_result['calmar']:.3f}")
        print(f"\nOptimal Parameters:")
        for k, v in best_params.items():
            print(f"  {k}: {v}")
    else:
        print("No configuration met the target (CAGR > 15%, DD > -50%)")

    # Show top 10 by Calmar
    if results:
        results_df = pd.DataFrame(results)
        results_df['calmar'] = results_df['cagr'] / abs(results_df['max_dd'])
        results_df = results_df.sort_values('calmar', ascending=False)

        print("\n\nTop 10 Configurations by Calmar Ratio:")
        print("-" * 70)
        for i, row in results_df.head(10).iterrows():
            print(f"CAGR: {row['cagr']*100:.1f}% | DD: {row['max_dd']*100:.1f}% | Calmar: {row['calmar']:.2f}")

        # Save results
        results_df.to_csv('optimization_results.csv', index=False)
        print("\nResults saved to optimization_results.csv")

    return best_params, best_result


if __name__ == '__main__':
    run_optimization()
