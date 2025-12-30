"""
SMART LEVERAGE + FAST EXIT
Same proven entry as Smart Leverage, but with much faster exits

Key changes from Smart Leverage:
1. Tighter trailing stops (especially when leveraged)
2. Daily momentum check for exit
3. Portfolio-level regime filter
4. Instant deleverage on any weakness
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass


PARAMS = {
    # Entry: Exact same as Smart Leverage
    'entry_mom_12m': 0.10,
    'entry_mom_6m': 0.05,
    'entry_mom_3m': 0.02,
    'entry_mom_1m': 0.01,
    'min_signals': 3,

    # Position sizing
    'position_size': 0.05,         # Slightly smaller
    'max_positions': 12,

    # Leverage: Same tiers but MORE SELECTIVE
    'lev_tier_1': 1.0,
    'lev_tier_2': 1.5,
    'lev_tier_3': 2.0,
    'lev_tier_4': 2.5,
    'lev_min_profit': 0.04,        # Need 4% profit
    'lev_min_days': 8,             # Need 8 profitable days

    # FASTER DELEVERAGE (key change)
    'delev_pullback': 0.012,       # 1.2% pullback = instant deleverage
    'delev_daily_loss': -0.012,    # -1.2% daily move = deleverage
    'delev_mom_1w_neg': True,      # Weekly momentum negative = deleverage

    # TIGHTER TRAILING STOPS (key change)
    'trail_base': 1.8,             # Tighter base
    'trail_at_profit': 1.2,        # Much tighter after profit
    'trail_lev': 0.9,              # Very tight when leveraged

    # Exits
    'exit_stop': -0.03,            # 3% stop (tighter)
    'exit_mom_rev': -0.015,        # Exit at smaller momentum reversal

    # REGIME FILTER
    'market_ticker': 'SP500',
    'regime_check': True,
}


@dataclass
class Position:
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: float
    leverage: float = 1.0
    highest_price: float = 0.0
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


class SmartFastExitBacktester:
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
        df['Mom_1w'] = df['Close'].pct_change(5)
        df['Daily_Return'] = df['Close'].pct_change()
        df['TR'] = np.maximum(df['High'] - df['Low'],
                              np.maximum(abs(df['High'] - df['Close'].shift(1)),
                                        abs(df['Low'] - df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(14).mean()
        return df

    def _get_signal_strength(self, ticker: str, date: datetime) -> int:
        if ticker not in self.data or date not in self.data[ticker].index:
            return 0

        row = self.data[ticker].loc[date]
        score = 0

        mom_12m = row.get('Mom_12m', 0)
        mom_6m = row.get('Mom_6m', 0)
        mom_3m = row.get('Mom_3m', 0)
        mom_1m = row.get('Mom_1m', 0)

        if not pd.isna(mom_12m) and mom_12m > PARAMS['entry_mom_12m']:
            score += 1
        if not pd.isna(mom_6m) and mom_6m > PARAMS['entry_mom_6m']:
            score += 1
        if not pd.isna(mom_3m) and mom_3m > PARAMS['entry_mom_3m']:
            score += 1
        if not pd.isna(mom_1m) and mom_1m > PARAMS['entry_mom_1m']:
            score += 1

        return score

    def _check_entry(self, ticker: str, date: datetime) -> bool:
        strength = self._get_signal_strength(ticker, date)
        if strength < PARAMS['min_signals']:
            return False

        if ticker not in self.data or date not in self.data[ticker].index:
            return False

        row = self.data[ticker].loc[date]
        sma50 = row.get('SMA50')
        sma200 = row.get('SMA200')

        if pd.isna(sma50) or pd.isna(sma200):
            return False
        if row['Close'] <= sma50 or sma50 <= sma200:
            return False

        return True

    def _is_market_ok(self, date: datetime) -> bool:
        """Check if S&P500 is above 200 SMA"""
        if not PARAMS['regime_check']:
            return True

        market = PARAMS['market_ticker']
        if market not in self.data or date not in self.data[market].index:
            return True

        row = self.data[market].loc[date]
        sma200 = row.get('SMA200')
        if pd.isna(sma200):
            return True

        return row['Close'] > sma200 * 0.98  # 2% buffer

    def run_backtest(self, start_date='1980-01-01', end_date='2024-12-31'):
        print(f"\nSmart Fast Exit backtest: {start_date} to {end_date}")
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

            market_ok = self._is_market_ok(date)
            to_close = []

            # Process existing positions
            for ticker, pos in list(self.positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue

                row = self.data[ticker].loc[date]
                price = row['Close']
                daily_ret = row.get('Daily_Return', 0)

                if price > pos.highest_price:
                    pos.highest_price = price

                pnl_pct = (price - pos.entry_price) / pos.entry_price

                if pnl_pct > 0:
                    pos.days_profitable += 1

                strength = self._get_signal_strength(ticker, date)

                # ===== FAST DELEVERAGE =====
                if pos.leverage > 1:
                    should_delev = False

                    # Pullback from high
                    if pos.highest_price > 0:
                        pullback = (pos.highest_price - price) / pos.highest_price
                        if pullback > PARAMS['delev_pullback']:
                            should_delev = True

                    # Daily loss
                    if not pd.isna(daily_ret) and daily_ret < PARAMS['delev_daily_loss']:
                        should_delev = True

                    # Weekly momentum negative
                    mom_1w = row.get('Mom_1w')
                    if PARAMS['delev_mom_1w_neg'] and not pd.isna(mom_1w) and mom_1w < 0:
                        should_delev = True

                    # Market not OK
                    if not market_ok:
                        should_delev = True

                    if should_delev:
                        pos.leverage = 1.0

                # ===== EXITS =====
                # Stop loss
                if pnl_pct * pos.leverage <= PARAMS['exit_stop']:
                    to_close.append((ticker, "STOP", price))
                    continue

                # Trailing stop
                atr = row.get('ATR')
                if not pd.isna(atr) and pos.highest_price > 0:
                    if pos.leverage > 1:
                        mult = PARAMS['trail_lev']
                    elif pnl_pct > 0.05:
                        mult = PARAMS['trail_at_profit']
                    else:
                        mult = PARAMS['trail_base']

                    trail_stop = pos.highest_price - mult * atr
                    if price < trail_stop:
                        to_close.append((ticker, "TRAIL", price))
                        continue

                # Momentum reversal (faster)
                mom_1m = row.get('Mom_1m')
                if not pd.isna(mom_1m) and mom_1m < PARAMS['exit_mom_rev']:
                    to_close.append((ticker, "MOM_REV", price))
                    continue

                # ===== UPDATE LEVERAGE =====
                if pos.leverage == 1.0 and market_ok:
                    if pos.days_profitable >= PARAMS['lev_min_days'] and pnl_pct >= PARAMS['lev_min_profit']:
                        if strength >= 4:
                            pos.leverage = PARAMS['lev_tier_4']
                        elif strength >= 3:
                            pos.leverage = PARAMS['lev_tier_3']

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

            # New entries (only if market is OK)
            if market_ok and len(self.positions) < PARAMS['max_positions']:
                for ticker in self.data:
                    if ticker in self.positions:
                        continue

                    if self._check_entry(ticker, date) and date in self.data[ticker].index:
                        row = self.data[ticker].loc[date]
                        price = row['Close']

                        # Get portfolio value for position sizing
                        portfolio_value = self.capital
                        for t, p in self.positions.items():
                            if t in self.data and date in self.data[t].index:
                                px = self.data[t].loc[date, 'Close']
                                upnl = (px - p.entry_price) * p.shares * p.leverage
                                portfolio_value += p.shares * p.entry_price + upnl

                        pos_value = portfolio_value * PARAMS['position_size']
                        if self.capital < pos_value:
                            continue

                        shares = pos_value / price

                        pos = Position(
                            ticker=ticker,
                            entry_date=date,
                            entry_price=price,
                            shares=shares,
                            leverage=1.0,
                            highest_price=price,
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
                    mkt = "OK" if market_ok else "BEAR"
                    print(f"  {date.strftime('%Y-%m-%d')}: ${portfolio_value:,.0f} | CAGR: {cagr*100:.1f}% | DD: {dd:.1f}% | {mkt}")

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

        equity_df.to_csv('smart_fast_exit_equity.csv')
        return report


def main():
    print("\n" + "=" * 70)
    print("SMART LEVERAGE + FAST EXIT BACKTEST")
    print("Same entries as Smart Leverage, but faster exits")
    print("=" * 70)

    bt = SmartFastExitBacktester('historical_data', 100000)
    r = bt.run_backtest()

    print("\n" + "=" * 70)
    print("SMART FAST EXIT RESULTS")
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
