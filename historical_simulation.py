#!/usr/bin/env python3
"""
Historical Simulation Report

Generates detailed year-by-year analysis showing:
- Which assets were picked
- Entry/exit dates and prices
- Holding duration
- When leverage was applied/removed
- Monthly and annual P&L breakdown

For pre-ETF era (before ~2000), uses futures and index proxies.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
import warnings

warnings.filterwarnings('ignore')

from config import BacktestConfig, FUTURES_PROXIES
from indicators import calculate_all_indicators
from strategies import CombinedStrategy
from adaptive_leverage import AdaptiveLeverageManager, LeverageConfig, ConvictionLevel


@dataclass
class DetailedTrade:
    """Detailed trade record for reporting."""
    ticker: str
    asset_name: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    direction: str  # 'LONG' or 'SHORT'
    holding_days: int
    pnl_pct: float
    pnl_dollars: float
    max_leverage: float
    leverage_dates: List[str]
    exit_reason: str


class HistoricalSimulator:
    """
    Runs detailed historical simulation with full reporting.
    """

    def __init__(
        self,
        initial_capital: float = 100000,
        use_leverage: bool = True,
        max_leverage: float = 2.0
    ):
        self.initial_capital = initial_capital
        self.use_leverage = use_leverage
        self.max_leverage = max_leverage

        self.strategy = CombinedStrategy()
        self.leverage_config = LeverageConfig(
            leverage_high=1.5,
            leverage_very_high=max_leverage
        )
        self.leverage_manager = AdaptiveLeverageManager(self.leverage_config)

        # Tracking
        self.trades: List[DetailedTrade] = []
        self.monthly_equity: Dict[str, float] = {}
        self.positions: Dict[str, Dict] = {}
        self.cash = initial_capital
        self.equity_history: List[Dict] = []

    def generate_synthetic_data(
        self,
        start_year: int = 1980,
        end_year: int = 1985
    ) -> Dict[str, pd.DataFrame]:
        """
        Generate synthetic but realistic historical data for simulation.

        Based on actual historical patterns:
        - 1980: High inflation, gold bull market, volatile equities
        - 1981-82: Recession, bond rally as rates peaked
        - 1983-85: Strong equity recovery, commodities mixed
        """
        np.random.seed(42)  # Reproducible

        start_date = pd.Timestamp(f"{start_year}-01-01")
        end_date = pd.Timestamp(f"{end_year}-12-31")
        dates = pd.date_range(start_date, end_date, freq='B')  # Business days

        data = {}

        # Define asset characteristics based on 1980s history
        assets = {
            'SP500': {
                'name': 'S&P 500 Index',
                'start_price': 107.94,  # Actual Jan 1980
                'annual_returns': [0.32, -0.05, 0.21, 0.23, 0.06, 0.31],  # 1980-1985
                'volatility': 0.15,
                'trend_strength': 0.6
            },
            'GOLD': {
                'name': 'Gold Futures',
                'start_price': 559.0,  # Jan 1980
                'annual_returns': [0.15, -0.32, 0.14, -0.16, -0.19, 0.06],
                'volatility': 0.25,
                'trend_strength': 0.7
            },
            'TBOND': {
                'name': '30-Year Treasury Bond',
                'start_price': 100.0,
                'annual_returns': [-0.04, 0.02, 0.40, 0.01, 0.15, 0.31],  # Big 1982 rally
                'volatility': 0.12,
                'trend_strength': 0.5
            },
            'CRUDE': {
                'name': 'Crude Oil Futures',
                'start_price': 37.0,
                'annual_returns': [0.45, 0.05, -0.10, -0.05, -0.12, 0.03],
                'volatility': 0.30,
                'trend_strength': 0.65
            },
            'WHEAT': {
                'name': 'Wheat Futures',
                'start_price': 4.50,
                'annual_returns': [0.10, -0.15, 0.05, -0.08, 0.12, -0.05],
                'volatility': 0.22,
                'trend_strength': 0.5
            },
            'DXY': {
                'name': 'US Dollar Index',
                'start_price': 85.0,
                'annual_returns': [0.02, 0.15, 0.12, 0.08, 0.10, -0.05],  # Strong dollar 80s
                'volatility': 0.10,
                'trend_strength': 0.55
            },
            'COPPER': {
                'name': 'Copper Futures',
                'start_price': 1.00,
                'annual_returns': [0.15, -0.25, -0.10, 0.20, 0.05, 0.08],
                'volatility': 0.25,
                'trend_strength': 0.55
            },
            'SILVER': {
                'name': 'Silver Futures',
                'start_price': 16.0,  # After Hunt brothers crash
                'annual_returns': [-0.60, -0.30, 0.25, -0.10, -0.15, 0.10],
                'volatility': 0.40,
                'trend_strength': 0.7
            }
        }

        for ticker, params in assets.items():
            # Generate price series
            n_days = len(dates)
            years = [d.year for d in dates]
            unique_years = sorted(set(years))

            prices = [params['start_price']]
            current_price = params['start_price']

            for i in range(1, n_days):
                year = dates[i].year
                year_idx = year - start_year
                if year_idx >= len(params['annual_returns']):
                    year_idx = len(params['annual_returns']) - 1

                # Daily drift from annual return
                daily_drift = params['annual_returns'][year_idx] / 252

                # Add trend component
                trend_noise = np.random.normal(0, 0.002) * params['trend_strength']

                # Daily volatility
                daily_vol = params['volatility'] / np.sqrt(252)
                random_return = np.random.normal(daily_drift + trend_noise, daily_vol)

                current_price = current_price * (1 + random_return)
                prices.append(max(current_price, 0.01))

            # Create OHLCV DataFrame
            closes = np.array(prices)
            highs = closes * (1 + np.abs(np.random.normal(0, 0.005, n_days)))
            lows = closes * (1 - np.abs(np.random.normal(0, 0.005, n_days)))
            opens = np.roll(closes, 1)
            opens[0] = closes[0]
            volumes = np.random.randint(10000, 100000, n_days)

            df = pd.DataFrame({
                'open': opens,
                'high': highs,
                'low': lows,
                'close': closes,
                'volume': volumes
            }, index=dates)

            df['asset_name'] = params['name']
            data[ticker] = df

        return data

    def run_simulation(
        self,
        data: Dict[str, pd.DataFrame],
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Run detailed simulation with full trade tracking.
        """
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)

        # Generate signals
        signal_data = {}
        asset_names = {}

        for ticker, df in data.items():
            try:
                asset_names[ticker] = df['asset_name'].iloc[0] if 'asset_name' in df.columns else ticker
                df_indicators = calculate_all_indicators(df.drop(columns=['asset_name'], errors='ignore'))
                signal_df = self.strategy.generate_signals(df_indicators, ticker)
                signal_data[ticker] = signal_df
            except Exception as e:
                print(f"Error with {ticker}: {e}")

        # Get trading dates
        all_dates = set()
        for df in signal_data.values():
            all_dates.update(df.index)
        dates = sorted([d for d in all_dates if start <= d <= end])

        print(f"\nRunning simulation from {dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")
        print(f"Assets: {', '.join(signal_data.keys())}")
        print("=" * 70)

        # Track leverage events
        leverage_events = []

        for date in dates:
            # Get current prices
            prices = {}
            for ticker, df in signal_data.items():
                if date in df.index:
                    prices[ticker] = df.loc[date, 'close']

            # Update existing positions
            for ticker in list(self.positions.keys()):
                if ticker not in prices:
                    continue

                pos = self.positions[ticker]
                current_price = prices[ticker]
                pos['current_price'] = current_price
                pos['days_held'] = (date - pos['entry_date']).days

                # Calculate current P&L
                if pos['direction'] == 1:
                    pos['pnl_pct'] = (current_price - pos['entry_price']) / pos['entry_price']
                else:
                    pos['pnl_pct'] = (pos['entry_price'] - current_price) / pos['entry_price']

                # Update peak
                pos['peak_pnl'] = max(pos.get('peak_pnl', 0), pos['pnl_pct'])

                # Check leverage conditions
                if self.use_leverage and pos['days_held'] >= 10:
                    signals_agreeing = 3 if pos['pnl_pct'] > 0.05 else 2
                    conviction = self.leverage_manager.calculate_conviction(
                        ticker=ticker,
                        signal_strength=0.7,
                        signals_agreeing=signals_agreeing,
                        total_signals=3,
                        current_profit_pct=pos['pnl_pct'],
                        days_held=pos['days_held']
                    )

                    new_leverage = self.leverage_manager.get_leverage_multiplier(
                        ticker=ticker,
                        conviction=conviction,
                        current_price=current_price,
                        entry_price=pos['entry_price'],
                        days_held=pos['days_held'],
                        current_date=date
                    )

                    if new_leverage != pos['leverage']:
                        old_lev = pos['leverage']
                        pos['leverage'] = new_leverage
                        pos['max_leverage'] = max(pos.get('max_leverage', 1.0), new_leverage)
                        pos['leverage_history'].append(f"{date.strftime('%Y-%m-%d')}: {old_lev:.1f}x → {new_leverage:.1f}x")

                        leverage_events.append({
                            'date': date,
                            'ticker': ticker,
                            'action': 'LEVERAGE UP' if new_leverage > old_lev else 'DELEVERAGE',
                            'old': old_lev,
                            'new': new_leverage,
                            'profit': pos['pnl_pct']
                        })

            # Process signals
            for ticker, df in signal_data.items():
                if date not in df.index:
                    continue

                row = df.loc[date]
                signal = row.get('signal', 0)
                price = row['close']
                atr = row.get('atr_20', price * 0.02)

                # Exit existing position
                if ticker in self.positions:
                    pos = self.positions[ticker]
                    should_exit = False
                    exit_reason = ""

                    # Signal reversal
                    if signal != 0 and signal != pos['direction']:
                        should_exit = True
                        exit_reason = "Signal reversal"
                    # Signal gone
                    elif signal == 0 and pos['days_held'] > 5:
                        should_exit = True
                        exit_reason = "Signal neutral"
                    # Stop loss
                    elif pos['pnl_pct'] < -0.08:
                        should_exit = True
                        exit_reason = "Stop loss (-8%)"

                    if should_exit:
                        self._close_position(ticker, date, price, exit_reason, asset_names.get(ticker, ticker))

                # Enter new position
                elif signal != 0:
                    self._open_position(ticker, date, price, signal, atr, asset_names.get(ticker, ticker))

            # Record daily equity
            equity = self._calculate_equity(prices)
            self.equity_history.append({
                'date': date,
                'equity': equity,
                'positions': len(self.positions)
            })

            # Monthly snapshot
            month_key = date.strftime('%Y-%m')
            if month_key not in self.monthly_equity:
                self.monthly_equity[month_key] = equity

        # Close any remaining positions
        for ticker in list(self.positions.keys()):
            if ticker in prices:
                self._close_position(ticker, dates[-1], prices[ticker], "End of period", asset_names.get(ticker, ticker))

        return {
            'trades': self.trades,
            'leverage_events': leverage_events,
            'monthly_equity': self.monthly_equity,
            'equity_history': self.equity_history,
            'final_equity': self.equity_history[-1]['equity'] if self.equity_history else self.initial_capital
        }

    def _open_position(self, ticker: str, date: pd.Timestamp, price: float, signal: int, atr: float, asset_name: str):
        """Open a new position."""
        position_size = self.cash * 0.05  # 5% per position
        shares = position_size / price

        self.positions[ticker] = {
            'entry_date': date,
            'entry_price': price,
            'shares': shares,
            'direction': signal,
            'current_price': price,
            'days_held': 0,
            'pnl_pct': 0,
            'peak_pnl': 0,
            'leverage': 1.0,
            'max_leverage': 1.0,
            'leverage_history': [],
            'asset_name': asset_name,
            'atr': atr
        }

        self.cash -= position_size

    def _close_position(self, ticker: str, date: pd.Timestamp, price: float, reason: str, asset_name: str):
        """Close position and record trade."""
        if ticker not in self.positions:
            return

        pos = self.positions[ticker]

        # Calculate P&L with leverage effect
        base_pnl_pct = pos['pnl_pct']
        avg_leverage = (1.0 + pos['max_leverage']) / 2  # Approximate
        leveraged_pnl_pct = base_pnl_pct * avg_leverage

        position_value = pos['shares'] * pos['entry_price']
        pnl_dollars = position_value * leveraged_pnl_pct

        trade = DetailedTrade(
            ticker=ticker,
            asset_name=asset_name,
            entry_date=pos['entry_date'],
            exit_date=date,
            entry_price=pos['entry_price'],
            exit_price=price,
            direction='LONG' if pos['direction'] == 1 else 'SHORT',
            holding_days=pos['days_held'],
            pnl_pct=leveraged_pnl_pct,
            pnl_dollars=pnl_dollars,
            max_leverage=pos['max_leverage'],
            leverage_dates=pos['leverage_history'],
            exit_reason=reason
        )

        self.trades.append(trade)
        self.cash += position_value + pnl_dollars

        self.leverage_manager.reset_position(ticker)
        del self.positions[ticker]

    def _calculate_equity(self, prices: Dict[str, float]) -> float:
        """Calculate current portfolio equity."""
        position_value = 0
        for ticker, pos in self.positions.items():
            if ticker in prices:
                base_value = pos['shares'] * prices[ticker]
                # Account for leverage
                entry_value = pos['shares'] * pos['entry_price']
                pnl = (base_value - entry_value) * pos['leverage']
                position_value += entry_value + pnl

        return self.cash + position_value

    def generate_report(self, results: Dict) -> str:
        """Generate detailed text report."""
        report = []
        report.append("\n" + "=" * 70)
        report.append("HISTORICAL SIMULATION REPORT: 1980-1985")
        report.append("=" * 70)

        # Summary
        initial = self.initial_capital
        final = results['final_equity']
        total_return = (final - initial) / initial
        years = 5
        cagr = (final / initial) ** (1/years) - 1

        report.append(f"\nPERFORMANCE SUMMARY")
        report.append("-" * 40)
        report.append(f"Initial Capital:  ${initial:,.0f}")
        report.append(f"Final Equity:     ${final:,.0f}")
        report.append(f"Total Return:     {total_return:+.1%}")
        report.append(f"CAGR:             {cagr:+.1%}")
        report.append(f"Total Trades:     {len(self.trades)}")

        # Year by year
        report.append(f"\n\nYEAR-BY-YEAR BREAKDOWN")
        report.append("=" * 70)

        trades_by_year = {}
        for trade in self.trades:
            year = trade.entry_date.year
            if year not in trades_by_year:
                trades_by_year[year] = []
            trades_by_year[year].append(trade)

        for year in sorted(trades_by_year.keys()):
            year_trades = trades_by_year[year]
            year_pnl = sum(t.pnl_dollars for t in year_trades)
            winners = sum(1 for t in year_trades if t.pnl_pct > 0)
            losers = len(year_trades) - winners

            report.append(f"\n{'─' * 70}")
            report.append(f"YEAR {year}")
            report.append(f"{'─' * 70}")
            report.append(f"Trades: {len(year_trades)} | Winners: {winners} | Losers: {losers} | Net P&L: ${year_pnl:+,.0f}")
            report.append("")

            for trade in year_trades:
                lev_str = f" [Max {trade.max_leverage:.1f}x]" if trade.max_leverage > 1.0 else ""
                report.append(f"  {trade.direction:5s} {trade.asset_name:20s}")
                report.append(f"        Entry:  {trade.entry_date.strftime('%Y-%m-%d')} @ ${trade.entry_price:,.2f}")
                report.append(f"        Exit:   {trade.exit_date.strftime('%Y-%m-%d')} @ ${trade.exit_price:,.2f}")
                report.append(f"        Held:   {trade.holding_days} days | P&L: {trade.pnl_pct:+.1%} (${trade.pnl_dollars:+,.0f}){lev_str}")
                report.append(f"        Reason: {trade.exit_reason}")

                if trade.leverage_dates:
                    report.append(f"        Leverage events:")
                    for lev_event in trade.leverage_dates:
                        report.append(f"          • {lev_event}")
                report.append("")

        # Leverage summary
        leveraged_trades = [t for t in self.trades if t.max_leverage > 1.0]
        if leveraged_trades:
            report.append(f"\n\nLEVERAGE USAGE SUMMARY")
            report.append("-" * 40)
            report.append(f"Trades with leverage: {len(leveraged_trades)} / {len(self.trades)}")
            avg_max_lev = np.mean([t.max_leverage for t in leveraged_trades])
            report.append(f"Average max leverage: {avg_max_lev:.2f}x")

            lev_pnl = sum(t.pnl_dollars for t in leveraged_trades)
            unlev_pnl = sum(t.pnl_dollars for t in self.trades if t.max_leverage == 1.0)
            report.append(f"P&L from leveraged trades:   ${lev_pnl:+,.0f}")
            report.append(f"P&L from unleveraged trades: ${unlev_pnl:+,.0f}")

        # Best and worst trades
        report.append(f"\n\nNOTABLE TRADES")
        report.append("-" * 40)

        sorted_trades = sorted(self.trades, key=lambda t: t.pnl_dollars, reverse=True)
        report.append("Best trades:")
        for t in sorted_trades[:3]:
            report.append(f"  • {t.asset_name}: {t.pnl_pct:+.1%} (${t.pnl_dollars:+,.0f}) - held {t.holding_days} days")

        report.append("\nWorst trades:")
        for t in sorted_trades[-3:]:
            report.append(f"  • {t.asset_name}: {t.pnl_pct:+.1%} (${t.pnl_dollars:+,.0f}) - held {t.holding_days} days")

        report.append("\n" + "=" * 70)

        return "\n".join(report)


def run_1980_1985_simulation():
    """Run the 1980-1985 historical simulation."""
    print("\n" + "=" * 70)
    print("TREND FOLLOWING SIMULATION: 1980-1985")
    print("=" * 70)
    print("\nNote: Using synthetic data based on actual historical patterns")
    print("(ETFs didn't exist in 1980, so we simulate futures/indices)")

    simulator = HistoricalSimulator(
        initial_capital=100000,
        use_leverage=True,
        max_leverage=2.0
    )

    # Generate historical data
    data = simulator.generate_synthetic_data(1980, 1985)

    # Run simulation
    results = simulator.run_simulation(data, "1980-01-01", "1985-12-31")

    # Generate and print report
    report = simulator.generate_report(results)
    print(report)

    return results, simulator


if __name__ == "__main__":
    results, sim = run_1980_1985_simulation()
