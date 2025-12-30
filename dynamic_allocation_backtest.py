"""
DYNAMIC ALLOCATION Smart Leverage Strategy
Key Innovations on top of Smart Leverage:
1. PYRAMIDING: Add to winners (scale IN as trend confirms)
2. SCALING OUT: Reduce holdings before full exit (partial profit taking)
3. REBALANCING: Shift capital from weak to strong positions
4. DYNAMIC LEVERAGE: Leverage only on best positions with multiple confirmations
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass


PARAMS = {
    # Entry: Same as Smart Leverage
    'entry_mom_12m': 0.10,
    'entry_mom_6m': 0.05,
    'entry_mom_3m': 0.02,
    'entry_mom_1m': 0.01,
    'min_signals': 3,

    # PYRAMIDING: Scale into winners
    'initial_position': 0.03,      # Start with 3% (smaller than before)
    'pyramid_1_profit': 0.03,      # Add at 3% profit
    'pyramid_1_size': 0.02,        # Add 2% more
    'pyramid_2_profit': 0.06,      # Add at 6% profit
    'pyramid_2_size': 0.02,        # Add 2% more
    'max_position_size': 0.10,     # Max 10% per position

    # SCALING OUT: Partial profit taking
    'scale_out_1_profit': 0.15,    # Take 25% off at 15% profit
    'scale_out_1_pct': 0.25,
    'scale_out_2_profit': 0.25,    # Take another 25% off at 25% profit
    'scale_out_2_pct': 0.25,

    # DYNAMIC LEVERAGE: Only on confirmed winners
    'leverage_min_profit': 0.05,   # Need 5% profit before leverage
    'leverage_min_days': 10,       # Need 10 days profitable
    'leverage_tier_1': 1.0,        # Base
    'leverage_tier_2': 1.5,        # Good trend (3 signals)
    'leverage_tier_3': 2.0,        # Strong trend (4 signals + breakout)
    'leverage_tier_4': 2.5,        # Very strong (all confirmations)

    # DELEVERAGE triggers
    'delev_pullback': 0.02,        # 2% pullback = deleverage
    'delev_below_sma50': True,

    # EXIT triggers
    'exit_stop': -0.04,
    'trail_base': 2.0,
    'trail_leveraged': 1.2,
    'exit_mom_rev': -0.03,

    # Portfolio
    'max_positions': 12,
    'max_portfolio_leverage': 1.8,  # Overall portfolio leverage cap
}


@dataclass
class Position:
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: float
    cost_basis: float             # Total cost basis
    leverage: float = 1.0
    highest_price: float = 0.0
    days_profitable: int = 0
    pyramid_level: int = 0        # 0=initial, 1=first add, 2=second add
    scaled_out_1: bool = False
    scaled_out_2: bool = False
    peak_profit_pct: float = 0.0


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


class DynamicAllocationBacktester:
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
        df['Donchian_High'] = df['High'].rolling(20).max()
        df['TR'] = np.maximum(df['High'] - df['Low'],
                              np.maximum(abs(df['High'] - df['Close'].shift(1)),
                                        abs(df['Low'] - df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(14).mean()
        return df

    def _get_signal_strength(self, ticker: str, date: datetime) -> int:
        """Calculate signal strength (0-5)"""
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

        # Breakout bonus
        donchian = row.get('Donchian_High')
        if not pd.isna(donchian) and row['Close'] >= donchian:
            score += 1

        return score

    def _check_entry(self, ticker: str, date: datetime) -> bool:
        if ticker not in self.data or date not in self.data[ticker].index:
            return False

        strength = self._get_signal_strength(ticker, date)
        if strength < PARAMS['min_signals']:
            return False

        row = self.data[ticker].loc[date]
        sma50 = row.get('SMA50')
        sma200 = row.get('SMA200')

        if pd.isna(sma50) or pd.isna(sma200):
            return False
        if row['Close'] <= sma50 or sma50 <= sma200:
            return False

        return True

    def _get_portfolio_value(self, date: datetime) -> float:
        """Calculate total portfolio value"""
        value = self.capital
        for ticker, pos in self.positions.items():
            if ticker in self.data and date in self.data[ticker].index:
                price = self.data[ticker].loc[date, 'Close']
                upnl = (price - pos.entry_price) * pos.shares * pos.leverage
                value += pos.cost_basis + upnl
        return value

    def _get_portfolio_leverage(self, date: datetime) -> float:
        """Calculate overall portfolio leverage"""
        portfolio_value = self._get_portfolio_value(date)
        if portfolio_value <= 0:
            return 0

        total_exposure = 0
        for ticker, pos in self.positions.items():
            if ticker in self.data and date in self.data[ticker].index:
                price = self.data[ticker].loc[date, 'Close']
                total_exposure += pos.shares * price * pos.leverage

        return total_exposure / portfolio_value

    def _get_leverage_for_position(self, pos: Position, strength: int, date: datetime) -> float:
        """Determine appropriate leverage for a position"""
        # Check if position qualifies for leverage
        current_profit = 0
        if pos.ticker in self.data and date in self.data[pos.ticker].index:
            price = self.data[pos.ticker].loc[date, 'Close']
            current_profit = (price - pos.entry_price) / pos.entry_price

        # Need minimum profit and days before leverage
        if current_profit < PARAMS['leverage_min_profit']:
            return 1.0
        if pos.days_profitable < PARAMS['leverage_min_days']:
            return 1.0

        # Check portfolio leverage cap
        if self._get_portfolio_leverage(date) >= PARAMS['max_portfolio_leverage']:
            return pos.leverage  # Don't increase

        # Assign leverage based on strength
        if strength >= 5:
            return PARAMS['leverage_tier_4']
        elif strength >= 4:
            return PARAMS['leverage_tier_3']
        elif strength >= 3:
            return PARAMS['leverage_tier_2']
        else:
            return PARAMS['leverage_tier_1']

    def run_backtest(self, start_date='1980-01-01', end_date='2024-12-31'):
        print(f"\nDynamic Allocation backtest: {start_date} to {end_date}")
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
            portfolio_value = self._get_portfolio_value(date)

            # Process existing positions
            for ticker, pos in list(self.positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue

                row = self.data[ticker].loc[date]
                price = row['Close']

                if price > pos.highest_price:
                    pos.highest_price = price

                pnl_pct = (price - pos.entry_price) / pos.entry_price

                if pnl_pct > 0:
                    pos.days_profitable += 1
                if pnl_pct > pos.peak_profit_pct:
                    pos.peak_profit_pct = pnl_pct

                strength = self._get_signal_strength(ticker, date)

                # ===== PYRAMIDING: Add to winners =====
                if pos.pyramid_level == 0 and pnl_pct >= PARAMS['pyramid_1_profit']:
                    if strength >= PARAMS['min_signals']:
                        # Add to position
                        add_value = portfolio_value * PARAMS['pyramid_1_size']
                        if self.capital >= add_value:
                            add_shares = add_value / price
                            pos.shares += add_shares
                            pos.cost_basis += add_value
                            self.capital -= add_value
                            pos.pyramid_level = 1

                elif pos.pyramid_level == 1 and pnl_pct >= PARAMS['pyramid_2_profit']:
                    if strength >= PARAMS['min_signals']:
                        add_value = portfolio_value * PARAMS['pyramid_2_size']
                        current_pos_value = pos.shares * price
                        if self.capital >= add_value and current_pos_value < portfolio_value * PARAMS['max_position_size']:
                            add_shares = add_value / price
                            pos.shares += add_shares
                            pos.cost_basis += add_value
                            self.capital -= add_value
                            pos.pyramid_level = 2

                # ===== SCALING OUT: Partial profit taking =====
                if not pos.scaled_out_1 and pnl_pct >= PARAMS['scale_out_1_profit']:
                    # Sell 25% of position
                    sell_shares = pos.shares * PARAMS['scale_out_1_pct']
                    sell_value = sell_shares * price
                    pos.shares -= sell_shares
                    pos.cost_basis -= sell_shares * pos.entry_price
                    self.capital += sell_value
                    pos.scaled_out_1 = True

                elif not pos.scaled_out_2 and pnl_pct >= PARAMS['scale_out_2_profit']:
                    sell_shares = pos.shares * PARAMS['scale_out_2_pct']
                    sell_value = sell_shares * price
                    pos.shares -= sell_shares
                    pos.cost_basis -= sell_shares * pos.entry_price
                    self.capital += sell_value
                    pos.scaled_out_2 = True

                # ===== DELEVERAGE triggers =====
                if pos.leverage > 1:
                    # Pullback from high
                    if pos.highest_price > 0:
                        pullback = (pos.highest_price - price) / pos.highest_price
                        if pullback > PARAMS['delev_pullback']:
                            pos.leverage = 1.0

                    # Below SMA50
                    sma50 = row.get('SMA50')
                    if PARAMS['delev_below_sma50'] and not pd.isna(sma50) and price < sma50:
                        pos.leverage = 1.0

                # ===== EXIT triggers =====
                # Stop loss
                if pnl_pct * pos.leverage <= PARAMS['exit_stop']:
                    to_close.append((ticker, "STOP", price))
                    continue

                # Trailing stop
                atr = row.get('ATR')
                if not pd.isna(atr) and pos.highest_price > 0:
                    trail_mult = PARAMS['trail_leveraged'] if pos.leverage > 1 else PARAMS['trail_base']
                    trail_stop = pos.highest_price - trail_mult * atr
                    if price < trail_stop:
                        to_close.append((ticker, "TRAIL", price))
                        continue

                # Momentum reversal
                mom_1m = row.get('Mom_1m')
                if not pd.isna(mom_1m) and mom_1m < PARAMS['exit_mom_rev']:
                    to_close.append((ticker, "MOM_REV", price))
                    continue

                # ===== UPDATE LEVERAGE =====
                new_lev = self._get_leverage_for_position(pos, strength, date)
                if new_lev > pos.leverage:
                    pos.leverage = new_lev

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
                self.capital += pos.cost_basis + pnl
                del self.positions[ticker]

            # New entries
            if len(self.positions) < PARAMS['max_positions']:
                # Sort by signal strength
                candidates = []
                for ticker in self.data:
                    if ticker in self.positions:
                        continue
                    if self._check_entry(ticker, date):
                        strength = self._get_signal_strength(ticker, date)
                        candidates.append((ticker, strength))

                candidates.sort(key=lambda x: -x[1])

                for ticker, strength in candidates:
                    if len(self.positions) >= PARAMS['max_positions']:
                        break

                    if date not in self.data[ticker].index:
                        continue

                    row = self.data[ticker].loc[date]
                    price = row['Close']

                    # Start with smaller position (will pyramid if trend continues)
                    pos_value = self._get_portfolio_value(date) * PARAMS['initial_position']
                    if self.capital < pos_value:
                        continue

                    shares = pos_value / price

                    pos = Position(
                        ticker=ticker,
                        entry_date=date,
                        entry_price=price,
                        shares=shares,
                        cost_basis=pos_value,
                        leverage=1.0,
                        highest_price=price,
                        days_profitable=0,
                        pyramid_level=0,
                        scaled_out_1=False,
                        scaled_out_2=False,
                        peak_profit_pct=0.0
                    )
                    self.positions[ticker] = pos
                    self.capital -= pos_value

            # Portfolio value
            portfolio_value = self._get_portfolio_value(date)

            if portfolio_value > self.peak_equity:
                self.peak_equity = portfolio_value

            self.equity_curve.append((date, portfolio_value))

            if i % 1000 == 0:
                years = (date - trading_dates[252]).days / 365.25
                if years > 0:
                    cagr = (portfolio_value / self.initial_capital) ** (1/years) - 1
                    dd = (portfolio_value - self.peak_equity) / self.peak_equity * 100
                    port_lev = self._get_portfolio_leverage(date)
                    print(f"  {date.strftime('%Y-%m-%d')}: ${portfolio_value:,.0f} | CAGR: {cagr*100:.1f}% | DD: {dd:.1f}% | Lev: {port_lev:.1f}x")

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

        equity_df.to_csv('dynamic_allocation_equity.csv')
        return report


def main():
    print("\n" + "=" * 70)
    print("DYNAMIC ALLOCATION TREND-FOLLOWING BACKTEST")
    print("Pyramiding + Scaling Out + Dynamic Leverage")
    print("=" * 70)

    bt = DynamicAllocationBacktester('historical_data', 100000)
    r = bt.run_backtest()

    print("\n" + "=" * 70)
    print("DYNAMIC ALLOCATION RESULTS")
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
