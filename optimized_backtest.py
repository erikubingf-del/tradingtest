"""
OPTIMIZED Trend-Following Strategy Backtest
Aggressive parameters targeting higher CAGR
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass


# =============================================================================
# OPTIMIZED STRATEGY PARAMETERS
# =============================================================================
STRATEGY_PARAMS = {
    # Entry conditions (more relaxed for more trades)
    'momentum_lookback': 252,        # 12-month momentum
    'sma_short': 50,                 # Short moving average
    'sma_long': 200,                 # Long moving average
    'donchian_period': 20,           # Shorter breakout period (was 55)
    'atr_period': 14,                # ATR for position sizing

    # Position sizing (MORE AGGRESSIVE)
    'base_position_size': 0.05,      # 5% per position (was 2%)
    'max_positions': 15,             # More positions (was 10)
    'max_sector_exposure': 0.40,     # 40% max per sector (was 30%)

    # Leverage rules (MORE AGGRESSIVE)
    'leverage_up_profit': 0.02,      # 2% profit to go 1.5x (was 3%)
    'leverage_up_days': 5,           # Faster leverage (was 10)
    'leverage_medium': 1.5,          # Medium leverage
    'leverage_max_profit': 0.05,     # 5% profit to go 2x (was 8%)
    'leverage_max_days': 10,         # Faster max leverage (was 20)
    'leverage_max': 2.5,             # Higher max leverage (was 2.0)
    'leverage_pullback_threshold': 0.03,  # 3% pullback triggers deleverage
    'leverage_max_duration': 90,     # Longer at leverage (was 60)

    # Exit rules (tighter stops, let winners run)
    'stop_loss': -0.06,              # -6% stop loss (was -8%)
    'trailing_atr_multiple': 2.5,    # 2.5 ATR trailing stop (was 3)
}


@dataclass
class Position:
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


class OptimizedBacktester:
    """Optimized backtester for higher returns"""

    def __init__(self, data_dir: str = 'historical_data', initial_capital: float = 100000):
        self.data_dir = data_dir
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []

        # Load all data
        print("Loading data...")
        self.data = self._load_all_data()
        self.all_dates = self._get_all_trading_dates()

        # Asset sectors
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
        """Load all CSV files"""
        data = {}
        for filename in os.listdir(self.data_dir):
            if filename.endswith('.csv') and filename != 'data_summary.csv':
                ticker = filename.replace('.csv', '')
                filepath = os.path.join(self.data_dir, filename)
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
                        data[ticker] = df
                except Exception as e:
                    pass
        print(f"  Loaded {len(data)} assets")
        return data

    def _get_all_trading_dates(self) -> pd.DatetimeIndex:
        all_dates = set()
        for df in self.data.values():
            all_dates.update(df.index.tolist())
        return pd.DatetimeIndex(sorted(all_dates))

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['SMA50'] = df['Close'].rolling(window=50, min_periods=50).mean()
        df['SMA200'] = df['Close'].rolling(window=200, min_periods=200).mean()
        df['Momentum'] = df['Close'].pct_change(periods=252)
        df['Momentum_3m'] = df['Close'].pct_change(periods=63)  # 3-month momentum too

        df['TR'] = np.maximum(
            df['High'] - df['Low'],
            np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1)))
        )
        df['ATR'] = df['TR'].rolling(window=14, min_periods=14).mean()
        df['Donchian_High'] = df['High'].rolling(window=20, min_periods=20).max()
        df['Donchian_Low'] = df['Low'].rolling(window=20, min_periods=20).min()

        return df

    def _check_entry_signals(self, ticker: str, date: datetime) -> Tuple[bool, str]:
        """Optimized entry: momentum + trend + breakout"""
        if ticker not in self.data:
            return False, ""

        df = self.data[ticker]
        if date not in df.index:
            return False, ""

        idx = df.index.get_loc(date)
        if idx < 252:
            return False, ""

        row = df.iloc[idx]

        if pd.isna(row.get('Momentum')) or pd.isna(row.get('SMA200')):
            return False, ""

        # Entry conditions (relaxed for more trades)
        momentum_ok = row['Momentum'] > 0
        momentum_3m_ok = row.get('Momentum_3m', 0) > 0 if not pd.isna(row.get('Momentum_3m')) else True
        above_sma200 = row['Close'] > row['SMA200']
        golden_cross = row['SMA50'] > row['SMA200'] if not pd.isna(row.get('SMA50')) else False

        # Need momentum + above SMA200 (golden cross optional for more entries)
        if momentum_ok and above_sma200 and (golden_cross or momentum_3m_ok):
            reason = f"Mom12m={row['Momentum']*100:.1f}%"
            return True, reason

        return False, ""

    def _check_exit_signals(self, pos: Position, date: datetime) -> Tuple[bool, str]:
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return False, ""

        row = self.data[ticker].loc[date]
        current_price = row['Close']
        pnl_pct = (current_price - pos.entry_price) / pos.entry_price

        # Stop loss
        if pnl_pct <= STRATEGY_PARAMS['stop_loss']:
            return True, f"STOP LOSS: {pnl_pct*100:.1f}%"

        # Trailing stop
        if not pd.isna(row.get('ATR')) and pos.highest_price > 0:
            trailing_stop = pos.highest_price - (STRATEGY_PARAMS['trailing_atr_multiple'] * row['ATR'])
            if current_price < trailing_stop:
                return True, f"TRAILING STOP"

        # Trend reversal
        if not pd.isna(row.get('SMA50')) and not pd.isna(row.get('SMA200')):
            if row['SMA50'] < row['SMA200'] and current_price < row['SMA200']:
                return True, "TREND REVERSAL"

        return False, ""

    def _update_leverage(self, pos: Position, date: datetime) -> float:
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return pos.leverage

        row = self.data[ticker].loc[date]
        current_price = row['Close']
        pnl_pct = (current_price - pos.entry_price) / pos.entry_price
        days_held = (date - pos.entry_date).days

        if current_price > pos.highest_price:
            pos.highest_price = current_price

        pullback = (pos.highest_price - current_price) / pos.highest_price if pos.highest_price > 0 else 0

        # Deleverage on pullback
        if pos.leverage > 1.0:
            pos.days_at_leverage += 1
            if pullback > STRATEGY_PARAMS['leverage_pullback_threshold']:
                pos.leverage = 1.0
                pos.days_at_leverage = 0
                return pos.leverage
            if pos.days_at_leverage > STRATEGY_PARAMS['leverage_max_duration']:
                pos.leverage = max(1.0, pos.leverage - 0.5)
                pos.days_at_leverage = 0
                return pos.leverage

        # Leverage up
        if pnl_pct >= STRATEGY_PARAMS['leverage_max_profit'] and days_held >= STRATEGY_PARAMS['leverage_max_days']:
            if pos.leverage < STRATEGY_PARAMS['leverage_max']:
                pos.leverage = min(STRATEGY_PARAMS['leverage_max'], pos.leverage + 0.5)
        elif pnl_pct >= STRATEGY_PARAMS['leverage_up_profit'] and days_held >= STRATEGY_PARAMS['leverage_up_days']:
            if pos.leverage < STRATEGY_PARAMS['leverage_medium']:
                pos.leverage = STRATEGY_PARAMS['leverage_medium']

        return pos.leverage

    def _get_sector_exposure(self, sector: str) -> float:
        total = 0
        for pos in self.positions.values():
            if self.sectors.get(pos.ticker, 'unknown') == sector:
                if pos.ticker in self.data and len(self.data[pos.ticker]) > 0:
                    price = self.data[pos.ticker]['Close'].iloc[-1]
                    total += pos.shares * price * pos.leverage
        return total / self.capital if self.capital > 0 else 0

    def run_backtest(self, start_date: str = '1980-01-01', end_date: str = '2024-12-31') -> dict:
        print(f"\nRunning optimized backtest: {start_date} to {end_date}")
        print("=" * 70)

        # Calculate indicators
        for ticker in self.data:
            self.data[ticker] = self._calculate_indicators(self.data[ticker])

        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(end_date)
        trading_dates = [d for d in self.all_dates if start_dt <= d <= end_dt]

        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []

        for i, date in enumerate(trading_dates):
            if i < 252:
                continue

            # Check exits
            positions_to_close = []
            for ticker, pos in list(self.positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue

                current_price = self.data[ticker].loc[date, 'Close']
                if current_price > pos.highest_price:
                    pos.highest_price = current_price

                should_exit, exit_reason = self._check_exit_signals(pos, date)
                if should_exit:
                    positions_to_close.append((ticker, exit_reason, current_price))
                else:
                    self._update_leverage(pos, date)

            # Close positions
            for ticker, exit_reason, exit_price in positions_to_close:
                pos = self.positions[ticker]
                pnl = (exit_price - pos.entry_price) * pos.shares * pos.leverage
                pnl_pct = (exit_price - pos.entry_price) / pos.entry_price * pos.leverage

                trade = Trade(
                    ticker=ticker, entry_date=pos.entry_date, exit_date=date,
                    entry_price=pos.entry_price, exit_price=exit_price,
                    shares=pos.shares, max_leverage=pos.leverage,
                    pnl=pnl, pnl_pct=pnl_pct,
                    days_held=(date - pos.entry_date).days, exit_reason=exit_reason
                )
                self.trades.append(trade)
                self.capital += pos.shares * pos.entry_price + pnl
                del self.positions[ticker]

            # New entries
            if len(self.positions) < STRATEGY_PARAMS['max_positions']:
                for ticker in self.data:
                    if ticker in self.positions:
                        continue

                    sector = self.sectors.get(ticker, 'unknown')
                    if self._get_sector_exposure(sector) >= STRATEGY_PARAMS['max_sector_exposure']:
                        continue

                    should_enter, _ = self._check_entry_signals(ticker, date)
                    if should_enter and date in self.data[ticker].index:
                        entry_price = self.data[ticker].loc[date, 'Close']
                        position_value = self.capital * STRATEGY_PARAMS['base_position_size']
                        shares = position_value / entry_price

                        pos = Position(
                            ticker=ticker, entry_date=date, entry_price=entry_price,
                            shares=shares, leverage=1.0, highest_price=entry_price, sector=sector
                        )
                        self.positions[ticker] = pos
                        self.capital -= position_value

                        if len(self.positions) >= STRATEGY_PARAMS['max_positions']:
                            break

            # Calculate portfolio value
            portfolio_value = self.capital
            for ticker, pos in self.positions.items():
                if ticker in self.data and date in self.data[ticker].index:
                    current_price = self.data[ticker].loc[date, 'Close']
                    unrealized_pnl = (current_price - pos.entry_price) * pos.shares * pos.leverage
                    portfolio_value += pos.shares * pos.entry_price + unrealized_pnl

            self.equity_curve.append((date, portfolio_value))

            if i % 1000 == 0:
                years = (date - trading_dates[252]).days / 365.25
                if years > 0:
                    cagr = (portfolio_value / self.initial_capital) ** (1 / years) - 1
                    print(f"  {date.strftime('%Y-%m-%d')}: ${portfolio_value:,.0f} | CAGR: {cagr*100:.1f}% | Pos: {len(self.positions)}")

        return self._generate_report()

    def _generate_report(self) -> dict:
        if not self.equity_curve:
            return {}

        equity_df = pd.DataFrame(self.equity_curve, columns=['Date', 'Equity'])
        equity_df.set_index('Date', inplace=True)

        final_equity = equity_df['Equity'].iloc[-1]
        start_date = equity_df.index[0]
        end_date = equity_df.index[-1]
        years = (end_date - start_date).days / 365.25

        cagr = (final_equity / self.initial_capital) ** (1 / years) - 1 if years > 0 else 0

        equity_df['Returns'] = equity_df['Equity'].pct_change()
        volatility = equity_df['Returns'].std() * np.sqrt(252)
        sharpe = (cagr - 0.03) / volatility if volatility > 0 else 0

        equity_df['Peak'] = equity_df['Equity'].cummax()
        equity_df['Drawdown'] = (equity_df['Equity'] - equity_df['Peak']) / equity_df['Peak']
        max_drawdown = equity_df['Drawdown'].min()

        if self.trades:
            winning = [t for t in self.trades if t.pnl > 0]
            losing = [t for t in self.trades if t.pnl <= 0]
            win_rate = len(winning) / len(self.trades)
            avg_win = np.mean([t.pnl_pct for t in winning]) if winning else 0
            avg_loss = np.mean([t.pnl_pct for t in losing]) if losing else 0
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

        equity_df.to_csv('optimized_equity_curve.csv')

        trades_df = pd.DataFrame([{
            'Entry': t.entry_date.strftime('%Y-%m-%d'),
            'Exit': t.exit_date.strftime('%Y-%m-%d'),
            'Ticker': t.ticker,
            'Entry$': round(t.entry_price, 2),
            'Exit$': round(t.exit_price, 2),
            'Leverage': t.max_leverage,
            'PnL$': round(t.pnl, 2),
            'PnL%': round(t.pnl_pct * 100, 2),
            'Days': t.days_held,
            'Reason': t.exit_reason
        } for t in self.trades])
        trades_df.to_csv('optimized_trades.csv', index=False)

        return report


def main():
    print("\n" + "=" * 70)
    print("OPTIMIZED TREND-FOLLOWING STRATEGY BACKTEST")
    print("More aggressive parameters for higher returns")
    print("=" * 70)

    backtester = OptimizedBacktester(data_dir='historical_data', initial_capital=100000)
    report = backtester.run_backtest(start_date='1980-01-01', end_date='2024-12-31')

    print("\n" + "=" * 70)
    print("OPTIMIZED BACKTEST RESULTS")
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

    return report


if __name__ == '__main__':
    main()
