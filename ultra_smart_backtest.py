"""
ULTRA-SMART Trend-Following Strategy
Goal: 20%+ CAGR with <45% Max Drawdown

Key innovations:
1. Volatility targeting - reduce exposure in high-vol regimes
2. Profit locking - trailing stops tighten as gains increase
3. Multi-timeframe momentum confirmation
4. Instant deleverage on ANY weakness signal
5. Only leverage after sustained trend confirmation
6. Cross-asset breadth confirmation
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass


PARAMS = {
    # ENTRY: Very selective - need strong multi-timeframe confirmation
    'entry_mom_12m': 0.12,       # 12% 12m momentum
    'entry_mom_6m': 0.06,        # 6% 6m momentum
    'entry_mom_3m': 0.03,        # 3% 3m momentum
    'entry_mom_1m': 0.01,        # 1% 1m momentum
    'entry_above_sma200': True,  # Must be above SMA200
    'entry_golden_cross': True,  # SMA50 > SMA200

    # LEVERAGE: Only apply after trend proven for X days
    'leverage_confirmation_days': 10,  # Wait 10 days profitable before leverage
    'leverage_min_profit': 0.03,       # Need 3% profit before leverage
    'leverage_tier_1': 1.0,            # Base (first 10 days)
    'leverage_tier_2': 1.5,            # After confirmation
    'leverage_tier_3': 2.0,            # Strong trend (all timeframes + breakout)
    'leverage_tier_4': 2.5,            # Very strong (sustained momentum acceleration)

    # VOLATILITY TARGETING - Key innovation
    'target_volatility': 0.15,         # Target 15% annualized vol
    'vol_lookback': 21,                # 21-day realized vol
    'vol_max_multiplier': 1.5,         # Max 1.5x position in low vol
    'vol_min_multiplier': 0.3,         # Min 0.3x position in high vol

    # PROFIT LOCKING - Trailing stops tighten with gains
    'trail_base_atr': 2.5,             # Base: 2.5 ATR
    'trail_profit_5pct': 2.0,          # After 5% gain: 2.0 ATR
    'trail_profit_10pct': 1.5,         # After 10% gain: 1.5 ATR
    'trail_profit_20pct': 1.0,         # After 20% gain: 1.0 ATR (lock it in!)

    # INSTANT DELEVERAGE TRIGGERS (any one = immediate deleverage)
    'delev_pullback': 0.015,           # 1.5% pullback from high
    'delev_mom_1m_negative': True,     # 1m momentum goes negative
    'delev_below_sma50': True,         # Price drops below SMA50
    'delev_vol_spike': 1.3,            # Volatility up 30%

    # EXIT TRIGGERS
    'exit_stop': -0.03,                # 3% hard stop
    'exit_mom_reversal': -0.03,        # 3m momentum reversal
    'exit_below_sma200': True,         # Price below SMA200

    # POSITION SIZING
    'base_position_size': 0.06,
    'max_positions': 12,
    'max_sector_exposure': 0.35,       # Max 35% per sector

    # REGIME FILTER - Portfolio level
    'regime_min_uptrends': 0.4,        # At least 40% of assets in uptrend
}


@dataclass
class Position:
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: float
    leverage: float = 1.0
    highest_price: float = 0.0
    highest_profit_pct: float = 0.0
    days_held: int = 0
    confirmed: bool = False
    entry_volatility: float = 0.15
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


class UltraSmartBacktester:
    def __init__(self, data_dir: str = 'historical_data', initial_capital: float = 100000):
        self.data_dir = data_dir
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve = []
        self.peak_equity = initial_capital

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

        # Moving averages
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()

        # Multi-timeframe momentum
        df['Mom_12m'] = df['Close'].pct_change(252)
        df['Mom_6m'] = df['Close'].pct_change(126)
        df['Mom_3m'] = df['Close'].pct_change(63)
        df['Mom_1m'] = df['Close'].pct_change(21)
        df['Mom_1w'] = df['Close'].pct_change(5)

        # Momentum acceleration (rate of change of momentum)
        df['Mom_Accel'] = df['Mom_1m'] - df['Mom_1m'].shift(5)

        # Volatility (for position sizing)
        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(PARAMS['vol_lookback']).std() * np.sqrt(252)

        # ATR for trailing stops
        df['TR'] = np.maximum(df['High'] - df['Low'],
                              np.maximum(abs(df['High'] - df['Close'].shift(1)),
                                        abs(df['Low'] - df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(14).mean()

        # Donchian for breakouts
        df['Donchian_High'] = df['High'].rolling(20).max()
        df['Donchian_Low'] = df['Low'].rolling(20).min()

        return df

    def _get_market_breadth(self, date: datetime) -> float:
        """Calculate % of assets in uptrend (above SMA200 with positive momentum)"""
        uptrends = 0
        total = 0

        for ticker, df in self.data.items():
            if date not in df.index:
                continue
            row = df.loc[date]
            sma200 = row.get('SMA200')
            mom_3m = row.get('Mom_3m')

            if pd.isna(sma200) or pd.isna(mom_3m):
                continue

            total += 1
            if row['Close'] > sma200 and mom_3m > 0:
                uptrends += 1

        return uptrends / total if total > 0 else 0.5

    def _get_volatility_multiplier(self, ticker: str, date: datetime) -> float:
        """Volatility targeting - reduce size in high vol, increase in low vol"""
        if ticker not in self.data or date not in self.data[ticker].index:
            return 1.0

        vol = self.data[ticker].loc[date].get('Volatility')
        if pd.isna(vol) or vol <= 0:
            return 1.0

        # Target volatility adjustment
        multiplier = PARAMS['target_volatility'] / vol

        # Clamp to reasonable range
        multiplier = max(PARAMS['vol_min_multiplier'],
                        min(PARAMS['vol_max_multiplier'], multiplier))

        return multiplier

    def _get_sector_exposure(self, sector: str) -> float:
        """Calculate current exposure to a sector"""
        total_value = self.capital
        sector_value = 0

        for ticker, pos in self.positions.items():
            pos_value = pos.shares * pos.entry_price
            total_value += pos_value
            if pos.sector == sector:
                sector_value += pos_value

        return sector_value / total_value if total_value > 0 else 0

    def _check_entry(self, ticker: str, date: datetime) -> Tuple[bool, int]:
        """Check entry conditions - returns (can_enter, strength_score)"""
        if ticker not in self.data or date not in self.data[ticker].index:
            return False, 0

        row = self.data[ticker].loc[date]
        score = 0

        # Multi-timeframe momentum check
        mom_12m = row.get('Mom_12m', 0)
        mom_6m = row.get('Mom_6m', 0)
        mom_3m = row.get('Mom_3m', 0)
        mom_1m = row.get('Mom_1m', 0)

        if pd.isna(mom_12m) or pd.isna(mom_6m) or pd.isna(mom_3m) or pd.isna(mom_1m):
            return False, 0

        if mom_12m > PARAMS['entry_mom_12m']:
            score += 1
        if mom_6m > PARAMS['entry_mom_6m']:
            score += 1
        if mom_3m > PARAMS['entry_mom_3m']:
            score += 1
        if mom_1m > PARAMS['entry_mom_1m']:
            score += 1

        # Need at least 3 timeframes aligned
        if score < 3:
            return False, 0

        # SMA200 check
        sma200 = row.get('SMA200')
        if PARAMS['entry_above_sma200'] and (pd.isna(sma200) or row['Close'] <= sma200):
            return False, 0

        # Golden cross check
        sma50 = row.get('SMA50')
        if PARAMS['entry_golden_cross'] and (pd.isna(sma50) or pd.isna(sma200) or sma50 <= sma200):
            return False, 0

        # Breakout bonus
        donchian_high = row.get('Donchian_High')
        if not pd.isna(donchian_high) and row['Close'] >= donchian_high:
            score += 1

        # Momentum acceleration bonus
        mom_accel = row.get('Mom_Accel')
        if not pd.isna(mom_accel) and mom_accel > 0.01:
            score += 1

        return True, score

    def _get_dynamic_trailing_stop(self, pos: Position, current_price: float, atr: float) -> float:
        """Trailing stop that tightens as profit increases"""
        profit_pct = (current_price - pos.entry_price) / pos.entry_price

        if profit_pct >= 0.20:
            atr_mult = PARAMS['trail_profit_20pct']
        elif profit_pct >= 0.10:
            atr_mult = PARAMS['trail_profit_10pct']
        elif profit_pct >= 0.05:
            atr_mult = PARAMS['trail_profit_5pct']
        else:
            atr_mult = PARAMS['trail_base_atr']

        # Tighter stop when leveraged
        if pos.leverage > 1.0:
            atr_mult *= 0.7

        return pos.highest_price - atr_mult * atr

    def _check_deleverage(self, pos: Position, date: datetime) -> bool:
        """Check if we should immediately reduce leverage"""
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return False

        row = self.data[ticker].loc[date]
        price = row['Close']

        # Pullback from high
        if pos.highest_price > 0:
            pullback = (pos.highest_price - price) / pos.highest_price
            if pullback > PARAMS['delev_pullback']:
                return True

        # 1m momentum negative
        mom_1m = row.get('Mom_1m')
        if PARAMS['delev_mom_1m_negative'] and not pd.isna(mom_1m) and mom_1m < 0:
            return True

        # Below SMA50
        sma50 = row.get('SMA50')
        if PARAMS['delev_below_sma50'] and not pd.isna(sma50) and price < sma50:
            return True

        # Volatility spike
        vol = row.get('Volatility')
        if not pd.isna(vol) and pos.entry_volatility > 0:
            if vol > pos.entry_volatility * PARAMS['delev_vol_spike']:
                return True

        return False

    def _check_exit(self, pos: Position, date: datetime) -> Tuple[bool, str]:
        """Check exit conditions"""
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return False, ""

        row = self.data[ticker].loc[date]
        price = row['Close']
        pnl_pct = (price - pos.entry_price) / pos.entry_price

        # Hard stop loss
        if pnl_pct <= PARAMS['exit_stop']:
            return True, "STOP"

        # Dynamic trailing stop
        atr = row.get('ATR')
        if not pd.isna(atr) and pos.highest_price > 0:
            trail_stop = self._get_dynamic_trailing_stop(pos, price, atr)
            if price < trail_stop:
                return True, "TRAIL"

        # Momentum reversal
        mom_3m = row.get('Mom_3m')
        if not pd.isna(mom_3m) and mom_3m < PARAMS['exit_mom_reversal']:
            return True, "MOM_REV"

        # Below SMA200
        sma200 = row.get('SMA200')
        if PARAMS['exit_below_sma200'] and not pd.isna(sma200) and price < sma200:
            return True, "SMA200"

        return False, ""

    def _update_leverage(self, pos: Position, date: datetime, strength: int):
        """Update leverage based on position status and trend strength"""
        # First check for deleverage triggers
        if self._check_deleverage(pos, date):
            pos.leverage = 1.0
            pos.confirmed = False
            return

        # Need to be confirmed (profitable for X days) before leverage
        if not pos.confirmed:
            if pos.days_held >= PARAMS['leverage_confirmation_days']:
                current_profit = 0
                if pos.ticker in self.data and date in self.data[pos.ticker].index:
                    price = self.data[pos.ticker].loc[date, 'Close']
                    current_profit = (price - pos.entry_price) / pos.entry_price

                if current_profit >= PARAMS['leverage_min_profit']:
                    pos.confirmed = True
            else:
                return  # Keep at 1x until confirmed

        # Assign leverage based on strength
        if strength >= 6:
            pos.leverage = PARAMS['leverage_tier_4']
        elif strength >= 5:
            pos.leverage = PARAMS['leverage_tier_3']
        elif strength >= 4:
            pos.leverage = PARAMS['leverage_tier_2']
        else:
            pos.leverage = PARAMS['leverage_tier_1']

    def run_backtest(self, start_date='1980-01-01', end_date='2024-12-31'):
        print(f"\nUltra-Smart backtest: {start_date} to {end_date}")
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

            # Check market breadth (regime filter)
            breadth = self._get_market_breadth(date)
            allow_new_entries = breadth >= PARAMS['regime_min_uptrends']

            # Process existing positions
            to_close = []
            for ticker, pos in list(self.positions.items()):
                if ticker not in self.data or date not in self.data[ticker].index:
                    continue

                row = self.data[ticker].loc[date]
                price = row['Close']

                # Update tracking
                pos.days_held += 1
                if price > pos.highest_price:
                    pos.highest_price = price

                profit_pct = (price - pos.entry_price) / pos.entry_price
                if profit_pct > pos.highest_profit_pct:
                    pos.highest_profit_pct = profit_pct

                # Check exit
                should_exit, reason = self._check_exit(pos, date)
                if should_exit:
                    to_close.append((ticker, reason, price))
                else:
                    # Update leverage
                    _, strength = self._check_entry(ticker, date)
                    self._update_leverage(pos, date, strength)

            # Execute exits
            for ticker, reason, price in to_close:
                pos = self.positions[ticker]
                pnl = (price - pos.entry_price) * pos.shares * pos.leverage
                pnl_pct = (price - pos.entry_price) / pos.entry_price * pos.leverage
                self.trades.append(Trade(
                    ticker, pos.entry_date, date, pos.entry_price, price,
                    pos.shares, pos.leverage, pnl, pnl_pct, pos.days_held, reason
                ))
                self.capital += pos.shares * pos.entry_price + pnl
                del self.positions[ticker]

            # New entries (only if breadth is good)
            if allow_new_entries and len(self.positions) < PARAMS['max_positions']:
                # Sort candidates by strength
                candidates = []
                for ticker in self.data:
                    if ticker in self.positions:
                        continue
                    can_enter, strength = self._check_entry(ticker, date)
                    if can_enter:
                        candidates.append((ticker, strength))

                # Take strongest first
                candidates.sort(key=lambda x: -x[1])

                for ticker, strength in candidates:
                    if len(self.positions) >= PARAMS['max_positions']:
                        break

                    # Check sector exposure
                    sector = self.sectors.get(ticker, 'unknown')
                    if self._get_sector_exposure(sector) >= PARAMS['max_sector_exposure']:
                        continue

                    if date not in self.data[ticker].index:
                        continue

                    row = self.data[ticker].loc[date]
                    price = row['Close']

                    # Volatility-adjusted position size
                    vol_mult = self._get_volatility_multiplier(ticker, date)
                    pos_size = PARAMS['base_position_size'] * vol_mult
                    pos_value = self.capital * pos_size
                    shares = pos_value / price

                    entry_vol = row.get('Volatility', 0.15)
                    if pd.isna(entry_vol):
                        entry_vol = 0.15

                    pos = Position(
                        ticker=ticker,
                        entry_date=date,
                        entry_price=price,
                        shares=shares,
                        leverage=1.0,  # Start at 1x, confirm before leverage
                        highest_price=price,
                        highest_profit_pct=0.0,
                        days_held=0,
                        confirmed=False,
                        entry_volatility=entry_vol,
                        sector=sector
                    )
                    self.positions[ticker] = pos
                    self.capital -= pos_value

            # Calculate portfolio value
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
                    print(f"  {date.strftime('%Y-%m-%d')}: ${portfolio_value:,.0f} | CAGR: {cagr*100:.1f}% | DD: {dd:.1f}% | Breadth: {breadth:.0%}")

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

        # Calculate Calmar ratio (CAGR / Max DD)
        calmar = abs(cagr / max_dd) if max_dd != 0 else 0

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
            'calmar_ratio': round(calmar, 2),
            'max_drawdown': round(max_dd * 100, 2),
            'total_trades': len(self.trades),
            'win_rate': round(win_rate * 100, 2),
            'avg_win': round(avg_win * 100, 2),
            'avg_loss': round(avg_loss * 100, 2),
            'avg_leverage': round(avg_lev, 2),
        }

        equity_df.to_csv('ultra_smart_equity_curve.csv')

        return report


def main():
    print("\n" + "=" * 70)
    print("ULTRA-SMART TREND-FOLLOWING BACKTEST")
    print("Goal: 20%+ CAGR with <45% Max Drawdown")
    print("=" * 70)

    bt = UltraSmartBacktester('historical_data', 100000)
    r = bt.run_backtest()

    print("\n" + "=" * 70)
    print("ULTRA-SMART BACKTEST RESULTS")
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
""")

    return r


if __name__ == '__main__':
    main()
