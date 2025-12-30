"""
SMART LEVERAGE Trend-Following Strategy
- Aggressive leverage ONLY during confirmed strong trends
- Quick deleverage at first sign of weakness
- Goal: High CAGR with controlled drawdowns
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass


# =============================================================================
# SMART LEVERAGE PARAMETERS
# =============================================================================
PARAMS = {
    # Trend confirmation thresholds (must ALL be met for max leverage)
    'strong_momentum_12m': 0.15,     # 12m momentum > 15% for strong trend
    'strong_momentum_3m': 0.05,      # 3m momentum > 5%
    'strong_momentum_1m': 0.02,      # 1m momentum > 2%
    'price_above_sma_pct': 0.05,     # Price 5% above SMA200

    # Leverage levels based on trend strength
    'leverage_weak': 1.0,            # Weak trend = no leverage
    'leverage_moderate': 1.5,        # Moderate trend
    'leverage_strong': 2.5,          # Strong trend (MORE aggressive)
    'leverage_very_strong': 3.0,     # Very strong (all signals aligned)

    # Position sizing
    'base_position_size': 0.06,      # 6% per position (slightly smaller)
    'max_positions': 15,

    # Quick deleverage triggers (ANY of these = immediate deleverage)
    'deleverage_pullback': 0.02,     # 2% pullback from high
    'deleverage_mom_decay': 0.40,    # Momentum dropped 40% from peak
    'deleverage_volatility_spike': 1.4,  # ATR increased 40%

    # Exit rules (TIGHTER STOPS)
    'stop_loss': -0.04,              # -4% stop (tighter)
    'trailing_atr_base': 2.0,        # Tighter trailing stop
    'trailing_atr_leveraged': 1.5,   # Much tighter when leveraged
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


class SmartLeverageBacktester:
    def __init__(self, data_dir: str = 'historical_data', initial_capital: float = 100000):
        self.data_dir = data_dir
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve = []
        self.leverage_log = []  # Track leverage decisions

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

        # Multiple timeframe momentum
        df['Mom_12m'] = df['Close'].pct_change(252)
        df['Mom_3m'] = df['Close'].pct_change(63)
        df['Mom_1m'] = df['Close'].pct_change(21)

        # Moving averages
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()

        # Distance from SMA200 (for trend strength)
        df['Dist_SMA200'] = (df['Close'] - df['SMA200']) / df['SMA200']

        # ATR for volatility tracking
        df['TR'] = np.maximum(df['High'] - df['Low'],
                              np.maximum(abs(df['High'] - df['Close'].shift(1)),
                                        abs(df['Low'] - df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(14).mean()
        df['ATR_MA'] = df['ATR'].rolling(20).mean()  # Average ATR for comparison

        # Donchian for breakouts
        df['Donchian_High'] = df['High'].rolling(20).max()

        return df

    def _calculate_trend_strength(self, ticker: str, date: datetime) -> Tuple[int, str]:
        """
        Calculate trend strength score (0-4):
        0 = No trend (don't enter)
        1 = Weak trend (1.0x leverage)
        2 = Moderate trend (1.5x leverage)
        3 = Strong trend (2.0x leverage)
        4 = Very strong trend (2.5x leverage)
        """
        if ticker not in self.data or date not in self.data[ticker].index:
            return 0, "No data"

        row = self.data[ticker].loc[date]
        signals = []
        score = 0

        # Check each signal
        mom_12m = row.get('Mom_12m', 0)
        mom_3m = row.get('Mom_3m', 0)
        mom_1m = row.get('Mom_1m', 0)
        dist_sma = row.get('Dist_SMA200', 0)
        sma50 = row.get('SMA50', 0)
        sma200 = row.get('SMA200', 0)

        if pd.isna(mom_12m) or pd.isna(sma200):
            return 0, "Insufficient data"

        # Base requirement: positive 12m momentum
        if mom_12m <= 0:
            return 0, f"Negative 12m momentum: {mom_12m*100:.1f}%"

        score += 1
        signals.append(f"12m={mom_12m*100:.1f}%")

        # Strong 12m momentum
        if mom_12m >= PARAMS['strong_momentum_12m']:
            score += 1
            signals.append("Strong12m")

        # Positive and strong 3m momentum
        if not pd.isna(mom_3m) and mom_3m >= PARAMS['strong_momentum_3m']:
            score += 1
            signals.append(f"3m={mom_3m*100:.1f}%")

        # Positive 1m momentum (trend accelerating)
        if not pd.isna(mom_1m) and mom_1m >= PARAMS['strong_momentum_1m']:
            score += 1
            signals.append(f"1m={mom_1m*100:.1f}%")

        # Price well above SMA200
        if not pd.isna(dist_sma) and dist_sma >= PARAMS['price_above_sma_pct']:
            score += 1
            signals.append(f">{PARAMS['price_above_sma_pct']*100:.0f}%>SMA200")

        # Golden cross
        if not pd.isna(sma50) and sma50 > sma200:
            score += 1
            signals.append("GoldenX")

        # Cap at 4
        score = min(score, 4)

        return score, " | ".join(signals)

    def _get_leverage_for_strength(self, strength: int) -> float:
        """Map trend strength to leverage"""
        if strength <= 1:
            return PARAMS['leverage_weak']
        elif strength == 2:
            return PARAMS['leverage_moderate']
        elif strength == 3:
            return PARAMS['leverage_strong']
        else:
            return PARAMS['leverage_very_strong']

    def _check_deleverage_signals(self, pos: Position, date: datetime) -> Tuple[bool, str]:
        """
        Check if we should immediately reduce leverage.
        Returns (should_deleverage, reason)
        """
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return False, ""

        row = self.data[ticker].loc[date]
        price = row['Close']

        # 1. Pullback from high
        if pos.highest_price > 0:
            pullback = (pos.highest_price - price) / pos.highest_price
            if pullback >= PARAMS['deleverage_pullback']:
                return True, f"Pullback {pullback*100:.1f}%"

        # 2. Momentum decay (momentum dropped significantly from when we entered)
        current_mom = row.get('Mom_12m', 0)
        if not pd.isna(current_mom) and pos.peak_momentum > 0:
            if current_mom < pos.peak_momentum * (1 - PARAMS['deleverage_mom_decay']):
                return True, f"Mom decay {current_mom*100:.1f}% vs peak {pos.peak_momentum*100:.1f}%"

        # 3. Volatility spike (ATR increased significantly)
        current_atr = row.get('ATR', 0)
        if not pd.isna(current_atr) and pos.entry_atr > 0:
            if current_atr > pos.entry_atr * PARAMS['deleverage_volatility_spike']:
                return True, f"Vol spike ATR {current_atr:.2f} vs entry {pos.entry_atr:.2f}"

        # 4. Trend weakening (short-term momentum turning negative)
        mom_1m = row.get('Mom_1m', 0)
        if not pd.isna(mom_1m) and mom_1m < -0.02:  # 1-month momentum negative
            return True, f"Short-term reversal {mom_1m*100:.1f}%"

        return False, ""

    def _update_leverage(self, pos: Position, date: datetime) -> Tuple[float, str]:
        """Update position leverage based on trend strength and deleverage signals"""
        old_leverage = pos.leverage

        # First check deleverage signals (priority)
        should_delev, delev_reason = self._check_deleverage_signals(pos, date)
        if should_delev and pos.leverage > 1.0:
            pos.leverage = 1.0
            return 1.0, f"DELEVERAGE: {delev_reason}"

        # If not deleveraging, check if we can increase leverage
        strength, strength_reason = self._calculate_trend_strength(pos.ticker, date)
        target_leverage = self._get_leverage_for_strength(strength)

        # Only increase leverage, never decrease based on strength (use deleverage signals for that)
        if target_leverage > pos.leverage:
            # Additional check: need to be profitable to increase leverage
            price = self.data[pos.ticker].loc[date, 'Close']
            pnl = (price - pos.entry_price) / pos.entry_price
            if pnl > 0.02:  # At least 2% profit
                pos.leverage = target_leverage
                return target_leverage, f"LEVERAGE UP to {target_leverage}x: {strength_reason}"

        return pos.leverage, ""

    def _check_entry(self, ticker: str, date: datetime) -> Tuple[bool, str]:
        """Check entry conditions"""
        strength, reason = self._calculate_trend_strength(ticker, date)
        if strength >= 2:  # Need at least moderate trend
            return True, reason
        return False, ""

    def _check_exit(self, pos: Position, date: datetime) -> Tuple[bool, str]:
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return False, ""

        row = self.data[ticker].loc[date]
        price = row['Close']
        pnl = (price - pos.entry_price) / pos.entry_price

        # Stop loss (tighter when leveraged)
        effective_stop = PARAMS['stop_loss']
        if pos.leverage > 1.5:
            effective_stop = PARAMS['stop_loss'] * 0.8  # Tighter stop when leveraged

        if pnl <= effective_stop:
            return True, f"STOP: {pnl*100:.1f}%"

        # Trailing stop (tighter when leveraged)
        atr = row.get('ATR', 0)
        if not pd.isna(atr) and pos.highest_price > 0:
            if pos.leverage > 1.0:
                trail_mult = PARAMS['trailing_atr_leveraged']
            else:
                trail_mult = PARAMS['trailing_atr_base']

            stop_price = pos.highest_price - (trail_mult * atr)
            if price < stop_price:
                return True, f"TRAIL: {price:.2f} < {stop_price:.2f}"

        # Trend reversal (momentum goes negative)
        mom_12m = row.get('Mom_12m', 0)
        if not pd.isna(mom_12m) and mom_12m < -0.05:
            return True, f"TREND REVERSAL: Mom={mom_12m*100:.1f}%"

        return False, ""

    def run_backtest(self, start_date='1980-01-01', end_date='2024-12-31'):
        print(f"\nSmart Leverage Backtest: {start_date} to {end_date}")
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
            if i < 252:
                continue

            # Process exits and leverage updates
            to_close = []
            for ticker, pos in list(self.positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue

                row = self.data[ticker].loc[date]
                price = row['Close']

                # Update tracking
                if price > pos.highest_price:
                    pos.highest_price = price
                mom = row.get('Mom_12m', 0)
                if not pd.isna(mom) and mom > pos.peak_momentum:
                    pos.peak_momentum = mom

                # Check exit
                should_exit, exit_reason = self._check_exit(pos, date)
                if should_exit:
                    to_close.append((ticker, exit_reason, price))
                else:
                    # Update leverage (may increase or decrease)
                    new_lev, lev_reason = self._update_leverage(pos, date)
                    if lev_reason:
                        self.leverage_log.append({
                            'date': date, 'ticker': ticker,
                            'old_lev': pos.leverage, 'new_lev': new_lev,
                            'reason': lev_reason
                        })

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

            # New entries
            if len(self.positions) < PARAMS['max_positions']:
                for ticker in self.data:
                    if ticker in self.positions:
                        continue

                    should_enter, entry_reason = self._check_entry(ticker, date)
                    if should_enter and date in self.data[ticker].index:
                        row = self.data[ticker].loc[date]
                        price = row['Close']

                        # Get initial leverage based on trend strength
                        strength, _ = self._calculate_trend_strength(ticker, date)
                        initial_leverage = self._get_leverage_for_strength(strength)

                        pos_value = self.capital * PARAMS['base_position_size']
                        shares = pos_value / price

                        pos = Position(
                            ticker=ticker,
                            entry_date=date,
                            entry_price=price,
                            shares=shares,
                            leverage=initial_leverage,
                            highest_price=price,
                            peak_momentum=row.get('Mom_12m', 0) if not pd.isna(row.get('Mom_12m')) else 0,
                            entry_atr=row.get('ATR', 0) if not pd.isna(row.get('ATR')) else 0,
                            sector=self.sectors.get(ticker, 'unknown')
                        )
                        self.positions[ticker] = pos
                        self.capital -= pos_value

                        if len(self.positions) >= PARAMS['max_positions']:
                            break

            # Calculate portfolio value
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
                    avg_lev = np.mean([p.leverage for p in self.positions.values()]) if self.positions else 1.0
                    print(f"  {date.strftime('%Y-%m-%d')}: ${portfolio:,.0f} | CAGR: {cagr*100:.1f}% | Pos: {len(self.positions)} | AvgLev: {avg_lev:.1f}x")

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

        # Calculate average leverage when leveraged
        leveraged_trades = [t for t in self.trades if t.max_leverage > 1.0]
        avg_lev = np.mean([t.max_leverage for t in self.trades]) if self.trades else 1.0
        avg_lev_when_lev = np.mean([t.max_leverage for t in leveraged_trades]) if leveraged_trades else 1.0
        pct_leveraged = len(leveraged_trades) / len(self.trades) * 100 if self.trades else 0

        if self.trades:
            wins = [t for t in self.trades if t.pnl > 0]
            losses = [t for t in self.trades if t.pnl <= 0]
            win_rate = len(wins) / len(self.trades)
            avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
            avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0
        else:
            win_rate = avg_win = avg_loss = 0

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
            'avg_leverage_when_leveraged': round(avg_lev_when_lev, 2),
            'pct_trades_leveraged': round(pct_leveraged, 1),
        }

        # Save files
        equity_df.to_csv('smart_leverage_equity.csv')

        trades_df = pd.DataFrame([{
            'Entry': t.entry_date.strftime('%Y-%m-%d'),
            'Exit': t.exit_date.strftime('%Y-%m-%d'),
            'Ticker': t.ticker,
            'EntryPrice': round(t.entry_price, 2),
            'ExitPrice': round(t.exit_price, 2),
            'Leverage': t.max_leverage,
            'PnL$': round(t.pnl, 2),
            'PnL%': round(t.pnl_pct * 100, 2),
            'Days': t.days_held,
            'Reason': t.exit_reason
        } for t in self.trades])
        trades_df.to_csv('smart_leverage_trades.csv', index=False)

        # Save leverage decisions
        if self.leverage_log:
            lev_df = pd.DataFrame(self.leverage_log)
            lev_df.to_csv('smart_leverage_decisions.csv', index=False)

        return report


def main():
    print("\n" + "=" * 70)
    print("SMART LEVERAGE TREND-FOLLOWING BACKTEST")
    print("Aggressive leverage during confirmed trends, quick deleverage on weakness")
    print("=" * 70)

    bt = SmartLeverageBacktester('historical_data', 100000)
    r = bt.run_backtest()

    print("\n" + "=" * 70)
    print("SMART LEVERAGE RESULTS")
    print("=" * 70)
    print(f"""
Period:              {r['start_date']} to {r['end_date']} ({r['years']} years)
Initial:             ${r['initial_capital']:,}
Final:               ${r['final_equity']:,.2f}
Total Return:        {r['total_return']}%

CAGR:                {r['cagr']}%
Volatility:          {r['volatility']}%
Sharpe:              {r['sharpe_ratio']}
Max Drawdown:        {r['max_drawdown']}%

Trades:              {r['total_trades']}
Win Rate:            {r['win_rate']}%
Avg Win:             {r['avg_win']}%
Avg Loss:            {r['avg_loss']}%

LEVERAGE STATS:
  Avg Leverage:      {r['avg_leverage']}x
  Avg When Leveraged:{r['avg_leverage_when_leveraged']}x
  % Trades Leveraged:{r['pct_trades_leveraged']}%
""")
    print("=" * 70)

    return r


if __name__ == '__main__':
    main()
