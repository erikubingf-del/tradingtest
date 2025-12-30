"""
CRASH-PROTECTED Trend-Following Strategy
Key Innovation: Daily momentum protection + aggressive profit-locking

Goal: 18%+ CAGR with <45% Max Drawdown
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass


PARAMS = {
    # Entry: Standard trend confirmation
    'entry_mom_12m': 0.10,
    'entry_mom_6m': 0.05,
    'entry_mom_3m': 0.02,
    'entry_mom_1m': 0.01,
    'min_signals': 3,

    # LEVERAGE: Conservative, only after proof
    'max_leverage': 2.0,           # Cap at 2x (not 3x)
    'lev_confirm_days': 7,         # Need 7 profitable days
    'lev_min_profit': 0.04,        # Need 4% profit before leverage

    # CRASH PROTECTION - Exit if today's move is bad
    'daily_loss_exit': -0.02,      # Exit if today's price move is -2%
    'daily_loss_delev': -0.01,     # Deleverage if today's move is -1%

    # PROFIT LOCKING - Aggressive trailing stops
    'trail_base': 2.0,
    'trail_at_5pct': 1.5,          # After 5% gain
    'trail_at_10pct': 1.0,         # After 10% gain
    'trail_at_15pct': 0.7,         # After 15% gain - LOCK IT IN

    # QUICK PROFITS - Take profits early
    'take_profit_20pct': True,     # Exit at 20% profit (don't be greedy)

    # Standard exits
    'stop_loss': -0.035,           # 3.5% stop
    'mom_reversal': -0.02,         # Exit if 1m momentum goes to -2%

    # Position sizing
    'position_size': 0.06,
    'max_positions': 12,
}


@dataclass
class Position:
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: float
    leverage: float = 1.0
    highest_price: float = 0.0
    prev_close: float = 0.0
    days_profitable: int = 0


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


class CrashProtectedBacktester:
    def __init__(self, data_dir: str = 'historical_data', initial_capital: float = 100000):
        self.data_dir = data_dir
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve = []
        self.peak_equity = initial_capital

        print("Loading data...")
        self.data = self._load_all_data()
        self.all_dates = self._get_all_trading_dates()

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
                    if 'Close' in df.columns and len(df) > 252:
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
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['Mom_12m'] = df['Close'].pct_change(252)
        df['Mom_6m'] = df['Close'].pct_change(126)
        df['Mom_3m'] = df['Close'].pct_change(63)
        df['Mom_1m'] = df['Close'].pct_change(21)
        df['Daily_Return'] = df['Close'].pct_change()  # TODAY's return
        df['TR'] = np.maximum(df['High'] - df['Low'],
                              np.maximum(abs(df['High'] - df['Close'].shift(1)),
                                        abs(df['Low'] - df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(14).mean()
        return df

    def _check_entry(self, ticker: str, date: datetime) -> Tuple[bool, int]:
        if ticker not in self.data or date not in self.data[ticker].index:
            return False, 0

        row = self.data[ticker].loc[date]
        score = 0

        mom_12m = row.get('Mom_12m', 0)
        mom_6m = row.get('Mom_6m', 0)
        mom_3m = row.get('Mom_3m', 0)
        mom_1m = row.get('Mom_1m', 0)

        if pd.isna(mom_12m):
            return False, 0

        if mom_12m > PARAMS['entry_mom_12m']:
            score += 1
        if not pd.isna(mom_6m) and mom_6m > PARAMS['entry_mom_6m']:
            score += 1
        if not pd.isna(mom_3m) and mom_3m > PARAMS['entry_mom_3m']:
            score += 1
        if not pd.isna(mom_1m) and mom_1m > PARAMS['entry_mom_1m']:
            score += 1

        if score < PARAMS['min_signals']:
            return False, 0

        # Golden cross + above SMA50
        sma50 = row.get('SMA50')
        sma200 = row.get('SMA200')
        if pd.isna(sma50) or pd.isna(sma200):
            return False, 0
        if row['Close'] <= sma50 or sma50 <= sma200:
            return False, 0

        return True, score

    def _get_trailing_atr_mult(self, profit_pct: float, leveraged: bool) -> float:
        """Tighten trailing stop as profit increases"""
        if profit_pct >= 0.15:
            mult = PARAMS['trail_at_15pct']
        elif profit_pct >= 0.10:
            mult = PARAMS['trail_at_10pct']
        elif profit_pct >= 0.05:
            mult = PARAMS['trail_at_5pct']
        else:
            mult = PARAMS['trail_base']

        if leveraged:
            mult *= 0.8  # Even tighter when leveraged

        return mult

    def run_backtest(self, start_date='1980-01-01', end_date='2024-12-31'):
        print(f"\nCrash-Protected backtest: {start_date} to {end_date}")
        print("=" * 70)

        for ticker in self.data:
            self.data[ticker] = self._calculate_indicators(self.data[ticker])

        start_dt, end_dt = pd.Timestamp(start_date), pd.Timestamp(end_date)
        trading_dates = [d for d in self.all_dates if start_dt <= d <= end_dt]

        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.peak_equity = self.initial_capital

        for i, date in enumerate(trading_dates):
            if i < 252:
                continue

            to_close = []

            for ticker, pos in list(self.positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue

                row = self.data[ticker].loc[date]
                price = row['Close']
                daily_ret = row.get('Daily_Return', 0)

                # Update tracking
                if price > pos.highest_price:
                    pos.highest_price = price

                pnl_pct = (price - pos.entry_price) / pos.entry_price
                if pnl_pct > 0:
                    pos.days_profitable += 1

                # ===== CRASH PROTECTION: Daily loss check =====
                if not pd.isna(daily_ret):
                    # Exit if today's loss is severe
                    if daily_ret <= PARAMS['daily_loss_exit']:
                        to_close.append((ticker, "DAILY_CRASH", price))
                        continue
                    # Deleverage if today's loss is moderate
                    if daily_ret <= PARAMS['daily_loss_delev'] and pos.leverage > 1:
                        pos.leverage = 1.0

                # ===== TAKE PROFIT: Don't be greedy =====
                if PARAMS['take_profit_20pct'] and pnl_pct >= 0.20:
                    to_close.append((ticker, "TAKE_PROFIT", price))
                    continue

                # ===== STOP LOSS =====
                if pnl_pct * pos.leverage <= PARAMS['stop_loss']:
                    to_close.append((ticker, "STOP", price))
                    continue

                # ===== TRAILING STOP =====
                atr = row.get('ATR')
                if not pd.isna(atr) and pos.highest_price > 0:
                    mult = self._get_trailing_atr_mult(pnl_pct, pos.leverage > 1)
                    trail_stop = pos.highest_price - mult * atr
                    if price < trail_stop:
                        to_close.append((ticker, "TRAIL", price))
                        continue

                # ===== MOMENTUM REVERSAL =====
                mom_1m = row.get('Mom_1m')
                if not pd.isna(mom_1m) and mom_1m < PARAMS['mom_reversal']:
                    to_close.append((ticker, "MOM_REV", price))
                    continue

                # ===== UPDATE LEVERAGE =====
                # Only add leverage after confirmed profitable period
                if pos.days_profitable >= PARAMS['lev_confirm_days'] and pnl_pct >= PARAMS['lev_min_profit']:
                    if pos.leverage < PARAMS['max_leverage']:
                        pos.leverage = PARAMS['max_leverage']

                pos.prev_close = price

            # Execute exits
            for ticker, reason, price in to_close:
                pos = self.positions[ticker]
                pnl = (price - pos.entry_price) * pos.shares * pos.leverage
                pnl_pct = (price - pos.entry_price) / pos.entry_price * pos.leverage
                days_held = (date - pos.entry_date).days
                self.trades.append(Trade(
                    ticker, pos.entry_date, date, pos.entry_price, price,
                    pos.shares, pos.leverage, pnl, pnl_pct, days_held, reason
                ))
                self.capital += pos.shares * pos.entry_price + pnl
                del self.positions[ticker]

            # New entries
            if len(self.positions) < PARAMS['max_positions']:
                for ticker in self.data:
                    if ticker in self.positions:
                        continue

                    can_enter, strength = self._check_entry(ticker, date)
                    if can_enter and date in self.data[ticker].index:
                        row = self.data[ticker].loc[date]
                        price = row['Close']

                        pos_value = self.capital * PARAMS['position_size']
                        shares = pos_value / price

                        pos = Position(
                            ticker=ticker,
                            entry_date=date,
                            entry_price=price,
                            shares=shares,
                            leverage=1.0,
                            highest_price=price,
                            prev_close=price,
                            days_profitable=0
                        )
                        self.positions[ticker] = pos
                        self.capital -= pos_value

                        if len(self.positions) >= PARAMS['max_positions']:
                            break

            # Portfolio value
            portfolio_value = self.capital
            for ticker, pos in self.positions.items():
                if ticker in self.data and date in self.data[ticker].index:
                    price = self.data[ticker].loc[date, 'Close']
                    upnl = (price - pos.entry_price) * pos.shares * pos.leverage
                    portfolio_value += pos.shares * pos.entry_price + upnl

            if portfolio_value > self.peak_equity:
                self.peak_equity = portfolio_value

            self.equity_curve.append((date, portfolio_value))

            if i % 1000 == 0:
                years = (date - trading_dates[252]).days / 365.25
                if years > 0:
                    cagr = (portfolio_value / self.initial_capital) ** (1/years) - 1
                    dd = (portfolio_value - self.peak_equity) / self.peak_equity * 100
                    print(f"  {date.strftime('%Y-%m-%d')}: ${portfolio_value:,.0f} | CAGR: {cagr*100:.1f}% | DD: {dd:.1f}%")

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
        calmar = abs(cagr / max_dd) if max_dd != 0 else 0

        if self.trades:
            wins = [t for t in self.trades if t.pnl > 0]
            losses = [t for t in self.trades if t.pnl <= 0]
            win_rate = len(wins) / len(self.trades)
            avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
            avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0
            avg_lev = np.mean([t.max_leverage for t in self.trades])

            # Exit reason breakdown
            exit_reasons = {}
            for t in self.trades:
                exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1
        else:
            win_rate = avg_win = avg_loss = avg_lev = 0
            exit_reasons = {}

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
            'calmar_ratio': round(calmar, 2),
            'max_drawdown': round(max_dd * 100, 2),
            'total_trades': len(self.trades),
            'win_rate': round(win_rate * 100, 2),
            'avg_win': round(avg_win * 100, 2),
            'avg_loss': round(avg_loss * 100, 2),
            'avg_leverage': round(avg_lev, 2),
            'exit_reasons': exit_reasons,
        }

        equity_df.to_csv('crash_protected_equity.csv')

        return report


def main():
    print("\n" + "=" * 70)
    print("CRASH-PROTECTED TREND-FOLLOWING BACKTEST")
    print("Goal: 18%+ CAGR with <45% Max Drawdown")
    print("=" * 70)

    bt = CrashProtectedBacktester('historical_data', 100000)
    r = bt.run_backtest()

    print("\n" + "=" * 70)
    print("CRASH-PROTECTED BACKTEST RESULTS")
    print("=" * 70)
    print(f"""
Period:           {r['start_date']} to {r['end_date']} ({r['years']} years)
Initial:          ${r['initial_capital']:,}
Final:            ${r['final_equity']:,.2f}
Total Return:     {r['total_return']}%

CAGR:             {r['cagr']}%
Volatility:       {r['volatility']}%
Sharpe:           {r['sharpe_ratio']}
Calmar:           {r['calmar_ratio']}
Max Drawdown:     {r['max_drawdown']}%

Trades:           {r['total_trades']}
Win Rate:         {r['win_rate']}%
Avg Win:          {r['avg_win']}%
Avg Loss:         {r['avg_loss']}%
Avg Leverage:     {r['avg_leverage']}x

Exit Reasons:     {r['exit_reasons']}
""")

    return r


if __name__ == '__main__':
    main()
