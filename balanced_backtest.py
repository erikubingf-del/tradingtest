"""
BALANCED Trend-Following Strategy Backtest
Target: ~17% CAGR with ~45% Max Drawdown
Middle ground between aggressive returns and controlled risk
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass


PARAMS = {
    # Trend confirmation - moderate selectivity
    'mom_12m_min': 0.08,         # 8% 12m momentum minimum
    'mom_6m_min': 0.04,          # 4% 6m momentum
    'mom_3m_min': 0.02,          # 2% 3m momentum
    'mom_1m_min': 0.01,          # 1% 1m momentum (positive)

    # Leverage tiers - CAPPED AT 2x (key difference from aggressive)
    'lev_tier_1': 1.0,           # Base - no leverage
    'lev_tier_2': 1.25,          # Moderate trend
    'lev_tier_3': 1.75,          # Strong trend
    'lev_tier_4': 2.0,           # Very strong - capped at 2x (not 3x)

    # Position sizing
    'position_size': 0.06,       # 6% per position
    'max_positions': 15,

    # Deleverage triggers - FAST but not instant
    'delev_pullback': 0.02,      # 2% pullback = reduce leverage
    'delev_mom_decay': 0.35,     # Momentum dropped 35% from peak

    # Exit triggers - MODERATE
    'exit_stop': -0.04,          # 4% stop loss
    'exit_trail_lev': 1.5,       # 1.5 ATR when leveraged
    'exit_trail_base': 2.2,      # 2.2 ATR when not leveraged
    'exit_pullback': 0.05,       # 5% pullback from high = exit

    # NO drawdown protection - rely on position-level risk management
}


@dataclass
class Position:
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: float
    leverage: float = 1.0
    highest_price: float = 0.0
    peak_momentum: float = 0.0
    entry_atr: float = 0.0


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


class BalancedBacktester:
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
        df['TR'] = np.maximum(df['High'] - df['Low'],
                              np.maximum(abs(df['High'] - df['Close'].shift(1)),
                                        abs(df['Low'] - df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(14).mean()
        df['Donchian_High'] = df['High'].rolling(20).max()
        return df

    def _get_trend_strength(self, ticker: str, date: datetime) -> int:
        """Calculate trend strength score (0-4)"""
        if ticker not in self.data or date not in self.data[ticker].index:
            return 0

        row = self.data[ticker].loc[date]
        score = 0

        # Check each momentum timeframe
        mom_12m = row.get('Mom_12m', 0)
        mom_6m = row.get('Mom_6m', 0)
        mom_3m = row.get('Mom_3m', 0)
        mom_1m = row.get('Mom_1m', 0)

        if not pd.isna(mom_12m) and mom_12m > PARAMS['mom_12m_min']:
            score += 1
        if not pd.isna(mom_6m) and mom_6m > PARAMS['mom_6m_min']:
            score += 1
        if not pd.isna(mom_3m) and mom_3m > PARAMS['mom_3m_min']:
            score += 1
        if not pd.isna(mom_1m) and mom_1m > PARAMS['mom_1m_min']:
            score += 1

        return score

    def _get_leverage_for_strength(self, strength: int) -> float:
        """Map trend strength to leverage level"""
        if strength <= 1:
            return PARAMS['lev_tier_1']
        elif strength == 2:
            return PARAMS['lev_tier_2']
        elif strength == 3:
            return PARAMS['lev_tier_3']
        else:
            return PARAMS['lev_tier_4']

    def _check_entry(self, ticker: str, date: datetime) -> Tuple[bool, int]:
        """Check if we should enter a position"""
        strength = self._get_trend_strength(ticker, date)

        if strength < 2:  # Need at least 2 momentum timeframes aligned
            return False, 0

        if ticker not in self.data or date not in self.data[ticker].index:
            return False, 0

        row = self.data[ticker].loc[date]

        # Golden cross check
        sma50 = row.get('SMA50', 0)
        sma200 = row.get('SMA200', 0)
        if pd.isna(sma50) or pd.isna(sma200) or sma50 <= sma200:
            return False, 0

        # Price above SMA50
        if row['Close'] < sma50:
            return False, 0

        return True, strength

    def _check_deleverage(self, pos: Position, date: datetime) -> float:
        """Check if we should reduce leverage"""
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return pos.leverage

        row = self.data[ticker].loc[date]
        price = row['Close']

        # Pullback check
        if pos.highest_price > 0:
            pullback = (pos.highest_price - price) / pos.highest_price
            if pullback > PARAMS['delev_pullback']:
                return max(1.0, pos.leverage - 0.5)

        # Momentum decay check
        current_mom = row.get('Mom_12m', 0)
        if not pd.isna(current_mom) and pos.peak_momentum > 0:
            decay = 1 - (current_mom / pos.peak_momentum)
            if decay > PARAMS['delev_mom_decay']:
                return max(1.0, pos.leverage - 0.5)

        return pos.leverage

    def _check_exit(self, pos: Position, date: datetime) -> Tuple[bool, str]:
        """Check if we should exit a position"""
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return False, ""

        row = self.data[ticker].loc[date]
        price = row['Close']
        pnl = (price - pos.entry_price) / pos.entry_price

        # Stop loss
        if pnl <= PARAMS['exit_stop']:
            return True, "STOP"

        # Pullback exit
        if pos.highest_price > 0:
            pullback = (pos.highest_price - price) / pos.highest_price
            if pullback > PARAMS['exit_pullback']:
                return True, "PULLBACK"

        # Trailing stop (ATR-based)
        atr = row.get('ATR', 0)
        if not pd.isna(atr) and pos.highest_price > 0 and atr > 0:
            trail_mult = PARAMS['exit_trail_lev'] if pos.leverage > 1.0 else PARAMS['exit_trail_base']
            stop = pos.highest_price - trail_mult * atr
            if price < stop:
                return True, "TRAIL"

        # Momentum reversal
        mom_1m = row.get('Mom_1m', 0)
        if not pd.isna(mom_1m) and mom_1m < -0.05:  # 5% negative 1m momentum
            return True, "MOM_REV"

        return False, ""

    def run_backtest(self, start_date='1980-01-01', end_date='2024-12-31'):
        print(f"\nBalanced backtest: {start_date} to {end_date}")
        print("Target: ~17% CAGR, ~45% Max DD")
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

            # Process exits
            to_close = []
            for ticker, pos in list(self.positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue

                price = self.data[ticker].loc[date, 'Close']
                if price > pos.highest_price:
                    pos.highest_price = price

                # Update momentum peak
                mom = self.data[ticker].loc[date].get('Mom_12m', 0)
                if not pd.isna(mom) and mom > pos.peak_momentum:
                    pos.peak_momentum = mom

                # Check for deleverage
                new_leverage = self._check_deleverage(pos, date)
                if new_leverage < pos.leverage:
                    pos.leverage = new_leverage

                # Check for exit
                should_exit, reason = self._check_exit(pos, date)
                if should_exit:
                    to_close.append((ticker, reason, price))

            # Execute exits
            for ticker, reason, price in to_close:
                pos = self.positions[ticker]
                pnl = (price - pos.entry_price) * pos.shares * pos.leverage
                pnl_pct = (price - pos.entry_price) / pos.entry_price * pos.leverage
                self.trades.append(Trade(
                    ticker, pos.entry_date, date, pos.entry_price, price,
                    pos.shares, pos.leverage, pnl, pnl_pct,
                    (date - pos.entry_date).days, reason
                ))
                self.capital += pos.shares * pos.entry_price + pnl
                del self.positions[ticker]

            # Calculate portfolio value
            portfolio_value = self.capital
            for ticker, pos in self.positions.items():
                if ticker in self.data and date in self.data[ticker].index:
                    price = self.data[ticker].loc[date, 'Close']
                    upnl = (price - pos.entry_price) * pos.shares * pos.leverage
                    portfolio_value += pos.shares * pos.entry_price + upnl

            # Update peak
            if portfolio_value > self.peak_equity:
                self.peak_equity = portfolio_value

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
                        leverage = self._get_leverage_for_strength(strength)

                        pos = Position(
                            ticker=ticker,
                            entry_date=date,
                            entry_price=price,
                            shares=shares,
                            leverage=leverage,
                            highest_price=price,
                            peak_momentum=row.get('Mom_12m', 0) if not pd.isna(row.get('Mom_12m')) else 0,
                            entry_atr=row.get('ATR', 0) if not pd.isna(row.get('ATR')) else 0
                        )
                        self.positions[ticker] = pos
                        self.capital -= pos_value

                        if len(self.positions) >= PARAMS['max_positions']:
                            break

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

        equity_df.to_csv('balanced_equity_curve.csv')
        trades_df = pd.DataFrame([{
            'Entry': t.entry_date.strftime('%Y-%m-%d'),
            'Exit': t.exit_date.strftime('%Y-%m-%d'),
            'Ticker': t.ticker,
            'Lev': t.max_leverage,
            'PnL%': round(t.pnl_pct * 100, 2),
            'Reason': t.exit_reason
        } for t in self.trades])
        trades_df.to_csv('balanced_trades.csv', index=False)

        return report


def main():
    print("\n" + "=" * 70)
    print("BALANCED TREND-FOLLOWING BACKTEST")
    print("Target: ~17% CAGR with ~45% Max Drawdown")
    print("=" * 70)

    bt = BalancedBacktester('historical_data', 100000)
    r = bt.run_backtest()

    print("\n" + "=" * 70)
    print("BALANCED BACKTEST RESULTS")
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
