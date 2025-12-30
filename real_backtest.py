"""
Real Historical Data Backtester
Tests the trend-following strategy with adaptive leverage on actual market data (1980-2024)
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# =============================================================================
# STRATEGY PARAMETERS (Identical to strategy_spec.py)
# =============================================================================
STRATEGY_PARAMS = {
    # Entry conditions
    'momentum_lookback': 252,        # 12-month momentum
    'sma_short': 50,                 # Short moving average
    'sma_long': 200,                 # Long moving average
    'donchian_period': 55,           # Donchian channel breakout
    'atr_period': 20,                # ATR for position sizing

    # Position sizing
    'base_position_size': 0.02,      # 2% per position
    'max_positions': 10,             # Maximum concurrent positions
    'max_sector_exposure': 0.30,     # 30% max per sector

    # Leverage rules
    'leverage_up_profit': 0.03,      # 3% profit to go 1.5x
    'leverage_up_days': 10,          # Minimum days before leverage
    'leverage_medium': 1.5,          # Medium leverage
    'leverage_max_profit': 0.08,     # 8% profit to go 2x
    'leverage_max_days': 20,         # Minimum days for max leverage
    'leverage_max': 2.0,             # Maximum leverage
    'leverage_pullback_threshold': 0.02,  # 2% pullback triggers deleverage
    'leverage_max_duration': 60,     # Max days at high leverage

    # Exit rules
    'stop_loss': -0.08,              # -8% stop loss
    'trailing_atr_multiple': 3.0,    # 3 ATR trailing stop
}


@dataclass
class Position:
    """Represents an open position"""
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: float
    leverage: float = 1.0
    highest_price: float = 0.0
    sector: str = 'unknown'
    days_at_leverage: int = 0


@dataclass
class Trade:
    """Completed trade record"""
    ticker: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    shares: float
    max_leverage: float
    pnl: float
    pnl_pct: float
    days_held: int
    exit_reason: str


class RealBacktester:
    """Backtester using real historical data"""

    def __init__(self, data_dir: str = 'historical_data', initial_capital: float = 100000):
        self.data_dir = data_dir
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.daily_log: List[dict] = []

        # Load all data
        self.data = self._load_all_data()
        self.all_dates = self._get_all_trading_dates()

        # Asset sectors for diversification
        self.sectors = {
            'SP500': 'equity', 'NASDAQ': 'equity', 'DOW': 'equity', 'RUSSELL2000': 'equity',
            'NIKKEI': 'equity', 'FTSE': 'equity', 'DAX': 'equity', 'HANGSENG': 'equity',
            'GOLD': 'commodity', 'SILVER': 'commodity', 'PLATINUM': 'commodity',
            'CRUDE': 'commodity', 'NATGAS': 'commodity', 'COPPER': 'commodity',
            'CORN': 'agriculture', 'WHEAT': 'agriculture', 'SOYBEANS': 'agriculture',
            'COFFEE': 'agriculture', 'SUGAR': 'agriculture', 'COTTON': 'agriculture',
            'TBOND': 'bond', 'TNOTE10': 'bond',
            'EURUSD': 'currency', 'GBPUSD': 'currency', 'USDJPY': 'currency', 'DXY': 'currency',
            'BTC': 'crypto', 'ETH': 'crypto',
            'XLF': 'sector_etf', 'XLE': 'sector_etf', 'XLK': 'sector_etf', 'XLV': 'sector_etf',
        }

    def _load_all_data(self) -> Dict[str, pd.DataFrame]:
        """Load all CSV files from data directory"""
        data = {}
        for filename in os.listdir(self.data_dir):
            if filename.endswith('.csv') and filename != 'data_summary.csv':
                ticker = filename.replace('.csv', '')
                filepath = os.path.join(self.data_dir, filename)
                try:
                    # Read CSV with special handling for yfinance format
                    df = pd.read_csv(filepath, header=[0, 1, 2])

                    # Flatten multi-level columns and get just the column names
                    df.columns = [col[0] for col in df.columns]

                    # First column should be the date
                    df = df.rename(columns={df.columns[0]: 'Date'})
                    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                    df = df.dropna(subset=['Date'])
                    df.set_index('Date', inplace=True)

                    # Convert numeric columns
                    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')

                    # Ensure we have required columns
                    if 'Close' in df.columns and len(df) > 252:
                        data[ticker] = df
                        print(f"  Loaded {ticker}: {len(df)} days ({df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')})")
                except Exception as e:
                    print(f"  Error loading {ticker}: {e}")
        return data

    def _get_all_trading_dates(self) -> pd.DatetimeIndex:
        """Get union of all trading dates"""
        all_dates = set()
        for df in self.data.values():
            all_dates.update(df.index.tolist())
        return pd.DatetimeIndex(sorted(all_dates))

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators for a dataframe"""
        df = df.copy()

        # Moving averages
        df['SMA50'] = df['Close'].rolling(window=50, min_periods=50).mean()
        df['SMA200'] = df['Close'].rolling(window=200, min_periods=200).mean()

        # Momentum (12-month return)
        df['Momentum'] = df['Close'].pct_change(periods=252)

        # ATR
        df['TR'] = np.maximum(
            df['High'] - df['Low'],
            np.maximum(
                abs(df['High'] - df['Close'].shift(1)),
                abs(df['Low'] - df['Close'].shift(1))
            )
        )
        df['ATR'] = df['TR'].rolling(window=20, min_periods=20).mean()

        # Donchian Channel (55-day)
        df['Donchian_High'] = df['High'].rolling(window=55, min_periods=55).max()
        df['Donchian_Low'] = df['Low'].rolling(window=55, min_periods=55).min()

        return df

    def _check_entry_signals(self, ticker: str, date: datetime) -> Tuple[bool, str]:
        """
        Check if entry conditions are met:
        1. 12-month momentum > 0
        2. Price > SMA200
        3. Golden Cross (SMA50 > SMA200)
        4. Donchian breakout (price > 55-day high)
        """
        if ticker not in self.data:
            return False, ""

        df = self.data[ticker]
        if date not in df.index:
            return False, ""

        idx = df.index.get_loc(date)
        if idx < 252:  # Need enough history
            return False, ""

        row = df.iloc[idx]

        # Check all conditions
        if pd.isna(row.get('Momentum')) or pd.isna(row.get('SMA200')):
            return False, ""

        momentum_ok = row['Momentum'] > 0
        above_sma200 = row['Close'] > row['SMA200']
        golden_cross = row['SMA50'] > row['SMA200'] if not pd.isna(row.get('SMA50')) else False
        breakout = row['Close'] > row['Donchian_High'] if not pd.isna(row.get('Donchian_High')) else False

        if momentum_ok and above_sma200 and golden_cross:
            reason = f"Mom={row['Momentum']*100:.1f}% | Price>SMA200 | GoldenCross"
            if breakout:
                reason += " | Breakout"
            return True, reason

        return False, ""

    def _check_exit_signals(self, pos: Position, date: datetime) -> Tuple[bool, str]:
        """
        Check if exit conditions are met:
        1. Stop loss (-8%)
        2. Trailing stop (3 ATR from high)
        3. Trend reversal (death cross + price < SMA200)
        4. Momentum reversal (12m momentum < 0)
        """
        ticker = pos.ticker
        if ticker not in self.data:
            return False, "Data unavailable"

        df = self.data[ticker]
        if date not in df.index:
            return False, ""

        idx = df.index.get_loc(date)
        row = df.iloc[idx]
        current_price = row['Close']

        # Calculate P&L
        pnl_pct = (current_price - pos.entry_price) / pos.entry_price

        # 1. Stop loss
        if pnl_pct <= STRATEGY_PARAMS['stop_loss']:
            return True, f"STOP LOSS: {pnl_pct*100:.1f}%"

        # 2. Trailing stop (3 ATR from highest price)
        if not pd.isna(row.get('ATR')) and pos.highest_price > 0:
            trailing_stop = pos.highest_price - (STRATEGY_PARAMS['trailing_atr_multiple'] * row['ATR'])
            if current_price < trailing_stop:
                return True, f"TRAILING STOP: Price {current_price:.2f} < Stop {trailing_stop:.2f}"

        # 3. Trend reversal
        if not pd.isna(row.get('SMA50')) and not pd.isna(row.get('SMA200')):
            death_cross = row['SMA50'] < row['SMA200']
            below_sma200 = current_price < row['SMA200']
            if death_cross and below_sma200:
                return True, "TREND REVERSAL: Death cross + below SMA200"

        # 4. Momentum reversal
        if not pd.isna(row.get('Momentum')) and row['Momentum'] < -0.05:
            return True, f"MOMENTUM REVERSAL: {row['Momentum']*100:.1f}%"

        return False, ""

    def _update_leverage(self, pos: Position, date: datetime) -> Tuple[float, str]:
        """
        Update position leverage based on:
        - Increase: P&L > 3% after 10 days -> 1.5x
        - Increase: P&L > 8% after 20 days -> 2.0x
        - Decrease: Pullback > 2% from high
        - Decrease: Duration > 60 days at leverage
        """
        ticker = pos.ticker
        if ticker not in self.data:
            return pos.leverage, ""

        df = self.data[ticker]
        if date not in df.index:
            return pos.leverage, ""

        row = df.iloc[df.index.get_loc(date)]
        current_price = row['Close']
        pnl_pct = (current_price - pos.entry_price) / pos.entry_price
        days_held = (date - pos.entry_date).days

        # Update highest price
        if current_price > pos.highest_price:
            pos.highest_price = current_price

        # Calculate pullback from high
        pullback = (pos.highest_price - current_price) / pos.highest_price if pos.highest_price > 0 else 0

        old_leverage = pos.leverage
        new_leverage = pos.leverage
        reason = ""

        # Deleverage conditions
        if pos.leverage > 1.0:
            pos.days_at_leverage += 1

            if pullback > STRATEGY_PARAMS['leverage_pullback_threshold']:
                new_leverage = 1.0
                reason = f"DELEVERAGE: Pullback {pullback*100:.1f}%"
            elif pos.days_at_leverage > STRATEGY_PARAMS['leverage_max_duration']:
                new_leverage = 1.0
                reason = f"DELEVERAGE: Duration {pos.days_at_leverage}d"

        # Leverage up conditions
        if new_leverage == old_leverage and pos.leverage < STRATEGY_PARAMS['leverage_max']:
            if pnl_pct >= STRATEGY_PARAMS['leverage_max_profit'] and days_held >= STRATEGY_PARAMS['leverage_max_days']:
                new_leverage = STRATEGY_PARAMS['leverage_max']
                reason = f"LEVERAGE UP: PnL={pnl_pct*100:.1f}% Days={days_held} -> 2.0x"
            elif pnl_pct >= STRATEGY_PARAMS['leverage_up_profit'] and days_held >= STRATEGY_PARAMS['leverage_up_days']:
                if pos.leverage < STRATEGY_PARAMS['leverage_medium']:
                    new_leverage = STRATEGY_PARAMS['leverage_medium']
                    reason = f"LEVERAGE UP: PnL={pnl_pct*100:.1f}% Days={days_held} -> 1.5x"

        if new_leverage != old_leverage:
            pos.leverage = new_leverage
            if new_leverage <= 1.0:
                pos.days_at_leverage = 0

        return new_leverage, reason

    def _get_sector_exposure(self, sector: str) -> float:
        """Calculate current exposure to a sector"""
        total_exposure = 0
        for pos in self.positions.values():
            if self.sectors.get(pos.ticker, 'unknown') == sector:
                total_exposure += pos.shares * self._get_current_price(pos.ticker) * pos.leverage
        return total_exposure / self.capital if self.capital > 0 else 0

    def _get_current_price(self, ticker: str) -> float:
        """Get current price for a ticker"""
        if ticker in self.data and len(self.data[ticker]) > 0:
            return self.data[ticker]['Close'].iloc[-1]
        return 0

    def run_backtest(self, start_date: str = '1980-01-01', end_date: str = '2024-12-31') -> dict:
        """Run the full backtest"""
        print("\n" + "=" * 70)
        print("RUNNING REAL DATA BACKTEST")
        print(f"Period: {start_date} to {end_date}")
        print("=" * 70)

        # Pre-calculate indicators for all assets
        print("\nCalculating indicators...")
        for ticker in self.data:
            self.data[ticker] = self._calculate_indicators(self.data[ticker])
            print(f"  {ticker}: indicators calculated")

        # Filter dates
        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(end_date)
        trading_dates = [d for d in self.all_dates if start_dt <= d <= end_dt]

        print(f"\nSimulating {len(trading_dates)} trading days...")
        print("-" * 70)

        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []

        for i, date in enumerate(trading_dates):
            # Skip if we don't have enough history
            if i < 252:
                continue

            daily_pnl = 0

            # 1. Check exits and update positions
            positions_to_close = []
            for ticker, pos in list(self.positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue

                current_price = self.data[ticker].loc[date, 'Close']

                # Update highest price
                if current_price > pos.highest_price:
                    pos.highest_price = current_price

                # Check exit
                should_exit, exit_reason = self._check_exit_signals(pos, date)
                if should_exit:
                    positions_to_close.append((ticker, exit_reason, current_price))
                else:
                    # Update leverage
                    new_leverage, lev_reason = self._update_leverage(pos, date)

            # Close positions
            for ticker, exit_reason, exit_price in positions_to_close:
                pos = self.positions[ticker]
                pnl = (exit_price - pos.entry_price) * pos.shares * pos.leverage
                pnl_pct = (exit_price - pos.entry_price) / pos.entry_price * pos.leverage

                trade = Trade(
                    ticker=ticker,
                    entry_date=pos.entry_date,
                    exit_date=date,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    shares=pos.shares,
                    max_leverage=pos.leverage,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    days_held=(date - pos.entry_date).days,
                    exit_reason=exit_reason
                )
                self.trades.append(trade)
                self.capital += pos.shares * pos.entry_price + pnl
                daily_pnl += pnl
                del self.positions[ticker]

            # 2. Check for new entries
            if len(self.positions) < STRATEGY_PARAMS['max_positions']:
                for ticker in self.data:
                    if ticker in self.positions:
                        continue

                    # Check sector exposure
                    sector = self.sectors.get(ticker, 'unknown')
                    if self._get_sector_exposure(sector) >= STRATEGY_PARAMS['max_sector_exposure']:
                        continue

                    should_enter, entry_reason = self._check_entry_signals(ticker, date)
                    if should_enter:
                        entry_price = self.data[ticker].loc[date, 'Close']

                        # Position sizing: 2% of capital
                        position_value = self.capital * STRATEGY_PARAMS['base_position_size']
                        shares = position_value / entry_price

                        pos = Position(
                            ticker=ticker,
                            entry_date=date,
                            entry_price=entry_price,
                            shares=shares,
                            leverage=1.0,
                            highest_price=entry_price,
                            sector=sector
                        )
                        self.positions[ticker] = pos
                        self.capital -= position_value

                        if len(self.positions) >= STRATEGY_PARAMS['max_positions']:
                            break

            # 3. Calculate portfolio value
            portfolio_value = self.capital
            for ticker, pos in self.positions.items():
                if ticker in self.data and date in self.data[ticker].index:
                    current_price = self.data[ticker].loc[date, 'Close']
                    position_value = pos.shares * current_price
                    unrealized_pnl = (current_price - pos.entry_price) * pos.shares * pos.leverage
                    portfolio_value += pos.shares * pos.entry_price + unrealized_pnl

            self.equity_curve.append((date, portfolio_value))

            # Progress update
            if i % 1000 == 0:
                years_elapsed = (date - trading_dates[252]).days / 365.25
                if years_elapsed > 0:
                    cagr = (portfolio_value / self.initial_capital) ** (1 / years_elapsed) - 1
                    print(f"  {date.strftime('%Y-%m-%d')}: ${portfolio_value:,.0f} | CAGR: {cagr*100:.1f}% | Positions: {len(self.positions)}")

        # Final results
        return self._generate_report()

    def _generate_report(self) -> dict:
        """Generate comprehensive backtest report"""
        if not self.equity_curve:
            return {}

        equity_df = pd.DataFrame(self.equity_curve, columns=['Date', 'Equity'])
        equity_df.set_index('Date', inplace=True)

        # Calculate metrics
        final_equity = equity_df['Equity'].iloc[-1]
        start_date = equity_df.index[0]
        end_date = equity_df.index[-1]
        years = (end_date - start_date).days / 365.25

        # CAGR
        cagr = (final_equity / self.initial_capital) ** (1 / years) - 1 if years > 0 else 0

        # Returns
        equity_df['Returns'] = equity_df['Equity'].pct_change()

        # Volatility (annualized)
        volatility = equity_df['Returns'].std() * np.sqrt(252)

        # Sharpe Ratio (assuming 3% risk-free rate)
        sharpe = (cagr - 0.03) / volatility if volatility > 0 else 0

        # Max Drawdown
        equity_df['Peak'] = equity_df['Equity'].cummax()
        equity_df['Drawdown'] = (equity_df['Equity'] - equity_df['Peak']) / equity_df['Peak']
        max_drawdown = equity_df['Drawdown'].min()

        # Trade statistics
        if self.trades:
            winning_trades = [t for t in self.trades if t.pnl > 0]
            losing_trades = [t for t in self.trades if t.pnl <= 0]
            win_rate = len(winning_trades) / len(self.trades)
            avg_win = np.mean([t.pnl_pct for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t.pnl_pct for t in losing_trades]) if losing_trades else 0
            avg_leverage = np.mean([t.max_leverage for t in self.trades])
        else:
            win_rate = avg_win = avg_loss = avg_leverage = 0

        report = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'years': round(years, 1),
            'initial_capital': self.initial_capital,
            'final_equity': round(final_equity, 2),
            'total_return': round((final_equity / self.initial_capital - 1) * 100, 2),
            'cagr': round(cagr * 100, 2),
            'volatility': round(volatility * 100, 2),
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown': round(max_drawdown * 100, 2),
            'total_trades': len(self.trades),
            'win_rate': round(win_rate * 100, 2),
            'avg_win': round(avg_win * 100, 2),
            'avg_loss': round(avg_loss * 100, 2),
            'avg_leverage': round(avg_leverage, 2),
        }

        # Save equity curve
        equity_df.to_csv('backtest_equity_curve.csv')

        # Save trades
        trades_df = pd.DataFrame([
            {
                'Entry Date': t.entry_date.strftime('%Y-%m-%d'),
                'Exit Date': t.exit_date.strftime('%Y-%m-%d'),
                'Ticker': t.ticker,
                'Entry Price': round(t.entry_price, 4),
                'Exit Price': round(t.exit_price, 4),
                'Shares': round(t.shares, 4),
                'Max Leverage': t.max_leverage,
                'PnL': round(t.pnl, 2),
                'PnL %': round(t.pnl_pct * 100, 2),
                'Days Held': t.days_held,
                'Exit Reason': t.exit_reason
            }
            for t in self.trades
        ])
        trades_df.to_csv('backtest_trades.csv', index=False)

        return report


def main():
    """Run the backtest"""
    print("\n" + "=" * 70)
    print("TREND-FOLLOWING STRATEGY BACKTEST")
    print("Using Real Historical Data (1980-2024)")
    print("=" * 70)

    # Initialize backtester
    backtester = RealBacktester(data_dir='historical_data', initial_capital=100000)

    # Run backtest
    report = backtester.run_backtest(start_date='1980-01-01', end_date='2024-12-31')

    # Print results
    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    print(f"""
Period:           {report['start_date']} to {report['end_date']} ({report['years']} years)
Initial Capital:  ${report['initial_capital']:,}
Final Equity:     ${report['final_equity']:,.2f}
Total Return:     {report['total_return']}%

CAGR:             {report['cagr']}%
Volatility:       {report['volatility']}%
Sharpe Ratio:     {report['sharpe_ratio']}
Max Drawdown:     {report['max_drawdown']}%

Total Trades:     {report['total_trades']}
Win Rate:         {report['win_rate']}%
Avg Win:          {report['avg_win']}%
Avg Loss:         {report['avg_loss']}%
Avg Leverage:     {report['avg_leverage']}x
""")

    print("=" * 70)
    print("Files saved:")
    print("  - backtest_equity_curve.csv")
    print("  - backtest_trades.csv")
    print("=" * 70)

    return report


if __name__ == '__main__':
    main()
