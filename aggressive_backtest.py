"""
AGGRESSIVE Trend-Following Strategy Backtest
Maximum risk parameters targeting 20%+ CAGR
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass


# =============================================================================
# AGGRESSIVE STRATEGY PARAMETERS
# =============================================================================
STRATEGY_PARAMS = {
    # Entry conditions (fastest possible)
    'momentum_lookback': 126,        # 6-month momentum (faster)
    'sma_short': 20,                 # Faster MA
    'sma_long': 100,                 # Faster long MA
    'donchian_period': 10,           # Quick breakout

    # Position sizing (MAXIMUM AGGRESSIVE)
    'base_position_size': 0.10,      # 10% per position
    'max_positions': 20,             # Many positions
    'max_sector_exposure': 0.50,     # 50% per sector

    # Leverage rules (ALWAYS LEVERAGED)
    'default_leverage': 1.5,         # Start at 1.5x
    'leverage_up_profit': 0.01,      # 1% profit -> more leverage
    'leverage_up_days': 3,           # Very fast
    'leverage_max': 3.0,             # Maximum 3x
    'leverage_pullback_threshold': 0.05,  # 5% pullback

    # Exit rules
    'stop_loss': -0.05,              # -5% stop
    'trailing_atr_multiple': 2.0,    # Tight trailing
}


@dataclass
class Position:
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: float
    leverage: float = 1.5
    highest_price: float = 0.0
    sector: str = 'unknown'


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


class AggressiveBacktester:
    def __init__(self, data_dir: str = 'historical_data', initial_capital: float = 100000):
        self.data_dir = data_dir
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve = []

        print("Loading data...")
        self.data = self._load_all_data()
        self.all_dates = self._get_all_trading_dates()

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
                    if 'Close' in df.columns and len(df) > 126:
                        data[ticker] = df
                except:
                    pass
        print(f"  Loaded {len(data)} assets")
        return data

    def _get_all_trading_dates(self):
        all_dates = set()
        for df in self.data.values():
            all_dates.update(df.index.tolist())
        return pd.DatetimeIndex(sorted(all_dates))

    def _calculate_indicators(self, df):
        df = df.copy()
        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA100'] = df['Close'].rolling(100).mean()
        df['Momentum'] = df['Close'].pct_change(126)  # 6-month
        df['Momentum_1m'] = df['Close'].pct_change(21)  # 1-month

        df['TR'] = np.maximum(df['High'] - df['Low'],
                              np.maximum(abs(df['High'] - df['Close'].shift(1)),
                                        abs(df['Low'] - df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(14).mean()
        df['Donchian_High'] = df['High'].rolling(10).max()
        return df

    def _check_entry(self, ticker: str, date: datetime) -> bool:
        if ticker not in self.data or date not in self.data[ticker].index:
            return False

        df = self.data[ticker]
        idx = df.index.get_loc(date)
        if idx < 126:
            return False

        row = df.iloc[idx]

        # Simple entry: positive momentum + above short-term MA
        mom_ok = row.get('Momentum', 0) > 0 if not pd.isna(row.get('Momentum')) else False
        mom_1m_ok = row.get('Momentum_1m', 0) > 0 if not pd.isna(row.get('Momentum_1m')) else False
        above_sma = row['Close'] > row.get('SMA20', 0) if not pd.isna(row.get('SMA20')) else False

        return mom_ok and mom_1m_ok and above_sma

    def _check_exit(self, pos: Position, date: datetime) -> Tuple[bool, str]:
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return False, ""

        row = self.data[ticker].loc[date]
        price = row['Close']
        pnl = (price - pos.entry_price) / pos.entry_price

        # Stop loss
        if pnl <= STRATEGY_PARAMS['stop_loss']:
            return True, "STOP"

        # Trailing stop
        if not pd.isna(row.get('ATR')) and pos.highest_price > 0:
            stop = pos.highest_price - STRATEGY_PARAMS['trailing_atr_multiple'] * row['ATR']
            if price < stop:
                return True, "TRAIL"

        # Momentum reversal
        if row.get('Momentum', 0) < -0.05:
            return True, "MOM_REV"

        return False, ""

    def _update_leverage(self, pos: Position, date: datetime):
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return

        price = self.data[ticker].loc[date, 'Close']
        pnl = (price - pos.entry_price) / pos.entry_price
        days = (date - pos.entry_date).days

        if price > pos.highest_price:
            pos.highest_price = price

        pullback = (pos.highest_price - price) / pos.highest_price if pos.highest_price > 0 else 0

        # Deleverage on pullback
        if pullback > STRATEGY_PARAMS['leverage_pullback_threshold']:
            pos.leverage = max(1.0, pos.leverage - 0.5)
            return

        # Increase leverage on profit
        if pnl > STRATEGY_PARAMS['leverage_up_profit'] and days >= STRATEGY_PARAMS['leverage_up_days']:
            if pos.leverage < STRATEGY_PARAMS['leverage_max']:
                pos.leverage = min(STRATEGY_PARAMS['leverage_max'], pos.leverage + 0.5)

    def run_backtest(self, start_date='1980-01-01', end_date='2024-12-31'):
        print(f"\nAggressive backtest: {start_date} to {end_date}")
        print("=" * 70)

        for ticker in self.data:
            self.data[ticker] = self._calculate_indicators(self.data[ticker])

        start_dt, end_dt = pd.Timestamp(start_date), pd.Timestamp(end_date)
        trading_dates = [d for d in self.all_dates if start_dt <= d <= end_dt]

        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []

        for i, date in enumerate(trading_dates):
            if i < 126:
                continue

            # Exits
            to_close = []
            for ticker, pos in list(self.positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue
                price = self.data[ticker].loc[date, 'Close']
                if price > pos.highest_price:
                    pos.highest_price = price

                should_exit, reason = self._check_exit(pos, date)
                if should_exit:
                    to_close.append((ticker, reason, price))
                else:
                    self._update_leverage(pos, date)

            for ticker, reason, price in to_close:
                pos = self.positions[ticker]
                pnl = (price - pos.entry_price) * pos.shares * pos.leverage
                pnl_pct = (price - pos.entry_price) / pos.entry_price * pos.leverage
                self.trades.append(Trade(ticker, pos.entry_date, date, pos.entry_price, price,
                                        pos.shares, pos.leverage, pnl, pnl_pct,
                                        (date - pos.entry_date).days, reason))
                self.capital += pos.shares * pos.entry_price + pnl
                del self.positions[ticker]

            # Entries
            if len(self.positions) < STRATEGY_PARAMS['max_positions']:
                for ticker in self.data:
                    if ticker in self.positions:
                        continue
                    if self._check_entry(ticker, date) and date in self.data[ticker].index:
                        price = self.data[ticker].loc[date, 'Close']
                        pos_value = self.capital * STRATEGY_PARAMS['base_position_size']
                        shares = pos_value / price
                        sector = self.sectors.get(ticker, 'unknown')

                        self.positions[ticker] = Position(
                            ticker, date, price, shares,
                            STRATEGY_PARAMS['default_leverage'], price, sector
                        )
                        self.capital -= pos_value

                        if len(self.positions) >= STRATEGY_PARAMS['max_positions']:
                            break

            # Portfolio value
            portfolio = self.capital
            for ticker, pos in self.positions.items():
                if ticker in self.data and date in self.data[ticker].index:
                    price = self.data[ticker].loc[date, 'Close']
                    upnl = (price - pos.entry_price) * pos.shares * pos.leverage
                    portfolio += pos.shares * pos.entry_price + upnl

            self.equity_curve.append((date, portfolio))

            if i % 1000 == 0:
                years = (date - trading_dates[126]).days / 365.25
                if years > 0:
                    cagr = (portfolio / self.initial_capital) ** (1/years) - 1
                    print(f"  {date.strftime('%Y-%m-%d')}: ${portfolio:,.0f} | CAGR: {cagr*100:.1f}% | Pos: {len(self.positions)}")

        return self._generate_report()

    def _generate_report(self):
        if not self.equity_curve:
            return {}

        equity_df = pd.DataFrame(self.equity_curve, columns=['Date', 'Equity'])
        equity_df.set_index('Date', inplace=True)

        final = equity_df['Equity'].iloc[-1]
        start = equity_df.index[0]
        end = equity_df.index[-1]
        years = (end - start).days / 365.25

        cagr = (final / self.initial_capital) ** (1/years) - 1 if years > 0 else 0

        equity_df['Ret'] = equity_df['Equity'].pct_change()
        vol = equity_df['Ret'].std() * np.sqrt(252)
        sharpe = (cagr - 0.03) / vol if vol > 0 else 0

        equity_df['Peak'] = equity_df['Equity'].cummax()
        equity_df['DD'] = (equity_df['Equity'] - equity_df['Peak']) / equity_df['Peak']
        max_dd = equity_df['DD'].min()

        if self.trades:
            wins = [t for t in self.trades if t.pnl > 0]
            losses = [t for t in self.trades if t.pnl <= 0]
            win_rate = len(wins) / len(self.trades)
            avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
            avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0
            avg_lev = np.mean([t.max_leverage for t in self.trades])
        else:
            win_rate = avg_win = avg_loss = avg_lev = 0

        report = {
            'start_date': start.strftime('%Y-%m-%d'),
            'end_date': end.strftime('%Y-%m-%d'),
            'years': round(years, 1),
            'initial_capital': self.initial_capital,
            'final_equity': round(final, 2),
            'total_return': round((final / self.initial_capital - 1) * 100, 2),
            'cagr': round(cagr * 100, 2),
            'volatility': round(vol * 100, 2),
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown': round(max_dd * 100, 2),
            'total_trades': len(self.trades),
            'win_rate': round(win_rate * 100, 2),
            'avg_win': round(avg_win * 100, 2),
            'avg_loss': round(avg_loss * 100, 2),
            'avg_leverage': round(avg_lev, 2),
        }

        equity_df.to_csv('aggressive_equity_curve.csv')
        trades_df = pd.DataFrame([{
            'Entry': t.entry_date.strftime('%Y-%m-%d'),
            'Exit': t.exit_date.strftime('%Y-%m-%d'),
            'Ticker': t.ticker,
            'Lev': t.max_leverage,
            'PnL%': round(t.pnl_pct * 100, 2),
            'Reason': t.exit_reason
        } for t in self.trades])
        trades_df.to_csv('aggressive_trades.csv', index=False)

        return report


def main():
    print("\n" + "=" * 70)
    print("AGGRESSIVE TREND-FOLLOWING BACKTEST")
    print("Maximum risk for maximum returns")
    print("=" * 70)

    bt = AggressiveBacktester('historical_data', 100000)
    r = bt.run_backtest()

    print("\n" + "=" * 70)
    print("AGGRESSIVE BACKTEST RESULTS")
    print("=" * 70)
    print(f"""
Period:           {r['start_date']} to {r['end_date']} ({r['years']} years)
Initial:          ${r['initial_capital']:,}
Final:            ${r['final_equity']:,.2f}
Total Return:     {r['total_return']}%

CAGR:             {r['cagr']}%
Volatility:       {r['volatility']}%
Sharpe:           {r['sharpe_ratio']}
Max Drawdown:     {r['max_drawdown']}%

Trades:           {r['total_trades']}
Win Rate:         {r['win_rate']}%
Avg Win:          {r['avg_win']}%
Avg Loss:         {r['avg_loss']}%
Avg Leverage:     {r['avg_leverage']}x
""")

    return r


if __name__ == '__main__':
    main()
