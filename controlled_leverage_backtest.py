"""
CONTROLLED LEVERAGE Strategy
Target: 20% CAGR with -40% max drawdown

Key innovations:
1. Market regime filter - reduce leverage when SP500 is weak
2. Portfolio-level leverage cap
3. Volatility-adjusted position sizing
4. Faster exits, not just deleverage
5. Drawdown protection mode
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass


PARAMS = {
    # Trend confirmation
    'strong_momentum_12m': 0.12,
    'strong_momentum_3m': 0.04,
    'strong_momentum_1m': 0.015,
    'price_above_sma_pct': 0.03,

    # Leverage levels
    'leverage_weak': 1.0,
    'leverage_moderate': 1.5,
    'leverage_strong': 2.0,
    'leverage_very_strong': 2.5,

    # PORTFOLIO-LEVEL CONTROLS (NEW)
    'max_portfolio_leverage': 2.0,    # Cap total portfolio leverage
    'drawdown_protection_threshold': -0.15,  # Enter protection mode at -15% drawdown
    'drawdown_protection_leverage': 1.0,     # Max leverage in protection mode

    # Position sizing with volatility adjustment
    'base_position_size': 0.05,
    'max_positions': 12,
    'volatility_lookback': 20,
    'volatility_target': 0.15,        # Target 15% annualized vol per position

    # Deleverage triggers (more sensitive)
    'deleverage_pullback': 0.015,     # 1.5% pullback
    'deleverage_mom_decay': 0.30,     # 30% momentum decay
    'deleverage_volatility_spike': 1.25,  # 25% vol increase

    # EXIT triggers (not just deleverage)
    'exit_pullback': 0.04,            # 4% pullback = EXIT position
    'exit_mom_reversal': -0.02,       # 1-month momentum negative = EXIT

    # Stop losses (very tight)
    'stop_loss': -0.035,              # -3.5% stop
    'trailing_atr_base': 1.8,
    'trailing_atr_leveraged': 1.2,

    # Market regime (using SP500 as proxy)
    'regime_sma': 100,                # Use 100-day SMA for regime
    'regime_momentum': 63,            # 3-month momentum for regime
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
    entry_volatility: float = 0.0


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


class ControlledLeverageBacktester:
    def __init__(self, data_dir='historical_data', initial_capital=100000):
        self.data_dir = data_dir
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve = []
        self.peak_equity = initial_capital
        self.in_protection_mode = False

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

    def _load_all_data(self):
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
        df['Mom_12m'] = df['Close'].pct_change(252)
        df['Mom_3m'] = df['Close'].pct_change(63)
        df['Mom_1m'] = df['Close'].pct_change(21)
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA100'] = df['Close'].rolling(100).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['Dist_SMA200'] = (df['Close'] - df['SMA200']) / df['SMA200']

        df['TR'] = np.maximum(df['High'] - df['Low'],
                              np.maximum(abs(df['High'] - df['Close'].shift(1)),
                                        abs(df['Low'] - df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(14).mean()

        # Volatility (annualized)
        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(20).std() * np.sqrt(252)

        return df

    def _get_market_regime(self, date) -> str:
        """
        Determine market regime using SP500:
        - BULL: Price > SMA100 and 3m momentum > 0
        - BEAR: Price < SMA100 and 3m momentum < 0
        - NEUTRAL: Otherwise
        """
        if 'SP500' not in self.data or date not in self.data['SP500'].index:
            return 'NEUTRAL'

        row = self.data['SP500'].loc[date]
        price = row['Close']
        sma100 = row.get('SMA100', price)
        mom_3m = row.get('Mom_3m', 0)

        if pd.isna(sma100) or pd.isna(mom_3m):
            return 'NEUTRAL'

        if price > sma100 and mom_3m > 0:
            return 'BULL'
        elif price < sma100 and mom_3m < -0.05:
            return 'BEAR'
        else:
            return 'NEUTRAL'

    def _get_max_leverage_for_regime(self, regime: str) -> float:
        """Reduce max leverage based on market regime"""
        if self.in_protection_mode:
            return PARAMS['drawdown_protection_leverage']

        if regime == 'BULL':
            return PARAMS['leverage_very_strong']
        elif regime == 'NEUTRAL':
            return PARAMS['leverage_moderate']
        else:  # BEAR
            return 1.0  # No leverage in bear markets

    def _calculate_portfolio_leverage(self, date) -> float:
        """Calculate current total portfolio leverage"""
        if not self.positions:
            return 0

        total_leveraged_exposure = 0
        total_base_value = 0

        for ticker, pos in self.positions.items():
            if ticker in self.data and date in self.data[ticker].index:
                price = self.data[ticker].loc[date, 'Close']
                base_value = pos.shares * pos.entry_price
                leveraged_value = base_value * pos.leverage
                total_base_value += base_value
                total_leveraged_exposure += leveraged_value

        if total_base_value > 0:
            return total_leveraged_exposure / total_base_value
        return 0

    def _get_volatility_adjusted_size(self, ticker: str, date) -> float:
        """Adjust position size based on current volatility"""
        base_size = PARAMS['base_position_size']

        if ticker not in self.data or date not in self.data[ticker].index:
            return base_size

        vol = self.data[ticker].loc[date].get('Volatility', 0.15)
        if pd.isna(vol) or vol <= 0:
            vol = 0.15

        # Scale position inversely with volatility
        vol_scalar = PARAMS['volatility_target'] / vol
        vol_scalar = np.clip(vol_scalar, 0.5, 1.5)  # Limit adjustment

        return base_size * vol_scalar

    def _calculate_trend_strength(self, ticker, date) -> int:
        if ticker not in self.data or date not in self.data[ticker].index:
            return 0

        row = self.data[ticker].loc[date]
        score = 0

        mom_12m = row.get('Mom_12m', 0)
        mom_3m = row.get('Mom_3m', 0)
        mom_1m = row.get('Mom_1m', 0)
        dist_sma = row.get('Dist_SMA200', 0)
        sma50 = row.get('SMA50', 0)
        sma200 = row.get('SMA200', 0)

        if pd.isna(mom_12m) or mom_12m <= 0:
            return 0

        score += 1

        if mom_12m >= PARAMS['strong_momentum_12m']:
            score += 1
        if not pd.isna(mom_3m) and mom_3m >= PARAMS['strong_momentum_3m']:
            score += 1
        if not pd.isna(mom_1m) and mom_1m >= PARAMS['strong_momentum_1m']:
            score += 1
        if not pd.isna(dist_sma) and dist_sma >= PARAMS['price_above_sma_pct']:
            score += 1
        if not pd.isna(sma50) and not pd.isna(sma200) and sma50 > sma200:
            score += 1

        return min(score, 4)

    def _get_leverage_for_strength(self, strength, regime_max_leverage):
        if strength <= 1:
            base_lev = PARAMS['leverage_weak']
        elif strength == 2:
            base_lev = PARAMS['leverage_moderate']
        elif strength == 3:
            base_lev = PARAMS['leverage_strong']
        else:
            base_lev = PARAMS['leverage_very_strong']

        return min(base_lev, regime_max_leverage)

    def _check_exit_signals(self, pos, date) -> Tuple[bool, str]:
        """Check for EXIT signals (not just deleverage)"""
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return False, ""

        row = self.data[ticker].loc[date]
        price = row['Close']
        pnl = (price - pos.entry_price) / pos.entry_price

        # Stop loss
        if pnl <= PARAMS['stop_loss']:
            return True, f"STOP: {pnl*100:.1f}%"

        # Trailing stop (tighter when leveraged)
        atr = row.get('ATR', 0)
        if not pd.isna(atr) and pos.highest_price > 0:
            mult = PARAMS['trailing_atr_leveraged'] if pos.leverage > 1 else PARAMS['trailing_atr_base']
            stop = pos.highest_price - mult * atr
            if price < stop:
                return True, "TRAIL"

        # Large pullback = EXIT (not just deleverage)
        if pos.highest_price > 0:
            pullback = (pos.highest_price - price) / pos.highest_price
            if pullback >= PARAMS['exit_pullback']:
                return True, f"PULLBACK: {pullback*100:.1f}%"

        # Momentum reversal
        mom_1m = row.get('Mom_1m', 0)
        if not pd.isna(mom_1m) and mom_1m <= PARAMS['exit_mom_reversal']:
            return True, f"MOM_REV: {mom_1m*100:.1f}%"

        # Trend breakdown
        mom_12m = row.get('Mom_12m', 0)
        if not pd.isna(mom_12m) and mom_12m < -0.03:
            return True, "TREND_BREAK"

        return False, ""

    def _check_deleverage(self, pos, date) -> bool:
        """Check if we should reduce leverage"""
        ticker = pos.ticker
        if ticker not in self.data or date not in self.data[ticker].index:
            return False

        row = self.data[ticker].loc[date]
        price = row['Close']

        # Pullback from high
        if pos.highest_price > 0:
            pullback = (pos.highest_price - price) / pos.highest_price
            if pullback >= PARAMS['deleverage_pullback']:
                return True

        # Momentum decay
        current_mom = row.get('Mom_12m', 0)
        if not pd.isna(current_mom) and pos.peak_momentum > 0:
            if current_mom < pos.peak_momentum * (1 - PARAMS['deleverage_mom_decay']):
                return True

        # Volatility spike
        current_atr = row.get('ATR', 0)
        if not pd.isna(current_atr) and pos.entry_atr > 0:
            if current_atr > pos.entry_atr * PARAMS['deleverage_volatility_spike']:
                return True

        return False

    def run_backtest(self, start_date='1980-01-01', end_date='2024-12-31'):
        print(f"\nControlled Leverage Backtest: {start_date} to {end_date}")
        print("=" * 70)

        for ticker in self.data:
            self.data[ticker] = self._calculate_indicators(self.data[ticker])

        start_dt, end_dt = pd.Timestamp(start_date), pd.Timestamp(end_date)
        trading_dates = [d for d in self.all_dates if start_dt <= d <= end_dt]

        self.capital = self.initial_capital
        self.peak_equity = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.in_protection_mode = False

        for i, date in enumerate(trading_dates):
            if i < 252:
                continue

            # Get market regime
            regime = self._get_market_regime(date)
            max_regime_leverage = self._get_max_leverage_for_regime(regime)

            # Check portfolio-level leverage cap
            portfolio_leverage = self._calculate_portfolio_leverage(date)

            # Process positions
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

                # Check EXIT (not just deleverage)
                should_exit, reason = self._check_exit_signals(pos, date)
                if should_exit:
                    to_close.append((ticker, reason, price))
                else:
                    # Check deleverage
                    if self._check_deleverage(pos, date) and pos.leverage > 1:
                        pos.leverage = 1.0
                    # Also reduce leverage if regime is bearish
                    if pos.leverage > max_regime_leverage:
                        pos.leverage = max_regime_leverage
                    # Or if portfolio leverage is too high
                    if portfolio_leverage > PARAMS['max_portfolio_leverage'] and pos.leverage > 1:
                        pos.leverage = max(1.0, pos.leverage - 0.5)

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

            # Calculate current equity
            portfolio_value = self.capital
            for ticker, pos in self.positions.items():
                if ticker in self.data and date in self.data[ticker].index:
                    price = self.data[ticker].loc[date, 'Close']
                    upnl = (price - pos.entry_price) * pos.shares * pos.leverage
                    portfolio_value += pos.shares * pos.entry_price + upnl

            # Update peak and check for protection mode (only after some growth)
            if portfolio_value > self.peak_equity:
                self.peak_equity = portfolio_value
                self.in_protection_mode = False

            # Only enter protection mode if we've had significant gains first
            # AND then experienced a drawdown
            if self.peak_equity > self.initial_capital * 1.1:  # Only after 10% gain
                current_dd = (portfolio_value - self.peak_equity) / self.peak_equity
                if current_dd < PARAMS['drawdown_protection_threshold']:
                    self.in_protection_mode = True

            # New entries (only if not in severe bear market)
            # Allow entries in protection mode but with reduced leverage
            can_enter = (regime != 'BEAR') or (regime == 'BEAR' and not self.in_protection_mode)
            if can_enter and len(self.positions) < PARAMS['max_positions']:
                for ticker in self.data:
                    if ticker in self.positions:
                        continue

                    strength = self._calculate_trend_strength(ticker, date)
                    if strength >= 2 and date in self.data[ticker].index:
                        row = self.data[ticker].loc[date]
                        price = row['Close']

                        # Volatility-adjusted position size
                        pos_size = self._get_volatility_adjusted_size(ticker, date)
                        pos_value = self.capital * pos_size
                        shares = pos_value / price

                        # Initial leverage based on strength and regime
                        # Reduce leverage in protection mode
                        if self.in_protection_mode:
                            initial_leverage = 1.0
                        else:
                            initial_leverage = self._get_leverage_for_strength(strength, max_regime_leverage)

                        pos = Position(
                            ticker=ticker,
                            entry_date=date,
                            entry_price=price,
                            shares=shares,
                            leverage=initial_leverage,
                            highest_price=price,
                            peak_momentum=row.get('Mom_12m', 0) if not pd.isna(row.get('Mom_12m')) else 0,
                            entry_atr=row.get('ATR', 0) if not pd.isna(row.get('ATR')) else 0,
                            entry_volatility=row.get('Volatility', 0.15) if not pd.isna(row.get('Volatility')) else 0.15
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
                    avg_lev = np.mean([p.leverage for p in self.positions.values()]) if self.positions else 0
                    mode = "PROTECT" if self.in_protection_mode else regime
                    print(f"  {date.strftime('%Y-%m-%d')}: ${portfolio_value:,.0f} | CAGR: {cagr*100:.1f}% | DD: {dd:.1f}% | {mode} | AvgLev: {avg_lev:.1f}x")

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

        equity_df.to_csv('controlled_leverage_equity.csv')
        trades_df = pd.DataFrame([{
            'Entry': t.entry_date.strftime('%Y-%m-%d'),
            'Exit': t.exit_date.strftime('%Y-%m-%d'),
            'Ticker': t.ticker,
            'Lev': t.max_leverage,
            'PnL%': round(t.pnl_pct * 100, 2),
            'Reason': t.exit_reason
        } for t in self.trades])
        trades_df.to_csv('controlled_leverage_trades.csv', index=False)

        return report


def main():
    print("\n" + "=" * 70)
    print("CONTROLLED LEVERAGE STRATEGY")
    print("Target: 20% CAGR with -40% Max Drawdown")
    print("=" * 70)

    bt = ControlledLeverageBacktester('historical_data', 100000)
    r = bt.run_backtest()

    print("\n" + "=" * 70)
    print("CONTROLLED LEVERAGE RESULTS")
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
    print("=" * 70)

    # Check if we hit target
    if r['cagr'] >= 20 and r['max_drawdown'] >= -40:
        print("\n*** TARGET ACHIEVED: 20%+ CAGR with <40% Drawdown! ***")
    elif r['cagr'] >= 18 and r['max_drawdown'] >= -45:
        print("\n*** CLOSE TO TARGET: Needs minor tuning ***")

    return r


if __name__ == '__main__':
    main()
