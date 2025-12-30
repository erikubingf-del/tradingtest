"""
Enhanced Backtester with Adaptive Leverage

This extends the base backtester to apply dynamic leverage based on
trend conviction, allowing the strategy to reach ~20% CAGR target.

Key concept: Only leverage during the "90% probability" phase of trends.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from tqdm import tqdm

from config import BacktestConfig
from backtester import Backtester, Trade, PortfolioState, print_results
from adaptive_leverage import (
    AdaptiveLeverageManager, LeverageConfig, ConvictionLevel,
    TrendPhaseDetector
)
from indicators import calculate_all_indicators
from strategies import create_strategy


@dataclass
class LeveragedTrade(Trade):
    """Trade with leverage information."""
    leverage_used: float = 1.0
    max_leverage: float = 1.0
    conviction_at_entry: str = "LOW"


class LeveragedBacktester(Backtester):
    """
    Backtester with adaptive leverage based on trend conviction.

    Strategy:
    1. Enter positions at 1x (no leverage) with 2-5% allocation
    2. Once trend is CONFIRMED (3%+ profit, signals agree): apply 1.5x
    3. When trend is STRONG (8%+ profit, all signals agree): apply 2x
    4. Reduce leverage when: pullback from peak, momentum weakening, extended duration
    5. Exit normally based on signals/stops
    """

    def __init__(
        self,
        config: BacktestConfig = None,
        strategy_name: str = "combined",
        leverage_config: LeverageConfig = None
    ):
        super().__init__(config, strategy_name)

        self.leverage_config = leverage_config or LeverageConfig()
        self.leverage_manager = AdaptiveLeverageManager(self.leverage_config)
        self.phase_detector = TrendPhaseDetector()

        # Track leverage usage
        self.leverage_history: List[Dict] = []
        self.total_leveraged_exposure = 0.0

    def execute_entry(
        self,
        ticker: str,
        date: pd.Timestamp,
        price: float,
        signal: int,
        atr: float,
        volatility: float,
        signal_strength: float = 0.5,
        signals_agreeing: int = 1,
        total_signals: int = 3
    ) -> Optional[Dict]:
        """
        Execute entry - always at 1x leverage initially.
        """
        if ticker in self.portfolio.positions:
            return None

        portfolio_value = self.portfolio.total_value()

        # Calculate base position weight (no leverage on entry)
        if hasattr(self.strategy, 'calculate_weight'):
            weight = self.strategy.calculate_weight(abs(signal), volatility)
        else:
            weight = self.config.risk.initial_position_pct

        # Apply risk manager (no leverage adjustment yet)
        weight = self.risk_manager.apply_drawdown_rule(portfolio_value, weight)

        # Calculate shares
        position_value = portfolio_value * weight
        shares = int(position_value / price)

        if shares <= 0:
            return None

        # Calculate costs
        is_crypto = '-USD' in ticker or 'BTC' in ticker
        cost = self.calculate_transaction_cost(shares, price, is_crypto)

        required_cash = shares * price + cost
        if required_cash > self.portfolio.cash:
            available = self.portfolio.cash - cost
            shares = int(available / price)
            if shares <= 0:
                return None

        # Stop price
        if signal > 0:
            stop_price = price - 2 * atr
        else:
            stop_price = price + 2 * atr

        # Execute at 1x leverage
        self.portfolio.cash -= shares * price + cost

        position = {
            'ticker': ticker,
            'entry_date': date,
            'entry_price': price,
            'shares': shares,
            'base_shares': shares,  # Track original shares
            'direction': signal,
            'stop_price': stop_price,
            'current_price': price,
            'peak_price': price,
            'weight': weight,
            'base_weight': weight,
            'atr': atr,
            'cost': cost,
            'leverage': 1.0,
            'signal_strength': signal_strength,
            'signals_agreeing': signals_agreeing,
            'total_signals': total_signals,
            'days_held': 0,
            'peak_profit_pct': 0.0
        }

        self.portfolio.positions[ticker] = position
        return position

    def update_leverage(
        self,
        ticker: str,
        date: pd.Timestamp,
        current_price: float,
        signal_strength: float,
        signals_agreeing: int,
        total_signals: int,
        momentum: float = 0.0,
        momentum_prev: float = 0.0
    ):
        """
        Update leverage for existing position based on conviction.
        """
        if ticker not in self.portfolio.positions:
            return

        position = self.portfolio.positions[ticker]
        entry_price = position['entry_price']
        direction = position['direction']

        # Calculate current profit
        if direction > 0:
            profit_pct = (current_price - entry_price) / entry_price
        else:
            profit_pct = (entry_price - current_price) / entry_price

        # Update peak
        position['peak_price'] = max(position['peak_price'], current_price) if direction > 0 \
            else min(position.get('peak_price', current_price), current_price)

        # Calculate peak profit
        if direction > 0:
            peak_profit_pct = (position['peak_price'] - entry_price) / entry_price
        else:
            peak_profit_pct = (entry_price - position['peak_price']) / entry_price

        position['peak_profit_pct'] = max(position.get('peak_profit_pct', 0), peak_profit_pct)

        # Days held
        position['days_held'] = (date - position['entry_date']).days

        # Check if we should deleverage
        if position['leverage'] > 1.0:
            should_delever = self.leverage_manager.should_deleverage(
                ticker=ticker,
                signal_strength=signal_strength,
                momentum=momentum,
                momentum_prev=momentum_prev,
                profit_pct=profit_pct,
                peak_profit_pct=position['peak_profit_pct']
            )

            if should_delever:
                # Reduce leverage
                self._adjust_leverage(ticker, date, current_price, 1.0)
                self.leverage_history.append({
                    'date': date,
                    'ticker': ticker,
                    'action': 'deleverage',
                    'reason': 'trend_weakening',
                    'old_leverage': position['leverage'],
                    'new_leverage': 1.0
                })
                return

        # Calculate new conviction
        conviction = self.leverage_manager.calculate_conviction(
            ticker=ticker,
            signal_strength=signal_strength,
            signals_agreeing=signals_agreeing,
            total_signals=total_signals,
            current_profit_pct=profit_pct,
            days_held=position['days_held']
        )

        # Get recommended leverage
        new_leverage = self.leverage_manager.get_leverage_multiplier(
            ticker=ticker,
            conviction=conviction,
            current_price=current_price,
            entry_price=entry_price,
            days_held=position['days_held'],
            current_date=date
        )

        # Check portfolio leverage limits
        new_leverage, actual = self.leverage_manager.calculate_leveraged_position(
            position['base_weight'],
            new_leverage,
            self.total_leveraged_exposure
        )
        new_leverage = actual

        # Only increase leverage, or reduce if mandated
        old_leverage = position['leverage']
        if new_leverage > old_leverage or new_leverage < old_leverage * 0.8:
            self._adjust_leverage(ticker, date, current_price, new_leverage)

            if new_leverage != old_leverage:
                self.leverage_history.append({
                    'date': date,
                    'ticker': ticker,
                    'action': 'leverage_change',
                    'conviction': conviction.name,
                    'old_leverage': old_leverage,
                    'new_leverage': new_leverage,
                    'profit_pct': profit_pct
                })

    def _adjust_leverage(
        self,
        ticker: str,
        date: pd.Timestamp,
        price: float,
        new_leverage: float
    ):
        """
        Adjust position leverage by buying/selling shares.
        """
        position = self.portfolio.positions[ticker]
        old_leverage = position['leverage']

        if abs(new_leverage - old_leverage) < 0.1:
            return

        base_shares = position['base_shares']
        old_shares = position['shares']
        new_shares = int(base_shares * new_leverage)

        share_diff = new_shares - old_shares

        if share_diff == 0:
            return

        is_crypto = '-USD' in ticker or 'BTC' in ticker
        cost = self.calculate_transaction_cost(abs(share_diff), price, is_crypto)

        if share_diff > 0:
            # Buying more (increasing leverage)
            required = share_diff * price + cost
            if required > self.portfolio.cash:
                # Reduce to what we can afford
                affordable_shares = int((self.portfolio.cash - cost) / price)
                if affordable_shares <= 0:
                    return
                share_diff = affordable_shares
                new_shares = old_shares + share_diff

            self.portfolio.cash -= share_diff * price + cost
        else:
            # Selling (reducing leverage)
            self.portfolio.cash += abs(share_diff) * price - cost

        # Update position
        position['shares'] = new_shares
        position['leverage'] = new_shares / base_shares if base_shares > 0 else 1.0
        position['cost'] += cost

        # Update total leveraged exposure
        self._update_leveraged_exposure()

    def _update_leveraged_exposure(self):
        """Calculate total portfolio leveraged exposure."""
        portfolio_value = self.portfolio.total_value()
        if portfolio_value <= 0:
            self.total_leveraged_exposure = 0
            return

        leveraged = sum(
            p['shares'] * p['current_price'] * (p['leverage'] - 1.0)
            for p in self.portfolio.positions.values()
            if p['leverage'] > 1.0
        )

        self.total_leveraged_exposure = leveraged / portfolio_value

    def run(
        self,
        data_dict: Dict[str, pd.DataFrame],
        start_date: str = None,
        end_date: str = None,
        show_progress: bool = True
    ) -> Dict:
        """
        Run backtest with adaptive leverage.
        """
        start = pd.Timestamp(start_date or self.config.start_date)
        end = pd.Timestamp(end_date or self.config.end_date)

        # Generate signals
        print("Generating signals...")
        for ticker, df in tqdm(data_dict.items(), disable=not show_progress):
            try:
                df_with_indicators = calculate_all_indicators(df)
                signal_df = self.strategy.generate_signals(df_with_indicators, ticker)
                self.signal_data[ticker] = signal_df
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                continue

        if not self.signal_data:
            raise ValueError("No valid signal data")

        # Get dates
        all_dates = set()
        for df in self.signal_data.values():
            all_dates.update(df.index)
        dates = sorted([d for d in all_dates if start <= d <= end])

        print(f"Running leveraged backtest from {dates[0]} to {dates[-1]}...")

        prev_momentum = {}

        for date in tqdm(dates, disable=not show_progress):
            current_prices = {}
            for ticker, df in self.signal_data.items():
                if date in df.index:
                    current_prices[ticker] = df.loc[date, 'close']

            # Update positions
            self.update_positions(date, current_prices)

            # Check stops
            self.check_stops(date, current_prices)

            # Process each asset
            for ticker, df in self.signal_data.items():
                if date not in df.index:
                    continue

                row = df.loc[date]
                signal = row.get('signal', 0)
                price = row['close']
                atr = row.get('atr', row.get('atr_20', price * 0.02))
                volatility = row.get('volatility', row.get('volatility_60d', 0.15))
                signal_strength = row.get('signal_strength', abs(signal) if signal != 0 else 0)

                # Get individual signals for conviction calculation
                turtle_sig = row.get('turtle_signal', 0) if 'turtle_signal' in row else 0
                mom_sig = row.get('momentum_signal', 0) if 'momentum_signal' in row else 0
                ma_sig = row.get('ma_signal', row.get('ma_trend', 0))

                signals = [turtle_sig, mom_sig, ma_sig]
                if signal > 0:
                    agreeing = sum(1 for s in signals if s > 0)
                elif signal < 0:
                    agreeing = sum(1 for s in signals if s < 0)
                else:
                    agreeing = 0

                # Momentum tracking
                momentum = row.get('mom_12m', row.get('momentum', 0))
                momentum_prev = prev_momentum.get(ticker, momentum)
                prev_momentum[ticker] = momentum

                # Handle existing positions - update leverage
                if ticker in self.portfolio.positions:
                    self.update_leverage(
                        ticker, date, price, signal_strength,
                        agreeing, 3, momentum, momentum_prev
                    )

                    position = self.portfolio.positions[ticker]

                    # Exit if signal reverses or goes to zero
                    if signal != 0 and signal != position['direction']:
                        self.execute_exit(ticker, date, price, "signal")
                        self.leverage_manager.reset_position(ticker)
                    elif signal == 0:
                        self.execute_exit(ticker, date, price, "signal")
                        self.leverage_manager.reset_position(ticker)

                # Handle new entries
                elif signal != 0:
                    self.execute_entry(
                        ticker, date, price, signal, atr, volatility,
                        signal_strength, agreeing, 3
                    )

            # Record equity
            equity = self.portfolio.total_value()
            leveraged_value = sum(
                p['shares'] * p['current_price']
                for p in self.portfolio.positions.values()
            )
            unleveraged_value = sum(
                p['base_shares'] * p['current_price']
                for p in self.portfolio.positions.values()
            )

            self.equity_curve.append({
                'date': date,
                'equity': equity,
                'cash': self.portfolio.cash,
                'positions': len(self.portfolio.positions),
                'leveraged_exposure': leveraged_value,
                'base_exposure': unleveraged_value,
                'avg_leverage': leveraged_value / unleveraged_value if unleveraged_value > 0 else 1.0
            })

            if len(self.equity_curve) > 1:
                prev_equity = self.equity_curve[-2]['equity']
                daily_return = (equity - prev_equity) / prev_equity
                self.daily_returns.append(daily_return)

        results = self.calculate_metrics()
        results['leverage_history'] = self.leverage_history

        return results

    def calculate_metrics(self) -> Dict:
        """Calculate metrics including leverage stats."""
        results = super().calculate_metrics()

        # Add leverage-specific metrics
        if self.equity_curve:
            equity_df = pd.DataFrame(self.equity_curve)
            results['avg_leverage'] = equity_df['avg_leverage'].mean()
            results['max_leverage'] = equity_df['avg_leverage'].max()
            results['pct_time_leveraged'] = (equity_df['avg_leverage'] > 1.05).mean()

        if self.leverage_history:
            lev_df = pd.DataFrame(self.leverage_history)
            results['leverage_adjustments'] = len(lev_df)
            results['avg_leverage_on_adjustment'] = lev_df['new_leverage'].mean()

        return results


def print_leveraged_results(metrics: Dict):
    """Print results with leverage information."""
    print_results(metrics)

    print("\nLeverage Statistics:")
    print(f"  Average Leverage:     {metrics.get('avg_leverage', 1.0):.2f}x")
    print(f"  Max Leverage:         {metrics.get('max_leverage', 1.0):.2f}x")
    print(f"  % Time Leveraged:     {metrics.get('pct_time_leveraged', 0):.1%}")
    print(f"  Leverage Adjustments: {metrics.get('leverage_adjustments', 0)}")


if __name__ == "__main__":
    import yfinance as yf

    print("Testing Leveraged Backtester...")
    print("=" * 60)

    # Fetch test data
    test_tickers = ["SPY", "QQQ", "GLD", "TLT"]
    data = {}

    for ticker in test_tickers:
        try:
            df = yf.download(ticker, start="2015-01-01", end="2024-01-01", progress=False)
            if not df.empty:
                df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
                data[ticker] = df
        except:
            pass

    if data:
        # Test unleveraged first
        print("\n1. Base Strategy (No Leverage):")
        config = BacktestConfig(
            start_date="2015-01-01",
            end_date="2024-01-01",
            initial_capital=100000
        )

        base_bt = Backtester(config, strategy_name="combined")
        base_results = base_bt.run(data, show_progress=False)
        print(f"   CAGR: {base_results['cagr']:.2%}")
        print(f"   Sharpe: {base_results['sharpe_ratio']:.2f}")
        print(f"   Max DD: {base_results['max_drawdown']:.2%}")

        # Test with adaptive leverage
        print("\n2. With Adaptive Leverage:")
        leverage_config = LeverageConfig(
            leverage_high=1.5,
            leverage_very_high=2.0,
            profit_to_confirm=0.03,
            profit_to_strong=0.08
        )

        lev_bt = LeveragedBacktester(config, "combined", leverage_config)
        lev_results = lev_bt.run(data, show_progress=False)

        print(f"   CAGR: {lev_results['cagr']:.2%}")
        print(f"   Sharpe: {lev_results['sharpe_ratio']:.2f}")
        print(f"   Max DD: {lev_results['max_drawdown']:.2%}")
        print(f"   Avg Leverage: {lev_results.get('avg_leverage', 1.0):.2f}x")

        improvement = lev_results['cagr'] - base_results['cagr']
        print(f"\n   CAGR Improvement: +{improvement:.2%}")
