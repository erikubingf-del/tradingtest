"""
Backtesting Engine for Trend Following Strategies

Features:
- Multi-asset portfolio backtesting
- Realistic transaction costs and slippage
- Position tracking and PnL attribution
- Performance metrics and analysis
- Monte Carlo simulation support
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from tqdm import tqdm

from config import BacktestConfig, TransactionCosts
from strategies import (
    TurtleStrategy, MomentumStrategy, DualMomentumStrategy,
    CombinedStrategy, TrendScanner, create_strategy
)
from position_sizing import RiskManager, ScaleInManager
from indicators import calculate_all_indicators


@dataclass
class Trade:
    """Represents a completed trade."""
    ticker: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: int
    direction: int  # 1 long, -1 short
    pnl: float
    pnl_pct: float
    holding_days: int
    exit_reason: str  # 'signal', 'stop', 'target'


@dataclass
class PortfolioState:
    """Current portfolio state."""
    cash: float
    positions: Dict[str, Dict] = field(default_factory=dict)
    equity: float = 0.0
    date: pd.Timestamp = None

    def total_value(self) -> float:
        """Calculate total portfolio value."""
        position_value = sum(
            p['shares'] * p['current_price'] * p['direction']
            for p in self.positions.values()
        )
        return self.cash + position_value


class Backtester:
    """
    Main backtesting engine.
    """

    def __init__(
        self,
        config: BacktestConfig = None,
        strategy_name: str = "combined"
    ):
        self.config = config or BacktestConfig()
        self.strategy_name = strategy_name

        # Initialize components
        self.strategy = create_strategy(strategy_name)
        self.risk_manager = RiskManager()
        self.scale_manager = ScaleInManager(
            initial_pct=self.config.risk.initial_position_pct,
            max_pct=self.config.risk.max_position_pct
        )

        # State tracking
        self.portfolio = PortfolioState(cash=self.config.initial_capital)
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
        self.daily_returns: List[float] = []

        # Signal data storage
        self.signal_data: Dict[str, pd.DataFrame] = {}

    def calculate_transaction_cost(
        self,
        shares: int,
        price: float,
        is_crypto: bool = False
    ) -> float:
        """Calculate transaction costs including slippage."""
        costs = self.config.costs

        if is_crypto:
            slippage = costs.crypto_slippage_pct
            commission = costs.crypto_commission_pct
        else:
            slippage = costs.slippage_pct
            commission = costs.commission_pct

        trade_value = shares * price
        slippage_cost = trade_value * slippage
        commission_cost = max(trade_value * commission, costs.min_commission)

        return slippage_cost + commission_cost

    def execute_entry(
        self,
        ticker: str,
        date: pd.Timestamp,
        price: float,
        signal: int,
        atr: float,
        volatility: float
    ) -> Optional[Dict]:
        """
        Execute a trade entry.

        Returns position info or None if entry rejected.
        """
        if ticker in self.portfolio.positions:
            return None  # Already have position

        portfolio_value = self.portfolio.total_value()

        # Calculate position weight
        if hasattr(self.strategy, 'calculate_weight'):
            weight = self.strategy.calculate_weight(abs(signal), volatility)
        else:
            weight = self.config.risk.initial_position_pct

        # Apply risk manager checks
        weight = self.risk_manager.apply_drawdown_rule(portfolio_value, weight)

        # Calculate shares
        position_value = portfolio_value * weight
        shares = int(position_value / price)

        if shares <= 0:
            return None

        # Calculate costs
        is_crypto = '-USD' in ticker or 'BTC' in ticker
        cost = self.calculate_transaction_cost(shares, price, is_crypto)

        # Check if we have enough cash
        required_cash = shares * price + cost
        if required_cash > self.portfolio.cash:
            # Reduce position to fit
            available = self.portfolio.cash - cost
            shares = int(available / price)
            if shares <= 0:
                return None

        # Calculate stop price
        if signal > 0:  # Long
            stop_price = price - 2 * atr
        else:  # Short
            stop_price = price + 2 * atr

        # Execute
        self.portfolio.cash -= shares * price + cost

        position = {
            'ticker': ticker,
            'entry_date': date,
            'entry_price': price,
            'shares': shares,
            'direction': signal,
            'stop_price': stop_price,
            'current_price': price,
            'weight': weight,
            'atr': atr,
            'cost': cost
        }

        self.portfolio.positions[ticker] = position

        return position

    def execute_exit(
        self,
        ticker: str,
        date: pd.Timestamp,
        price: float,
        reason: str = "signal"
    ) -> Optional[Trade]:
        """
        Execute a trade exit.

        Returns completed Trade or None if no position.
        """
        if ticker not in self.portfolio.positions:
            return None

        position = self.portfolio.positions[ticker]

        # Calculate costs
        is_crypto = '-USD' in ticker or 'BTC' in ticker
        cost = self.calculate_transaction_cost(position['shares'], price, is_crypto)

        # Calculate PnL
        if position['direction'] > 0:  # Long
            gross_pnl = (price - position['entry_price']) * position['shares']
        else:  # Short
            gross_pnl = (position['entry_price'] - price) * position['shares']

        total_cost = position['cost'] + cost
        net_pnl = gross_pnl - total_cost

        pnl_pct = net_pnl / (position['entry_price'] * position['shares'])

        # Create trade record
        trade = Trade(
            ticker=ticker,
            entry_date=position['entry_date'],
            exit_date=date,
            entry_price=position['entry_price'],
            exit_price=price,
            shares=position['shares'],
            direction=position['direction'],
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            holding_days=(date - position['entry_date']).days,
            exit_reason=reason
        )

        # Update cash
        self.portfolio.cash += position['shares'] * price - cost

        # Remove position
        del self.portfolio.positions[ticker]

        self.trades.append(trade)

        return trade

    def check_stops(
        self,
        date: pd.Timestamp,
        prices: Dict[str, float]
    ) -> List[Trade]:
        """Check and execute any stop losses."""
        stopped_trades = []

        for ticker, position in list(self.portfolio.positions.items()):
            if ticker not in prices:
                continue

            current_price = prices[ticker]

            if position['direction'] > 0:  # Long
                if current_price <= position['stop_price']:
                    trade = self.execute_exit(ticker, date, current_price, "stop")
                    if trade:
                        stopped_trades.append(trade)
            else:  # Short
                if current_price >= position['stop_price']:
                    trade = self.execute_exit(ticker, date, current_price, "stop")
                    if trade:
                        stopped_trades.append(trade)

        return stopped_trades

    def update_positions(
        self,
        date: pd.Timestamp,
        prices: Dict[str, float]
    ):
        """Update current prices for all positions."""
        for ticker, position in self.portfolio.positions.items():
            if ticker in prices:
                position['current_price'] = prices[ticker]

    def run(
        self,
        data_dict: Dict[str, pd.DataFrame],
        start_date: str = None,
        end_date: str = None,
        show_progress: bool = True
    ) -> Dict:
        """
        Run backtest on provided data.

        Args:
            data_dict: Dictionary mapping ticker to OHLCV DataFrame
            start_date: Optional start date override
            end_date: Optional end date override
            show_progress: Show progress bar

        Returns:
            Dictionary with results and metrics
        """
        start = pd.Timestamp(start_date or self.config.start_date)
        end = pd.Timestamp(end_date or self.config.end_date)

        # Generate signals for all assets
        print("Generating signals...")
        for ticker, df in tqdm(data_dict.items(), disable=not show_progress):
            try:
                # Add technical indicators
                df_with_indicators = calculate_all_indicators(df)

                # Generate strategy signals
                signal_df = self.strategy.generate_signals(df_with_indicators, ticker)
                self.signal_data[ticker] = signal_df
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                continue

        if not self.signal_data:
            raise ValueError("No valid signal data generated")

        # Get common dates
        all_dates = set()
        for ticker, df in self.signal_data.items():
            all_dates.update(df.index)

        dates = sorted([d for d in all_dates if start <= d <= end])

        print(f"Running backtest from {dates[0]} to {dates[-1]}...")

        # Main backtest loop
        for date in tqdm(dates, disable=not show_progress):
            # Get current prices
            current_prices = {}
            for ticker, df in self.signal_data.items():
                if date in df.index:
                    current_prices[ticker] = df.loc[date, 'close']

            # Update position prices
            self.update_positions(date, current_prices)

            # Check stops
            self.check_stops(date, current_prices)

            # Process signals
            for ticker, df in self.signal_data.items():
                if date not in df.index:
                    continue

                row = df.loc[date]
                signal = row.get('signal', 0)
                price = row['close']
                atr = row.get('atr', row.get('atr_20', price * 0.02))
                volatility = row.get('volatility', row.get('volatility_60d', 0.15))

                # Handle exits first
                if ticker in self.portfolio.positions:
                    position = self.portfolio.positions[ticker]

                    # Exit if signal reverses
                    if signal != 0 and signal != position['direction']:
                        self.execute_exit(ticker, date, price, "signal")

                    # Exit if signal goes to zero
                    elif signal == 0:
                        self.execute_exit(ticker, date, price, "signal")

                # Handle entries
                elif signal != 0:
                    self.execute_entry(ticker, date, price, signal, atr, volatility)

            # Record equity
            equity = self.portfolio.total_value()
            self.equity_curve.append({
                'date': date,
                'equity': equity,
                'cash': self.portfolio.cash,
                'positions': len(self.portfolio.positions)
            })

            # Calculate daily return
            if len(self.equity_curve) > 1:
                prev_equity = self.equity_curve[-2]['equity']
                daily_return = (equity - prev_equity) / prev_equity
                self.daily_returns.append(daily_return)

        # Calculate final metrics
        results = self.calculate_metrics()

        return results

    def calculate_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics."""
        if not self.equity_curve:
            return {}

        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.set_index('date', inplace=True)

        returns = pd.Series(self.daily_returns)

        # Basic metrics
        initial_capital = self.config.initial_capital
        final_equity = equity_df['equity'].iloc[-1]
        total_return = (final_equity - initial_capital) / initial_capital

        # Time-based metrics
        years = (equity_df.index[-1] - equity_df.index[0]).days / 365.25
        cagr = (final_equity / initial_capital) ** (1 / years) - 1 if years > 0 else 0

        # Risk metrics
        volatility = returns.std() * np.sqrt(252) if len(returns) > 0 else 0
        sharpe = (cagr - 0.02) / volatility if volatility > 0 else 0  # Assume 2% risk-free

        # Drawdown
        running_max = equity_df['equity'].cummax()
        drawdown = (equity_df['equity'] - running_max) / running_max
        max_drawdown = drawdown.min()

        # Calmar ratio
        calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else 0

        # Trade statistics
        if self.trades:
            trade_df = pd.DataFrame([{
                'pnl': t.pnl,
                'pnl_pct': t.pnl_pct,
                'holding_days': t.holding_days
            } for t in self.trades])

            win_rate = (trade_df['pnl'] > 0).mean()
            avg_win = trade_df[trade_df['pnl'] > 0]['pnl'].mean() if (trade_df['pnl'] > 0).any() else 0
            avg_loss = trade_df[trade_df['pnl'] < 0]['pnl'].mean() if (trade_df['pnl'] < 0).any() else 0
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            avg_holding = trade_df['holding_days'].mean()
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
            avg_holding = 0

        metrics = {
            'initial_capital': initial_capital,
            'final_equity': final_equity,
            'total_return': total_return,
            'cagr': cagr,
            'target_cagr': self.config.target_cagr,
            'cagr_vs_target': cagr - self.config.target_cagr,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar,
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'avg_holding_days': avg_holding,
            'years': years,
            'equity_curve': equity_df,
            'trades': self.trades
        }

        return metrics

    def get_annual_returns(self) -> pd.Series:
        """Calculate annual returns."""
        if not self.equity_curve:
            return pd.Series()

        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.set_index('date', inplace=True)
        equity_df['year'] = equity_df.index.year

        annual = equity_df.groupby('year')['equity'].agg(['first', 'last'])
        annual['return'] = (annual['last'] - annual['first']) / annual['first']

        return annual['return']

    def get_decade_cagr(self) -> pd.DataFrame:
        """
        Calculate CAGR for each rolling 10-year period.
        Used to validate 20% target.
        """
        if not self.equity_curve:
            return pd.DataFrame()

        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.set_index('date', inplace=True)

        results = []
        years = equity_df.index.year.unique()

        for start_year in years:
            end_year = start_year + 10
            start_date = pd.Timestamp(f"{start_year}-01-01")
            end_date = pd.Timestamp(f"{end_year}-01-01")

            mask = (equity_df.index >= start_date) & (equity_df.index < end_date)
            period_df = equity_df[mask]

            if len(period_df) < 252 * 8:  # At least 8 years of data
                continue

            start_equity = period_df['equity'].iloc[0]
            end_equity = period_df['equity'].iloc[-1]
            actual_years = (period_df.index[-1] - period_df.index[0]).days / 365.25

            cagr = (end_equity / start_equity) ** (1 / actual_years) - 1

            results.append({
                'period': f"{start_year}-{min(end_year, years[-1])}",
                'start_year': start_year,
                'end_year': min(end_year, years[-1]),
                'cagr': cagr,
                'meets_target': cagr >= 0.20
            })

        return pd.DataFrame(results)


class MonteCarloSimulator:
    """
    Monte Carlo simulation for strategy robustness testing.
    """

    def __init__(self, backtester: Backtester, n_simulations: int = 1000):
        self.backtester = backtester
        self.n_simulations = n_simulations

    def run_bootstrap(
        self,
        data_dict: Dict[str, pd.DataFrame],
        block_size: int = 21  # Monthly blocks
    ) -> pd.DataFrame:
        """
        Run bootstrap simulation with block resampling.
        """
        results = []

        for i in tqdm(range(self.n_simulations), desc="Monte Carlo"):
            # Resample returns with blocks
            resampled_data = self._resample_blocks(data_dict, block_size)

            # Run backtest
            bt = Backtester(self.backtester.config, self.backtester.strategy_name)
            try:
                metrics = bt.run(resampled_data, show_progress=False)
                results.append({
                    'simulation': i,
                    'cagr': metrics['cagr'],
                    'sharpe': metrics['sharpe_ratio'],
                    'max_dd': metrics['max_drawdown'],
                    'win_rate': metrics['win_rate']
                })
            except Exception:
                continue

        return pd.DataFrame(results)

    def _resample_blocks(
        self,
        data_dict: Dict[str, pd.DataFrame],
        block_size: int
    ) -> Dict[str, pd.DataFrame]:
        """Resample data using block bootstrap."""
        resampled = {}

        for ticker, df in data_dict.items():
            n_blocks = len(df) // block_size
            if n_blocks < 2:
                resampled[ticker] = df.copy()
                continue

            # Create blocks
            blocks = []
            for i in range(n_blocks):
                start = i * block_size
                end = start + block_size
                blocks.append(df.iloc[start:end])

            # Randomly sample blocks with replacement
            sampled_indices = np.random.choice(n_blocks, size=n_blocks, replace=True)
            sampled_blocks = [blocks[i] for i in sampled_indices]

            # Concatenate and reindex
            resampled_df = pd.concat(sampled_blocks, ignore_index=True)
            resampled_df.index = pd.date_range(
                start=df.index[0],
                periods=len(resampled_df),
                freq='D'
            )

            resampled[ticker] = resampled_df

        return resampled


def print_results(metrics: Dict):
    """Pretty print backtest results."""
    print("\n" + "="*60)
    print("BACKTEST RESULTS")
    print("="*60)

    print(f"\nPerformance Metrics:")
    print(f"  Initial Capital:    ${metrics['initial_capital']:,.2f}")
    print(f"  Final Equity:       ${metrics['final_equity']:,.2f}")
    print(f"  Total Return:       {metrics['total_return']:.2%}")
    print(f"  CAGR:               {metrics['cagr']:.2%}")
    print(f"  Target CAGR:        {metrics['target_cagr']:.2%}")
    print(f"  CAGR vs Target:     {metrics['cagr_vs_target']:+.2%}")

    print(f"\nRisk Metrics:")
    print(f"  Volatility:         {metrics['volatility']:.2%}")
    print(f"  Sharpe Ratio:       {metrics['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown:       {metrics['max_drawdown']:.2%}")
    print(f"  Calmar Ratio:       {metrics['calmar_ratio']:.2f}")

    print(f"\nTrade Statistics:")
    print(f"  Total Trades:       {metrics['total_trades']}")
    print(f"  Win Rate:           {metrics['win_rate']:.2%}")
    print(f"  Avg Win:            ${metrics['avg_win']:,.2f}")
    print(f"  Avg Loss:           ${metrics['avg_loss']:,.2f}")
    print(f"  Profit Factor:      {metrics['profit_factor']:.2f}")
    print(f"  Avg Holding (days): {metrics['avg_holding_days']:.1f}")

    print(f"\nBacktest Period: {metrics['years']:.1f} years")
    print("="*60)


if __name__ == "__main__":
    import yfinance as yf

    # Quick test with limited assets
    print("Running quick backtest test...")

    test_tickers = ["SPY", "QQQ", "GLD", "TLT"]
    data = {}

    for ticker in test_tickers:
        df = yf.download(ticker, start="2015-01-01", end="2024-01-01", progress=False)
        if not df.empty:
            df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
            data[ticker] = df

    if data:
        config = BacktestConfig(
            start_date="2015-01-01",
            end_date="2024-01-01",
            initial_capital=100000
        )

        bt = Backtester(config, strategy_name="combined")
        results = bt.run(data)

        print_results(results)

        # Show annual returns
        print("\nAnnual Returns:")
        annual = bt.get_annual_returns()
        for year, ret in annual.items():
            print(f"  {year}: {ret:.2%}")
