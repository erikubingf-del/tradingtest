"""
OPTIMAL LEVERAGE Strategy
Target: 20% CAGR with -40% Max Drawdown

Simplified approach:
1. High leverage (2.5-3x) ONLY when multiple momentum timeframes align
2. Immediate deleverage on ANY weakness signal
3. Tighter stops when leveraged
4. No complex protection modes - just dynamic leverage management
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass


PARAMS = {
    # Strong trend requirements - MORE SELECTIVE
    'mom_12m_strong': 0.25,    # 25% 12m momentum for leverage
    'mom_6m_strong': 0.15,     # 15% 6m momentum
    'mom_3m_strong': 0.08,     # 8% 3m momentum
    'mom_1m_positive': 0.02,   # 2% 1m momentum

    # Leverage tiers - HIGHER MAX but less usage
    'lev_tier_1': 1.0,   # Base - no leverage (default)
    'lev_tier_2': 1.0,   # Still no leverage - need stronger signal
    'lev_tier_3': 2.0,   # Strong - 4+ signals aligned
    'lev_tier_4': 3.0,   # Very strong - all aligned + breakout

    # Position sizing - slightly larger
    'position_size': 0.07,
    'max_positions': 12,

    # IMMEDIATE deleverage triggers - VERY FAST
    'delev_pullback': 0.008,      # 0.8% pullback = deleverage
    'delev_mom_1m_neg': -0.002,   # Any negative 1m = deleverage

    # Exit triggers - VERY TIGHT
    'exit_stop': -0.025,          # 2.5% stop (very tight)
    'exit_trail_lev': 1.0,        # 1.0 ATR when leveraged (extremely tight)
    'exit_trail_base': 1.8,       # 1.8 ATR when not leveraged
    'exit_pullback': 0.025,       # 2.5% pullback = exit
}


@dataclass
class Position:
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: float
    leverage: float = 1.0
    highest_price: float = 0.0
    max_leverage_used: float = 1.0


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


class OptimalLeverageBacktester:
    def __init__(self, data_dir='historical_data', initial_capital=100000):
        self.data_dir = data_dir
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve = []

        print("Loading data...")
        self.data = self._load_all_data()
        self.all_dates = self._get_all_trading_dates()
        print(f"  Loaded {len(self.data)} assets")

    def _load_all_data(self):
        data = {}
        for f in os.listdir(self.data_dir):
            if f.endswith('.csv') and f != 'data_summary.csv':
                ticker = f.replace('.csv', '')
                try:
                    df = pd.read_csv(os.path.join(self.data_dir, f), header=[0,1,2])
                    df.columns = [c[0] for c in df.columns]
                    df = df.rename(columns={df.columns[0]: 'Date'})
                    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                    df = df.dropna(subset=['Date'])
                    df.set_index('Date', inplace=True)
                    for col in ['Open','High','Low','Close','Volume']:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    if 'Close' in df.columns and len(df) > 252:
                        data[ticker] = df
                except:
                    pass
        return data

    def _get_all_trading_dates(self):
        dates = set()
        for df in self.data.values():
            dates.update(df.index.tolist())
        return pd.DatetimeIndex(sorted(dates))

    def _calc_indicators(self, df):
        df = df.copy()
        df['Mom_12m'] = df['Close'].pct_change(252)
        df['Mom_6m'] = df['Close'].pct_change(126)
        df['Mom_3m'] = df['Close'].pct_change(63)
        df['Mom_1m'] = df['Close'].pct_change(21)
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['TR'] = np.maximum(df['High']-df['Low'],
                    np.maximum(abs(df['High']-df['Close'].shift(1)),
                              abs(df['Low']-df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(14).mean()
        df['High_20'] = df['High'].rolling(20).max()
        return df

    def _get_leverage_tier(self, ticker, date) -> Tuple[float, int]:
        """
        Returns (leverage, tier) based on momentum alignment
        Tier 0 = no entry
        Tier 1-4 = increasing leverage
        """
        if ticker not in self.data or date not in self.data[ticker].index:
            return 0, 0

        row = self.data[ticker].loc[date]

        mom_12m = row.get('Mom_12m', 0)
        mom_6m = row.get('Mom_6m', 0)
        mom_3m = row.get('Mom_3m', 0)
        mom_1m = row.get('Mom_1m', 0)

        if pd.isna(mom_12m) or pd.isna(mom_6m):
            return 0, 0

        # Must have positive 12m momentum to enter
        if mom_12m <= 0:
            return 0, 0

        tier = 1  # Base tier - positive 12m momentum

        # Check for aligned momentum across timeframes
        aligned = 0
        if mom_12m >= PARAMS['mom_12m_strong']:
            aligned += 1
        if not pd.isna(mom_6m) and mom_6m >= PARAMS['mom_6m_strong']:
            aligned += 1
        if not pd.isna(mom_3m) and mom_3m >= PARAMS['mom_3m_strong']:
            aligned += 1
        if not pd.isna(mom_1m) and mom_1m >= PARAMS['mom_1m_positive']:
            aligned += 1

        # Golden cross bonus
        sma50, sma200 = row.get('SMA50'), row.get('SMA200')
        if not pd.isna(sma50) and not pd.isna(sma200) and sma50 > sma200:
            aligned += 1

        # Breakout bonus
        high_20 = row.get('High_20')
        if not pd.isna(high_20) and row['Close'] >= high_20 * 0.99:
            aligned += 1

        if aligned >= 5:
            tier = 4
        elif aligned >= 4:
            tier = 3
        elif aligned >= 2:
            tier = 2
        else:
            tier = 1

        leverage = [0, PARAMS['lev_tier_1'], PARAMS['lev_tier_2'],
                   PARAMS['lev_tier_3'], PARAMS['lev_tier_4']][tier]

        return leverage, tier

    def _should_deleverage(self, pos, date) -> bool:
        """Check if position should be deleveraged immediately"""
        if pos.leverage <= 1.0:
            return False

        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return False

        row = self.data[ticker].loc[date]
        price = row['Close']

        # Pullback from high
        if pos.highest_price > 0:
            pullback = (pos.highest_price - price) / pos.highest_price
            if pullback >= PARAMS['delev_pullback']:
                return True

        # 1-month momentum turning negative
        mom_1m = row.get('Mom_1m', 0)
        if not pd.isna(mom_1m) and mom_1m < PARAMS['delev_mom_1m_neg']:
            return True

        return False

    def _should_exit(self, pos, date) -> Tuple[bool, str]:
        """Check if position should be exited"""
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return False, ""

        row = self.data[ticker].loc[date]
        price = row['Close']
        pnl = (price - pos.entry_price) / pos.entry_price

        # Stop loss
        if pnl <= PARAMS['exit_stop']:
            return True, f"STOP:{pnl*100:.1f}%"

        # Trailing stop
        atr = row.get('ATR', 0)
        if not pd.isna(atr) and pos.highest_price > 0:
            mult = PARAMS['exit_trail_lev'] if pos.leverage > 1 else PARAMS['exit_trail_base']
            stop = pos.highest_price - mult * atr
            if price < stop:
                return True, "TRAIL"

        # Large pullback
        if pos.highest_price > 0:
            pullback = (pos.highest_price - price) / pos.highest_price
            if pullback >= PARAMS['exit_pullback']:
                return True, f"PULL:{pullback*100:.1f}%"

        # Trend reversal
        mom_12m = row.get('Mom_12m', 0)
        if not pd.isna(mom_12m) and mom_12m < -0.05:
            return True, "TREND_REV"

        return False, ""

    def run_backtest(self, start_date='1980-01-01', end_date='2024-12-31'):
        print(f"\nOptimal Leverage Backtest: {start_date} to {end_date}")
        print("=" * 70)

        # Calculate indicators
        for ticker in self.data:
            self.data[ticker] = self._calc_indicators(self.data[ticker])

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

            # Process positions
            to_close = []
            for ticker, pos in list(self.positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue

                price = self.data[ticker].loc[date, 'Close']

                # Update highest price
                if price > pos.highest_price:
                    pos.highest_price = price

                # Check exit
                should_exit, reason = self._should_exit(pos, date)
                if should_exit:
                    to_close.append((ticker, reason, price))
                    continue

                # Check deleverage
                if self._should_deleverage(pos, date):
                    pos.leverage = 1.0
                else:
                    # Check if we can increase leverage
                    new_lev, tier = self._get_leverage_tier(ticker, date)
                    if new_lev > pos.leverage:
                        # Only increase leverage if profitable
                        pnl = (price - pos.entry_price) / pos.entry_price
                        if pnl > 0.015:  # 1.5% profit required
                            pos.leverage = new_lev
                            if new_lev > pos.max_leverage_used:
                                pos.max_leverage_used = new_lev

            # Execute exits
            for ticker, reason, price in to_close:
                pos = self.positions[ticker]
                pnl = (price - pos.entry_price) * pos.shares * pos.leverage
                pnl_pct = (price - pos.entry_price) / pos.entry_price * pos.leverage
                self.trades.append(Trade(
                    ticker, pos.entry_date, date, pos.entry_price, price,
                    pos.shares, pos.max_leverage_used, pnl, pnl_pct,
                    (date - pos.entry_date).days, reason
                ))
                self.capital += pos.shares * pos.entry_price + pnl
                del self.positions[ticker]

            # New entries
            if len(self.positions) < PARAMS['max_positions']:
                for ticker in self.data:
                    if ticker in self.positions:
                        continue

                    lev, tier = self._get_leverage_tier(ticker, date)
                    if tier >= 2 and date in self.data[ticker].index:  # Need at least tier 2
                        price = self.data[ticker].loc[date, 'Close']
                        pos_value = self.capital * PARAMS['position_size']
                        shares = pos_value / price

                        self.positions[ticker] = Position(
                            ticker=ticker,
                            entry_date=date,
                            entry_price=price,
                            shares=shares,
                            leverage=lev,
                            highest_price=price,
                            max_leverage_used=lev
                        )
                        self.capital -= pos_value

                        if len(self.positions) >= PARAMS['max_positions']:
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
                years = (date - trading_dates[252]).days / 365.25
                if years > 0:
                    cagr = (portfolio / self.initial_capital) ** (1/years) - 1
                    avg_lev = np.mean([p.leverage for p in self.positions.values()]) if self.positions else 0
                    print(f"  {date.strftime('%Y-%m-%d')}: ${portfolio:,.0f} | CAGR: {cagr*100:.1f}% | Pos: {len(self.positions)} | AvgLev: {avg_lev:.1f}x")

        return self._generate_report()

    def _generate_report(self):
        if not self.equity_curve:
            return {}

        eq = pd.DataFrame(self.equity_curve, columns=['Date', 'Equity'])
        eq.set_index('Date', inplace=True)

        final = eq['Equity'].iloc[-1]
        start, end = eq.index[0], eq.index[-1]
        years = (end - start).days / 365.25

        cagr = (final / self.initial_capital) ** (1/years) - 1 if years > 0 else 0

        eq['Ret'] = eq['Equity'].pct_change()
        vol = eq['Ret'].std() * np.sqrt(252)
        sharpe = (cagr - 0.03) / vol if vol > 0 else 0

        eq['Peak'] = eq['Equity'].cummax()
        eq['DD'] = (eq['Equity'] - eq['Peak']) / eq['Peak']
        max_dd = eq['DD'].min()

        if self.trades:
            wins = [t for t in self.trades if t.pnl > 0]
            losses = [t for t in self.trades if t.pnl <= 0]
            win_rate = len(wins) / len(self.trades)
            avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
            avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0
            avg_lev = np.mean([t.max_leverage for t in self.trades])
            pct_lev = len([t for t in self.trades if t.max_leverage > 1]) / len(self.trades) * 100
        else:
            win_rate = avg_win = avg_loss = avg_lev = pct_lev = 0

        report = {
            'start_date': start.strftime('%Y-%m-%d'),
            'end_date': end.strftime('%Y-%m-%d'),
            'years': round(years, 1),
            'initial_capital': self.initial_capital,
            'final_equity': round(final, 2),
            'total_return': round((final/self.initial_capital - 1) * 100, 2),
            'cagr': round(cagr * 100, 2),
            'volatility': round(vol * 100, 2),
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown': round(max_dd * 100, 2),
            'total_trades': len(self.trades),
            'win_rate': round(win_rate * 100, 2),
            'avg_win': round(avg_win * 100, 2),
            'avg_loss': round(avg_loss * 100, 2),
            'avg_leverage': round(avg_lev, 2),
            'pct_leveraged': round(pct_lev, 1),
        }

        eq.to_csv('optimal_leverage_equity.csv')
        pd.DataFrame([{
            'Entry': t.entry_date.strftime('%Y-%m-%d'),
            'Exit': t.exit_date.strftime('%Y-%m-%d'),
            'Ticker': t.ticker,
            'MaxLev': t.max_leverage,
            'PnL%': round(t.pnl_pct*100, 2),
            'Reason': t.exit_reason
        } for t in self.trades]).to_csv('optimal_leverage_trades.csv', index=False)

        return report


def main():
    print("\n" + "=" * 70)
    print("OPTIMAL LEVERAGE STRATEGY")
    print("Target: 20% CAGR with -40% Max Drawdown")
    print("=" * 70)

    bt = OptimalLeverageBacktester('historical_data', 100000)
    r = bt.run_backtest()

    print("\n" + "=" * 70)
    print("OPTIMAL LEVERAGE RESULTS")
    print("=" * 70)
    print(f"""
Period:         {r['start_date']} to {r['end_date']} ({r['years']} years)
Initial:        ${r['initial_capital']:,}
Final:          ${r['final_equity']:,.2f}

CAGR:           {r['cagr']}%
Max Drawdown:   {r['max_drawdown']}%
Sharpe:         {r['sharpe_ratio']}
Volatility:     {r['volatility']}%

Trades:         {r['total_trades']}
Win Rate:       {r['win_rate']}%
Avg Win:        {r['avg_win']}%
Avg Loss:       {r['avg_loss']}%
Avg Leverage:   {r['avg_leverage']}x
% Leveraged:    {r['pct_leveraged']}%
""")

    # Assessment
    print("=" * 70)
    if r['cagr'] >= 20 and r['max_drawdown'] >= -40:
        print("TARGET ACHIEVED: 20%+ CAGR with <40% Drawdown!")
    elif r['cagr'] >= 18 and r['max_drawdown'] >= -50:
        print("CLOSE: Good risk-adjusted returns")
    else:
        print(f"Needs tuning: CAGR={r['cagr']}%, MaxDD={r['max_drawdown']}%")

    return r


if __name__ == '__main__':
    main()
